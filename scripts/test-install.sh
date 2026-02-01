#!/bin/bash
# test-install.sh - Integration tests for Claude Code++ installation
# Run with: ./scripts/test-install.sh

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Test directory
TEST_DIR="${TEST_DIR:-$(mktemp -d)}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(dirname "$SCRIPT_DIR")"

# Counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

log_skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

run_test() {
    local name="$1"
    local func="$2"

    TESTS_RUN=$((TESTS_RUN + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log_info "Running: $name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if $func; then
        log_pass "$name"
        return 0
    else
        log_fail "$name"
        return 1
    fi
}

# =============================================================================
# TEST: Resource Detection
# =============================================================================

test_resource_detection_exists() {
    if [ ! -f "$SCRIPT_DIR/detect-resources.sh" ]; then
        echo "detect-resources.sh not found"
        return 1
    fi
    return 0
}

test_resource_detection_executable() {
    if [ ! -x "$SCRIPT_DIR/detect-resources.sh" ]; then
        echo "detect-resources.sh is not executable"
        return 1
    fi
    return 0
}

test_resource_detection_json_output() {
    local output
    output=$("$SCRIPT_DIR/detect-resources.sh" --json 2>/dev/null) || {
        echo "Failed to run detect-resources.sh --json"
        return 1
    }

    # Check JSON structure
    if ! echo "$output" | jq -e '.profile' > /dev/null 2>&1; then
        echo "Missing 'profile' in JSON output"
        return 1
    fi

    if ! echo "$output" | jq -e '.ram.total_gb' > /dev/null 2>&1; then
        echo "Missing 'ram.total_gb' in JSON output"
        return 1
    fi

    if ! echo "$output" | jq -e '.cpu.cores' > /dev/null 2>&1; then
        echo "Missing 'cpu.cores' in JSON output"
        return 1
    fi

    return 0
}

test_resource_detection_env_output() {
    local output
    output=$("$SCRIPT_DIR/detect-resources.sh" --env 2>/dev/null) || {
        echo "Failed to run detect-resources.sh --env"
        return 1
    }

    # Check for expected environment variables
    if ! echo "$output" | grep -q "CAIIDE_PROFILE="; then
        echo "Missing CAIIDE_PROFILE in env output"
        return 1
    fi

    if ! echo "$output" | grep -q "CAIIDE_RAM_GB="; then
        echo "Missing CAIIDE_RAM_GB in env output"
        return 1
    fi

    return 0
}

test_resource_detection_profile_valid() {
    local profile
    profile=$("$SCRIPT_DIR/detect-resources.sh" --profile 2>/dev/null) || {
        echo "Failed to run detect-resources.sh --profile"
        return 1
    }

    # Check profile is one of the valid values
    case "$profile" in
        minimal|standard|full|enterprise)
            return 0
            ;;
        *)
            echo "Invalid profile: $profile"
            return 1
            ;;
    esac
}

# =============================================================================
# TEST: Secret Generation
# =============================================================================

test_secret_generation_exists() {
    if [ ! -f "$SCRIPT_DIR/generate-env.sh" ]; then
        echo "generate-env.sh not found"
        return 1
    fi
    return 0
}

test_secret_generation_executable() {
    if [ ! -x "$SCRIPT_DIR/generate-env.sh" ]; then
        echo "generate-env.sh is not executable"
        return 1
    fi
    return 0
}

test_secret_generation_creates_env() {
    local test_env_dir="$TEST_DIR/secret-test"
    mkdir -p "$test_env_dir"

    CLAUDE_CODE_PP_DIR="$test_env_dir" "$SCRIPT_DIR/generate-env.sh" > /dev/null 2>&1 || {
        echo "generate-env.sh failed to run"
        return 1
    }

    if [ ! -f "$test_env_dir/.env" ]; then
        echo ".env file was not created"
        return 1
    fi

    return 0
}

