# Story 4.9: Position Tracking and Status

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR24

## User Story

**As an** operator,
**I want** all open positions tracked with current status,
**So that** I have visibility into active trades.

## Acceptance Criteria

### AC 1: Position Creation
**Given** a trade is executed
**When** position is created
**Then** position record includes:
- position_id, wallet, token, entry_price, amount, entry_time
- signal_id (link to originating signal)
- exit_strategy_id, current stop/TP levels
- status: "open"

### AC 2: Status Query
**Given** open position
**When** status is queried
**Then** current price is fetched
**And** unrealized PnL is calculated
**And** current profit multiplier is shown (e.g., x1.5)
**And** time held is displayed

### AC 3: Partial Close
**Given** position is partially closed
**When** take-profit level is hit
**Then** partial_exits array is updated
**And** remaining_amount is recalculated
**And** realized PnL for that portion is recorded

### AC 4: Full Close
**Given** position is fully closed
**When** final exit occurs
**Then** status changes to "closed"
**And** total realized PnL is calculated
**And** position remains in history

## Technical Notes

- FR24: Track all open positions and their current status
- Implement positions table in Supabase
- Create `trade_repo.py` in `src/walltrack/data/supabase/repositories/`

## Implementation Tasks

- [ ] Create positions table schema in Supabase
- [ ] Create `src/walltrack/data/supabase/repositories/trade_repo.py`
- [ ] Implement position creation on trade
- [ ] Link positions to signals
- [ ] Calculate unrealized PnL
- [ ] Track partial exits
- [ ] Calculate realized PnL on close

## Definition of Done

- [ ] Positions created on trade execution
- [ ] Status includes PnL and multiplier
- [ ] Partial exits tracked correctly
- [ ] Full close calculates total PnL

---

## Technical Specifications

### Data Models

