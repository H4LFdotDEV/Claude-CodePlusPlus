#!/usr/bin/env bash
# Auto-update openclaw submodule from fork
# Runs silently on session start, logs to ~/.claude-code-pp/logs/autoupdate.log

set -euo pipefail

CLAUDE_CODE_PP_DIR="${CLAUDE_CODE_PP_DIR:-$HOME/.claude-code-pp}"
LOG_DIR="$CLAUDE_CODE_PP_DIR/logs"
LOG_FILE="$LOG_DIR/autoupdate.log"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCLAW_DIR="$REPO_DIR/openclaw"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

# Check if we should skip (e.g., no network, recently updated)
LAST_CHECK_FILE="$CLAUDE_CODE_PP_DIR/.last-openclaw-update"
MIN_CHECK_INTERVAL=3600  # 1 hour between checks

if [[ -f "$LAST_CHECK_FILE" ]]; then
    last_check=$(cat "$LAST_CHECK_FILE")
    now=$(date +%s)
    if (( now - last_check < MIN_CHECK_INTERVAL )); then
        exit 0  # Skip, checked recently
    fi
fi

# Record this check
date +%s > "$LAST_CHECK_FILE"

log "Starting auto-update check"

# Check if openclaw directory exists and is a git repo
if [[ ! -d "$OPENCLAW_DIR/.git" ]] && [[ ! -f "$OPENCLAW_DIR/.git" ]]; then
    log "openclaw directory not found or not a git repo"
    exit 0
fi

cd "$OPENCLAW_DIR"

# Fetch latest from origin (fork)
if ! git fetch origin main --quiet 2>/dev/null; then
    log "Failed to fetch from origin (network issue?)"
    exit 0
fi

# Check if we're behind
LOCAL=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
REMOTE=$(git rev-parse origin/main 2>/dev/null || echo "unknown")

if [[ "$LOCAL" == "$REMOTE" ]]; then
    log "Already up to date ($LOCAL)"
    exit 0
fi

BEHIND=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "0")
if [[ "$BEHIND" == "0" ]]; then
    log "Already up to date"
    exit 0
fi

log "Found $BEHIND new commits, updating..."

# Check for local changes
if ! git diff --quiet 2>/dev/null || ! git diff --cached --quiet 2>/dev/null; then
    log "Local changes detected, skipping auto-update"
    exit 0
fi

# Pull changes
if git pull --ff-only origin main --quiet 2>/dev/null; then
    NEW_HEAD=$(git rev-parse --short HEAD)
    log "Updated to $NEW_HEAD ($BEHIND commits)"

    # Update parent repo submodule reference
    cd "$REPO_DIR"
    if git diff --quiet openclaw 2>/dev/null; then
        log "Submodule reference unchanged"
    else
        log "Submodule reference updated locally (commit manually if desired)"
    fi
else
    log "Fast-forward failed, manual intervention required"
fi
