# Story 9.9: Signal Repository & Logging

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Story 9.7 (Signal Pipeline Integration)
- **Required by**: Epic 6 (Feedback Loop - Accuracy Tracking)

## User Story

**As a** system operator,
**I want** all processed signals to be stored and logged,
**So that** I can analyze signal quality, track accuracy, and improve the system.

## Problem Statement

Currently:
- Signals are processed but not persisted
- No way to track which signals passed/failed threshold
- Cannot measure signal accuracy over time
- No data for the feedback loop (Epic 6)
- Cannot debug why specific signals were rejected

## Acceptance Criteria

### AC 1: Signal Storage
**Given** a signal is processed through the pipeline
**When** scoring and threshold check complete
**Then** the full signal record is stored in database
**And** includes: wallet, token, direction, amounts, timestamp
**And** includes: score, conviction level, threshold result

### AC 2: Score Breakdown Storage
**Given** a signal is scored
**When** stored in database
**Then** individual score components are saved
**And** wallet score breakdown is included
**And** token score breakdown is included
**And** cluster amplification factor is recorded

### AC 3: Threshold Decision Logging
**Given** a signal reaches threshold checker
**When** decision is made
**Then** pass/fail is logged with reason
**And** margin above/below threshold is recorded
**And** safety filter results are stored

### AC 4: Signal Lifecycle Tracking
**Given** a signal becomes a trade
**When** trade outcome is known
**Then** signal is linked to trade result
**And** accuracy can be calculated
**And** signal is marked as verified/failed

### AC 5: Query Capabilities
**Given** stored signals exist
**When** analysis is needed
**Then** signals can be queried by date range
**And** filtered by wallet, token, or outcome
**And** aggregated for statistics
**And** exported for analysis

## Technical Specifications

### Database Schema

```sql
-- Migration: 019_signals.sql

-- Processed signals table
CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Signal identification
    tx_signature VARCHAR(100) UNIQUE NOT NULL,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,  -- 'buy' or 'sell'

    -- Amounts
    amount_sol DECIMAL(20, 9),
    amount_token DECIMAL(30, 9),

    -- Timestamps
    signal_timestamp TIMESTAMPTZ NOT NULL,
    processed_at TIMESTAMPTZ DEFAULT NOW(),

    -- Filter result
    filter_status VARCHAR(30) NOT NULL,  -- 'passed', 'blocked_blacklist', 'not_monitored'
    filter_time_ms DECIMAL(10, 2),

    -- Scoring (NULL if not scored)
    final_score DECIMAL(5, 4),
    wallet_score DECIMAL(5, 4),
    token_score DECIMAL(5, 4),
    cluster_score DECIMAL(5, 4),
    context_score DECIMAL(5, 4),

    -- Score breakdowns (JSONB for flexibility)
    wallet_score_breakdown JSONB,
    token_score_breakdown JSONB,

    -- Threshold result (NULL if not checked)
    threshold_passed BOOLEAN,
    threshold_value DECIMAL(5, 4),
    margin_above_threshold DECIMAL(5, 4),
    conviction_level VARCHAR(20),  -- 'high', 'standard', 'none'

    -- Safety checks
    safety_checks JSONB,  -- {min_liquidity: true, honeypot: false, ...}

    -- Trade linkage (NULL until trade executed)
    trade_id UUID REFERENCES trades(id),
    trade_outcome VARCHAR(20),  -- 'profit', 'loss', 'pending'

    -- Indexing
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_signals_wallet ON signals(wallet_address);
CREATE INDEX idx_signals_token ON signals(token_address);
CREATE INDEX idx_signals_timestamp ON signals(signal_timestamp);
CREATE INDEX idx_signals_threshold ON signals(threshold_passed);
CREATE INDEX idx_signals_score ON signals(final_score);
CREATE INDEX idx_signals_created ON signals(created_at);

-- View for signal statistics
CREATE OR REPLACE VIEW signal_stats AS
SELECT
    DATE_TRUNC('hour', processed_at) as hour,
    COUNT(*) as total_signals,
    COUNT(*) FILTER (WHERE filter_status = 'passed') as passed_filter,
    COUNT(*) FILTER (WHERE threshold_passed = true) as passed_threshold,
    AVG(final_score) FILTER (WHERE final_score IS NOT NULL) as avg_score,
    AVG(filter_time_ms) as avg_filter_time_ms
FROM signals
GROUP BY DATE_TRUNC('hour', processed_at)
ORDER BY hour DESC;
```

### Signal Repository

