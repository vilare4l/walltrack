"""Global RPC rate limiter for Solana RPC requests.

This module provides a singleton rate limiter that ensures all RPC requests
across the application (Discovery Worker, Profiling Worker, Decay Scheduler)
respect the global Solana RPC rate limit of 4 req/sec.

We use 2 req/sec as a safety margin to avoid hitting the limit.

Story: 3.5.5 - Global Rate Limiter + Autonomous Wallet Discovery Worker
"""

import asyncio
import time
from typing import ClassVar

import structlog

log = structlog.get_logger()


class GlobalRateLimiter:
    """Singleton rate limiter for all RPC requests.

    Ensures that all RPC requests across all workers (Discovery, Profiling, Decay)
    respect the global Solana RPC rate limit.

    Rate limit: 2 req/sec (safety margin below 4 req/sec Solana limit)

    Thread-safe via asyncio.Lock.

    Example:
        ```python
        limiter = GlobalRateLimiter.get_instance()
        await limiter.acquire()  # Waits if necessary to respect rate limit
        response = await rpc_client._request(...)  # Make RPC request
        ```
    """

    # Singleton instance (shared across all workers)
    _instance: ClassVar["GlobalRateLimiter | None"] = None

    # Global lock for thread-safe rate limiting
    _lock: ClassVar[asyncio.Lock] = asyncio.Lock()

    # Rate limit configuration (in seconds)
    # Default: 1.0s = 1 req/sec (can be overridden via configure())
    _rate_limit_delay: ClassVar[float] = 1.0

    def __init__(self) -> None:
        """Initialize rate limiter.

        Note: Use get_instance() instead of calling this directly.
        """
        # Last request time (shared across all workers)
        self._last_request_time: float = 0.0

        log.info(
            "global_rate_limiter_initialized",
            rate_limit_delay=self._rate_limit_delay,
            max_rps=1.0 / self._rate_limit_delay,
        )

    @classmethod
    def get_instance(cls) -> "GlobalRateLimiter":
        """Get or create the singleton instance.

        Thread-safe singleton creation.

        Returns:
            The singleton GlobalRateLimiter instance.
        """
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def configure(cls, delay_ms: int) -> None:
        """Configure rate limit delay (should be called at app startup).

        Args:
            delay_ms: Delay in milliseconds between requests.
                     1000ms = 1 req/sec (recommended)
                     500ms = 2 req/sec (aggressive, may hit rate limits)

        Example:
            ```python
            # At app startup
            config_repo = ConfigRepository(supabase_client)
            delay_ms = await config_repo.get_value("profiling_rpc_delay_ms", default="1000")
            GlobalRateLimiter.configure(int(delay_ms))
            ```
        """
        cls._rate_limit_delay = delay_ms / 1000.0  # Convert ms to seconds
        log.info(
            "global_rate_limiter_configured",
            delay_ms=delay_ms,
            delay_seconds=cls._rate_limit_delay,
            max_rps=1.0 / cls._rate_limit_delay,
        )

    async def acquire(self) -> None:
        """Acquire permission to make an RPC request.

        This method ensures that requests are spaced at least 500ms apart
        (2 req/sec) across all workers.

        Thread-safe via asyncio.Lock - only one worker can check/update
        _last_request_time at a time.

        Example:
            ```python
            limiter = GlobalRateLimiter.get_instance()

            # Worker 1
            await limiter.acquire()  # Checks: time_since_last = 600ms → OK, no sleep
            await rpc_client._request(...)

            # Worker 2 (immediately after Worker 1)
            await limiter.acquire()  # Checks: time_since_last = 10ms → Sleep 490ms
            await rpc_client._request(...)
            ```
        """
        async with self._lock:
            current_time = time.time()
            time_since_last = current_time - self._last_request_time

            if time_since_last < self._rate_limit_delay:
                sleep_time = self._rate_limit_delay - time_since_last

                log.debug(
                    "rate_limit_throttling",
                    time_since_last_ms=int(time_since_last * 1000),
                    sleep_ms=int(sleep_time * 1000),
                )

                await asyncio.sleep(sleep_time)

            # Update last request time
            self._last_request_time = time.time()

    @classmethod
    def reset_for_testing(cls) -> None:
        """Reset singleton instance for testing.

        **TESTING ONLY** - Do not use in production code.

        This allows each test to start with a fresh rate limiter instance.
        Also recreates the lock to avoid event loop binding issues in pytest.
        """
        cls._instance = None
        cls._lock = asyncio.Lock()  # Recreate lock for new event loop
