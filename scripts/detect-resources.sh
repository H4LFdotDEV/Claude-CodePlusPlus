#!/bin/bash
#
# Resource Detection for Claude Code++ Installation
# Detects system resources and recommends installation profile
#
# Usage:
#   ./detect-resources.sh              # Human-readable output
#   ./detect-resources.sh --json       # JSON output
#   ./detect-resources.sh --profile    # Just print recommended profile
#   eval $(./detect-resources.sh --env) # Export as environment variables
#

set -e

# Output format
OUTPUT_FORMAT="${1:-human}"

# Detect RAM (in GB)
detect_ram() {
    local ram_gb=0

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        local ram_bytes
        ram_bytes=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
        ram_gb=$((ram_bytes / 1073741824))
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        local ram_kb
        ram_kb=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
        ram_gb=$((ram_kb / 1048576))
    fi

    echo "$ram_gb"
}

# Detect CPU cores
detect_cpu_cores() {
    local cores=1

    if [[ "$OSTYPE" == "darwin"* ]]; then
        cores=$(sysctl -n hw.ncpu 2>/dev/null || echo 1)
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        cores=$(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo 2>/dev/null || echo 1)
    fi

    echo "$cores"
}

# Detect CPU model/architecture
detect_cpu_model() {
    local model="unknown"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        model=$(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo "Apple Silicon")
        # Check for Apple Silicon
        if [[ "$(uname -m)" == "arm64" ]]; then
            model="Apple Silicon ($(sysctl -n machdep.cpu.brand_string 2>/dev/null || echo 'M-series'))"
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        model=$(grep "model name" /proc/cpuinfo 2>/dev/null | head -1 | cut -d: -f2 | xargs || echo "unknown")
    fi

    echo "$model"
}

# Detect GPU
detect_gpu() {
    local gpu_type="none"
    local gpu_name="none"

    # Check for NVIDIA GPU
    if command -v nvidia-smi &> /dev/null; then
        gpu_type="nvidia"
        gpu_name=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1 || echo "NVIDIA GPU")
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        # Check for Apple Silicon GPU (Metal)
        if [[ "$(uname -m)" == "arm64" ]]; then
            gpu_type="apple_metal"
            gpu_name="Apple Silicon GPU (Metal)"
        else
            # Intel Mac - check for discrete GPU
            local gpu_info
            gpu_info=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Chipset Model" | head -1 | cut -d: -f2 | xargs || echo "")
            if [[ -n "$gpu_info" ]]; then
                gpu_type="integrated"
                gpu_name="$gpu_info"
            fi
        fi
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Check for AMD GPU
        if lspci 2>/dev/null | grep -i "vga.*amd\|radeon" &> /dev/null; then
            gpu_type="amd"
            gpu_name=$(lspci 2>/dev/null | grep -i "vga.*amd\|radeon" | head -1 | cut -d: -f3 | xargs || echo "AMD GPU")
        fi
    fi

    echo "$gpu_type|$gpu_name"
}

# Detect available disk space (in GB)
detect_disk_space() {
    local disk_gb=0
    local home_dir="${HOME:-/home/$(whoami)}"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS - use df
        disk_gb=$(df -g "$home_dir" 2>/dev/null | tail -1 | awk '{print $4}' || echo 0)
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux - use df in 1G blocks
        disk_gb=$(df -BG "$home_dir" 2>/dev/null | tail -1 | awk '{print $4}' | tr -d 'G' || echo 0)
    fi

    echo "$disk_gb"
}

# Detect Docker availability
detect_docker() {
    local docker_available="false"
    local docker_version=""
    local docker_running="false"

    if command -v docker &> /dev/null; then
        docker_available="true"
        docker_version=$(docker --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || echo "unknown")

        # Check if Docker daemon is running
        if docker info &> /dev/null; then
            docker_running="true"
        fi
    fi

    echo "$docker_available|$docker_version|$docker_running"
}

# Detect OS and architecture
detect_os() {
    local os_type="unknown"
    local os_arch="unknown"
    local os_version=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        os_type="macos"
        os_arch=$(uname -m)
        os_version=$(sw_vers -productVersion 2>/dev/null || echo "unknown")
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        os_type="linux"
        os_arch=$(uname -m)
        if [ -f /etc/os-release ]; then
            os_version=$(. /etc/os-release && echo "$NAME $VERSION_ID")
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        os_type="windows"
        os_arch=$(uname -m)
        os_version="WSL2"
    fi

    echo "$os_type|$os_arch|$os_version"
}

# Determine recommended profile based on resources
determine_profile() {
    local ram_gb=$1
    local cpu_cores=$2
    local gpu_type=$3
    local disk_gb=$4
    local docker_running=$5

    local profile="minimal"

    # Enterprise: >32GB RAM, GPU available, >50GB disk
    if [[ $ram_gb -ge 32 ]] && [[ "$gpu_type" != "none" ]] && [[ $disk_gb -ge 50 ]]; then
        profile="enterprise"
    # Full: 16-32GB RAM, >20GB disk, Docker running
    elif [[ $ram_gb -ge 16 ]] && [[ $disk_gb -ge 20 ]] && [[ "$docker_running" == "true" ]]; then
        profile="full"
    # Standard: 8-16GB RAM, >10GB disk
    elif [[ $ram_gb -ge 8 ]] && [[ $disk_gb -ge 10 ]]; then
        profile="standard"
    # Minimal: <8GB RAM or <5GB disk
    else
        profile="minimal"
    fi

    echo "$profile"
}

