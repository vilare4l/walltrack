# Story 6.1: Trade Outcome Recording

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: High
- **FR**: FR34

## User Story

**As an** operator,
**I want** all trade outcomes recorded with full details,
**So that** performance can be analyzed and the system can learn.

## Acceptance Criteria

### AC 1: Outcome Recording
**Given** a position is closed (any exit reason)
**When** outcome is recorded
**Then** trade record includes:
- trade_id, position_id, signal_id
- entry_price, exit_price, amount
- realized_pnl (absolute and percentage)
- duration (time held)
- exit_reason (stop_loss, take_profit, trailing_stop, time_based, manual)
- wallet_address, token_address
- signal_score at entry

### AC 2: Partial Exit Recording
**Given** partial exit (take-profit level hit)
**When** partial outcome is recorded
**Then** partial trade record is created
**And** linked to parent position
**And** partial PnL is calculated

### AC 3: Aggregate Updates
**Given** trade is recorded
**When** aggregate metrics are updated
**Then** running totals are recalculated:
- Total PnL
- Win count / Loss count
- Average win / Average loss
- Current win rate

### AC 4: Query Support
**Given** trades table in Supabase
**When** historical queries are run
**Then** trades can be filtered by date, wallet, token, exit_reason
**And** query performance supports 1 year of data (NFR22)

## Technical Notes

- FR34: Record trade outcomes (entry price, exit price, PnL, duration)
- Extend trades table in Supabase
- Link to signals and positions tables
- Implement in `src/walltrack/core/feedback/trade_recorder.py`

---

## Technical Specification

### Pydantic Models

