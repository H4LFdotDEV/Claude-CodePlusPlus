#!/bin/bash
# Claude Code++ Uninstallation Script
# Jeremiah Kroesche | Halfservers LLC

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.claude-code-pp"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DRY_RUN=false
KEEP_DATA=false
KEEP_DOCKER=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --keep-data)
            KEEP_DATA=true
            shift
            ;;
        --keep-docker)
            KEEP_DOCKER=true
            shift
            ;;
        --help|-h)
            echo "Claude Code++ Uninstallation Script"
            echo ""
            echo "Usage: ./uninstall.sh [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run      Show what would be done without making changes"
            echo "  --keep-data    Keep memory data (SQLite, FAISS indices)"
            echo "  --keep-docker  Don't stop Docker containers"
            echo "  --help, -h     Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

run_cmd() {
    if [ "$DRY_RUN" = true ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $1"
    else
        eval "$1"
    fi
}

echo ""
echo -e "${RED}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║${NC}           Claude Code++ Uninstallation                  ${RED}║${NC}"
echo -e "${RED}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    log_warn "Running in dry-run mode - no changes will be made"
    echo ""
fi

# Confirmation
if [ "$DRY_RUN" = false ]; then
    echo -e "${YELLOW}This will remove Claude Code++ from your system.${NC}"
    if [ "$KEEP_DATA" = false ]; then
        echo -e "${RED}WARNING: This will delete all memory data!${NC}"
        echo "Use --keep-data to preserve your memory database."
    fi
    echo ""
    read -p "Are you sure you want to continue? [y/N] " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Uninstallation cancelled"
        exit 0
    fi
    echo ""
fi

# =============================================================================
# Step 1: Stop Docker Services
# =============================================================================

if [ "$KEEP_DOCKER" = false ]; then
    log_info "Stopping Docker services..."

    if [ -f "$SCRIPT_DIR/docker/docker-compose.yaml" ]; then
        cd "$SCRIPT_DIR/docker"

        if command -v docker-compose &> /dev/null; then
            run_cmd "docker-compose down 2>/dev/null || true"
            log_success "Docker services stopped"
        else
            log_warn "docker-compose not found"
        fi

        cd "$SCRIPT_DIR"
    else
        log_info "No docker-compose.yaml found"
    fi

    echo ""
fi

# =============================================================================
# Step 2: Uninstall Python Package
# =============================================================================

log_info "Uninstalling Python package..."

if python3 -c "import memory_mcp" &> /dev/null 2>&1; then
    run_cmd "pip3 uninstall memory-mcp -y 2>/dev/null || true"
    log_success "memory-mcp uninstalled"
else
    log_info "memory-mcp not installed"
fi

echo ""

# =============================================================================
# Step 3: Remove Binaries
# =============================================================================

log_info "Removing binaries..."

if [ -f "$INSTALL_DIR/bin/system-controller-cli" ]; then
    run_cmd "rm -f '$INSTALL_DIR/bin/system-controller-cli'"
    log_success "Removed system-controller-cli"
fi

# Check for global installation
if [ -f "/usr/local/bin/system-controller-cli" ]; then
    log_warn "Found /usr/local/bin/system-controller-cli"
    log_info "Remove manually if desired: sudo rm /usr/local/bin/system-controller-cli"
fi

echo ""

# =============================================================================
# Step 4: Remove Configuration
# =============================================================================

log_info "Removing configuration..."

# Remove config directory
if [ -d "$INSTALL_DIR/config" ]; then
    run_cmd "rm -rf '$INSTALL_DIR/config'"
    log_success "Removed config directory"
fi

# Remove logs
if [ -d "$INSTALL_DIR/logs" ]; then
    run_cmd "rm -rf '$INSTALL_DIR/logs'"
    log_success "Removed logs directory"
fi

# Remove cache
if [ -d "$INSTALL_DIR/cache" ]; then
    run_cmd "rm -rf '$INSTALL_DIR/cache'"
    log_success "Removed cache directory"
fi

# Remove bin
if [ -d "$INSTALL_DIR/bin" ]; then
    run_cmd "rm -rf '$INSTALL_DIR/bin'"
    log_success "Removed bin directory"
fi

echo ""

# =============================================================================
# Step 5: Remove Data (Optional)
# =============================================================================

if [ "$KEEP_DATA" = false ]; then
    log_info "Removing memory data..."

    if [ -d "$INSTALL_DIR/memory" ]; then
        run_cmd "rm -rf '$INSTALL_DIR/memory'"
        log_success "Removed memory directory"
    fi
else
    log_info "Keeping memory data (--keep-data specified)"
    log_info "Data location: $INSTALL_DIR/memory"
fi

echo ""

# =============================================================================
# Step 6: Remove Installation Directory
# =============================================================================

log_info "Cleaning up installation directory..."

# Check if directory is empty or only contains memory (if kept)
if [ -d "$INSTALL_DIR" ]; then
    if [ "$KEEP_DATA" = true ]; then
        # Only remove if empty except for memory
        REMAINING=$(ls -A "$INSTALL_DIR" | grep -v "^memory$" || true)
        if [ -z "$REMAINING" ]; then
            log_info "Installation directory contains only preserved data"
        else
            log_warn "Unexpected files in $INSTALL_DIR: $REMAINING"
        fi
    else
        # Remove entire directory
        run_cmd "rm -rf '$INSTALL_DIR'"
        log_success "Removed $INSTALL_DIR"
    fi
fi

echo ""

# =============================================================================
# Step 7: Clean Swift Build Artifacts
# =============================================================================

log_info "Cleaning build artifacts..."

if [ -d "$SCRIPT_DIR/swift-system-controller/.build" ]; then
    run_cmd "rm -rf '$SCRIPT_DIR/swift-system-controller/.build'"
    log_success "Removed Swift build directory"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}           Uninstallation Complete!                      ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$KEEP_DATA" = true ]; then
    echo "Memory data preserved at: $INSTALL_DIR/memory"
    echo ""
fi

echo "Manual cleanup (if desired):"
echo "  - Remove MCP entries from ~/.claude.json"
echo "  - Revoke accessibility permissions in System Preferences"

if [ "$KEEP_DOCKER" = true ]; then
    echo "  - Stop Docker: docker-compose -f docker/docker-compose.yaml down"
fi

echo ""
echo "To reinstall, run: ./install.sh"
