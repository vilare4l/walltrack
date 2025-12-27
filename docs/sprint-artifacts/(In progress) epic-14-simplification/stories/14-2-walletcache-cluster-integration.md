# Story 14.2: WalletCache Cluster Integration

## Story Info
- **Epic**: Epic 14 - System Simplification & Automation
- **Status**: ready-for-dev
- **Priority**: P0 - Critical
- **Story Points**: 3
- **Depends on**: None
- **Blocks**: Story 14-3, Story 14-4

## User Story

**As a** system operator,
**I want** the WalletCache to properly load and track cluster membership data,
**So that** signal scoring actually uses cluster amplification instead of always returning the solo_signal_base value.

## Background

**Critical Bug:** The current `WalletCache` has `cluster_id = None` for all wallets because cluster data from Neo4j is never loaded into the cache. This means:
- The `cluster_score` factor (25% of total) always returns `solo_signal_base = 0.50`
- All the clustering work in Neo4j is **wasted**
- Cluster leaders get no bonus
- Cluster amplification is never applied

**Code References:**
```python
# wallet_cache.py:73-74 (current bug)
cluster_id=None,  # TODO: Add cluster integration in Epic 2
is_leader=False,

# wallet_cache.py:149 (current bug)
cluster_id=None,  # TODO: Add cluster integration
```

## Acceptance Criteria

### AC 1: Cluster Membership Loading on Initialization
**Given** the WalletCache is being initialized
**When** `initialize()` is called
**Then** cluster memberships are loaded from Neo4j
**And** each cached wallet has its `cluster_id` populated (if in a cluster)
**And** each cached wallet has its `is_leader` flag set correctly
**And** initialization completes without blocking on Neo4j errors

### AC 2: Leader Flag Accuracy
**Given** a cluster exists with wallet A as leader
**When** the WalletCache is initialized
**Then** wallet A has `is_leader = True`
**And** other cluster members have `is_leader = False`
**And** wallets not in any cluster have `is_leader = False`

### AC 3: Cache Update Method
**Given** a new cluster is formed with members [A, B, C] and leader A
**When** `update_cluster_for_members()` is called
**Then** all three wallets in cache have `cluster_id` set to the new cluster ID
**And** wallet A has `is_leader = True`
**And** wallets B and C have `is_leader = False`
**And** the update is O(1) per wallet (direct dict access)

### AC 4: Signal Processing Uses Cluster Data
**Given** a wallet in a cluster sends a signal
**When** the signal is processed by SignalScorer
**Then** the wallet's `cluster_id` is available (not None)
**And** the cluster amplification factor is applied
**And** log output shows the cluster_id being used

### AC 5: Graceful Neo4j Failure
**Given** Neo4j is unavailable during initialization
**When** the WalletCache tries to load cluster memberships
**Then** initialization completes without crashing
**And** wallets have `cluster_id = None` as fallback
**And** a warning is logged about Neo4j unavailability

## Technical Specifications

### Modified: WalletCache.initialize()

**src/walltrack/services/signal/wallet_cache.py:**
```python
class WalletCache:
    def __init__(self, db_pool, neo4j_client: Neo4jClient):
        self._pool = db_pool
        self._neo4j = neo4j_client
        self._cache: dict[str, WalletCacheEntry] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Load initial wallet data from database."""
        # ... existing code to load from PostgreSQL ...

        # NEW: Load cluster memberships from Neo4j
        try:
            cluster_memberships = await self._load_cluster_memberships()
            for wallet_address, cluster_id, is_leader in cluster_memberships:
                if wallet_address in self._cache:
                    self._cache[wallet_address].cluster_id = cluster_id
                    self._cache[wallet_address].is_leader = is_leader
            logger.info(f"Loaded {len(cluster_memberships)} cluster memberships")
        except Exception as e:
            logger.warning(f"Failed to load cluster memberships from Neo4j: {e}")
            # Continue without cluster data - graceful degradation

        self._initialized = True

    async def _load_cluster_memberships(self) -> list[tuple[str, str, bool]]:
        """Load wallet->cluster mappings from Neo4j."""
        query = """
        MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster)
        RETURN w.address as wallet,
               c.id as cluster_id,
               CASE WHEN c.leader_address = w.address
                    THEN true ELSE false END as is_leader
        """
        results = await self._neo4j.execute_query(query)
        return [(r["wallet"], r["cluster_id"], r["is_leader"]) for r in results]
```

### New Method: update_cluster_for_members()

```python
    async def update_cluster_for_members(
        self,
        cluster_id: str,
        member_addresses: list[str],
        leader_address: str | None = None
    ) -> int:
        """
        Update cluster_id for all cluster members.

        Args:
            cluster_id: The cluster ID to set
            member_addresses: List of wallet addresses in the cluster
            leader_address: Address of the cluster leader (optional)

        Returns:
            Number of wallets updated in cache
        """
        updated_count = 0
        for address in member_addresses:
            if address in self._cache:
                entry = self._cache[address]
                entry.cluster_id = cluster_id
                entry.is_leader = (address == leader_address)
                updated_count += 1

        logger.info(
            f"Updated cluster {cluster_id} for {updated_count}/{len(member_addresses)} "
            f"cached wallets (leader: {leader_address})"
        )
        return updated_count
```

### Modified: WalletCacheEntry

Verify the model supports cluster fields (should already exist but verify):
```python
@dataclass
class WalletCacheEntry:
    address: str
    status: WalletStatus
    score: float
    win_rate: float
    avg_pnl: float
    last_active: datetime
    cluster_id: str | None = None  # <- Must be populated
    is_leader: bool = False        # <- Must be populated
    # ... other fields
```