test_secret_generation_passwords_set() {
    local test_env_dir="$TEST_DIR/secret-test-passwords"
    mkdir -p "$test_env_dir"

    CLAUDE_CODE_PP_DIR="$test_env_dir" "$SCRIPT_DIR/generate-env.sh" > /dev/null 2>&1

    # Source the env file
    source "$test_env_dir/.env"

    # Check required passwords
    if [ -z "${NEO4J_PASSWORD:-}" ]; then
        echo "NEO4J_PASSWORD not set"
        return 1
    fi

    if [ ${#NEO4J_PASSWORD} -lt 24 ]; then
        echo "NEO4J_PASSWORD too short (${#NEO4J_PASSWORD} chars)"
        return 1
    fi

    if [ -z "${REDIS_PASSWORD:-}" ]; then
        echo "REDIS_PASSWORD not set"
        return 1
    fi

    if [ ${#REDIS_PASSWORD} -lt 24 ]; then
        echo "REDIS_PASSWORD too short"
        return 1
    fi

    if [ -z "${LITELLM_MASTER_KEY:-}" ]; then
        echo "LITELLM_MASTER_KEY not set"
        return 1
    fi

    if [[ ! "$LITELLM_MASTER_KEY" =~ ^sk-litellm- ]]; then
        echo "LITELLM_MASTER_KEY has wrong prefix"
        return 1
    fi

    return 0
}

test_secret_generation_secure_permissions() {
    local test_env_dir="$TEST_DIR/secret-test-perms"
    mkdir -p "$test_env_dir"

    CLAUDE_CODE_PP_DIR="$test_env_dir" "$SCRIPT_DIR/generate-env.sh" > /dev/null 2>&1

    local perms
    perms=$(stat -f "%Lp" "$test_env_dir/.env" 2>/dev/null || stat -c "%a" "$test_env_dir/.env" 2>/dev/null)

    if [ "$perms" != "600" ]; then
        echo "Permissions are $perms, expected 600"
        return 1
    fi

    return 0
}

test_secret_generation_no_overwrite() {
    local test_env_dir="$TEST_DIR/secret-test-nooverwrite"
    mkdir -p "$test_env_dir"

    # First run
    CLAUDE_CODE_PP_DIR="$test_env_dir" "$SCRIPT_DIR/generate-env.sh" > /dev/null 2>&1
    source "$test_env_dir/.env"
    local first_password="$NEO4J_PASSWORD"

    # Second run (should not overwrite without --force)
    CLAUDE_CODE_PP_DIR="$test_env_dir" "$SCRIPT_DIR/generate-env.sh" > /dev/null 2>&1
    source "$test_env_dir/.env"
    local second_password="$NEO4J_PASSWORD"

    if [ "$first_password" != "$second_password" ]; then
        echo "Password was overwritten without --force"
        return 1
    fi

    return 0
}

# =============================================================================
# TEST: Docker Compose Validation
# =============================================================================

test_docker_compose_valid() {
    if [ ! -f "$REPO_DIR/docker/docker-compose.yaml" ]; then
        echo "docker-compose.yaml not found"
        return 1
    fi

    # Validate YAML syntax
    if command -v docker-compose &> /dev/null; then
        # Set required env vars for validation
        export NEO4J_PASSWORD="test"
        export REDIS_PASSWORD="test"
        export LITELLM_MASTER_KEY="sk-litellm-test"
        export ANTHROPIC_API_KEY=""
        export OPENAI_API_KEY=""

        if ! docker-compose -f "$REPO_DIR/docker/docker-compose.yaml" config > /dev/null 2>&1; then
            echo "docker-compose.yaml validation failed"
            return 1
        fi
    else
        log_skip "docker-compose not installed, skipping validation"
    fi

    return 0
}

test_docker_compose_container_names() {
    if [ ! -f "$REPO_DIR/docker/docker-compose.yaml" ]; then
        return 1
    fi

    # Check for expected container name prefix
    if ! grep -q "claude-code-pp-redis" "$REPO_DIR/docker/docker-compose.yaml"; then
        echo "Missing claude-code-pp-redis container name"
        return 1
    fi

    return 0
}

# =============================================================================
# TEST: Python Package
# =============================================================================

test_python_package_exists() {
    if [ ! -f "$REPO_DIR/python/pyproject.toml" ]; then
        echo "pyproject.toml not found"
        return 1
    fi
    return 0
}

test_python_package_has_extras() {
    if ! grep -q '\[project.optional-dependencies\]' "$REPO_DIR/python/pyproject.toml"; then
        echo "No optional dependencies defined"
        return 1
    fi

    # Check for expected extras
    if ! grep -q 'redis' "$REPO_DIR/python/pyproject.toml"; then
        echo "Missing redis extra"
        return 1
    fi

    return 0
}

# =============================================================================
# TEST: Install Script
# =============================================================================

test_install_script_exists() {
    if [ ! -f "$REPO_DIR/install.sh" ]; then
        echo "install.sh not found"
        return 1
    fi
    return 0
}

test_install_script_executable() {
    if [ ! -x "$REPO_DIR/install.sh" ]; then
        echo "install.sh is not executable"
        return 1
    fi
    return 0
}

test_install_script_has_secret_generation() {
    if ! grep -q "generate_secrets" "$REPO_DIR/install.sh"; then
        echo "install.sh missing generate_secrets function"
        return 1
    fi
    return 0
}

test_install_script_uses_correct_container_names() {
    if grep -q 'docker exec redis redis-cli' "$REPO_DIR/install.sh"; then
        echo "install.sh still uses incorrect container name 'redis'"
        return 1
    fi

    if ! grep -q 'CONTAINER_PREFIX' "$REPO_DIR/install.sh"; then
        echo "install.sh missing CONTAINER_PREFIX variable"
        return 1
    fi

    return 0
}

# =============================================================================
# TEST: Extension Files
# =============================================================================

test_onboarding_extension_exists() {
    local ext_dir="$REPO_DIR/CAIIDE++/extensions/caiide-onboarding"

    if [ ! -f "$ext_dir/package.json" ]; then
        echo "caiide-onboarding package.json not found"
        return 1
    fi

    if [ ! -f "$ext_dir/src/extension.ts" ]; then
        echo "extension.ts not found"
        return 1
    fi

    if [ ! -f "$ext_dir/src/onboardingPanel.ts" ]; then
        echo "onboardingPanel.ts not found"
        return 1
    fi

    return 0
}

test_onboarding_has_api_key_export() {
    local panel_file="$REPO_DIR/CAIIDE++/extensions/caiide-onboarding/src/onboardingPanel.ts"

    if [ ! -f "$panel_file" ]; then
        return 1
    fi

    # Check for shell profile export function
    if ! grep -q "_appendToShellProfile" "$panel_file"; then
        echo "Missing _appendToShellProfile function"
        return 1
    fi

    # Check for .env update function
    if ! grep -q "_updateEnvFile" "$panel_file"; then
        echo "Missing _updateEnvFile function"
        return 1
    fi

    return 0
}

test_onboarding_has_questionnaire() {
    local panel_file="$REPO_DIR/CAIIDE++/extensions/caiide-onboarding/src/onboardingPanel.ts"

    if [ ! -f "$panel_file" ]; then
        return 1
    fi

    # Check for user profile handling
    if ! grep -q "saveUserProfile" "$panel_file"; then
        echo "Missing saveUserProfile handler"
        return 1
    fi

    # Check for questionnaire fields
    if ! grep -q "role" "$panel_file" || ! grep -q "languages" "$panel_file"; then
        echo "Missing questionnaire fields"
        return 1
    fi

    return 0
}

# =============================================================================
# Main
# =============================================================================

print_summary() {
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "                        TEST SUMMARY"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Tests run:    $TESTS_RUN"
    echo -e "Tests passed: ${GREEN}$TESTS_PASSED${NC}"
    echo -e "Tests failed: ${RED}$TESTS_FAILED${NC}"
    echo ""

    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed.${NC}"
        return 1
    fi
}

cleanup() {
    if [ -d "$TEST_DIR" ] && [[ "$TEST_DIR" == /tmp/* ]]; then
        rm -rf "$TEST_DIR"
    fi
}

main() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║           Claude Code++ Installation Test Suite                    ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Test directory: $TEST_DIR"
    echo "Repository: $REPO_DIR"

    trap cleanup EXIT

    # Resource Detection Tests
    run_test "Resource detection script exists" test_resource_detection_exists
    run_test "Resource detection script is executable" test_resource_detection_executable

    if command -v jq &> /dev/null; then
        run_test "Resource detection JSON output valid" test_resource_detection_json_output
    else
        log_skip "Resource detection JSON output (jq not installed)"
    fi

    run_test "Resource detection ENV output valid" test_resource_detection_env_output
    run_test "Resource detection profile is valid" test_resource_detection_profile_valid

    # Secret Generation Tests
    run_test "Secret generation script exists" test_secret_generation_exists
    run_test "Secret generation script is executable" test_secret_generation_executable
    run_test "Secret generation creates .env file" test_secret_generation_creates_env
    run_test "Secret generation sets required passwords" test_secret_generation_passwords_set
    run_test "Secret generation sets secure permissions" test_secret_generation_secure_permissions
    run_test "Secret generation does not overwrite without --force" test_secret_generation_no_overwrite

    # Docker Compose Tests
    run_test "Docker compose file is valid" test_docker_compose_valid
    run_test "Docker compose uses correct container names" test_docker_compose_container_names

    # Python Package Tests
    run_test "Python package exists" test_python_package_exists
    run_test "Python package has extras" test_python_package_has_extras

    # Install Script Tests
    run_test "Install script exists" test_install_script_exists
    run_test "Install script is executable" test_install_script_executable
    run_test "Install script has secret generation" test_install_script_has_secret_generation
    run_test "Install script uses correct container names" test_install_script_uses_correct_container_names

    # Extension Tests
    run_test "Onboarding extension exists" test_onboarding_extension_exists
    run_test "Onboarding has API key export" test_onboarding_has_api_key_export
    run_test "Onboarding has questionnaire" test_onboarding_has_questionnaire

    print_summary
}

main "$@"
