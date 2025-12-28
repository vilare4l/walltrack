"""Token fetcher service with caching and fallback."""

import time

import structlog

from walltrack.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenSource,
)
from walltrack.services.birdeye.client import BirdeyeClient
from walltrack.services.dexscreener.client import DexScreenerClient
from walltrack.services.token.cache import TokenCache

logger = structlog.get_logger(__name__)


class TokenFetcher:
    """Fetches token characteristics with caching and fallback.

    Priority: Cache -> DexScreener -> Birdeye -> Neutral
    """

    def __init__(
        self,
        dexscreener_client: DexScreenerClient,
        birdeye_client: BirdeyeClient,
        token_cache: TokenCache,
    ) -> None:
        """Initialize token fetcher.

        Args:
            dexscreener_client: DexScreener API client
            birdeye_client: Birdeye API client (fallback)
            token_cache: Token cache
        """
        self.dexscreener = dexscreener_client
        self.birdeye = birdeye_client
        self.cache = token_cache

    async def fetch(self, token_address: str) -> TokenFetchResult:
        """Fetch token characteristics with fallback chain.

        1. Check cache
        2. Try DexScreener
        3. Fallback to Birdeye
        4. Return neutral if all fail

        Args:
            token_address: Solana token mint address

        Returns:
            TokenFetchResult with token data
        """
        start_time = time.perf_counter()

        # Step 1: Check cache (AC2)
        cached = await self.cache.get(token_address)
        if cached:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "token_cache_hit",
                token=token_address[:8] + "...",
            )
            return TokenFetchResult(
                success=True,
                token=cached,
                source=TokenSource.CACHE,
                fetch_time_ms=fetch_time_ms,
            )

        # Step 2: Try DexScreener (AC1)
        try:
            result = await self.dexscreener.fetch_token(token_address)
            if result.success and result.token:
                await self.cache.set(result.token)
                return result
        except Exception as e:
            logger.warning(
                "dexscreener_fetch_failed",
                token=token_address[:8] + "...",
                error=str(e),
            )
            result = TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.DEXSCREENER,
                error_message=str(e),
            )

        # Step 3: Fallback to Birdeye (AC3 / NFR18)
        logger.info(
            "token_fallback_birdeye",
            token=token_address[:8] + "...",
            dexscreener_error=result.error_message if result else "Unknown",
        )

        try:
            birdeye_result = await self.birdeye.fetch_token(token_address)
            if birdeye_result.success and birdeye_result.token:
                await self.cache.set(birdeye_result.token)
                return birdeye_result
        except Exception as e:
            logger.warning(
                "birdeye_fetch_failed",
                token=token_address[:8] + "...",
                error=str(e),
            )
            birdeye_result = TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.BIRDEYE,
                error_message=str(e),
                used_fallback=True,
            )

        # Step 4: Check cache again (might have stale data)
        stale_cached = self.cache.get_stale(token_address)
        if stale_cached:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "token_using_stale_cache",
                token=token_address[:8] + "...",
            )
            stale_cached.source = TokenSource.CACHE
            return TokenFetchResult(
                success=True,
                token=stale_cached,
                source=TokenSource.CACHE,
                fetch_time_ms=fetch_time_ms,
                used_fallback=True,
            )

        # Step 5: Return neutral (AC3 - no data available)
        fetch_time_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "token_fallback_neutral",
            token=token_address[:8] + "...",
        )

        neutral_token = TokenCharacteristics(
            token_address=token_address,
            source=TokenSource.FALLBACK_NEUTRAL,
            is_new_token=True,  # Assume new if we can't get data
        )

        return TokenFetchResult(
            success=True,  # Neutral is still "success" for scoring
            token=neutral_token,
            source=TokenSource.FALLBACK_NEUTRAL,
            fetch_time_ms=fetch_time_ms,
            used_fallback=True,
            error_message="All sources failed, using neutral defaults",
        )

    async def close(self) -> None:
        """Close all clients."""
        await self.dexscreener.close()
        await self.birdeye.close()


# Singleton instance
_token_fetcher: TokenFetcher | None = None


async def get_token_fetcher() -> TokenFetcher:
    """Get or create token fetcher singleton."""
    global _token_fetcher

    if _token_fetcher is None:
        dexscreener = DexScreenerClient()
        birdeye = BirdeyeClient()
        cache = TokenCache()

        _token_fetcher = TokenFetcher(dexscreener, birdeye, cache)

    return _token_fetcher


async def reset_token_fetcher() -> None:
    """Reset token fetcher singleton (for testing)."""
    global _token_fetcher
    if _token_fetcher:
        await _token_fetcher.close()
    _token_fetcher = None
