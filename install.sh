#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.claude-code-pp"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$REPO_DIR/scripts"
ENV_FILE="$INSTALL_DIR/.env"

# Remote install environment (set by remote-install.sh)
IS_REMOTE_INSTALL="${CAIIDE_REMOTE_INSTALL:-false}"
DETECTED_OS="${CAIIDE_OS:-}"
DETECTED_ARCH="${CAIIDE_ARCH:-}"

# Profile and resource variables (populated by detect_resources)
PROFILE=""
RAM_GB=""
CPU_CORES=""
DISK_GB=""
GPU_TYPE=""
DOCKER_AVAILABLE=""
DOCKER_RUNNING=""

# Docker container name prefix (matches docker-compose.yaml)
CONTAINER_PREFIX="claude-code-pp"

print_banner() {
    echo -e "${CYAN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║                   Claude Code++ Installer                  ║"
    echo "║      AI-Native Development with Persistent Memory          ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[OK]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Generate or load secrets
generate_secrets() {
    info "Setting up environment secrets..."

    # Create install directory if it doesn't exist
    mkdir -p "$INSTALL_DIR"

    # Check if secrets script exists
    if [ -f "$SCRIPT_DIR/generate-env.sh" ]; then
        if [ -f "$ENV_FILE" ]; then
            info "Environment file exists, loading..."
            # shellcheck disable=SC1090
            source "$ENV_FILE"
            success "Loaded existing secrets from $ENV_FILE"
        else
            info "Generating new secrets..."
            chmod +x "$SCRIPT_DIR/generate-env.sh"
            CLAUDE_CODE_PP_DIR="$INSTALL_DIR" "$SCRIPT_DIR/generate-env.sh"
            # shellcheck disable=SC1090
            source "$ENV_FILE"
            success "Generated and loaded new secrets"
        fi
    else
        # Inline secret generation if script not found
        warn "generate-env.sh not found, generating inline..."

        NEO4J_PASSWORD=$(openssl rand -hex 24)
        REDIS_PASSWORD=$(openssl rand -hex 24)

        cat > "$ENV_FILE" << EOF
# Claude Code++ Environment - Auto-generated
NEO4J_PASSWORD=$NEO4J_PASSWORD
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379
SQLITE_PATH=$INSTALL_DIR/memory/sqlite/memories.db
OBSIDIAN_VAULT_PATH=$INSTALL_DIR/memory/vault
EOF
        chmod 600 "$ENV_FILE"
        # shellcheck disable=SC1090
        source "$ENV_FILE"
        success "Generated inline secrets"
    fi

    # Export for Docker and child processes
    export NEO4J_PASSWORD REDIS_PASSWORD
    export REDIS_URL SQLITE_PATH OBSIDIAN_VAULT_PATH
}

# Detect system resources and set installation profile
detect_resources() {
    info "Detecting system resources..."

    if [ -f "$SCRIPT_DIR/detect-resources.sh" ]; then
        # Source environment variables from detect-resources.sh
        eval "$("$SCRIPT_DIR/detect-resources.sh" --env)"

        PROFILE="$CAIIDE_PROFILE"
        RAM_GB="$CAIIDE_RAM_GB"
        CPU_CORES="$CAIIDE_CPU_CORES"
        DISK_GB="$CAIIDE_DISK_GB"
        GPU_TYPE="$CAIIDE_GPU_TYPE"
        DOCKER_AVAILABLE="$CAIIDE_DOCKER_AVAILABLE"
        DOCKER_RUNNING="$CAIIDE_DOCKER_RUNNING"

        echo ""
        echo "  RAM:     ${RAM_GB} GB"
        echo "  CPU:     ${CPU_CORES} cores"
        echo "  Disk:    ${DISK_GB} GB available"
        echo "  Docker:  $([ "$DOCKER_RUNNING" == "true" ] && echo "Running" || echo "Not running")"
        echo ""
        success "Recommended profile: $PROFILE"
    else
        warn "Resource detection script not found, using defaults"
        PROFILE="standard"
        DOCKER_AVAILABLE="false"
        DOCKER_RUNNING="false"
    fi

    # Allow override via environment or user input (non-remote install)
    if [ "$IS_REMOTE_INSTALL" != "true" ]; then
        echo ""
        echo "Installation profiles:"
        echo "  minimal   - SQLite + Vault (lightweight, no Docker)"
        echo "  standard  - + Redis (recommended for most)"
        echo "  full      - + Neo4j/Graphiti (knowledge graph)"
        echo "  enterprise - + livegrep + LiteLLM (maximum features)"
        echo ""
        read -p "Use recommended profile '$PROFILE'? [Y/n]: " use_recommended
        use_recommended=${use_recommended:-Y}

        if [[ ! "$use_recommended" =~ ^[Yy]$ ]]; then
            read -p "Enter profile (minimal/standard/full/enterprise): " PROFILE
            PROFILE=${PROFILE:-standard}
        fi
    fi

    export CAIIDE_PROFILE="$PROFILE"
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Python
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
        if python3 -c 'import sys; exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
            success "Python $PYTHON_VERSION found"
        else
            error "Python 3.10+ required (found $PYTHON_VERSION)"
        fi
    else
        error "Python 3 not found. Please install Python 3.10+"
    fi

    # Node.js (for npx)
    if command -v node &> /dev/null; then
        NODE_VERSION=$(node -v)
        success "Node.js $NODE_VERSION found"
    else
        warn "Node.js not found. Some MCP servers (prompts) won't work"
    fi

    # pip
    if command -v pip3 &> /dev/null || command -v pip &> /dev/null; then
        success "pip found"
    else
        error "pip not found. Please install pip"
    fi

    # Claude Code
    if command -v claude &> /dev/null; then
        success "Claude Code CLI found"
    else
        warn "Claude Code CLI not found. Install from: https://docs.anthropic.com/claude-code"
    fi

    # Docker (for full/enterprise profiles)
    if [ "$PROFILE" == "full" ] || [ "$PROFILE" == "enterprise" ]; then
        if [ "$DOCKER_RUNNING" != "true" ]; then
            warn "Docker not running - $PROFILE profile requires Docker for Neo4j/Graphiti"
            warn "Some features will be unavailable. Start Docker for full functionality."
        fi
    fi
}

# Create directory structure
create_directories() {
    info "Creating directory structure..."

    mkdir -p "$INSTALL_DIR"/{bin,config,logs,cache}
    mkdir -p "$INSTALL_DIR"/memory/{sqlite,vault/{code,notes,conversations,references,daily}}

    success "Created $INSTALL_DIR"
}

# Install Python package based on profile
install_python_package() {
    info "Installing Python package for profile: $PROFILE"

    cd "$REPO_DIR/python"

    # Create virtual environment
    VENV_DIR="$INSTALL_DIR/venv"
    if [ ! -d "$VENV_DIR" ]; then
        info "Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi

    # Activate venv and install
    source "$VENV_DIR/bin/activate"
    PIP="$VENV_DIR/bin/pip"

    # Upgrade pip
    "$PIP" install --upgrade pip -q

    # Install based on profile
    case $PROFILE in
        minimal)
            info "Installing core package only..."
            "$PIP" install -e .
            ;;
        standard)
            info "Installing with Redis support..."
            "$PIP" install -e ".[redis]"
            ;;
        full)
            info "Installing with all memory tiers..."
            "$PIP" install -e ".[all]"
            ;;
        enterprise)
            info "Installing enterprise package..."
            "$PIP" install -e ".[all]"
            ;;
        *)
            info "Installing recommended package..."
            "$PIP" install -e ".[all]"
            ;;
    esac

    deactivate 2>/dev/null || true
    success "Python package installed in virtual environment"
}

