"""Unit tests for wallet cache service.

Epic 14 Story 14-5: Updated to remove cluster caching tests.
Cluster data is now fetched via ClusterService.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.signal.wallet_cache import WalletCache


@pytest.fixture
def mock_wallet_repo() -> MagicMock:
    """Create mock wallet repository."""
    repo = MagicMock()
    repo.get_active_wallets = AsyncMock(return_value=[])
    repo.get_by_status = AsyncMock(return_value=[])
    repo.get_by_address = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def wallet_cache(mock_wallet_repo: MagicMock) -> WalletCache:
    """Create wallet cache with mock repo."""
    return WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)


class TestWalletCacheInitialization:
    """Tests for WalletCache initialization."""

    @pytest.mark.asyncio
    async def test_initialize_empty(self, wallet_cache: WalletCache):
        """Test initialization with no wallets."""
        await wallet_cache.initialize()

        assert wallet_cache._initialized is True
        assert len(wallet_cache._monitored_set) == 0
        assert len(wallet_cache._blacklist_set) == 0
        assert len(wallet_cache._cache) == 0

    @pytest.mark.asyncio
    async def test_initialize_with_monitored_wallets(self, mock_wallet_repo: MagicMock):
        """Test initialization with monitored wallets."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        assert cache._initialized is True
        assert "wallet123" in cache._monitored_set
        assert "wallet123" in cache._cache
        assert cache._cache["wallet123"].is_monitored is True
        assert cache._cache["wallet123"].reputation_score == 0.8

    @pytest.mark.asyncio
    async def test_initialize_with_blacklisted_wallets(self, mock_wallet_repo: MagicMock):
        """Test initialization with blacklisted wallets."""
        blacklisted_wallet = MagicMock()
        blacklisted_wallet.address = "blacklisted123"

        mock_wallet_repo.get_by_status.return_value = [blacklisted_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        assert "blacklisted123" in cache._blacklist_set

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, wallet_cache: WalletCache, mock_wallet_repo: MagicMock):
        """Test that initialize is idempotent."""
        await wallet_cache.initialize()
        await wallet_cache.initialize()

        # Should only call repository once
        mock_wallet_repo.get_active_wallets.assert_called_once()

    @pytest.mark.asyncio
    async def test_initialize_marks_blacklisted_in_cache(self, mock_wallet_repo: MagicMock):
        """Test monitored wallet that is also blacklisted."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.7

        blacklisted_wallet = MagicMock()
        blacklisted_wallet.address = "wallet123"  # Same wallet

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]
        mock_wallet_repo.get_by_status.return_value = [blacklisted_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        # Should be in both sets and cache entry should reflect blacklisted status
        assert "wallet123" in cache._monitored_set
        assert "wallet123" in cache._blacklist_set
        assert cache._cache["wallet123"].is_blacklisted is True


class TestWalletCacheGet:
    """Tests for WalletCache.get method."""

    @pytest.mark.asyncio
    async def test_get_monitored_wallet_cache_hit(self, mock_wallet_repo: MagicMock):
        """Test getting monitored wallet from cache."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        entry, cache_hit = await cache.get("wallet123")

        assert entry is not None
        assert entry.wallet_address == "wallet123"
        assert entry.is_monitored is True
        assert cache_hit is True

    @pytest.mark.asyncio
    async def test_get_non_monitored_wallet(self, wallet_cache: WalletCache):
        """Test getting non-monitored wallet."""
        await wallet_cache.initialize()

        entry, cache_hit = await wallet_cache.get("unknown_wallet")

        assert entry is not None
        assert entry.wallet_address == "unknown_wallet"
        assert entry.is_monitored is False
        assert cache_hit is False

    @pytest.mark.asyncio
    async def test_get_blacklisted_wallet(self, mock_wallet_repo: MagicMock):
        """Test getting blacklisted wallet."""
        blacklisted_wallet = MagicMock()
        blacklisted_wallet.address = "blacklisted123"

        mock_wallet_repo.get_by_status.return_value = [blacklisted_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        entry, _ = await cache.get("blacklisted123")

        assert entry is not None
        assert entry.is_blacklisted is True

    @pytest.mark.asyncio
    async def test_get_auto_initializes(self, wallet_cache: WalletCache, mock_wallet_repo: MagicMock):
        """Test that get() auto-initializes cache if needed."""
        assert wallet_cache._initialized is False

        await wallet_cache.get("wallet123")

        assert wallet_cache._initialized is True
        mock_wallet_repo.get_active_wallets.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_monitored_not_in_cache(self, mock_wallet_repo: MagicMock):
        """Test getting monitored wallet not yet in cache."""
        # Start with empty cache but wallet in monitored set
        mock_wallet_repo.get_active_wallets.return_value = []
        mock_wallet_repo.get_by_status.return_value = []

        db_wallet = MagicMock()
        db_wallet.score = 0.75
        mock_wallet_repo.get_by_address.return_value = db_wallet

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        # Manually add to monitored set to simulate new wallet
        cache._monitored_set.add("new_wallet")

        entry, cache_hit = await cache.get("new_wallet")

        assert entry is not None
        assert entry.is_monitored is True
        assert entry.reputation_score == 0.75
        assert cache_hit is False
        # Should now be in cache
        assert "new_wallet" in cache._cache


class TestWalletCacheLRU:
    """Tests for WalletCache LRU eviction."""

    @pytest.mark.asyncio
    async def test_lru_eviction(self, mock_wallet_repo: MagicMock):
        """Test LRU eviction when cache is full."""
        mock_wallet_repo.get_active_wallets.return_value = []
        mock_wallet_repo.get_by_status.return_value = []
        mock_wallet_repo.get_by_address.return_value = MagicMock(score=0.5)

        cache = WalletCache(mock_wallet_repo, max_size=2, ttl_seconds=300)
        await cache.initialize()

        # Add to monitored set
        cache._monitored_set = {"w1", "w2", "w3"}

        # Fill cache
        await cache.get("w1")
        await cache.get("w2")

        assert len(cache._cache) == 2
        assert "w1" in cache._cache
        assert "w2" in cache._cache

        # Add third - should evict oldest (w1)
        await cache.get("w3")

        assert len(cache._cache) == 2
        assert "w1" not in cache._cache  # Evicted
        assert "w2" in cache._cache
        assert "w3" in cache._cache

    @pytest.mark.asyncio
    async def test_lru_access_updates_order(self, mock_wallet_repo: MagicMock):
        """Test that accessing an entry moves it to end of LRU."""
        mock_wallet_repo.get_active_wallets.return_value = []
        mock_wallet_repo.get_by_status.return_value = []
        mock_wallet_repo.get_by_address.return_value = MagicMock(score=0.5)

        cache = WalletCache(mock_wallet_repo, max_size=2, ttl_seconds=300)
        await cache.initialize()

        cache._monitored_set = {"w1", "w2", "w3"}

        # Fill cache: w1, then w2
        await cache.get("w1")
        await cache.get("w2")

        # Access w1 again - moves it to end
        await cache.get("w1")

        # Add w3 - should evict w2 (now oldest)
        await cache.get("w3")

        assert "w1" in cache._cache  # Not evicted - was accessed recently
        assert "w2" not in cache._cache  # Evicted
        assert "w3" in cache._cache


class TestWalletCacheExpiration:
    """Tests for WalletCache entry expiration."""

    @pytest.mark.asyncio
    async def test_expired_entry_refreshed(self, mock_wallet_repo: MagicMock):
        """Test that expired entries are refreshed."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        db_wallet = MagicMock()
        db_wallet.score = 0.9  # Updated score

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]
        mock_wallet_repo.get_by_status.return_value = []
        mock_wallet_repo.get_by_address.return_value = db_wallet

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=1)  # 1 second TTL
        await cache.initialize()

        # First access
        entry, _ = await cache.get("wallet123")
        assert entry.reputation_score == 0.8

        # Manually expire the entry
        cache._cache["wallet123"].cached_at = datetime.now(UTC) - timedelta(seconds=10)

        # Access again - should refresh
        entry, _ = await cache.get("wallet123")
        assert entry.reputation_score == 0.9
        mock_wallet_repo.get_by_address.assert_called()


class TestWalletCacheInvalidation:
    """Tests for WalletCache invalidation."""

    @pytest.mark.asyncio
    async def test_invalidate_entry(self, mock_wallet_repo: MagicMock):
        """Test invalidating a cache entry."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        assert "wallet123" in cache._cache

        await cache.invalidate("wallet123")

        assert "wallet123" not in cache._cache

    @pytest.mark.asyncio
    async def test_invalidate_nonexistent_entry(self, wallet_cache: WalletCache):
        """Test invalidating entry that doesn't exist."""
        await wallet_cache.initialize()

        # Should not raise
        await wallet_cache.invalidate("nonexistent")


class TestWalletCacheRefresh:
    """Tests for WalletCache set refresh."""

    @pytest.mark.asyncio
    async def test_refresh_sets(self, mock_wallet_repo: MagicMock):
        """Test refreshing monitored and blacklist sets."""
        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        # Set up new data for refresh
        new_monitored = MagicMock()
        new_monitored.address = "new_wallet"

        new_blacklisted = MagicMock()
        new_blacklisted.address = "new_blacklisted"

        mock_wallet_repo.get_active_wallets.return_value = [new_monitored]
        mock_wallet_repo.get_by_status.return_value = [new_blacklisted]

        await cache.refresh_sets()

        assert "new_wallet" in cache._monitored_set
        assert "new_blacklisted" in cache._blacklist_set


class TestWalletCacheNoClusterData:
    """Tests confirming cluster data is not cached.

    Epic 14 Story 14-5: Cluster data removed from WalletCache.
    Use ClusterService for cluster info instead.
    """

    @pytest.mark.asyncio
    async def test_cache_entry_has_no_cluster_fields(self, mock_wallet_repo: MagicMock):
        """Cache entries do not have cluster_id or is_leader fields."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]

        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        entry = cache._cache["wallet123"]

        # These fields should not exist on the model
        assert not hasattr(entry, "cluster_id")
        assert not hasattr(entry, "is_leader")

    @pytest.mark.asyncio
    async def test_cache_init_does_not_require_neo4j(self, mock_wallet_repo: MagicMock):
        """Cache can be initialized without Neo4j client."""
        monitored_wallet = MagicMock()
        monitored_wallet.address = "wallet123"
        monitored_wallet.score = 0.8

        mock_wallet_repo.get_active_wallets.return_value = [monitored_wallet]

        # No neo4j parameter needed
        cache = WalletCache(mock_wallet_repo, max_size=100, ttl_seconds=300)
        await cache.initialize()

        assert cache._initialized is True
        assert "wallet123" in cache._cache
