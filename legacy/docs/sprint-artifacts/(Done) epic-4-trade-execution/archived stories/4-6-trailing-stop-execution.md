# Story 4.6: Trailing Stop Execution

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR25

## User Story

**As an** operator,
**I want** trailing stops to lock in profits as price rises,
**So that** I capture more upside while protecting gains.

## Acceptance Criteria

### AC 1: Activation
**Given** position with trailing stop enabled in strategy
**When** price reaches activation multiplier (e.g., x2)
**Then** trailing stop becomes active
**And** trailing stop level is set at (peak - distance%)

### AC 2: Ratcheting
**Given** active trailing stop
**When** price continues rising
**Then** peak price is updated
**And** trailing stop level rises with it (ratchets up)
**And** trailing stop NEVER decreases

### AC 3: Trigger
**Given** active trailing stop
**When** price drops below trailing stop level
**Then** position is sold (remaining after any take-profits)
**And** trade is recorded with exit_reason = "trailing_stop"
**And** actual exit price vs peak is logged

### AC 4: Regular Stop-Loss Precedence
**Given** trailing stop not yet activated
**When** price drops below regular stop-loss
**Then** regular stop-loss takes precedence
**And** position exits via stop-loss

## Technical Notes

- FR25: Execute trailing stop on active positions
- Implement in `src/walltrack/core/execution/trailing_stop.py`
- Track peak_price per position

## Implementation Tasks

- [ ] Create `src/walltrack/core/execution/trailing_stop.py`
- [ ] Implement activation trigger
- [ ] Track peak price per position
- [ ] Implement ratcheting logic (never decrease)
- [ ] Execute trailing stop on trigger
- [ ] Coordinate with regular stop-loss

## Definition of Done

- [ ] Trailing stop activates at configured multiplier
- [ ] Peak price tracked and ratchets up
- [ ] Trailing stop executes on price drop
- [ ] Regular stop-loss takes precedence before activation

---

## Technical Specifications

### Data Models

```python
# src/walltrack/core/execution/models/trailing_stop.py
"""Trailing stop models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field


class TrailingStopState(StrEnum):
    """Trailing stop lifecycle states."""

    INACTIVE = "inactive"      # Price hasn't reached activation multiplier
    ACTIVE = "active"          # Trailing stop is active and tracking
    TRIGGERED = "triggered"    # Price dropped below trailing stop level


class TrailingStopStatus(BaseModel):
    """Current status of a trailing stop for a position."""

    position_id: str
    state: TrailingStopState = TrailingStopState.INACTIVE

    # Activation tracking
    activation_price: Decimal | None = Field(
        None,
        description="Price at which trailing stop activates (entry * activation_multiplier)"
    )

    # Active state tracking
    peak_price: Decimal | None = Field(
        None,
        description="Highest price reached since activation"
    )
    trailing_stop_level: Decimal | None = Field(
        None,
        description="Current trailing stop price (peak - distance%)"
    )

    # Configuration from strategy
    activation_multiplier: Decimal = Field(
        default=Decimal("2.0"),
        description="Price multiplier to activate trailing stop"
    )
    distance_percentage: Decimal = Field(
        default=Decimal("30.0"),
        description="Percentage below peak for trailing stop level"
    )

    # Timestamps
    activated_at: datetime | None = None
    last_ratchet_at: datetime | None = None


class TrailingStopUpdate(BaseModel):
    """Result of a trailing stop check/update."""

    position_id: str
    previous_state: TrailingStopState
    current_state: TrailingStopState
    current_price: Decimal

    # If state changed
    newly_activated: bool = False
    newly_triggered: bool = False

    # If ratcheted
    ratcheted: bool = False
    previous_peak: Decimal | None = None
    new_peak: Decimal | None = None
    previous_level: Decimal | None = None
    new_level: Decimal | None = None


class TrailingStopTrigger(BaseModel):
    """Trailing stop trigger event for execution."""

    position_id: str
    trigger_price: Decimal = Field(description="Price that triggered the stop")
    trailing_stop_level: Decimal = Field(description="The trailing stop level")
    peak_price: Decimal = Field(description="Highest price recorded")
    entry_price: Decimal

    # Profit metrics at trigger
    peak_multiplier: Decimal = Field(description="peak_price / entry_price")
    exit_multiplier: Decimal = Field(description="trigger_price / entry_price")
    profit_captured_percentage: Decimal = Field(
        description="Percentage of peak profit captured"
    )

    triggered_at: datetime = Field(default_factory=datetime.utcnow)
```

