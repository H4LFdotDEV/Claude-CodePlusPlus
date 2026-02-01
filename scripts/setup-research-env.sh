#!/bin/bash

# ============================================================================
# ROOM-SCALE CLAUDE RESEARCH ENVIRONMENT
# Setup Script for M4 Mac Mini
# ============================================================================
# Author: Jeremiah Kroesche | Halfservers LLC
# Purpose: Configure a voice + vision enabled Claude research environment
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}"
echo "============================================================================"
echo "  ROOM-SCALE CLAUDE RESEARCH ENVIRONMENT SETUP"
echo "  For M4 Mac Mini"
echo "============================================================================"
echo -e "${NC}"

# ----------------------------------------------------------------------------
# STEP 1: Check Prerequisites
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 1/7] Checking prerequisites...${NC}"

# Check if running on macOS
if [[ "$(uname)" != "Darwin" ]]; then
    echo -e "${RED}Error: This script is designed for macOS.${NC}"
    exit 1
fi

# Check for Apple Silicon
if [[ "$(uname -m)" != "arm64" ]]; then
    echo -e "${YELLOW}Warning: This script is optimized for Apple Silicon (M-series).${NC}"
fi

echo -e "${GREEN}✓ Running on macOS Apple Silicon${NC}"

# ----------------------------------------------------------------------------
# STEP 2: Install Homebrew (if not present)
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 2/7] Checking Homebrew...${NC}"

if ! command -v brew &> /dev/null; then
    echo "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    
    # Add Homebrew to PATH for Apple Silicon
    echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> ~/.zprofile
    eval "$(/opt/homebrew/bin/brew shellenv)"
else
    echo -e "${GREEN}✓ Homebrew already installed${NC}"
fi

# ----------------------------------------------------------------------------
# STEP 3: Install System Dependencies
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 3/7] Installing system dependencies...${NC}"

# Essential tools
brew install --quiet ffmpeg node portaudio python@3.12

# Verify installations
echo -e "${GREEN}✓ ffmpeg $(ffmpeg -version 2>&1 | head -n1 | cut -d' ' -f3)${NC}"
echo -e "${GREEN}✓ node $(node --version)${NC}"
echo -e "${GREEN}✓ python $(python3 --version)${NC}"

# ----------------------------------------------------------------------------
# STEP 4: Install UV (Python package manager)
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 4/7] Installing UV package manager...${NC}"

if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    
    # Source the UV installation
    source "$HOME/.local/bin/env" 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
else
    echo -e "${GREEN}✓ UV already installed${NC}"
fi

# Verify UV
echo -e "${GREEN}✓ uv $(uv --version)${NC}"

# ----------------------------------------------------------------------------
# STEP 5: Install Claude Code CLI
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 5/7] Checking Claude Code CLI...${NC}"

if ! command -v claude &> /dev/null; then
    echo "Installing Claude Code CLI via npm..."
    npm install -g @anthropic-ai/claude-code
else
    echo -e "${GREEN}✓ Claude Code CLI already installed${NC}"
fi

# ----------------------------------------------------------------------------
# STEP 6: Install VoiceMode
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 6/7] Installing VoiceMode...${NC}"

# Install voice-mode
uv tool install voice-mode --force

# Run the VoiceMode installer for additional dependencies
echo "Running VoiceMode dependency installer..."
uvx voice-mode-install || echo -e "${YELLOW}Note: Some optional dependencies may not have installed. Core functionality should work.${NC}"

# Add VoiceMode to Claude
echo "Adding VoiceMode to Claude MCP..."
claude mcp add --scope user voicemode -- uvx --refresh voice-mode 2>/dev/null || \
    echo -e "${YELLOW}Note: Run 'claude mcp add --scope user voicemode -- uvx --refresh voice-mode' manually if needed${NC}"

echo -e "${GREEN}✓ VoiceMode installed${NC}"

# ----------------------------------------------------------------------------
# STEP 7: Install mcp-webcam
# ----------------------------------------------------------------------------
echo -e "${YELLOW}[Step 7/7] Installing mcp-webcam...${NC}"

# Add webcam MCP to Claude
claude mcp add-json "webcam" '{"command":"npx","args":["-y","@llmindset/mcp-webcam"]}' 2>/dev/null || \
    echo -e "${YELLOW}Note: Run the mcp add command manually if needed${NC}"

echo -e "${GREEN}✓ mcp-webcam configured${NC}"

# ----------------------------------------------------------------------------
# Create Research Directory Structure
# ----------------------------------------------------------------------------
echo -e "${YELLOW}Creating research directory structure...${NC}"

RESEARCH_DIR="$HOME/Research/PocketDimension"
mkdir -p "$RESEARCH_DIR"/{sessions,diagrams,simulations,documentation,exports}

# Create a README for the research directory
cat > "$RESEARCH_DIR/README.md" << 'EOF'
# Pocket Dimension Research Project

**Researcher:** Jeremiah Kroesche | Halfservers LLC