```python
# src/walltrack/core/execution/models/position.py
"""Position tracking models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field, computed_field
from typing import Any


class PositionStatus(StrEnum):
    """Position lifecycle status."""

    OPEN = "open"
    PARTIALLY_CLOSED = "partially_closed"
    CLOSED = "closed"


class PartialExit(BaseModel):
    """Record of a partial position exit."""

    id: str
    exit_time: datetime
    amount_sold: Decimal
    exit_price: Decimal
    exit_reason: str  # "take_profit", "trailing_stop", etc.

    # PnL for this partial exit
    realized_pnl: Decimal
    realized_pnl_percentage: Decimal

    # Context
    level_index: int | None = None  # For take-profit levels
    metadata: dict[str, Any] = Field(default_factory=dict)


class Position(BaseModel):
    """Active or closed trading position."""

    id: str
    wallet_id: str
    token_mint: str
    token_symbol: str | None = None

    # Entry info
    entry_price: Decimal
    entry_amount: Decimal = Field(description="Original amount bought")
    entry_time: datetime
    entry_tx_signature: str | None = None

    # Current state
    status: PositionStatus = PositionStatus.OPEN
    remaining_amount: Decimal = Field(description="Amount still held")

    # Strategy
    signal_id: str
    signal_score: Decimal
    exit_strategy_id: str
    exit_strategy: Any | None = None  # ExitStrategy object

    # Partial exits
    partial_exits: list[PartialExit] = Field(default_factory=list)

    # Full close info (when status = CLOSED)
    closed_at: datetime | None = None
    final_exit_reason: str | None = None
    final_exit_price: Decimal | None = None
    final_exit_tx: str | None = None

    # Tracking
    peak_price: Decimal | None = None
    peak_multiplier: Decimal | None = None

    @computed_field
    @property
    def is_moonbag(self) -> bool:
        """Check if position is in moonbag state."""
        if self.status != PositionStatus.OPEN:
            return False
        # Moonbag if remaining is significantly less than entry
        return self.remaining_amount < self.entry_amount * Decimal("0.5")

    def calculate_unrealized_pnl(self, current_price: Decimal) -> tuple[Decimal, Decimal]:
        """Calculate unrealized PnL for remaining position.

        Returns (pnl_amount, pnl_percentage).
        """
        if self.remaining_amount == 0:
            return Decimal("0"), Decimal("0")

        current_value = self.remaining_amount * current_price
        cost_basis = self.remaining_amount * self.entry_price
        pnl = current_value - cost_basis

        pnl_pct = (pnl / cost_basis) * 100 if cost_basis > 0 else Decimal("0")

        return pnl, pnl_pct

    def calculate_realized_pnl(self) -> tuple[Decimal, Decimal]:
        """Calculate total realized PnL from partial exits.

        Returns (total_pnl, weighted_avg_pnl_percentage).
        """
        if not self.partial_exits:
            return Decimal("0"), Decimal("0")

        total_pnl = sum(pe.realized_pnl for pe in self.partial_exits)
        total_sold = sum(pe.amount_sold for pe in self.partial_exits)

        if total_sold == 0:
            return Decimal("0"), Decimal("0")

        # Weighted average PnL percentage
        weighted_sum = sum(
            pe.realized_pnl_percentage * pe.amount_sold
            for pe in self.partial_exits
        )
        avg_pnl_pct = weighted_sum / total_sold

        return total_pnl, avg_pnl_pct

    def calculate_multiplier(self, current_price: Decimal) -> Decimal:
        """Calculate current profit multiplier (e.g., x2.5)."""
        if self.entry_price == 0:
            return Decimal("1")
        return current_price / self.entry_price


class PositionStatusResponse(BaseModel):
    """Full position status for API/dashboard."""

    position: Position

    # Current market data
    current_price: Decimal
    current_time: datetime = Field(default_factory=datetime.utcnow)

    # Calculated metrics
    unrealized_pnl: Decimal
    unrealized_pnl_percentage: Decimal
    realized_pnl: Decimal
    realized_pnl_percentage: Decimal
    total_pnl: Decimal

    multiplier: Decimal
    time_held_hours: float

    # Exit strategy status
    next_tp_level: int | None = None
    stop_loss_price: Decimal | None = None
    trailing_stop_active: bool = False
    trailing_stop_level: Decimal | None = None


class PositionSummary(BaseModel):
    """Lightweight position summary for lists."""

    id: str
    token_symbol: str
    entry_price: Decimal
    current_price: Decimal
    pnl_percentage: Decimal
    multiplier: Decimal
    status: PositionStatus
    time_held_hours: float
    exit_strategy_name: str
```

### Position Repository

