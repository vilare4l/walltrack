"""DexScreener API client for token data."""

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
    DEXSCREENER_BASE_URL,
    DEXSCREENER_TIMEOUT_SECONDS,
    MAX_RETRIES,
    NEW_TOKEN_AGE_MINUTES,
)
from walltrack.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenPriceChange,
    TokenSource,
    TokenTransactions,
    TokenVolume,
)

logger = structlog.get_logger(__name__)


class DexScreenerClient:
    """Client for DexScreener API."""

    def __init__(self, timeout: int = DEXSCREENER_TIMEOUT_SECONDS) -> None:
        """Initialize DexScreener client.

        Args:
            timeout: Request timeout in seconds
        """
        self.base_url = DEXSCREENER_BASE_URL
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Accept": "application/json"},
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
        """Fetch token characteristics from DexScreener.

        Args:
            token_address: Solana token mint address

        Returns:
            TokenFetchResult with token data or error
        """
        start_time = time.perf_counter()

        try:
            client = await self._get_client()
            url = f"{self.base_url}/dex/tokens/{token_address}"

            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            fetch_time_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            token = self._parse_response(token_address, data)

            logger.debug(
                "dexscreener_fetch_success",
                token=token_address[:8] + "...",
                fetch_time_ms=round(fetch_time_ms, 2),
            )

            return TokenFetchResult(
                success=True,
                token=token,
                source=TokenSource.DEXSCREENER,
                fetch_time_ms=fetch_time_ms,
            )

        except httpx.TimeoutException as e:
            logger.warning(
                "dexscreener_timeout",
                token=token_address[:8] + "...",
                error=str(e),
            )
            raise  # Will be caught by tenacity for retry

        except httpx.HTTPStatusError as e:
            logger.warning(
                "dexscreener_http_error",
                token=token_address[:8] + "...",
                status=e.response.status_code,
            )
            raise

        except Exception as e:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "dexscreener_error",
                token=token_address[:8] + "...",
                error=str(e),
            )
            return TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.DEXSCREENER,
                fetch_time_ms=fetch_time_ms,
                error_message=str(e),
            )

    def _parse_response(
        self,
        token_address: str,
        data: dict[str, Any],
    ) -> TokenCharacteristics:
        """Parse DexScreener API response."""
        pairs = data.get("pairs", [])

        if not pairs:
            # No trading pairs found - return minimal data
            return TokenCharacteristics(
                token_address=token_address,
                source=TokenSource.DEXSCREENER,
                is_new_token=True,  # Assume new if no pairs
            )

        # Use the highest liquidity pair
        pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))

        # Parse creation time
        created_at = None
        age_minutes = 0
        if pair.get("pairCreatedAt"):
            created_at = datetime.fromtimestamp(
                pair["pairCreatedAt"] / 1000,
                tz=UTC,
            )
            age_minutes = int((datetime.now(UTC) - created_at).total_seconds() / 60)

        # Parse liquidity
        liq = pair.get("liquidity", {})
        liquidity = TokenLiquidity(
            usd=liq.get("usd", 0),
            base=liq.get("base", 0),
            quote=liq.get("quote", 0),
        )

        # Parse price changes
        pc = pair.get("priceChange", {})
        price_change = TokenPriceChange(
            m5=pc.get("m5"),
            h1=pc.get("h1"),
            h6=pc.get("h6"),
            h24=pc.get("h24"),
        )

        # Parse volume
        vol = pair.get("volume", {})
        volume = TokenVolume(
            m5=vol.get("m5", 0),
            h1=vol.get("h1", 0),
            h6=vol.get("h6", 0),
            h24=vol.get("h24", 0),
        )

        # Parse transactions
        txns = pair.get("txns", {}).get("h24", {})
        transactions = TokenTransactions(
            buys=txns.get("buys", 0),
            sells=txns.get("sells", 0),
            total=txns.get("buys", 0) + txns.get("sells", 0),
        )

        # Get base token info
        base_token = pair.get("baseToken", {})

        return TokenCharacteristics(
            token_address=token_address,
            name=base_token.get("name"),
            symbol=base_token.get("symbol"),
            price_usd=float(pair.get("priceUsd", 0) or 0),
            price_sol=float(pair.get("priceNative", 0) or 0),
            market_cap_usd=pair.get("marketCap"),
            fdv_usd=pair.get("fdv"),
            liquidity=liquidity,
            volume=volume,
            price_change=price_change,
            transactions_24h=transactions,
            created_at=created_at,
            age_minutes=age_minutes,
            is_new_token=age_minutes < NEW_TOKEN_AGE_MINUTES,
            source=TokenSource.DEXSCREENER,
        )
