# Room-Scale Research Environment

Voice and vision integration for hands-free Claude interaction with whiteboard support.

## Overview

The Research Environment extends Claude Code++ with:

- **Voice Mode** - Natural voice conversations with Claude
- **Webcam Integration** - Show Claude diagrams, whiteboards, or physical documents
- **Session Management** - Automatic logging and organization of research sessions

## Quick Start

```bash
# Run the setup script
./scripts/setup-research-env.sh

# Start a research session
start_research
```

## Components

### VoiceMode

[VoiceMode](https://github.com/anthropics/voice-mode) enables hands-free interaction:

```bash
# Start voice conversation
claude converse

# Or use the alias
voice
```

**Voice Commands:**
- "Capture the whiteboard" - Save current camera view
- "Document this insight" - Store to memory
- "Summarize what we've discussed" - Get session summary

### mcp-webcam

[mcp-webcam](https://github.com/evalstate/mcp-webcam) provides camera access:

```bash
# Start webcam server
npx @llmindset/mcp-webcam

# Open control UI
open http://localhost:3333
```

**Features:**
- Live camera preview
- Snapshot capture
- Multi-camera support

## Integration with Memory MCP

The Research Environment integrates with the Memory MCP for persistent storage:

| Content Type | Storage Location |
|--------------|------------------|
| Voice transcripts | SQLite (cold tier) |
| Whiteboard captures | Vault (archive tier) |
| Session context | Redis (hot tier) |
| Key insights | Graphiti (warm tier) |

### Storing Captures to Memory

```python
# Whiteboard captures can be stored via MCP
memory_store({
    "content": "Whiteboard capture: Casimir effect geometry",
    "type": "reference",
    "tags": ["whiteboard", "physics", "casimir"],
    "source": "diagrams/2024-01-26-casimir.png"
})
```

## Directory Structure

```
~/Research/PocketDimension/
├── sessions/           # Voice session transcripts
├── diagrams/           # Whiteboard captures
├── simulations/        # Physics code & results
├── documentation/      # Formal docs
└── exports/            # Shareable outputs
```

## Hardware Requirements

### Recommended Webcams

| Camera | Price | Notes |
|--------|-------|-------|
| Logitech C920 | ~$50-70 | Best value, excellent quality |
| Logitech Brio 100 | ~$40 | Budget-friendly |
| Any 1080p USB webcam | $20-40 | Works fine for whiteboard |

### Webcam Setup Tips

1. **Position:** 2-4 feet from whiteboard
2. **Lighting:** Even lighting, avoid glare
3. **Angle:** Straight-on view
4. **Focus:** Manual focus on whiteboard if available

## Environment Configuration

The setup creates `~/.research-env`:

```bash
# OpenAI API Key (optional, for cloud TTS/STT)
export OPENAI_API_KEY="your-key-here"

# VoiceMode settings
export VOICEMODE_SAVE_AUDIO=true

# Research directory
export RESEARCH_DIR="$HOME/Research/PocketDimension"

# Aliases
alias research="cd $RESEARCH_DIR"
alias voice="claude converse"
alias webcam-ui="open http://localhost:3333"
```

## Permissions Required

Grant these in System Preferences > Privacy & Security:

- **Microphone** - Terminal
- **Camera** - Terminal, Browser
- **Accessibility** - Terminal (for System Controller)

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No audio | Check System Preferences > Sound > Input |
| Webcam not found | Reconnect USB, check Privacy > Camera |
| Voice not responding | Run `claude auth` to authenticate |
| Webcam UI won't load | Run `npx @llmindset/mcp-webcam` manually |

## See Also

- [Quick Reference Card](../docs/whiteboard-quick-reference.md)
- [Memory MCP Behavioral Guidelines](Memory-MCP-Behavioral-Guidelines.md)
- [System Controller](System-Controller.md)
