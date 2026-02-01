#!/bin/bash
# Claude Code++ Quick Install
# Usage: curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/quick-install.sh | bash
#
# Or with options:
#   curl -fsSL ... | bash -s -- --profile standard --with-openclaw

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
REPO_URL="https://github.com/H4LFdotDEV/Claude-CodePlusPlus.git"
INSTALL_DIR="$HOME/.claude-code-pp"
CLONE_DIR="$HOME/.claude-code-pp-src"

# Parse arguments
PROFILE=""
WITH_OPENCLAW="false"
QUICK_MODE="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        --profile)
            PROFILE="$2"
            shift 2
            ;;
        --with-openclaw)
            WITH_OPENCLAW="true"
            shift
            ;;
        --quick|-q)
            QUICK_MODE="true"
            shift
            ;;
        --help|-h)
            echo "Claude Code++ Quick Install"
            echo ""
            echo "Usage: curl -fsSL <url> | bash -s -- [options]"
            echo ""
            echo "Options:"
            echo "  --profile <name>   Set installation profile (minimal/standard/full/enterprise)"
            echo "  --with-openclaw    Include OpenClaw multi-channel gateway"
            echo "  --quick, -q        Use all defaults, no prompts"
            echo "  --help, -h         Show this help"
            echo ""
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Print banner
echo -e "${CYAN}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              Claude Code++ Quick Install                       ║"
echo "║     AI-Native Development with Persistent Memory               ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Step counter
TOTAL_STEPS=6
current_step=0

step() {
    current_step=$((current_step + 1))
    echo ""
    echo -e "${BOLD}[${current_step}/${TOTAL_STEPS}]${NC} ${CYAN}$1${NC}"
    echo ""
}

info() { echo -e "  ${BLUE}→${NC} $1"; }
success() { echo -e "  ${GREEN}✓${NC} $1"; }
warn() { echo -e "  ${YELLOW}!${NC} $1"; }
error() { echo -e "  ${RED}✗${NC} $1"; exit 1; }

# Check prerequisites
step "Checking prerequisites"

# Python
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
        success "Python $PYTHON_VERSION"
    else
        error "Python 3.10+ required (found $PYTHON_VERSION)"
    fi
else
    error "Python 3 not found. Please install Python 3.10+"
fi

# Git
if command -v git &> /dev/null; then
    success "Git found"
else
    error "Git not found. Please install Git"
fi

# Docker (optional)
DOCKER_OK="false"
if command -v docker &> /dev/null && docker info &>/dev/null 2>&1; then
    success "Docker running"
    DOCKER_OK="true"
else
    warn "Docker not running (optional - some features unavailable)"
fi

# Node.js (optional for OpenClaw)
NODE_OK="false"
if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v | sed 's/v\([0-9]*\).*/\1/')
    if [[ "$NODE_VERSION" =~ ^[0-9]+$ ]] && [ "$NODE_VERSION" -ge 22 ]; then
        success "Node.js $NODE_VERSION"
        NODE_OK="true"
    else
        warn "Node.js $NODE_VERSION (22+ required for OpenClaw)"
    fi
else
    warn "Node.js not found (optional - required for OpenClaw)"
fi

# Claude Code CLI
if command -v claude &> /dev/null; then
    success "Claude Code CLI found"
else
    warn "Claude Code CLI not found (install from: https://docs.anthropic.com/claude-code)"
fi

# Determine profile if not set
if [ -z "$PROFILE" ]; then
    if [ "$QUICK_MODE" == "true" ]; then
        # Auto-detect based on resources
        RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/{print $2}' || sysctl -n hw.memsize 2>/dev/null | awk '{print int($1/1024/1024/1024)}')
        if [ "$DOCKER_OK" == "true" ] && [ "${RAM_GB:-4}" -ge 8 ]; then
            PROFILE="full"
        elif [ "$DOCKER_OK" == "true" ] && [ "${RAM_GB:-4}" -ge 4 ]; then
            PROFILE="standard"
        else
            PROFILE="minimal"
        fi
        info "Auto-selected profile: $PROFILE"
    else
        echo ""
        echo "Installation profiles:"
        echo "  ${GREEN}standard${NC}   - Redis + SQLite + Vault (recommended)"
        echo "  minimal    - SQLite + Vault only (lightweight)"
        echo "  full       - + Neo4j/Graphiti knowledge graph"
        echo "  enterprise - + livegrep code search"
        echo ""
        read -p "Select profile [standard]: " PROFILE
        PROFILE=${PROFILE:-standard}
    fi
