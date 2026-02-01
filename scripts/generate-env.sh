#!/bin/bash
# generate-env.sh - Generate secure secrets for Claude Code++ services
# Uses cryptographic random generation for all secrets

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default paths
CLAUDE_CODE_PP_DIR="${CLAUDE_CODE_PP_DIR:-$HOME/.claude-code-pp}"
ENV_FILE="${ENV_FILE:-$CLAUDE_CODE_PP_DIR/.env}"

# Ensure directory exists
mkdir -p "$CLAUDE_CODE_PP_DIR"

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# Generate a cryptographically secure random hex string
generate_secret() {
    local length="${1:-24}"
    openssl rand -hex "$length"
}

# Generate a LiteLLM-style API key
generate_litellm_key() {
    echo "sk-litellm-$(openssl rand -hex 16)"
}

# Generate a UUID v4
generate_uuid() {
    if command -v uuidgen &> /dev/null; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        # Fallback: generate UUID-like string from random bytes
        local hex
        hex=$(openssl rand -hex 16)
        echo "${hex:0:8}-${hex:8:4}-4${hex:13:3}-${hex:16:4}-${hex:20:12}"
    fi
}

# Check if .env file already exists
check_existing() {
    if [ -f "$ENV_FILE" ]; then
        if [ "${FORCE:-false}" = "true" ]; then
            log_warn "Overwriting existing .env file (--force specified)"
            return 0
        fi

        log_warn "Environment file already exists: $ENV_FILE"
        echo "  Use --force to regenerate all secrets"
        echo "  Use --update to only add missing variables"

        if [ "${UPDATE:-false}" = "true" ]; then
            return 1  # Signal to update mode
        fi

        exit 0
    fi
    return 0
}

# Load existing values if in update mode
load_existing() {
    if [ -f "$ENV_FILE" ]; then
        # shellcheck disable=SC1090
        source "$ENV_FILE"
    fi
}

# Generate all secrets
generate_all_secrets() {
    local mode="${1:-create}"

    log_info "Generating secure secrets for Claude Code++..."
    echo ""

    # Database passwords
    if [ "$mode" = "create" ] || [ -z "${NEO4J_PASSWORD:-}" ]; then
        NEO4J_PASSWORD=$(generate_secret 24)
        log_success "Generated NEO4J_PASSWORD"
    fi

    if [ "$mode" = "create" ] || [ -z "${REDIS_PASSWORD:-}" ]; then
        REDIS_PASSWORD=$(generate_secret 24)
        log_success "Generated REDIS_PASSWORD"
    fi

    if [ "$mode" = "create" ] || [ -z "${POSTGRES_PASSWORD:-}" ]; then
        POSTGRES_PASSWORD=$(generate_secret 24)
        log_success "Generated POSTGRES_PASSWORD"
    fi

    # LiteLLM
    if [ "$mode" = "create" ] || [ -z "${LITELLM_MASTER_KEY:-}" ]; then
        LITELLM_MASTER_KEY=$(generate_litellm_key)
        log_success "Generated LITELLM_MASTER_KEY"
    fi

    if [ "$mode" = "create" ] || [ -z "${LITELLM_SALT_KEY:-}" ]; then
        LITELLM_SALT_KEY=$(generate_secret 32)
        log_success "Generated LITELLM_SALT_KEY"
    fi

    # Session secrets
    if [ "$mode" = "create" ] || [ -z "${SESSION_SECRET:-}" ]; then
        SESSION_SECRET=$(generate_secret 32)
        log_success "Generated SESSION_SECRET"
    fi

    # Encryption keys
    if [ "$mode" = "create" ] || [ -z "${ENCRYPTION_KEY:-}" ]; then
        ENCRYPTION_KEY=$(generate_secret 32)
        log_success "Generated ENCRYPTION_KEY"
    fi

    # Webhook secrets
    if [ "$mode" = "create" ] || [ -z "${WEBHOOK_SECRET:-}" ]; then
        WEBHOOK_SECRET=$(generate_secret 24)
        log_success "Generated WEBHOOK_SECRET"
    fi

    # Installation ID
    if [ "$mode" = "create" ] || [ -z "${INSTALLATION_ID:-}" ]; then
        INSTALLATION_ID=$(generate_uuid)
        log_success "Generated INSTALLATION_ID"
    fi
}

# Write the .env file
write_env_file() {
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    cat > "$ENV_FILE" << EOF
# Claude Code++ Environment Configuration
# Generated: $timestamp
# Installation ID: $INSTALLATION_ID
#
# SECURITY: This file contains sensitive secrets.
# Do NOT commit this file to version control.
# Do NOT share this file publicly.

# =============================================================================
# DATABASE CREDENTIALS
# =============================================================================

# Neo4j (Graphiti knowledge graph)
NEO4J_PASSWORD=$NEO4J_PASSWORD
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j

# Redis (Hot memory tier)
REDIS_PASSWORD=$REDIS_PASSWORD
REDIS_URL=redis://:$REDIS_PASSWORD@localhost:6379

# PostgreSQL (Optional - for advanced deployments)
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_USER=claude_code_pp
POSTGRES_DB=claude_code_pp
DATABASE_URL=postgresql://claude_code_pp:$POSTGRES_PASSWORD@localhost:5432/claude_code_pp

# =============================================================================
# LITELLM MODEL ROUTER
# =============================================================================

LITELLM_MASTER_KEY=$LITELLM_MASTER_KEY
LITELLM_SALT_KEY=$LITELLM_SALT_KEY
LITELLM_BASE_URL=http://localhost:4000

# =============================================================================
# SECURITY KEYS
# =============================================================================

# Session encryption
SESSION_SECRET=$SESSION_SECRET

# Data encryption key (for sensitive stored data)
ENCRYPTION_KEY=$ENCRYPTION_KEY

# Webhook signature verification
WEBHOOK_SECRET=$WEBHOOK_SECRET

# =============================================================================
# API KEYS (User must provide these)
# =============================================================================

# Required: Anthropic API key for Claude models
# Get yours at: https://console.anthropic.com/
ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY:-}