## Directory Structure

- `sessions/` - Voice session transcripts and notes
- `diagrams/` - Whiteboard captures and sketches
- `simulations/` - Physics simulation code and results
- `documentation/` - Formal documentation and papers
- `exports/` - Exportable summaries and reports

## Quick Start

1. Start a voice session: `claude converse`
2. Point webcam at whiteboard
3. Say "Claude, capture the whiteboard" to save a snapshot
4. All sessions are auto-logged

## Key Research Areas

1. Vacuum manipulation via Casimir effect
2. Geometry-dependent vacuum energy
3. ER = EPR and entanglement-based storage
4. Information encoding (holographic principle)

## Commands

- Start voice conversation: `claude converse`
- Access webcam UI: http://localhost:3333

---

*"The path might be narrow but in Christ I can do all things."*
EOF

echo -e "${GREEN}✓ Research directory created at: $RESEARCH_DIR${NC}"

# ----------------------------------------------------------------------------
# Create Environment Configuration
# ----------------------------------------------------------------------------
echo -e "${YELLOW}Creating environment configuration...${NC}"

# Create a config file for easy customization
cat > "$HOME/.research-env" << 'EOF'
# Room-Scale Claude Research Environment Configuration
# Source this file: source ~/.research-env

# OpenAI API Key (for VoiceMode TTS/STT if using OpenAI)
# Uncomment and add your key if you have one:
# export OPENAI_API_KEY="your-key-here"

# VoiceMode Settings
export VOICEMODE_SAVE_AUDIO=true

# Research Directory
export RESEARCH_DIR="$HOME/Research/PocketDimension"

# Aliases for quick access
alias research="cd $HOME/Research/PocketDimension"
alias voice="claude converse"
alias webcam-ui="open http://localhost:3333"

# Function to start a research session
start_research() {
    echo "Starting Room-Scale Claude Research Environment..."
    echo "1. Webcam UI will open at http://localhost:3333"
    echo "2. Point your camera at your whiteboard"
    echo "3. Voice mode will start automatically"
    echo ""
    echo "Say 'Claude, capture the whiteboard' to save snapshots"
    echo ""
    
    # Start webcam server in background
    npx @llmindset/mcp-webcam &
    WEBCAM_PID=$!
    
    # Wait a moment for server to start
    sleep 2
    
    # Open webcam UI
    open http://localhost:3333
    
    # Start voice conversation
    claude converse
    
    # Cleanup when done
    kill $WEBCAM_PID 2>/dev/null
}

echo "Research environment loaded. Type 'start_research' to begin."
EOF

# Add to shell profile
if [[ -f "$HOME/.zshrc" ]]; then
    if ! grep -q "source ~/.research-env" "$HOME/.zshrc"; then
        echo "" >> "$HOME/.zshrc"
        echo "# Room-Scale Claude Research Environment" >> "$HOME/.zshrc"
        echo "source ~/.research-env" >> "$HOME/.zshrc"
    fi
fi

echo -e "${GREEN}✓ Environment configuration created${NC}"

# ----------------------------------------------------------------------------
# Final Summary
# ----------------------------------------------------------------------------
echo ""
echo -e "${BLUE}============================================================================${NC}"
echo -e "${GREEN}  SETUP COMPLETE!${NC}"
echo -e "${BLUE}============================================================================${NC}"
echo ""
echo -e "Your Room-Scale Claude Research Environment is ready."
echo ""
echo -e "${YELLOW}Next Steps:${NC}"
echo ""
echo "1. ${BLUE}Restart your terminal${NC} or run: source ~/.research-env"
echo ""
echo "2. ${BLUE}Get a webcam${NC} (recommendations below)"
echo ""
echo "3. ${BLUE}Start researching:${NC}"
echo "   - Type 'start_research' to launch everything"
echo "   - Or manually:"
echo "     • Start webcam: npx @llmindset/mcp-webcam"
echo "     • Open UI: http://localhost:3333"
echo "     • Start voice: claude converse"
echo ""
echo -e "${YELLOW}Camera Recommendations (Budget-Friendly):${NC}"
echo "  • Logitech C920/C922 (~\$50-70) - Great quality, reliable"
echo "  • Logitech Brio 100 (~\$40) - Budget option, decent quality"
echo "  • Any 1080p USB webcam works for whiteboard capture"
echo ""
echo -e "${YELLOW}Optional: Set up OpenAI API key for cloud TTS/STT${NC}"
echo "  Edit ~/.research-env and add your OPENAI_API_KEY"
echo "  (VoiceMode can also use local models - see their docs)"
echo ""
echo -e "${YELLOW}Research Directory:${NC} $RESEARCH_DIR"
echo ""
echo -e "${BLUE}============================================================================${NC}"
echo -e "  Jeremiah Kroesche | Halfservers LLC"
echo -e "  'The path might be narrow but in Christ I can do all things.'"
echo -e "${BLUE}============================================================================${NC}"
