"""Unit tests for token cache service."""

import asyncio

import pytest

from walltrack.models.token import TokenCharacteristics, TokenSource
from walltrack.services.token.cache import TokenCache


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Create sample token for testing."""
    return TokenCharacteristics(
        token_address="TokenMint12345678901234567890123456789012",
        name="Test Token",
        symbol="TEST",
        price_usd=0.001,
        market_cap_usd=100000,
        source=TokenSource.DEXSCREENER,
    )


class TestTokenCacheBasic:
    """Basic cache operations tests."""

    @pytest.mark.asyncio
    async def test_cache_miss(self):
        """Test cache miss returns None."""
        cache = TokenCache()
        result = await cache.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, sample_token: TokenCharacteristics):
        """Test setting and getting from cache."""
        cache = TokenCache()
        await cache.set(sample_token)

        result = await cache.get(sample_token.token_address)

        assert result is not None
        assert result.token_address == sample_token.token_address
        assert result.source == TokenSource.CACHE  # Source updated to CACHE

    @pytest.mark.asyncio
    async def test_cache_invalidate(self, sample_token: TokenCharacteristics):
        """Test invalidating cache entry."""
        cache = TokenCache()
        await cache.set(sample_token)

        await cache.invalidate(sample_token.token_address)

        result = await cache.get(sample_token.token_address)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_clear(self, sample_token: TokenCharacteristics):
        """Test clearing entire cache."""
        cache = TokenCache()
        await cache.set(sample_token)

        await cache.clear()

        result = await cache.get(sample_token.token_address)
        assert result is None


class TestTokenCacheTTL:
    """Cache TTL (time-to-live) tests."""

    @pytest.mark.asyncio
    async def test_ttl_not_expired(self, sample_token: TokenCharacteristics):
        """Test cache hit for non-expired entry."""
        cache = TokenCache(ttl_seconds=300)
        await cache.set(sample_token)

        result = await cache.get(sample_token.token_address)
        assert result is not None

    @pytest.mark.asyncio
    async def test_ttl_expired(self, sample_token: TokenCharacteristics):
        """Test cache miss for expired entry."""
        cache = TokenCache(ttl_seconds=1)
        await cache.set(sample_token)

        # Wait for expiry
        await asyncio.sleep(1.1)

        result = await cache.get(sample_token.token_address)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_stale_bypasses_ttl(self, sample_token: TokenCharacteristics):
        """Test get_stale returns expired entry."""
        cache = TokenCache(ttl_seconds=1)
        await cache.set(sample_token)

        # Wait for expiry
        await asyncio.sleep(1.1)

        # Regular get returns None
        result = await cache.get(sample_token.token_address)
        assert result is None

        # get_stale returns the entry
        stale = cache.get_stale(sample_token.token_address)
        assert stale is not None
        assert stale.token_address == sample_token.token_address


class TestTokenCacheLRU:
    """Cache LRU eviction tests."""

    @pytest.mark.asyncio
    async def test_lru_eviction_at_capacity(self):
        """Test LRU eviction when cache is full."""
        cache = TokenCache(max_size=2)

        # Add three tokens
        for i in range(3):
            token = TokenCharacteristics(
                token_address=f"Token{i}{'0' * 38}",
                source=TokenSource.DEXSCREENER,
            )
            await cache.set(token)

        # First token should be evicted
        assert await cache.get("Token0" + "0" * 38) is None
        assert await cache.get("Token1" + "0" * 38) is not None
        assert await cache.get("Token2" + "0" * 38) is not None

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self):
        """Test accessing entry moves it to end of LRU."""
        cache = TokenCache(max_size=2)

        # Add two tokens
        token1 = TokenCharacteristics(
            token_address="Token1" + "0" * 38,
            source=TokenSource.DEXSCREENER,
        )
        token2 = TokenCharacteristics(
            token_address="Token2" + "0" * 38,
            source=TokenSource.DEXSCREENER,
        )

        await cache.set(token1)
        await cache.set(token2)

        # Access token1 - moves it to end
        await cache.get(token1.token_address)

        # Add token3 - should evict token2 (now oldest)
        token3 = TokenCharacteristics(
            token_address="Token3" + "0" * 38,
            source=TokenSource.DEXSCREENER,
        )
        await cache.set(token3)

        # token1 should still exist (accessed recently)
        assert await cache.get(token1.token_address) is not None
        # token2 should be evicted
        assert await cache.get(token2.token_address) is None
        # token3 should exist
        assert await cache.get(token3.token_address) is not None


class TestTokenCacheStats:
    """Cache statistics tests."""

    @pytest.mark.asyncio
    async def test_initial_stats(self):
        """Test initial cache stats."""
        cache = TokenCache(max_size=100, ttl_seconds=300)
        stats = cache.get_stats()

        assert stats["size"] == 0
        assert stats["max_size"] == 100
        assert stats["ttl_seconds"] == 300
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_stats_after_operations(self, sample_token: TokenCharacteristics):
        """Test stats after cache operations."""
        cache = TokenCache()

        # Miss
        await cache.get("nonexistent")

        # Set and hit
        await cache.set(sample_token)
        await cache.get(sample_token.token_address)

        stats = cache.get_stats()

        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    @pytest.mark.asyncio
    async def test_stats_reset_on_clear(self, sample_token: TokenCharacteristics):
        """Test stats reset when cache is cleared."""
        cache = TokenCache()
        await cache.set(sample_token)
        await cache.get(sample_token.token_address)

        await cache.clear()

        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