```python
# src/walltrack/data/supabase/repositories/trade_repo.py
"""Trade and position repository."""

import structlog
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from walltrack.data.supabase.client import get_supabase_client
from walltrack.core.execution.models.position import (
    Position,
    PositionStatus,
    PartialExit,
)

logger = structlog.get_logger(__name__)


class TradeRepository:
    """Repository for position and trade data."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    async def create_position(self, position: Position) -> Position:
        """Create a new position record."""
        client = await self._get_client()

        data = {
            "id": position.id,
            "wallet_id": position.wallet_id,
            "token_mint": position.token_mint,
            "token_symbol": position.token_symbol,
            "entry_price": str(position.entry_price),
            "entry_amount": str(position.entry_amount),
            "remaining_amount": str(position.remaining_amount),
            "entry_time": position.entry_time.isoformat(),
            "entry_tx_signature": position.entry_tx_signature,
            "status": position.status.value,
            "signal_id": position.signal_id,
            "signal_score": str(position.signal_score),
            "exit_strategy_id": position.exit_strategy_id,
            "partial_exits": [],
        }

        result = await client.table("positions").insert(data).execute()

        logger.info(
            "position_created",
            position_id=position.id,
            token=position.token_mint,
            entry_price=float(position.entry_price),
            amount=float(position.entry_amount),
        )

        return position

    async def get_by_id(self, position_id: str) -> Optional[Position]:
        """Get position by ID."""
        client = await self._get_client()

        result = await client.table("positions").select("*").eq("id", position_id).execute()

        if not result.data:
            return None

        return self._to_position(result.data[0])

    async def get_open_positions(self, wallet_id: str | None = None) -> list[Position]:
        """Get all open positions, optionally filtered by wallet."""
        client = await self._get_client()

        query = client.table("positions").select("*").neq("status", "closed")

        if wallet_id:
            query = query.eq("wallet_id", wallet_id)

        result = await query.order("entry_time", desc=True).execute()

        return [self._to_position(row) for row in result.data]

    async def get_closed_positions(
        self,
        wallet_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Position]:
        """Get closed positions with pagination."""
        client = await self._get_client()

        query = client.table("positions").select("*").eq("status", "closed")

        if wallet_id:
            query = query.eq("wallet_id", wallet_id)

        result = await query.order("closed_at", desc=True).range(offset, offset + limit - 1).execute()

        return [self._to_position(row) for row in result.data]

    async def add_partial_exit(
        self,
        position_id: str,
        partial_exit: PartialExit,
    ) -> Position:
        """Add a partial exit to a position."""
        client = await self._get_client()

        # Get current position
        position = await self.get_by_id(position_id)
        if not position:
            raise ValueError(f"Position not found: {position_id}")

        # Add partial exit
        position.partial_exits.append(partial_exit)
        position.remaining_amount -= partial_exit.amount_sold

        # Update status if needed
        if position.remaining_amount <= 0:
            position.status = PositionStatus.CLOSED
            position.closed_at = partial_exit.exit_time
            position.final_exit_reason = partial_exit.exit_reason
            position.final_exit_price = partial_exit.exit_price
        elif len(position.partial_exits) > 0:
            position.status = PositionStatus.PARTIALLY_CLOSED

        # Save to DB
        update_data = {
            "remaining_amount": str(position.remaining_amount),
            "status": position.status.value,
            "partial_exits": [pe.model_dump(mode="json") for pe in position.partial_exits],
            "closed_at": position.closed_at.isoformat() if position.closed_at else None,
            "final_exit_reason": position.final_exit_reason,
            "final_exit_price": str(position.final_exit_price) if position.final_exit_price else None,
        }

        await client.table("positions").update(update_data).eq("id", position_id).execute()

        logger.info(
            "partial_exit_recorded",
            position_id=position_id,
            amount_sold=float(partial_exit.amount_sold),
            exit_price=float(partial_exit.exit_price),
            realized_pnl=float(partial_exit.realized_pnl),
            remaining=float(position.remaining_amount),
            status=position.status.value,
        )

        return position

    async def close_position(
        self,
        position_id: str,
        exit_price: Decimal,
        exit_reason: str,
        exit_tx: str | None = None,
    ) -> Position:
        """Fully close a position."""
        client = await self._get_client()

        position = await self.get_by_id(position_id)
        if not position:
            raise ValueError(f"Position not found: {position_id}")

        # Create final partial exit for remaining amount
        final_exit = PartialExit(
            id=str(uuid4()),
            exit_time=datetime.utcnow(),
            amount_sold=position.remaining_amount,
            exit_price=exit_price,
            exit_reason=exit_reason,
            realized_pnl=(exit_price - position.entry_price) * position.remaining_amount,
            realized_pnl_percentage=((exit_price - position.entry_price) / position.entry_price) * 100,
        )

        position.partial_exits.append(final_exit)
        position.remaining_amount = Decimal("0")
        position.status = PositionStatus.CLOSED
        position.closed_at = datetime.utcnow()
        position.final_exit_reason = exit_reason
        position.final_exit_price = exit_price
        position.final_exit_tx = exit_tx

        # Calculate total realized PnL
        total_pnl, avg_pnl_pct = position.calculate_realized_pnl()

        update_data = {
            "remaining_amount": "0",
            "status": "closed",
            "partial_exits": [pe.model_dump(mode="json") for pe in position.partial_exits],
            "closed_at": position.closed_at.isoformat(),
            "final_exit_reason": exit_reason,
            "final_exit_price": str(exit_price),
            "final_exit_tx": exit_tx,
        }

        await client.table("positions").update(update_data).eq("id", position_id).execute()

        logger.info(
            "position_closed",
            position_id=position_id,
            exit_reason=exit_reason,
            exit_price=float(exit_price),
            total_realized_pnl=float(total_pnl),
            avg_pnl_pct=float(avg_pnl_pct),
        )

        return position

    async def update_peak_price(
        self,
        position_id: str,
        peak_price: Decimal,
        entry_price: Decimal,
    ) -> None:
        """Update position's peak price tracking."""
        client = await self._get_client()

        multiplier = peak_price / entry_price if entry_price > 0 else Decimal("1")

        await client.table("positions").update({
            "peak_price": str(peak_price),
            "peak_multiplier": str(multiplier),
        }).eq("id", position_id).execute()

    def _to_position(self, row: dict) -> Position:
        """Convert database row to Position model."""
        partial_exits = [
            PartialExit(**pe) for pe in (row.get("partial_exits") or [])
        ]

        return Position(
            id=row["id"],
            wallet_id=row["wallet_id"],
            token_mint=row["token_mint"],
            token_symbol=row.get("token_symbol"),
            entry_price=Decimal(row["entry_price"]),
            entry_amount=Decimal(row["entry_amount"]),
            remaining_amount=Decimal(row["remaining_amount"]),
            entry_time=datetime.fromisoformat(row["entry_time"]),
            entry_tx_signature=row.get("entry_tx_signature"),
            status=PositionStatus(row["status"]),
            signal_id=row["signal_id"],
            signal_score=Decimal(row["signal_score"]),
            exit_strategy_id=row["exit_strategy_id"],
            partial_exits=partial_exits,
            closed_at=datetime.fromisoformat(row["closed_at"]) if row.get("closed_at") else None,
            final_exit_reason=row.get("final_exit_reason"),
            final_exit_price=Decimal(row["final_exit_price"]) if row.get("final_exit_price") else None,
            final_exit_tx=row.get("final_exit_tx"),
            peak_price=Decimal(row["peak_price"]) if row.get("peak_price") else None,
            peak_multiplier=Decimal(row["peak_multiplier"]) if row.get("peak_multiplier") else None,
        )


# Singleton
_trade_repo: TradeRepository | None = None


async def get_trade_repo() -> TradeRepository:
    """Get trade repository singleton."""
    global _trade_repo
    if _trade_repo is None:
        _trade_repo = TradeRepository()
    return _trade_repo
```