### Trailing Stop Manager Service

```python
# src/walltrack/core/execution/trailing_stop.py
"""Trailing stop execution service."""

import structlog
from datetime import datetime
from decimal import Decimal

from walltrack.core.execution.models.trailing_stop import (
    TrailingStopState,
    TrailingStopStatus,
    TrailingStopUpdate,
    TrailingStopTrigger,
)
from walltrack.core.execution.models.position import Position
from walltrack.core.execution.models.exit_strategy import TrailingStopConfig

logger = structlog.get_logger(__name__)


class TrailingStopManager:
    """Manages trailing stop logic for positions.

    Trailing stop lifecycle:
    1. INACTIVE: Price below activation multiplier, regular stop-loss applies
    2. ACTIVE: Price reached activation, trailing stop tracks peak
    3. TRIGGERED: Price dropped below trailing stop level, execute sell
    """

    def __init__(self) -> None:
        # In-memory cache of trailing stop status per position
        self._status_cache: dict[str, TrailingStopStatus] = {}

    def initialize_for_position(
        self,
        position: Position,
        config: TrailingStopConfig,
    ) -> TrailingStopStatus:
        """Initialize trailing stop tracking for a new position."""

        if not config.enabled:
            logger.debug(
                "trailing_stop_disabled",
                position_id=position.id,
            )
            return TrailingStopStatus(
                position_id=position.id,
                state=TrailingStopState.INACTIVE,
            )

        activation_price = position.entry_price * config.activation_multiplier

        status = TrailingStopStatus(
            position_id=position.id,
            state=TrailingStopState.INACTIVE,
            activation_price=activation_price,
            activation_multiplier=config.activation_multiplier,
            distance_percentage=config.distance_percentage,
        )

        self._status_cache[position.id] = status

        logger.info(
            "trailing_stop_initialized",
            position_id=position.id,
            entry_price=float(position.entry_price),
            activation_price=float(activation_price),
            activation_multiplier=float(config.activation_multiplier),
            distance_percentage=float(config.distance_percentage),
        )

        return status

    def check_and_update(
        self,
        position: Position,
        current_price: Decimal,
    ) -> TrailingStopUpdate:
        """Check trailing stop status and update if needed.

        Returns update details including any state changes or ratcheting.
        """
        status = self._status_cache.get(position.id)

        if not status or not status.activation_price:
            # Trailing stop not enabled for this position
            return TrailingStopUpdate(
                position_id=position.id,
                previous_state=TrailingStopState.INACTIVE,
                current_state=TrailingStopState.INACTIVE,
                current_price=current_price,
            )

        previous_state = status.state
        update = TrailingStopUpdate(
            position_id=position.id,
            previous_state=previous_state,
            current_state=previous_state,
            current_price=current_price,
        )

        if status.state == TrailingStopState.INACTIVE:
            # Check for activation
            if current_price >= status.activation_price:
                self._activate(status, current_price)
                update.current_state = TrailingStopState.ACTIVE
                update.newly_activated = True
                update.new_peak = current_price
                update.new_level = status.trailing_stop_level

        elif status.state == TrailingStopState.ACTIVE:
            # Check for trigger or ratchet
            if current_price <= status.trailing_stop_level:
                # Triggered!
                status.state = TrailingStopState.TRIGGERED
                update.current_state = TrailingStopState.TRIGGERED
                update.newly_triggered = True

            elif current_price > status.peak_price:
                # Ratchet up
                update.previous_peak = status.peak_price
                update.previous_level = status.trailing_stop_level

                self._ratchet(status, current_price)

                update.ratcheted = True
                update.new_peak = status.peak_price
                update.new_level = status.trailing_stop_level

        return update

    def _activate(self, status: TrailingStopStatus, price: Decimal) -> None:
        """Activate trailing stop at current price."""

        status.state = TrailingStopState.ACTIVE
        status.peak_price = price
        status.activated_at = datetime.utcnow()

        # Calculate trailing stop level
        distance = price * (status.distance_percentage / Decimal("100"))
        status.trailing_stop_level = price - distance

        logger.info(
            "trailing_stop_activated",
            position_id=status.position_id,
            activation_price=float(price),
            peak_price=float(status.peak_price),
            trailing_stop_level=float(status.trailing_stop_level),
            distance_percentage=float(status.distance_percentage),
        )

    def _ratchet(self, status: TrailingStopStatus, new_peak: Decimal) -> None:
        """Ratchet trailing stop up to new peak."""

        old_peak = status.peak_price
        old_level = status.trailing_stop_level

        status.peak_price = new_peak
        status.last_ratchet_at = datetime.utcnow()

        # Recalculate trailing stop level
        distance = new_peak * (status.distance_percentage / Decimal("100"))
        status.trailing_stop_level = new_peak - distance

        logger.debug(
            "trailing_stop_ratcheted",
            position_id=status.position_id,
            old_peak=float(old_peak) if old_peak else None,
            new_peak=float(new_peak),
            old_level=float(old_level) if old_level else None,
            new_level=float(status.trailing_stop_level),
        )

    def create_trigger(
        self,
        position: Position,
        trigger_price: Decimal,
    ) -> TrailingStopTrigger:
        """Create trigger event with profit metrics."""

        status = self._status_cache[position.id]

        peak_multiplier = status.peak_price / position.entry_price
        exit_multiplier = trigger_price / position.entry_price

        # Profit captured = (exit - entry) / (peak - entry)
        peak_profit = status.peak_price - position.entry_price
        exit_profit = trigger_price - position.entry_price

        if peak_profit > 0:
            profit_captured = (exit_profit / peak_profit) * Decimal("100")
        else:
            profit_captured = Decimal("0")

        trigger = TrailingStopTrigger(
            position_id=position.id,
            trigger_price=trigger_price,
            trailing_stop_level=status.trailing_stop_level,
            peak_price=status.peak_price,
            entry_price=position.entry_price,
            peak_multiplier=peak_multiplier,
            exit_multiplier=exit_multiplier,
            profit_captured_percentage=profit_captured,
        )

        logger.info(
            "trailing_stop_triggered",
            position_id=position.id,
            entry_price=float(position.entry_price),
            peak_price=float(status.peak_price),
            trigger_price=float(trigger_price),
            trailing_stop_level=float(status.trailing_stop_level),
            peak_multiplier=float(peak_multiplier),
            exit_multiplier=float(exit_multiplier),
            profit_captured_pct=float(profit_captured),
        )

        return trigger

    def get_status(self, position_id: str) -> TrailingStopStatus | None:
        """Get current trailing stop status for a position."""
        return self._status_cache.get(position_id)

    def remove_position(self, position_id: str) -> None:
        """Remove trailing stop tracking for closed position."""
        self._status_cache.pop(position_id, None)

    def should_use_regular_stop_loss(
        self,
        position_id: str,
        current_price: Decimal,
        stop_loss_level: Decimal,
    ) -> bool:
        """Check if regular stop-loss should take precedence.

        Regular stop-loss applies when:
        - Trailing stop is INACTIVE (not yet activated)
        - Price is below stop-loss level
        """
        status = self._status_cache.get(position_id)

        if not status or status.state == TrailingStopState.INACTIVE:
            return current_price <= stop_loss_level

        return False


# Singleton instance
_trailing_stop_manager: TrailingStopManager | None = None


def get_trailing_stop_manager() -> TrailingStopManager:
    """Get trailing stop manager singleton."""
    global _trailing_stop_manager
    if _trailing_stop_manager is None:
        _trailing_stop_manager = TrailingStopManager()
    return _trailing_stop_manager
```

