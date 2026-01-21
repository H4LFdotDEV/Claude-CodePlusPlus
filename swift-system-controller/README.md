# Swift System Controller

macOS Accessibility API integration for Claude Code++. Provides screen reading, mouse/keyboard control, and window management through MCP protocol.

## Requirements

- macOS 12.0+
- Swift 5.9+
- Accessibility permissions in System Preferences

## Building

```bash
# Build
swift build

# Build release
swift build -c release

# Run tests
swift test

# Install CLI globally
cp .build/release/system-controller-cli /usr/local/bin/
```

## Usage

### MCP Server Mode (stdio)

```bash
# Start MCP server
system-controller-cli --stdio

# Test with JSON-RPC
echo '{"jsonrpc":"2.0","method":"check_accessibility","params":{},"id":1}' | system-controller-cli --stdio
```

### Check Permissions

```bash
system-controller-cli --check-permissions
```

## Granting Accessibility Permissions

1. Open **System Preferences** > **Security & Privacy** > **Privacy**
2. Select **Accessibility** in the left sidebar
3. Click the lock icon and authenticate
4. Add Terminal (or your IDE) to the allowed apps
5. Restart the application

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                    MCP Protocol Layer                     │
│                 (JSON-RPC 2.0 over stdio)                │
├──────────────────────────────────────────────────────────┤
│                       MCPBridge                           │
│              (Request routing & serialization)            │
├──────────────────────────────────────────────────────────┤
│                    SystemController                       │
│    ┌─────────────┬─────────────┬─────────────────────┐  │
│    │ScreenReader │ MouseControl│ KeyboardControl     │  │
│    ├─────────────┼─────────────┼─────────────────────┤  │
│    │ WindowMgmt  │ Clipboard   │ PermissionManager   │  │
│    └─────────────┴─────────────┴─────────────────────┘  │
├──────────────────────────────────────────────────────────┤
│                  macOS Frameworks                         │
│   ApplicationServices | CoreGraphics | AppKit | Carbon    │
└──────────────────────────────────────────────────────────┘
```

## MCP Methods

### Screen Reading

#### screen_read_at
Read UI element at screen coordinates.

```json
{
  "method": "screen_read_at",
  "params": {"x": 100, "y": 200}
}
```

**Response:**
```json
{
  "result": {
    "role": "button",
    "title": "Submit",
    "value": null,
    "description": "Submit form",
    "frame": {"x": 90, "y": 190, "width": 80, "height": 30}
  }
}
```

#### get_active_window
Get information about the currently active window.

```json
{
  "method": "get_active_window",
  "params": {}
}
```

### Mouse Control

#### click
Perform mouse click at coordinates.

```json
{
  "method": "click",
  "params": {"x": 100, "y": 200, "button": "left"}
}
```

**Parameters:**
- `x`, `y` (required): Screen coordinates
- `button` (optional): `left` | `right` | `middle` (default: `left`)

#### double_click
Perform double-click at coordinates.

```json
{
  "method": "double_click",
  "params": {"x": 100, "y": 200}
}
```

#### scroll
Scroll at coordinates.

```json
{
  "method": "scroll",
  "params": {"x": 100, "y": 200, "delta_x": 0, "delta_y": -3}
}
```

**Parameters:**
- `x`, `y` (required): Screen coordinates
- `delta_y` (required): Vertical scroll amount (negative = down)
- `delta_x` (optional): Horizontal scroll amount

### Keyboard Control

#### type_text
Type text string.

```json
{
  "method": "type_text",
  "params": {"text": "Hello, World!"}
}
```

#### hotkey
Press keyboard shortcut.

```json
{
  "method": "hotkey",
  "params": {"key": "c", "modifiers": ["command"]}
}
```

**Parameters:**
- `key` (required): Key to press
- `modifiers` (optional): Array of `command` | `control` | `option` | `shift`

### Clipboard

#### clipboard_get
Read clipboard contents.

```json
{
  "method": "clipboard_get",
  "params": {}
}
```

#### clipboard_set
Set clipboard contents.

```json
{
  "method": "clipboard_set",
  "params": {"text": "Copied text"}
}
```

### Window Management

#### focus_app
Focus application by name.

```json
{
  "method": "focus_app",
  "params": {"app_name": "Safari"}
}
```

#### move_window
Move active window to position.

```json
{
  "method": "move_window",
  "params": {"x": 0, "y": 0}
}
```

#### resize_window
Resize active window.

```json
{
  "method": "resize_window",
  "params": {"width": 1200, "height": 800}
}
```

### Permission Management

#### check_accessibility
Check if accessibility permissions are granted.

```json
{
  "method": "check_accessibility",
  "params": {}
}
```

**Response:**
```json
{
  "result": {"has_access": true}
}
```

#### get_permission_level
Get current permission level.

```json
{
  "method": "get_permission_level",
  "params": {}
}
```

## Permission Levels

| Level | Name | Capabilities |
|-------|------|--------------|
| 0 | Sandboxed | Read-only screen access |
| 1 | Observer | Screen reading, clipboard read |
| 2 | Basic | Mouse click, basic keyboard |
| 3 | Standard | Full keyboard, clipboard write |
| 4 | Elevated | Window management, app focus |
| 5 | Unrestricted | All capabilities |

Configure in `~/.claude-code-pp/config/settings.yaml`:

```yaml
system_control:
  permission_level: 3
  rate_limits:
    clicks_per_second: 10
    keystrokes_per_second: 20