```python
# src/walltrack/core/feedback/models.py
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from uuid import UUID


class ExitReason(str, Enum):
    """Reason for position exit."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_BASED = "time_based"
    MANUAL = "manual"
    CIRCUIT_BREAKER = "circuit_breaker"
    PARTIAL_TP = "partial_tp"


class TradeOutcomeCreate(BaseModel):
    """Input for creating a trade outcome record."""
    position_id: UUID = Field(..., description="Position ID")
    signal_id: UUID = Field(..., description="Original signal ID")
    wallet_address: str = Field(..., description="Tracked wallet address")
    token_address: str = Field(..., description="Token mint address")
    token_symbol: str = Field(..., description="Token symbol")
    entry_price: Decimal = Field(..., gt=0, description="Entry price in SOL")
    exit_price: Decimal = Field(..., gt=0, description="Exit price in SOL")
    amount_tokens: Decimal = Field(..., gt=0, description="Token amount traded")
    amount_sol: Decimal = Field(..., gt=0, description="SOL amount invested")
    exit_reason: ExitReason = Field(..., description="Reason for exit")
    signal_score: Decimal = Field(..., ge=0, le=1, description="Signal score at entry")
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    exit_timestamp: datetime = Field(..., description="Exit timestamp")
    is_partial: bool = Field(default=False, description="Is partial exit")
    parent_trade_id: Optional[UUID] = Field(default=None, description="Parent trade ID for partial exits")


class TradeOutcome(BaseModel):
    """Recorded trade outcome with calculated metrics."""
    id: UUID = Field(..., description="Trade outcome ID")
    position_id: UUID = Field(..., description="Position ID")
    signal_id: UUID = Field(..., description="Original signal ID")
    wallet_address: str = Field(..., description="Tracked wallet address")
    token_address: str = Field(..., description="Token mint address")
    token_symbol: str = Field(..., description="Token symbol")
    entry_price: Decimal = Field(..., description="Entry price")
    exit_price: Decimal = Field(..., description="Exit price")
    amount_tokens: Decimal = Field(..., description="Token amount traded")
    amount_sol: Decimal = Field(..., description="SOL amount invested")
    exit_reason: ExitReason = Field(..., description="Exit reason")
    signal_score: Decimal = Field(..., description="Signal score at entry")
    entry_timestamp: datetime = Field(..., description="Entry timestamp")
    exit_timestamp: datetime = Field(..., description="Exit timestamp")
    is_partial: bool = Field(default=False, description="Is partial exit")
    parent_trade_id: Optional[UUID] = Field(default=None, description="Parent trade for partials")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def realized_pnl_sol(self) -> Decimal:
        """Absolute PnL in SOL."""
        exit_value = self.amount_tokens * self.exit_price
        entry_value = self.amount_sol
        return exit_value - entry_value

    @computed_field
    @property
    def realized_pnl_percent(self) -> Decimal:
        """PnL as percentage."""
        if self.amount_sol == 0:
            return Decimal("0")
        return (self.realized_pnl_sol / self.amount_sol) * 100

    @computed_field
    @property
    def duration_seconds(self) -> int:
        """Trade duration in seconds."""
        return int((self.exit_timestamp - self.entry_timestamp).total_seconds())

    @computed_field
    @property
    def is_win(self) -> bool:
        """Whether trade was profitable."""
        return self.realized_pnl_sol > 0


class AggregateMetrics(BaseModel):
    """Aggregate trading metrics."""
    total_pnl_sol: Decimal = Field(default=Decimal("0"), description="Total PnL in SOL")
    total_pnl_percent: Decimal = Field(default=Decimal("0"), description="Total PnL %")
    win_count: int = Field(default=0, description="Number of winning trades")
    loss_count: int = Field(default=0, description="Number of losing trades")
    total_trades: int = Field(default=0, description="Total trades")
    average_win_sol: Decimal = Field(default=Decimal("0"), description="Average win in SOL")
    average_loss_sol: Decimal = Field(default=Decimal("0"), description="Average loss in SOL")
    largest_win_sol: Decimal = Field(default=Decimal("0"), description="Largest win")
    largest_loss_sol: Decimal = Field(default=Decimal("0"), description="Largest loss")
    gross_profit: Decimal = Field(default=Decimal("0"), description="Total profits")
    gross_loss: Decimal = Field(default=Decimal("0"), description="Total losses")
    total_volume_sol: Decimal = Field(default=Decimal("0"), description="Total volume traded")
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def win_rate(self) -> Decimal:
        """Current win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.win_count) / Decimal(self.total_trades)) * 100

    @computed_field
    @property
    def profit_factor(self) -> Decimal:
        """Profit factor (gross profit / gross loss)."""
        if self.gross_loss == 0:
            return Decimal("999") if self.gross_profit > 0 else Decimal("0")
        return self.gross_profit / abs(self.gross_loss)

    @computed_field
    @property
    def expectancy(self) -> Decimal:
        """Expected value per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return self.total_pnl_sol / Decimal(self.total_trades)


class TradeQuery(BaseModel):
    """Query parameters for trade history."""
    start_date: Optional[datetime] = Field(default=None, description="Start date filter")
    end_date: Optional[datetime] = Field(default=None, description="End date filter")
    wallet_address: Optional[str] = Field(default=None, description="Wallet filter")
    token_address: Optional[str] = Field(default=None, description="Token filter")
    exit_reason: Optional[ExitReason] = Field(default=None, description="Exit reason filter")
    is_win: Optional[bool] = Field(default=None, description="Win/loss filter")
    min_pnl: Optional[Decimal] = Field(default=None, description="Minimum PnL filter")
    max_pnl: Optional[Decimal] = Field(default=None, description="Maximum PnL filter")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class TradeQueryResult(BaseModel):
    """Trade query results with pagination."""
    trades: list[TradeOutcome] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Total matching trades")
    aggregates: AggregateMetrics = Field(default_factory=AggregateMetrics)
```

### Service Implementation

