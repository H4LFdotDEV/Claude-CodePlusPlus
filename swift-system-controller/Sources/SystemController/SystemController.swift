// SystemController.swift
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC
//
// Main entry point for system control via macOS Accessibility API.
// Provides click, type, screen reading, and window management capabilities.

import Foundation
import ApplicationServices
import CoreGraphics
import AppKit

// MARK: - Permission Levels

public enum PermissionLevel: Int, Codable {
    case sandboxed = 0      // Project files only
    case standard = 1       // + MCP tools, allowlisted commands
    case automation = 2     // + AppleScript/JXA for any app
    case accessibility = 3  // + Full screen control
    case administrator = 4  // + SSH to remote hosts
    case unrestricted = 5   // Everything the user can do
}

// MARK: - Errors

public enum SystemControllerError: Error {
    case accessibilityError(String)
    case windowError(String)
}

// MARK: - Action Results

public enum ActionResult {
    case success
    case permissionDenied(String)
    case rateLimited(String)
    case failure(String)
    
    public var isSuccess: Bool {
        if case .success = self { return true }
        return false
    }
    
    public func toDict() -> [String: Any] {
        switch self {
        case .success:
            return ["status": "success"]
        case .permissionDenied(let reason):
            return ["status": "error", "error": "permission_denied", "reason": reason]
        case .rateLimited(let reason):
            return ["status": "error", "error": "rate_limited", "reason": reason]
        case .failure(let reason):
            return ["status": "error", "error": "failure", "reason": reason]
        }
    }
}

// MARK: - Mouse Button

public enum MouseButton: String, Codable {
    case left
    case right
    case middle
    
    var downEventType: CGEventType {
        switch self {
        case .left: return .leftMouseDown
        case .right: return .rightMouseDown
        case .middle: return .otherMouseDown
        }
    }
    
    var upEventType: CGEventType {
        switch self {
        case .left: return .leftMouseUp
        case .right: return .rightMouseUp
        case .middle: return .otherMouseUp
        }
    }
    
    var cgButton: CGMouseButton {
        switch self {
        case .left: return .left
        case .right: return .right
        case .middle: return .center
        }
    }
}

// MARK: - Keyboard Modifiers

public enum Modifier: String, Codable {
    case cmd
    case ctrl
    case alt
    case shift
    
    var cgFlag: CGEventFlags {
        switch self {
        case .cmd: return .maskCommand
        case .ctrl: return .maskControl
        case .alt: return .maskAlternate
        case .shift: return .maskShift
        }
    }
}

// MARK: - Element Info

public struct ElementInfo: Codable {
    public let role: String?
    public let title: String?
    public let value: String?
    public let enabled: Bool
    public let position: CGPoint?
    public let size: CGSize?
    
    public init(from element: AXUIElement) {
        self.role = ElementInfo.getAttribute(element, kAXRoleAttribute) as? String
        self.title = ElementInfo.getAttribute(element, kAXTitleAttribute) as? String
        self.value = ElementInfo.getAttribute(element, kAXValueAttribute) as? String
        self.enabled = (ElementInfo.getAttribute(element, kAXEnabledAttribute) as? Bool) ?? false
        
        if let positionValue = ElementInfo.getAttribute(element, kAXPositionAttribute),
           CFGetTypeID(positionValue) == AXValueGetTypeID() {
            let axValue = unsafeBitCast(positionValue, to: AXValue.self)
            var point = CGPoint.zero
            AXValueGetValue(axValue, .cgPoint, &point)
            self.position = point
        } else {
            self.position = nil
        }

        if let sizeValue = ElementInfo.getAttribute(element, kAXSizeAttribute),
           CFGetTypeID(sizeValue) == AXValueGetTypeID() {
            let axValue = unsafeBitCast(sizeValue, to: AXValue.self)
            var size = CGSize.zero
            AXValueGetValue(axValue, .cgSize, &size)
            self.size = size
        } else {
            self.size = nil
        }
    }
    
    private static func getAttribute(_ element: AXUIElement, _ attribute: String) -> AnyObject? {
        var value: AnyObject?
        let result = AXUIElementCopyAttributeValue(element, attribute as CFString, &value)
        return result == .success ? value : nil
    }
    
    public func toDict() -> [String: Any] {
        var dict: [String: Any] = [
            "enabled": enabled
        ]
        if let role = role { dict["role"] = role }
        if let title = title { dict["title"] = title }
        if let value = value { dict["value"] = value }
        if let pos = position { dict["position"] = ["x": pos.x, "y": pos.y] }
        if let s = size { dict["size"] = ["width": s.width, "height": s.height] }
        return dict
    }
}