# Create wrapper script for MCP server
create_wrapper_script() {
    info "Creating MCP server wrapper..."

    mkdir -p "$INSTALL_DIR/bin"

    VENV_PYTHON="$INSTALL_DIR/venv/bin/python"

    cat > "$INSTALL_DIR/bin/memory-mcp" << EOF
#!/bin/bash
# Memory MCP Server wrapper
# Auto-generated by install.sh

# Source environment secrets if available
ENV_FILE="$INSTALL_DIR/.env"
if [ -f "\$ENV_FILE" ]; then
    set -a
    source "\$ENV_FILE"
    set +a
fi

# Core paths
export MEMORY_MCP_LOG_FILE="$INSTALL_DIR/logs/memory.log"
export SQLITE_PATH="\${SQLITE_PATH:-$INSTALL_DIR/memory/sqlite/memories.db}"
export OBSIDIAN_VAULT_PATH="\${OBSIDIAN_VAULT_PATH:-$INSTALL_DIR/memory/vault}"

# Redis connection (from .env or defaults)
export REDIS_URL="\${REDIS_URL:-redis://localhost:6379}"

exec "$VENV_PYTHON" -m memory_mcp "\$@"
EOF

    chmod +x "$INSTALL_DIR/bin/memory-mcp"
    success "Created $INSTALL_DIR/bin/memory-mcp"
}

