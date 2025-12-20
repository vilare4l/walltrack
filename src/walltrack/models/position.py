"""Position and exit execution models.

Models for:
- Position tracking and status
- Calculated exit levels (stop-loss, take-profit)
- Exit execution records
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class PositionStatus(str, Enum):
    """Status of a position."""

    PENDING = "pending"  # Trade submitted, not confirmed
    OPEN = "open"  # Active position
    PARTIAL_EXIT = "partial_exit"  # Some take profits hit
    CLOSING = "closing"  # Exit in progress
    CLOSED = "closed"  # Fully exited
    MOONBAG = "moonbag"  # Only moonbag remains


class ExitReason(str, Enum):
    """Reason for position exit."""

    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_LIMIT = "time_limit"
    STAGNATION = "stagnation"
    MANUAL = "manual"
    MOONBAG_STOP = "moonbag_stop"


class CalculatedLevel(BaseModel):
    """A calculated price level (SL or TP)."""

    level_type: str = Field(..., description="stop_loss, take_profit_1, etc.")
    trigger_price: float = Field(..., gt=0)
    sell_percentage: float = Field(..., ge=0, le=100)
    is_triggered: bool = Field(default=False)
    triggered_at: datetime | None = Field(default=None)
    tx_signature: str | None = Field(default=None)


class PositionLevels(BaseModel):
    """All calculated exit levels for a position."""

    entry_price: float = Field(..., gt=0)
    stop_loss_price: float = Field(..., gt=0)
    take_profit_levels: list[CalculatedLevel] = Field(default_factory=list)
    trailing_stop_activation_price: float | None = Field(default=None)
    trailing_stop_current_price: float | None = Field(default=None)
    moonbag_stop_price: float | None = Field(default=None)

    @computed_field
    @property
    def next_take_profit(self) -> CalculatedLevel | None:
        """Get next un-triggered take profit level."""
        for level in self.take_profit_levels:
            if not level.is_triggered:
                return level
        return None

    @computed_field
    @property
    def all_take_profits_hit(self) -> bool:
        """Check if all take profit levels have been triggered."""
        if not self.take_profit_levels:
            return False
        return all(level.is_triggered for level in self.take_profit_levels)


class Position(BaseModel):
    """An open or closed trading position."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = Field(..., description="Source signal ID")
    token_address: str = Field(...)
    token_symbol: str | None = Field(default=None)

    # Status
    status: PositionStatus = Field(default=PositionStatus.PENDING)

    # Entry details
    entry_tx_signature: str | None = Field(default=None)
    entry_price: float = Field(..., gt=0)
    entry_amount_sol: float = Field(..., gt=0)
    entry_amount_tokens: float = Field(..., gt=0)
    entry_time: datetime = Field(default_factory=datetime.utcnow)

    # Current state
    current_amount_tokens: float = Field(..., ge=0)
    realized_pnl_sol: float = Field(default=0.0)

    # Exit strategy
    exit_strategy_id: str = Field(...)
    conviction_tier: str = Field(...)  # "high" or "standard"
    levels: PositionLevels | None = Field(default=None)

    # Moonbag tracking
    is_moonbag: bool = Field(default=False)
    moonbag_percentage: float = Field(default=0.0)

    # Exit details (when closed)
    exit_reason: ExitReason | None = Field(default=None)
    exit_time: datetime | None = Field(default=None)
    exit_price: float | None = Field(default=None)
    exit_tx_signatures: list[str] = Field(default_factory=list)

    # Tracking
    last_price_check: datetime | None = Field(default=None)
    peak_price: float | None = Field(default=None)  # For trailing stop
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def current_value_multiple(self) -> float | None:
        """Current price as multiple of entry (e.g., 2.0 = 2x)."""
        if self.peak_price and self.entry_price > 0:
            return self.peak_price / self.entry_price
        return None

    @computed_field
    @property
    def is_in_profit(self) -> bool:
        """Check if position is currently profitable."""
        if self.peak_price:
            return self.peak_price > self.entry_price
        return False


class ExitExecution(BaseModel):
    """Record of an exit execution (partial or full)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = Field(...)
    exit_reason: ExitReason
    trigger_level: str = Field(..., description="stop_loss, take_profit_1, etc.")

    # Execution details
    sell_percentage: float = Field(..., ge=0, le=100)
    amount_tokens_sold: float = Field(..., ge=0)
    amount_sol_received: float = Field(..., ge=0)
    exit_price: float = Field(..., gt=0)
    tx_signature: str = Field(...)

    # P&L
    realized_pnl_sol: float = Field(...)

    executed_at: datetime = Field(default_factory=datetime.utcnow)
