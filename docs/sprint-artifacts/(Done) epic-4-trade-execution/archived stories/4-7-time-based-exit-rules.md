# Story 4.7: Time-Based Exit Rules

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: Medium
- **FR**: FR26

## User Story

**As an** operator,
**I want** time-based exit rules,
**So that** capital isn't stuck in stagnant positions.

## Acceptance Criteria

### AC 1: Max Hold Duration
**Given** position with time_rules in strategy
**When** max_hold_hours is configured
**Then** position age is tracked
**And** if age exceeds max_hold_hours, position is closed
**And** exit_reason = "max_hold_duration"

### AC 2: Stagnation Exit
**Given** stagnation_exit enabled
**When** price movement over stagnation_hours < stagnation_threshold
**Then** position is flagged as stagnant
**And** position is closed
**And** exit_reason = "stagnation"

### AC 3: Time Check Integration
**Given** time rules are checked
**When** monitoring loop runs
**Then** time checks occur alongside price checks
**And** time-based exits are logged with duration and price movement

### AC 4: Profitable Stagnation
**Given** position is profitable but stagnant
**When** stagnation exit triggers
**Then** current profit is captured
**And** capital is freed for new opportunities

## Technical Notes

- FR26: Apply time-based exit rules
- Implement in `src/walltrack/core/execution/exit_manager.py`
- Track position_opened_at timestamp

## Implementation Tasks

- [ ] Add time tracking to positions
- [ ] Implement max hold duration check
- [ ] Implement stagnation detection
- [ ] Calculate price movement over time window
- [ ] Execute time-based exits
- [ ] Log duration and movement on exit

## Definition of Done

- [ ] Max hold duration triggers exit
- [ ] Stagnation detected and exits position
- [ ] Time checks run alongside price checks
- [ ] Exit reasons logged correctly

---

## Technical Specifications

### Data Models

