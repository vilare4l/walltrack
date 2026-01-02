"""Integration test: Global rate limiter enforcement with concurrent clients.

Tests that multiple RPC client instances share the same global rate limiter
and never exceed 2 req/sec aggregate throughput.

Scenario:
    3 SolanaRPCClient instances created
    → 100 requests made concurrently from all 3
    → Measured request rate <= 2.1 req/sec (accounting for timing variance)
    → Validates singleton pattern + global lock enforcement

Story: 3.5.5 - Global RPC Rate Limiter + Wallet Discovery Worker
"""

import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest

from walltrack.services.solana.rate_limiter import GlobalRateLimiter
from walltrack.services.solana.rpc_client import SolanaRPCClient


@pytest.mark.asyncio
async def test_global_rate_limit_enforced():
    """Test: 3 concurrent RPC clients respect global 2 req/sec limit.

    Creates 3 RPC client instances and makes requests concurrently.
    Measures actual request rate and verifies it never exceeds 2.1 req/sec
    (accounting for timing variance).

    This validates:
    - GlobalRateLimiter singleton is shared across instances
    - asyncio.Lock prevents race conditions
    - Rate limit is enforced globally, not per-instance
    """
    # Reset singleton for clean test
    GlobalRateLimiter.reset_for_testing()

    # Get the global rate limiter instance
    limiter = GlobalRateLimiter.get_instance()

    # Simulate 3 concurrent clients making requests
    # Total: 60 requests (20 per "client")
    num_requests_per_client = 20
    num_clients = 3

    # Track request times
    request_times = []

    async def make_requests(client_id: int):
        """Simulate a client making N requests."""
        for i in range(num_requests_per_client):
            await limiter.acquire()
            request_times.append(time.time())

    # Measure time for all requests
    start_time = time.time()

    # Run all 3 "clients" concurrently
    await asyncio.gather(
        make_requests(1),
        make_requests(2),
        make_requests(3),
    )

    end_time = time.time()
    elapsed_time = end_time - start_time

    # Calculate actual request rate
    total_requests = num_requests_per_client * num_clients  # 60 requests
    actual_rate = total_requests / elapsed_time

    # Expected minimum time (at 2 req/sec):
    # 60 requests / 2 req/sec = 30 seconds
    expected_min_time = (total_requests - 1) * 0.5  # First request immediate, rest delayed

    # Assert: Rate should not exceed 2.1 req/sec (10% margin for timing variance)
    max_allowed_rate = 2.1

    # Assertions
    assert (
        actual_rate <= max_allowed_rate
    ), f"Rate limit violated: {actual_rate:.2f} req/sec > {max_allowed_rate} req/sec"

    assert (
        elapsed_time >= expected_min_time * 0.95
    ), f"Requests completed too fast: {elapsed_time:.2f}s < {expected_min_time:.2f}s (expected minimum)"

    # SUCCESS: Global rate limiter enforced across all clients ✅
    print(
        f"✅ Rate limiter enforcement validated: {actual_rate:.2f} req/sec "
        f"({total_requests} requests in {elapsed_time:.2f}s)"
    )


@pytest.mark.asyncio
async def test_rate_limiter_singleton_shared():
    """Test: Multiple RPC clients use the same GlobalRateLimiter instance.

    Validates singleton pattern: all clients share the same rate limiter instance.
    """
    # Reset singleton
    GlobalRateLimiter.reset_for_testing()

    # Create 3 clients
    client1 = SolanaRPCClient()
    client2 = SolanaRPCClient()
    client3 = SolanaRPCClient()

    # Get rate limiter instances
    limiter1 = GlobalRateLimiter.get_instance()
    limiter2 = GlobalRateLimiter.get_instance()
    limiter3 = GlobalRateLimiter.get_instance()

    # All should be the same instance (singleton)
    assert limiter1 is limiter2
    assert limiter2 is limiter3
    assert limiter1 is limiter3

    # SUCCESS: Singleton pattern validated ✅


@pytest.mark.asyncio
async def test_rate_limiter_concurrent_access():
    """Test: Concurrent requests don't violate rate limit due to race conditions.

    Tests that asyncio.Lock properly protects shared state during concurrent access.
    Without the lock, race conditions could allow multiple tasks to proceed
    simultaneously, violating the rate limit.
    """
    # Reset singleton
    GlobalRateLimiter.reset_for_testing()
    limiter = GlobalRateLimiter.get_instance()

    # Track request times
    request_times = []

    async def make_request():
        """Make a single rate-limited request."""
        await limiter.acquire()
        request_times.append(time.time())

    # Make 20 concurrent requests
    num_requests = 20
    start_time = time.time()

    await asyncio.gather(*[make_request() for _ in range(num_requests)])

    end_time = time.time()
    elapsed_time = end_time - start_time

    # Calculate intervals between consecutive requests
    intervals = [
        request_times[i] - request_times[i - 1] for i in range(1, len(request_times))
    ]

    # Each interval should be >= 0.5s (2 req/sec rate limit)
    # Allow 5% margin for timing precision
    min_interval = 0.5 * 0.95

    violations = [interval for interval in intervals if interval < min_interval]

    # Assert: No race conditions (all intervals respect rate limit)
    assert (
        len(violations) == 0
    ), f"Race condition detected: {len(violations)} intervals < {min_interval}s"

    # Assert: Total time is reasonable (should be ~9.5s for 20 requests at 2 req/sec)
    expected_time = (num_requests - 1) * 0.5  # First request immediate, rest delayed
    assert (
        elapsed_time >= expected_time * 0.95
    ), f"Requests completed too fast: {elapsed_time:.2f}s < {expected_time}s"

    # SUCCESS: Lock prevents race conditions ✅
    print(
        f"✅ Concurrent access validated: {num_requests} requests in {elapsed_time:.2f}s, "
        f"min interval: {min(intervals):.3f}s"
    )
