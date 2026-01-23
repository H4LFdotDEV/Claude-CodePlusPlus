# System Controller

macOS Accessibility API integration for screen reading and system control.

## Overview

The System Controller is a Swift-based MCP server that provides Claude with the ability to interact with macOS through the Accessibility API. This enables screen reading, mouse control, keyboard input, and window management.

## Requirements

- macOS 12.0+
- Accessibility permissions granted in System Preferences

## Granting Permissions

1. Open **System Preferences** > **Privacy & Security** > **Accessibility**
2. Click the lock to make changes
3. Add your terminal application (Terminal, iTerm2, etc.)
4. Add Claude Code if running as a standalone app

## MCP Tools

### Mouse Control

| Tool | Description |
|------|-------------|
| `click` | Click at coordinates |
| `double_click` | Double-click at coordinates |
| `right_click` | Right-click at coordinates |
| `scroll` | Scroll at coordinates |

### Keyboard Control

| Tool | Description |
|------|-------------|
| `type_text` | Type text with optional modifiers |
| `hotkey` | Press keyboard shortcuts |

### Clipboard

| Tool | Description |
|------|-------------|
| `clipboard_get` | Read clipboard contents |
| `clipboard_set` | Write to clipboard |

### Window Management

| Tool | Description |
|------|-------------|
| `focus_app` | Focus application by name |
| `move_window` | Move window to coordinates |
| `resize_window` | Resize window |
| `get_active_window` | Get current window info |

### Screen Reading

| Tool | Description |
|------|-------------|
| `screen_read_at` | Read text at coordinates |
| `check_accessibility` | Verify permissions |

## Permission Levels

| Level | Name | Capabilities |
|-------|------|--------------|
| 0 | Sandboxed | Read-only screen access |
| 1 | Observer | Screen reading, clipboard read |
| 2 | Basic | Mouse click, basic keyboard |
| 3 | Standard | Full keyboard, clipboard write |
| 4 | Elevated | Window management, app focus |
| 5 | Unrestricted | All capabilities |

## Configuration

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

## Usage Examples

### Click at Coordinates

```
system_click(x=100, y=200)
```

### Type Text

```
system_type_text(text="Hello, World!")
```

### Keyboard Shortcut

```
system_hotkey(keys=["cmd", "c"])  # Copy
system_hotkey(keys=["cmd", "v"])  # Paste
```

### Focus Application

```
system_focus_app(name="Safari")
```

### Read Screen Text

```
system_screen_read_at(x=100, y=200, width=300, height=50)
```

## Troubleshooting

### Permission Denied

```bash
# Check accessibility permissions
system-controller-cli --check-permissions
```

If permissions aren't working:
1. Remove the app from Accessibility list
2. Re-add it
3. Restart the terminal

### Controller Not Found

```bash
# Verify installation
which system-controller-cli

# Check if binary exists
ls -la ~/.claude-code-pp/bin/system-controller-cli
```

### Building from Source

```bash
cd swift-system-controller
swift build -c release
cp .build/release/system-controller-cli ~/.claude-code-pp/bin/
```

## Security Considerations

- The System Controller has significant system access
- Only grant permissions to trusted applications
- Consider using lower permission levels for routine tasks
- Review actions before allowing automated control

## Related Pages

- [[Architecture]] - System overview
- [[Configuration]] - Setup options
- [[Troubleshooting]] - Common issues