// MARK: - Window Info

public struct WindowInfo: Codable {
    public let appName: String
    public let windowTitle: String
    public let bounds: CGRect
    public let pid: pid_t
    
    public func toDict() -> [String: Any] {
        return [
            "app_name": appName,
            "window_title": windowTitle,
            "bounds": [
                "x": bounds.origin.x,
                "y": bounds.origin.y,
                "width": bounds.size.width,
                "height": bounds.size.height
            ],
            "pid": pid
        ]
    }
}

// MARK: - Controller Configuration

public struct ControllerConfig {
    public let logPath: String
    public let rateLimit: RateLimitConfig
    
    public static let `default` = ControllerConfig(
        logPath: "~/.claude-code-pp/logs/system-controller.log",
        rateLimit: RateLimitConfig.default
    )
    
    public init(logPath: String, rateLimit: RateLimitConfig) {
        self.logPath = logPath
        self.rateLimit = rateLimit
    }
}

public struct RateLimitConfig {
    public let maxClicksPerSecond: Int
    public let maxKeysPerSecond: Int
    
    public static let `default` = RateLimitConfig(
        maxClicksPerSecond: 10,
        maxKeysPerSecond: 1000
    )
}

// MARK: - Main Controller

public class SystemController {
    
    private let permissionManager: PermissionManager
    private let logger: ActionLogger
    private let rateLimiter: RateLimiter
    
    public var currentPermissionLevel: PermissionLevel {
        permissionManager.currentLevel
    }
    
    public init(config: ControllerConfig = .default) {
        self.permissionManager = PermissionManager()
        self.logger = ActionLogger(path: config.logPath)
        self.rateLimiter = RateLimiter(config: config.rateLimit)
    }
    
    // MARK: - Permission Check
    
