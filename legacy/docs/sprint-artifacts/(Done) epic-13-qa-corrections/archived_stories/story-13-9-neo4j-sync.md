# Story 13-9: Add Neo4j Bidirectional Sync

## Priority: HIGH

## Problem Statement

Currently Neo4j sync is one-directional:
- Wallet discovery -> Neo4j (works)
- Postgres wallet updates -> Neo4j (NOT synced)
- Cluster data -> Postgres (NOT synced - clusters only in Neo4j)

## Evidence

**WalletDiscoveryScanner (`scanner.py`):**
```python
# Creates wallet in both Supabase AND Neo4j
await self.wallet_repo.create(wallet)  # Supabase
await self.wallet_queries.create_or_update_wallet(wallet)  # Neo4j
```

**WalletProfiler (updates scores):**
```python
# Only updates Supabase, NOT Neo4j
await self.wallet_repo.update(wallet)
# Neo4j wallet node has stale score!
```

**ClusterGrouper:**
```python
# Creates clusters in Neo4j only
await self.cluster_queries.create_cluster(...)
# No Postgres backup for cluster data!
```

## Impact

1. Neo4j wallet scores become stale after profiling
2. DecayDetector changes don't reflect in Neo4j
3. If Neo4j is reset, all cluster data is lost
4. Signal amplification uses outdated wallet scores

## Solution

### Part 1: Sync Wallet Updates to Neo4j

**Create: `src/walltrack/services/wallet/sync_service.py`**

```python
"""Wallet sync service for Neo4j bidirectional sync."""

import structlog
from walltrack.data.neo4j.client import get_neo4j_client
from walltrack.data.neo4j.queries.wallet import WalletQueries
from walltrack.models.wallet import Wallet

logger = structlog.get_logger(__name__)


class WalletSyncService:
    """Syncs wallet updates to Neo4j."""

    def __init__(self):
        self._neo4j_client = None
        self._wallet_queries = None

    async def _get_queries(self) -> WalletQueries:
        if self._wallet_queries is None:
            self._neo4j_client = await get_neo4j_client()
            self._wallet_queries = WalletQueries(self._neo4j_client)
        return self._wallet_queries

    async def sync_wallet_update(self, wallet: Wallet) -> None:
        """Sync wallet score/status updates to Neo4j."""
        try:
            queries = await self._get_queries()
            await queries.create_or_update_wallet(
                address=wallet.address,
                score=wallet.wallet_score,
                status=wallet.status,
                win_rate=wallet.metrics.win_rate if wallet.metrics else None,
                total_pnl=wallet.metrics.total_pnl_sol if wallet.metrics else None,
            )
            logger.debug("wallet_synced_to_neo4j", address=wallet.address[:8])
        except Exception as e:
            logger.warning(
                "wallet_neo4j_sync_failed",
                address=wallet.address[:8],
                error=str(e),
            )

    async def sync_wallet_status(
        self,
        address: str,
        status: str,
    ) -> None:
        """Sync status change (blacklist, decay, etc.) to Neo4j."""
        try:
            queries = await self._get_queries()
            await queries.update_wallet_status(address, status)
            logger.debug("wallet_status_synced", address=address[:8], status=status)
        except Exception as e:
            logger.warning(
                "wallet_status_sync_failed",
                address=address[:8],
                error=str(e),
            )


_sync_service: WalletSyncService | None = None


async def get_wallet_sync_service() -> WalletSyncService:
    global _sync_service
    if _sync_service is None:
        _sync_service = WalletSyncService()
    return _sync_service
```

**Update: `src/walltrack/services/wallet/profiler.py`**

```python
# After updating wallet in Supabase:
await self.wallet_repo.update(wallet)

# Add Neo4j sync:
from walltrack.services.wallet.sync_service import get_wallet_sync_service
sync_svc = await get_wallet_sync_service()
await sync_svc.sync_wallet_update(wallet)
```

**Update: `src/walltrack/services/wallet/decay_detector.py`**

```python
# After updating wallet status:
await self.wallet_repo.update_status(address, "in_decay")

# Add Neo4j sync:
from walltrack.services.wallet.sync_service import get_wallet_sync_service
sync_svc = await get_wallet_sync_service()
await sync_svc.sync_wallet_status(address, "in_decay")
```

### Part 2: Backup Clusters to Postgres

**Create migration: `V16__cluster_backup.sql`**

```sql
-- Cluster backup table for disaster recovery
CREATE TABLE IF NOT EXISTS walltrack.cluster_snapshots (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    leader_address TEXT,
    size INTEGER NOT NULL,
    cohesion_score DECIMAL(5, 4),
    signal_multiplier DECIMAL(5, 2),
    member_addresses TEXT[] NOT NULL,
    relationship_data JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cluster_snapshots_leader
    ON walltrack.cluster_snapshots(leader_address);
```

**Update: `src/walltrack/core/cluster/grouping.py`**

```python
async def _create_cluster(self, members: list[str], name: str) -> str:
    # Create in Neo4j
    cluster_id = await self.cluster_queries.create_cluster(
        name=name,
        member_addresses=members,
    )

    # Backup to Postgres
    await self._backup_cluster_to_postgres(cluster_id, name, members)

    return cluster_id

async def _backup_cluster_to_postgres(
    self,
    cluster_id: str,
    name: str,
    members: list[str],
) -> None:
    """Backup cluster to Postgres for disaster recovery."""
    try:
        from walltrack.data.supabase.client import get_supabase_client
        client = await get_supabase_client()

        await client.table("cluster_snapshots").upsert({
            "id": cluster_id,
            "name": name,
            "member_addresses": members,
            "size": len(members),
            "synced_at": datetime.now(UTC).isoformat(),
        }).execute()

        logger.debug("cluster_backed_up", cluster_id=cluster_id[:8])
    except Exception as e:
        logger.warning("cluster_backup_failed", cluster_id=cluster_id[:8], error=str(e))
```

## Acceptance Criteria

- [ ] WalletSyncService created
- [ ] WalletProfiler syncs updates to Neo4j
- [ ] DecayDetector syncs status changes to Neo4j
- [ ] BlacklistService syncs status changes to Neo4j
- [ ] cluster_snapshots table created
- [ ] ClusterGrouper backs up clusters to Postgres
- [ ] Sync failures don't break main operations (graceful degradation)

## Files to Create/Modify

- CREATE: `src/walltrack/services/wallet/sync_service.py`
- CREATE: `migrations/V16__cluster_backup.sql`
- MODIFY: `src/walltrack/services/wallet/profiler.py`
- MODIFY: `src/walltrack/services/wallet/decay_detector.py`
- MODIFY: `src/walltrack/services/wallet/blacklist_service.py`
- MODIFY: `src/walltrack/core/cluster/grouping.py`

## Testing

```python
async def test_wallet_update_syncs_to_neo4j():
    # Update wallet score in Supabase
    await profiler.profile_wallet(address)

    # Verify Neo4j has updated score
    wallet_queries = WalletQueries(neo4j_client)
    neo4j_wallet = await wallet_queries.get_wallet(address)
    assert neo4j_wallet.score == expected_score

async def test_cluster_backed_up_to_postgres():
    # Create cluster
    cluster_id = await grouper.find_clusters()

    # Verify Postgres backup exists
    client = await get_supabase_client()
    result = await client.table("cluster_snapshots").select("*").eq("id", cluster_id).execute()
    assert len(result.data) == 1
```

## Estimated Effort

3-4 hours

## Risk

- Neo4j sync failures should not block main operations
- All sync operations wrapped in try/except
- Logging for debugging sync issues
