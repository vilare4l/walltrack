# Story 12.4: Price History - Position-Level Collection

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 8
- **Depends on**: Story 10.5-7 (Price History Infrastructure)

## User Story

**As a** the system,
**I want** stocker l'historique des prix pour chaque position,
**So that** je peux simuler des stratégies alternatives sur les trades passés.

## Acceptance Criteria

### AC 1: Price Collection for Open Positions
**Given** une position est ouverte
**When** le prix change
**Then** un snapshot est enregistré avec:
- Timestamp, Price, Position ID

### AC 2: Collection Frequency
**Given** la position dure 6 heures
**When** je regarde l'historique
**Then** j'ai des points toutes les ~1 minute (360 points)

### AC 3: Compression After 7 Days
**Given** la position est clôturée
**When** 7 jours passent
**Then** l'historique détaillé est compressé (1 point / 5 min)

### AC 4: Cleanup After 30 Days
**Given** l'historique compressé existe
**When** 30 jours passent
**Then** l'historique est supprimé (garder seulement résumé dans position)

### AC 5: Link to Token Price History
**Given** une position existe
**When** je demande l'historique
**Then** je récupère les données depuis position_price_history
**Or** je fallback sur price_history général si disponible

## Technical Specifications

### Position Price Collector

**src/walltrack/services/pricing/position_price_collector.py:**
```python
"""Position-level price history collection."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog
import asyncio

from walltrack.services.pricing.price_oracle import get_price_oracle

logger = structlog.get_logger(__name__)


class PositionPriceCollector:
    """
    Collects price history for active positions.

    Uses the PriceOracle to fetch prices and stores
    them in position_price_history table.
    """

    def __init__(
        self,
        collection_interval_seconds: int = 60,
    ):
        self.interval = collection_interval_seconds
        self._running = False
        self._client = None
        self._price_oracle = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def _get_price_oracle(self):
        """Get price oracle."""
        if self._price_oracle is None:
            self._price_oracle = await get_price_oracle()
        return self._price_oracle

    async def get_active_positions(self) -> list[dict]:
        """Get all open positions."""
        client = await self._get_client()

        result = await client.table("positions") \
            .select("id, token_address") \
            .eq("status", "open") \
            .execute()

        return result.data or []

    async def collect_price(self, position_id: str, token_address: str) -> bool:
        """Collect and store current price for a position."""
        client = await self._get_client()
        oracle = await self._get_price_oracle()

        try:
            # Get current price
            price = await oracle.get_price(token_address)
            if price is None:
                logger.warning("price_fetch_failed", token=token_address)
                return False

            # Store in position_price_history
            data = {
                "position_id": position_id,
                "token_address": token_address,
                "timestamp": datetime.utcnow().isoformat(),
                "price": str(price),
            }

            await client.table("position_price_history") \
                .insert(data) \
                .execute()

            return True

        except Exception as e:
            logger.error("price_collection_error", position=position_id, error=str(e))
            return False

    async def collect_all_positions(self) -> dict:
        """Collect prices for all active positions."""
        positions = await self.get_active_positions()

        results = {
            "total": len(positions),
            "success": 0,
            "failed": 0,
        }

        for pos in positions:
            success = await self.collect_price(pos["id"], pos["token_address"])
            if success:
                results["success"] += 1
            else:
                results["failed"] += 1

        logger.info("price_collection_complete", **results)
        return results

    async def start(self):
        """Start continuous price collection."""
        self._running = True
        logger.info("position_price_collector_started", interval=self.interval)

        while self._running:
            try:
                await self.collect_all_positions()
            except Exception as e:
                logger.error("collection_loop_error", error=str(e))

            await asyncio.sleep(self.interval)

    def stop(self):
        """Stop price collection."""
        self._running = False
        logger.info("position_price_collector_stopped")


class PriceHistoryCompressor:
    """
    Compresses and cleans up old price history.

    - After 7 days: compress to 5-minute intervals
    - After 30 days: delete (keep summary in position)
    """

    def __init__(self):
        self._client = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def compress_old_history(self, days_old: int = 7) -> int:
        """
        Compress history older than N days to 5-minute intervals.

        Returns number of rows deleted.
        """
        client = await self._get_client()
        cutoff = datetime.utcnow() - timedelta(days=days_old)

        # Get positions with old closed trades
        positions_result = await client.table("positions") \
            .select("id") \
            .eq("status", "closed") \
            .lt("exit_time", cutoff.isoformat()) \
            .execute()

        if not positions_result.data:
            return 0

        position_ids = [p["id"] for p in positions_result.data]
        total_deleted = 0

        for pos_id in position_ids:
            deleted = await self._compress_position_history(pos_id)
            total_deleted += deleted

        logger.info("history_compression_complete", positions=len(position_ids), deleted=total_deleted)
        return total_deleted

    async def _compress_position_history(self, position_id: str) -> int:
        """Compress history for a single position to 5-minute intervals."""
        client = await self._get_client()

        # Get all history for position
        result = await client.table("position_price_history") \
            .select("*") \
            .eq("position_id", position_id) \
            .order("timestamp") \
            .execute()

        if not result.data or len(result.data) <= 1:
            return 0

        history = result.data

        # Keep one point per 5 minutes
        kept_timestamps = set()
        to_delete = []

        for row in history:
            ts = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
            bucket = ts.replace(minute=(ts.minute // 5) * 5, second=0, microsecond=0)
            bucket_key = bucket.isoformat()

            if bucket_key in kept_timestamps:
                to_delete.append(row["id"])
            else:
                kept_timestamps.add(bucket_key)

        # Delete excess rows
        if to_delete:
            for batch in [to_delete[i:i+100] for i in range(0, len(to_delete), 100)]:
                await client.table("position_price_history") \
                    .delete() \
                    .in_("id", batch) \
                    .execute()

        return len(to_delete)

    async def cleanup_old_history(self, days_old: int = 30) -> int:
        """
        Delete history older than N days completely.

        Before deletion, ensure summary is stored in position.
        """
        client = await self._get_client()
        cutoff = datetime.utcnow() - timedelta(days=days_old)

        # Get positions with very old closed trades
        positions_result = await client.table("positions") \
            .select("id, token_address") \
            .eq("status", "closed") \
            .lt("exit_time", cutoff.isoformat()) \
            .execute()

        if not positions_result.data:
            return 0

        total_deleted = 0

        for pos in positions_result.data:
            # Store summary before deletion
            await self._store_summary(pos["id"])

            # Delete history
            result = await client.table("position_price_history") \
                .delete() \
                .eq("position_id", pos["id"]) \
                .execute()

            total_deleted += len(result.data) if result.data else 0

        logger.info("history_cleanup_complete", positions=len(positions_result.data), deleted=total_deleted)
        return total_deleted

    async def _store_summary(self, position_id: str):
        """Store price summary in position before deleting history."""
        client = await self._get_client()

        # Get min/max/avg from history
        result = await client.table("position_price_history") \
            .select("price") \
            .eq("position_id", position_id) \
            .execute()

        if not result.data:
            return

        prices = [Decimal(str(r["price"])) for r in result.data]

        summary = {
            "price_summary": {
                "min_price": str(min(prices)),
                "max_price": str(max(prices)),
                "avg_price": str(sum(prices) / len(prices)),
                "data_points": len(prices),
            }
        }

        await client.table("positions") \
            .update(summary) \
            .eq("id", position_id) \
            .execute()
```

