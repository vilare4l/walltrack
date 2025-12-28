"""Exit strategy models for position management.

Defines configurable exit strategies with multiple take-profit levels,
trailing stops, time-based rules, and moonbag configurations per FR23.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator


class StrategyPreset(str, Enum):
    """Built-in strategy presets."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    MOONBAG_AGGRESSIVE = "moonbag_aggressive"
    QUICK_FLIP = "quick_flip"
    DIAMOND_HANDS = "diamond_hands"
    CUSTOM = "custom"


class TakeProfitLevel(BaseModel):
    """Single take-profit level configuration.

    Example: trigger_multiplier=2.0, sell_percentage=50
    means sell 50% of position when price doubles.
    """

    trigger_multiplier: float = Field(
        ...,
        gt=1.0,
        le=100.0,
        description="Price multiplier to trigger (e.g., 2.0 = 2x)",
    )
    sell_percentage: float = Field(
        ...,
        gt=0,
        le=100,
        description="Percentage of remaining position to sell",
    )

    @field_validator("trigger_multiplier")
    @classmethod
    def validate_multiplier(cls, v: float) -> float:
        """Ensure multiplier is profitable."""
        if v <= 1.0:
            raise ValueError("Trigger multiplier must be > 1.0 (profit)")
        return round(v, 2)


class TrailingStopConfig(BaseModel):
    """Trailing stop configuration.

    Activates when price reaches activation_multiplier,
    then trails at distance_percentage below peak.
    """

    enabled: bool = Field(default=False)
    activation_multiplier: float = Field(
        default=2.0,
        gt=1.0,
        le=50.0,
        description="Multiplier to activate trailing stop",
    )
    distance_percentage: float = Field(
        default=30.0,
        gt=5.0,
        le=50.0,
        description="Distance from peak as percentage (e.g., 30% below)",
    )


class TimeRulesConfig(BaseModel):
    """Time-based exit rules.

    Handles max hold duration and stagnation exits.
    """

    max_hold_hours: int | None = Field(
        default=None,
        ge=1,
        le=720,  # Max 30 days
        description="Maximum hold time before forced exit",
    )
    stagnation_exit_enabled: bool = Field(
        default=False,
        description="Exit if price stagnates",
    )
    stagnation_threshold_pct: float = Field(
        default=5.0,
        ge=1.0,
        le=20.0,
        description="Price movement threshold to be considered stagnant",
    )
    stagnation_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Hours of stagnation before exit",
    )


class MoonbagConfig(BaseModel):
    """Moonbag (keep forever) configuration.

    A moonbag is a small portion kept regardless of other rules.
    """

    percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage to keep as moonbag",
    )
    stop_loss: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Stop loss for moonbag (null = ride to zero)",
    )

    @property
    def has_moonbag(self) -> bool:
        """Check if moonbag is configured."""
        return self.percentage > 0

    @property
    def ride_to_zero(self) -> bool:
        """Check if moonbag rides to zero."""
        return self.has_moonbag and self.stop_loss is None


class ExitStrategy(BaseModel):
    """Complete exit strategy configuration.

    Defines how and when to exit a position.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)
    preset: StrategyPreset = Field(default=StrategyPreset.CUSTOM)
    is_default: bool = Field(default=False, description="Is this a built-in preset")

    # Take profit levels (executed in order of trigger)
    take_profit_levels: list[TakeProfitLevel] = Field(
        default_factory=list,
        max_length=10,
        description="Take profit levels in order",
    )

    # Stop loss
    stop_loss: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Stop loss threshold (0.5 = -50%)",
    )

    # Trailing stop
    trailing_stop: TrailingStopConfig = Field(default_factory=TrailingStopConfig)

    # Time rules
    time_rules: TimeRulesConfig = Field(default_factory=TimeRulesConfig)

    # Moonbag
    moonbag: MoonbagConfig = Field(default_factory=MoonbagConfig)

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_take_profit_order(self) -> ExitStrategy:
        """Ensure take profit levels are in ascending order."""
        if len(self.take_profit_levels) <= 1:
            return self

        multipliers = [tp.trigger_multiplier for tp in self.take_profit_levels]
        if multipliers != sorted(multipliers):
            # Auto-sort them
            self.take_profit_levels = sorted(
                self.take_profit_levels,
                key=lambda x: x.trigger_multiplier,
            )

        return self

    @property
    def has_take_profits(self) -> bool:
        """Check if take profit levels are configured."""
        return len(self.take_profit_levels) > 0

    @property
    def has_trailing_stop(self) -> bool:
        """Check if trailing stop is enabled."""
        return self.trailing_stop.enabled

    @property
    def has_time_limits(self) -> bool:
        """Check if time-based limits are configured."""
        return (
            self.time_rules.max_hold_hours is not None
            or self.time_rules.stagnation_exit_enabled
        )


class ExitStrategyAssignment(BaseModel):
    """Assignment of exit strategy to a conviction tier or specific position."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = Field(..., description="Exit strategy ID")
    conviction_tier: str | None = Field(
        default=None,
        description="Conviction tier this applies to (high, standard)",
    )
    position_id: str | None = Field(
        default=None,
        description="Specific position ID (overrides tier)",
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def validate_assignment(self) -> ExitStrategyAssignment:
        """Either tier or position_id must be set."""
        if self.conviction_tier is None and self.position_id is None:
            raise ValueError("Either conviction_tier or position_id must be set")
        return self