# Get profile description
get_profile_description() {
    local profile=$1

    case "$profile" in
        minimal)
            echo "SQLite + Vault (lightweight, no Docker required)"
            ;;
        standard)
            echo "SQLite + Vault + Redis (recommended for most users)"
            ;;
        full)
            echo "Redis + Neo4j/Graphiti + SQLite + Vault (full memory tiers)"
            ;;
        enterprise)
            echo "Full + LiteLLM + livegrep (maximum features)"
            ;;
        *)
            echo "Unknown profile"
            ;;
    esac
}

# Get profile services
get_profile_services() {
    local profile=$1

    case "$profile" in
        minimal)
            echo "sqlite,vault"
            ;;
        standard)
            echo "redis,sqlite,vault"
            ;;
        full)
            echo "redis,neo4j,sqlite,vault"
            ;;
        enterprise)
            echo "redis,neo4j,sqlite,vault,litellm,livegrep"
            ;;
        *)
            echo "sqlite,vault"
            ;;
    esac
}

# Main detection
main() {
    # Collect all resource information
    local ram_gb
    ram_gb=$(detect_ram)

    local cpu_cores
    cpu_cores=$(detect_cpu_cores)

    local cpu_model
    cpu_model=$(detect_cpu_model)

    local gpu_info
    gpu_info=$(detect_gpu)
    local gpu_type="${gpu_info%%|*}"
    local gpu_name="${gpu_info#*|}"

    local disk_gb
    disk_gb=$(detect_disk_space)

    local docker_info
    docker_info=$(detect_docker)
    local docker_available="${docker_info%%|*}"
    local docker_rest="${docker_info#*|}"
    local docker_version="${docker_rest%%|*}"
    local docker_running="${docker_rest#*|}"

    local os_info
    os_info=$(detect_os)
    local os_type="${os_info%%|*}"
    local os_rest="${os_info#*|}"
    local os_arch="${os_rest%%|*}"
    local os_version="${os_rest#*|}"

    # Determine profile
    local profile
    profile=$(determine_profile "$ram_gb" "$cpu_cores" "$gpu_type" "$disk_gb" "$docker_running")

    local profile_desc
    profile_desc=$(get_profile_description "$profile")

    local profile_services
    profile_services=$(get_profile_services "$profile")

    # Output based on format
    case "$OUTPUT_FORMAT" in
        --json)
            cat << EOF
{
  "os": {
    "type": "$os_type",
    "arch": "$os_arch",
    "version": "$os_version"
  },
  "ram": {
    "total_gb": $ram_gb
  },
  "cpu": {
    "cores": $cpu_cores,
    "model": "$cpu_model"
  },
  "gpu": {
    "type": "$gpu_type",
    "name": "$gpu_name"
  },
  "disk": {
    "available_gb": $disk_gb
  },
  "docker": {
    "available": $docker_available,
    "version": "$docker_version",
    "running": $docker_running
  },
  "profile": {
    "recommended": "$profile",
    "description": "$profile_desc",
    "services": "$profile_services"
  }
}
EOF
            ;;

        --profile)
            echo "$profile"
            ;;

        --env)
            cat << EOF
export CAIIDE_OS_TYPE="$os_type"
export CAIIDE_OS_ARCH="$os_arch"
export CAIIDE_OS_VERSION="$os_version"
export CAIIDE_RAM_GB="$ram_gb"
export CAIIDE_CPU_CORES="$cpu_cores"
export CAIIDE_CPU_MODEL="$cpu_model"
export CAIIDE_GPU_TYPE="$gpu_type"
export CAIIDE_GPU_NAME="$gpu_name"
export CAIIDE_DISK_GB="$disk_gb"
export CAIIDE_DOCKER_AVAILABLE="$docker_available"
export CAIIDE_DOCKER_VERSION="$docker_version"
export CAIIDE_DOCKER_RUNNING="$docker_running"
export CAIIDE_PROFILE="$profile"
export CAIIDE_PROFILE_SERVICES="$profile_services"
EOF
            ;;

        *)
            # Human-readable output
            echo ""
            echo "╔═══════════════════════════════════════════════════════════╗"
            echo "║              System Resource Detection                     ║"
            echo "╚═══════════════════════════════════════════════════════════╝"
            echo ""
            echo "Operating System:"
            echo "  Type:     $os_type"
            echo "  Arch:     $os_arch"
            echo "  Version:  $os_version"
            echo ""
            echo "Hardware:"
            echo "  RAM:      ${ram_gb} GB"
            echo "  CPU:      ${cpu_cores} cores ($cpu_model)"
            if [[ "$gpu_type" != "none" ]]; then
                echo "  GPU:      $gpu_name"
            else
                echo "  GPU:      Not detected"
            fi
            echo "  Disk:     ${disk_gb} GB available"
            echo ""
            echo "Docker:"
            if [[ "$docker_available" == "true" ]]; then
                echo "  Version:  $docker_version"
                if [[ "$docker_running" == "true" ]]; then
                    echo "  Status:   Running"
                else
                    echo "  Status:   Not running (start Docker to enable full features)"
                fi
            else
                echo "  Status:   Not installed"
            fi
            echo ""
            echo "═══════════════════════════════════════════════════════════════"
            echo ""
            echo "Recommended Profile: $profile"
            echo "  $profile_desc"
            echo ""
            echo "Services: $profile_services"
            echo ""
            ;;
    esac
}

main "$@"