```python
# src/walltrack/core/execution/models/time_rules.py
"""Time-based exit rule models."""

from datetime import datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator


class TimeExitReason(StrEnum):
    """Time-based exit reasons."""

    MAX_HOLD_DURATION = "max_hold_duration"
    STAGNATION = "stagnation"


class TimeRulesConfig(BaseModel):
    """Configuration for time-based exit rules."""

    # Max hold duration
    max_hold_hours: int | None = Field(
        default=None,
        ge=1,
        le=720,  # Max 30 days
        description="Maximum hours to hold position before forced exit"
    )

    # Stagnation detection
    stagnation_exit_enabled: bool = Field(
        default=False,
        description="Enable stagnation-based exits"
    )
    stagnation_hours: int = Field(
        default=6,
        ge=1,
        le=168,  # Max 1 week
        description="Hours to measure price movement for stagnation"
    )
    stagnation_threshold_percentage: Decimal = Field(
        default=Decimal("5.0"),
        ge=Decimal("1.0"),
        le=Decimal("50.0"),
        description="Minimum price movement % to avoid stagnation flag"
    )

    @field_validator("stagnation_threshold_percentage", mode="before")
    @classmethod
    def coerce_to_decimal(cls, v):
        return Decimal(str(v)) if v is not None else v


class PositionTimeInfo(BaseModel):
    """Time-related information for a position."""

    position_id: str
    opened_at: datetime
    current_time: datetime = Field(default_factory=datetime.utcnow)

    # Calculated fields
    hours_held: float = Field(description="Hours since position opened")
    time_remaining_hours: float | None = Field(
        None,
        description="Hours until max hold duration (if configured)"
    )

    # Stagnation tracking
    stagnation_window_start: datetime | None = None
    price_at_window_start: Decimal | None = None
    current_price: Decimal | None = None
    price_movement_percentage: Decimal | None = None
    is_stagnant: bool = False

    @classmethod
    def calculate(
        cls,
        position_id: str,
        opened_at: datetime,
        max_hold_hours: int | None = None,
        stagnation_data: dict | None = None,
    ) -> "PositionTimeInfo":
        """Calculate time info for a position."""
        now = datetime.utcnow()
        hours_held = (now - opened_at).total_seconds() / 3600

        time_remaining = None
        if max_hold_hours:
            time_remaining = max(0, max_hold_hours - hours_held)

        info = cls(
            position_id=position_id,
            opened_at=opened_at,
            current_time=now,
            hours_held=hours_held,
            time_remaining_hours=time_remaining,
        )

        if stagnation_data:
            info.stagnation_window_start = stagnation_data.get("window_start")
            info.price_at_window_start = stagnation_data.get("price_at_start")
            info.current_price = stagnation_data.get("current_price")
            info.price_movement_percentage = stagnation_data.get("movement_pct")
            info.is_stagnant = stagnation_data.get("is_stagnant", False)

        return info


class TimeExitCheck(BaseModel):
    """Result of time-based exit check."""

    position_id: str
    should_exit: bool = False
    exit_reason: TimeExitReason | None = None

    # Duration info
    hours_held: float
    max_hold_hours: int | None = None

    # Stagnation info
    is_stagnant: bool = False
    stagnation_hours: int | None = None
    price_movement_percentage: Decimal | None = None
    stagnation_threshold: Decimal | None = None

    # For profitable stagnation exits
    current_price: Decimal | None = None
    entry_price: Decimal | None = None
    unrealized_pnl_percentage: Decimal | None = None


class StagnationWindow(BaseModel):
    """Price tracking window for stagnation detection."""

    position_id: str
    window_start: datetime
    window_hours: int
    price_at_start: Decimal
    prices_sampled: list[tuple[datetime, Decimal]] = Field(default_factory=list)

    def add_price(self, price: Decimal) -> None:
        """Add price sample to window."""
        self.prices_sampled.append((datetime.utcnow(), price))

    def calculate_movement(self, current_price: Decimal) -> Decimal:
        """Calculate price movement percentage from window start."""
        if self.price_at_start == 0:
            return Decimal("0")

        movement = abs(current_price - self.price_at_start)
        return (movement / self.price_at_start) * Decimal("100")

    def is_window_complete(self) -> bool:
        """Check if stagnation window has elapsed."""
        elapsed = datetime.utcnow() - self.window_start
        return elapsed >= timedelta(hours=self.window_hours)
```

### Time-Based Exit Service

