"""Birdeye API client for token data fallback."""

import time
from datetime import UTC, datetime
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from walltrack.constants.token import (
    BIRDEYE_BASE_URL,
    BIRDEYE_TIMEOUT_SECONDS,
    MAX_RETRIES,
    NEW_TOKEN_AGE_MINUTES,
)
from walltrack.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenSource,
)

logger = structlog.get_logger(__name__)


class BirdeyeClient:
    """Fallback client for Birdeye API (NFR18)."""

    def __init__(self, api_key: str | None = None) -> None:
        """Initialize Birdeye client.

        Args:
            api_key: Birdeye API key (optional, uses env if not provided)
        """
        self.base_url = BIRDEYE_BASE_URL
        self.api_key = api_key or ""
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            headers: dict[str, str] = {"Accept": "application/json"}
            if self.api_key:
                headers["X-API-KEY"] = self.api_key

            self._client = httpx.AsyncClient(
                timeout=BIRDEYE_TIMEOUT_SECONDS,
                headers=headers,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def fetch_token(self, token_address: str) -> TokenFetchResult:
        """Fetch token characteristics from Birdeye (fallback).

        Args:
            token_address: Solana token mint address

        Returns:
            TokenFetchResult with token data or error
        """
        start_time = time.perf_counter()

        try:
            client = await self._get_client()

            # Fetch token overview
            url = f"{self.base_url}/defi/token_overview"
            params = {"address": token_address}

            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            fetch_time_ms = (time.perf_counter() - start_time) * 1000

            token = self._parse_response(token_address, data.get("data", {}))

            logger.debug(
                "birdeye_fetch_success",
                token=token_address[:8] + "...",
                fetch_time_ms=round(fetch_time_ms, 2),
            )

            return TokenFetchResult(
                success=True,
                token=token,
                source=TokenSource.BIRDEYE,
                fetch_time_ms=fetch_time_ms,
                used_fallback=True,
            )

        except httpx.TimeoutException as e:
            logger.warning(
                "birdeye_timeout",
                token=token_address[:8] + "...",
                error=str(e),
            )
            raise  # Will be caught by tenacity for retry

        except httpx.HTTPStatusError as e:
            logger.warning(
                "birdeye_http_error",
                token=token_address[:8] + "...",
                status=e.response.status_code,
            )
            raise

        except Exception as e:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "birdeye_error",
                token=token_address[:8] + "...",
                error=str(e),
            )
            return TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.BIRDEYE,
                fetch_time_ms=fetch_time_ms,
                error_message=str(e),
                used_fallback=True,
            )

    def _parse_response(
        self,
        token_address: str,
        data: dict[str, Any],
    ) -> TokenCharacteristics:
        """Parse Birdeye API response."""
        # Parse creation time if available
        created_at = None
        age_minutes = 0

        if data.get("createdAt"):
            created_at = datetime.fromtimestamp(
                data["createdAt"],
                tz=UTC,
            )
            age_minutes = int((datetime.now(UTC) - created_at).total_seconds() / 60)

        return TokenCharacteristics(
            token_address=token_address,
            name=data.get("name"),
            symbol=data.get("symbol"),
            price_usd=float(data.get("price", 0) or 0),
            market_cap_usd=data.get("mc"),
            liquidity=TokenLiquidity(usd=data.get("liquidity", 0) or 0),
            holder_count=data.get("holder"),
            created_at=created_at,
            age_minutes=age_minutes,
            is_new_token=age_minutes < NEW_TOKEN_AGE_MINUTES,
            source=TokenSource.BIRDEYE,
        )
