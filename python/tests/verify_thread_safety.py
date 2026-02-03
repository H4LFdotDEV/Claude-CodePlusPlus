#!/usr/bin/env python3
"""
Verification script for thread safety of rate limiter.

This script demonstrates that the rate limiter correctly handles
concurrent access from multiple threads without race conditions.
"""

import threading
import time
from memory_mcp.rate_limiter import RateLimiter


def test_concurrent_access():
    """Test that concurrent access maintains correct counts."""
    print("Testing concurrent access to rate limiter...")
    print("=" * 60)

    # Create rate limiter with 50 request limit
    limiter = RateLimiter(max_requests=50, window_seconds=10)

    results = []

    def worker(thread_id):
        """Each thread tries to make 10 requests."""
        for i in range(10):
            result = limiter.check("shared_client")
            results.append((thread_id, i, result.allowed, result.current_count))

    # Launch 10 threads (100 total request attempts)
    threads = [
        threading.Thread(target=worker, args=(i,))
        for i in range(10)
    ]

    start_time = time.time()

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    elapsed = time.time() - start_time

    # Analyze results
    allowed = [r for r in results if r[2]]  # r[2] is allowed flag
    denied = [r for r in results if not r[2]]

    print(f"\nCompleted in {elapsed:.3f} seconds")
    print(f"Total requests attempted: {len(results)}")
    print(f"Requests allowed: {len(allowed)}")
    print(f"Requests denied: {len(denied)}")

    # Verify final state
    status = limiter.get_client_status("shared_client")
    print(f"\nFinal client status:")
    print(f"  Current count: {status.current_count}")
    print(f"  Limit: {status.limit}")
    print(f"  Allowed: {status.allowed}")

    # Check for correctness
    print("\nVerification:")
    if len(allowed) == 50 and len(denied) == 50:
        print("  ✓ Exactly 50 requests allowed, 50 denied")
    else:
        print(f"  ✗ Expected 50/50, got {len(allowed)}/{len(denied)}")

    if status.current_count == 50:
        print("  ✓ Final count is correct (50)")
    else:
        print(f"  ✗ Final count is incorrect (expected 50, got {status.current_count})")

    # Check that no duplicate counts occurred (would indicate race condition)
    allowed_counts = [r[3] for r in results if r[2]]  # r[3] is current_count
    unique_counts = len(set(allowed_counts))

    if unique_counts == len(allowed):
        print(f"  ✓ All allowed requests have unique counts ({unique_counts})")
    else:
        print(f"  ✗ Duplicate counts detected (race condition)")

    print("=" * 60)

    return len(allowed) == 50 and status.current_count == 50 and unique_counts == len(allowed)


def test_concurrent_different_clients():
    """Test that different clients maintain independent limits."""
    print("\nTesting concurrent access for different clients...")
    print("=" * 60)

    limiter = RateLimiter(max_requests=20, window_seconds=10)

    def worker(client_id):
        """Each thread makes requests for its own client."""
        for _ in range(20):
            limiter.check(client_id)

    # Launch 5 threads for different clients
    threads = [
        threading.Thread(target=worker, args=(f"client_{i}",))
        for i in range(5)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify each client has exactly 20 requests
    print("\nClient statuses:")
    all_correct = True
    for i in range(5):
        status = limiter.get_client_status(f"client_{i}")
        print(f"  client_{i}: {status.current_count} requests")
        if status.current_count != 20:
            all_correct = False

    stats = limiter.stats()
    print(f"\nOverall stats:")
    print(f"  Active clients: {stats['active_clients']}")
    print(f"  Total requests: {stats['total_requests_in_window']}")

    print("\nVerification:")
    if all_correct:
        print("  ✓ All clients have correct counts (20 each)")
    else:
        print("  ✗ Some clients have incorrect counts")

    if stats['active_clients'] == 5 and stats['total_requests_in_window'] == 100:
        print("  ✓ Stats are correct (5 clients, 100 total)")
    else:
        print(f"  ✗ Stats incorrect (got {stats['active_clients']} clients, {stats['total_requests_in_window']} requests)")

    print("=" * 60)

    return all_correct and stats['active_clients'] == 5


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Rate Limiter Thread Safety Verification")
    print("=" * 60)

    test1_passed = test_concurrent_access()
    test2_passed = test_concurrent_different_clients()

    print("\n" + "=" * 60)
    print("Summary:")
    print("=" * 60)
    if test1_passed and test2_passed:
        print("✓ All tests passed - Rate limiter is thread-safe!")
    else:
        print("✗ Some tests failed - Thread safety issues detected")
    print("=" * 60 + "\n")
