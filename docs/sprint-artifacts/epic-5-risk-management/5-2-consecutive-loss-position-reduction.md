# Story 5.2: Consecutive Loss Position Size Reduction

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: ready
- **Priority**: Medium
- **FR**: FR29

## User Story

**As an** operator,
**I want** position size reduced after consecutive losses,
**So that** losing streaks don't drain capital quickly.

## Acceptance Criteria

### AC 1: Loss Tracking
**Given** trade outcome is recorded
**When** outcome is a loss
**Then** consecutive_loss_count is incremented

### AC 2: Position Size Reduction
**Given** consecutive_loss_count reaches threshold (default 3)
**When** next trade is sized
**Then** position size is reduced by configured factor (default 50%)
**And** reduction is logged with reason

### AC 3: Recovery
**Given** reduced position sizing is active
**When** a trade is profitable
**Then** consecutive_loss_count resets to 0
**And** position sizing returns to normal
**And** recovery is logged

### AC 4: Critical Threshold
**Given** consecutive losses continue after reduction
**When** loss count reaches critical threshold (e.g., 5)
**Then** additional reduction or full pause may trigger
**And** operator is alerted

## Technical Notes

- FR29: Reduce position size after consecutive losses
- Implement in `src/walltrack/core/risk/position_limits.py`
- Track consecutive_loss_count per system (not per wallet)

## Implementation Tasks

- [ ] Create `src/walltrack/core/risk/position_limits.py`
- [ ] Track consecutive loss count
- [ ] Implement position size reduction at threshold
- [ ] Reset on profitable trade
- [ ] Implement critical threshold handling
- [ ] Log all reductions and recoveries

## Definition of Done

- [ ] Consecutive losses tracked correctly
- [ ] Position size reduced at threshold
- [ ] Recovery resets to normal sizing
- [ ] Critical threshold alerts operator

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/risk/models.py (additions)
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, List


class TradeOutcome(str, Enum):
    """Result of a completed trade."""
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class SizingMode(str, Enum):
    """Position sizing mode."""
    NORMAL = "normal"
    REDUCED = "reduced"
    CRITICAL = "critical"
    PAUSED = "paused"


class ConsecutiveLossConfig(BaseModel):
    """Configuration for consecutive loss position reduction."""
    reduction_threshold: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of consecutive losses before reduction"
    )
    reduction_factor: Decimal = Field(
        default=Decimal("0.5"),
        gt=Decimal("0"),
        lt=Decimal("1"),
        description="Factor to multiply position size (0.5 = 50% reduction)"
    )
    critical_threshold: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Number of consecutive losses for critical mode"
    )
    critical_action: str = Field(
        default="pause",
        description="Action at critical threshold: 'pause' or 'further_reduce'"
    )
    further_reduction_factor: Decimal = Field(
        default=Decimal("0.25"),
        description="Factor for further reduction at critical threshold"
    )

    class Config:
        json_encoders = {Decimal: str}


class TradeResult(BaseModel):
    """Record of a trade result for tracking."""
    trade_id: str
    closed_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: TradeOutcome
    pnl_percent: Decimal
    pnl_absolute: Decimal
    entry_price: Decimal
    exit_price: Decimal
    token_address: str


class ConsecutiveLossState(BaseModel):
    """Current state of consecutive loss tracking."""
    consecutive_loss_count: int = Field(default=0, ge=0)
    sizing_mode: SizingMode = Field(default=SizingMode.NORMAL)
    current_size_factor: Decimal = Field(default=Decimal("1.0"))
    last_trade_outcome: Optional[TradeOutcome] = None
    streak_started_at: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def is_reduced(self) -> bool:
        """Whether position sizing is currently reduced."""
        return self.sizing_mode != SizingMode.NORMAL

    @computed_field
    @property
    def reduction_percent(self) -> Decimal:
        """Current reduction as percentage."""
        return (Decimal("1") - self.current_size_factor) * Decimal("100")


class SizeAdjustmentResult(BaseModel):
    """Result of a position size adjustment."""
    original_size: Decimal
    adjusted_size: Decimal
    size_factor: Decimal
    sizing_mode: SizingMode
    consecutive_losses: int
    reason: str


class LossStreakEvent(BaseModel):
    """Event record for loss streak changes."""
    id: Optional[str] = None
    event_type: str  # "reduction_triggered", "critical_triggered", "recovery"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    consecutive_losses: int
    previous_mode: SizingMode
    new_mode: SizingMode
    previous_factor: Decimal
    new_factor: Decimal
    triggering_trade_id: Optional[str] = None