    public func checkAccessibilityPermission() -> Bool {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: false]
        return AXIsProcessTrustedWithOptions(options as CFDictionary)
    }
    
    public func requestAccessibilityPermission() {
        let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: true]
        _ = AXIsProcessTrustedWithOptions(options as CFDictionary)
    }
    
    // MARK: - Screen Reading
    
    public func readElementAt(x: CGFloat, y: CGFloat) -> ElementInfo? {
        guard permissionManager.check(.accessibility) else {
            return nil
        }
        
        let point = CGPoint(x: x, y: y)
        var element: AXUIElement?
        
        let result = AXUIElementCopyElementAtPosition(
            AXUIElementCreateSystemWide(),
            Float(point.x),
            Float(point.y),
            &element
        )
        
        guard result == .success, let element = element else {
            return nil
        }
        
        logger.log(.screenRead(point: point))
        return ElementInfo(from: element)
    }
    
    public func readActiveWindow() -> WindowInfo? {
        guard permissionManager.check(.accessibility) else {
            return nil
        }
        
        let systemWide = AXUIElementCreateSystemWide()
        var focusedApp: AnyObject?
        
        guard AXUIElementCopyAttributeValue(
            systemWide,
            kAXFocusedApplicationAttribute as CFString,
            &focusedApp
        ) == .success else {
            return nil
        }
        
        // focusedApp is AnyObject but should be AXUIElement - use unsafeBitCast since we verified success
        guard let fa = focusedApp else { return nil }
        let appElement = unsafeBitCast(fa, to: AXUIElement.self)

        // Get app name
        var appName: AnyObject?
        AXUIElementCopyAttributeValue(appElement, kAXTitleAttribute as CFString, &appName)

        // Get focused window
        var focusedWindow: AnyObject?
        guard AXUIElementCopyAttributeValue(
            appElement,
            kAXFocusedWindowAttribute as CFString,
            &focusedWindow
        ) == .success, let fw = focusedWindow else {
            return nil
        }
        let windowElement = unsafeBitCast(fw, to: AXUIElement.self)

        // Get window title
        var windowTitle: AnyObject?
        AXUIElementCopyAttributeValue(windowElement, kAXTitleAttribute as CFString, &windowTitle)

        // Get window bounds
        var position = CGPoint.zero
        var size = CGSize.zero

        var posValue: AnyObject?
        if AXUIElementCopyAttributeValue(windowElement, kAXPositionAttribute as CFString, &posValue) == .success,
           let pv = posValue, CFGetTypeID(pv) == AXValueGetTypeID() {
            let axPosValue = unsafeBitCast(pv, to: AXValue.self)
            AXValueGetValue(axPosValue, .cgPoint, &position)
        }

        var sizeValue: AnyObject?
        if AXUIElementCopyAttributeValue(windowElement, kAXSizeAttribute as CFString, &sizeValue) == .success,
           let sv = sizeValue, CFGetTypeID(sv) == AXValueGetTypeID() {
            let axSizeValue = unsafeBitCast(sv, to: AXValue.self)
            AXValueGetValue(axSizeValue, .cgSize, &size)
        }
        
        // Get PID
        var pid: pid_t = 0
        AXUIElementGetPid(appElement, &pid)
        
        logger.log(.windowRead)
        
        return WindowInfo(
            appName: (appName as? String) ?? "Unknown",
            windowTitle: (windowTitle as? String) ?? "Untitled",
            bounds: CGRect(origin: position, size: size),
            pid: pid
        )
    }
    
    public func findElements(role: String? = nil, title: String? = nil, app: String? = nil) -> [ElementInfo] {
        guard permissionManager.check(.accessibility) else {
            return []
        }

        var results: [ElementInfo] = []

        // Get all running applications
        let workspace = NSWorkspace.shared
        let runningApps = workspace.runningApplications.filter { $0.activationPolicy == .regular }

        for runningApp in runningApps {
            // Filter by app name if specified
            if let appFilter = app, runningApp.localizedName != appFilter {
                continue
            }

            let appElement = AXUIElementCreateApplication(runningApp.processIdentifier)

            // Get windows for this app
            var windowsValue: AnyObject?
            guard AXUIElementCopyAttributeValue(appElement, kAXWindowsAttribute as CFString, &windowsValue) == .success,
                  let windows = windowsValue as? [AXUIElement] else {
                continue
            }

            for window in windows {
                searchElement(window, role: role, title: title, results: &results, depth: 0, maxDepth: 10)
            }
        }

        return results
    }

    private func searchElement(_ element: AXUIElement, role: String?, title: String?, results: inout [ElementInfo], depth: Int, maxDepth: Int) {
        guard depth < maxDepth else { return }

        let info = ElementInfo(from: element)

        // Check if this element matches the criteria
        var matches = true
        if let roleFilter = role, info.role != roleFilter {
            matches = false
        }
        if let titleFilter = title, info.title != titleFilter {
            matches = false
        }

        if matches && (role != nil || title != nil) {
            results.append(info)
        }

        // Get children and recurse
        var childrenValue: AnyObject?
        if AXUIElementCopyAttributeValue(element, kAXChildrenAttribute as CFString, &childrenValue) == .success,
           let children = childrenValue as? [AXUIElement] {
            for child in children {
                searchElement(child, role: role, title: title, results: &results, depth: depth + 1, maxDepth: maxDepth)
            }
        }
    }
    
    // MARK: - Mouse Control
    
    public func click(at point: CGPoint, button: MouseButton = .left) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        guard rateLimiter.allowClick() else {
            return .rateLimited("Too many clicks, pausing for safety")
        }
        
        logger.log(.click(point: point, button: button))
        
        let mouseDown = CGEvent(
            mouseEventSource: nil,
            mouseType: button.downEventType,
            mouseCursorPosition: point,
            mouseButton: button.cgButton
        )
        let mouseUp = CGEvent(
            mouseEventSource: nil,
            mouseType: button.upEventType,
            mouseCursorPosition: point,
            mouseButton: button.cgButton
        )
        
        mouseDown?.post(tap: .cghidEventTap)
        usleep(50000) // 50ms delay
        mouseUp?.post(tap: .cghidEventTap)
        
        return .success
    }
    
    public func doubleClick(at point: CGPoint) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        guard rateLimiter.allowClick() && rateLimiter.allowClick() else {
            return .rateLimited("Too many clicks, pausing for safety")
        }
        
        logger.log(.doubleClick(point: point))
        
        for _ in 0..<2 {
            let mouseDown = CGEvent(
                mouseEventSource: nil,
                mouseType: .leftMouseDown,
                mouseCursorPosition: point,
                mouseButton: .left
            )
            let mouseUp = CGEvent(
                mouseEventSource: nil,
                mouseType: .leftMouseUp,
                mouseCursorPosition: point,
                mouseButton: .left
            )
            
            mouseDown?.setIntegerValueField(.mouseEventClickState, value: 2)
            mouseUp?.setIntegerValueField(.mouseEventClickState, value: 2)
            
            mouseDown?.post(tap: .cghidEventTap)
            mouseUp?.post(tap: .cghidEventTap)
        }
        
        return .success
    }
    
    public func moveMouse(to point: CGPoint) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        let moveEvent = CGEvent(
            mouseEventSource: nil,
            mouseType: .mouseMoved,
            mouseCursorPosition: point,
            mouseButton: .left
        )
        
        moveEvent?.post(tap: .cghidEventTap)
        return .success
    }
    
    public func scroll(at point: CGPoint, deltaX: Int32 = 0, deltaY: Int32) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        // Move to position first
        _ = moveMouse(to: point)
        
        let scrollEvent = CGEvent(
            scrollWheelEvent2Source: nil,
            units: .pixel,
            wheelCount: 2,
            wheel1: deltaY,
            wheel2: deltaX,
            wheel3: 0
        )
        
        scrollEvent?.post(tap: .cghidEventTap)
        logger.log(.scroll(point: point, deltaX: deltaX, deltaY: deltaY))
        
        return .success
    }
    
    // MARK: - Keyboard Control
    
    public func typeText(_ text: String, delayBetweenKeys: UInt32 = 10000) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        guard rateLimiter.allowKeys(count: text.count) else {
            return .rateLimited("Input too fast, pausing for safety")
        }
        
        // Log truncated text for privacy
        let logText = text.count > 50 ? String(text.prefix(50)) + "..." : text
        logger.log(.type(text: logText))
        
        let source = CGEventSource(stateID: .hidSystemState)
        
        for char in text {
            if let (keyCode, needsShift) = KeyCodeMap.mapping(for: char) {
                var flags: CGEventFlags = []
                if needsShift {
                    flags.insert(.maskShift)
                }
                
                let keyDown = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: true)
                let keyUp = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: false)
                
                keyDown?.flags = flags
                keyUp?.flags = flags
                
                keyDown?.post(tap: .cghidEventTap)
                keyUp?.post(tap: .cghidEventTap)
                
                usleep(delayBetweenKeys)
            }
        }
        
        return .success
    }
    
    public func pressHotkey(_ modifiers: [Modifier], key: String) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        logger.log(.hotkey(modifiers: modifiers, key: key))
        
        // Build modifier flags
        var flags: CGEventFlags = []
        for mod in modifiers {
            flags.insert(mod.cgFlag)
        }
        
        guard let char = key.first,
              let (keyCode, _) = KeyCodeMap.mapping(for: char) else {
            return .failure("Unknown key: \(key)")
        }
        
        let source = CGEventSource(stateID: .hidSystemState)
        let keyDown = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: true)
        let keyUp = CGEvent(keyboardEventSource: source, virtualKey: keyCode, keyDown: false)
        
        keyDown?.flags = flags
        keyUp?.flags = flags
        
        keyDown?.post(tap: .cghidEventTap)
        usleep(50000)
        keyUp?.post(tap: .cghidEventTap)
        
        return .success
    }
    
    // MARK: - Clipboard
    
    public func getClipboard() -> String? {
        guard permissionManager.check(.automation) else {
            return nil
        }
        
        let pasteboard = NSPasteboard.general
        return pasteboard.string(forType: .string)
    }
    
    public func setClipboard(_ text: String) -> ActionResult {
        guard permissionManager.check(.automation) else {
            return .permissionDenied("Automation access required")
        }
        
        let pasteboard = NSPasteboard.general
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
        
        logger.log(.clipboardSet)
        return .success
    }
    
    // MARK: - Window Management
    
    public func focusApp(named appName: String) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }
        
        let workspace = NSWorkspace.shared
        let apps = workspace.runningApplications
        
        guard let app = apps.first(where: { $0.localizedName == appName }) else {
            return .failure("Application not found: \(appName)")
        }
        
        app.activate(options: [.activateIgnoringOtherApps])
        logger.log(.focusApp(name: appName))
        
        return .success
    }
    
    public func moveWindow(to point: CGPoint) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }

        guard let window = getActiveWindowElement() else {
            return .failure("No active window")
        }

        var position = point
        guard let positionValue = AXValueCreate(.cgPoint, &position) else {
            return .failure("Failed to create position value for window move")
        }

        let result = AXUIElementSetAttributeValue(
            window,
            kAXPositionAttribute as CFString,
            positionValue
        )

        if result == .success {
            logger.log(.moveWindow(point: point))
            return .success
        } else {
            return .failure("Failed to move window")
        }
    }
    
    public func resizeWindow(to size: CGSize) -> ActionResult {
        guard permissionManager.check(.accessibility) else {
            return .permissionDenied("Accessibility access required")
        }

        guard let window = getActiveWindowElement() else {
            return .failure("No active window")
        }

        var newSize = size
        guard let sizeValue = AXValueCreate(.cgSize, &newSize) else {
            return .failure("Failed to create size value for window resize")
        }

        let result = AXUIElementSetAttributeValue(
            window,
            kAXSizeAttribute as CFString,
            sizeValue
        )

        if result == .success {
            logger.log(.resizeWindow(size: size))
            return .success
        } else {
            return .failure("Failed to resize window")
        }
    }
    
    // MARK: - Private Helpers
    
    private func getActiveWindowElement() -> AXUIElement? {
        let systemWide = AXUIElementCreateSystemWide()
        var focusedApp: AnyObject?

        guard AXUIElementCopyAttributeValue(
            systemWide,
            kAXFocusedApplicationAttribute as CFString,
            &focusedApp
        ) == .success, let fa = focusedApp else {
            return nil
        }
        let appElement = unsafeBitCast(fa, to: AXUIElement.self)

        var focusedWindow: AnyObject?
        guard AXUIElementCopyAttributeValue(
            appElement,
            kAXFocusedWindowAttribute as CFString,
            &focusedWindow
        ) == .success, let fw = focusedWindow else {
            return nil
        }

        return unsafeBitCast(fw, to: AXUIElement.self)
    }
}

