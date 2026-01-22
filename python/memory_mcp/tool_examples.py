# tool_examples.py
# Input Examples for Memory MCP Tools
#
# These examples follow Anthropic's recommendation for improving tool use accuracy
# through concrete input_examples in tool schemas. Examples should demonstrate
# representative use cases and proper parameter formatting.

from typing import Dict, Any, List


def get_tool_examples() -> Dict[str, List[Dict[str, Any]]]:
    """
    Get input examples for all MCP tools.

    Returns:
        Dictionary mapping tool names to lists of example inputs.
        Each example includes 'description' and 'input' fields.

    These examples are used to:
    1. Demonstrate proper tool usage to the model
    2. Show representative parameter combinations
    3. Illustrate when and how to use each tool
    """
    return {
        "memory_store": [
            {
                "description": "Store a user preference",
                "input": {
                    "content": "User prefers functional programming patterns. Avoid classes, prefer pure functions, use Option/Either for error handling.",
                    "type": "note",
                    "source": "conversation:2024-01-15",
                    "tags": ["preference", "coding-style", "functional"],
                    "project": "user-profile"
                }
            },
            {
                "description": "Store a resolved error with solution",
                "input": {
                    "content": "TypeError: Cannot read property 'map' of undefined in UserList.tsx:45. Root cause: async data not loaded before render. Solution: Added loading state check and early return.",
                    "type": "code",
                    "source": "src/components/UserList.tsx",
                    "tags": ["error", "react", "async", "resolved"],
                    "project": "dashboard-app"
                }
            },
            {
                "description": "Store an architectural decision",
                "input": {
                    "content": "Decided to use JWT for authentication instead of sessions. Reasons: stateless scaling, microservices compatibility, mobile client support. Trade-off: need refresh token rotation strategy.",
                    "type": "reference",
                    "source": "architecture-decision:auth-strategy",
                    "tags": ["architecture", "auth", "jwt", "decision"],
                    "project": "api-gateway"
                }
            },
            {
                "description": "Store a code snippet for future reference",
                "input": {
                    "content": "```typescript\nconst retryWithBackoff = async <T>(fn: () => Promise<T>, maxRetries = 3): Promise<T> => {\n  for (let i = 0; i < maxRetries; i++) {\n    try { return await fn(); }\n    catch (e) { if (i === maxRetries - 1) throw e; await sleep(Math.pow(2, i) * 100); }\n  }\n  throw new Error('Unreachable');\n};\n```",
                    "type": "code",
                    "source": "src/utils/retry.ts",
                    "tags": ["utility", "async", "retry", "typescript"],
                    "project": "shared-utils"
                }
            }
        ],

        "memory_search": [
            {
                "description": "Search for user preferences",
                "input": {
                    "query": "user preferences coding style",
                    "type": "text",
                    "limit": 5
                }
            },
            {
                "description": "Semantic search for similar errors",
                "input": {
                    "query": "undefined property error in React component",
                    "type": "semantic",
                    "limit": 10,
                    "filters": {
                        "doc_type": "code",
                        "tags": ["error", "react"]
                    }
                }
            },
            {
                "description": "Hybrid search for project context",
                "input": {
                    "query": "authentication implementation decisions",
                    "type": "hybrid",
                    "limit": 15,
                    "filters": {
                        "project": "api-gateway"
                    }
                }
            },
            {
                "description": "Search for specific project decisions",
                "input": {
                    "query": "database choice postgresql mongodb",
                    "type": "text",
                    "limit": 10,
                    "filters": {
                        "doc_type": "reference",
                        "project": "backend-services"
                    }
                }
            }
        ],

        "memory_recall": [
            {
                "description": "Recall a specific memory by ID",
                "input": {
                    "id": "mem_abc123def456"
                }
            },
            {
                "description": "Recall a memory from search results",
                "input": {
                    "id": "doc_2024-01-15_auth-decision"
                }
            }
        ],

        "memory_delete": [
            {
                "description": "Delete an outdated preference",
                "input": {
                    "id": "mem_old-db-preference"
                }
            },
            {
                "description": "Delete a superseded decision",
                "input": {
                    "id": "doc_2023-12-01_old-auth-approach"
                }
            }
        ],

        "memory_list": [
            {
                "description": "List recent memories across all projects",
                "input": {
                    "limit": 20
                }
            },
            {
                "description": "List memories for a specific project",
                "input": {
                    "limit": 15,
                    "project": "api-gateway"
                }
            },
            {
                "description": "List only code-type memories",
                "input": {
                    "limit": 10,
                    "type": "code"
                }
            },
            {
                "description": "List recent notes for a project",
                "input": {
                    "limit": 25,
                    "type": "note",
                    "project": "dashboard-app"
                }
            }
        ],

        "session_save": [
            {
                "description": "Save basic session state",
                "input": {
                    "project_path": "/Users/dev/projects/api-gateway"
                }
            },
            {
                "description": "Save session with active files",
                "input": {
                    "project_path": "/Users/dev/projects/api-gateway",
                    "active_files": [
                        "src/auth/middleware.ts",
                        "src/auth/jwt.ts",
                        "tests/auth.test.ts"
                    ]
                }
            },
            {
                "description": "Save session with full context",
                "input": {
                    "project_path": "/Users/dev/projects/api-gateway",
                    "active_files": [
                        "src/auth/refresh.ts",
                        "src/models/token.ts"
                    ],
                    "context": {
                        "current_task": "Implementing refresh token rotation",
                        "completed": ["JWT verification", "Access token generation"],
                        "blockers": ["Need to decide on refresh token storage strategy"],
                        "next_steps": ["Implement token blacklist", "Add rotation endpoint"]
                    }
                }
            }
        ],

        "session_restore": [
            {
                "description": "Restore most recent session",
                "input": {}
            },
            {
                "description": "Restore specific session by ID",
                "input": {
                    "session_id": "sess_2024-01-15_api-gateway"
                }
            }
        ],

        "vault_write": [
            {
                "description": "Write a project documentation note",
                "input": {
                    "path": "projects/api-gateway/architecture",
                    "content": "# API Gateway Architecture\n\n## Overview\nThe API gateway handles authentication, rate limiting, and request routing.\n\n## Components\n- Auth middleware: JWT validation\n- Rate limiter: Token bucket algorithm\n- Router: Path-based routing to microservices",
                    "folder": "references",
                    "tags": ["architecture", "api-gateway", "documentation"]
                }
            },
            {
                "description": "Write a daily note",
                "input": {
                    "path": "daily/2024-01-15",
                    "content": "# 2024-01-15\n\n## Worked On\n- Implemented JWT refresh token rotation\n- Fixed race condition in token validation\n\n## Decisions Made\n- Using Redis for refresh token storage\n- 7-day refresh token expiry\n\n## Tomorrow\n- Add token blacklist for logout",
                    "folder": "daily",
                    "tags": ["daily", "api-gateway", "auth"]
                }
            },
            {
                "description": "Write a code reference note",
                "input": {
                    "path": "code/retry-patterns",
                    "content": "# Retry Patterns\n\n## Exponential Backoff\n```typescript\nasync function retry<T>(fn: () => Promise<T>, attempts = 3): Promise<T> {\n  // implementation\n}\n```\n\n## Circuit Breaker\nUse when calling unreliable external services.",
                    "folder": "code",
                    "tags": ["patterns", "reliability", "typescript"]
                }
            }
        ],

        "vault_read": [
            {
                "description": "Read project architecture documentation",
                "input": {
                    "path": "references/projects/api-gateway/architecture"
                }
            },
            {
                "description": "Read a daily note",
                "input": {
                    "path": "daily/2024-01-15"
                }
            },
            {
                "description": "Read a code reference",
                "input": {
                    "path": "code/retry-patterns"
                }
            }
        ],

        "memory_stats": [
            {
                "description": "Get full memory system statistics",
                "input": {}
            }
        ],

        # Knowledge graph tools (Graphiti)
        "search_entities": [
            {
                "description": "Search for user entity",
                "input": {
                    "query": "user preferences",
                    "limit": 10
                }
            },
            {
                "description": "Search for project entities",
                "input": {
                    "query": "api-gateway authentication",
                    "limit": 5
                }
            }
        ],

        "search_facts": [
            {
                "description": "Search for architectural decisions",
                "input": {
                    "query": "decided to use JWT",
                    "limit": 10
                }
            },
            {
                "description": "Search for user preferences relationships",
                "input": {
                    "query": "user prefers functional programming",
                    "limit": 5
                }
            }
        ],

        # Code search tools
        "code_search": [
            {
                "description": "Search for function implementations",
                "input": {
                    "query": "async function.*retry",
                    "path_filter": "*.ts",
                    "max_matches": 20
                }
            },
            {
                "description": "Search in specific repository",
                "input": {
                    "query": "JWT.*verify",
                    "repo_filter": "api-gateway",
                    "max_matches": 10
                }
            }
        ],

        "search_function": [
            {
                "description": "Find function definition",
                "input": {
                    "function_name": "authenticateRequest",
                    "language": "typescript",
                    "max_matches": 5
                }
            },
            {
                "description": "Find Python function",
                "input": {
                    "function_name": "process_request",
                    "language": "python",
                    "max_matches": 10
                }
            }
        ],

        "search_class": [
            {
                "description": "Find class definition",
                "input": {
                    "class_name": "AuthMiddleware",
                    "language": "typescript",
                    "max_matches": 5
                }
            },
            {
                "description": "Find Python class",
                "input": {
                    "class_name": "RequestHandler",
                    "language": "python",
                    "max_matches": 10
                }
            }
        ]
    }


def get_examples_for_tool(tool_name: str) -> List[Dict[str, Any]]:
    """
    Get examples for a specific tool.

    Args:
        tool_name: Name of the MCP tool

    Returns:
        List of example dictionaries, empty list if tool not found
    """
    all_examples = get_tool_examples()
    return all_examples.get(tool_name, [])


def format_examples_for_schema(tool_name: str) -> List[Dict[str, Any]]:
    """
    Format examples for inclusion in MCP tool schema.

    Args:
        tool_name: Name of the MCP tool

    Returns:
        List of input examples formatted for schema inclusion

    The returned format matches Anthropic's input_examples specification:
    [{"input": {...}}, {"input": {...}}]
    """
    examples = get_examples_for_tool(tool_name)
    return [{"input": ex["input"]} for ex in examples]