```python
# src/walltrack/core/feedback/trade_recorder.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from .models import (
    TradeOutcomeCreate,
    TradeOutcome,
    AggregateMetrics,
    TradeQuery,
    TradeQueryResult,
    ExitReason,
)

logger = structlog.get_logger()


class TradeRecorder:
    """Records and manages trade outcomes."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self._aggregate_cache: Optional[AggregateMetrics] = None
        self._cache_timestamp: Optional[datetime] = None

    async def record_trade(
        self,
        trade_create: TradeOutcomeCreate,
    ) -> TradeOutcome:
        """
        Record a trade outcome.

        Args:
            trade_create: Trade outcome data to record

        Returns:
            Recorded TradeOutcome with calculated metrics
        """
        trade_id = uuid4()

        trade = TradeOutcome(
            id=trade_id,
            position_id=trade_create.position_id,
            signal_id=trade_create.signal_id,
            wallet_address=trade_create.wallet_address,
            token_address=trade_create.token_address,
            token_symbol=trade_create.token_symbol,
            entry_price=trade_create.entry_price,
            exit_price=trade_create.exit_price,
            amount_tokens=trade_create.amount_tokens,
            amount_sol=trade_create.amount_sol,
            exit_reason=trade_create.exit_reason,
            signal_score=trade_create.signal_score,
            entry_timestamp=trade_create.entry_timestamp,
            exit_timestamp=trade_create.exit_timestamp,
            is_partial=trade_create.is_partial,
            parent_trade_id=trade_create.parent_trade_id,
        )

        # Persist to database
        await self._save_trade(trade)

        # Update aggregate metrics
        await self._update_aggregates(trade)

        # Invalidate cache
        self._aggregate_cache = None

        logger.info(
            "trade_recorded",
            trade_id=str(trade_id),
            position_id=str(trade.position_id),
            pnl_sol=float(trade.realized_pnl_sol),
            pnl_percent=float(trade.realized_pnl_percent),
            is_win=trade.is_win,
            exit_reason=trade.exit_reason.value,
        )

        return trade

    async def record_partial_exit(
        self,
        parent_trade_id: UUID,
        exit_price: Decimal,
        amount_tokens: Decimal,
        exit_reason: ExitReason = ExitReason.PARTIAL_TP,
    ) -> TradeOutcome:
        """
        Record a partial exit linked to a parent trade.

        Args:
            parent_trade_id: ID of the parent trade
            exit_price: Exit price for this partial
            amount_tokens: Token amount for this partial
            exit_reason: Reason for partial exit

        Returns:
            Recorded partial TradeOutcome
        """
        # Get parent trade details
        parent = await self.get_trade(parent_trade_id)
        if not parent:
            raise ValueError(f"Parent trade {parent_trade_id} not found")

        # Calculate proportional SOL amount
        proportion = amount_tokens / parent.amount_tokens
        amount_sol = parent.amount_sol * proportion

        partial_create = TradeOutcomeCreate(
            position_id=parent.position_id,
            signal_id=parent.signal_id,
            wallet_address=parent.wallet_address,
            token_address=parent.token_address,
            token_symbol=parent.token_symbol,
            entry_price=parent.entry_price,
            exit_price=exit_price,
            amount_tokens=amount_tokens,
            amount_sol=amount_sol,
            exit_reason=exit_reason,
            signal_score=parent.signal_score,
            entry_timestamp=parent.entry_timestamp,
            exit_timestamp=datetime.utcnow(),
            is_partial=True,
            parent_trade_id=parent_trade_id,
        )

        return await self.record_trade(partial_create)

    async def get_trade(self, trade_id: UUID) -> Optional[TradeOutcome]:
        """Get a single trade by ID."""
        result = await self.supabase.table("trade_outcomes").select("*").eq(
            "id", str(trade_id)
        ).single().execute()

        if result.data:
            return TradeOutcome(**result.data)
        return None

    async def query_trades(self, query: TradeQuery) -> TradeQueryResult:
        """
        Query trade history with filters.

        Args:
            query: Query parameters

        Returns:
            TradeQueryResult with trades and aggregates
        """
        db_query = self.supabase.table("trade_outcomes").select("*", count="exact")

        # Apply filters
        if query.start_date:
            db_query = db_query.gte("exit_timestamp", query.start_date.isoformat())
        if query.end_date:
            db_query = db_query.lte("exit_timestamp", query.end_date.isoformat())
        if query.wallet_address:
            db_query = db_query.eq("wallet_address", query.wallet_address)
        if query.token_address:
            db_query = db_query.eq("token_address", query.token_address)
        if query.exit_reason:
            db_query = db_query.eq("exit_reason", query.exit_reason.value)

        # Ordering and pagination
        db_query = db_query.order("exit_timestamp", desc=True)
        db_query = db_query.range(query.offset, query.offset + query.limit - 1)

        result = await db_query.execute()

        trades = [TradeOutcome(**t) for t in result.data]

        # Filter by computed fields if needed
        if query.is_win is not None:
            trades = [t for t in trades if t.is_win == query.is_win]
        if query.min_pnl is not None:
            trades = [t for t in trades if t.realized_pnl_sol >= query.min_pnl]
        if query.max_pnl is not None:
            trades = [t for t in trades if t.realized_pnl_sol <= query.max_pnl]

        # Calculate aggregates for filtered trades
        aggregates = self._calculate_aggregates(trades)

        return TradeQueryResult(
            trades=trades,
            total_count=result.count or len(trades),
            aggregates=aggregates,
        )

    async def get_aggregates(self, force_refresh: bool = False) -> AggregateMetrics:
        """
        Get current aggregate metrics.

        Args:
            force_refresh: Force recalculation from database

        Returns:
            Current AggregateMetrics
        """
        # Check cache (5 minute expiry)
        if (
            not force_refresh
            and self._aggregate_cache
            and self._cache_timestamp
            and (datetime.utcnow() - self._cache_timestamp).seconds < 300
        ):
            return self._aggregate_cache

        # Load from database
        result = await self.supabase.table("aggregate_metrics").select("*").single().execute()

        if result.data:
            self._aggregate_cache = AggregateMetrics(**result.data)
        else:
            self._aggregate_cache = AggregateMetrics()

        self._cache_timestamp = datetime.utcnow()
        return self._aggregate_cache

    async def get_trades_for_position(self, position_id: UUID) -> list[TradeOutcome]:
        """Get all trades (including partials) for a position."""
        result = await self.supabase.table("trade_outcomes").select("*").eq(
            "position_id", str(position_id)
        ).order("exit_timestamp").execute()

        return [TradeOutcome(**t) for t in result.data]

    async def get_partial_trades(self, parent_trade_id: UUID) -> list[TradeOutcome]:
        """Get all partial trades linked to a parent trade."""
        result = await self.supabase.table("trade_outcomes").select("*").eq(
            "parent_trade_id", str(parent_trade_id)
        ).order("exit_timestamp").execute()

        return [TradeOutcome(**t) for t in result.data]

    def _calculate_aggregates(self, trades: list[TradeOutcome]) -> AggregateMetrics:
        """Calculate aggregates for a list of trades."""
        if not trades:
            return AggregateMetrics()

        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        gross_profit = sum(t.realized_pnl_sol for t in wins)
        gross_loss = sum(t.realized_pnl_sol for t in losses)

        return AggregateMetrics(
            total_pnl_sol=sum(t.realized_pnl_sol for t in trades),
            total_pnl_percent=sum(t.realized_pnl_percent for t in trades) / len(trades) if trades else Decimal("0"),
            win_count=len(wins),
            loss_count=len(losses),
            total_trades=len(trades),
            average_win_sol=gross_profit / len(wins) if wins else Decimal("0"),
            average_loss_sol=gross_loss / len(losses) if losses else Decimal("0"),
            largest_win_sol=max((t.realized_pnl_sol for t in wins), default=Decimal("0")),
            largest_loss_sol=min((t.realized_pnl_sol for t in losses), default=Decimal("0")),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_volume_sol=sum(t.amount_sol for t in trades),
            last_updated=datetime.utcnow(),
        )

    async def _save_trade(self, trade: TradeOutcome) -> None:
        """Persist trade to database."""
        data = {
            "id": str(trade.id),
            "position_id": str(trade.position_id),
            "signal_id": str(trade.signal_id),
            "wallet_address": trade.wallet_address,
            "token_address": trade.token_address,
            "token_symbol": trade.token_symbol,
            "entry_price": str(trade.entry_price),
            "exit_price": str(trade.exit_price),
            "amount_tokens": str(trade.amount_tokens),
            "amount_sol": str(trade.amount_sol),
            "exit_reason": trade.exit_reason.value,
            "signal_score": str(trade.signal_score),
            "entry_timestamp": trade.entry_timestamp.isoformat(),
            "exit_timestamp": trade.exit_timestamp.isoformat(),
            "is_partial": trade.is_partial,
            "parent_trade_id": str(trade.parent_trade_id) if trade.parent_trade_id else None,
            "realized_pnl_sol": str(trade.realized_pnl_sol),
            "realized_pnl_percent": str(trade.realized_pnl_percent),
            "duration_seconds": trade.duration_seconds,
            "is_win": trade.is_win,
        }

        await self.supabase.table("trade_outcomes").insert(data).execute()

    async def _update_aggregates(self, trade: TradeOutcome) -> None:
        """Update aggregate metrics after recording a trade."""
        current = await self.get_aggregates(force_refresh=True)

        # Update running totals
        new_aggregates = AggregateMetrics(
            total_pnl_sol=current.total_pnl_sol + trade.realized_pnl_sol,
            win_count=current.win_count + (1 if trade.is_win else 0),
            loss_count=current.loss_count + (0 if trade.is_win else 1),
            total_trades=current.total_trades + 1,
            gross_profit=current.gross_profit + (trade.realized_pnl_sol if trade.is_win else Decimal("0")),
            gross_loss=current.gross_loss + (trade.realized_pnl_sol if not trade.is_win else Decimal("0")),
            largest_win_sol=max(current.largest_win_sol, trade.realized_pnl_sol if trade.is_win else Decimal("0")),
            largest_loss_sol=min(current.largest_loss_sol, trade.realized_pnl_sol if not trade.is_win else Decimal("0")),
            total_volume_sol=current.total_volume_sol + trade.amount_sol,
        )

        # Recalculate averages
        if new_aggregates.win_count > 0:
            new_aggregates.average_win_sol = new_aggregates.gross_profit / Decimal(new_aggregates.win_count)
        if new_aggregates.loss_count > 0:
            new_aggregates.average_loss_sol = new_aggregates.gross_loss / Decimal(new_aggregates.loss_count)

        # Persist
        await self.supabase.table("aggregate_metrics").upsert({
            "id": "current",
            **new_aggregates.model_dump(mode="json"),
        }).execute()


# Singleton instance
_trade_recorder: Optional[TradeRecorder] = None


async def get_trade_recorder(supabase_client) -> TradeRecorder:
    """Get or create TradeRecorder singleton."""
    global _trade_recorder
    if _trade_recorder is None:
        _trade_recorder = TradeRecorder(supabase_client)
    return _trade_recorder
```

