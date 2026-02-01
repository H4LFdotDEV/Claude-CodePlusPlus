// SystemControllerTests.swift
// Claude Code++ System Controller Tests
// Jeremiah Kroesche | Halfservers LLC

import XCTest
@testable import SystemController
@testable import MCPBridge

final class SystemControllerTests: XCTestCase {

    func testPermissionLevelValues() {
        XCTAssertEqual(PermissionLevel.sandboxed.rawValue, 0)
        XCTAssertEqual(PermissionLevel.standard.rawValue, 1)
        XCTAssertEqual(PermissionLevel.automation.rawValue, 2)
        XCTAssertEqual(PermissionLevel.accessibility.rawValue, 3)
        XCTAssertEqual(PermissionLevel.administrator.rawValue, 4)
        XCTAssertEqual(PermissionLevel.unrestricted.rawValue, 5)
    }

    func testActionResultSuccess() {
        let result = ActionResult.success
        XCTAssertTrue(result.isSuccess)

        let dict = result.toDict()
        XCTAssertEqual(dict["status"] as? String, "success")
    }

    func testActionResultFailure() {
        let result = ActionResult.failure("Test error")
        XCTAssertFalse(result.isSuccess)

        let dict = result.toDict()
        XCTAssertEqual(dict["status"] as? String, "error")
        XCTAssertEqual(dict["error"] as? String, "failure")
        XCTAssertEqual(dict["reason"] as? String, "Test error")
    }

    func testMouseButtonEventTypes() {
        XCTAssertEqual(MouseButton.left.downEventType, .leftMouseDown)
        XCTAssertEqual(MouseButton.left.upEventType, .leftMouseUp)
        XCTAssertEqual(MouseButton.right.downEventType, .rightMouseDown)
        XCTAssertEqual(MouseButton.right.upEventType, .rightMouseUp)
    }

    func testModifierFlags() {
        XCTAssertEqual(Modifier.cmd.cgFlag, .maskCommand)
        XCTAssertEqual(Modifier.ctrl.cgFlag, .maskControl)
        XCTAssertEqual(Modifier.alt.cgFlag, .maskAlternate)
        XCTAssertEqual(Modifier.shift.cgFlag, .maskShift)
    }

    func testKeyCodeMapBasicKeys() {
        // Test lowercase letters
        if let (code, shift) = KeyCodeMap.mapping(for: "a") {
            XCTAssertEqual(code, 0)
            XCTAssertFalse(shift)
        } else {
            XCTFail("Should have mapping for 'a'")
        }

        // Test uppercase (should need shift)
        if let (code, shift) = KeyCodeMap.mapping(for: "A") {
            XCTAssertEqual(code, 0)
            XCTAssertTrue(shift)
        } else {
            XCTFail("Should have mapping for 'A'")
        }

        // Test space
        if let (code, shift) = KeyCodeMap.mapping(for: " ") {
            XCTAssertEqual(code, 49)
            XCTAssertFalse(shift)
        } else {
            XCTFail("Should have mapping for space")
        }
    }

    func testKeyCodeMapSpecialKeys() {
        // Test function keys
        XCTAssertEqual(KeyCodeMap.specialKey("f1"), 122)
        XCTAssertEqual(KeyCodeMap.specialKey("f12"), 111)

        // Test arrow keys
        XCTAssertEqual(KeyCodeMap.specialKey("up"), 126)
        XCTAssertEqual(KeyCodeMap.specialKey("down"), 125)
        XCTAssertEqual(KeyCodeMap.specialKey("left"), 123)
        XCTAssertEqual(KeyCodeMap.specialKey("right"), 124)

        // Test escape
        XCTAssertEqual(KeyCodeMap.specialKey("escape"), 53)
        XCTAssertEqual(KeyCodeMap.specialKey("esc"), 53)
    }

    func testRateLimitConfig() {
        let config = RateLimitConfig.default
        XCTAssertEqual(config.maxClicksPerSecond, 10)
        XCTAssertEqual(config.maxKeysPerSecond, 1000)
    }

    func testControllerConfig() {
        let config = ControllerConfig.default
        XCTAssertEqual(config.logPath, "~/.claude-code-pp/logs/system-controller.log")
    }
}

// MARK: - MCP Bridge Tests

final class MCPBridgeTests: XCTestCase {

    func testAnyCodableString() {
        let value = AnyCodable("test")
        XCTAssertEqual(value.asString(), "test")
    }

    func testAnyCodableInt() {
        let value = AnyCodable(42)
        XCTAssertEqual(value.asInt(), 42)
    }

