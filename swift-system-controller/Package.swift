// swift-tools-version:5.9
// Claude Code++ System Controller
// Jeremiah Kroesche | Halfservers LLC

import PackageDescription

let package = Package(
    name: "SystemController",
    platforms: [
        .macOS(.v12)
    ],
    products: [
        .library(
            name: "SystemController",
            targets: ["SystemController"]
        ),
        .library(
            name: "MCPBridge",
            targets: ["MCPBridge"]
        ),
        .executable(
            name: "system-controller-cli",
            targets: ["SystemControllerCLI"]
        )
    ],
    dependencies: [],
    targets: [
        .target(
            name: "SystemController",
            dependencies: [],
            path: "Sources/SystemController",
            linkerSettings: [
                .linkedFramework("ApplicationServices"),
                .linkedFramework("CoreGraphics"),
                .linkedFramework("AppKit")
            ]
        ),
        .target(
            name: "MCPBridge",
            dependencies: ["SystemController"],
            path: "Sources/MCPBridge"
        ),
        .executableTarget(
            name: "SystemControllerCLI",
            dependencies: ["SystemController", "MCPBridge"],
            path: "Sources/CLI"
        ),
        .testTarget(
            name: "SystemControllerTests",
            dependencies: ["SystemController", "MCPBridge"],
            path: "Tests/SystemControllerTests"
        )
    ]
)