```python
# src/walltrack/core/execution/time_exit_manager.py
"""Time-based exit rule management."""

import structlog
from datetime import datetime, timedelta
from decimal import Decimal

from walltrack.core.execution.models.time_rules import (
    TimeRulesConfig,
    TimeExitCheck,
    TimeExitReason,
    PositionTimeInfo,
    StagnationWindow,
)
from walltrack.core.execution.models.position import Position

logger = structlog.get_logger(__name__)


class TimeExitManager:
    """Manages time-based exit rules for positions.

    Handles:
    1. Max hold duration - forced exit after N hours
    2. Stagnation detection - exit if price movement < threshold over window
    """

    def __init__(self) -> None:
        # Track stagnation windows per position
        self._stagnation_windows: dict[str, StagnationWindow] = {}

    def initialize_for_position(
        self,
        position: Position,
        config: TimeRulesConfig,
    ) -> None:
        """Initialize time tracking for a new position."""

        if config.stagnation_exit_enabled:
            window = StagnationWindow(
                position_id=position.id,
                window_start=position.entry_time,
                window_hours=config.stagnation_hours,
                price_at_start=position.entry_price,
            )
            self._stagnation_windows[position.id] = window

            logger.info(
                "stagnation_tracking_initialized",
                position_id=position.id,
                window_hours=config.stagnation_hours,
                threshold_pct=float(config.stagnation_threshold_percentage),
            )

    def check_time_exits(
        self,
        position: Position,
        config: TimeRulesConfig,
        current_price: Decimal,
    ) -> TimeExitCheck:
        """Check all time-based exit conditions.

        Returns exit decision with detailed info for logging.
        """
        now = datetime.utcnow()
        hours_held = (now - position.entry_time).total_seconds() / 3600

        result = TimeExitCheck(
            position_id=position.id,
            hours_held=hours_held,
            max_hold_hours=config.max_hold_hours,
            current_price=current_price,
            entry_price=position.entry_price,
        )

        # Calculate unrealized PnL for logging
        if position.entry_price > 0:
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            result.unrealized_pnl_percentage = pnl_pct

        # 1. Check max hold duration
        if config.max_hold_hours and hours_held >= config.max_hold_hours:
            result.should_exit = True
            result.exit_reason = TimeExitReason.MAX_HOLD_DURATION

            logger.info(
                "max_hold_duration_triggered",
                position_id=position.id,
                hours_held=hours_held,
                max_hours=config.max_hold_hours,
                current_price=float(current_price),
                unrealized_pnl_pct=float(result.unrealized_pnl_percentage or 0),
            )

            return result

        # 2. Check stagnation
        if config.stagnation_exit_enabled:
            stagnation_result = self._check_stagnation(
                position,
                config,
                current_price,
            )

            if stagnation_result.is_stagnant:
                result.should_exit = True
                result.exit_reason = TimeExitReason.STAGNATION
                result.is_stagnant = True
                result.stagnation_hours = config.stagnation_hours
                result.price_movement_percentage = stagnation_result.price_movement_percentage
                result.stagnation_threshold = config.stagnation_threshold_percentage

                logger.info(
                    "stagnation_exit_triggered",
                    position_id=position.id,
                    hours_held=hours_held,
                    stagnation_hours=config.stagnation_hours,
                    price_movement_pct=float(stagnation_result.price_movement_percentage or 0),
                    threshold_pct=float(config.stagnation_threshold_percentage),
                    current_price=float(current_price),
                    unrealized_pnl_pct=float(result.unrealized_pnl_percentage or 0),
                )

                return result

        return result

    def _check_stagnation(
        self,
        position: Position,
        config: TimeRulesConfig,
        current_price: Decimal,
    ) -> TimeExitCheck:
        """Check if position is stagnant."""

        result = TimeExitCheck(
            position_id=position.id,
            hours_held=0,  # Will be filled by caller
            stagnation_hours=config.stagnation_hours,
            stagnation_threshold=config.stagnation_threshold_percentage,
        )

        window = self._stagnation_windows.get(position.id)

        if not window:
            # Initialize window if not exists
            window = StagnationWindow(
                position_id=position.id,
                window_start=datetime.utcnow(),
                window_hours=config.stagnation_hours,
                price_at_start=current_price,
            )
            self._stagnation_windows[position.id] = window
            return result

        # Add current price sample
        window.add_price(current_price)

        # Check if window has elapsed
        if not window.is_window_complete():
            return result

        # Calculate price movement
        movement_pct = window.calculate_movement(current_price)
        result.price_movement_percentage = movement_pct

        # Check if stagnant
        if movement_pct < config.stagnation_threshold_percentage:
            result.is_stagnant = True

            logger.debug(
                "stagnation_detected",
                position_id=position.id,
                movement_pct=float(movement_pct),
                threshold_pct=float(config.stagnation_threshold_percentage),
                window_hours=config.stagnation_hours,
            )
        else:
            # Reset window for next check period
            self._reset_stagnation_window(position.id, current_price, config.stagnation_hours)

        return result

    def _reset_stagnation_window(
        self,
        position_id: str,
        current_price: Decimal,
        window_hours: int,
    ) -> None:
        """Reset stagnation window for new period."""

        self._stagnation_windows[position_id] = StagnationWindow(
            position_id=position_id,
            window_start=datetime.utcnow(),
            window_hours=window_hours,
            price_at_start=current_price,
        )

    def get_time_info(
        self,
        position: Position,
        config: TimeRulesConfig,
        current_price: Decimal,
    ) -> PositionTimeInfo:
        """Get detailed time information for a position."""

        stagnation_data = None
        window = self._stagnation_windows.get(position.id)

        if window:
            movement = window.calculate_movement(current_price)
            stagnation_data = {
                "window_start": window.window_start,
                "price_at_start": window.price_at_start,
                "current_price": current_price,
                "movement_pct": movement,
                "is_stagnant": movement < config.stagnation_threshold_percentage
                    if window.is_window_complete() else False,
            }

        return PositionTimeInfo.calculate(
            position_id=position.id,
            opened_at=position.entry_time,
            max_hold_hours=config.max_hold_hours,
            stagnation_data=stagnation_data,
        )

    def remove_position(self, position_id: str) -> None:
        """Remove time tracking for closed position."""
        self._stagnation_windows.pop(position_id, None)


# Singleton instance
_time_exit_manager: TimeExitManager | None = None


def get_time_exit_manager() -> TimeExitManager:
    """Get time exit manager singleton."""
    global _time_exit_manager
    if _time_exit_manager is None:
        _time_exit_manager = TimeExitManager()
    return _time_exit_manager
```

