#!/bin/bash
#
# Start MCP Inspector with Memory MCP Server
#
# Usage:
#   ./scripts/start-inspector.sh
#   ./scripts/start-inspector.sh --port 8080
#   MEMORY_MCP_LOG_LEVEL=DEBUG ./scripts/start-inspector.sh
#

set -e

# Default port
PORT="${MCP_INSPECTOR_PORT:-6274}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --port)
            PORT="$2"
            shift 2
            ;;
        --debug)
            export MEMORY_MCP_LOG_LEVEL=DEBUG
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --port PORT   Set the inspector port (default: 6274)"
            echo "  --debug       Enable debug logging"
            echo "  --help        Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  MEMORY_MCP_LOG_LEVEL   Log level (DEBUG, INFO, WARNING, ERROR)"
            echo "  MEMORY_MCP_LOG_FILE    Log file path"
            echo "  REDIS_URL              Redis connection URL"
            echo "  OBSIDIAN_VAULT_PATH    Obsidian vault directory"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Check for Node.js
if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required but not installed."
    echo "Install from: https://nodejs.org/"
    exit 1
fi

# Check for npx
if ! command -v npx &> /dev/null; then
    echo "Error: npx is required but not installed."
    echo "It should come with Node.js. Try reinstalling Node.js."
    exit 1
fi

# Check for Python
if ! command -v python &> /dev/null && ! command -v python3 &> /dev/null; then
    echo "Error: Python is required but not installed."
    exit 1
fi

# Determine Python command
PYTHON_CMD="python"
if ! command -v python &> /dev/null; then
    PYTHON_CMD="python3"
fi

# Verify memory_mcp is installed
if ! $PYTHON_CMD -c "import memory_mcp" &> /dev/null; then
    echo "Error: memory_mcp module not found."
    echo "Install with: pip install -e python/"
    exit 1
fi

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║           MCP Inspector - Memory MCP Server                  ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Starting MCP Inspector on port $PORT..."
echo "Open http://localhost:$PORT in your browser"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Start the inspector
npx @modelcontextprotocol/inspector --port "$PORT" $PYTHON_CMD -m memory_mcp.server