// MARK: - Key Code Map

struct KeyCodeMap {
    // Returns (keyCode, needsShift)
    static func mapping(for char: Character) -> (CGKeyCode, Bool)? {
        let lowercased = char.lowercased().first ?? char
        let needsShift = char.isUppercase || shiftChars.contains(char)

        if let code = keyMap[lowercased] {
            return (code, needsShift)
        }
        return nil
    }

    // Get key code for special keys by name
    static func specialKey(_ name: String) -> CGKeyCode? {
        return specialKeyMap[name.lowercased()]
    }

    private static let shiftChars: Set<Character> = [
        "!", "@", "#", "$", "%", "^", "&", "*", "(", ")",
        "_", "+", "{", "}", "|", ":", "\"", "<", ">", "?", "~"
    ]

    private static let keyMap: [Character: CGKeyCode] = [
        // Letters
        "a": 0, "b": 11, "c": 8, "d": 2, "e": 14, "f": 3, "g": 5, "h": 4,
        "i": 34, "j": 38, "k": 40, "l": 37, "m": 46, "n": 45, "o": 31, "p": 35,
        "q": 12, "r": 15, "s": 1, "t": 17, "u": 32, "v": 9, "w": 13, "x": 7,
        "y": 16, "z": 6,
        // Numbers
        "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28,
        "9": 25, "0": 29,
        // Whitespace
        " ": 49, "\n": 36, "\t": 48,
        // Punctuation
        "-": 27, "=": 24, "[": 33, "]": 30, "\\": 42, ";": 41, "'": 39,
        ",": 43, ".": 47, "/": 44, "`": 50
    ]