### Integration with Exit Manager

```python
# src/walltrack/core/execution/exit_manager.py (time check additions)
"""Exit manager integration with time-based rules."""

from walltrack.core.execution.time_exit_manager import (
    get_time_exit_manager,
    TimeExitReason,
)


class ExitManager:
    """Enhanced exit manager with time-based checks."""

    async def check_all_exit_conditions(
        self,
        position: Position,
        current_price: Decimal,
    ) -> ExitDecision:
        """Check all exit conditions: price-based AND time-based."""

        # 1. Check price-based exits first (stop-loss, take-profit, trailing)
        price_decision = await self.check_price_exit_conditions(position, current_price)

        if price_decision.should_exit:
            return price_decision

        # 2. Check time-based exits
        time_mgr = get_time_exit_manager()
        time_rules = position.exit_strategy.time_rules

        if time_rules:
            time_check = time_mgr.check_time_exits(
                position,
                time_rules,
                current_price,
            )

            if time_check.should_exit:
                return ExitDecision(
                    should_exit=True,
                    exit_reason=time_check.exit_reason.value,
                    sell_percentage=100,  # Full exit on time-based triggers
                    trigger_price=current_price,
                    metadata={
                        "hours_held": time_check.hours_held,
                        "max_hold_hours": time_check.max_hold_hours,
                        "is_stagnant": time_check.is_stagnant,
                        "price_movement_pct": float(time_check.price_movement_percentage or 0),
                        "unrealized_pnl_pct": float(time_check.unrealized_pnl_percentage or 0),
                    },
                )

        return ExitDecision(should_exit=False)
```

### Database Schema

```sql
-- Add time tracking columns to positions
ALTER TABLE positions ADD COLUMN IF NOT EXISTS time_rules JSONB DEFAULT NULL;
ALTER TABLE positions ADD COLUMN IF NOT EXISTS stagnation_tracking JSONB DEFAULT NULL;

-- Time-based exit events log
CREATE TABLE IF NOT EXISTS time_exit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES positions(id),
    exit_reason VARCHAR(30) NOT NULL, -- 'max_hold_duration', 'stagnation'

    -- Duration info
    hours_held DECIMAL(10, 2) NOT NULL,
    max_hold_hours INTEGER,

    -- Stagnation info
    stagnation_hours INTEGER,
    price_movement_percentage DECIMAL(10, 4),
    stagnation_threshold DECIMAL(10, 4),

    -- Profit at exit
    current_price DECIMAL(20, 10) NOT NULL,
    entry_price DECIMAL(20, 10) NOT NULL,
    unrealized_pnl_percentage DECIMAL(10, 4),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_time_exits_position ON time_exit_events(position_id);
CREATE INDEX idx_time_exits_reason ON time_exit_events(exit_reason);
CREATE INDEX idx_time_exits_date ON time_exit_events(created_at);
```

