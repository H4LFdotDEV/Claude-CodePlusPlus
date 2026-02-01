#!/bin/bash
#
# Claude Code++ Remote Installer
# One-line install: curl -fsSL https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main/scripts/remote-install.sh | bash
#
# This bootstrap script:
# 1. Detects OS and architecture
# 2. Downloads the appropriate release
# 3. Runs the full installer
#

set -e

# Configuration
REPO_URL="https://github.com/H4LFdotDEV/Claude-CodePlusPlus"
REPO_RAW="https://raw.githubusercontent.com/H4LFdotDEV/Claude-CodePlusPlus/main"
INSTALL_DIR="$HOME/.claude-code-pp"
TMP_DIR="${TMPDIR:-/tmp}/claude-code-pp-install"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Print banner
print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                  Claude Code++ Installer                   ║"
    echo "║      AI-Native Development with Persistent Memory          ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Detect OS
detect_os() {
    local os=""

    case "$(uname -s)" in
        Darwin*)
            os="darwin"
            ;;
        Linux*)
            os="linux"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            os="windows"
            warn "Windows detected. WSL2 is recommended for best experience."
            ;;
        *)
            error "Unsupported operating system: $(uname -s)"
            ;;
    esac

    echo "$os"
}

# Detect architecture
detect_arch() {
    local arch=""

    case "$(uname -m)" in
        x86_64|amd64)
            arch="x64"
            ;;
        arm64|aarch64)
            arch="arm64"
            ;;
        armv7l)
            arch="arm"
            warn "32-bit ARM detected. Some features may be limited."
            ;;
        *)
            error "Unsupported architecture: $(uname -m)"
            ;;
    esac

    echo "$arch"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check for curl or wget
    if ! command -v curl &> /dev/null && ! command -v wget &> /dev/null; then
        error "Neither curl nor wget found. Please install one of them."
    fi

    # Check for Python 3.10+
    if command -v python3 &> /dev/null; then
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            success "Python $(python3 --version 2>&1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+') found"
        else
            error "Python 3.10+ required. Found: $(python3 --version 2>&1)"
        fi
    else
        error "Python 3 not found. Please install Python 3.10+"
    fi

    # Check for git
    if command -v git &> /dev/null; then
        success "Git found"
    else
        warn "Git not found. Will use release downloads instead of git clone."
    fi
}

# Download file with fallback
download_file() {
    local url="$1"
    local output="$2"

    if command -v curl &> /dev/null; then
        curl -fsSL "$url" -o "$output"
    elif command -v wget &> /dev/null; then
        wget -q "$url" -O "$output"
    else
        error "No download tool available"
    fi
}

# Clone or download repository
get_repository() {
    info "Getting Claude Code++ repository..."

    mkdir -p "$TMP_DIR"

    if command -v git &> /dev/null; then
        # Clone repository
        if [ -d "$TMP_DIR/repo" ]; then
            rm -rf "$TMP_DIR/repo"
        fi
        git clone --depth 1 "$REPO_URL.git" "$TMP_DIR/repo" 2>&1 | grep -v "^remote:" || true
        success "Repository cloned"
    else
        # Download release archive
        info "Downloading release archive..."
        download_file "$REPO_URL/archive/refs/heads/main.zip" "$TMP_DIR/repo.zip"

        # Extract
        if command -v unzip &> /dev/null; then
            unzip -q "$TMP_DIR/repo.zip" -d "$TMP_DIR"
            mv "$TMP_DIR/Claude-CodePlusPlus-main" "$TMP_DIR/repo"
        else
            error "unzip not found. Please install unzip or git."
        fi
        success "Repository downloaded"
    fi
}

# Download CAIIDE++ for platform
download_caiide() {
    local os="$1"
    local arch="$2"

    info "Checking for CAIIDE++ pre-built binary..."

    local caiide_dir="$TMP_DIR/repo/CAIIDE++"
    local caiide_binary=""

    case "$os-$arch" in
        darwin-arm64)
            caiide_binary="CAIIDE++-darwin-arm64.dmg"
            ;;
        darwin-x64)
            caiide_binary="CAIIDE++-darwin-x64.dmg"
            ;;
        linux-x64)
            caiide_binary="CAIIDE++-linux-x64.AppImage"
            ;;
        *)
            warn "No pre-built CAIIDE++ binary for $os-$arch. Will build from source."
            return 1
            ;;
    esac

    # Try to download pre-built binary from releases
    local release_url="$REPO_URL/releases/latest/download/$caiide_binary"

    if download_file "$release_url" "$TMP_DIR/$caiide_binary" 2>/dev/null; then
        success "Downloaded CAIIDE++ binary: $caiide_binary"
        export CAIIDE_BINARY="$TMP_DIR/$caiide_binary"
        return 0
    else
        warn "Pre-built binary not available. Will build from source if possible."
        return 1
    fi
}