# Start Docker services based on profile
start_docker_services() {
    if [ "$PROFILE" == "minimal" ]; then
        info "Minimal profile - skipping Docker services"
        return 0
    fi

    if [ "$DOCKER_RUNNING" != "true" ]; then
        warn "Docker not running - skipping service startup"
        return 0
    fi

    info "Starting Docker services for profile: $PROFILE"

    DOCKER_DIR="$REPO_DIR/docker"
    if [ ! -f "$DOCKER_DIR/docker-compose.yaml" ]; then
        warn "docker-compose.yaml not found - skipping services"
        return 0
    fi

    cd "$DOCKER_DIR"

    # Pass environment variables to docker-compose
    export NEO4J_PASSWORD REDIS_PASSWORD
    export ANTHROPIC_API_KEY="${ANTHROPIC_API_KEY:-}"
    export OPENAI_API_KEY="${OPENAI_API_KEY:-}"

    case $PROFILE in
        standard)
            # Just Redis
            if docker-compose ps "${CONTAINER_PREFIX}-redis" 2>/dev/null | grep -q "Up"; then
                success "Redis already running"
            else
                info "Starting Redis..."
                docker-compose up -d redis 2>/dev/null || warn "Redis startup failed"
            fi
            ;;
        full)
            # Redis + Neo4j
            info "Starting Redis + Neo4j..."
            docker-compose up -d redis neo4j 2>/dev/null || warn "Some services failed to start"
            ;;
        enterprise)
            # All services including livegrep
            info "Starting all enterprise services..."
            docker-compose --profile livegrep --profile browser --profile local-llm up -d 2>/dev/null || \
                docker-compose --profile livegrep up -d 2>/dev/null || \
                docker-compose up -d 2>/dev/null || warn "Some services failed to start"
            ;;
    esac

    # Wait for services to be ready
    sleep 3

    # Verify Redis if applicable
    if [ "$PROFILE" != "minimal" ]; then
        verify_redis_connection
    fi
}

# Verify Redis is accessible
verify_redis_connection() {
    local container_name="${CONTAINER_PREFIX}-redis"
    local max_attempts=5
    local attempt=1

    while [ $attempt -le $max_attempts ]; do
        # Try local redis-cli first (for standalone Redis)
        if command -v redis-cli &> /dev/null; then
            if redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
                success "Redis is running (standalone)"
                return 0
            fi
        fi

        # Try Docker container
        if docker exec "$container_name" redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
            success "Redis container is running"
            return 0
        fi

        # Fallback: try without password (for development)
        if docker exec "$container_name" redis-cli ping 2>/dev/null | grep -q "PONG"; then
            success "Redis container is running (no auth)"
            return 0
        fi

        info "Waiting for Redis... (attempt $attempt/$max_attempts)"
        sleep 2
        attempt=$((attempt + 1))
    done

    warn "Redis not responding after $max_attempts attempts"
}