fi

info "Profile: $PROFILE"

# Check OpenClaw
if [ "$WITH_OPENCLAW" != "true" ] && [ "$QUICK_MODE" != "true" ]; then
    if [ "$NODE_OK" == "true" ]; then
        echo ""
        read -p "Install OpenClaw multi-channel gateway? [Y/n]: " install_oc
        install_oc=${install_oc:-Y}
        if [[ "$install_oc" =~ ^[Yy]$ ]]; then
            WITH_OPENCLAW="true"
        fi
    fi
fi

# Pre-flight summary
step "Installation Summary"

echo "  Installation directory: $INSTALL_DIR"
echo "  Profile: $PROFILE"
echo "  OpenClaw: $([ "$WITH_OPENCLAW" == "true" ] && echo "Yes" || echo "No")"
echo ""
echo "  Components:"
case $PROFILE in
    minimal)
        echo "    - SQLite (cold storage)"
        echo "    - Vault (archive tier)"
        ;;
    standard)
        echo "    - Redis (hot cache)"
        echo "    - SQLite (cold storage)"
        echo "    - Vault (archive tier)"
        ;;
    full)
        echo "    - Redis (hot cache)"
        echo "    - Neo4j/Graphiti (knowledge graph)"
        echo "    - SQLite (cold storage)"
        echo "    - Vault (archive tier)"
        ;;
    enterprise)
        echo "    - Redis (hot cache)"
        echo "    - Neo4j/Graphiti (knowledge graph)"
        echo "    - livegrep (code search)"
        echo "    - SQLite (cold storage)"
        echo "    - Vault (archive tier)"
        ;;
esac
if [ "$WITH_OPENCLAW" == "true" ]; then
    echo "    - OpenClaw (multi-channel AI gateway)"
fi

if [ "$QUICK_MODE" != "true" ]; then
    echo ""
    read -p "Proceed with installation? [Y/n]: " proceed
    proceed=${proceed:-Y}
    if [[ ! "$proceed" =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 0
    fi
fi

# Clone repository
step "Downloading Claude Code++"

if [ -d "$CLONE_DIR" ]; then
    info "Updating existing repository..."
    cd "$CLONE_DIR"
    git pull --quiet || warn "Could not update repository"
else
    info "Cloning repository..."
    git clone --depth 1 --quiet "$REPO_URL" "$CLONE_DIR"
fi

success "Repository ready"

# Run main installer
step "Running installer"

cd "$CLONE_DIR"

# Build installer args
INSTALLER_ARGS=""
if [ "$QUICK_MODE" == "true" ]; then
    export CAIIDE_REMOTE_INSTALL="true"
fi

export CAIIDE_PROFILE="$PROFILE"

if [ "$WITH_OPENCLAW" == "true" ]; then
    export SETUP_OPENCLAW="true"
fi

# Run installer
chmod +x install.sh
./install.sh

# Final step
step "Verifying installation"

if [ -x "$INSTALL_DIR/bin/memory-mcp" ]; then
    success "Memory MCP server installed"
else
    warn "Memory MCP server not found"
fi

if [ -f "$HOME/.claude.json" ] && grep -q "memory" "$HOME/.claude.json" 2>/dev/null; then
    success "Claude Code configured"
else
    warn "Claude Code configuration may need manual setup"
fi

if [ "$WITH_OPENCLAW" == "true" ] && command -v openclaw &> /dev/null; then
    success "OpenClaw installed"
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                   Installation Complete!                       ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Next steps:"
echo "  1. Restart your terminal or run: source ~/.zshrc"
echo "  2. Run: claude"
echo "  3. In Claude, run: memory_stats"
if [ "$WITH_OPENCLAW" == "true" ]; then
    echo "  4. Start OpenClaw: openclaw gateway run"
fi
echo ""
echo "Documentation: https://github.com/H4LFdotDEV/Claude-CodePlusPlus/wiki"
echo ""
