# Changelog

All notable changes to Claude Code++ will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- CAIIDE++ VS Code fork absorbed into monorepo
- Onboarding wizard with 6-step setup flow
- Secret generation script (`scripts/generate-env.sh`)
- Resource detection script (`scripts/detect-resources.sh`)
- Remote installation script for curl-based setup
- CI/CD pipeline with GitHub Actions
- CONTRIBUTING.md with development guidelines
- Integration test suite (22 tests)

### Changed
- Updated pyproject.toml: removed FAISS, added Graphiti dependencies
- Fixed container name prefix (`claude-code-pp-*`)
- Enhanced install.sh with secret generation and profile support

### Fixed
- License mismatch (pyproject.toml now correctly shows Apache-2.0)
- Docker compose environment variable handling
- Redis connection verification with password auth

## [1.0.0] - 2025-01-31

### Added
- Initial release of Claude Code++
- Tiered memory system (Redis → Graphiti → SQLite → Vault)
- Memory MCP server with 23 tools
- System Controller for macOS accessibility
- Research environment (VoiceMode + webcam)
- OpenClaw messaging integrations
- Docker infrastructure (Redis, Neo4j, LiteLLM)

### Memory Tiers
- **Hot**: Redis cache for active session data
- **Warm**: Graphiti/Neo4j knowledge graph for entities and relationships
- **Cold**: SQLite with FTS5 for full-text search
- **Archive**: Obsidian-compatible vault for human-readable notes

### MCP Tools
- Core: memory_store, memory_search, memory_recall, memory_delete, memory_list
- Sessions: session_save, session_restore
- Vault: vault_write, vault_read
- Stats: memory_stats
- Research: research_session_*, research_transcript_store, research_capture_store
- Knowledge graph: search_entities, search_facts
- Code search: code_search, search_function, search_class
- Proactive: proactive_status, extract_insights, configure_proactive

[Unreleased]: https://github.com/H4LFdotDEV/Claude-CodePlusPlus/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/H4LFdotDEV/Claude-CodePlusPlus/releases/tag/v1.0.0