    func testAnyCodableDouble() {
        let value = AnyCodable(3.14)
        XCTAssertEqual(value.asDouble(), 3.14)
    }

    func testAnyCodableIntToDouble() {
        let value = AnyCodable(42)
        XCTAssertEqual(value.asDouble(), 42.0)
    }

    func testAnyCodableDoubleToInt() {
        let value = AnyCodable(42.9)
        XCTAssertEqual(value.asInt(), 42)
    }

    func testAnyCodableArray() {
        let value = AnyCodable([1, 2, 3])
        let array = value.asArray()
        XCTAssertNotNil(array)
        XCTAssertEqual(array?.count, 3)
    }

    func testAnyCodableNil() {
        let value = AnyCodable("test")
        XCTAssertNil(value.asInt())
        XCTAssertNil(value.asDouble())
    }

    func testMCPErrorCodes() {
        XCTAssertEqual(MCPError.invalidRequest.code, -32600)
        XCTAssertEqual(MCPError.methodNotFound.code, -32601)
        XCTAssertEqual(MCPError.invalidParams.code, -32602)
        XCTAssertEqual(MCPError.internalError.code, -32603)
    }

    func testMCPErrorPermissionDenied() {
        let error = MCPError.permissionDenied("Test reason")
        XCTAssertEqual(error.code, -32001)
        XCTAssertTrue(error.message.contains("Test reason"))
    }

    func testMCPErrorRateLimited() {
        let error = MCPError.rateLimited("Too many clicks")
        XCTAssertEqual(error.code, -32002)
        XCTAssertTrue(error.message.contains("Too many clicks"))
    }

    func testMCPResponseSuccess() throws {
        let response = MCPResponse(id: 1, result: AnyCodable(["status": "ok"]))
        XCTAssertEqual(response.jsonrpc, "2.0")
        XCTAssertEqual(response.id, 1)
        XCTAssertNil(response.error)
    }

    func testMCPResponseError() {
        let response = MCPResponse(id: 1, error: .methodNotFound)
        XCTAssertEqual(response.jsonrpc, "2.0")
        XCTAssertEqual(response.id, 1)
        XCTAssertNil(response.result)
        XCTAssertEqual(response.error?.code, -32601)
    }
}

// MARK: - MCPBridge Integration Tests

final class MCPBridgeIntegrationTests: XCTestCase {

    var controller: SystemController!
    var bridge: MCPBridge!

    override func setUp() {
        super.setUp()
        controller = SystemController()
        bridge = MCPBridge(controller: controller)
    }

    override func tearDown() {
        controller = nil
        bridge = nil
        super.tearDown()
    }

    func testHandleInvalidJSON() {
        let response = bridge.handleRequestString("not valid json")
        XCTAssertTrue(response.contains("Invalid Request"))
    }

    func testHandleUnknownMethod() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"unknown_method","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Method not found"))
    }

    func testHandleGetPermissionLevel() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"get_permission_level","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("level"))
    }

    func testHandleCheckAccessibility() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"check_accessibility","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("has_access"))
    }

    func testHandleClickMissingParams() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"click","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleScrollMissingDeltaY() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"scroll","params":{"x":100,"y":200}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleTypeTextMissingParams() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"type_text","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleHotkeyMissingKey() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"hotkey","params":{"modifiers":["command"]}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleClipboardSetMissingText() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"clipboard_set","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleFocusAppMissingName() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"focus_app","params":{}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleMoveWindowMissingCoords() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"move_window","params":{"x":100}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleResizeWindowMissingDimensions() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"resize_window","params":{"width":100}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }

    func testHandleScreenReadAtMissingCoords() {
        let request = """
        {"jsonrpc":"2.0","id":1,"method":"screen_read_at","params":{"x":100}}
        """
        let response = bridge.handleRequestString(request)
        XCTAssertTrue(response.contains("Invalid params"))
    }
}

// MARK: - Additional Unit Tests

final class SystemControllerAdditionalTests: XCTestCase {

    func testActionResultPermissionDenied() {
        let result = ActionResult.permissionDenied("Need higher permission")
        XCTAssertFalse(result.isSuccess)

        let dict = result.toDict()
        XCTAssertEqual(dict["status"] as? String, "error")
        XCTAssertEqual(dict["error"] as? String, "permission_denied")
    }

    func testActionResultRateLimited() {
        let result = ActionResult.rateLimited("Exceeded click limit")
        XCTAssertFalse(result.isSuccess)

        let dict = result.toDict()
        XCTAssertEqual(dict["status"] as? String, "error")
        XCTAssertEqual(dict["error"] as? String, "rate_limited")
    }

