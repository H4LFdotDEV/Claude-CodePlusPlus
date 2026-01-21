#!/bin/bash
# Claude Code++ Installation Script
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
SKIP_DOCKER=false
SKIP_SWIFT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-docker)
            SKIP_DOCKER=true
            shift
            ;;
        --skip-swift)
            SKIP_SWIFT=true
            shift
            ;;
        --help|-h)
            echo "Claude Code++ Installation Script"
            echo ""
            echo "Usage: ./install.sh [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run      Show what would be done without making changes"
            echo "  --skip-docker  Skip Docker services installation"
            echo "  --skip-swift   Skip Swift controller build"
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

# Check if command exists
check_command() {
    if command -v "$1" &> /dev/null; then
        return 0
    else
        return 1
    fi
}

# Version comparison
version_gte() {
    [ "$(printf '%s\n' "$1" "$2" | sort -V | head -n1)" = "$2" ]
}

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}           Claude Code++ Installation                   ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$DRY_RUN" = true ]; then
    log_warn "Running in dry-run mode - no changes will be made"
    echo ""
fi

# =============================================================================
# Step 1: Check Prerequisites
# =============================================================================

log_info "Checking prerequisites..."

# Check macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    log_error "This script is designed for macOS only"
    exit 1
fi
log_success "macOS detected"

# Check Python
if check_command python3; then
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    if version_gte "$PYTHON_VERSION" "3.10.0"; then
        log_success "Python $PYTHON_VERSION found"
    else
        log_error "Python 3.10+ required, found $PYTHON_VERSION"
        exit 1
    fi
else
    log_error "Python 3 not found. Please install Python 3.10+"
    exit 1
fi

# Check Swift (optional)
if [ "$SKIP_SWIFT" = false ]; then
    if check_command swift; then
        SWIFT_VERSION=$(swift --version 2>&1 | head -1 | sed 's/.*version //' | awk '{print $1}')
        if version_gte "$SWIFT_VERSION" "5.9"; then
            log_success "Swift $SWIFT_VERSION found"
        else
            log_warn "Swift 5.9+ recommended, found $SWIFT_VERSION"
        fi
    else
        log_warn "Swift not found - system controller will not be built"
        SKIP_SWIFT=true
    fi
fi

# Check Docker (optional)
if [ "$SKIP_DOCKER" = false ]; then
    if check_command docker; then
        if docker info &> /dev/null; then
            log_success "Docker is running"
        else
            log_warn "Docker is installed but not running"
            SKIP_DOCKER=true
        fi
    else
        log_warn "Docker not found - infrastructure services will not be started"
        SKIP_DOCKER=true
    fi
fi

# Check pip
if ! check_command pip3; then
    log_error "pip3 not found. Please install pip"
    exit 1
fi
log_success "pip3 found"

echo ""

# =============================================================================
# Step 2: Create Directory Structure
# =============================================================================

log_info "Creating directory structure..."

directories=(
    "$INSTALL_DIR"
    "$INSTALL_DIR/config"
    "$INSTALL_DIR/memory"
    "$INSTALL_DIR/memory/sqlite"
    "$INSTALL_DIR/memory/faiss"
    "$INSTALL_DIR/logs"
    "$INSTALL_DIR/cache"
    "$INSTALL_DIR/bin"
)

for dir in "${directories[@]}"; do
    if [ ! -d "$dir" ]; then
        run_cmd "mkdir -p '$dir'"
        log_success "Created $dir"
    else
        log_info "Directory exists: $dir"
    fi
done

echo ""

# =============================================================================
# Step 3: Copy Configuration Files
# =============================================================================

log_info "Installing configuration files..."

# Copy settings.yaml if not exists
if [ ! -f "$INSTALL_DIR/config/settings.yaml" ]; then
    if [ -f "$SCRIPT_DIR/config/settings.yaml" ]; then
        run_cmd "cp '$SCRIPT_DIR/config/settings.yaml' '$INSTALL_DIR/config/settings.yaml'"
        log_success "Copied settings.yaml"
    else
        log_warn "settings.yaml not found in source"
    fi
else
    log_info "settings.yaml already exists (not overwriting)"
fi

# Copy litellm.yaml if not exists
if [ ! -f "$INSTALL_DIR/config/litellm.yaml" ]; then
    if [ -f "$SCRIPT_DIR/config/litellm.yaml" ]; then
        run_cmd "cp '$SCRIPT_DIR/config/litellm.yaml' '$INSTALL_DIR/config/litellm.yaml'"
        log_success "Copied litellm.yaml"
    fi
fi

echo ""

# =============================================================================
# Step 4: Build Swift Controller
# =============================================================================