### Position Status Service

```python
# src/walltrack/core/execution/position_status.py
"""Position status calculation service."""

import structlog
from datetime import datetime
from decimal import Decimal

from walltrack.core.execution.models.position import (
    Position,
    PositionStatusResponse,
    PositionSummary,
)
from walltrack.core.pricing.price_service import get_price_service
from walltrack.core.execution.trailing_stop import get_trailing_stop_manager
from walltrack.core.execution.level_calculator import LevelCalculator
from walltrack.data.supabase.repositories.trade_repo import get_trade_repo

logger = structlog.get_logger(__name__)


class PositionStatusService:
    """Service for calculating position status and metrics."""

    def __init__(self):
        self._level_calculator = LevelCalculator()

    async def get_position_status(self, position_id: str) -> PositionStatusResponse | None:
        """Get full status for a position."""
        repo = await get_trade_repo()
        position = await repo.get_by_id(position_id)

        if not position:
            return None

        # Get current price
        price_service = get_price_service()
        current_price = await price_service.get_price(position.token_mint)

        return self._build_status_response(position, current_price)

    async def get_all_open_positions(
        self,
        wallet_id: str | None = None,
    ) -> list[PositionStatusResponse]:
        """Get status for all open positions."""
        repo = await get_trade_repo()
        positions = await repo.get_open_positions(wallet_id)

        # Get prices for all tokens
        price_service = get_price_service()
        token_mints = list(set(p.token_mint for p in positions))
        prices = await price_service.get_prices(token_mints)

        statuses = []
        for position in positions:
            current_price = prices.get(position.token_mint, position.entry_price)
            statuses.append(self._build_status_response(position, current_price))

        return statuses

    async def get_position_summaries(
        self,
        wallet_id: str | None = None,
    ) -> list[PositionSummary]:
        """Get lightweight summaries for listing."""
        statuses = await self.get_all_open_positions(wallet_id)

        return [
            PositionSummary(
                id=s.position.id,
                token_symbol=s.position.token_symbol or s.position.token_mint[:8],
                entry_price=s.position.entry_price,
                current_price=s.current_price,
                pnl_percentage=s.unrealized_pnl_percentage,
                multiplier=s.multiplier,
                status=s.position.status,
                time_held_hours=s.time_held_hours,
                exit_strategy_name=s.position.exit_strategy_id,
            )
            for s in statuses
        ]

    def _build_status_response(
        self,
        position: Position,
        current_price: Decimal,
    ) -> PositionStatusResponse:
        """Build full status response for a position."""
        now = datetime.utcnow()

        # Calculate PnL
        unrealized_pnl, unrealized_pnl_pct = position.calculate_unrealized_pnl(current_price)
        realized_pnl, realized_pnl_pct = position.calculate_realized_pnl()
        total_pnl = unrealized_pnl + realized_pnl

        # Calculate time held
        time_held = (now - position.entry_time).total_seconds() / 3600

        # Calculate multiplier
        multiplier = position.calculate_multiplier(current_price)

        # Get exit strategy levels
        next_tp_level = None
        stop_loss_price = None
        trailing_stop_active = False
        trailing_stop_level = None

        if position.exit_strategy:
            levels = self._level_calculator.calculate(position, position.exit_strategy)
            stop_loss_price = levels.stop_loss.price

            # Find next untriggered TP level
            triggered_count = len(position.partial_exits)
            if triggered_count < len(levels.take_profit_levels):
                next_tp_level = triggered_count

            # Check trailing stop status
            ts_manager = get_trailing_stop_manager()
            ts_status = ts_manager.get_status(position.id)
            if ts_status:
                trailing_stop_active = ts_status.state.value == "active"
                trailing_stop_level = ts_status.trailing_stop_level

        return PositionStatusResponse(
            position=position,
            current_price=current_price,
            current_time=now,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percentage=unrealized_pnl_pct,
            realized_pnl=realized_pnl,
            realized_pnl_percentage=realized_pnl_pct,
            total_pnl=total_pnl,
            multiplier=multiplier,
            time_held_hours=time_held,
            next_tp_level=next_tp_level,
            stop_loss_price=stop_loss_price,
            trailing_stop_active=trailing_stop_active,
            trailing_stop_level=trailing_stop_level,
        )


# Singleton
_position_status_service: PositionStatusService | None = None


def get_position_status_service() -> PositionStatusService:
    """Get position status service singleton."""
    global _position_status_service
    if _position_status_service is None:
        _position_status_service = PositionStatusService()
    return _position_status_service
```