    func testKeyCodeMapNumbers() {
        // Test number keys
        if let (code, shift) = KeyCodeMap.mapping(for: "1") {
            XCTAssertEqual(code, 18)
            XCTAssertFalse(shift)
        } else {
            XCTFail("Should have mapping for '1'")
        }

        // Test shifted number (!)
        if let (code, shift) = KeyCodeMap.mapping(for: "!") {
            XCTAssertEqual(code, 18)
            XCTAssertTrue(shift)
        } else {
            XCTFail("Should have mapping for '!'")
        }
    }

    func testKeyCodeMapSymbols() {
        // Test common symbols
        let symbols = ["-", "=", "[", "]", "\\", ";", "'", ",", ".", "/"]
        for symbol in symbols {
            XCTAssertNotNil(KeyCodeMap.mapping(for: symbol), "Should have mapping for '\(symbol)'")
        }
    }

    func testKeyCodeMapTabAndReturn() {
        if let (code, _) = KeyCodeMap.mapping(for: "\t") {
            XCTAssertEqual(code, 48) // Tab
        } else {
            XCTFail("Should have mapping for tab")
        }

        if let (code, _) = KeyCodeMap.mapping(for: "\n") {
            XCTAssertEqual(code, 36) // Return
        } else {
            XCTFail("Should have mapping for return")
        }
    }

    func testKeyCodeMapSpecialKeysCaseInsensitive() {
        // Should work regardless of case
        XCTAssertEqual(KeyCodeMap.specialKey("ESCAPE"), 53)
        XCTAssertEqual(KeyCodeMap.specialKey("Escape"), 53)
        XCTAssertEqual(KeyCodeMap.specialKey("escape"), 53)
    }

    func testKeyCodeMapDeleteAndBackspace() {
        XCTAssertEqual(KeyCodeMap.specialKey("delete"), 51)
        XCTAssertEqual(KeyCodeMap.specialKey("backspace"), 51)
        XCTAssertEqual(KeyCodeMap.specialKey("forward_delete"), 117)
    }

    func testKeyCodeMapHomeEndPageKeys() {
        XCTAssertEqual(KeyCodeMap.specialKey("home"), 115)
        XCTAssertEqual(KeyCodeMap.specialKey("end"), 119)
        XCTAssertEqual(KeyCodeMap.specialKey("page_up"), 116)
        XCTAssertEqual(KeyCodeMap.specialKey("page_down"), 121)
    }

    func testMouseButtonMiddle() {
        XCTAssertEqual(MouseButton.middle.downEventType, .otherMouseDown)
        XCTAssertEqual(MouseButton.middle.upEventType, .otherMouseUp)
    }

    func testModifierRawValues() {
        XCTAssertEqual(Modifier.cmd.rawValue, "command")
        XCTAssertEqual(Modifier.ctrl.rawValue, "control")
        XCTAssertEqual(Modifier.alt.rawValue, "option")
        XCTAssertEqual(Modifier.shift.rawValue, "shift")
    }

    func testPermissionLevelComparison() {
        XCTAssertTrue(PermissionLevel.accessibility.rawValue > PermissionLevel.sandboxed.rawValue)
        XCTAssertTrue(PermissionLevel.unrestricted.rawValue > PermissionLevel.administrator.rawValue)
    }
}

// MARK: - PermissionManager Tests

final class PermissionManagerTests: XCTestCase {

    var tempDir: URL!
    var permissionManager: PermissionManager!

    override func setUp() {
        super.setUp()
        tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        let configPath = tempDir.appendingPathComponent("permissions.yaml").path
        permissionManager = PermissionManager(configPath: configPath)
    }

    override func tearDown() {
        permissionManager = nil
        try? FileManager.default.removeItem(at: tempDir)
        super.tearDown()
    }

    func testInitialLevelIsSandboxed() {
        XCTAssertEqual(permissionManager.currentLevel, .sandboxed)
    }

    func testSetLevel() {
        permissionManager.setLevel(.standard)
        XCTAssertEqual(permissionManager.currentLevel, .standard)

        permissionManager.setLevel(.automation)
        XCTAssertEqual(permissionManager.currentLevel, .automation)
    }

    func testCheckPermissionAtSameLevel() {
        permissionManager.setLevel(.standard)
        XCTAssertTrue(permissionManager.check(.standard))
    }

    func testCheckPermissionBelowCurrentLevel() {
        permissionManager.setLevel(.automation)
        XCTAssertTrue(permissionManager.check(.standard))
        XCTAssertTrue(permissionManager.check(.sandboxed))
    }