    private static let specialKeyMap: [String: CGKeyCode] = [
        // Function keys
        "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97,
        "f7": 98, "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
        "f13": 105, "f14": 107, "f15": 113, "f16": 106, "f17": 64, "f18": 79,
        "f19": 80, "f20": 90,
        // Navigation
        "up": 126, "down": 125, "left": 123, "right": 124,
        "pageup": 116, "pagedown": 121, "home": 115, "end": 119,
        // Editing
        "delete": 51, "forwarddelete": 117, "backspace": 51,
        "escape": 53, "esc": 53,
        "return": 36, "enter": 76,  // 76 is keypad enter
        "tab": 48,
        // Modifiers (for reference, though typically used as flags)
        "capslock": 57, "shift": 56, "control": 59, "option": 58, "command": 55,
        "rightshift": 60, "rightoption": 61, "rightcontrol": 62,
        // Other
        "space": 49, "help": 114, "clear": 71,
        // Keypad
        "keypad0": 82, "keypad1": 83, "keypad2": 84, "keypad3": 85, "keypad4": 86,
        "keypad5": 87, "keypad6": 88, "keypad7": 89, "keypad8": 91, "keypad9": 92,
        "keypaddecimal": 65, "keypadmultiply": 67, "keypadplus": 69,
        "keypadclear": 71, "keypaddivide": 75, "keypadenter": 76, "keypadminus": 78,
        "keypadequals": 81
    ]
}
