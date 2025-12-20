"""In-memory LRU cache for monitored wallet lookups."""

import asyncio
from collections import OrderedDict

import structlog

from walltrack.constants.signal_filter import (
    WALLET_CACHE_MAX_SIZE,
    WALLET_CACHE_TTL_SECONDS,
)
from walltrack.data.models.wallet import WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.models.signal_filter import WalletCacheEntry

logger = structlog.get_logger(__name__)


class WalletCache:
    """
    In-memory LRU cache for monitored wallet lookups.

    Provides O(1) lookups to meet < 50ms requirement.
    """

    def __init__(
        self,
        wallet_repo: WalletRepository,
        max_size: int = WALLET_CACHE_MAX_SIZE,
        ttl_seconds: int = WALLET_CACHE_TTL_SECONDS,
    ) -> None:
        """Initialize wallet cache.

        Args:
            wallet_repo: Wallet repository for database queries
            max_size: Maximum cache entries
            ttl_seconds: Cache entry TTL
        """
        self.wallet_repo = wallet_repo
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, WalletCacheEntry] = OrderedDict()
        self._monitored_set: set[str] = set()  # Fast O(1) membership check
        self._blacklist_set: set[str] = set()  # Fast O(1) blacklist check
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Load initial wallet data from database."""
        async with self._lock:
            if self._initialized:
                return

            try:
                # Load active (monitored) wallets
                active_wallets = await self.wallet_repo.get_active_wallets(
                    min_score=0.0, limit=self.max_size
                )
                self._monitored_set = {w.address for w in active_wallets}

                # Load blacklisted wallets
                blacklisted = await self.wallet_repo.get_by_status(
                    WalletStatus.BLACKLISTED, limit=10000
                )
                self._blacklist_set = {w.address for w in blacklisted}

                # Pre-populate cache with wallet metadata
                for wallet in active_wallets[: self.max_size]:
                    entry = WalletCacheEntry(
                        wallet_address=wallet.address,
                        is_monitored=True,
                        is_blacklisted=wallet.address in self._blacklist_set,
                        cluster_id=None,  # TODO: Add cluster integration in Epic 2
                        is_leader=False,
                        reputation_score=wallet.score,
                        ttl_seconds=self.ttl_seconds,
                    )
                    self._cache[wallet.address] = entry

                self._initialized = True
                logger.info(
                    "wallet_cache_initialized",
                    monitored_count=len(self._monitored_set),
                    blacklist_count=len(self._blacklist_set),
                    cache_size=len(self._cache),
                )
            except Exception as e:
                logger.error("wallet_cache_init_failed", error=str(e))
                raise

    async def get(self, wallet_address: str) -> tuple[WalletCacheEntry | None, bool]:
        """
        Get wallet entry from cache.

        Args:
            wallet_address: Wallet address to lookup

        Returns:
            Tuple of (entry, cache_hit)
        """
        if not self._initialized:
            await self.initialize()

        # Fast path: check sets first (O(1))
        is_monitored = wallet_address in self._monitored_set
        is_blacklisted = wallet_address in self._blacklist_set

        # Check cache for full metadata
        if wallet_address in self._cache:
            entry = self._cache[wallet_address]

            # Check if expired
            if entry.is_expired():
                await self._refresh_entry(wallet_address)
                entry = self._cache.get(wallet_address)

            # Move to end for LRU
            if entry:
                self._cache.move_to_end(wallet_address)
                return entry, True

        # Not in cache but in monitored set - fetch and cache
        if is_monitored:
            entry = await self._fetch_and_cache(wallet_address, is_blacklisted)
            return entry, False

        # Not monitored - create minimal entry for logging
        return (
            WalletCacheEntry(
                wallet_address=wallet_address,
                is_monitored=False,
                is_blacklisted=is_blacklisted,
            ),
            False,
        )

    async def _fetch_and_cache(
        self,
        wallet_address: str,
        is_blacklisted: bool,
    ) -> WalletCacheEntry:
        """Fetch wallet from DB and add to cache."""
        wallet = await self.wallet_repo.get_by_address(wallet_address)

        entry = WalletCacheEntry(
            wallet_address=wallet_address,
            is_monitored=True,
            is_blacklisted=is_blacklisted,
            cluster_id=None,  # TODO: Add cluster integration
            is_leader=False,
            reputation_score=wallet.score if wallet else 0.5,
            ttl_seconds=self.ttl_seconds,
        )

        # Add to cache with LRU eviction
        async with self._lock:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Remove oldest
            self._cache[wallet_address] = entry

        return entry

    async def _refresh_entry(self, wallet_address: str) -> None:
        """Refresh expired cache entry."""
        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if wallet:
            entry = WalletCacheEntry(
                wallet_address=wallet_address,
                is_monitored=True,
                is_blacklisted=wallet_address in self._blacklist_set,
                cluster_id=None,
                is_leader=False,
                reputation_score=wallet.score,
                ttl_seconds=self.ttl_seconds,
            )
            self._cache[wallet_address] = entry

    async def invalidate(self, wallet_address: str) -> None:
        """Remove wallet from cache (e.g., after status change)."""
        async with self._lock:
            self._cache.pop(wallet_address, None)

    async def refresh_sets(self) -> None:
        """Refresh monitored and blacklist sets from database."""
        async with self._lock:
            active = await self.wallet_repo.get_active_wallets(
                min_score=0.0, limit=self.max_size
            )
            self._monitored_set = {w.address for w in active}

            blacklisted = await self.wallet_repo.get_by_status(
                WalletStatus.BLACKLISTED, limit=10000
            )
            self._blacklist_set = {w.address for w in blacklisted}

            logger.info(
                "wallet_sets_refreshed",
                monitored_count=len(self._monitored_set),
                blacklist_count=len(self._blacklist_set),
            )


# Singleton instance
_wallet_cache: WalletCache | None = None


async def get_wallet_cache(wallet_repo: WalletRepository) -> WalletCache:
    """Get or create wallet cache singleton."""
    global _wallet_cache
    if _wallet_cache is None:
        _wallet_cache = WalletCache(wallet_repo)
        await _wallet_cache.initialize()
    return _wallet_cache
