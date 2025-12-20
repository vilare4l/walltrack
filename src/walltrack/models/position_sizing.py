"""Position sizing models for dynamic trade allocation.

Implements conviction-based position sizing with configurable multipliers
and limit enforcement per FR20.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class ConvictionTier(str, Enum):
    """Signal conviction tiers with associated multipliers."""

    HIGH = "high"  # >= 0.85, 1.5x multiplier
    STANDARD = "standard"  # 0.70-0.84, 1.0x multiplier
    NONE = "none"  # < 0.70, no trade


class SizingDecision(str, Enum):
    """Decision made by position sizer."""

    APPROVED = "approved"
    REDUCED = "reduced"  # Reduced due to balance/limits
    SKIPPED_MIN_SIZE = "skipped_min_size"
    SKIPPED_NO_BALANCE = "skipped_no_balance"
    SKIPPED_MAX_POSITIONS = "skipped_max_positions"
    SKIPPED_LOW_SCORE = "skipped_low_score"


class PositionSizingConfig(BaseModel):
    """Configuration for dynamic position sizing.

    Stored in Supabase, editable via dashboard.
    """

    # Base sizing
    base_position_pct: float = Field(
        default=2.0,
        ge=0.1,
        le=10.0,
        description="Base position size as % of capital",
    )
    min_position_sol: float = Field(
        default=0.01,
        ge=0.001,
        description="Minimum position size in SOL",
    )
    max_position_sol: float = Field(
        default=1.0,
        ge=0.01,
        description="Maximum position size in SOL",
    )

    # Conviction multipliers
    high_conviction_multiplier: float = Field(
        default=1.5,
        ge=1.0,
        le=3.0,
        description="Multiplier for high conviction signals (>=0.85)",
    )
    standard_conviction_multiplier: float = Field(
        default=1.0,
        ge=0.5,
        le=2.0,
        description="Multiplier for standard conviction signals (0.70-0.84)",
    )

    # Thresholds
    high_conviction_threshold: float = Field(
        default=0.85,
        ge=0.5,
        le=1.0,
        description="Score threshold for high conviction",
    )
    min_conviction_threshold: float = Field(
        default=0.70,
        ge=0.3,
        le=0.9,
        description="Minimum score to trade",
    )

    # Limits
    max_concurrent_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum open positions at once",
    )
    max_capital_allocation_pct: float = Field(
        default=50.0,
        ge=10.0,
        le=100.0,
        description="Maximum % of capital allocated across all positions",
    )

    # Safety
    reserve_sol: float = Field(
        default=0.05,
        ge=0.01,
        description="SOL to keep in reserve for fees",
    )

    # Metadata
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_by: str | None = Field(default=None)

    @model_validator(mode="after")
    def validate_thresholds(self) -> PositionSizingConfig:
        """Ensure threshold ordering is valid."""
        if self.high_conviction_threshold <= self.min_conviction_threshold:
            raise ValueError("high_conviction_threshold must be > min_conviction_threshold")
        return self

    @model_validator(mode="after")
    def validate_position_limits(self) -> PositionSizingConfig:
        """Ensure position limits are valid."""
        if self.max_position_sol < self.min_position_sol:
            raise ValueError("max_position_sol must be >= min_position_sol")
        return self


class PositionSizeRequest(BaseModel):
    """Request to calculate position size."""

    signal_score: float = Field(..., ge=0.0, le=1.0, description="Signal composite score")
    available_balance_sol: float = Field(..., ge=0, description="Available SOL balance")
    current_position_count: int = Field(default=0, ge=0, description="Current open positions")
    current_allocated_sol: float = Field(default=0, ge=0, description="SOL already in positions")
    token_address: str | None = Field(default=None, description="Token for logging")
    signal_id: str | None = Field(default=None, description="Signal ID for tracking")


class PositionSizeResult(BaseModel):
    """Result of position size calculation."""

    decision: SizingDecision
    conviction_tier: ConvictionTier
    base_size_sol: float = Field(..., ge=0)
    multiplier: float = Field(..., ge=0)
    calculated_size_sol: float = Field(..., ge=0)
    final_size_sol: float = Field(..., ge=0)
    reason: str | None = Field(default=None)

    # Calculation breakdown
    capital_used_for_base: float = Field(..., ge=0)
    reduction_applied: bool = Field(default=False)
    reduction_reason: str | None = Field(default=None)

    @property
    def should_trade(self) -> bool:
        """Check if trade should proceed."""
        return self.decision in (SizingDecision.APPROVED, SizingDecision.REDUCED)


class PositionSizeAudit(BaseModel):
    """Audit entry for position sizing decisions."""

    id: str | None = Field(default=None)
    signal_id: str | None = Field(default=None)
    token_address: str | None = Field(default=None)

    # Input
    signal_score: float
    available_balance_sol: float
    current_position_count: int
    current_allocated_sol: float

    # Config snapshot
    config_snapshot: dict[str, Any]

    # Result
    result: PositionSizeResult

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
