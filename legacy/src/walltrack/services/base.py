"""Base API client with retry logic and circuit breaker."""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

import httpx
import structlog

from walltrack.config.settings import get_settings
from walltrack.core.exceptions import CircuitBreakerOpenError

log = structlog.get_logger()


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Simple circuit breaker implementation."""

    failure_threshold: int = 5
    cooldown_seconds: int = 30
    failure_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)

    def record_success(self) -> None:
        """Record a successful call."""
        self.failure_count = 0
        self.state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()

        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log.warning(
                "circuit_breaker_opened",
                failure_count=self.failure_count,
                cooldown=self.cooldown_seconds,
            )

    def can_execute(self) -> bool:
        """Check if a call can be executed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            if self.last_failure_time is None:
                return True

            elapsed = datetime.utcnow() - self.last_failure_time
            if elapsed > timedelta(seconds=self.cooldown_seconds):
                self.state = CircuitState.HALF_OPEN
                log.info("circuit_breaker_half_open")
                return True
            return False

        # HALF_OPEN - allow one request
        return True

    def raise_if_open(self) -> None:
        """Raise exception if circuit is open."""
        if not self.can_execute():
            raise CircuitBreakerOpenError(
                f"Circuit breaker is open. Retry after {self.cooldown_seconds}s"
            )


class BaseAPIClient:
    """Base class for external API clients."""

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.headers = headers or {}
        self._client: httpx.AsyncClient | None = None
        settings = get_settings()
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=settings.circuit_breaker_threshold,
            cooldown_seconds=settings.circuit_breaker_cooldown,
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self.headers,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with retry and circuit breaker."""
        self._circuit_breaker.raise_if_open()

        client = await self._get_client()
        last_exception: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await client.request(method, path, **kwargs)
                response.raise_for_status()
                self._circuit_breaker.record_success()
                return response
            except (TimeoutError, httpx.HTTPError) as e:
                last_exception = e
                self._circuit_breaker.record_failure()
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 4)
                    log.warning(
                        "api_request_retry",
                        method=method,
                        path=path,
                        attempt=attempt + 1,
                        wait_time=wait_time,
                    )
                    await asyncio.sleep(wait_time)

        log.error("api_request_failed", method=method, path=path, error=str(last_exception))
        if last_exception is not None:
            raise last_exception
        raise RuntimeError("Request failed without exception")

    async def get(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make GET request."""
        return await self._request("GET", path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make POST request."""
        return await self._request("POST", path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make PUT request."""
        return await self._request("PUT", path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> httpx.Response:
        """Make DELETE request."""
        return await self._request("DELETE", path, **kwargs)
