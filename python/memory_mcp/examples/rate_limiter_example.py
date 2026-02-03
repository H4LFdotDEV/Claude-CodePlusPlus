#!/usr/bin/env python3
"""
Example demonstrating per-tool rate limiting.

Shows how different tools have independent rate limits and how
resource-intensive tools have stricter limits than lightweight ones.
"""

import sys
import os

# Direct import to avoid package initialization dependencies
rate_limiter_path = os.path.join(os.path.dirname(__file__), '..', 'rate_limiter.py')

# Load the rate_limiter module directly
with open(rate_limiter_path, 'r') as f:
    code = f.read()

namespace = {}
exec(code, namespace)

PerToolRateLimiter = namespace['PerToolRateLimiter']
TOOL_LIMITS = namespace['TOOL_LIMITS']


def main():
    """Demonstrate per-tool rate limiting."""
    print("=" * 70)
    print("Per-Tool Rate Limiter Example")
    print("=" * 70)
    print()

    # Show configured limits
    print("Configured Tool Limits:")
    print("-" * 70)
    for tool, (max_req, window) in TOOL_LIMITS.items():
        print(f"  {tool:30s} {max_req:4d} requests / {window:3d} seconds")
    print()

    # Create limiter
    limiter = PerToolRateLimiter()
    client_id = "example_client"

    # Example 1: High-frequency reads are allowed
    print("Example 1: High-frequency reads (memory_search)")
    print("-" * 70)
    for i in range(1, 6):
        result = limiter.check("memory_search", client_id)
        print(f"  Request {i}: {'✓ ALLOWED' if result.allowed else '✗ BLOCKED'} "
              f"({result.current_count}/{result.limit})")
    print()

    # Example 2: I/O intensive operations have stricter limits
    print("Example 2: I/O intensive operations (vault_write)")
    print("-" * 70)
    for i in range(1, 6):
        result = limiter.check("vault_write", client_id)
        status = '✓ ALLOWED' if result.allowed else f'✗ BLOCKED (retry after {result.retry_after:.1f}s)'
        print(f"  Request {i}: {status} ({result.current_count}/{result.limit})")
    print()

    # Example 3: Tools have independent limits
    print("Example 3: Tool independence")
    print("-" * 70)
    # Fill up vault_write limit
    for _ in range(20):
        limiter.check("vault_write", f"{client_id}_2")

    vault_result = limiter.check("vault_write", f"{client_id}_2")
    search_result = limiter.check("memory_search", f"{client_id}_2")

    print(f"  vault_write (after 20 requests): {'✓ ALLOWED' if vault_result.allowed else '✗ BLOCKED'}")
    print(f"  memory_search (independent):     {'✓ ALLOWED' if search_result.allowed else '✗ BLOCKED'}")
    print()

    # Example 4: Unknown tools use default limit
    print("Example 4: Unknown tool uses default limit")
    print("-" * 70)
    result = limiter.check("unknown_tool", f"{client_id}_3")
    default_limit = TOOL_LIMITS["default"]
    print(f"  unknown_tool: {result.limit} requests / {result.window_seconds}s "
          f"(default: {default_limit[0]}/{default_limit[1]}s)")
    print()

    # Example 5: Stats
    print("Example 5: Rate limiter statistics")
    print("-" * 70)
    stats = limiter.stats()
    print(f"  Tools tracked:    {stats['aggregate']['tools_tracked']}")
    print(f"  Active clients:   {stats['aggregate']['total_active_clients']}")
    print(f"  Total requests:   {stats['aggregate']['total_requests_in_window']}")
    print()
    print("  Per-tool breakdown:")
    for tool, tool_stats in stats['per_tool'].items():
        print(f"    {tool:20s} {tool_stats['total_requests_in_window']:3d} requests")
    print()

    print("=" * 70)
    print("Example complete!")
    print("=" * 70)


if __name__ == "__main__":
    main()