### Database Schema

```sql
-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    wallet_id UUID NOT NULL REFERENCES wallets(id),
    token_mint VARCHAR(100) NOT NULL,
    token_symbol VARCHAR(20),

    -- Entry info
    entry_price DECIMAL(20, 10) NOT NULL,
    entry_amount DECIMAL(20, 10) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,
    entry_tx_signature VARCHAR(100),

    -- Current state
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    remaining_amount DECIMAL(20, 10) NOT NULL,

    -- Strategy
    signal_id UUID NOT NULL REFERENCES signals(id),
    signal_score DECIMAL(5, 4) NOT NULL,
    exit_strategy_id VARCHAR(100) NOT NULL,
    strategy_assignment JSONB,

    -- Partial exits
    partial_exits JSONB DEFAULT '[]',

    -- Close info
    closed_at TIMESTAMPTZ,
    final_exit_reason VARCHAR(50),
    final_exit_price DECIMAL(20, 10),
    final_exit_tx VARCHAR(100),

    -- Peak tracking
    peak_price DECIMAL(20, 10),
    peak_multiplier DECIMAL(10, 4),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_positions_wallet ON positions(wallet_id);
CREATE INDEX idx_positions_status ON positions(status);
CREATE INDEX idx_positions_token ON positions(token_mint);
CREATE INDEX idx_positions_signal ON positions(signal_id);
CREATE INDEX idx_positions_entry_time ON positions(entry_time DESC);
CREATE INDEX idx_positions_closed_at ON positions(closed_at DESC) WHERE closed_at IS NOT NULL;

-- Trigger to update updated_at
CREATE OR REPLACE FUNCTION update_positions_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER positions_updated_at
    BEFORE UPDATE ON positions
    FOR EACH ROW
    EXECUTE FUNCTION update_positions_updated_at();
```