if [ "$SKIP_SWIFT" = false ]; then
    log_info "Building Swift System Controller..."

    if [ -d "$SCRIPT_DIR/swift-system-controller" ]; then
        cd "$SCRIPT_DIR/swift-system-controller"

        run_cmd "swift build -c release"

        if [ "$DRY_RUN" = false ] && [ -f ".build/release/system-controller-cli" ]; then
            run_cmd "cp '.build/release/system-controller-cli' '$INSTALL_DIR/bin/'"
            log_success "Swift controller built and installed"
        elif [ "$DRY_RUN" = true ]; then
            log_success "Swift controller would be built and installed"
        else
            log_warn "Swift build may have failed"
        fi

        cd "$SCRIPT_DIR"
    else
        log_warn "swift-system-controller directory not found"
    fi

    echo ""
fi

# =============================================================================
# Step 5: Install Python Dependencies
# =============================================================================

log_info "Installing Python dependencies..."

if [ -d "$SCRIPT_DIR/python" ]; then
    cd "$SCRIPT_DIR/python"

    # Install with all optional dependencies
    run_cmd "pip3 install -e '.[all]' --quiet"
    log_success "Python memory-mcp installed"

    cd "$SCRIPT_DIR"
else
    log_warn "python directory not found"
fi

echo ""

# =============================================================================
# Step 6: Configure MCP Servers
# =============================================================================

log_info "Configuring MCP servers..."

CLAUDE_CONFIG="$HOME/.claude.json"

# Create base config if it doesn't exist
if [ ! -f "$CLAUDE_CONFIG" ]; then
    if [ "$DRY_RUN" = false ]; then
        cat > "$CLAUDE_CONFIG" << 'EOF'
{
  "mcpServers": {}
}
EOF
        log_success "Created ~/.claude.json"
    else
        log_info "Would create ~/.claude.json"
    fi
fi

# Note: We don't automatically modify the user's claude.json
# Instead, we provide instructions
log_info "Add the following to your ~/.claude.json mcpServers section:"
echo ""
echo -e "${YELLOW}  \"memory\": {"
echo "    \"command\": \"python3\","
echo "    \"args\": [\"-m\", \"memory_mcp.server\"]"
echo "  },"
if [ "$SKIP_SWIFT" = false ]; then
    echo "  \"system-controller\": {"
    echo "    \"command\": \"$INSTALL_DIR/bin/system-controller-cli\","
    echo "    \"args\": [\"--stdio\"]"
    echo "  }"
fi
echo -e "${NC}"

echo ""

# =============================================================================
# Step 7: Start Docker Services
# =============================================================================

if [ "$SKIP_DOCKER" = false ]; then
    log_info "Starting Docker services..."

    if [ -f "$SCRIPT_DIR/docker/docker-compose.yaml" ]; then
        cd "$SCRIPT_DIR/docker"

        run_cmd "docker-compose up -d redis chromadb"

        if [ "$DRY_RUN" = false ]; then
            # Wait for services to be ready
            sleep 2

            # Check Redis
            if docker-compose exec -T redis redis-cli ping &> /dev/null; then
                log_success "Redis is running"
            else
                log_warn "Redis may not be ready yet"
            fi

            # Check ChromaDB
            if curl -s http://localhost:8000/api/v1/heartbeat &> /dev/null; then
                log_success "ChromaDB is running"
            else
                log_warn "ChromaDB may not be ready yet"
            fi
        fi

        cd "$SCRIPT_DIR"
    else
        log_warn "docker-compose.yaml not found"
    fi

    echo ""
fi

# =============================================================================
# Step 8: Verify Installation
# =============================================================================

log_info "Verifying installation..."

# Check Python package
if python3 -c "import memory_mcp" &> /dev/null; then
    log_success "memory_mcp Python package importable"
else
    log_warn "memory_mcp may not be properly installed"
fi

# Check Swift binary
if [ "$SKIP_SWIFT" = false ] && [ -f "$INSTALL_DIR/bin/system-controller-cli" ]; then
    log_success "system-controller-cli installed"
fi

# Check directories
if [ -d "$INSTALL_DIR" ]; then
    log_success "Installation directory created"
fi

echo ""

# =============================================================================
# Summary
# =============================================================================

echo -e "${GREEN}╔════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║${NC}           Installation Complete!                        ${GREEN}║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Installation directory: $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "  1. Add MCP servers to ~/.claude.json (see above)"
echo "  2. Grant accessibility permissions (System Preferences > Privacy)"
echo "  3. Start Claude Code: claude"
echo ""

if [ "$SKIP_SWIFT" = true ]; then
    echo -e "${YELLOW}Note: Swift controller was skipped${NC}"
fi

if [ "$SKIP_DOCKER" = true ]; then
    echo -e "${YELLOW}Note: Docker services were skipped${NC}"
    echo "  Run: docker-compose -f docker/docker-compose.yaml up -d"
fi

echo ""
echo "For troubleshooting, see: $SCRIPT_DIR/CLAUDE.md"