```python
# src/walltrack/data/supabase/repositories/signal_repo.py

from datetime import datetime
from typing import Any
from uuid import UUID

import structlog

from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger()


class SignalRepository:
    """Repository for storing and querying processed signals."""

    def __init__(self, client: SupabaseClient) -> None:
        self._client = client
        self._table = "signals"

    async def store_signal(self, signal: ProcessedSignal) -> UUID:
        """
        Store a processed signal with all scoring data.

        Args:
            signal: Fully processed signal with scores

        Returns:
            UUID of stored signal
        """
        record = {
            "tx_signature": signal.tx_signature,
            "wallet_address": signal.wallet_address,
            "token_address": signal.token_address,
            "direction": signal.direction,
            "amount_sol": signal.amount_sol,
            "amount_token": signal.amount_token,
            "signal_timestamp": signal.timestamp.isoformat(),

            # Filter result
            "filter_status": signal.filter_status.value,
            "filter_time_ms": signal.filter_time_ms,

            # Scores (may be None if not scored)
            "final_score": signal.final_score,
            "wallet_score": signal.scores.wallet if signal.scores else None,
            "token_score": signal.scores.token if signal.scores else None,
            "cluster_score": signal.scores.cluster if signal.scores else None,
            "context_score": signal.scores.context if signal.scores else None,

            # Breakdowns
            "wallet_score_breakdown": signal.wallet_breakdown,
            "token_score_breakdown": signal.token_breakdown,

            # Threshold
            "threshold_passed": signal.threshold_passed,
            "threshold_value": signal.threshold_value,
            "margin_above_threshold": signal.margin,
            "conviction_level": signal.conviction.value if signal.conviction else None,

            # Safety
            "safety_checks": signal.safety_checks,
        }

        result = await self._client.table(self._table).insert(record).execute()
        signal_id = UUID(result.data[0]["id"])

        log.info(
            "signal_stored",
            id=str(signal_id)[:8],
            wallet=signal.wallet_address[:12],
            score=f"{signal.final_score:.2f}" if signal.final_score else None,
            passed=signal.threshold_passed,
        )

        return signal_id

    async def link_to_trade(
        self, signal_id: UUID, trade_id: UUID, outcome: str
    ) -> None:
        """Link signal to resulting trade."""
        await self._client.table(self._table).update({
            "trade_id": str(trade_id),
            "trade_outcome": outcome,
        }).eq("id", str(signal_id)).execute()

    async def get_by_wallet(
        self,
        wallet_address: str,
        limit: int = 100,
        since: datetime | None = None,
    ) -> list[dict[str, Any]]:
        """Get signals for a specific wallet."""
        query = self._client.table(self._table).select("*").eq(
            "wallet_address", wallet_address
        )

        if since:
            query = query.gte("signal_timestamp", since.isoformat())

        query = query.order("signal_timestamp", desc=True).limit(limit)
        result = await query.execute()
        return result.data

    async def get_by_token(
        self,
        token_address: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get signals for a specific token."""
        result = await self._client.table(self._table).select("*").eq(
            "token_address", token_address
        ).order("signal_timestamp", desc=True).limit(limit).execute()
        return result.data

    async def get_passed_signals(
        self,
        since: datetime,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get signals that passed threshold."""
        result = await self._client.table(self._table).select("*").eq(
            "threshold_passed", True
        ).gte(
            "processed_at", since.isoformat()
        ).order("processed_at", desc=True).limit(limit).execute()
        return result.data

    async def get_statistics(
        self,
        since: datetime,
    ) -> dict[str, Any]:
        """Get signal statistics for a time period."""
        # Use the stats view
        result = await self._client.table("signal_stats").select("*").gte(
            "hour", since.isoformat()
        ).execute()

        if not result.data:
            return {
                "total_signals": 0,
                "passed_filter": 0,
                "passed_threshold": 0,
                "avg_score": 0,
            }

        # Aggregate
        total = sum(r["total_signals"] for r in result.data)
        passed_filter = sum(r["passed_filter"] for r in result.data)
        passed_threshold = sum(r["passed_threshold"] for r in result.data)

        scores = [r["avg_score"] for r in result.data if r["avg_score"]]
        avg_score = sum(scores) / len(scores) if scores else 0

        return {
            "total_signals": total,
            "passed_filter": passed_filter,
            "passed_threshold": passed_threshold,
            "filter_pass_rate": passed_filter / total if total else 0,
            "threshold_pass_rate": passed_threshold / passed_filter if passed_filter else 0,
            "avg_score": avg_score,
        }

    async def get_accuracy_data(
        self,
        since: datetime,
    ) -> dict[str, Any]:
        """Get data for accuracy calculation (Epic 6)."""
        result = await self._client.table(self._table).select(
            "final_score", "trade_outcome"
        ).eq(
            "threshold_passed", True
        ).not_.is_("trade_id", "null").gte(
            "processed_at", since.isoformat()
        ).execute()

        if not result.data:
            return {"total": 0, "profitable": 0, "accuracy": 0}

        total = len(result.data)
        profitable = len([r for r in result.data if r["trade_outcome"] == "profit"])

        return {
            "total": total,
            "profitable": profitable,
            "accuracy": profitable / total if total else 0,
        }
```