# Configure Claude Code
configure_claude() {
    info "Configuring Claude Code..."

    CLAUDE_CONFIG="$HOME/.claude.json"
    MCP_COMMAND="$INSTALL_DIR/bin/memory-mcp"

    # Backup existing config
    if [ -f "$CLAUDE_CONFIG" ]; then
        cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup.$(date +%Y%m%d%H%M%S)"
        info "Backed up existing config"
    fi

    # Check if config exists and has mcpServers
    if [ -f "$CLAUDE_CONFIG" ]; then
        if command -v jq &> /dev/null; then
            # Use jq to merge configs with proper variable passing
            TEMP_CONFIG=$(mktemp)
            jq --arg cmd "$MCP_COMMAND" '
                .mcpServers.memory = {
                    "command": $cmd,
                    "args": []
                } |
                .mcpServers.prompts = {
                    "command": "npx",
                    "args": ["-y", "prompts.chat", "mcp"]
                }
            ' "$CLAUDE_CONFIG" > "$TEMP_CONFIG"
            mv "$TEMP_CONFIG" "$CLAUDE_CONFIG"
            success "Updated $CLAUDE_CONFIG with MCP servers"
        else
            warn "jq not found - please manually add MCP config to ~/.claude.json"
            echo ""
            echo "Add this to your ~/.claude.json mcpServers:"
            echo '  "memory": {'
            echo "    \"command\": \"$MCP_COMMAND\","
            echo '    "args": []'
            echo '  },'
            echo '  "prompts": {'
            echo '    "command": "npx",'
            echo '    "args": ["-y", "prompts.chat", "mcp"]'
            echo '  }'
        fi
    else
        # Create new config
        cat > "$CLAUDE_CONFIG" << EOF
{
  "mcpServers": {
    "memory": {
      "command": "$MCP_COMMAND",
      "args": []
    },
    "prompts": {
      "command": "npx",
      "args": ["-y", "prompts.chat", "mcp"]
    }
  }
}
EOF
        success "Created $CLAUDE_CONFIG"
    fi
}

# Copy rules and hooks
copy_claude_extensions() {
    info "Installing Claude Code extensions..."

    CLAUDE_DIR="$HOME/.claude"
    mkdir -p "$CLAUDE_DIR"/{rules,agents,commands,skills}

    # Copy rules if they exist
    if [ -d "$REPO_DIR/.claude/rules" ]; then
        cp -r "$REPO_DIR/.claude/rules/"* "$CLAUDE_DIR/rules/" 2>/dev/null || true
        success "Copied rules to $CLAUDE_DIR/rules/"
    fi

    # Copy agents if they exist
    if [ -d "$REPO_DIR/.claude/agents" ]; then
        cp -r "$REPO_DIR/.claude/agents/"* "$CLAUDE_DIR/agents/" 2>/dev/null || true
        success "Copied agents to $CLAUDE_DIR/agents/"
    fi

    # Copy commands if they exist
    if [ -d "$REPO_DIR/.claude/commands" ]; then
        cp -r "$REPO_DIR/.claude/commands/"* "$CLAUDE_DIR/commands/" 2>/dev/null || true
        success "Copied commands to $CLAUDE_DIR/commands/"
    fi

    # Copy skills if they exist
    if [ -d "$REPO_DIR/.claude/skills" ]; then
        cp -r "$REPO_DIR/.claude/skills/"* "$CLAUDE_DIR/skills/" 2>/dev/null || true
        success "Copied skills to $CLAUDE_DIR/skills/"
    fi
}

