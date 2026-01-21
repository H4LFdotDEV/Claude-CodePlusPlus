// MCPBridge.swift
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC
//
// Exposes SystemController as an MCP server for Claude Code integration.

import Foundation
import SystemController

// MARK: - MCP Protocol Types

public struct MCPRequest: Codable {
    public let jsonrpc: String
    public let id: Int
    public let method: String
    public let params: [String: AnyCodable]
    
    public init(jsonrpc: String = "2.0", id: Int, method: String, params: [String: AnyCodable]) {
        self.jsonrpc = jsonrpc
        self.id = id
        self.method = method
        self.params = params
    }
}

public struct MCPResponse: Codable {
    public let jsonrpc: String
    public let id: Int
    public let result: AnyCodable?
    public let error: MCPError?
    
    public init(id: Int, result: AnyCodable? = nil, error: MCPError? = nil) {
        self.jsonrpc = "2.0"
        self.id = id
        self.result = result
        self.error = error
    }
}

public struct MCPError: Codable {
    public let code: Int
    public let message: String
    
    public static let invalidRequest = MCPError(code: -32600, message: "Invalid Request")
    public static let methodNotFound = MCPError(code: -32601, message: "Method not found")
    public static let invalidParams = MCPError(code: -32602, message: "Invalid params")
    public static let internalError = MCPError(code: -32603, message: "Internal error")
    
    public static func permissionDenied(_ reason: String) -> MCPError {
        return MCPError(code: -32001, message: "Permission denied: \(reason)")
    }
    
    public static func rateLimited(_ reason: String) -> MCPError {
        return MCPError(code: -32002, message: "Rate limited: \(reason)")
    }
}

// MARK: - AnyCodable Helper

public struct AnyCodable: Codable {
    public let value: Any
    
    public init(_ value: Any) {
        self.value = value
    }
    
    public init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        
        if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dict = try? container.decode([String: AnyCodable].self) {
            value = dict.mapValues { $0.value }
        } else {
            value = NSNull()
        }
    }
    
    public func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        
        switch value {
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map { AnyCodable($0) })
        case let dict as [String: Any]:
            try container.encode(dict.mapValues { AnyCodable($0) })
        default:
            try container.encodeNil()
        }
    }
    
    public func asDouble() -> Double? {
        if let d = value as? Double { return d }
        if let i = value as? Int { return Double(i) }
        return nil
    }
    
    public func asString() -> String? {
        return value as? String
    }
    
    public func asInt() -> Int? {
        if let i = value as? Int { return i }
        if let d = value as? Double { return Int(d) }
        return nil
    }
    
    public func asArray() -> [Any]? {
        return value as? [Any]
    }
}

// MARK: - MCP Bridge

public class MCPBridge {
    
    private let controller: SystemController
    
    public init(controller: SystemController) {
        self.controller = controller
    }
    
    public func handleRequest(_ jsonData: Data) -> Data {
        do {
            let request = try JSONDecoder().decode(MCPRequest.self, from: jsonData)
            let response = processRequest(request)
            return try JSONEncoder().encode(response)
        } catch {
            let errorResponse = MCPResponse(id: 0, error: .invalidRequest)
            return try! JSONEncoder().encode(errorResponse)
        }
    }
    
    public func handleRequestString(_ json: String) -> String {
        guard let data = json.data(using: .utf8) else {
            return #"{"jsonrpc":"2.0","id":0,"error":{"code":-32600,"message":"Invalid Request"}}"#
        }
        let responseData = handleRequest(data)
        return String(data: responseData, encoding: .utf8) ?? ""
    }
    