    func testCheckPermissionAboveCurrentLevel() {
        permissionManager.setLevel(.standard)
        XCTAssertFalse(permissionManager.check(.automation))
        XCTAssertFalse(permissionManager.check(.accessibility))
    }

    func testSetLevelPersists() {
        let configPath = tempDir.appendingPathComponent("persist.yaml").path
        let manager1 = PermissionManager(configPath: configPath)
        manager1.setLevel(.accessibility)

        // Create new instance with same config path
        let manager2 = PermissionManager(configPath: configPath)
        XCTAssertEqual(manager2.currentLevel, .accessibility)
    }

    func testAllPermissionLevels() {
        let levels: [PermissionLevel] = [
            .sandboxed, .standard, .automation,
            .accessibility, .administrator, .unrestricted
        ]

        for level in levels {
            permissionManager.setLevel(level)
            XCTAssertEqual(permissionManager.currentLevel, level)
        }
    }

    func testElevateAlreadyAtLevel() {
        permissionManager.setLevel(.automation)
        // Should return true without prompting when already at or above level
        XCTAssertTrue(permissionManager.elevate(to: .sandboxed, reason: "test"))
        XCTAssertTrue(permissionManager.elevate(to: .standard, reason: "test"))
        XCTAssertTrue(permissionManager.elevate(to: .automation, reason: "test"))
    }
}

// MARK: - RateLimiter Tests

final class RateLimiterTests: XCTestCase {

    func testAllowClickUnderLimit() {
        let config = RateLimitConfig(maxClicksPerSecond: 10, maxKeysPerSecond: 1000)
        let limiter = RateLimiter(config: config)

        // Should allow clicks under the limit
        for _ in 0..<10 {
            XCTAssertTrue(limiter.allowClick())
        }
    }

    func testAllowClickOverLimit() {
        let config = RateLimitConfig(maxClicksPerSecond: 5, maxKeysPerSecond: 1000)
        let limiter = RateLimiter(config: config)

        // Use up the limit
        for _ in 0..<5 {
            XCTAssertTrue(limiter.allowClick())
        }

        // 6th click should be denied
        XCTAssertFalse(limiter.allowClick())
    }

    func testAllowKeysUnderLimit() {
        let config = RateLimitConfig(maxClicksPerSecond: 10, maxKeysPerSecond: 100)
        let limiter = RateLimiter(config: config)

        // Should allow keys under the limit
        XCTAssertTrue(limiter.allowKeys(count: 50))
        XCTAssertTrue(limiter.allowKeys(count: 50))
    }

    func testAllowKeysOverLimit() {
        let config = RateLimitConfig(maxClicksPerSecond: 10, maxKeysPerSecond: 100)
        let limiter = RateLimiter(config: config)

        // Use most of the limit
        XCTAssertTrue(limiter.allowKeys(count: 90))

        // This would exceed the limit
        XCTAssertFalse(limiter.allowKeys(count: 20))

        // But this fits
        XCTAssertTrue(limiter.allowKeys(count: 10))
    }

    func testReset() {
        let config = RateLimitConfig(maxClicksPerSecond: 3, maxKeysPerSecond: 100)
        let limiter = RateLimiter(config: config)

        // Use up limits
        for _ in 0..<3 {
            _ = limiter.allowClick()
        }
        _ = limiter.allowKeys(count: 100)

        // Should be at limit
        XCTAssertFalse(limiter.allowClick())
        XCTAssertFalse(limiter.allowKeys(count: 1))

        // Reset
        limiter.reset()

        // Should be able to click/type again
        XCTAssertTrue(limiter.allowClick())
        XCTAssertTrue(limiter.allowKeys(count: 1))
    }

    func testDefaultConfig() {
        let config = RateLimitConfig.default
        let limiter = RateLimiter(config: config)

        // Default allows 10 clicks per second
        for _ in 0..<10 {
            XCTAssertTrue(limiter.allowClick())
        }
        XCTAssertFalse(limiter.allowClick())
    }

    func testConcurrentAccess() {
        let config = RateLimitConfig(maxClicksPerSecond: 100, maxKeysPerSecond: 1000)
        let limiter = RateLimiter(config: config)

        let expectation = expectation(description: "Concurrent access")
        expectation.expectedFulfillmentCount = 10

        // Simulate concurrent access from multiple threads
        for _ in 0..<10 {
            DispatchQueue.global().async {
                for _ in 0..<5 {
                    _ = limiter.allowClick()
                }
                expectation.fulfill()
            }
        }

        wait(for: [expectation], timeout: 5.0)
        // Test passes if no crashes occur (thread safety check)
    }
}