# Install CAIIDE++ IDE
install_caiide() {
    info "Installing CAIIDE++ IDE..."

    CAIIDE_DIR="$REPO_DIR/CAIIDE++"

    # Check for pre-built binary (from remote install)
    if [ -n "${CAIIDE_BINARY:-}" ] && [ -f "$CAIIDE_BINARY" ]; then
        info "Installing from pre-built binary..."
        install_caiide_binary "$CAIIDE_BINARY"
        return 0
    fi

    # Check if CAIIDE++ directory exists
    if [ ! -d "$CAIIDE_DIR" ]; then
        warn "CAIIDE++ directory not found - skipping IDE installation"
        return 1
    fi

    # Check for existing build
    if [ -d "$CAIIDE_DIR/VSCode-darwin-arm64" ] || [ -d "$CAIIDE_DIR/VSCode-darwin-x64" ] || [ -d "$CAIIDE_DIR/VSCode-linux-x64" ]; then
        info "Using existing CAIIDE++ build..."
        install_caiide_from_build
        return 0
    fi

    # Try to build from source
    if [ -f "$CAIIDE_DIR/build-caiide.sh" ]; then
        # Check for Node.js (required for build)
        if ! command -v node &> /dev/null; then
            warn "Node.js not found - cannot build CAIIDE++"
            warn "Install Node.js 18+ and run: cd CAIIDE++ && ./build-caiide.sh"
            return 1
        fi

        if ! command -v yarn &> /dev/null; then
            warn "Yarn not found - cannot build CAIIDE++"
            warn "Install Yarn and run: cd CAIIDE++ && ./build-caiide.sh"
            return 1
        fi

        echo ""
        read -p "Build CAIIDE++ from source? This may take 10-20 minutes. [y/N]: " build_caiide
        build_caiide=${build_caiide:-N}

        if [[ "$build_caiide" =~ ^[Yy]$ ]]; then
            info "Building CAIIDE++..."
            cd "$CAIIDE_DIR"
            chmod +x build-caiide.sh
            ./build-caiide.sh || {
                warn "CAIIDE++ build failed. You can build manually later."
                return 1
            }
            install_caiide_from_build
        else
            info "Skipping CAIIDE++ build. Run later: cd CAIIDE++ && ./build-caiide.sh"
            return 1
        fi
    else
        warn "CAIIDE++ build script not found"
        return 1
    fi
}