### Integration Point: SignalScorer

Verify SignalScorer uses cluster data from WalletCache:
```python
# In signal_scorer.py - should already work once cache is fixed
async def _calculate_cluster_score(self, wallet: WalletCacheEntry) -> float:
    if wallet.cluster_id is None:
        return self.config.solo_signal_base  # 0.50 for solo wallets

    # Get cluster info and calculate amplification
    cluster = await self._get_cluster(wallet.cluster_id)
    if cluster is None:
        return self.config.solo_signal_base

    # Apply amplification
    return cluster.amplification_factor
```

## Implementation Tasks

- [ ] Add `neo4j_client` parameter to WalletCache `__init__`
- [ ] Implement `_load_cluster_memberships()` method
- [ ] Modify `initialize()` to call cluster loading
- [ ] Add try/except for graceful Neo4j failure
- [ ] Implement `update_cluster_for_members()` method
- [ ] Verify WalletCacheEntry has cluster_id and is_leader fields
- [ ] Add logging for cluster data loading
- [ ] Update WalletCache instantiation in dependency injection
- [ ] Write unit tests for cluster loading
- [ ] Write unit tests for cache update method
- [ ] Write integration test verifying signal scoring uses cluster_id
- [ ] Run `uv run pytest` - verify all tests pass
- [ ] Run `uv run mypy src/` - verify no type errors

## Definition of Done

- [ ] `cluster_id` is populated from Neo4j on cache initialization
- [ ] `is_leader` flag is correctly set for cluster leaders
- [ ] Cache can be updated when new clusters are formed
- [ ] Signal scoring receives correct cluster context
- [ ] Graceful degradation when Neo4j is unavailable
- [ ] All tests pass
- [ ] No type errors

## Test Cases

```python
# tests/unit/services/signal/test_wallet_cache_cluster.py

import pytest
from unittest.mock import AsyncMock, MagicMock
from walltrack.services.signal.wallet_cache import WalletCache, WalletCacheEntry


class TestWalletCacheClusterIntegration:
    """Test cluster data loading in WalletCache."""

    @pytest.fixture
    def mock_neo4j(self):
        """Mock Neo4j client."""
        client = AsyncMock()
        client.execute_query = AsyncMock(return_value=[
            {"wallet": "wallet_A", "cluster_id": "cluster_1", "is_leader": True},
            {"wallet": "wallet_B", "cluster_id": "cluster_1", "is_leader": False},
            {"wallet": "wallet_C", "cluster_id": "cluster_1", "is_leader": False},
        ])
        return client

    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool."""
        pool = AsyncMock()
        # Return some wallets from PostgreSQL
        pool.fetch = AsyncMock(return_value=[
            {"address": "wallet_A", "status": "active", "score": 0.8},
            {"address": "wallet_B", "status": "active", "score": 0.7},
            {"address": "wallet_C", "status": "active", "score": 0.6},
            {"address": "wallet_D", "status": "active", "score": 0.5},  # Not in cluster
        ])
        return pool

    async def test_initialize_loads_cluster_memberships(
        self, mock_db_pool, mock_neo4j
    ):
        """Cluster memberships are loaded on initialization."""
        cache = WalletCache(mock_db_pool, mock_neo4j)
        await cache.initialize()

        # Verify cluster data loaded
        assert cache.get("wallet_A").cluster_id == "cluster_1"
        assert cache.get("wallet_A").is_leader is True
        assert cache.get("wallet_B").cluster_id == "cluster_1"
        assert cache.get("wallet_B").is_leader is False
        assert cache.get("wallet_D").cluster_id is None  # Not in cluster

    async def test_initialize_graceful_neo4j_failure(
        self, mock_db_pool, mock_neo4j
    ):
        """Initialization continues if Neo4j fails."""
        mock_neo4j.execute_query = AsyncMock(
            side_effect=Exception("Neo4j connection failed")
        )

        cache = WalletCache(mock_db_pool, mock_neo4j)
        await cache.initialize()  # Should not raise

        # Wallets loaded from PostgreSQL, cluster_id is None
        assert cache.get("wallet_A") is not None
        assert cache.get("wallet_A").cluster_id is None

    async def test_update_cluster_for_members(self, mock_db_pool, mock_neo4j):
        """Cache can be updated with new cluster data."""
        cache = WalletCache(mock_db_pool, mock_neo4j)
        await cache.initialize()

        # Form a new cluster
        updated = await cache.update_cluster_for_members(
            cluster_id="cluster_2",
            member_addresses=["wallet_D", "wallet_E"],  # wallet_E not in cache
            leader_address="wallet_D"
        )

        assert updated == 1  # Only wallet_D was in cache
        assert cache.get("wallet_D").cluster_id == "cluster_2"
        assert cache.get("wallet_D").is_leader is True


class TestClusterLeaderDetection:
    """Test leader flag accuracy."""

    async def test_only_leader_has_flag(self, mock_db_pool, mock_neo4j):
        """Only the cluster leader has is_leader=True."""
        cache = WalletCache(mock_db_pool, mock_neo4j)
        await cache.initialize()

        leader_count = sum(
            1 for addr in ["wallet_A", "wallet_B", "wallet_C"]
            if cache.get(addr).is_leader
        )
        assert leader_count == 1
        assert cache.get("wallet_A").is_leader is True
```

## File List

### New Files
- `tests/unit/services/signal/test_wallet_cache_cluster.py`

### Modified Files
- `src/walltrack/services/signal/wallet_cache.py` - Add cluster loading and update methods
- `src/walltrack/services/signal/__init__.py` - Update exports if needed
- `src/walltrack/api/dependencies.py` - Pass neo4j_client to WalletCache (if not already)