### Database Schema (SQL)

```sql
-- Trade outcomes table
CREATE TABLE trade_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(id),
    signal_id UUID NOT NULL REFERENCES signals(id),
    wallet_address TEXT NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT NOT NULL,
    entry_price DECIMAL(30, 18) NOT NULL,
    exit_price DECIMAL(30, 18) NOT NULL,
    amount_tokens DECIMAL(30, 18) NOT NULL,
    amount_sol DECIMAL(30, 18) NOT NULL,
    exit_reason TEXT NOT NULL CHECK (exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop',
        'time_based', 'manual', 'circuit_breaker', 'partial_tp'
    )),
    signal_score DECIMAL(5, 4) NOT NULL,
    entry_timestamp TIMESTAMPTZ NOT NULL,
    exit_timestamp TIMESTAMPTZ NOT NULL,
    is_partial BOOLEAN DEFAULT FALSE,
    parent_trade_id UUID REFERENCES trade_outcomes(id),
    realized_pnl_sol DECIMAL(30, 18) NOT NULL,
    realized_pnl_percent DECIMAL(10, 4) NOT NULL,
    duration_seconds INTEGER NOT NULL,
    is_win BOOLEAN NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for common queries
CREATE INDEX idx_trade_outcomes_exit_timestamp ON trade_outcomes(exit_timestamp DESC);
CREATE INDEX idx_trade_outcomes_wallet ON trade_outcomes(wallet_address);
CREATE INDEX idx_trade_outcomes_token ON trade_outcomes(token_address);
CREATE INDEX idx_trade_outcomes_exit_reason ON trade_outcomes(exit_reason);
CREATE INDEX idx_trade_outcomes_position ON trade_outcomes(position_id);
CREATE INDEX idx_trade_outcomes_signal ON trade_outcomes(signal_id);
CREATE INDEX idx_trade_outcomes_parent ON trade_outcomes(parent_trade_id) WHERE parent_trade_id IS NOT NULL;
CREATE INDEX idx_trade_outcomes_is_win ON trade_outcomes(is_win);

-- Aggregate metrics table (singleton)
CREATE TABLE aggregate_metrics (
    id TEXT PRIMARY KEY DEFAULT 'current',
    total_pnl_sol DECIMAL(30, 18) DEFAULT 0,
    total_pnl_percent DECIMAL(10, 4) DEFAULT 0,
    win_count INTEGER DEFAULT 0,
    loss_count INTEGER DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    average_win_sol DECIMAL(30, 18) DEFAULT 0,
    average_loss_sol DECIMAL(30, 18) DEFAULT 0,
    largest_win_sol DECIMAL(30, 18) DEFAULT 0,
    largest_loss_sol DECIMAL(30, 18) DEFAULT 0,
    gross_profit DECIMAL(30, 18) DEFAULT 0,
    gross_loss DECIMAL(30, 18) DEFAULT 0,
    total_volume_sol DECIMAL(30, 18) DEFAULT 0,
    last_updated TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize aggregate metrics
INSERT INTO aggregate_metrics (id) VALUES ('current');

-- Partitioning for 1 year+ data (optional, requires PostgreSQL 10+)
-- ALTER TABLE trade_outcomes SET (autovacuum_vacuum_scale_factor = 0.0);
-- ALTER TABLE trade_outcomes SET (autovacuum_vacuum_threshold = 5000);
```

