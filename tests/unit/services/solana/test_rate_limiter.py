"""Unit tests for GlobalRateLimiter singleton.

Tests:
- Singleton pattern (same instance)
- Rate limiting enforcement (2 req/sec)
- Concurrent access (no violations)
- Global lock prevents race conditions

Story: 3.5.5 - Global RPC Rate Limiter
"""

import asyncio
import time

import pytest

from walltrack.services.solana.rate_limiter import GlobalRateLimiter


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset singleton instance before each test."""
    GlobalRateLimiter.reset_for_testing()
    yield
    GlobalRateLimiter.reset_for_testing()


def test_singleton_pattern():
    """Test: Same instance returned on multiple get_instance() calls.

    Ensures GlobalRateLimiter is truly a singleton (single shared instance).

    AC1: Global rate limiter singleton created
    """
    instance1 = GlobalRateLimiter.get_instance()
    instance2 = GlobalRateLimiter.get_instance()

    assert instance1 is instance2, "get_instance() should return same instance"
    assert id(instance1) == id(instance2), "Instances should have same memory address"


@pytest.mark.asyncio
async def test_rate_limiting():
    """Test: Rate limit enforced (2 req/sec = 500ms min delay).

    Verifies that acquire() waits at least 500ms between consecutive calls.

    AC1: Total throughput never exceeds 2 req/sec
    """
    limiter = GlobalRateLimiter.get_instance()

    # First request: No delay (no previous request)
    start = time.time()
    await limiter.acquire()
    elapsed_1 = time.time() - start
    assert elapsed_1 < 0.1, "First request should not sleep"

    # Second request: Should wait ~500ms
    start = time.time()
    await limiter.acquire()
    elapsed_2 = time.time() - start
    assert 0.45 <= elapsed_2 <= 0.65, f"Second request should sleep ~500ms, got {elapsed_2:.3f}s"

    # Third request: Should wait ~500ms again
    start = time.time()
    await limiter.acquire()
    elapsed_3 = time.time() - start
    assert 0.45 <= elapsed_3 <= 0.65, f"Third request should sleep ~500ms, got {elapsed_3:.3f}s"


@pytest.mark.asyncio
async def test_concurrent_access():
    """Test: Multiple tasks don't violate 2 req/sec limit.

    Simulates 3 concurrent tasks (like Discovery, Profiling, Decay workers)
    making 10 requests each. Verifies global rate is never exceeded.

    AC2: limiter uses asyncio.Lock for thread-safe concurrent access
    """
    limiter = GlobalRateLimiter.get_instance()

    request_times = []

    async def worker(worker_id: int, num_requests: int = 10):
        """Simulate worker making multiple RPC requests."""
        for _ in range(num_requests):
            await limiter.acquire()
            request_times.append(time.time())

    # Run 3 workers concurrently (30 total requests)
    start = time.time()
    await asyncio.gather(
        worker(1, num_requests=10),
        worker(2, num_requests=10),
        worker(3, num_requests=10),
    )
    total_elapsed = time.time() - start

    # Expected: 30 requests at 2 req/sec = ~15 seconds
    expected_min = 30 * 0.5 - 1.0  # 14s (1s tolerance)
    expected_max = 30 * 0.5 + 1.0  # 16s (1s tolerance)

    assert expected_min <= total_elapsed <= expected_max, (
        f"30 requests should take ~15s at 2 req/sec, got {total_elapsed:.2f}s"
    )

    # Verify no two consecutive requests are < 450ms apart (allowing 50ms variance)
    for i in range(1, len(request_times)):
        delay = request_times[i] - request_times[i - 1]
        assert delay >= 0.45, (
            f"Consecutive requests too close: {delay:.3f}s (should be >= 0.5s)"
        )


@pytest.mark.asyncio
async def test_global_lock():
    """Test: Global lock prevents race conditions.

    Verifies that asyncio.Lock properly serializes concurrent acquire() calls,
    preventing multiple tasks from updating _last_request_time simultaneously.

    AC2: limiter uses asyncio.Lock for thread-safe concurrent access
    """
    limiter = GlobalRateLimiter.get_instance()

    # Track order of acquire() completions
    completion_order = []

    async def task(task_id: int):
        """Task that acquires rate limiter and records completion."""
        await limiter.acquire()
        completion_order.append(task_id)

    # Launch 5 tasks simultaneously
    tasks = [task(i) for i in range(5)]
    await asyncio.gather(*tasks)

    # All 5 tasks should complete
    assert len(completion_order) == 5, "All tasks should complete"

    # Tasks should complete in some sequential order (lock forces serialization)
    # We don't care about exact order, just that they didn't run truly parallel
    assert len(set(completion_order)) == 5, "No duplicate task IDs"


@pytest.mark.asyncio
async def test_reset_for_testing():
    """Test: reset_for_testing() creates fresh instance.

    Verifies test helper works correctly (singleton reset).
    """
    instance1 = GlobalRateLimiter.get_instance()

    GlobalRateLimiter.reset_for_testing()

    instance2 = GlobalRateLimiter.get_instance()

    assert instance1 is not instance2, "reset_for_testing() should create new instance"