// MARK: - ActionLogger Tests

final class ActionLoggerTests: XCTestCase {

    var tempDir: URL!
    var logPath: String!

    override func setUp() {
        super.setUp()
        tempDir = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        try? FileManager.default.createDirectory(at: tempDir, withIntermediateDirectories: true)
        logPath = tempDir.appendingPathComponent("test.log").path
    }

    override func tearDown() {
        try? FileManager.default.removeItem(at: tempDir)
        super.tearDown()
    }

    func testLogCreatesFile() {
        let logger = ActionLogger(path: logPath)
        logger.log(.windowRead)

        XCTAssertTrue(FileManager.default.fileExists(atPath: logPath))
    }

    func testLogWritesEntry() {
        let logger = ActionLogger(path: logPath)
        logger.log(.click(point: CGPoint(x: 100, y: 200), button: .left))

        let contents = try? String(contentsOfFile: logPath, encoding: .utf8)
        XCTAssertNotNil(contents)
        XCTAssertTrue(contents?.contains("click(left at 100,200)") ?? false)
    }

    func testGetRecentLogs() {
        let logger = ActionLogger(path: logPath)

        // Log several actions
        logger.log(.click(point: CGPoint(x: 10, y: 20), button: .left))
        logger.log(.type(text: "Hello"))
        logger.log(.windowRead)

        let logs = logger.getRecentLogs(count: 10)
        XCTAssertGreaterThanOrEqual(logs.count, 3)
    }

    func testGetRecentLogsLimit() {
        let logger = ActionLogger(path: logPath)

        // Log 10 actions
        for i in 0..<10 {
            logger.log(.click(point: CGPoint(x: CGFloat(i), y: 0), button: .left))
        }

        // Request only 5
        let logs = logger.getRecentLogs(count: 5)
        XCTAssertLessThanOrEqual(logs.count, 6) // May include empty trailing line
    }

    func testActionTypeDescriptions() {
        // Test that all action types produce valid descriptions
        let actions: [ActionType] = [
            .click(point: CGPoint(x: 100, y: 200), button: .left),
            .click(point: CGPoint(x: 100, y: 200), button: .right),
            .doubleClick(point: CGPoint(x: 50, y: 50)),
            .type(text: "Hello World"),
            .hotkey(modifiers: [.cmd, .shift], key: "a"),
            .screenRead(point: CGPoint(x: 0, y: 0)),
            .windowRead,
            .scroll(point: CGPoint(x: 100, y: 100), deltaX: 0, deltaY: -5),
            .clipboardSet,
            .focusApp(name: "Safari"),
            .moveWindow(point: CGPoint(x: 0, y: 0)),
            .resizeWindow(size: CGSize(width: 800, height: 600))
        ]

        for action in actions {
            XCTAssertFalse(action.description.isEmpty)
        }
    }

    func testClickActionDescription() {
        let action = ActionType.click(point: CGPoint(x: 100, y: 200), button: .left)
        XCTAssertEqual(action.description, "click(left at 100,200)")
    }

    func testDoubleClickDescription() {
        let action = ActionType.doubleClick(point: CGPoint(x: 50, y: 100))
        XCTAssertEqual(action.description, "double_click(at 50,100)")
    }

    func testTypeDescription() {
        let action = ActionType.type(text: "Hello World")
        XCTAssertEqual(action.description, "type(11 chars)")
    }

    func testHotkeyDescription() {
        let action = ActionType.hotkey(modifiers: [.cmd, .shift], key: "c")
        XCTAssertTrue(action.description.contains("command"))
        XCTAssertTrue(action.description.contains("shift"))
        XCTAssertTrue(action.description.contains("+c"))
    }

    func testScrollDescription() {
        let action = ActionType.scroll(point: CGPoint(x: 100, y: 200), deltaX: 5, deltaY: -10)
        XCTAssertEqual(action.description, "scroll(at 100,200 delta:5,-10)")
    }

    func testFocusAppDescription() {
        let action = ActionType.focusApp(name: "Terminal")
        XCTAssertEqual(action.description, "focus_app(Terminal)")
    }

    func testMoveWindowDescription() {
        let action = ActionType.moveWindow(point: CGPoint(x: 100, y: 50))
        XCTAssertEqual(action.description, "move_window(to 100,50)")
    }

    func testResizeWindowDescription() {
        let action = ActionType.resizeWindow(size: CGSize(width: 1920, height: 1080))
        XCTAssertEqual(action.description, "resize_window(to 1920x1080)")
    }
}
