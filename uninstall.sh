#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/.claude-code-pp"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║                Claude Code++ Uninstaller                   ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo "This will remove:"
echo "  - $INSTALL_DIR (all memories and data)"
echo "  - Memory MCP entries from ~/.claude.json"
echo "  - memory_mcp Python package"
echo ""
echo -e "${YELLOW}WARNING: This will delete all stored memories!${NC}"
echo ""
read -p "Are you sure you want to continue? [y/N]: " confirm

if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 0
fi

# Backup memories before deletion
echo ""
read -p "Create backup of memories before deletion? [Y/n]: " backup
backup=${backup:-Y}

if [[ "$backup" =~ ^[Yy]$ ]]; then
    BACKUP_FILE="$HOME/claude-code-pp-backup-$(date +%Y%m%d%H%M%S).tar.gz"
    info "Creating backup..."
    if [ -d "$INSTALL_DIR" ]; then
        tar -czf "$BACKUP_FILE" -C "$HOME" ".claude-code-pp" 2>/dev/null || true
        success "Backup saved to $BACKUP_FILE"
    fi
fi

# Remove installation directory
if [ -d "$INSTALL_DIR" ]; then
    info "Removing $INSTALL_DIR..."
    rm -rf "$INSTALL_DIR"
    success "Removed installation directory"
else
    info "Installation directory not found"
fi

# Remove from Claude config
CLAUDE_CONFIG="$HOME/.claude.json"
if [ -f "$CLAUDE_CONFIG" ] && command -v jq &> /dev/null; then
    info "Removing MCP servers from Claude config..."
    TEMP_CONFIG=$(mktemp)
    jq 'del(.mcpServers.memory) | del(.mcpServers.prompts)' "$CLAUDE_CONFIG" > "$TEMP_CONFIG"
    mv "$TEMP_CONFIG" "$CLAUDE_CONFIG"
    success "Updated ~/.claude.json"
else
    warn "Please manually remove 'memory' and 'prompts' from ~/.claude.json mcpServers"
fi

# Uninstall Python package
info "Uninstalling Python package..."
pip3 uninstall -y memory-mcp 2>/dev/null || pip uninstall -y memory-mcp 2>/dev/null || true
success "Python package uninstalled"

# Stop Redis if running via Homebrew
if [[ "$OSTYPE" == "darwin"* ]]; then
    read -p "Stop Redis service? [y/N]: " stop_redis
    if [[ "$stop_redis" =~ ^[Yy]$ ]]; then
        brew services stop redis 2>/dev/null || true
        success "Redis stopped"
    fi
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════╗"
echo "║              Uninstallation Complete!                      ║"
echo "╚═══════════════════════════════════════════════════════════╝${NC}"
echo ""
if [[ "$backup" =~ ^[Yy]$ ]] && [ -f "$BACKUP_FILE" ]; then
    echo "Your data was backed up to: $BACKUP_FILE"
fi
echo ""
