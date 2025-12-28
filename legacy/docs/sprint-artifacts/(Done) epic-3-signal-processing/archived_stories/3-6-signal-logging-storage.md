# Story 3.6: Signal Logging and Storage

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: High
- **FR**: FR18

## User Story

**As an** operator,
**I want** all signals logged regardless of score,
**So that** I can analyze patterns and improve the system.

## Acceptance Criteria

### AC 1: Signal Storage
**Given** any signal (filtered, scored, or discarded)
**When** signal processing completes
**Then** signal is stored in Supabase signals table
**And** stored data includes: timestamp, wallet, token, score, factors, status, processing_time

### AC 2: Query Support
**Given** signals table
**When** queried for analysis
**Then** signals can be filtered by: date range, wallet, score range, status
**And** query performance is acceptable for 6 months of data (NFR23)

### AC 3: Trade Linking
**Given** a signal is stored
**When** trade is later executed (Epic 4)
**Then** signal record is linked to trade record
**And** signal-to-trade correlation is trackable

### AC 4: Async Logging
**Given** signal logging
**When** high volume of signals arrives
**Then** logging does not block main processing pipeline
**And** async write ensures < 500ms processing time maintained

## Technical Notes

- FR18: Log all signals regardless of score for analysis
- Implement signals table in Supabase
- Create `signal_repo.py` in `src/walltrack/data/supabase/repositories/`
- Index on timestamp, wallet_address, score for query performance

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/signal_log.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Any


class SignalStatus(str, Enum):
    """Status of processed signal."""
    RECEIVED = "received"
    FILTERED_OUT = "filtered_out"
    SCORED = "scored"
    TRADE_ELIGIBLE = "trade_eligible"
    BELOW_THRESHOLD = "below_threshold"
    EXECUTED = "executed"
    FAILED = "failed"


class SignalLogEntry(BaseModel):
    """Complete signal log entry for storage."""

    # Identification
    id: str | None = None  # UUID from database
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"

    # Transaction details
    amount_token: float
    amount_sol: float
    slot: int | None = None

    # Scoring (nullable if filtered before scoring)
    final_score: float | None = None
    wallet_score: float | None = None
    cluster_score: float | None = None
    token_score: float | None = None
    context_score: float | None = None

    # Status
    status: SignalStatus = SignalStatus.RECEIVED
    eligibility_status: str | None = None  # trade_eligible, below_threshold
    conviction_tier: str | None = None  # high, standard, none

    # Filtering info
    filter_status: str | None = None  # passed, discarded, blocked
    filter_reason: str | None = None

    # Linked trade (populated later in Epic 4)
    trade_id: str | None = None

    # Timing
    timestamp: datetime  # Original transaction time
    received_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: float = 0.0

    # Metadata
    raw_factors: dict[str, Any] = Field(default_factory=dict)


class SignalLogFilter(BaseModel):
    """Filter criteria for querying signals."""

    # Date range
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Wallet filter
    wallet_address: str | None = None

    # Score range
    min_score: float | None = None
    max_score: float | None = None

    # Status filter
    status: SignalStatus | None = None
    eligibility_status: str | None = None

    # Pagination
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: str = "timestamp"
    sort_desc: bool = True


class SignalLogSummary(BaseModel):
    """Summary statistics for signals."""

    total_count: int = 0
    trade_eligible_count: int = 0
    below_threshold_count: int = 0
    filtered_count: int = 0
    executed_count: int = 0

    avg_score: float | None = None
    avg_processing_time_ms: float | None = None

    period_start: datetime | None = None
    period_end: datetime | None = None
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/signal_log.py
from typing import Final

# Query performance
MAX_QUERY_RESULTS: Final[int] = 1000
DEFAULT_QUERY_LIMIT: Final[int] = 100

# Data retention (NFR23: 6 months)
DATA_RETENTION_DAYS: Final[int] = 180

# Async logging
LOG_BATCH_SIZE: Final[int] = 50
LOG_FLUSH_INTERVAL_SECONDS: Final[int] = 5
MAX_LOG_QUEUE_SIZE: Final[int] = 1000
```

### 3. Signal Repository

```python
# src/walltrack/data/supabase/repositories/signal_repo.py
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.core.constants.signal_log import (
    DEFAULT_QUERY_LIMIT,
    MAX_QUERY_RESULTS,
)
from walltrack.core.models.signal_log import (
    SignalLogEntry,
    SignalLogFilter,
    SignalLogSummary,
    SignalStatus,
)

logger = structlog.get_logger(__name__)


