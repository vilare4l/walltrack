"""Base API client with circuit breaker and retry logic.

This module provides:
- CircuitState enum for circuit breaker states
- CircuitBreaker dataclass for tracking circuit breaker state
- BaseAPIClient class for making resilient HTTP requests
"""

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import httpx
import structlog

from walltrack.core.exceptions import CircuitBreakerOpenError, ExternalServiceError

log = structlog.get_logger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests allowed
    OPEN = "open"  # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Tracks consecutive failures and opens the circuit when threshold is reached.
    After cooldown period, allows a single test request (half-open state).

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit.
        cooldown_seconds: Seconds to wait before half-open test.
        failure_count: Current consecutive failure count.
        last_failure_time: Timestamp of most recent failure.
        state: Current circuit state (CLOSED, OPEN, HALF_OPEN).
    """

    failure_threshold: int = 5
    cooldown_seconds: int = 30
    failure_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)

    def record_success(self) -> None:
        """Record a successful request.

        Resets failure count and sets state to CLOSED.
        """
        self.failure_count = 0
        self.state = CircuitState.CLOSED
        log.debug("circuit_breaker_success", state="closed")

    def record_failure(self) -> None:
        """Record a failed request.

        Increments failure count and opens circuit if threshold reached.
        In HALF_OPEN state, a single failure reopens the circuit.
        """
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately reopens
            self.state = CircuitState.OPEN
            log.warning(
                "circuit_breaker_reopened",
                failure_count=self.failure_count,
                state="open",
            )
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log.warning(
                "circuit_breaker_opened",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
                state="open",
            )
        else:
            log.debug(
                "circuit_breaker_failure",
                failure_count=self.failure_count,
                threshold=self.failure_threshold,
                state="closed",
            )

    def can_execute(self) -> bool:
        """Check if a request can be executed.

        Returns:
            True if request is allowed, False otherwise.

        State transitions:
            - CLOSED: Always returns True
            - OPEN: Returns False unless cooldown elapsed, then transitions to HALF_OPEN
            - HALF_OPEN: Returns True (allows test request)
        """
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time is None:
                return False

            elapsed = datetime.now(UTC) - self.last_failure_time
            if elapsed > timedelta(seconds=self.cooldown_seconds):
                self.state = CircuitState.HALF_OPEN
                log.info(
                    "circuit_breaker_half_open",
                    cooldown_elapsed=elapsed.total_seconds(),
                    state="half_open",
                )
                return True
            return False

        # HALF_OPEN: allow test request
        return True

    def raise_if_open(self) -> None:
        """Raise exception if circuit is open and not ready for test.

        Raises:
            CircuitBreakerOpenError: If circuit is open and cooldown not elapsed.
        """
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Next retry in "
                f"{self._time_until_half_open():.1f} seconds."
            )

    def _time_until_half_open(self) -> float:
        """Calculate seconds until circuit transitions to half-open.

        Returns:
            Seconds remaining until half-open, or 0 if ready.
        """
        if self.last_failure_time is None:
            return 0.0

        elapsed = datetime.now(UTC) - self.last_failure_time
        remaining = self.cooldown_seconds - elapsed.total_seconds()
        return max(0.0, remaining)


class BaseAPIClient:
    """Base API client with retry and circuit breaker support.

    Provides resilient HTTP requests with:
    - Lazy client initialization (created on first request)
    - Automatic retry with exponential backoff
    - Circuit breaker pattern for failure protection
    - Proper resource cleanup

    Attributes:
        base_url: Base URL for all requests.
        timeout: Request timeout in seconds.
        headers: Default headers for all requests.

    Example:
        client = BaseAPIClient(
            base_url="https://api.example.com",
            headers={"Authorization": "Bearer token"}
        )
        response = await client.get("/endpoint")
        await client.close()
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
        circuit_breaker_threshold: int = 5,
        circuit_breaker_cooldown: int = 30,
    ) -> None:
        """Initialize BaseAPIClient.

        Args:
            base_url: Base URL for all requests.
            timeout: Request timeout in seconds (default: 30).
            headers: Default headers for all requests.
            circuit_breaker_threshold: Failures before circuit opens (default: 5).
            circuit_breaker_cooldown: Seconds before half-open (default: 30).
        """
        self.base_url = base_url
        self.timeout = timeout
        self.headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_threshold,
            cooldown_seconds=circuit_breaker_cooldown,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the httpx client (lazy initialization).

        Returns:
            The httpx AsyncClient instance.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
            )
            log.debug("httpx_client_created", base_url=self.base_url)
        return self._client

    async def close(self) -> None:
        """Close the httpx client and release resources."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            log.debug("httpx_client_closed", base_url=self.base_url)

    async def _request(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make an HTTP request with retry and circuit breaker.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE).
            path: Request path (appended to base_url).
            max_retries: Maximum retry attempts (default: 3).
            **kwargs: Additional arguments passed to httpx.request.

        Returns:
            httpx.Response on success.

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open.
            ExternalServiceError: If request fails after all retries.
        """
        # Check circuit breaker before making request
        self._circuit_breaker.raise_if_open()

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                log.debug(
                    "request_attempt",
                    method=method,
                    path=path,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

                response = await client.request(method, path, **kwargs)
                response.raise_for_status()

                # Success - reset circuit breaker
                self._circuit_breaker.record_success()
                return response

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code

                # 4xx errors (except 429) - no retry, fail immediately
                if 400 <= status_code < 500 and status_code != 429:
                    log.warning(
                        "request_client_error",
                        method=method,
                        path=path,
                        status_code=status_code,
                        error=str(e),
                    )
                    raise ExternalServiceError(
                        service=self.base_url,
                        message=str(e),
                        status_code=status_code,
                    ) from e

                # 429 or 5xx - retry
                self._circuit_breaker.record_failure()
                last_error = e
                log.warning(
                    "request_server_error",
                    method=method,
                    path=path,
                    status_code=status_code,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

            except (httpx.TimeoutException, httpx.RequestError) as e:
                self._circuit_breaker.record_failure()
                last_error = e
                log.warning(
                    "request_connection_error",
                    method=method,
                    path=path,
                    error=str(e),
                    attempt=attempt + 1,
                    max_retries=max_retries,
                )

            # Exponential backoff: 1s, 2s, 4s (capped)
            if attempt < max_retries - 1:
                backoff = min(2**attempt, 4)
                log.debug("request_retry_backoff", seconds=backoff)
                await asyncio.sleep(backoff)

        # All retries exhausted
        log.error(
            "request_max_retries_exceeded",
            method=method,
            path=path,
            max_retries=max_retries,
        )
        raise ExternalServiceError(
            service=self.base_url,
            message=f"Max retries ({max_retries}) exceeded: {last_error}",
        )

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a GET request.

        Args:
            path: Request path.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            httpx.Response on success.
        """
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a POST request.

        Args:
            path: Request path.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            httpx.Response on success.
        """
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a PUT request.

        Args:
            path: Request path.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            httpx.Response on success.
        """
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make a DELETE request.

        Args:
            path: Request path.
            **kwargs: Additional arguments passed to httpx.

        Returns:
            httpx.Response on success.
        """
        return await self._request("DELETE", path, **kwargs)
