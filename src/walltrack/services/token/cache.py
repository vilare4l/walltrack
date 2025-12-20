"""In-memory LRU cache for token characteristics."""

import asyncio
from collections import OrderedDict
from datetime import UTC, datetime

import structlog

from walltrack.constants.token import (
    TOKEN_CACHE_MAX_SIZE,
    TOKEN_CACHE_TTL_SECONDS,
)
from walltrack.models.token import TokenCharacteristics, TokenSource

logger = structlog.get_logger(__name__)


class TokenCache:
    """In-memory LRU cache for token characteristics."""

    def __init__(
        self,
        max_size: int = TOKEN_CACHE_MAX_SIZE,
        ttl_seconds: int = TOKEN_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize token cache.

        Args:
            max_size: Maximum cache entries
            ttl_seconds: Cache entry TTL
        """
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, TokenCharacteristics] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, token_address: str) -> TokenCharacteristics | None:
        """Get token from cache if valid.

        Args:
            token_address: Token mint address

        Returns:
            TokenCharacteristics if cached and valid, None otherwise
        """
        async with self._lock:
            if token_address not in self._cache:
                self._misses += 1
                return None

            token = self._cache[token_address]

            # Check TTL - return None but keep entry for stale fallback
            if not token.is_cache_valid():
                self._misses += 1
                return None

            # Move to end for LRU
            self._cache.move_to_end(token_address)
            self._hits += 1

            # Create copy with CACHE source to indicate cache hit
            token_copy = token.model_copy()
            token_copy.source = TokenSource.CACHE
            return token_copy

    async def set(self, token: TokenCharacteristics) -> None:
        """Store token in cache.

        Args:
            token: Token characteristics to cache
        """
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            # Update TTL and store
            token.cache_ttl_seconds = self.ttl_seconds
            token.fetched_at = datetime.now(UTC)
            self._cache[token.token_address] = token

    async def invalidate(self, token_address: str) -> None:
        """Remove token from cache.

        Args:
            token_address: Token mint address to invalidate
        """
        async with self._lock:
            self._cache.pop(token_address, None)

    async def clear(self) -> None:
        """Clear entire cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> dict:
        """Get cache statistics.

        Returns:
            dict with cache stats
        """
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }

    def get_stale(self, token_address: str) -> TokenCharacteristics | None:
        """Get potentially stale cache entry for fallback.

        This bypasses TTL check for use when all API sources fail.

        Args:
            token_address: Token mint address

        Returns:
            TokenCharacteristics if in cache (even expired), None otherwise
        """
        return self._cache.get(token_address)