### Unit Tests

```python
# tests/unit/core/execution/test_time_exit_manager.py
"""Tests for time-based exit rules."""

import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch

from walltrack.core.execution.time_exit_manager import TimeExitManager
from walltrack.core.execution.models.time_rules import (
    TimeRulesConfig,
    TimeExitReason,
)
from walltrack.core.execution.models.position import Position


@pytest.fixture
def manager():
    return TimeExitManager()


@pytest.fixture
def position():
    return Position(
        id="pos-001",
        wallet_id="wallet-001",
        token_mint="TOKEN123",
        entry_price=Decimal("1.00"),
        amount=Decimal("1000"),
        entry_time=datetime.utcnow(),
    )


@pytest.fixture
def time_config():
    return TimeRulesConfig(
        max_hold_hours=24,
        stagnation_exit_enabled=True,
        stagnation_hours=6,
        stagnation_threshold_percentage=Decimal("5.0"),
    )


class TestMaxHoldDuration:
    """Test max hold duration exits."""

    def test_no_exit_before_max_hold(self, manager, position, time_config):
        """Test no exit when within max hold duration."""
        # Position just opened
        result = manager.check_time_exits(position, time_config, Decimal("1.50"))

        assert not result.should_exit
        assert result.hours_held < 24

    def test_exit_at_max_hold(self, manager, time_config):
        """Test exit when max hold duration reached."""
        # Position opened 25 hours ago
        old_position = Position(
            id="pos-002",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=25),
        )

        result = manager.check_time_exits(old_position, time_config, Decimal("1.50"))

        assert result.should_exit
        assert result.exit_reason == TimeExitReason.MAX_HOLD_DURATION
        assert result.hours_held >= 24

    def test_profitable_max_hold_exit(self, manager, time_config):
        """Test max hold exit captures profit info."""
        old_position = Position(
            id="pos-003",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=30),
        )

        # Price is up 50%
        result = manager.check_time_exits(old_position, time_config, Decimal("1.50"))

        assert result.should_exit
        assert result.unrealized_pnl_percentage == Decimal("50")

    def test_no_max_hold_when_disabled(self, manager, position):
        """Test no max hold check when not configured."""
        config = TimeRulesConfig(max_hold_hours=None)

        # Even with old position
        old_position = Position(
            id="pos-004",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=1000),
        )

        result = manager.check_time_exits(old_position, config, Decimal("1.00"))

        assert not result.should_exit


class TestStagnationDetection:
    """Test stagnation-based exits."""

    def test_no_stagnation_before_window(self, manager, position, time_config):
        """Test no stagnation exit before window completes."""
        manager.initialize_for_position(position, time_config)

        # Immediately check (window not complete)
        result = manager.check_time_exits(position, time_config, Decimal("1.00"))

        assert not result.should_exit
        assert not result.is_stagnant

    def test_stagnation_detected(self, manager, time_config):
        """Test stagnation detected when price movement < threshold."""
        # Position opened 7 hours ago (past 6-hour window)
        old_position = Position(
            id="pos-005",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=7),
        )

        manager.initialize_for_position(old_position, time_config)

        # Manually set window start to be in the past
        window = manager._stagnation_windows[old_position.id]
        window.window_start = datetime.utcnow() - timedelta(hours=7)

        # Price only moved 2% (below 5% threshold)
        result = manager.check_time_exits(old_position, time_config, Decimal("1.02"))

        assert result.should_exit
        assert result.exit_reason == TimeExitReason.STAGNATION
        assert result.is_stagnant
        assert result.price_movement_percentage == Decimal("2")

    def test_no_stagnation_with_movement(self, manager, time_config):
        """Test no stagnation when price moves enough."""
        old_position = Position(
            id="pos-006",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=7),
        )

        manager.initialize_for_position(old_position, time_config)
        window = manager._stagnation_windows[old_position.id]
        window.window_start = datetime.utcnow() - timedelta(hours=7)

        # Price moved 10% (above 5% threshold)
        result = manager.check_time_exits(old_position, time_config, Decimal("1.10"))

        assert not result.should_exit
        assert not result.is_stagnant

    def test_stagnation_with_profit(self, manager, time_config):
        """Test stagnation exit can still be profitable."""
        old_position = Position(
            id="pos-007",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=10),
        )

        manager.initialize_for_position(old_position, time_config)
        window = manager._stagnation_windows[old_position.id]
        # Window starts at a higher price (position was already up)
        window.window_start = datetime.utcnow() - timedelta(hours=7)
        window.price_at_start = Decimal("1.48")  # Was up 48%

        # Now at 1.50 (only 1.35% move in window - stagnant)
        result = manager.check_time_exits(old_position, time_config, Decimal("1.50"))

        assert result.should_exit
        assert result.is_stagnant
        # Still profitable from entry
        assert result.unrealized_pnl_percentage == Decimal("50")

    def test_stagnation_disabled(self, manager, position):
        """Test no stagnation check when disabled."""
        config = TimeRulesConfig(
            stagnation_exit_enabled=False,
            stagnation_hours=6,
        )

        result = manager.check_time_exits(position, config, Decimal("1.00"))

        assert not result.should_exit
        assert not result.is_stagnant


class TestPositionTimeInfo:
    """Test time info calculation."""

    def test_time_info_calculation(self, manager, time_config):
        """Test detailed time info calculation."""
        position = Position(
            id="pos-008",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=12),
        )

        manager.initialize_for_position(position, time_config)

        info = manager.get_time_info(position, time_config, Decimal("1.20"))

        assert info.hours_held >= 12
        assert info.time_remaining_hours <= 12  # 24 - 12
        assert info.position_id == position.id

    def test_time_remaining_at_limit(self, manager, time_config):
        """Test time remaining at limit."""
        position = Position(
            id="pos-009",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=24),
        )

        info = manager.get_time_info(position, time_config, Decimal("1.00"))

        assert info.time_remaining_hours == 0


class TestEdgeCases:
    """Test edge cases."""

    def test_remove_position(self, manager, position, time_config):
        """Test removing position tracking."""
        manager.initialize_for_position(position, time_config)

        assert position.id in manager._stagnation_windows

        manager.remove_position(position.id)

        assert position.id not in manager._stagnation_windows

    def test_max_hold_takes_precedence(self, manager):
        """Test max hold duration triggers before stagnation check."""
        config = TimeRulesConfig(
            max_hold_hours=12,
            stagnation_exit_enabled=True,
            stagnation_hours=6,
            stagnation_threshold_percentage=Decimal("5.0"),
        )

        old_position = Position(
            id="pos-010",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("1.00"),
            amount=Decimal("1000"),
            entry_time=datetime.utcnow() - timedelta(hours=13),
        )

        result = manager.check_time_exits(old_position, config, Decimal("1.00"))

        # Should be max hold, not stagnation
        assert result.should_exit
        assert result.exit_reason == TimeExitReason.MAX_HOLD_DURATION

    def test_zero_entry_price_handling(self, manager, time_config):
        """Test handling of zero entry price."""
        position = Position(
            id="pos-011",
            wallet_id="wallet-001",
            token_mint="TOKEN123",
            entry_price=Decimal("0"),  # Edge case
            amount=Decimal("1000"),
            entry_time=datetime.utcnow(),
        )

        # Should not crash
        result = manager.check_time_exits(position, time_config, Decimal("1.00"))

        assert not result.should_exit
```