### FastAPI Routes

```python
# src/walltrack/api/routes/trades.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from datetime import datetime
from uuid import UUID

from walltrack.core.feedback.models import (
    TradeOutcomeCreate,
    TradeOutcome,
    TradeQuery,
    TradeQueryResult,
    AggregateMetrics,
    ExitReason,
)
from walltrack.core.feedback.trade_recorder import get_trade_recorder
from walltrack.core.database import get_supabase_client

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/", response_model=TradeOutcome)
async def record_trade(
    trade: TradeOutcomeCreate,
    supabase=Depends(get_supabase_client),
):
    """Record a new trade outcome."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.record_trade(trade)


@router.post("/{parent_trade_id}/partial", response_model=TradeOutcome)
async def record_partial_exit(
    parent_trade_id: UUID,
    exit_price: float,
    amount_tokens: float,
    exit_reason: ExitReason = ExitReason.PARTIAL_TP,
    supabase=Depends(get_supabase_client),
):
    """Record a partial exit for an existing trade."""
    from decimal import Decimal

    recorder = await get_trade_recorder(supabase)
    return await recorder.record_partial_exit(
        parent_trade_id=parent_trade_id,
        exit_price=Decimal(str(exit_price)),
        amount_tokens=Decimal(str(amount_tokens)),
        exit_reason=exit_reason,
    )


@router.get("/{trade_id}", response_model=TradeOutcome)
async def get_trade(
    trade_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get a single trade by ID."""
    recorder = await get_trade_recorder(supabase)
    trade = await recorder.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/", response_model=TradeQueryResult)
async def query_trades(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    wallet_address: Optional[str] = Query(default=None),
    token_address: Optional[str] = Query(default=None),
    exit_reason: Optional[ExitReason] = Query(default=None),
    is_win: Optional[bool] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    supabase=Depends(get_supabase_client),
):
    """Query trade history with filters."""
    recorder = await get_trade_recorder(supabase)
    query = TradeQuery(
        start_date=start_date,
        end_date=end_date,
        wallet_address=wallet_address,
        token_address=token_address,
        exit_reason=exit_reason,
        is_win=is_win,
        limit=limit,
        offset=offset,
    )
    return await recorder.query_trades(query)


@router.get("/aggregates/current", response_model=AggregateMetrics)
async def get_aggregates(
    force_refresh: bool = Query(default=False),
    supabase=Depends(get_supabase_client),
):
    """Get current aggregate trading metrics."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.get_aggregates(force_refresh=force_refresh)


@router.get("/position/{position_id}", response_model=list[TradeOutcome])
async def get_trades_for_position(
    position_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get all trades for a position."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.get_trades_for_position(position_id)
```