# Optional: OpenAI API key for GPT models
# Get yours at: https://platform.openai.com/api-keys
OPENAI_API_KEY=\${OPENAI_API_KEY:-}

# Optional: Voyage AI for better embeddings
# Get yours at: https://www.voyageai.com/
VOYAGE_API_KEY=\${VOYAGE_API_KEY:-}

# =============================================================================
# PATHS
# =============================================================================

# Memory storage
SQLITE_PATH=$CLAUDE_CODE_PP_DIR/memory/sqlite/memories.db
LANCEDB_PATH=$CLAUDE_CODE_PP_DIR/memory/lancedb

# Obsidian vault for human-readable notes
OBSIDIAN_VAULT_PATH=$CLAUDE_CODE_PP_DIR/memory/vault

# Logs
LOG_DIR=$CLAUDE_CODE_PP_DIR/logs

# =============================================================================
# INSTALLATION METADATA
# =============================================================================

INSTALLATION_ID=$INSTALLATION_ID
CLAUDE_CODE_PP_VERSION=2026.1.31
GENERATED_AT=$timestamp

EOF

    # Set secure permissions
    chmod 600 "$ENV_FILE"

    log_success "Environment file written to: $ENV_FILE"
}

# Create a docker-compose override for local secrets
create_docker_override() {
    local override_file="$CLAUDE_CODE_PP_DIR/docker-compose.override.yaml"

    cat > "$override_file" << EOF
# Docker Compose Override - Local Secrets
# Generated by generate-env.sh
# This file sources secrets from .env

version: '3.8'

services:
  redis:
    environment:
      - REDIS_PASSWORD=\${REDIS_PASSWORD}
    command: redis-server --requirepass \${REDIS_PASSWORD}

  neo4j:
    environment:
      - NEO4J_AUTH=neo4j/\${NEO4J_PASSWORD}

  litellm:
    environment:
      - LITELLM_MASTER_KEY=\${LITELLM_MASTER_KEY}
      - LITELLM_SALT_KEY=\${LITELLM_SALT_KEY}
      - ANTHROPIC_API_KEY=\${ANTHROPIC_API_KEY}
      - OPENAI_API_KEY=\${OPENAI_API_KEY}
EOF

    chmod 600 "$override_file"
    log_success "Docker override written to: $override_file"
}

# Print summary
print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo -e "${GREEN}Secrets generated successfully!${NC}"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Environment file: $ENV_FILE"
    echo ""
    echo "Next steps:"
    echo "  1. Add your API keys to $ENV_FILE:"
    echo "     - ANTHROPIC_API_KEY (required)"
    echo "     - OPENAI_API_KEY (optional)"
    echo ""
    echo "  2. Source the environment before starting services:"
    echo "     source $ENV_FILE"
    echo ""
    echo "  3. Start Docker services:"
    echo "     docker-compose -f docker/docker-compose.yaml up -d"
    echo ""
    echo -e "${YELLOW}Security reminder:${NC}"
    echo "  • Never commit .env files to version control"
    echo "  • Never share these secrets publicly"
    echo "  • Rotate secrets if compromised"
    echo ""
}

# Export secrets for shell usage
export_for_shell() {
    echo ""
    echo "# Add these to your shell profile (~/.zshrc or ~/.bashrc):"
    echo "export CLAUDE_CODE_PP_ENV=\"$ENV_FILE\""
    echo "[ -f \"\$CLAUDE_CODE_PP_ENV\" ] && source \"\$CLAUDE_CODE_PP_ENV\""
}

# Main
main() {
    local mode="create"

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            --force|-f)
                FORCE=true
                shift
                ;;
            --update|-u)
                UPDATE=true
                shift
                ;;
            --output|-o)
                ENV_FILE="$2"
                shift 2
                ;;
            --export)
                export_for_shell
                exit 0
                ;;
            --help|-h)
                echo "Usage: generate-env.sh [OPTIONS]"
                echo ""
                echo "Generate secure secrets for Claude Code++ services."
                echo ""
                echo "Options:"
                echo "  -f, --force      Regenerate all secrets (overwrites existing)"
                echo "  -u, --update     Only add missing variables to existing file"
                echo "  -o, --output     Specify output file path"
                echo "  --export         Print shell export commands"
                echo "  -h, --help       Show this help message"
                echo ""
                echo "Environment variables:"
                echo "  CLAUDE_CODE_PP_DIR   Base directory (default: ~/.claude-code-pp)"
                echo "  ENV_FILE             Output file (default: \$CLAUDE_CODE_PP_DIR/.env)"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done

    # Check for existing file
    if ! check_existing; then
        mode="update"
        load_existing
    fi

    # Generate secrets
    generate_all_secrets "$mode"

    # Write files
    write_env_file
    create_docker_override

    # Print summary
    print_summary
}

main "$@"
