# CAIIDE++ (Claude AI IDE++)

A privacy-focused VS Code fork with built-in AI memory capabilities and a warm, Claude-inspired aesthetic.

## Features

- **Privacy First**: All Microsoft telemetry stripped out
- **Open VSX Marketplace**: Uses the open-source extension marketplace instead of Microsoft's
- **Memory MCP Integration**: Built-in persistent memory via Memory MCP server
- **Claude-Inspired Theme**: Warm, elegant theme based on Claude's desktop app aesthetic
- **Community-Driven**: MIT licensed, fully open source

## Quick Start

### Prerequisites

- Node.js 18+
- Yarn 1.x (`npm install -g yarn`)
- Python 3.10+ (for Memory MCP)
- Git

### Build from Source

```bash
# Clone this repository
git clone https://github.com/halfservers/caiide.git
cd caiide

# Run the build script
chmod +x build-caiide.sh
./build-caiide.sh

# The built app will be in ./build/
```

### Manual Build Steps

If you prefer to build manually:

```bash
# 1. Clone VS Code
git clone --depth 1 https://github.com/microsoft/vscode.git vscode-base
cd vscode-base

# 2. Install dependencies
yarn install

# 3. Copy product.json (branding + Open VSX)
cp ../product.json ./product.json

# 4. Copy bundled extensions
cp -r ../extensions/memory-mcp ./extensions/caiide-memory
cp -r ../extensions/caiide-theme ./extensions/caiide-theme

# 5. Build
yarn gulp vscode-darwin-arm64-min  # macOS ARM
# or
yarn gulp vscode-darwin-x64-min    # macOS Intel
# or
yarn gulp vscode-linux-x64-min     # Linux
# or
yarn gulp vscode-win32-x64-min     # Windows
```

## Bundled Extensions

### CAIIDE++ Memory

Persistent memory integration via Memory MCP server.

**Features:**
- Semantic search across your coding memory
- Store code snippets, notes, and references
- Activity bar integration with search panel
- Keyboard shortcuts (Cmd+Shift+M for search)

**Requirements:**
- Memory MCP server running (`python -m memory_mcp.server`)
- Redis (optional, for hot cache)

### CAIIDE++ Theme

Claude-inspired color scheme with two variants:

**Light Theme:**
- Warm beige/cream backgrounds (#FAF9F6, #F5F1EB)
- Terracotta accents (#DA7756)
- Easy on the eyes for extended coding sessions

**Dark Theme:**
- Warm dark brown backgrounds (#1E1A14)
- Same terracotta accents
- Maintains warmth without harsh contrast

## Configuration

### Memory MCP Server

Configure the Memory MCP connection in settings:

```json
{
    "caiide-memory.serverCommand": "python -m memory_mcp.server",
    "caiide-memory.autoConnect": true
}
```

### Theme

To switch themes:
1. Open Command Palette (Cmd+Shift+P)
2. Type "Color Theme"
3. Select "CAIIDE++ Light" or "CAIIDE++ Dark"

## Telemetry

**All telemetry is disabled.** CAIIDE++ does not:
- Send crash reports to Microsoft
- Collect usage analytics
- Phone home in any way

You can verify this in the source code - all telemetry modules are stubbed out.

## Extension Marketplace

CAIIDE++ uses [Open VSX](https://open-vsx.org) instead of Microsoft's marketplace:

- Community-driven, open-source registry
- Same extension format as VS Code
- Most popular extensions are available

To publish your own extensions, see [Open VSX Publishing](https://github.com/eclipse/openvsx/wiki/Publishing-Extensions).

## Building Custom Icons

The default VS Code icons should be replaced with CAIIDE++ branding:

```
resources/
├── darwin/
│   └── code.icns          # macOS app icon (1024x1024)
├── linux/
│   ├── code.png           # Linux icon (512x512)
│   └── code_*.png         # Various sizes
└── win32/
    └── code.ico           # Windows icon (multi-resolution)
```

## Development

### Project Structure

```
CAIIDE++/
├── build-caiide.sh        # Main build script
├── product.json           # Branding & marketplace config
├── patches/               # Telemetry removal patches
├── extensions/
│   ├── memory-mcp/        # Memory MCP extension
│   └── caiide-theme/      # Theme extension
├── vscode-base/           # Cloned VS Code (after build)
└── build/                 # Built application
```

### Running from Source

```bash
cd vscode-base
yarn watch
# In another terminal:
./scripts/code.sh
```

### Extension Development

Extensions are standard VS Code extensions. To develop:

```bash
cd extensions/caiide-memory
npm install
npm run watch
```

Then press F5 in VS Code to launch Extension Development Host.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE)

## Credits

- Based on [VS Code](https://github.com/microsoft/vscode) by Microsoft
- Extension marketplace by [Open VSX](https://open-vsx.org)
- Memory system powered by [Memory MCP](../python/)
- Theme inspired by [Claude](https://claude.ai) by Anthropic