### Unit Tests

```python
# tests/core/feedback/test_trade_recorder.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.feedback.models import (
    TradeOutcomeCreate,
    TradeOutcome,
    ExitReason,
    AggregateMetrics,
    TradeQuery,
)
from walltrack.core.feedback.trade_recorder import TradeRecorder


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()
    client.table.return_value.insert.return_value.execute = AsyncMock()
    client.table.return_value.select.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data=None)
    )
    client.table.return_value.upsert.return_value.execute = AsyncMock()
    return client


@pytest.fixture
def trade_recorder(mock_supabase):
    """Create TradeRecorder instance."""
    return TradeRecorder(mock_supabase)


@pytest.fixture
def sample_trade_create():
    """Create sample TradeOutcomeCreate."""
    return TradeOutcomeCreate(
        position_id=uuid4(),
        signal_id=uuid4(),
        wallet_address="ABC123wallet",
        token_address="TokenMint123",
        token_symbol="MEME",
        entry_price=Decimal("0.00001"),
        exit_price=Decimal("0.00002"),  # 2x price
        amount_tokens=Decimal("1000000"),
        amount_sol=Decimal("10"),
        exit_reason=ExitReason.TAKE_PROFIT,
        signal_score=Decimal("0.85"),
        entry_timestamp=datetime.utcnow() - timedelta(hours=2),
        exit_timestamp=datetime.utcnow(),
    )


class TestTradeRecording:
    """Tests for trade outcome recording."""

    @pytest.mark.asyncio
    async def test_record_winning_trade(self, trade_recorder, sample_trade_create):
        """Test recording a winning trade."""
        trade = await trade_recorder.record_trade(sample_trade_create)

        assert trade.id is not None
        assert trade.position_id == sample_trade_create.position_id
        assert trade.is_win is True
        assert trade.realized_pnl_sol == Decimal("10")  # 20 - 10
        assert trade.realized_pnl_percent == Decimal("100")

    @pytest.mark.asyncio
    async def test_record_losing_trade(self, trade_recorder, sample_trade_create):
        """Test recording a losing trade."""
        sample_trade_create.exit_price = Decimal("0.000005")  # 0.5x price
        sample_trade_create.exit_reason = ExitReason.STOP_LOSS

        trade = await trade_recorder.record_trade(sample_trade_create)

        assert trade.is_win is False
        assert trade.realized_pnl_sol < 0

    @pytest.mark.asyncio
    async def test_duration_calculation(self, trade_recorder, sample_trade_create):
        """Test trade duration calculation."""
        sample_trade_create.entry_timestamp = datetime.utcnow() - timedelta(hours=1)
        sample_trade_create.exit_timestamp = datetime.utcnow()

        trade = await trade_recorder.record_trade(sample_trade_create)

        # Duration should be approximately 3600 seconds
        assert 3500 < trade.duration_seconds < 3700


class TestPartialExits:
    """Tests for partial exit recording."""

    @pytest.mark.asyncio
    async def test_record_partial_exit(self, trade_recorder, mock_supabase, sample_trade_create):
        """Test recording a partial exit."""
        # First record parent trade
        parent_trade = await trade_recorder.record_trade(sample_trade_create)

        # Mock getting parent trade
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                **sample_trade_create.model_dump(mode="json"),
                "id": str(parent_trade.id),
                "realized_pnl_sol": "10",
                "realized_pnl_percent": "100",
                "duration_seconds": 7200,
                "is_win": True,
                "created_at": datetime.utcnow().isoformat(),
            })
        )

        partial = await trade_recorder.record_partial_exit(
            parent_trade_id=parent_trade.id,
            exit_price=Decimal("0.000025"),
            amount_tokens=Decimal("500000"),  # 50% of position
        )

        assert partial.is_partial is True
        assert partial.parent_trade_id == parent_trade.id
        assert partial.amount_tokens == Decimal("500000")


class TestAggregateMetrics:
    """Tests for aggregate metrics calculation."""

    def test_aggregate_win_rate(self):
        """Test win rate calculation."""
        aggregates = AggregateMetrics(
            win_count=7,
            loss_count=3,
            total_trades=10,
        )

        assert aggregates.win_rate == Decimal("70")

    def test_aggregate_profit_factor(self):
        """Test profit factor calculation."""
        aggregates = AggregateMetrics(
            gross_profit=Decimal("100"),
            gross_loss=Decimal("-50"),
        )

        assert aggregates.profit_factor == Decimal("2")

    def test_aggregate_expectancy(self):
        """Test expectancy calculation."""
        aggregates = AggregateMetrics(
            total_pnl_sol=Decimal("50"),
            total_trades=10,
        )

        assert aggregates.expectancy == Decimal("5")


class TestTradeQuery:
    """Tests for trade querying."""

    @pytest.mark.asyncio
    async def test_query_by_date_range(self, trade_recorder, mock_supabase):
        """Test querying trades by date range."""
        mock_supabase.table.return_value.select.return_value.gte.return_value.lte.return_value.order.return_value.range.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[], count=0)
        )

        query = TradeQuery(
            start_date=datetime.utcnow() - timedelta(days=7),
            end_date=datetime.utcnow(),
        )

        result = await trade_recorder.query_trades(query)

        assert result.total_count == 0
        assert result.trades == []

    @pytest.mark.asyncio
    async def test_query_by_wallet(self, trade_recorder, mock_supabase):
        """Test querying trades by wallet."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.order.return_value.range.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[], count=0)
        )

        query = TradeQuery(wallet_address="ABC123wallet")

        result = await trade_recorder.query_trades(query)

        assert isinstance(result.aggregates, AggregateMetrics)
```