class SignalRepository:
    """Repository for signal logging and queries."""

    def __init__(self, client: AsyncClient):
        self.client = client

    async def save(self, signal: SignalLogEntry) -> str:
        """
        Save signal to database.

        Returns the generated UUID.
        """
        data = {
            "tx_signature": signal.tx_signature,
            "wallet_address": signal.wallet_address,
            "token_address": signal.token_address,
            "direction": signal.direction,
            "amount_token": signal.amount_token,
            "amount_sol": signal.amount_sol,
            "slot": signal.slot,
            "final_score": signal.final_score,
            "wallet_score": signal.wallet_score,
            "cluster_score": signal.cluster_score,
            "token_score": signal.token_score,
            "context_score": signal.context_score,
            "status": signal.status.value,
            "eligibility_status": signal.eligibility_status,
            "conviction_tier": signal.conviction_tier,
            "filter_status": signal.filter_status,
            "filter_reason": signal.filter_reason,
            "timestamp": signal.timestamp.isoformat(),
            "received_at": signal.received_at.isoformat(),
            "processing_time_ms": signal.processing_time_ms,
            "raw_factors": signal.raw_factors,
        }

        result = await self.client.table("signals").insert(data).execute()

        if result.data:
            signal_id = result.data[0]["id"]
            logger.debug(
                "signal_saved",
                signal_id=signal_id,
                tx=signal.tx_signature[:8] + "...",
                status=signal.status.value,
            )
            return signal_id

        raise Exception("Failed to save signal")

    async def save_batch(self, signals: list[SignalLogEntry]) -> list[str]:
        """Save multiple signals in a batch."""
        data = [
            {
                "tx_signature": s.tx_signature,
                "wallet_address": s.wallet_address,
                "token_address": s.token_address,
                "direction": s.direction,
                "amount_token": s.amount_token,
                "amount_sol": s.amount_sol,
                "final_score": s.final_score,
                "status": s.status.value,
                "eligibility_status": s.eligibility_status,
                "timestamp": s.timestamp.isoformat(),
                "received_at": s.received_at.isoformat(),
                "processing_time_ms": s.processing_time_ms,
            }
            for s in signals
        ]

        result = await self.client.table("signals").insert(data).execute()

        if result.data:
            return [r["id"] for r in result.data]
        return []

    async def get_by_signature(self, tx_signature: str) -> SignalLogEntry | None:
        """Get signal by transaction signature."""
        result = await self.client.table("signals").select(
            "*"
        ).eq("tx_signature", tx_signature).single().execute()

        if result.data:
            return self._row_to_entry(result.data)
        return None

    async def query(self, filter: SignalLogFilter) -> list[SignalLogEntry]:
        """Query signals with filters."""
        query = self.client.table("signals").select("*")

        # Apply filters
        if filter.start_date:
            query = query.gte("timestamp", filter.start_date.isoformat())
        if filter.end_date:
            query = query.lte("timestamp", filter.end_date.isoformat())
        if filter.wallet_address:
            query = query.eq("wallet_address", filter.wallet_address)
        if filter.min_score is not None:
            query = query.gte("final_score", filter.min_score)
        if filter.max_score is not None:
            query = query.lte("final_score", filter.max_score)
        if filter.status:
            query = query.eq("status", filter.status.value)
        if filter.eligibility_status:
            query = query.eq("eligibility_status", filter.eligibility_status)

        # Sorting
        query = query.order(
            filter.sort_by,
            desc=filter.sort_desc,
        )

        # Pagination
        limit = min(filter.limit, MAX_QUERY_RESULTS)
        query = query.range(filter.offset, filter.offset + limit - 1)

        result = await query.execute()

        return [self._row_to_entry(row) for row in result.data]

    async def get_summary(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SignalLogSummary:
        """Get summary statistics for signals."""
        if not start_date:
            start_date = datetime.now(timezone.utc) - timedelta(days=1)
        if not end_date:
            end_date = datetime.now(timezone.utc)

        # Count by status
        result = await self.client.table("signals").select(
            "status",
            count="exact",
        ).gte("timestamp", start_date.isoformat()).lte(
            "timestamp", end_date.isoformat()
        ).execute()

        total = result.count or 0

        # Get counts by eligibility
        eligible_result = await self.client.table("signals").select(
            "id", count="exact"
        ).eq("eligibility_status", "trade_eligible").gte(
            "timestamp", start_date.isoformat()
        ).execute()

        below_result = await self.client.table("signals").select(
            "id", count="exact"
        ).eq("eligibility_status", "below_threshold").gte(
            "timestamp", start_date.isoformat()
        ).execute()

        executed_result = await self.client.table("signals").select(
            "id", count="exact"
        ).eq("status", "executed").gte(
            "timestamp", start_date.isoformat()
        ).execute()

        # Calculate averages
        avg_result = await self.client.rpc(
            "get_signal_averages",
            {"start_ts": start_date.isoformat(), "end_ts": end_date.isoformat()},
        ).execute()

        avg_score = None
        avg_processing = None
        if avg_result.data:
            avg_score = avg_result.data.get("avg_score")
            avg_processing = avg_result.data.get("avg_processing_ms")

        return SignalLogSummary(
            total_count=total,
            trade_eligible_count=eligible_result.count or 0,
            below_threshold_count=below_result.count or 0,
            executed_count=executed_result.count or 0,
            avg_score=avg_score,
            avg_processing_time_ms=avg_processing,
            period_start=start_date,
            period_end=end_date,
        )

    async def link_to_trade(self, tx_signature: str, trade_id: str) -> None:
        """Link signal to executed trade."""
        await self.client.table("signals").update({
            "trade_id": trade_id,
            "status": SignalStatus.EXECUTED.value,
        }).eq("tx_signature", tx_signature).execute()

        logger.info(
            "signal_linked_to_trade",
            tx=tx_signature[:8] + "...",
            trade_id=trade_id,
        )

    async def update_status(
        self,
        tx_signature: str,
        status: SignalStatus,
    ) -> None:
        """Update signal status."""
        await self.client.table("signals").update({
            "status": status.value,
        }).eq("tx_signature", tx_signature).execute()

    def _row_to_entry(self, row: dict[str, Any]) -> SignalLogEntry:
        """Convert database row to SignalLogEntry."""
        return SignalLogEntry(
            id=row.get("id"),
            tx_signature=row["tx_signature"],
            wallet_address=row["wallet_address"],
            token_address=row["token_address"],
            direction=row["direction"],
            amount_token=row.get("amount_token", 0),
            amount_sol=row.get("amount_sol", 0),
            slot=row.get("slot"),
            final_score=row.get("final_score"),
            wallet_score=row.get("wallet_score"),
            cluster_score=row.get("cluster_score"),
            token_score=row.get("token_score"),
            context_score=row.get("context_score"),
            status=SignalStatus(row.get("status", "received")),
            eligibility_status=row.get("eligibility_status"),
            conviction_tier=row.get("conviction_tier"),
            filter_status=row.get("filter_status"),
            filter_reason=row.get("filter_reason"),
            trade_id=row.get("trade_id"),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            received_at=datetime.fromisoformat(row["received_at"]) if row.get("received_at") else datetime.now(timezone.utc),
            processing_time_ms=row.get("processing_time_ms", 0),
            raw_factors=row.get("raw_factors", {}),
        )
```

### 4. Async Signal Logger Service

```python
# src/walltrack/services/signal/async_logger.py
import asyncio
from datetime import datetime
from typing import List

import structlog

from walltrack.core.constants.signal_log import (
    LOG_BATCH_SIZE,
    LOG_FLUSH_INTERVAL_SECONDS,
    MAX_LOG_QUEUE_SIZE,
)
from walltrack.core.models.signal_log import SignalLogEntry
from walltrack.data.supabase.repositories.signal_repo import SignalRepository

logger = structlog.get_logger(__name__)


class AsyncSignalLogger:
    """
    Async signal logger that batches writes for performance.

    Ensures logging doesn't block the main processing pipeline (AC4).
    """

    def __init__(
        self,
        signal_repo: SignalRepository,
        batch_size: int = LOG_BATCH_SIZE,
        flush_interval: int = LOG_FLUSH_INTERVAL_SECONDS,
    ):
        self.signal_repo = signal_repo
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue[SignalLogEntry] = asyncio.Queue(
            maxsize=MAX_LOG_QUEUE_SIZE
        )
        self._running = False
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "async_logger_started",
            batch_size=self.batch_size,
            flush_interval=self.flush_interval,
        )

    async def stop(self) -> None:
        """Stop background flush task and flush remaining."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass

        # Flush remaining items
        await self._flush_batch()
        logger.info("async_logger_stopped")

    async def log(self, signal: SignalLogEntry) -> None:
        """
        Queue signal for async logging.

        Non-blocking to maintain < 500ms processing time.
        """
        try:
            self._queue.put_nowait(signal)
        except asyncio.QueueFull:
            logger.warning(
                "signal_log_queue_full",
                queue_size=MAX_LOG_QUEUE_SIZE,
            )
            # Drop oldest and add new
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(signal)
            except asyncio.QueueEmpty:
                pass

    async def _flush_loop(self) -> None:
        """Background loop to flush batches."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("signal_flush_error", error=str(e))

    async def _flush_batch(self) -> None:
        """Flush current batch to database."""
        batch: List[SignalLogEntry] = []

        # Collect items from queue
        while len(batch) < self.batch_size:
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        try:
            await self.signal_repo.save_batch(batch)
            logger.debug(
                "signal_batch_flushed",
                count=len(batch),
            )
        except Exception as e:
            logger.error(
                "signal_batch_save_error",
                count=len(batch),
                error=str(e),
            )
            # Re-queue failed items
            for item in batch:
                try:
                    self._queue.put_nowait(item)
                except asyncio.QueueFull:
                    break

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()
```

### 5. Database Schema

```sql
-- Supabase migration: signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,

    -- Transaction details
    amount_token DECIMAL(30, 10),
    amount_sol DECIMAL(20, 10),
    slot BIGINT,

    -- Scores
    final_score DECIMAL(5, 4),
    wallet_score DECIMAL(5, 4),
    cluster_score DECIMAL(5, 4),
    token_score DECIMAL(5, 4),
    context_score DECIMAL(5, 4),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'received',
    eligibility_status VARCHAR(30),
    conviction_tier VARCHAR(20),

    -- Filter info
    filter_status VARCHAR(20),
    filter_reason TEXT,

    -- Trade link
    trade_id UUID REFERENCES trades(id),

    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_time_ms DECIMAL(10, 2),

    -- Metadata
    raw_factors JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for query performance (AC2, NFR23)
