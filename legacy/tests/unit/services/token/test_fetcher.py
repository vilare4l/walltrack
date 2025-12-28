"""Unit tests for token fetcher service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenSource,
)
from walltrack.services.birdeye.client import BirdeyeClient
from walltrack.services.dexscreener.client import DexScreenerClient
from walltrack.services.token.cache import TokenCache
from walltrack.services.token.fetcher import TokenFetcher


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Sample token for testing."""
    return TokenCharacteristics(
        token_address="TokenMint12345678901234567890123456789012",
        name="Test Token",
        symbol="TEST",
        price_usd=0.001,
        market_cap_usd=100000,
        liquidity=TokenLiquidity(usd=50000),
        age_minutes=30,
        is_new_token=False,
        source=TokenSource.DEXSCREENER,
    )


@pytest.fixture
def mock_dexscreener() -> MagicMock:
    """Mock DexScreener client."""
    client = MagicMock(spec=DexScreenerClient)
    client.fetch_token = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_birdeye() -> MagicMock:
    """Mock Birdeye client."""
    client = MagicMock(spec=BirdeyeClient)
    client.fetch_token = AsyncMock()
    client.close = AsyncMock()
    return client


class TestTokenFetcherCache:
    """Tests for cache behavior."""

    @pytest.mark.asyncio
    async def test_fetch_from_cache(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test cache hit returns cached data."""
        cache = TokenCache()
        await cache.set(sample_token)

        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.CACHE
        mock_dexscreener.fetch_token.assert_not_called()
        mock_birdeye.fetch_token.assert_not_called()


class TestTokenFetcherDexScreener:
    """Tests for DexScreener fetching."""

    @pytest.mark.asyncio
    async def test_fetch_from_dexscreener(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test DexScreener fetch on cache miss."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
            fetch_time_ms=50.0,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.DEXSCREENER
        mock_dexscreener.fetch_token.assert_called_once()
        mock_birdeye.fetch_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_dexscreener_result_cached(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test DexScreener result is cached."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)

        # First fetch
        await fetcher.fetch(sample_token.token_address)

        # Second fetch should hit cache
        result = await fetcher.fetch(sample_token.token_address)

        assert result.source == TokenSource.CACHE
        mock_dexscreener.fetch_token.assert_called_once()  # Only called once


class TestTokenFetcherFallback:
    """Tests for fallback behavior."""

    @pytest.mark.asyncio
    async def test_fallback_to_birdeye(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test Birdeye fallback when DexScreener fails."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=False,
            token=None,
            source=TokenSource.DEXSCREENER,
            error_message="Timeout",
        )
        sample_token.source = TokenSource.BIRDEYE
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.BIRDEYE,
            used_fallback=True,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.BIRDEYE
        assert result.used_fallback is True
        mock_dexscreener.fetch_token.assert_called_once()
        mock_birdeye.fetch_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_neutral(
        self,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test neutral fallback when all sources fail."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=False,
            token=None,
            source=TokenSource.DEXSCREENER,
            error_message="API Error",
        )
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=False,
            token=None,
            source=TokenSource.BIRDEYE,
            error_message="API Error",
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch("UnknownToken12345678901234567890123")

        assert result.success is True  # Neutral is still success
        assert result.source == TokenSource.FALLBACK_NEUTRAL
        assert result.token is not None
        assert result.token.is_new_token is True
        assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_fallback_to_stale_cache(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test stale cache fallback when APIs fail."""
        # Pre-populate cache with stale data
        cache = TokenCache(ttl_seconds=1)
        await cache.set(sample_token)

        # Wait for TTL expiry
        import asyncio

        await asyncio.sleep(1.1)

        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=False, token=None, source=TokenSource.DEXSCREENER
        )
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=False, token=None, source=TokenSource.BIRDEYE
        )

        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.CACHE
        assert result.used_fallback is True
        assert result.token.token_address == sample_token.token_address


class TestTokenFetcherExceptionHandling:
    """Tests for exception handling."""

    @pytest.mark.asyncio
    async def test_dexscreener_exception_triggers_fallback(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test exception in DexScreener triggers Birdeye fallback."""
        mock_dexscreener.fetch_token.side_effect = Exception("Connection error")
        sample_token.source = TokenSource.BIRDEYE
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.BIRDEYE,
            used_fallback=True,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.BIRDEYE


class TestTokenFetcherClose:
    """Tests for closing the fetcher."""

    @pytest.mark.asyncio
    async def test_close_closes_clients(
        self,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test close() closes all clients."""
        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)

        await fetcher.close()

        mock_dexscreener.close.assert_called_once()
        mock_birdeye.close.assert_called_once()