# Run main installer
run_installer() {
    local os="$1"
    local arch="$2"

    info "Running Claude Code++ installer..."

    cd "$TMP_DIR/repo"

    # Make installer executable
    chmod +x install.sh

    # Set environment for remote install
    export CAIIDE_REMOTE_INSTALL="true"
    export CAIIDE_OS="$os"
    export CAIIDE_ARCH="$arch"

    # Run installer
    ./install.sh
}

# Install CAIIDE++ application
install_caiide() {
    local os="$1"

    if [ -z "${CAIIDE_BINARY:-}" ]; then
        info "Building CAIIDE++ from source..."

        local caiide_dir="$TMP_DIR/repo/CAIIDE++"

        if [ -f "$caiide_dir/build-caiide.sh" ]; then
            cd "$caiide_dir"
            chmod +x build-caiide.sh

            # Check for Node.js (required for VS Code build)
            if ! command -v node &> /dev/null; then
                warn "Node.js not found. CAIIDE++ build skipped."
                warn "Install Node.js 18+ and run: cd CAIIDE++ && ./build-caiide.sh"
                return 1
            fi

            ./build-caiide.sh || {
                warn "CAIIDE++ build failed. You can build manually later."
                return 1
            }
        else
            warn "CAIIDE++ build script not found"
            return 1
        fi
    else
        # Install pre-built binary
        info "Installing CAIIDE++ from binary..."

        case "$os" in
            darwin)
                # Mount DMG and copy app
                local mount_point
                mount_point=$(hdiutil attach "$CAIIDE_BINARY" -nobrowse -quiet | grep "Volumes" | cut -f3)

                if [ -n "$mount_point" ]; then
                    cp -R "$mount_point"/*.app /Applications/ 2>/dev/null || {
                        cp -R "$mount_point"/*.app "$HOME/Applications/" 2>/dev/null
                    }
                    hdiutil detach "$mount_point" -quiet
                    success "CAIIDE++ installed to Applications"
                fi
                ;;
            linux)
                # Make AppImage executable and move to bin
                chmod +x "$CAIIDE_BINARY"
                mkdir -p "$HOME/.local/bin"
                mv "$CAIIDE_BINARY" "$HOME/.local/bin/caiide"
                success "CAIIDE++ installed to ~/.local/bin/caiide"
                ;;
        esac
    fi
}

# Launch CAIIDE++ with onboarding
launch_caiide() {
    local os="$1"

    echo ""
    read -p "Launch CAIIDE++ with onboarding wizard? [Y/n]: " launch_choice
    launch_choice=${launch_choice:-Y}

    if [[ "$launch_choice" =~ ^[Yy]$ ]]; then
        info "Launching CAIIDE++..."

        export CAIIDE_ONBOARDING="true"

        case "$os" in
            darwin)
                if [ -d "/Applications/CAIIDE++.app" ]; then
                    open -a "CAIIDE++" --env CAIIDE_ONBOARDING=true
                elif [ -d "$HOME/Applications/CAIIDE++.app" ]; then
                    open -a "$HOME/Applications/CAIIDE++.app" --env CAIIDE_ONBOARDING=true
                else
                    warn "CAIIDE++ app not found. Run manually when built."
                fi
                ;;
            linux)
                if [ -x "$HOME/.local/bin/caiide" ]; then
                    "$HOME/.local/bin/caiide" &
                else
                    warn "CAIIDE++ not found. Run manually when built."
                fi
                ;;
        esac
    fi
}

# Cleanup
cleanup() {
    if [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}

# Print next steps
print_next_steps() {
    echo ""
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║              Installation Complete!                        ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Open CAIIDE++ to complete onboarding"
    echo "  2. Or use Claude Code CLI: claude"
    echo "  3. Run 'memory_stats' to verify Memory MCP is working"
    echo ""
    echo "Documentation: https://github.com/H4LFdotDEV/Claude-CodePlusPlus/wiki"
    echo ""
}

# Main installation flow
main() {
    # Trap cleanup on exit
    trap cleanup EXIT

    print_banner

    # Detect platform
    info "Detecting platform..."
    OS=$(detect_os)
    ARCH=$(detect_arch)
    success "Platform: $OS-$ARCH"
    echo ""

    # Check prerequisites
    check_prerequisites
    echo ""

    # Get repository
    get_repository
    echo ""

    # Try to download CAIIDE++ binary
    download_caiide "$OS" "$ARCH" || true
    echo ""

    # Run main installer
    run_installer "$OS" "$ARCH"
    echo ""

    # Install CAIIDE++
    install_caiide "$OS" || true
    echo ""

    # Launch with onboarding
    launch_caiide "$OS"

    print_next_steps
}

# Run
main "$@"