```

## Error Responses

### Permission Denied
```json
{
  "error": {
    "code": -32001,
    "message": "Permission denied: Accessibility access required"
  }
}
```

### Rate Limited
```json
{
  "error": {
    "code": -32002,
    "message": "Rate limited: Too many clicks"
  }
}
```

### Invalid Parameters
```json
{
  "error": {
    "code": -32602,
    "message": "Invalid params"
  }
}
```

## MCP Integration

Add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "system-controller": {
      "command": "system-controller-cli",
      "args": ["--stdio"]
    }
  }
}
```

Or with full path:

```json
{
  "mcpServers": {
    "system-controller": {
      "command": "/usr/local/bin/system-controller-cli",
      "args": ["--stdio"]
    }
  }
}
```

## Module Structure

```
Sources/
├── SystemController/
│   ├── SystemController.swift   # Main controller
│   ├── PermissionManager.swift  # Permission handling
│   ├── RateLimiter.swift        # Rate limiting
│   └── ActionLogger.swift       # Action logging
├── MCPBridge/
│   └── MCPBridge.swift          # MCP protocol bridge
└── CLI/
    └── main.swift               # CLI entry point

Tests/
└── SystemControllerTests/
    └── SystemControllerTests.swift
```

## Troubleshooting

### "Accessibility access required"

Grant accessibility permissions:
1. System Preferences > Security & Privacy > Privacy > Accessibility
2. Add your terminal or IDE
3. Restart the application

### "Rate limited"

Reduce action frequency or adjust rate limits:

```yaml
system_control:
  rate_limits:
    clicks_per_second: 20  # Increase limit
```

### Build errors

Ensure Xcode command line tools are installed:
```bash
xcode-select --install
```

### Permission not persisting

Try resetting:
```bash
tccutil reset Accessibility
```

Then re-grant permissions.

## Security Considerations

- All actions are logged to `~/.claude-code-pp/logs/actions.log`
- Rate limiting prevents abuse
- Permission levels restrict capabilities
- No actions are performed without explicit MCP request
- The controller never initiates actions on its own

## Development

### Running Tests

```bash
swift test -v
```

### Code Coverage

```bash
swift test --enable-code-coverage
xcrun llvm-cov report .build/debug/SystemControllerPackageTests.xctest/Contents/MacOS/SystemControllerPackageTests
```

### Linting

```bash
swiftlint
```
