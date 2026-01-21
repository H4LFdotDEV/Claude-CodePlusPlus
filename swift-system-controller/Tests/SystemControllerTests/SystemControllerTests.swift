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