### Integration with Exit Manager

```python
# src/walltrack/core/execution/exit_manager.py (additions)
"""Exit manager integration with trailing stops."""

from walltrack.core.execution.trailing_stop import (
    get_trailing_stop_manager,
    TrailingStopState,
)


class ExitManager:
    """Enhanced exit manager with trailing stop support."""

    async def check_exit_conditions(
        self,
        position: Position,
        current_price: Decimal,
    ) -> ExitDecision:
        """Check all exit conditions including trailing stop."""

        trailing_mgr = get_trailing_stop_manager()
        levels = self._level_calculator.calculate(position, position.exit_strategy)

        # 1. Check trailing stop first if active
        ts_update = trailing_mgr.check_and_update(position, current_price)

        if ts_update.newly_triggered:
            # Trailing stop triggered - execute
            trigger = trailing_mgr.create_trigger(position, current_price)
            return ExitDecision(
                should_exit=True,
                exit_reason="trailing_stop",
                sell_percentage=100,  # Sell remaining
                trigger_price=current_price,
                metadata={
                    "peak_price": float(trigger.peak_price),
                    "peak_multiplier": float(trigger.peak_multiplier),
                    "profit_captured_pct": float(trigger.profit_captured_percentage),
                },
            )

        # 2. If trailing stop inactive, check regular stop-loss
        if trailing_mgr.should_use_regular_stop_loss(
            position.id,
            current_price,
            levels.stop_loss.price,
        ):
            return ExitDecision(
                should_exit=True,
                exit_reason="stop_loss",
                sell_percentage=100,
                trigger_price=current_price,
            )

        # 3. Check take-profit levels
        for tp_level in levels.take_profit_levels:
            if not tp_level.triggered and current_price >= tp_level.price:
                return ExitDecision(
                    should_exit=True,
                    exit_reason="take_profit",
                    sell_percentage=tp_level.sell_percentage,
                    trigger_price=current_price,
                    level_index=tp_level.level_index,
                )

        return ExitDecision(should_exit=False)
```