```

### ConsecutiveLossManager Service

```python
# src/walltrack/core/risk/consecutive_loss.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional
from supabase import AsyncClient

from walltrack.core.risk.models import (
    TradeOutcome,
    SizingMode,
    ConsecutiveLossConfig,
    TradeResult,
    ConsecutiveLossState,
    SizeAdjustmentResult,
    LossStreakEvent,
    CircuitBreakerType,
    SystemStatus
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class ConsecutiveLossManager:
    """
    Manages position size reduction based on consecutive losses.

    Tracks loss streaks and adjusts position sizing to protect capital.
    """

    def __init__(self, config: ConsecutiveLossConfig):
        self.config = config
        self._supabase: Optional[AsyncClient] = None
        self._state = ConsecutiveLossState()

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load state from database on startup."""
        db = await self._get_db()

        result = await db.table("system_config").select("value").eq(
            "key", "consecutive_loss_state"
        ).single().execute()

        if result.data:
            self._state = ConsecutiveLossState(**result.data["value"])

        logger.info(
            "consecutive_loss_manager_initialized",
            loss_count=self._state.consecutive_loss_count,
            sizing_mode=self._state.sizing_mode.value,
            size_factor=str(self._state.current_size_factor)
        )

    async def record_trade_outcome(self, result: TradeResult) -> ConsecutiveLossState:
        """
        Record a trade outcome and update loss streak.

        Args:
            result: The trade result to record

        Returns:
            Updated consecutive loss state
        """
        db = await self._get_db()

        previous_state = self._state.model_copy()

        if result.outcome == TradeOutcome.LOSS:
            await self._handle_loss(result)
        elif result.outcome == TradeOutcome.WIN:
            await self._handle_win(result)
        # BREAKEVEN doesn't affect streak

        self._state.last_trade_outcome = result.outcome
        self._state.last_updated = datetime.utcnow()

        # Persist state
        await self._save_state()

        # Log state change if mode changed
        if previous_state.sizing_mode != self._state.sizing_mode:
            await self._record_event(
                event_type="mode_change",
                previous_state=previous_state,
                triggering_trade_id=result.trade_id
            )

        return self._state

    async def _handle_loss(self, result: TradeResult) -> None:
        """Handle a losing trade."""
        self._state.consecutive_loss_count += 1

        # Start streak tracking if first loss
        if self._state.streak_started_at is None:
            self._state.streak_started_at = datetime.utcnow()

        logger.info(
            "consecutive_loss_recorded",
            count=self._state.consecutive_loss_count,
            trade_id=result.trade_id
        )

        # Check critical threshold first
        if self._state.consecutive_loss_count >= self.config.critical_threshold:
            await self._enter_critical_mode(result)

        # Check reduction threshold
        elif self._state.consecutive_loss_count >= self.config.reduction_threshold:
            await self._enter_reduced_mode(result)

    async def _handle_win(self, result: TradeResult) -> None:
        """Handle a winning trade - resets streak."""
        if self._state.consecutive_loss_count > 0:
            logger.info(
                "loss_streak_broken",
                previous_count=self._state.consecutive_loss_count,
                trade_id=result.trade_id
            )

            previous_state = self._state.model_copy()

            # Reset to normal
            self._state.consecutive_loss_count = 0
            self._state.sizing_mode = SizingMode.NORMAL
            self._state.current_size_factor = Decimal("1.0")
            self._state.streak_started_at = None

            # Record recovery event
            await self._record_event(
                event_type="recovery",
                previous_state=previous_state,
                triggering_trade_id=result.trade_id
            )

    async def _enter_reduced_mode(self, result: TradeResult) -> None:
        """Enter reduced position sizing mode."""
        if self._state.sizing_mode == SizingMode.NORMAL:
            self._state.sizing_mode = SizingMode.REDUCED
            self._state.current_size_factor = self.config.reduction_factor

            logger.warning(
                "consecutive_loss_reduction_triggered",
                count=self._state.consecutive_loss_count,
                factor=str(self.config.reduction_factor)
            )

    async def _enter_critical_mode(self, result: TradeResult) -> None:
        """Enter critical mode at critical threshold."""
        db = await self._get_db()

        if self.config.critical_action == "pause":
            self._state.sizing_mode = SizingMode.PAUSED
            self._state.current_size_factor = Decimal("0")

            # Update system status
            await db.table("system_config").upsert({
                "key": "system_status",
                "value": SystemStatus.PAUSED_CONSECUTIVE_LOSS.value,
                "updated_at": datetime.utcnow().isoformat()
            }).execute()

            logger.error(
                "consecutive_loss_critical_pause",
                count=self._state.consecutive_loss_count,
                threshold=self.config.critical_threshold
            )

        else:  # further_reduce
            self._state.sizing_mode = SizingMode.CRITICAL
            self._state.current_size_factor = self.config.further_reduction_factor

            logger.error(
                "consecutive_loss_critical_reduction",
                count=self._state.consecutive_loss_count,
                factor=str(self.config.further_reduction_factor)
            )

        # Create circuit breaker trigger record
        await db.table("circuit_breaker_triggers").insert({
            "breaker_type": CircuitBreakerType.CONSECUTIVE_LOSS.value,
            "threshold_value": str(self.config.critical_threshold),
            "actual_value": str(self._state.consecutive_loss_count),
            "capital_at_trigger": "0",  # Will be updated by caller
            "peak_capital_at_trigger": "0"
        }).execute()

    async def _save_state(self) -> None:
        """Persist current state to database."""
        db = await self._get_db()

        await db.table("system_config").upsert({
            "key": "consecutive_loss_state",
            "value": self._state.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def _record_event(
        self,
        event_type: str,
        previous_state: ConsecutiveLossState,
        triggering_trade_id: Optional[str] = None
    ) -> None:
        """Record a loss streak event."""
        db = await self._get_db()

        event = LossStreakEvent(
            event_type=event_type,
            consecutive_losses=self._state.consecutive_loss_count,
            previous_mode=previous_state.sizing_mode,
            new_mode=self._state.sizing_mode,
            previous_factor=previous_state.current_size_factor,
            new_factor=self._state.current_size_factor,
            triggering_trade_id=triggering_trade_id
        )

        await db.table("loss_streak_events").insert(
            event.model_dump(exclude={"id"}, mode="json")
        ).execute()

    def calculate_adjusted_size(
        self,
        base_size: Decimal
    ) -> SizeAdjustmentResult:
        """
        Calculate adjusted position size based on current state.

        Args:
            base_size: The base position size before adjustment

        Returns:
            Size adjustment result with adjusted size and reason
        """
        adjusted = base_size * self._state.current_size_factor

        # Determine reason
        if self._state.sizing_mode == SizingMode.PAUSED:
            reason = f"Trading paused after {self._state.consecutive_loss_count} consecutive losses"
        elif self._state.sizing_mode == SizingMode.CRITICAL:
            reason = f"Critical reduction ({self._state.consecutive_loss_count} losses): {self._state.reduction_percent}% smaller"
        elif self._state.sizing_mode == SizingMode.REDUCED:
            reason = f"Reduced sizing ({self._state.consecutive_loss_count} losses): {self._state.reduction_percent}% smaller"
        else:
            reason = "Normal sizing"

        return SizeAdjustmentResult(
            original_size=base_size,
            adjusted_size=adjusted,
            size_factor=self._state.current_size_factor,
            sizing_mode=self._state.sizing_mode,
            consecutive_losses=self._state.consecutive_loss_count,
            reason=reason
        )

    async def manual_reset(self, operator_id: str) -> ConsecutiveLossState:
        """
        Manually reset the consecutive loss counter.

        Args:
            operator_id: ID of operator performing reset

        Returns:
            Reset state
        """
        db = await self._get_db()

        previous_state = self._state.model_copy()

        self._state.consecutive_loss_count = 0
        self._state.sizing_mode = SizingMode.NORMAL
        self._state.current_size_factor = Decimal("1.0")
        self._state.streak_started_at = None
        self._state.last_updated = datetime.utcnow()

        await self._save_state()

        # Reset system status if paused
        await db.table("system_config").upsert({
            "key": "system_status",
            "value": SystemStatus.RUNNING.value,
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

        # Mark circuit breaker as reset
        await db.table("circuit_breaker_triggers").update({
            "reset_at": datetime.utcnow().isoformat(),
            "reset_by": operator_id
        }).eq("breaker_type", CircuitBreakerType.CONSECUTIVE_LOSS.value).is_(
            "reset_at", "null"
        ).execute()

        await self._record_event(
            event_type="manual_reset",
            previous_state=previous_state
        )

        logger.info(
            "consecutive_loss_manual_reset",
            operator_id=operator_id,
            previous_count=previous_state.consecutive_loss_count
        )

        return self._state

    @property
    def state(self) -> ConsecutiveLossState:
        """Get current state."""
        return self._state

    @property
    def can_trade(self) -> bool:
        """Whether trading is currently allowed."""
        return self._state.sizing_mode != SizingMode.PAUSED


# Singleton instance
_loss_manager: Optional[ConsecutiveLossManager] = None


async def get_consecutive_loss_manager(
    config: Optional[ConsecutiveLossConfig] = None
) -> ConsecutiveLossManager:
    """Get or create consecutive loss manager singleton."""
    global _loss_manager

    if _loss_manager is None:
        if config is None:
            db = await get_supabase_client()
            result = await db.table("system_config").select("value").eq(
                "key", "consecutive_loss_config"
            ).single().execute()
            config = ConsecutiveLossConfig(**result.data["value"])

        _loss_manager = ConsecutiveLossManager(config)
        await _loss_manager.initialize()

    return _loss_manager
```

### Database Schema (Supabase)

```sql
-- Loss streak events for audit trail
CREATE TABLE loss_streak_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(50) NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    consecutive_losses INTEGER NOT NULL,
    previous_mode VARCHAR(50) NOT NULL,
    new_mode VARCHAR(50) NOT NULL,
    previous_factor DECIMAL(5, 4) NOT NULL,
    new_factor DECIMAL(5, 4) NOT NULL,
    triggering_trade_id VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_loss_streak_events_date ON loss_streak_events(occurred_at DESC);
CREATE INDEX idx_loss_streak_events_type ON loss_streak_events(event_type);

-- Insert default consecutive loss config
INSERT INTO system_config (key, value) VALUES
('consecutive_loss_config', '{
    "reduction_threshold": 3,
    "reduction_factor": "0.5",
    "critical_threshold": 5,
    "critical_action": "pause",
    "further_reduction_factor": "0.25"
}'),
('consecutive_loss_state', '{
    "consecutive_loss_count": 0,
    "sizing_mode": "normal",
    "current_size_factor": "1.0",
    "last_trade_outcome": null,
    "streak_started_at": null
}')
ON CONFLICT (key) DO NOTHING;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/risk.py (additions)
from walltrack.core.risk.consecutive_loss import (
    get_consecutive_loss_manager,
    ConsecutiveLossManager
)
from walltrack.core.risk.models import (
    ConsecutiveLossConfig,
    ConsecutiveLossState,
    TradeResult,
    SizeAdjustmentResult
)


class SizeCalculationRequest(BaseModel):
    base_size: Decimal


@router.get("/consecutive-loss/state", response_model=ConsecutiveLossState)
async def get_consecutive_loss_state(
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager)
):
    """Get current consecutive loss state."""
    return manager.state


@router.post("/consecutive-loss/record", response_model=ConsecutiveLossState)
async def record_trade_outcome(
    result: TradeResult,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager)
):
    """Record a trade outcome and update loss streak."""
    return await manager.record_trade_outcome(result)


@router.post("/consecutive-loss/calculate-size", response_model=SizeAdjustmentResult)
async def calculate_adjusted_size(
    request: SizeCalculationRequest,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager)
):
    """Calculate adjusted position size based on current streak."""
    return manager.calculate_adjusted_size(request.base_size)


@router.post("/consecutive-loss/reset")
async def reset_consecutive_loss(
    operator_id: str,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager)
):
    """Manually reset consecutive loss counter."""
    state = await manager.manual_reset(operator_id)
    return {"status": "reset", "state": state}


@router.put("/consecutive-loss/config")
async def update_consecutive_loss_config(
    config: ConsecutiveLossConfig,
    manager: ConsecutiveLossManager = Depends(get_consecutive_loss_manager)
):
    """Update consecutive loss configuration."""
    db = await manager._get_db()

    await db.table("system_config").upsert({
        "key": "consecutive_loss_config",
        "value": config.model_dump(mode="json")
    }).execute()

    manager.config = config
    return {"status": "updated", "config": config}
```

### Unit Tests

```python
# tests/unit/risk/test_consecutive_loss.py
import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.models import (
    TradeOutcome,
    SizingMode,
    ConsecutiveLossConfig,
    TradeResult,
    ConsecutiveLossState
)
from walltrack.core.risk.consecutive_loss import ConsecutiveLossManager


@pytest.fixture
def loss_config():
    return ConsecutiveLossConfig(
        reduction_threshold=3,
        reduction_factor=Decimal("0.5"),
        critical_threshold=5,
        critical_action="pause"
    )


@pytest.fixture
def manager(loss_config):
    return ConsecutiveLossManager(loss_config)


@pytest.fixture
def losing_trade():
    return TradeResult(
        trade_id="trade-001",
        outcome=TradeOutcome.LOSS,
        pnl_percent=Decimal("-10.0"),
        pnl_absolute=Decimal("-50.0"),
        entry_price=Decimal("100.0"),
        exit_price=Decimal("90.0"),
        token_address="0xabc123"
    )


@pytest.fixture
def winning_trade():
    return TradeResult(
        trade_id="trade-002",
        outcome=TradeOutcome.WIN,
        pnl_percent=Decimal("20.0"),
        pnl_absolute=Decimal("100.0"),
        entry_price=Decimal("100.0"),
        exit_price=Decimal("120.0"),
        token_address="0xabc123"
    )


class TestLossTracking:
    """Test consecutive loss tracking."""

    @pytest.mark.asyncio
    async def test_first_loss_starts_count(self, manager, losing_trade):
        """First loss starts the counter."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.record_trade_outcome(losing_trade)

            assert state.consecutive_loss_count == 1
            assert state.sizing_mode == SizingMode.NORMAL
            assert state.streak_started_at is not None

    @pytest.mark.asyncio
    async def test_consecutive_losses_increment(self, manager, losing_trade):
        """Consecutive losses increment counter."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            await manager.record_trade_outcome(losing_trade)
            state = await manager.record_trade_outcome(losing_trade)

            assert state.consecutive_loss_count == 2


class TestPositionSizeReduction:
    """Test position size reduction logic."""

    @pytest.mark.asyncio
    async def test_reduction_at_threshold(self, manager, losing_trade):
        """Position size reduced at threshold."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            # Record 3 losses (threshold)
            for _ in range(3):
                state = await manager.record_trade_outcome(losing_trade)

            assert state.sizing_mode == SizingMode.REDUCED
            assert state.current_size_factor == Decimal("0.5")

    def test_size_calculation_reduced(self, manager):
        """Size calculation applies reduction factor."""
        manager._state.sizing_mode = SizingMode.REDUCED
        manager._state.current_size_factor = Decimal("0.5")
        manager._state.consecutive_loss_count = 3

        result = manager.calculate_adjusted_size(Decimal("100.0"))

        assert result.adjusted_size == Decimal("50.0")
        assert result.size_factor == Decimal("0.5")
        assert "Reduced" in result.reason


class TestCriticalThreshold:
    """Test critical threshold handling."""

    @pytest.mark.asyncio
    async def test_critical_pause(self, manager, losing_trade):
        """Critical threshold pauses trading."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [{}]

        with patch.object(manager, '_get_db', return_value=mock_db):
            # Record 5 losses (critical threshold)
            for _ in range(5):
                state = await manager.record_trade_outcome(losing_trade)

            assert state.sizing_mode == SizingMode.PAUSED
            assert state.current_size_factor == Decimal("0")
            assert manager.can_trade is False


class TestRecovery:
    """Test recovery on winning trade."""

    @pytest.mark.asyncio
    async def test_win_resets_streak(self, manager, losing_trade, winning_trade):
        """Winning trade resets loss streak."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(manager, '_get_db', return_value=mock_db):
            # Record 3 losses
            for _ in range(3):
                await manager.record_trade_outcome(losing_trade)

            # Win resets
            state = await manager.record_trade_outcome(winning_trade)

            assert state.consecutive_loss_count == 0
            assert state.sizing_mode == SizingMode.NORMAL
            assert state.current_size_factor == Decimal("1.0")
            assert manager.can_trade is True


class TestManualReset:
    """Test manual reset functionality."""

    @pytest.mark.asyncio
    async def test_manual_reset_clears_state(self, manager):
        """Manual reset clears all state."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        manager._state.consecutive_loss_count = 5
        manager._state.sizing_mode = SizingMode.PAUSED

        with patch.object(manager, '_get_db', return_value=mock_db):
            state = await manager.manual_reset("operator-1")

            assert state.consecutive_loss_count == 0
            assert state.sizing_mode == SizingMode.NORMAL
            assert manager.can_trade is True
```
