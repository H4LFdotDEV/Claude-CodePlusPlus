// ActionLogger.swift
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC

import Foundation

public enum ActionType {
    case click(point: CGPoint, button: MouseButton)
    case doubleClick(point: CGPoint)
    case type(text: String)
    case hotkey(modifiers: [Modifier], key: String)
    case screenRead(point: CGPoint)
    case windowRead
    case scroll(point: CGPoint, deltaX: Int32, deltaY: Int32)
    case clipboardSet
    case focusApp(name: String)
    case moveWindow(point: CGPoint)
    case resizeWindow(size: CGSize)

    var description: String {
        switch self {
        case .click(let point, let button):
            return "click(\(button.rawValue) at \(Int(point.x)),\(Int(point.y)))"
        case .doubleClick(let point):
            return "double_click(at \(Int(point.x)),\(Int(point.y)))"
        case .type(let text):
            return "type(\(text.count) chars)"
        case .hotkey(let modifiers, let key):
            let mods = modifiers.map { $0.rawValue }.joined(separator: "+")
            return "hotkey(\(mods)+\(key))"
        case .screenRead(let point):
            return "screen_read(at \(Int(point.x)),\(Int(point.y)))"
        case .windowRead:
            return "window_read()"
        case .scroll(let point, let dx, let dy):
            return "scroll(at \(Int(point.x)),\(Int(point.y)) delta:\(dx),\(dy))"
        case .clipboardSet:
            return "clipboard_set()"
        case .focusApp(let name):
            return "focus_app(\(name))"
        case .moveWindow(let point):
            return "move_window(to \(Int(point.x)),\(Int(point.y)))"
        case .resizeWindow(let size):
            return "resize_window(to \(Int(size.width))x\(Int(size.height)))"
        }
    }
}

public class ActionLogger {

    private let logPath: String
    private var fileHandle: FileHandle?
    private let dateFormatter: ISO8601DateFormatter

    // Log rotation configuration
    private let maxLogSize: Int64 = 10 * 1024 * 1024  // 10 MB
    private let maxLogFiles: Int = 5

    public init(path: String) {
        self.logPath = (path as NSString).expandingTildeInPath
        self.dateFormatter = ISO8601DateFormatter()

        // Create log directory if needed
        let dir = (logPath as NSString).deletingLastPathComponent
        do {
            try FileManager.default.createDirectory(atPath: dir, withIntermediateDirectories: true)
        } catch {
            NSLog("ActionLogger: Failed to create log directory at \(dir): \(error.localizedDescription)")
        }

        // Create log file if needed
        if !FileManager.default.fileExists(atPath: logPath) {
            FileManager.default.createFile(atPath: logPath, contents: nil)
        }

        self.fileHandle = FileHandle(forWritingAtPath: logPath)
        fileHandle?.seekToEndOfFile()
    }

    deinit {
        fileHandle?.closeFile()
    }

    public func log(_ action: ActionType) {
        // Check if log rotation is needed before writing
        do {
            try rotateIfNeeded()
        } catch {
            NSLog("ActionLogger: Failed to rotate log: \(error.localizedDescription)")
        }

        let timestamp = dateFormatter.string(from: Date())
        let entry = "[\(timestamp)] \(action.description)\n"

        if let data = entry.data(using: .utf8) {
            fileHandle?.write(data)
        }
    }

    public func getRecentLogs(count: Int = 100) -> [String] {
        do {
            let contents = try String(contentsOfFile: logPath, encoding: .utf8)
            let lines = contents.components(separatedBy: .newlines)
            return Array(lines.suffix(count))
        } catch {
            NSLog("ActionLogger: Failed to read log file at \(logPath): \(error.localizedDescription)")
            return []
        }
    }

    // MARK: - Log Rotation

    /// Checks if the current log file exceeds the maximum size and rotates if needed.
    private func rotateIfNeeded() throws {
        guard FileManager.default.fileExists(atPath: logPath) else {
            return
        }

        let attr = try FileManager.default.attributesOfItem(atPath: logPath)
        let fileSize = attr[.size] as? Int64 ?? 0

        if fileSize > maxLogSize {
            try rotateLog()
        }
    }

    /// Rotates log files: log -> log.1 -> log.2 -> ... -> log.N (oldest is deleted)
    private func rotateLog() throws {
        // Close current file handle before rotating
        fileHandle?.closeFile()
        fileHandle = nil

        // Delete the oldest log file if it exists
        let oldestPath = "\(logPath).\(maxLogFiles)"
        if FileManager.default.fileExists(atPath: oldestPath) {
            try FileManager.default.removeItem(atPath: oldestPath)
        }

        // Shift existing log files: log.N-1 -> log.N, log.N-2 -> log.N-1, etc.
        for i in (1..<maxLogFiles).reversed() {
            let oldPath = "\(logPath).\(i)"
            let newPath = "\(logPath).\(i + 1)"
            if FileManager.default.fileExists(atPath: oldPath) {
                try FileManager.default.moveItem(atPath: oldPath, toPath: newPath)
            }
        }

        // Move current log to log.1
        if FileManager.default.fileExists(atPath: logPath) {
            try FileManager.default.moveItem(atPath: logPath, toPath: "\(logPath).1")
        }

        // Create new empty log file
        FileManager.default.createFile(atPath: logPath, contents: nil)

        // Reopen file handle
        self.fileHandle = FileHandle(forWritingAtPath: logPath)
        fileHandle?.seekToEndOfFile()

        NSLog("ActionLogger: Log rotated successfully")
    }
}