### Database Schema

```sql
-- Trailing stop tracking (can be in positions table or separate)
ALTER TABLE positions ADD COLUMN IF NOT EXISTS trailing_stop_status JSONB DEFAULT NULL;

-- Index for querying active trailing stops
CREATE INDEX IF NOT EXISTS idx_positions_trailing_active
ON positions USING GIN ((trailing_stop_status->'state'))
WHERE trailing_stop_status IS NOT NULL;

-- Trailing stop events log
CREATE TABLE IF NOT EXISTS trailing_stop_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES positions(id),
    event_type VARCHAR(20) NOT NULL, -- 'activated', 'ratcheted', 'triggered'

    -- Prices at event
    current_price DECIMAL(20, 10) NOT NULL,
    peak_price DECIMAL(20, 10),
    trailing_stop_level DECIMAL(20, 10),

    -- For ratchets
    previous_peak DECIMAL(20, 10),
    previous_level DECIMAL(20, 10),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_trailing_events_position ON trailing_stop_events(position_id);
CREATE INDEX idx_trailing_events_type ON trailing_stop_events(event_type);
```

### Unit Tests

```python
# tests/unit/core/execution/test_trailing_stop.py
"""Tests for trailing stop execution."""

import pytest
from decimal import Decimal
from datetime import datetime

from walltrack.core.execution.trailing_stop import TrailingStopManager
from walltrack.core.execution.models.trailing_stop import TrailingStopState
from walltrack.core.execution.models.exit_strategy import TrailingStopConfig
from walltrack.core.execution.models.position import Position


@pytest.fixture
def manager():
    return TrailingStopManager()


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
def trailing_config():
    return TrailingStopConfig(
        enabled=True,
        activation_multiplier=Decimal("2.0"),
        distance_percentage=Decimal("30.0"),
    )


class TestTrailingStopInitialization:
    """Test trailing stop initialization."""

    def test_initialize_enabled(self, manager, position, trailing_config):
        """Test initializing with enabled trailing stop."""
        status = manager.initialize_for_position(position, trailing_config)

        assert status.state == TrailingStopState.INACTIVE
        assert status.activation_price == Decimal("2.00")  # entry * 2.0
        assert status.peak_price is None
        assert status.trailing_stop_level is None

    def test_initialize_disabled(self, manager, position):
        """Test initializing with disabled trailing stop."""
        config = TrailingStopConfig(enabled=False)
        status = manager.initialize_for_position(position, config)

        assert status.state == TrailingStopState.INACTIVE
        assert status.activation_price is None


class TestTrailingStopActivation:
    """Test trailing stop activation."""

    def test_activation_at_multiplier(self, manager, position, trailing_config):
        """Test activation when price reaches multiplier."""
        manager.initialize_for_position(position, trailing_config)

        # Price below activation - should stay inactive
        update = manager.check_and_update(position, Decimal("1.50"))
        assert update.current_state == TrailingStopState.INACTIVE
        assert not update.newly_activated

        # Price at activation - should activate
        update = manager.check_and_update(position, Decimal("2.00"))
        assert update.current_state == TrailingStopState.ACTIVE
        assert update.newly_activated
        assert update.new_peak == Decimal("2.00")
        # Trailing stop at 2.00 - 30% = 1.40
        assert update.new_level == Decimal("1.40")

    def test_activation_above_multiplier(self, manager, position, trailing_config):
        """Test activation when price jumps above multiplier."""
        manager.initialize_for_position(position, trailing_config)

        # Price jumps to 3x
        update = manager.check_and_update(position, Decimal("3.00"))

        assert update.newly_activated
        assert update.new_peak == Decimal("3.00")
        # Trailing stop at 3.00 - 30% = 2.10
        assert update.new_level == Decimal("2.10")


class TestTrailingStopRatcheting:
    """Test trailing stop ratcheting behavior."""

    def test_ratchet_on_new_high(self, manager, position, trailing_config):
        """Test trailing stop ratchets up on new high."""
        manager.initialize_for_position(position, trailing_config)

        # Activate at 2x
        manager.check_and_update(position, Decimal("2.00"))

        # Price rises to 2.50
        update = manager.check_and_update(position, Decimal("2.50"))

        assert update.ratcheted
        assert update.previous_peak == Decimal("2.00")
        assert update.new_peak == Decimal("2.50")
        assert update.previous_level == Decimal("1.40")
        # New level: 2.50 - 30% = 1.75
        assert update.new_level == Decimal("1.75")

    def test_no_ratchet_on_price_drop(self, manager, position, trailing_config):
        """Test trailing stop does NOT decrease on price drop."""
        manager.initialize_for_position(position, trailing_config)

        # Activate at 2x
        manager.check_and_update(position, Decimal("2.00"))

        # Rise to 2.50
        manager.check_and_update(position, Decimal("2.50"))

        # Drop to 2.20 (but still above trailing stop of 1.75)
        update = manager.check_and_update(position, Decimal("2.20"))

        assert not update.ratcheted
        assert update.current_state == TrailingStopState.ACTIVE

        # Verify level hasn't changed
        status = manager.get_status(position.id)
        assert status.peak_price == Decimal("2.50")
        assert status.trailing_stop_level == Decimal("1.75")

    def test_multiple_ratchets(self, manager, position, trailing_config):
        """Test multiple consecutive ratchets."""
        manager.initialize_for_position(position, trailing_config)

        manager.check_and_update(position, Decimal("2.00"))  # Activate
        manager.check_and_update(position, Decimal("2.50"))  # Ratchet
        manager.check_and_update(position, Decimal("3.00"))  # Ratchet
        manager.check_and_update(position, Decimal("4.00"))  # Ratchet

        status = manager.get_status(position.id)
        assert status.peak_price == Decimal("4.00")
        # 4.00 - 30% = 2.80
        assert status.trailing_stop_level == Decimal("2.80")


class TestTrailingStopTrigger:
    """Test trailing stop trigger behavior."""

    def test_trigger_on_price_drop(self, manager, position, trailing_config):
        """Test trailing stop triggers on price drop below level."""
        manager.initialize_for_position(position, trailing_config)

        manager.check_and_update(position, Decimal("2.50"))  # Activate at 2.50
        # Trailing stop at 1.75

        # Drop below trailing stop
        update = manager.check_and_update(position, Decimal("1.70"))

        assert update.newly_triggered
        assert update.current_state == TrailingStopState.TRIGGERED

    def test_trigger_at_exact_level(self, manager, position, trailing_config):
        """Test trigger at exactly the trailing stop level."""
        manager.initialize_for_position(position, trailing_config)

        manager.check_and_update(position, Decimal("2.50"))  # Trailing stop at 1.75

        update = manager.check_and_update(position, Decimal("1.75"))

        assert update.newly_triggered

    def test_create_trigger_event(self, manager, position, trailing_config):
        """Test creating trigger event with metrics."""
        manager.initialize_for_position(position, trailing_config)

        manager.check_and_update(position, Decimal("3.00"))  # Peak at 3x
        manager.check_and_update(position, Decimal("2.00"))  # Drop below 2.10 trailing

        trigger = manager.create_trigger(position, Decimal("2.00"))

        assert trigger.peak_price == Decimal("3.00")
        assert trigger.trigger_price == Decimal("2.00")
        assert trigger.peak_multiplier == Decimal("3.0")  # 3.00 / 1.00
        assert trigger.exit_multiplier == Decimal("2.0")  # 2.00 / 1.00

        # Profit captured: (2.00-1.00)/(3.00-1.00) = 50%
        assert trigger.profit_captured_percentage == Decimal("50")


class TestRegularStopLossPrecedence:
    """Test regular stop-loss takes precedence before activation."""

    def test_stop_loss_before_activation(self, manager, position, trailing_config):
        """Test regular stop-loss applies when trailing stop inactive."""
        manager.initialize_for_position(position, trailing_config)

        stop_loss_level = Decimal("0.70")  # 30% stop-loss

        # Price at 0.65 - below stop-loss but trailing stop inactive
        should_use_sl = manager.should_use_regular_stop_loss(
            position.id,
            current_price=Decimal("0.65"),
            stop_loss_level=stop_loss_level,
        )

        assert should_use_sl is True

    def test_no_stop_loss_after_activation(self, manager, position, trailing_config):
        """Test regular stop-loss doesn't apply after trailing activation."""
        manager.initialize_for_position(position, trailing_config)

        # Activate trailing stop
        manager.check_and_update(position, Decimal("2.00"))

        # Even if price drops below regular stop-loss, trailing stop governs
        should_use_sl = manager.should_use_regular_stop_loss(
            position.id,
            current_price=Decimal("0.50"),
            stop_loss_level=Decimal("0.70"),
        )

        assert should_use_sl is False


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_unknown_position(self, manager, position):
        """Test handling unknown position ID."""
        update = manager.check_and_update(position, Decimal("2.00"))

        assert update.current_state == TrailingStopState.INACTIVE

    def test_remove_position(self, manager, position, trailing_config):
        """Test removing position from tracking."""
        manager.initialize_for_position(position, trailing_config)

        assert manager.get_status(position.id) is not None

        manager.remove_position(position.id)

        assert manager.get_status(position.id) is None

    def test_rapid_price_movements(self, manager, position, trailing_config):
        """Test handling rapid price movements."""
        manager.initialize_for_position(position, trailing_config)

        # Rapid sequence: activate, ratchet, trigger
        manager.check_and_update(position, Decimal("2.00"))  # Activate
        manager.check_and_update(position, Decimal("5.00"))  # Ratchet to 5x
        update = manager.check_and_update(position, Decimal("3.00"))  # Drop below 3.50

        assert update.newly_triggered

        status = manager.get_status(position.id)
        assert status.state == TrailingStopState.TRIGGERED
```
