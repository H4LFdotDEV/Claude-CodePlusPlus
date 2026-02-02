# TODO: Pin to digest for supply chain security
# To get digest: docker pull python:3.11-slim && docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Claude Code++ Memory MCP"
LABEL org.opencontainers.image.description="Tiered memory system with Redis, Neo4j, SQLite, and Obsidian vault"
LABEL org.opencontainers.image.vendor="Halfservers LLC"
LABEL org.opencontainers.image.source="https://github.com/H4LFdotDEV/Claude-CodePlusPlus"

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy Python package files first (for better layer caching)
COPY python/pyproject.toml python/README.md ./

# Create source directory structure
RUN mkdir -p memory_mcp

# Copy the actual source code
COPY python/memory_mcp ./memory_mcp

# Install with all optional dependencies
RUN pip install --no-cache-dir -e ".[all]"

# Create non-root user with configurable UID/GID for bind mount compatibility
# Default matches macOS/Linux standard user (1000:1000)
ARG USER_ID=1000
ARG GROUP_ID=1000

RUN groupadd -g ${GROUP_ID} mcp 2>/dev/null || true && \
    useradd -u ${USER_ID} -g ${GROUP_ID} -m mcp 2>/dev/null || true && \
    mkdir -p /data/sqlite /data/vault /mounts && \
    chown -R ${USER_ID}:${GROUP_ID} /app /data /mounts

# Switch to non-root user
USER mcp

# Environment defaults
ENV MEMORY_MCP_LOG_LEVEL=INFO
ENV SQLITE_PATH=/data/sqlite/memories.db
ENV OBSIDIAN_VAULT_PATH=/data/vault

# Data directories as volumes
VOLUME ["/data/sqlite", "/data/vault", "/mounts"]

# Health check - verify Python module loads
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import memory_mcp; print('ok')" || exit 1

# MCP servers use stdio for communication
ENTRYPOINT ["python", "-m", "memory_mcp"]