# Install CAIIDE++ from pre-built binary
install_caiide_binary() {
    local binary_path="$1"
    local os_type="${CAIIDE_OS:-$(uname -s | tr '[:upper:]' '[:lower:]')}"

    case "$os_type" in
        darwin)
            # Mount DMG and copy app
            local mount_point
            mount_point=$(hdiutil attach "$binary_path" -nobrowse -quiet 2>/dev/null | grep "Volumes" | cut -f3)

            if [ -n "$mount_point" ]; then
                # Try /Applications first, then ~/Applications
                if cp -R "$mount_point"/*.app /Applications/ 2>/dev/null; then
                    success "CAIIDE++ installed to /Applications"
                elif cp -R "$mount_point"/*.app "$HOME/Applications/" 2>/dev/null; then
                    mkdir -p "$HOME/Applications"
                    cp -R "$mount_point"/*.app "$HOME/Applications/"
                    success "CAIIDE++ installed to ~/Applications"
                fi
                hdiutil detach "$mount_point" -quiet 2>/dev/null || true
            else
                warn "Could not mount DMG"
                return 1
            fi
            ;;
        linux)
            # Make AppImage executable and move to bin
            chmod +x "$binary_path"
            mkdir -p "$HOME/.local/bin"
            cp "$binary_path" "$HOME/.local/bin/caiide"
            success "CAIIDE++ installed to ~/.local/bin/caiide"
            ;;
        *)
            warn "Unsupported OS for binary installation: $os_type"
            return 1
            ;;
    esac
}

# Install CAIIDE++ from local build
install_caiide_from_build() {
    local os_type="${CAIIDE_OS:-$(uname -s | tr '[:upper:]' '[:lower:]')}"
    local arch="${CAIIDE_ARCH:-$(uname -m)}"

    CAIIDE_DIR="$REPO_DIR/CAIIDE++"

    # Map architecture
    case "$arch" in
        arm64|aarch64) arch="arm64" ;;
        x86_64|amd64) arch="x64" ;;
    esac

    case "$os_type" in
        darwin)
            local build_dir="$CAIIDE_DIR/VSCode-darwin-$arch"
            if [ -d "$build_dir" ]; then
                local app_name=$(ls "$build_dir" | grep "\.app$" | head -1)
                if [ -n "$app_name" ]; then
                    # Copy to Applications
                    if cp -R "$build_dir/$app_name" /Applications/ 2>/dev/null; then
                        success "CAIIDE++ installed to /Applications/$app_name"
                    else
                        mkdir -p "$HOME/Applications"
                        cp -R "$build_dir/$app_name" "$HOME/Applications/"
                        success "CAIIDE++ installed to ~/Applications/$app_name"
                    fi
                fi
            else
                warn "Build not found for darwin-$arch"
                return 1
            fi
            ;;
        linux)
            local build_dir="$CAIIDE_DIR/VSCode-linux-$arch"
            if [ -d "$build_dir" ]; then
                mkdir -p "$HOME/.local/bin"
                # Create symlink to the binary
                local bin_path=$(find "$build_dir" -name "code" -type f -executable | head -1)
                if [ -n "$bin_path" ]; then
                    ln -sf "$bin_path" "$HOME/.local/bin/caiide"
                    success "CAIIDE++ linked to ~/.local/bin/caiide"
                fi
            else
                warn "Build not found for linux-$arch"
                return 1
            fi
            ;;
    esac
}

# Launch CAIIDE++ with onboarding
launch_caiide() {
    local os_type="${CAIIDE_OS:-$(uname -s | tr '[:upper:]' '[:lower:]')}"

    # Set onboarding environment variable
    export CAIIDE_ONBOARDING="true"
    export CAIIDE_PROFILE="$PROFILE"

    echo ""
    read -p "Launch CAIIDE++ with onboarding wizard? [Y/n]: " launch_choice
    launch_choice=${launch_choice:-Y}

    if [[ ! "$launch_choice" =~ ^[Yy]$ ]]; then
        info "Skipping CAIIDE++ launch. Open it manually when ready."
        return 0
    fi

    info "Launching CAIIDE++..."

    case "$os_type" in
        darwin)
            # Find the app
            local app_path=""
            for app_name in "CAIIDE++.app" "CAIIDE.app" "Code - OSS.app" "Visual Studio Code.app"; do
                if [ -d "/Applications/$app_name" ]; then
                    app_path="/Applications/$app_name"
                    break
                elif [ -d "$HOME/Applications/$app_name" ]; then
                    app_path="$HOME/Applications/$app_name"
                    break
                fi
            done

            if [ -n "$app_path" ]; then
                # Launch with environment variables
                open -a "$app_path" --env CAIIDE_ONBOARDING=true --env CAIIDE_PROFILE="$PROFILE" 2>/dev/null || \
                    open "$app_path" 2>/dev/null || \
                    warn "Could not launch CAIIDE++"
            else
                warn "CAIIDE++ app not found. Install it first."
            fi
            ;;
        linux)
            if [ -x "$HOME/.local/bin/caiide" ]; then
                CAIIDE_ONBOARDING=true CAIIDE_PROFILE="$PROFILE" "$HOME/.local/bin/caiide" &
                disown
            else
                warn "CAIIDE++ not found at ~/.local/bin/caiide"
            fi
            ;;
    esac
}

# Setup Redis (standalone, non-Docker)
setup_redis_standalone() {
    # Only offer standalone Redis if Docker is not being used
    if [ "$PROFILE" == "minimal" ] && [ "$DOCKER_RUNNING" != "true" ]; then
        echo ""
        read -p "Would you like to install Redis for hot caching? [y/N]: " setup_redis

        if [[ "$setup_redis" =~ ^[Yy]$ ]]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                if command -v brew &> /dev/null; then
                    if ! brew list redis &> /dev/null; then
                        info "Installing Redis via Homebrew..."
                        brew install redis
                    fi
                    info "Starting Redis..."
                    brew services start redis
                    success "Redis started"
                else
                    warn "Homebrew not found. Please install Redis manually"
                fi
            elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
                # Linux
                if command -v apt-get &> /dev/null; then
                    info "Installing Redis..."
                    sudo apt-get update && sudo apt-get install -y redis-server
                    sudo systemctl start redis-server
                    sudo systemctl enable redis-server
                    success "Redis installed and started"
                else
                    warn "Please install Redis manually"
                fi
            fi
        fi
    fi
}

# Optional: Setup Research Environment (VoiceMode + Webcam)
setup_research_env() {
    echo ""
    read -p "Would you like to install the Research Environment (voice + whiteboard)? [y/N]: " setup_research

    if [[ "$setup_research" =~ ^[Yy]$ ]]; then
        info "Setting up Research Environment..."

        # Create research directories
        RESEARCH_DIR="$HOME/Research/PocketDimension"
        mkdir -p "$RESEARCH_DIR"/{sessions,diagrams,simulations,documentation,exports}
        success "Created research directory at $RESEARCH_DIR"

        # Install VoiceMode
        if command -v uv &> /dev/null; then
            info "Installing VoiceMode via uv..."
            uv tool install voice-mode --force 2>/dev/null || warn "VoiceMode install failed"
            uvx voice-mode-install 2>/dev/null || warn "VoiceMode dependencies may need manual setup"
        elif command -v pip3 &> /dev/null; then
            info "Installing VoiceMode via pip..."
            pip3 install voice-mode 2>/dev/null || warn "VoiceMode install failed"
        else
            warn "Could not install VoiceMode - install uv or pip first"
        fi

        # Add VoiceMode MCP (if claude CLI available)
        if command -v claude &> /dev/null; then
            info "Adding VoiceMode to Claude MCP..."
            claude mcp add --scope user voicemode -- uvx --refresh voice-mode 2>/dev/null || \
                warn "VoiceMode MCP registration may need manual setup"

            info "Adding webcam MCP to Claude..."
            claude mcp add-json "webcam" '{"command":"npx","args":["-y","@llmindset/mcp-webcam"]}' 2>/dev/null || \
                warn "Webcam MCP registration may need manual setup"
        fi

        # Create research environment config
        cat > "$HOME/.research-env" << 'EOF'
# Room-Scale Claude Research Environment Configuration
# Source this file: source ~/.research-env

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
    open http://localhost:3333 2>/dev/null || xdg-open http://localhost:3333 2>/dev/null

    # Start voice conversation
    claude converse

    # Cleanup when done
    kill $WEBCAM_PID 2>/dev/null
}

echo "Research environment loaded. Type 'start_research' to begin."
EOF

        # Add to shell profile
        SHELL_RC=""
        if [ -f "$HOME/.zshrc" ]; then
            SHELL_RC="$HOME/.zshrc"
        elif [ -f "$HOME/.bashrc" ]; then
            SHELL_RC="$HOME/.bashrc"
        fi

        if [ -n "$SHELL_RC" ]; then
            if ! grep -q "source ~/.research-env" "$SHELL_RC"; then
                echo "" >> "$SHELL_RC"
                echo "# Room-Scale Claude Research Environment" >> "$SHELL_RC"
                echo "[ -f ~/.research-env ] && source ~/.research-env" >> "$SHELL_RC"
                success "Added research-env to $SHELL_RC"
            fi
        fi

        success "Research environment configured"
        echo ""
        echo "Research directory: $RESEARCH_DIR"
        echo "Start a session: source ~/.research-env && start_research"
    fi
}

# Verify installation
verify_installation() {
    info "Verifying installation..."
    echo ""

    # Check wrapper script
    if [ -x "$INSTALL_DIR/bin/memory-mcp" ]; then
        success "MCP wrapper script created"
    else
        warn "MCP wrapper script missing"
    fi

    # Check Python module (using venv)
    VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
    if [ -x "$VENV_PYTHON" ] && "$VENV_PYTHON" -c "import memory_mcp" 2>/dev/null; then
        success "memory_mcp module importable"
    else
        warn "memory_mcp module not found - check Python installation"
    fi

    # Check Redis
    if [ "$PROFILE" != "minimal" ]; then
        local redis_ok=false
        if command -v redis-cli &> /dev/null && redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
            success "Redis is running (standalone)"
            redis_ok=true
        elif docker exec "${CONTAINER_PREFIX}-redis" redis-cli -a "$REDIS_PASSWORD" ping 2>/dev/null | grep -q "PONG"; then
            success "Redis container is running"
            redis_ok=true
        fi

        if [ "$redis_ok" != "true" ]; then
            warn "Redis not available (optional for $PROFILE profile)"
        fi
    fi

    # Check directories
    if [ -d "$INSTALL_DIR/memory/sqlite" ]; then
        success "Directory structure created"
    else
        warn "Directory structure incomplete"
    fi

    # Check Claude config
    if [ -f "$HOME/.claude.json" ] && grep -q "memory-mcp" "$HOME/.claude.json" 2>/dev/null; then
        success "Claude Code configured"
    else
        warn "Claude Code configuration may need manual setup"
    fi

    # Test MCP server
    info "Testing MCP server..."
    if echo '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"0.1.0","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}' | "$INSTALL_DIR/bin/memory-mcp" 2>/dev/null | grep -q "protocolVersion"; then
        success "MCP server responds correctly"
    else
        warn "MCP server test failed - check logs at $INSTALL_DIR/logs/memory.log"
    fi
}

# Print summary
print_summary() {
    echo ""
    echo -e "${GREEN}"
    echo "╔═══════════════════════════════════════════════════════════╗"
    echo "║              Installation Complete!                        ║"
    echo "╚═══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo "Installation directory: $INSTALL_DIR"
    echo "Profile: $PROFILE"
    echo ""
    echo "Active services:"
    case $PROFILE in
        minimal)
            echo "  - SQLite (cold storage)"
            echo "  - Vault (archive)"
            ;;
        standard)
            echo "  - Redis (hot cache)"
            echo "  - SQLite (cold storage)"
            echo "  - Vault (archive)"
            ;;
        full)
            echo "  - Redis (hot cache)"
            echo "  - Neo4j/Graphiti (warm knowledge graph)"
            echo "  - SQLite (cold storage)"
            echo "  - Vault (archive)"
            ;;
        enterprise)
            echo "  - Redis (hot cache)"
            echo "  - Neo4j/Graphiti (warm knowledge graph)"
            echo "  - SQLite (cold storage)"
            echo "  - Vault (archive)"
            echo "  - livegrep (code search)"
            echo "  - LiteLLM (model routing)"
            ;;
    esac
    echo ""
    echo "Next steps:"
    echo "  1. Open CAIIDE++ to complete onboarding"
    echo "  2. Or restart Claude Code CLI and run 'memory_stats'"
    echo ""
    echo "Documentation: https://github.com/H4LFdotDEV/Claude-CodePlusPlus/wiki"
    echo ""
}

# Main installation flow
main() {
    print_banner

    # Detect resources and set profile
    detect_resources
    echo ""

    check_prerequisites
    echo ""

    create_directories
    echo ""

    # Generate secrets BEFORE starting services
    generate_secrets
    echo ""

    install_python_package
    echo ""

    create_wrapper_script
    echo ""

    # Start Docker services based on profile
    start_docker_services
    echo ""

    configure_claude
    echo ""

    copy_claude_extensions
    echo ""

    # Standalone Redis option (for minimal profile without Docker)
    setup_redis_standalone
    echo ""

    # Install CAIIDE++ IDE
    install_caiide
    echo ""

    # Research environment (optional)
    setup_research_env
    echo ""

    verify_installation

    print_summary

    # Launch CAIIDE++ with onboarding
    launch_caiide
}

# Run installer
main "$@"
