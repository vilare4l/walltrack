"""Position sizing models for dynamic trade allocation.

Implements conviction-based position sizing with configurable multipliers
and limit enforcement per FR20.

Story 10.5-8: Added risk-based sizing mode.
Story 10.5-9: Added drawdown-based size reduction.
Story 10.5-10: Added daily loss limit tracking.
Story 10.5-11: Added concentration limits.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class SizingMode(str, Enum):
    """Position sizing mode."""

    RISK_BASED = "risk_based"  # Size based on risk per trade and stop loss
    FIXED_PERCENT = "fixed_percent"  # Fixed percentage of capital (legacy)


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
    BLOCKED_DRAWDOWN = "blocked_drawdown"  # Story 10.5-9: Trading blocked by drawdown
    BLOCKED_DAILY_LOSS = "blocked_daily_loss"  # Story 10.5-10: Trading blocked by daily loss
    BLOCKED_CONCENTRATION = "blocked_concentration"  # Story 10.5-11: Concentration limit
    BLOCKED_DUPLICATE = "blocked_duplicate"  # Story 10.5-11: Position already exists


class DrawdownReductionTier(BaseModel):
    """A single drawdown reduction tier.

    Story 10.5-9: Defines threshold and reduction for a tier.
    Example: threshold_pct=10, size_reduction_pct=25 means
    when drawdown >= 10%, reduce position size by 25%.
    """

    threshold_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Drawdown % threshold to activate this tier",
    )
    size_reduction_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Position size reduction % (100 = blocked)",
    )


class DrawdownMetrics(BaseModel):
    """Current drawdown metrics.

    Story 10.5-9: Tracks portfolio drawdown from peak.
    """

    peak_capital_sol: float = Field(..., ge=0, description="Peak capital in SOL")
    current_capital_sol: float = Field(..., ge=0, description="Current capital in SOL")
    drawdown_pct: float = Field(default=0.0, ge=0, description="Current drawdown %")
    peak_date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    days_since_peak: int = Field(default=0, ge=0)

    @property
    def is_at_peak(self) -> bool:
        """Check if currently at peak (within 0.01%)."""
        return self.drawdown_pct <= 0.01


class DailyLossMetrics(BaseModel):
    """Daily profit/loss metrics.

    Story 10.5-10: Tracks daily P&L and limit status.
    """

    date: datetime = Field(default_factory=lambda: datetime.now(UTC))
    realized_pnl_sol: float = Field(default=0.0, description="Realized P&L from closed positions")
    unrealized_pnl_sol: float = Field(default=0.0, description="Unrealized P&L from open positions")
    total_pnl_sol: float = Field(default=0.0, description="Total P&L (realized + unrealized)")
    starting_capital_sol: float = Field(default=0.0, ge=0, description="Capital at start of day")
    pnl_pct: float = Field(default=0.0, description="P&L as % of starting capital")

    # Limit tracking
    daily_limit_pct: float = Field(default=5.0, ge=0, description="Daily loss limit %")
    limit_remaining_pct: float = Field(default=5.0, ge=0, description="Remaining limit %")
    is_limit_hit: bool = Field(default=False, description="Whether limit has been hit")
    is_warning_zone: bool = Field(default=False, description="Whether in warning zone (80%+)")

    @property
    def limit_usage_pct(self) -> float:
        """Percentage of daily limit used (0-100+)."""
        if self.daily_limit_pct == 0:
            return 0.0
        # Only count losses (negative P&L)
        if self.total_pnl_sol >= 0:
            return 0.0
        return min(100.0, abs(self.pnl_pct) / self.daily_limit_pct * 100)


class ConcentrationMetrics(BaseModel):
    """Concentration metrics for portfolio allocation.

    Story 10.5-11: Tracks token and cluster concentration.
    """

    # Token concentration
    token_address: str | None = Field(default=None)
    token_current_value_sol: float = Field(default=0.0, ge=0)
    token_current_pct: float = Field(default=0.0, ge=0)
    token_limit_pct: float = Field(default=25.0, ge=0)
    token_remaining_capacity_sol: float = Field(default=0.0, ge=0)

    # Cluster concentration (optional)
    cluster_id: str | None = Field(default=None)
    cluster_current_value_sol: float = Field(default=0.0, ge=0)
    cluster_current_pct: float = Field(default=0.0, ge=0)
    cluster_limit_pct: float = Field(default=50.0, ge=0)
    cluster_positions_count: int = Field(default=0, ge=0)
    cluster_max_positions: int = Field(default=3, ge=1)

    # Portfolio context
    portfolio_value_sol: float = Field(default=0.0, ge=0)

    # Block info
    is_duplicate: bool = Field(default=False)
    is_token_limit_hit: bool = Field(default=False)
    is_cluster_limit_hit: bool = Field(default=False)
    is_cluster_max_positions: bool = Field(default=False)
    block_reason: str | None = Field(default=None)

    # Adjustment info
    requested_amount_sol: float = Field(default=0.0, ge=0)
    max_allowed_sol: float = Field(default=0.0, ge=0)
    was_adjusted: bool = Field(default=False)

    @property
    def is_blocked(self) -> bool:
        """Check if entry should be blocked."""
        return (
            self.is_duplicate
            or self.is_token_limit_hit
            or self.is_cluster_limit_hit
            or self.is_cluster_max_positions
        )


class PositionSizingConfig(BaseModel):
    """Configuration for dynamic position sizing.

    Stored in Supabase, editable via dashboard.
    """

    # Sizing mode (Story 10.5-8)
    sizing_mode: SizingMode = Field(
        default=SizingMode.FIXED_PERCENT,
        description="Sizing mode: risk_based or fixed_percent",
    )

    # Risk-based sizing (Story 10.5-8)
    risk_per_trade_pct: float = Field(
        default=1.0,
        ge=0.1,
        le=5.0,
        description="Maximum % of capital to risk per trade",
    )
    default_stop_loss_pct: float = Field(
        default=10.0,
        ge=1.0,
        le=50.0,
        description="Default stop loss % if not specified",
    )

    # Base sizing (fixed_percent mode)
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

    # Story 10.5-9: Drawdown-based size reduction
    drawdown_reduction_enabled: bool = Field(
        default=True,
        description="Enable drawdown-based position size reduction",
    )
    drawdown_lookback_days: int = Field(
        default=30,
        ge=7,
        le=90,
        description="Days to look back for peak capital calculation",
    )
    drawdown_reduction_tiers: list[DrawdownReductionTier] = Field(
        default_factory=lambda: [
            DrawdownReductionTier(threshold_pct=5.0, size_reduction_pct=0.0),
            DrawdownReductionTier(threshold_pct=10.0, size_reduction_pct=25.0),
            DrawdownReductionTier(threshold_pct=15.0, size_reduction_pct=50.0),
            DrawdownReductionTier(threshold_pct=20.0, size_reduction_pct=100.0),
        ],
        description="Tiered drawdown reduction [5%→0%, 10%→25%, 15%→50%, 20%→blocked]",
    )

    # Story 10.5-10: Daily loss limit
    daily_loss_limit_enabled: bool = Field(
        default=True,
        description="Enable daily loss limit enforcement",
    )
    daily_loss_limit_pct: float = Field(
        default=5.0,
        ge=1.0,
        le=25.0,
        description="Maximum daily loss as % of starting capital",
    )
    daily_loss_warning_threshold_pct: float = Field(
        default=80.0,
        ge=50.0,
        le=95.0,
        description="Warn when this % of daily limit is used",
    )

    # Story 10.5-11: Concentration limits
    concentration_limits_enabled: bool = Field(
        default=True,
        description="Enable concentration limits enforcement",
    )
    max_token_concentration_pct: float = Field(
        default=25.0,
        ge=5.0,
        le=100.0,
        description="Maximum allocation to single token as % of portfolio",
    )
    max_cluster_concentration_pct: float = Field(
        default=50.0,
        ge=10.0,
        le=100.0,
        description="Maximum allocation to single cluster as % of portfolio",
    )
    max_positions_per_cluster: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Maximum open positions in a single cluster",
    )
    block_duplicate_positions: bool = Field(
        default=True,
        description="Block new position if one already exists for token",
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

    @model_validator(mode="after")
    def validate_drawdown_tiers(self) -> PositionSizingConfig:
        """Ensure drawdown tiers are sorted by threshold."""
        if self.drawdown_reduction_tiers:
            # Sort tiers by threshold ascending
            self.drawdown_reduction_tiers = sorted(
                self.drawdown_reduction_tiers,
                key=lambda t: t.threshold_pct,
            )
        return self


class PositionSizeRequest(BaseModel):
    """Request to calculate position size."""

    signal_score: float = Field(..., ge=0.0, le=1.0, description="Signal composite score")
    available_balance_sol: float = Field(..., ge=0, description="Available SOL balance")
    current_position_count: int = Field(default=0, ge=0, description="Current open positions")
    current_allocated_sol: float = Field(default=0, ge=0, description="SOL already in positions")
    token_address: str | None = Field(default=None, description="Token for logging")
    signal_id: str | None = Field(default=None, description="Signal ID for tracking")
    # Story 10.5-8: Risk-based sizing requires stop loss
    stop_loss_pct: float | None = Field(
        default=None,
        ge=1.0,
        le=50.0,
        description="Stop loss % for risk-based sizing (uses default if not specified)",
    )
    # Story 10.5-11: Concentration limits
    cluster_id: str | None = Field(
        default=None,
        description="Cluster ID for cluster concentration limits",
    )


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

    # Story 10.5-8: Risk-based sizing fields
    sizing_mode: SizingMode = Field(
        default=SizingMode.FIXED_PERCENT,
        description="Sizing mode used for calculation",
    )
    risk_amount_sol: float = Field(
        default=0.0,
        ge=0,
        description="Max SOL at risk (position * stop_loss_pct)",
    )
    stop_loss_pct_used: float = Field(
        default=0.0,
        ge=0,
        description="Stop loss % used in calculation",
    )

    # Story 10.5-9: Drawdown reduction fields
    drawdown_reduction_pct: float = Field(
        default=0.0,
        ge=0,
        description="Position size reduction % due to drawdown",
    )
    drawdown_metrics: DrawdownMetrics | None = Field(
        default=None,
        description="Drawdown metrics at time of calculation",
    )
    pre_drawdown_size_sol: float = Field(
        default=0.0,
        ge=0,
        description="Size before drawdown reduction applied",
    )

    # Story 10.5-10: Daily loss limit fields
    daily_loss_metrics: DailyLossMetrics | None = Field(
        default=None,
        description="Daily loss metrics at time of calculation",
    )
    daily_loss_blocked: bool = Field(
        default=False,
        description="Whether trading blocked by daily loss limit",
    )

    # Story 10.5-11: Concentration limit fields
    concentration_metrics: ConcentrationMetrics | None = Field(
        default=None,
        description="Concentration metrics at time of calculation",
    )
    concentration_blocked: bool = Field(
        default=False,
        description="Whether trading blocked by concentration limit",
    )
    concentration_adjusted: bool = Field(
        default=False,
        description="Whether size was adjusted due to concentration limit",
    )
    pre_concentration_size_sol: float = Field(
        default=0.0,
        ge=0,
        description="Size before concentration adjustment applied",
    )

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