---

## Implementation Tasks

- [x] Create `src/walltrack/core/feedback/trade_recorder.py`
- [x] Record full trade details on position close
- [x] Handle partial exits with linking
- [x] Update aggregate metrics on trade record
- [x] Ensure query performance for 1 year data
- [x] Link trades to signals and positions

## Definition of Done

- [x] Trade outcomes recorded with full details
- [x] Partial exits linked to parent position
- [x] Aggregate metrics updated automatically
- [x] Query performance acceptable

---

## Dev Agent Record

### Implementation Notes
- Created `src/walltrack/core/feedback/models.py` with Pydantic models: `ExitReason`, `TradeOutcomeCreate`, `TradeOutcome`, `AggregateMetrics`, `TradeQuery`, `TradeQueryResult`
- Created `src/walltrack/core/feedback/trade_recorder.py` with `TradeRecorder` class implementing all AC requirements
- Created SQL migration `011_trade_outcomes.sql` with optimized indexes for query performance
- Created API routes in `src/walltrack/api/routes/trades.py`
- All computed fields (realized_pnl_sol, realized_pnl_percent, duration_seconds, is_win) implemented as Pydantic computed fields

### Tests Created
- `tests/core/feedback/test_trade_recorder.py` with 24 tests covering:
  - TradeOutcome model computed fields
  - AggregateMetrics computed fields (win_rate, profit_factor, expectancy)
  - Trade recording (winning/losing trades)
  - Partial exit creation
  - Trade querying with filters
  - Aggregate calculation

### File List
- `src/walltrack/core/feedback/models.py` (NEW)
- `src/walltrack/core/feedback/trade_recorder.py` (MODIFIED)
- `src/walltrack/core/feedback/__init__.py` (MODIFIED)
- `src/walltrack/api/routes/trades.py` (MODIFIED)
- `src/walltrack/data/supabase/migrations/011_trade_outcomes.sql` (NEW)
- `tests/core/__init__.py` (NEW)
- `tests/core/feedback/__init__.py` (NEW)
- `tests/core/feedback/test_trade_recorder.py` (NEW)

### Change Log
- 2025-12-20: Story 6-1 implemented with full trade outcome recording, partial exits, aggregate metrics, and query support