    private func processRequest(_ request: MCPRequest) -> MCPResponse {
        switch request.method {
            
        // Screen Reading
        case "screen_read_at":
            guard let x = request.params["x"]?.asDouble(),
                  let y = request.params["y"]?.asDouble() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            if let element = controller.readElementAt(x: CGFloat(x), y: CGFloat(y)) {
                return MCPResponse(id: request.id, result: AnyCodable(element.toDict()))
            } else {
                return MCPResponse(id: request.id, error: .permissionDenied("Accessibility access required"))
            }
            
        case "get_active_window":
            if let window = controller.readActiveWindow() {
                return MCPResponse(id: request.id, result: AnyCodable(window.toDict()))
            } else {
                return MCPResponse(id: request.id, error: .permissionDenied("Accessibility access required"))
            }
            
        // Mouse Control
        case "click":
            guard let x = request.params["x"]?.asDouble(),
                  let y = request.params["y"]?.asDouble() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let buttonStr = request.params["button"]?.asString() ?? "left"
            let button = MouseButton(rawValue: buttonStr) ?? .left
            
            let result = controller.click(at: CGPoint(x: x, y: y), button: button)
            return resultToResponse(result, id: request.id)
            
        case "double_click":
            guard let x = request.params["x"]?.asDouble(),
                  let y = request.params["y"]?.asDouble() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.doubleClick(at: CGPoint(x: x, y: y))
            return resultToResponse(result, id: request.id)
            
        case "scroll":
            guard let x = request.params["x"]?.asDouble(),
                  let y = request.params["y"]?.asDouble(),
                  let deltaY = request.params["delta_y"]?.asInt() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let deltaX = request.params["delta_x"]?.asInt() ?? 0
            let result = controller.scroll(at: CGPoint(x: x, y: y), deltaX: Int32(deltaX), deltaY: Int32(deltaY))
            return resultToResponse(result, id: request.id)
            
        // Keyboard Control
        case "type_text":
            guard let text = request.params["text"]?.asString() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.typeText(text)
            return resultToResponse(result, id: request.id)
            
        case "hotkey":
            guard let key = request.params["key"]?.asString() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            var modifiers: [Modifier] = []
            if let modArray = request.params["modifiers"]?.asArray() {
                for mod in modArray {
                    if let modStr = mod as? String, let modifier = Modifier(rawValue: modStr) {
                        modifiers.append(modifier)
                    }
                }
            }
            
            let result = controller.pressHotkey(modifiers, key: key)
            return resultToResponse(result, id: request.id)
            
        // Clipboard
        case "clipboard_get":
            if let text = controller.getClipboard() {
                return MCPResponse(id: request.id, result: AnyCodable(["text": text]))
            } else {
                return MCPResponse(id: request.id, error: .permissionDenied("Automation access required"))
            }
            
        case "clipboard_set":
            guard let text = request.params["text"]?.asString() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.setClipboard(text)
            return resultToResponse(result, id: request.id)
            
        // Window Management
        case "focus_app":
            guard let appName = request.params["app_name"]?.asString() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.focusApp(named: appName)
            return resultToResponse(result, id: request.id)
            
        case "move_window":
            guard let x = request.params["x"]?.asDouble(),
                  let y = request.params["y"]?.asDouble() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.moveWindow(to: CGPoint(x: x, y: y))
            return resultToResponse(result, id: request.id)
            
        case "resize_window":
            guard let width = request.params["width"]?.asDouble(),
                  let height = request.params["height"]?.asDouble() else {
                return MCPResponse(id: request.id, error: .invalidParams)
            }
            
            let result = controller.resizeWindow(to: CGSize(width: width, height: height))
            return resultToResponse(result, id: request.id)
            
        // Permission Management
        case "get_permission_level":
            return MCPResponse(
                id: request.id,
                result: AnyCodable(["level": controller.currentPermissionLevel.rawValue])
            )
            
        case "check_accessibility":
            let hasAccess = controller.checkAccessibilityPermission()
            return MCPResponse(
                id: request.id,
                result: AnyCodable(["has_access": hasAccess])
            )
            
        default:
            return MCPResponse(id: request.id, error: .methodNotFound)
        }
    }
    
    private func resultToResponse(_ result: ActionResult, id: Int) -> MCPResponse {
        switch result {
        case .success:
            return MCPResponse(id: id, result: AnyCodable(["status": "success"]))
        case .permissionDenied(let reason):
            return MCPResponse(id: id, error: .permissionDenied(reason))
        case .rateLimited(let reason):
            return MCPResponse(id: id, error: .rateLimited(reason))
        case .failure(let reason):
            return MCPResponse(id: id, error: MCPError(code: -32000, message: reason))
        }
    }
}

// MARK: - Stdio Server

public class MCPStdioServer {
    
    private let bridge: MCPBridge
    
    public init(controller: SystemController) {
        self.bridge = MCPBridge(controller: controller)
    }
    
    public func run() {
        while let line = readLine() {
            let response = bridge.handleRequestString(line)
            print(response)
            fflush(stdout)
        }
    }
}