### Unit Tests

```python
# tests/unit/core/execution/test_position_tracking.py
"""Tests for position tracking and status."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from walltrack.core.execution.models.position import (
    Position,
    PositionStatus,
    PartialExit,
)


@pytest.fixture
def position():
    return Position(
        id="pos-001",
        wallet_id="wallet-001",
        token_mint="TOKEN123",
        token_symbol="TEST",
        entry_price=Decimal("1.00"),
        entry_amount=Decimal("1000"),
        remaining_amount=Decimal("1000"),
        entry_time=datetime.utcnow() - timedelta(hours=5),
        signal_id="sig-001",
        signal_score=Decimal("0.85"),
        exit_strategy_id="preset-balanced",
    )


class TestPositionPnLCalculation:
    """Test PnL calculation methods."""

    def test_unrealized_pnl_profit(self, position):
        """Test unrealized PnL calculation when profitable."""
        current_price = Decimal("1.50")  # Up 50%

        pnl, pnl_pct = position.calculate_unrealized_pnl(current_price)

        assert pnl == Decimal("500")  # 1000 * (1.50 - 1.00)
        assert pnl_pct == Decimal("50")

    def test_unrealized_pnl_loss(self, position):
        """Test unrealized PnL calculation when at loss."""
        current_price = Decimal("0.70")  # Down 30%

        pnl, pnl_pct = position.calculate_unrealized_pnl(current_price)

        assert pnl == Decimal("-300")
        assert pnl_pct == Decimal("-30")

    def test_unrealized_pnl_after_partial_exit(self, position):
        """Test unrealized PnL with remaining amount."""
        position.remaining_amount = Decimal("500")  # Half sold
        current_price = Decimal("2.00")  # Up 100%

        pnl, pnl_pct = position.calculate_unrealized_pnl(current_price)

        # PnL on remaining 500 tokens
        assert pnl == Decimal("500")  # 500 * (2.00 - 1.00)
        assert pnl_pct == Decimal("100")

    def test_realized_pnl_single_exit(self, position):
        """Test realized PnL with one partial exit."""
        position.partial_exits = [
            PartialExit(
                id="exit-1",
                exit_time=datetime.utcnow(),
                amount_sold=Decimal("500"),
                exit_price=Decimal("2.00"),
                exit_reason="take_profit",
                realized_pnl=Decimal("500"),  # 500 * (2.00 - 1.00)
                realized_pnl_percentage=Decimal("100"),
            )
        ]

        pnl, pnl_pct = position.calculate_realized_pnl()

        assert pnl == Decimal("500")
        assert pnl_pct == Decimal("100")

    def test_realized_pnl_multiple_exits(self, position):
        """Test realized PnL with multiple partial exits."""
        position.partial_exits = [
            PartialExit(
                id="exit-1",
                exit_time=datetime.utcnow(),
                amount_sold=Decimal("300"),
                exit_price=Decimal("2.00"),
                exit_reason="take_profit",
                realized_pnl=Decimal("300"),
                realized_pnl_percentage=Decimal("100"),  # 100% profit
            ),
            PartialExit(
                id="exit-2",
                exit_time=datetime.utcnow(),
                amount_sold=Decimal("200"),
                exit_price=Decimal("3.00"),
                exit_reason="take_profit",
                realized_pnl=Decimal("400"),
                realized_pnl_percentage=Decimal("200"),  # 200% profit
            ),
        ]

        pnl, pnl_pct = position.calculate_realized_pnl()

        assert pnl == Decimal("700")  # 300 + 400
        # Weighted avg: (100*300 + 200*200) / 500 = 140%
        assert pnl_pct == Decimal("140")


class TestPositionMultiplier:
    """Test multiplier calculation."""

    def test_multiplier_2x(self, position):
        """Test 2x multiplier calculation."""
        multiplier = position.calculate_multiplier(Decimal("2.00"))
        assert multiplier == Decimal("2")

    def test_multiplier_fractional(self, position):
        """Test fractional multiplier (loss)."""
        multiplier = position.calculate_multiplier(Decimal("0.50"))
        assert multiplier == Decimal("0.5")

    def test_multiplier_high(self, position):
        """Test high multiplier."""
        multiplier = position.calculate_multiplier(Decimal("10.00"))
        assert multiplier == Decimal("10")


class TestPositionStatus:
    """Test position status transitions."""

    def test_initial_status_open(self, position):
        """Test position starts as open."""
        assert position.status == PositionStatus.OPEN

    def test_status_partially_closed(self, position):
        """Test status changes to partially closed."""
        position.partial_exits.append(
            PartialExit(
                id="exit-1",
                exit_time=datetime.utcnow(),
                amount_sold=Decimal("500"),
                exit_price=Decimal("2.00"),
                exit_reason="take_profit",
                realized_pnl=Decimal("500"),
                realized_pnl_percentage=Decimal("100"),
            )
        )
        position.remaining_amount = Decimal("500")
        position.status = PositionStatus.PARTIALLY_CLOSED

        assert position.status == PositionStatus.PARTIALLY_CLOSED
        assert position.remaining_amount == Decimal("500")

    def test_is_moonbag(self, position):
        """Test moonbag detection."""
        assert position.is_moonbag is False

        # Sell down to 30%
        position.remaining_amount = Decimal("300")
        assert position.is_moonbag is True

        # Sell down to 50% - not moonbag
        position.remaining_amount = Decimal("500")
        assert position.is_moonbag is False

    def test_closed_position_not_moonbag(self, position):
        """Test closed position is never moonbag."""
        position.remaining_amount = Decimal("100")
        position.status = PositionStatus.CLOSED

        assert position.is_moonbag is False


class TestPartialExit:
    """Test partial exit model."""

    def test_partial_exit_creation(self):
        """Test creating a partial exit."""
        exit = PartialExit(
            id="exit-001",
            exit_time=datetime.utcnow(),
            amount_sold=Decimal("500"),
            exit_price=Decimal("2.00"),
            exit_reason="take_profit",
            realized_pnl=Decimal("500"),
            realized_pnl_percentage=Decimal("100"),
            level_index=0,
        )

        assert exit.amount_sold == Decimal("500")
        assert exit.exit_reason == "take_profit"
        assert exit.level_index == 0

    def test_partial_exit_with_metadata(self):
        """Test partial exit with extra metadata."""
        exit = PartialExit(
            id="exit-002",
            exit_time=datetime.utcnow(),
            amount_sold=Decimal("300"),
            exit_price=Decimal("1.50"),
            exit_reason="trailing_stop",
            realized_pnl=Decimal("150"),
            realized_pnl_percentage=Decimal("50"),
            metadata={
                "peak_price": 2.00,
                "profit_captured_pct": 75,
            },
        )

        assert exit.metadata["peak_price"] == 2.00
        assert exit.metadata["profit_captured_pct"] == 75
```
