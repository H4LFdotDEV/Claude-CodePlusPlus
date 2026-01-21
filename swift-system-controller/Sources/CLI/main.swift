// main.swift
// Claude Code++ System Controller CLI
// Jeremiah Kroesche | Halfservers LLC
//
// Entry point for the system controller. Can run in:
// - MCP stdio mode (--stdio): Reads JSON-RPC from stdin, writes to stdout
// - Check mode (--check-permissions): Verifies accessibility permissions
// - Interactive mode (default): Simple REPL for testing

import Foundation
import SystemController
import MCPBridge

// MARK: - CLI Arguments

struct CLIArgs {
    var mode: Mode = .interactive
    var configPath: String? = nil
    var verbose: Bool = false

    enum Mode {
        case stdio
        case checkPermissions
        case requestPermissions
        case interactive
        case version
        case help
    }
}

func parseArgs() -> CLIArgs {
    var args = CLIArgs()
    let arguments = CommandLine.arguments.dropFirst()

    var i = arguments.startIndex
    while i < arguments.endIndex {
        let arg = arguments[i]
        switch arg {
        case "--stdio", "-s":
            args.mode = .stdio
        case "--check-permissions", "-c":
            args.mode = .checkPermissions
        case "--request-permissions", "-r":
            args.mode = .requestPermissions
        case "--version", "-v":
            args.mode = .version
        case "--help", "-h":
            args.mode = .help
        case "--verbose":
            args.verbose = true
        case "--config":
            i = arguments.index(after: i)
            if i < arguments.endIndex {
                args.configPath = arguments[i]
            }
        default:
            if arg.hasPrefix("-") {
                fputs("Unknown option: \(arg)\n", stderr)
            }
        }
        i = arguments.index(after: i)
    }

    return args
}

// MARK: - Main

func main() {
    let args = parseArgs()

    switch args.mode {
    case .version:
        print("system-controller-cli v1.0.0")
        print("Claude Code++ System Controller")
        print("Jeremiah Kroesche | Halfservers LLC")

    case .help:
        printHelp()

    case .checkPermissions:
        checkPermissions()

    case .requestPermissions:
        requestPermissions()

    case .stdio:
        runStdioMode(verbose: args.verbose)

    case .interactive:
        runInteractiveMode()
    }
}

// MARK: - Modes

func printHelp() {
    print("""
    system-controller-cli - Claude Code++ System Controller

    USAGE:
        system-controller-cli [OPTIONS]

    OPTIONS:
        --stdio, -s              Run in MCP stdio mode (JSON-RPC over stdin/stdout)
        --check-permissions, -c  Check if accessibility permissions are granted
        --request-permissions, -r  Request accessibility permissions from user
        --config <path>          Path to configuration file
        --verbose                Enable verbose logging
        --version, -v            Print version information
        --help, -h               Print this help message

    EXAMPLES:
        # Run as MCP server for Claude Code integration
        system-controller-cli --stdio

        # Check accessibility permission status
        system-controller-cli --check-permissions

        # Interactive testing mode
        system-controller-cli
    """)
}

func checkPermissions() {
    let controller = SystemController()

    if controller.checkAccessibilityPermission() {
        print("Accessibility permission: GRANTED")
        exit(0)
    } else {
        print("Accessibility permission: NOT GRANTED")
        print("")
        print("To grant permission:")
        print("1. Open System Settings > Privacy & Security > Accessibility")
        print("2. Add and enable this application")
        print("")
        print("Or run: system-controller-cli --request-permissions")
        exit(1)
    }
}

func requestPermissions() {
    let controller = SystemController()
    print("Requesting accessibility permissions...")
    print("A system dialog should appear. Please grant access.")
    controller.requestAccessibilityPermission()

    // Wait a moment for user to respond
    sleep(2)

    if controller.checkAccessibilityPermission() {
        print("Permission granted!")
        exit(0)
    } else {
        print("Permission not yet granted. Please complete the authorization in System Settings.")
        exit(1)
    }
}

func runStdioMode(verbose: Bool) {
    let controller = SystemController()
    let server = MCPStdioServer(controller: controller)

    if verbose {
        fputs("Starting MCP stdio server...\n", stderr)
    }

    server.run()
}

func runInteractiveMode() {
    let controller = SystemController()
    let bridge = MCPBridge(controller: controller)

    print("Claude Code++ System Controller - Interactive Mode")
    print("Type 'help' for commands, 'quit' to exit")
    print("")

    // Check permissions on startup
    if !controller.checkAccessibilityPermission() {
        print("WARNING: Accessibility permission not granted.")
        print("Run with --request-permissions to enable full functionality.")
        print("")
    }

    while true {
        print("> ", terminator: "")
        fflush(stdout)

        guard let input = readLine()?.trimmingCharacters(in: .whitespaces) else {
            break
        }

        if input.isEmpty {
            continue
        }

        switch input.lowercased() {
        case "quit", "exit", "q":
            print("Goodbye!")
            return

        case "help", "h", "?":
            printInteractiveHelp()

        case "status":
            printStatus(controller)

        case "window":
            if let info = controller.readActiveWindow() {
                print("Active window: \(info.appName) - \(info.windowTitle)")
                print("Bounds: \(info.bounds)")
            } else {
                print("Could not read active window (permission denied or no window)")
            }

        default:
            // Try to parse as JSON-RPC for advanced testing
            if input.hasPrefix("{") {
                let response = bridge.handleRequestString(input)
                print(response)
            } else {
                print("Unknown command: \(input)")
                print("Type 'help' for available commands")
            }
        }
    }
}

func printInteractiveHelp() {
    print("""
    COMMANDS:
        status    - Show current permission level and status
        window    - Read active window information
        help      - Show this help message
        quit      - Exit the program

    You can also send raw JSON-RPC requests for testing:
        {"jsonrpc":"2.0","id":1,"method":"get_active_window","params":{}}
    """)
}

func printStatus(_ controller: SystemController) {
    let hasAccess = controller.checkAccessibilityPermission()
    let level = controller.currentPermissionLevel

    print("Accessibility API: \(hasAccess ? "GRANTED" : "NOT GRANTED")")
    print("Permission Level: \(level) (level \(level.rawValue))")
}

// MARK: - Entry Point

main()
