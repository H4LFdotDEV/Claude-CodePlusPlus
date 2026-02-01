#!/bin/bash
set -e

# CAIIDE++ Build Script
# This script clones VS Code, applies branding, strips telemetry, and builds

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VSCODE_DIR="$SCRIPT_DIR/vscode-base"
BUILD_DIR="$SCRIPT_DIR/build"

echo "==================================="
echo "  CAIIDE++ Build Script"
echo "==================================="
echo ""

# Step 1: Clone VS Code if not already cloned
if [ ! -d "$VSCODE_DIR" ]; then
    echo "[1/7] Cloning VS Code repository..."
    git clone --depth 1 https://github.com/microsoft/vscode.git "$VSCODE_DIR"
else
    echo "[1/7] VS Code already cloned, skipping..."
fi

cd "$VSCODE_DIR"

# Step 2: Install dependencies
echo "[2/7] Installing dependencies..."
yarn install

# Step 3: Apply product.json overrides (branding + Open VSX)
echo "[3/7] Applying CAIIDE++ branding..."
cp "$SCRIPT_DIR/product.json" "$VSCODE_DIR/product.json"

# Step 4: Strip telemetry
echo "[4/7] Stripping telemetry..."

# Remove telemetry from package.json
node -e "
const fs = require('fs');
const pkg = JSON.parse(fs.readFileSync('package.json', 'utf8'));

// Remove telemetry-related dependencies
const telemetryDeps = [
    '@vscode/extension-telemetry',
    'applicationinsights',
    '@microsoft/1ds-core-js',
    '@microsoft/1ds-post-js'
];

for (const dep of telemetryDeps) {
    delete pkg.dependencies?.[dep];
    delete pkg.devDependencies?.[dep];
}

fs.writeFileSync('package.json', JSON.stringify(pkg, null, 2));
console.log('  - Removed telemetry dependencies from package.json');
"

# Create telemetry stub
cat > "$VSCODE_DIR/src/vs/platform/telemetry/common/telemetryUtils.ts.patch" << 'EOF'
// Telemetry disabled in CAIIDE++
export const NullTelemetryService = {
    publicLog: () => {},
    publicLog2: () => {},
    publicLogError: () => {},
    publicLogError2: () => {},
    setExperimentProperty: () => {},
    telemetryLevel: 0,
    sendErrorTelemetry: false,
};
EOF

# Patch telemetry service to be disabled by default
find src -name "*.ts" -type f -exec grep -l "enableTelemetry" {} \; | while read file; do
    sed -i.bak 's/enableTelemetry: true/enableTelemetry: false/g' "$file"
    rm -f "$file.bak"
done 2>/dev/null || true

echo "  - Patched telemetry settings"

# Step 5: Copy bundled extensions
echo "[5/7] Bundling CAIIDE++ extensions..."
mkdir -p "$VSCODE_DIR/extensions/caiide-memory"
mkdir -p "$VSCODE_DIR/extensions/caiide-theme"

cp -r "$SCRIPT_DIR/extensions/memory-mcp/"* "$VSCODE_DIR/extensions/caiide-memory/"
cp -r "$SCRIPT_DIR/extensions/caiide-theme/"* "$VSCODE_DIR/extensions/caiide-theme/"

# Build the memory extension
echo "  - Building memory-mcp extension..."
cd "$VSCODE_DIR/extensions/caiide-memory"
if [ -f "package.json" ]; then
    npm install --legacy-peer-deps 2>/dev/null || yarn install 2>/dev/null || true
    npm run compile 2>/dev/null || yarn compile 2>/dev/null || true
fi
cd "$VSCODE_DIR"

echo "  - Extensions bundled"

# Step 6: Update branding assets
echo "[6/7] Updating branding assets..."

# Create a simple placeholder icon (in production, replace with actual icons)
mkdir -p "$VSCODE_DIR/resources/darwin"
mkdir -p "$VSCODE_DIR/resources/linux"
mkdir -p "$VSCODE_DIR/resources/win32"

# Note: You'll need to create actual icon files
# - resources/darwin/code.icns (macOS app icon)
# - resources/linux/code.png (Linux icon)
# - resources/win32/code.ico (Windows icon)
echo "  - Icon directories prepared (add custom icons manually)"

# Update application name in various places
for file in $(find . -name "*.json" -type f -not -path "./node_modules/*" 2>/dev/null | head -100); do
    if grep -q '"Visual Studio Code"' "$file" 2>/dev/null; then
        sed -i.bak 's/"Visual Studio Code"/"CAIIDE++"/g' "$file"
        rm -f "$file.bak"
    fi
done 2>/dev/null || true

echo "  - Updated application names"

# Step 7: Build
echo "[7/7] Building CAIIDE++..."
echo "  This may take 10-20 minutes..."

# Set build environment
export VSCODE_QUALITY=stable

# Build for current platform
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "  Building for macOS..."
    yarn gulp vscode-darwin-arm64-min 2>&1 | tail -20

    BUILD_OUTPUT="$VSCODE_DIR/../VSCode-darwin-arm64"
    if [ -d "$BUILD_OUTPUT" ]; then
        mv "$BUILD_OUTPUT" "$BUILD_DIR/CAIIDE++.app"
        echo ""
        echo "==================================="
        echo "  Build complete!"
        echo "  Output: $BUILD_DIR/CAIIDE++.app"
        echo "==================================="
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    echo "  Building for Linux..."
    yarn gulp vscode-linux-x64-min 2>&1 | tail -20

    BUILD_OUTPUT="$VSCODE_DIR/../VSCode-linux-x64"
    if [ -d "$BUILD_OUTPUT" ]; then
        mv "$BUILD_OUTPUT" "$BUILD_DIR/caiide"
        echo ""
        echo "==================================="
        echo "  Build complete!"
        echo "  Output: $BUILD_DIR/caiide"
        echo "==================================="
    fi
else
    echo "  Building for Windows..."
    yarn gulp vscode-win32-x64-min 2>&1 | tail -20

    BUILD_OUTPUT="$VSCODE_DIR/../VSCode-win32-x64"
    if [ -d "$BUILD_OUTPUT" ]; then
        mv "$BUILD_OUTPUT" "$BUILD_DIR/caiide"
        echo ""
        echo "==================================="
        echo "  Build complete!"
        echo "  Output: $BUILD_DIR/caiide"
        echo "==================================="
    fi
fi

echo ""
echo "Post-build steps:"
echo "1. Replace icons in resources/ with custom CAIIDE++ icons"
echo "2. Test the build: open $BUILD_DIR/CAIIDE++.app (macOS)"
echo "3. Verify telemetry is disabled in settings"
echo "4. Verify Open VSX marketplace is configured"