### ProcessedSignal Model

```python
# src/walltrack/services/signal/models.py

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from walltrack.services.signal.filter import FilterStatus
from walltrack.services.scoring.threshold_checker import ConvictionLevel


@dataclass
class ScoreBreakdown:
    """Individual score components."""
    wallet: float = 0.0
    token: float = 0.0
    cluster: float = 0.0
    context: float = 0.0


@dataclass
class ProcessedSignal:
    """Complete processed signal with all data."""
    # Identification
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str

    # Amounts
    amount_sol: float
    amount_token: float
    timestamp: datetime

    # Filter result
    filter_status: FilterStatus
    filter_time_ms: float = 0.0

    # Scores (may be None if not scored)
    final_score: float | None = None
    scores: ScoreBreakdown | None = None
    wallet_breakdown: dict[str, Any] = field(default_factory=dict)
    token_breakdown: dict[str, Any] = field(default_factory=dict)

    # Threshold result
    threshold_passed: bool | None = None
    threshold_value: float | None = None
    margin: float | None = None
    conviction: ConvictionLevel | None = None

    # Safety checks
    safety_checks: dict[str, bool] = field(default_factory=dict)
```

### Pipeline Integration

```python
# In pipeline.py, add signal storage:

async def process_swap_event(self, event: ParsedSwapEvent) -> ProcessingResult:
    """Full pipeline with signal storage."""

    processed_signal = ProcessedSignal(
        tx_signature=event.tx_signature,
        wallet_address=event.wallet_address,
        token_address=event.token_address,
        direction=event.direction.value,
        amount_sol=event.amount_sol,
        amount_token=event.amount_token,
        timestamp=event.timestamp,
        filter_status=FilterStatus.PASSED,  # Updated below
    )

    # Step 1: Filter
    filter_result = await self.filter.filter_signal(event)
    processed_signal.filter_status = filter_result.status
    processed_signal.filter_time_ms = filter_result.processing_time_ms

    if filter_result.status != FilterStatus.PASSED:
        await self.signal_repo.store_signal(processed_signal)
        return ProcessingResult(passed=False, reason=filter_result.status.value)

    # Step 2-4: Score and threshold (as before)
    # ... scoring logic ...

    processed_signal.final_score = scored_signal.final_score
    processed_signal.scores = ScoreBreakdown(...)
    processed_signal.threshold_passed = threshold_result.is_eligible
    processed_signal.conviction = threshold_result.conviction

    # Store signal
    signal_id = await self.signal_repo.store_signal(processed_signal)

    return ProcessingResult(
        passed=threshold_result.is_eligible,
        signal_id=signal_id,
        ...
    )
```

## API Endpoints

```python
# src/walltrack/api/routes/signals.py

router = APIRouter(prefix="/signals", tags=["signals"])

@router.get("/stats")
async def get_signal_stats(
    hours: int = Query(24, ge=1, le=168),
    repo: SignalRepository = Depends(get_signal_repo),
) -> dict[str, Any]:
    """Get signal statistics for the last N hours."""
    since = datetime.now(UTC) - timedelta(hours=hours)
    return await repo.get_statistics(since)

@router.get("/recent")
async def get_recent_signals(
    limit: int = Query(50, ge=1, le=200),
    passed_only: bool = Query(False),
    repo: SignalRepository = Depends(get_signal_repo),
) -> list[dict[str, Any]]:
    """Get recent signals."""
    ...

@router.get("/wallet/{address}")
async def get_wallet_signals(
    address: str,
    limit: int = Query(50),
    repo: SignalRepository = Depends(get_signal_repo),
) -> list[dict[str, Any]]:
    """Get signals for a specific wallet."""
    return await repo.get_by_wallet(address, limit)
```

## Testing Requirements

### Unit Tests
```python
class TestSignalRepository:
    async def test_store_signal(self):
        """Store and retrieve a signal."""

    async def test_link_to_trade(self):
        """Link signal to trade outcome."""

    async def test_get_statistics(self):
        """Calculate statistics correctly."""

    async def test_accuracy_calculation(self):
        """Calculate accuracy from outcomes."""
```

## Definition of Done

- [ ] Database migration created and applied
- [ ] SignalRepository implemented
- [ ] ProcessedSignal model created
- [ ] Pipeline stores all signals
- [ ] API endpoints for stats and queries
- [ ] Unit tests pass (>90% coverage)
- [ ] Signal stats visible in logs/API

## Estimated Effort

- **Implementation**: 3-4 hours
- **Testing**: 2 hours
- **Total**: 5-6 hours

## Notes

This repository enables:
1. Signal accuracy tracking for Epic 6 (Feedback Loop)
2. Debugging why signals were rejected
3. Analysis of scoring distribution
4. Historical signal queries for dashboards
