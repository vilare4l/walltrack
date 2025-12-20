"""Models for wallet score updates."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class ScoreUpdateType(str, Enum):
    """Type of score update."""

    TRADE_OUTCOME = "trade_outcome"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    DECAY_PENALTY = "decay_penalty"
    RECALIBRATION = "recalibration"


class ScoreUpdateConfig(BaseModel):
    """Configuration for score update calculations."""

    # Win impact
    base_win_increase: Decimal = Field(
        default=Decimal("0.02"),
        ge=0,
        le=Decimal("0.1"),
        description="Base score increase for a win",
    )
    profit_multiplier: Decimal = Field(
        default=Decimal("0.01"),
        ge=0,
        description="Additional increase per 10% profit",
    )
    max_win_increase: Decimal = Field(
        default=Decimal("0.10"),
        description="Maximum score increase from a single win",
    )

    # Loss impact
    base_loss_decrease: Decimal = Field(
        default=Decimal("0.03"),
        ge=0,
        le=Decimal("0.15"),
        description="Base score decrease for a loss",
    )
    loss_multiplier: Decimal = Field(
        default=Decimal("0.015"),
        ge=0,
        description="Additional decrease per 10% loss",
    )
    max_loss_decrease: Decimal = Field(
        default=Decimal("0.15"),
        description="Maximum score decrease from a single loss",
    )

    # Decay threshold
    decay_flag_threshold: Decimal = Field(
        default=Decimal("0.3"),
        description="Score below which wallet is flagged for decay",
    )
    blacklist_threshold: Decimal = Field(
        default=Decimal("0.15"),
        description="Score below which wallet is blacklisted",
    )

    # Rolling window
    rolling_window_trades: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of trades for rolling metrics",
    )


class WalletMetrics(BaseModel):
    """Wallet performance metrics."""

    wallet_address: str = Field(..., description="Wallet address")
    current_score: Decimal = Field(
        ...,
        ge=0,
        le=1,
        description="Current wallet score (0-1)",
    )
    lifetime_trades: int = Field(default=0, description="Total lifetime trades")
    lifetime_wins: int = Field(default=0, description="Total lifetime wins")
    lifetime_losses: int = Field(default=0, description="Total lifetime losses")
    lifetime_pnl: Decimal = Field(default=Decimal("0"), description="Lifetime PnL in SOL")
    rolling_trades: int = Field(default=0, description="Trades in rolling window")
    rolling_wins: int = Field(default=0, description="Wins in rolling window")
    rolling_pnl: Decimal = Field(default=Decimal("0"), description="PnL in rolling window")
    last_trade_timestamp: datetime | None = Field(default=None)
    last_score_update: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_flagged: bool = Field(default=False, description="Flagged for decay")
    is_blacklisted: bool = Field(default=False, description="Blacklisted")

    @computed_field
    @property
    def lifetime_win_rate(self) -> Decimal:
        """Lifetime win rate percentage."""
        if self.lifetime_trades == 0:
            return Decimal("0")
        return (Decimal(self.lifetime_wins) / Decimal(self.lifetime_trades)) * 100

    @computed_field
    @property
    def rolling_win_rate(self) -> Decimal:
        """Rolling window win rate percentage."""
        if self.rolling_trades == 0:
            return Decimal("0")
        return (Decimal(self.rolling_wins) / Decimal(self.rolling_trades)) * 100

    @computed_field
    @property
    def average_pnl(self) -> Decimal:
        """Average PnL per trade."""
        if self.lifetime_trades == 0:
            return Decimal("0")
        return self.lifetime_pnl / Decimal(self.lifetime_trades)


class ScoreUpdateInput(BaseModel):
    """Input for updating wallet score."""

    wallet_address: str = Field(..., description="Wallet address to update")
    trade_id: UUID = Field(..., description="Associated trade ID")
    pnl_sol: Decimal = Field(..., description="PnL from trade in SOL")
    pnl_percent: Decimal = Field(..., description="PnL percentage")
    is_win: bool = Field(..., description="Whether trade was profitable")


class ScoreUpdateResult(BaseModel):
    """Result of a score update operation."""

    wallet_address: str = Field(..., description="Wallet address")
    previous_score: Decimal = Field(..., description="Score before update")
    new_score: Decimal = Field(..., description="Score after update")
    score_change: Decimal = Field(..., description="Amount of change")
    update_type: ScoreUpdateType = Field(..., description="Type of update")
    trade_id: UUID | None = Field(default=None, description="Associated trade")
    triggered_flag: bool = Field(default=False, description="Whether decay flag was triggered")
    triggered_blacklist: bool = Field(
        default=False, description="Whether blacklist was triggered"
    )
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class WalletScoreHistory(BaseModel):
    """Historical score entry."""

    id: UUID = Field(..., description="History entry ID")
    wallet_address: str = Field(..., description="Wallet address")
    score: Decimal = Field(..., description="Score at this point")
    previous_score: Decimal = Field(..., description="Previous score")
    change: Decimal = Field(..., description="Score change")
    update_type: ScoreUpdateType = Field(..., description="Type of update")
    trade_id: UUID | None = Field(default=None, description="Associated trade")
    reason: str | None = Field(default=None, description="Update reason")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class BatchUpdateRequest(BaseModel):
    """Request for batch score updates."""

    updates: list[ScoreUpdateInput] = Field(..., min_length=1, max_length=100)


class BatchUpdateResult(BaseModel):
    """Result of batch score updates."""

    total_processed: int = Field(default=0)
    successful: int = Field(default=0)
    failed: int = Field(default=0)
    results: list[ScoreUpdateResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
