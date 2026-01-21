// PermissionManager.swift
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC

import Foundation

public class PermissionManager {
    
    private var _currentLevel: PermissionLevel = .sandboxed
    private let configPath: String
    
    public var currentLevel: PermissionLevel {
        return _currentLevel
    }
    
    public init(configPath: String = "~/.claude-code-pp/config/permissions.yaml") {
        self.configPath = (configPath as NSString).expandingTildeInPath
        loadPermissions()
    }
    
    public func check(_ required: PermissionLevel) -> Bool {
        return _currentLevel.rawValue >= required.rawValue
    }
    
    public func setLevel(_ level: PermissionLevel) {
        _currentLevel = level
        savePermissions()
    }
    
    public func elevate(to level: PermissionLevel, reason: String) -> Bool {
        // Already at or above requested level
        if _currentLevel.rawValue >= level.rawValue {
            return true
        }

        // Prompt user via CLI
        let levelName = levelToString(level)
        print("\n" + String(repeating: "=", count: 60))
        print("PERMISSION ELEVATION REQUEST")
        print(String(repeating: "=", count: 60))
        print("Requested level: \(levelName) (level \(level.rawValue))")
        print("Current level:   \(levelToString(_currentLevel)) (level \(_currentLevel.rawValue))")
        print("Reason: \(reason)")
        print(String(repeating: "-", count: 60))
        print("Grant permission? [y/N] (10 second timeout): ", terminator: "")

        // Flush stdout to ensure prompt is visible
        fflush(stdout)

        // Read with timeout
        let approved = readLineWithTimeout(seconds: 10)

        if approved?.lowercased() == "y" || approved?.lowercased() == "yes" {
            _currentLevel = level
            savePermissions()
            print("Permission granted. Level elevated to \(levelName).")
            return true
        } else {
            print("Permission denied.")
            return false
        }
    }

    private func levelToString(_ level: PermissionLevel) -> String {
        switch level {
        case .sandboxed: return "sandboxed"
        case .standard: return "standard"
        case .automation: return "automation"
        case .accessibility: return "accessibility"
        case .administrator: return "administrator"
        case .unrestricted: return "unrestricted"
        }
    }

    private func readLineWithTimeout(seconds: Int) -> String? {
        let inputSource = DispatchSource.makeReadSource(fileDescriptor: FileHandle.standardInput.fileDescriptor, queue: .main)
        var result: String? = nil
        var didRead = false

        inputSource.setEventHandler {
            if let line = readLine() {
                result = line
                didRead = true
            }
        }
        inputSource.resume()

        let deadline = DispatchTime.now() + .seconds(seconds)
        while !didRead && DispatchTime.now() < deadline {
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 0.1))
        }

        inputSource.cancel()
        return result
    }
    
    private func loadPermissions() {
        let path = (configPath as NSString).expandingTildeInPath
        guard FileManager.default.fileExists(atPath: path) else {
            _currentLevel = .sandboxed
            return
        }
        
        do {
            let contents = try String(contentsOfFile: path, encoding: .utf8)
            // Simple YAML parsing for permission level
            if contents.contains("level: unrestricted") {
                _currentLevel = .unrestricted
            } else if contents.contains("level: administrator") {
                _currentLevel = .administrator
            } else if contents.contains("level: accessibility") {
                _currentLevel = .accessibility
            } else if contents.contains("level: automation") {
                _currentLevel = .automation
            } else if contents.contains("level: standard") {
                _currentLevel = .standard
            } else {
                _currentLevel = .sandboxed
            }
        } catch {
            _currentLevel = .sandboxed
        }
    }
    
    private func savePermissions() {
        let levelString: String
        switch _currentLevel {
        case .sandboxed: levelString = "sandboxed"
        case .standard: levelString = "standard"
        case .automation: levelString = "automation"
        case .accessibility: levelString = "accessibility"
        case .administrator: levelString = "administrator"
        case .unrestricted: levelString = "unrestricted"
        }
        
        let yaml = """
        # Claude Code++ Permission Configuration
        # Jeremiah Kroesche | Halfservers LLC
        
        permissions:
          level: \(levelString)
          last_updated: \(ISO8601DateFormatter().string(from: Date()))
        """
        
        do {
            let dir = (configPath as NSString).deletingLastPathComponent
            try FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
            try yaml.write(toFile: configPath, atomically: true, encoding: .utf8)
        } catch {
            print("Failed to save permissions: \(error)")
        }
    }
}