### Position Price History Table

**migrations/V14__position_price_history.sql:**
```sql
-- Position-level price history for simulation
CREATE TABLE IF NOT EXISTS position_price_history (
    id BIGSERIAL PRIMARY KEY,
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    token_address VARCHAR(50) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price DECIMAL(20,10) NOT NULL,

    CONSTRAINT unique_position_time UNIQUE (position_id, timestamp)
);

CREATE INDEX idx_pph_position ON position_price_history(position_id);
CREATE INDEX idx_pph_position_time ON position_price_history(position_id, timestamp);
CREATE INDEX idx_pph_timestamp ON position_price_history(timestamp);

-- Add price_summary column to positions
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS price_summary JSONB DEFAULT NULL;

-- Partitioning for better performance (optional, for high volume)
-- Can partition by month if needed
```

### Background Jobs

**src/walltrack/jobs/price_history_jobs.py:**
```python
"""Background jobs for price history management."""

import asyncio
from datetime import datetime

import structlog

from walltrack.services.pricing.position_price_collector import (
    PositionPriceCollector,
    PriceHistoryCompressor,
)

logger = structlog.get_logger(__name__)


async def run_compression_job():
    """Run daily compression job."""
    compressor = PriceHistoryCompressor()

    # Compress 7-day old history
    compressed = await compressor.compress_old_history(days_old=7)
    logger.info("compression_job_complete", compressed=compressed)


async def run_cleanup_job():
    """Run daily cleanup job."""
    compressor = PriceHistoryCompressor()

    # Clean up 30-day old history
    deleted = await compressor.cleanup_old_history(days_old=30)
    logger.info("cleanup_job_complete", deleted=deleted)


async def run_collector():
    """Run continuous price collector."""
    collector = PositionPriceCollector(collection_interval_seconds=60)
    await collector.start()
```

## Implementation Tasks

- [ ] Create PositionPriceCollector class
- [ ] Implement price collection for active positions
- [ ] Create position_price_history table
- [ ] Create PriceHistoryCompressor class
- [ ] Implement 7-day compression logic
- [ ] Implement 30-day cleanup with summary
- [ ] Add price_summary column to positions
- [ ] Create background jobs
- [ ] Write tests

## Definition of Done

- [ ] Prices collected every minute for active positions
- [ ] Data stored in position_price_history
- [ ] Compression reduces data after 7 days
- [ ] Cleanup deletes after 30 days
- [ ] Summary preserved in position
- [ ] Jobs schedulable

## File List

### New Files
- `src/walltrack/services/pricing/position_price_collector.py` - Collector and compressor
- `src/walltrack/jobs/price_history_jobs.py` - Background jobs
- `migrations/V14__position_price_history.sql` - Table and columns

### Modified Files
- `src/walltrack/jobs/__init__.py` - Register jobs