CREATE INDEX idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX idx_signals_wallet ON signals(wallet_address, timestamp DESC);
CREATE INDEX idx_signals_score ON signals(final_score DESC) WHERE final_score IS NOT NULL;
CREATE INDEX idx_signals_status ON signals(status, timestamp DESC);
CREATE INDEX idx_signals_eligibility ON signals(eligibility_status, timestamp DESC);
CREATE INDEX idx_signals_trade ON signals(trade_id) WHERE trade_id IS NOT NULL;

-- Composite index for common queries
CREATE INDEX idx_signals_wallet_score ON signals(wallet_address, final_score DESC, timestamp DESC);

-- Function for averages
CREATE OR REPLACE FUNCTION get_signal_averages(start_ts TIMESTAMPTZ, end_ts TIMESTAMPTZ)
RETURNS TABLE(avg_score DECIMAL, avg_processing_ms DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(final_score)::DECIMAL,
        AVG(processing_time_ms)::DECIMAL
    FROM signals
    WHERE timestamp >= start_ts AND timestamp <= end_ts
    AND final_score IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Partition by month for performance with large data (NFR23: 6 months)
-- Note: Uncomment for production with high volume
-- CREATE TABLE signals_2024_01 PARTITION OF signals
--     FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/signals.py (extended)
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query

import structlog

from walltrack.core.models.signal_log import (
    SignalLogEntry,
    SignalLogFilter,
    SignalLogSummary,
    SignalStatus,
)
from walltrack.data.supabase.repositories.signal_repo import SignalRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


def get_signal_repo() -> SignalRepository:
    """Dependency for signal repository."""
    from walltrack.data.supabase.client import get_supabase_client
    return SignalRepository(get_supabase_client())


@router.get("/", response_model=list[SignalLogEntry])
async def list_signals(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    wallet: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    status: SignalStatus | None = None,
    eligibility: str | None = None,
    limit: int = Query(default=100, le=1000),
    offset: int = Query(default=0, ge=0),
    repo: SignalRepository = Depends(get_signal_repo),
) -> list[SignalLogEntry]:
    """
    Query signals with filters.

    Supports filtering by date range, wallet, score range, and status.
    """
    filter = SignalLogFilter(
        start_date=start_date,
        end_date=end_date,
        wallet_address=wallet,
        min_score=min_score,
        max_score=max_score,
        status=status,
        eligibility_status=eligibility,
        limit=limit,
        offset=offset,
    )

    return await repo.query(filter)


@router.get("/summary", response_model=SignalLogSummary)
async def get_signals_summary(
    start_date: datetime | None = None,
    end_date: datetime | None = None,
    repo: SignalRepository = Depends(get_signal_repo),
) -> SignalLogSummary:
    """Get summary statistics for signals."""
    return await repo.get_summary(start_date, end_date)


@router.get("/{tx_signature}", response_model=SignalLogEntry)
async def get_signal(
    tx_signature: str,
    repo: SignalRepository = Depends(get_signal_repo),
) -> SignalLogEntry:
    """Get signal by transaction signature."""
    signal = await repo.get_by_signature(tx_signature)
    if not signal:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal
```

### 7. Unit Tests

```python
# tests/unit/services/signal/test_async_logger.py
import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.models.signal_log import SignalLogEntry, SignalStatus
from walltrack.services.signal.async_logger import AsyncSignalLogger


@pytest.fixture
def sample_signal() -> SignalLogEntry:
    """Sample signal for testing."""
    return SignalLogEntry(
        tx_signature="sig123",
        wallet_address="Wallet123456789012345678901234567890123",
        token_address="Token1234567890123456789012345678901234",
        direction="buy",
        amount_token=1000000,
        amount_sol=1.0,
        final_score=0.75,
        status=SignalStatus.SCORED,
        timestamp=datetime.now(timezone.utc),
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    """Mock signal repository."""
    repo = MagicMock()
    repo.save_batch = AsyncMock(return_value=["id1", "id2"])
    return repo


class TestAsyncSignalLogger:
    """Tests for AsyncSignalLogger."""

    @pytest.mark.asyncio
    async def test_queue_signal(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test signal is queued for async logging."""
        logger = AsyncSignalLogger(mock_repo, batch_size=10, flush_interval=60)

        await logger.log(sample_signal)

        assert logger.queue_size == 1

    @pytest.mark.asyncio
    async def test_batch_flush(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test batch is flushed to database."""
        logger = AsyncSignalLogger(mock_repo, batch_size=2, flush_interval=1)
        await logger.start()

        # Queue signals
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        # Wait for flush
        await asyncio.sleep(1.5)

        await logger.stop()

        mock_repo.save_batch.assert_called()

    @pytest.mark.asyncio
    async def test_queue_full_handling(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test handling when queue is full."""
        # Small queue for testing
        logger = AsyncSignalLogger(mock_repo, batch_size=100)
        logger._queue = asyncio.Queue(maxsize=2)

        # Fill queue
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        # Should not raise, should drop oldest
        await logger.log(sample_signal)

        assert logger.queue_size == 2

    @pytest.mark.asyncio
    async def test_non_blocking_log(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test that logging is non-blocking."""
        import time

        logger = AsyncSignalLogger(mock_repo)

        start = time.perf_counter()
        await logger.log(sample_signal)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should be < 1ms (non-blocking)
        assert elapsed_ms < 10


class TestSignalRepository:
    """Tests for SignalRepository."""

    @pytest.mark.asyncio
    async def test_query_by_date_range(self, mock_repo):
        """Test querying signals by date range."""
        from walltrack.core.models.signal_log import SignalLogFilter
        from walltrack.data.supabase.repositories.signal_repo import SignalRepository

        # This would be an integration test with actual Supabase
        pass

    @pytest.mark.asyncio
    async def test_link_to_trade(self, mock_repo):
        """Test linking signal to trade."""
        pass
```

---

## Implementation Tasks

- [x] Create signals table schema in Supabase
- [x] Create `src/walltrack/data/supabase/repositories/signal_repo.py`
- [x] Implement async signal storage
- [x] Add indexes for query performance
- [x] Link signals to trades
- [x] Ensure < 500ms processing time

## Definition of Done

- [x] All signals stored in Supabase
- [x] Query by date, wallet, score, status works
- [x] Performance acceptable for 6 months data
- [x] Async logging doesn't block pipeline

---

## Dev Agent Record

**Completed:** 2024-12-18

### Files Created
- `src/walltrack/constants/signal_log.py` - Query/retention/batch constants
- `src/walltrack/models/signal_log.py` - SignalStatus, SignalLogEntry, SignalLogFilter, SignalLogSummary
- `src/walltrack/data/supabase/migrations/006_signals.sql` - Signals table with indexes
- `src/walltrack/data/supabase/repositories/signal_repo.py` - SignalRepository with CRUD operations
- `src/walltrack/services/signal/async_logger.py` - AsyncSignalLogger for non-blocking writes
- `tests/unit/services/signal/test_async_logger.py` - 16 tests for async logger
- `tests/unit/models/test_signal_log.py` - 17 tests for models

### Implementation Summary
1. **SignalLogEntry model**: Complete signal log with scores, status, filters, trade linking
2. **SignalRepository**: Full CRUD with batch save, query filters, summary stats
3. **AsyncSignalLogger**: Queue-based batching with background flush (< 500ms non-blocking)
4. **Database schema**: Signals table with 7 indexes for NFR23 (6 months data)

### Test Results
- 33 tests passing
- All acceptance criteria covered
