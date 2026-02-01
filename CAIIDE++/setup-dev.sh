#!/bin/bash
set -e

# CAIIDE++ Development Setup
# Quickly sets up a development environment without building the final app

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VSCODE_DIR="$SCRIPT_DIR/vscode-base"

echo "CAIIDE++ Development Setup"
echo "=========================="
echo ""

# Check prerequisites
echo "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    echo "Error: Node.js is required. Install from https://nodejs.org/"
    exit 1
fi

if ! command -v yarn &> /dev/null; then
    echo "Installing yarn..."
    npm install -g yarn
fi

if ! command -v git &> /dev/null; then
    echo "Error: Git is required"
    exit 1
fi

echo "Prerequisites OK"
echo ""

# Clone VS Code
if [ ! -d "$VSCODE_DIR" ]; then
    echo "Cloning VS Code (this may take a few minutes)..."
    git clone --depth 1 https://github.com/microsoft/vscode.git "$VSCODE_DIR"
else
    echo "VS Code already cloned"
fi

cd "$VSCODE_DIR"

# Apply branding
echo "Applying CAIIDE++ branding..."
cp "$SCRIPT_DIR/product.json" "$VSCODE_DIR/product.json"

# Copy extensions
echo "Setting up extensions..."
mkdir -p "$VSCODE_DIR/extensions/caiide-memory"
mkdir -p "$VSCODE_DIR/extensions/caiide-theme"
cp -r "$SCRIPT_DIR/extensions/memory-mcp/"* "$VSCODE_DIR/extensions/caiide-memory/" 2>/dev/null || true
cp -r "$SCRIPT_DIR/extensions/caiide-theme/"* "$VSCODE_DIR/extensions/caiide-theme/" 2>/dev/null || true

# Install dependencies
echo "Installing dependencies (this takes a while)..."
yarn install

echo ""
echo "=========================="
echo "Setup complete!"
echo ""
echo "To run CAIIDE++ in development mode:"
echo "  cd $VSCODE_DIR"
echo "  yarn watch  # In one terminal"
echo "  ./scripts/code.sh  # In another terminal"
echo ""
echo "To build a release:"
echo "  ./build-caiide.sh"
echo ""
