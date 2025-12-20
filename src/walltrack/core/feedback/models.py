"""Models for feedback loop and trade outcome recording."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


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
    parent_trade_id: UUID | None = Field(
        default=None, description="Parent trade ID for partial exits"
    )


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
    parent_trade_id: UUID | None = Field(
        default=None, description="Parent trade for partials"
    )
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

    total_pnl_sol: Decimal = Field(
        default=Decimal("0"), description="Total PnL in SOL"
    )
    total_pnl_percent: Decimal = Field(default=Decimal("0"), description="Total PnL %")
    win_count: int = Field(default=0, description="Number of winning trades")
    loss_count: int = Field(default=0, description="Number of losing trades")
    total_trades: int = Field(default=0, description="Total trades")
    average_win_sol: Decimal = Field(
        default=Decimal("0"), description="Average win in SOL"
    )
    average_loss_sol: Decimal = Field(
        default=Decimal("0"), description="Average loss in SOL"
    )
    largest_win_sol: Decimal = Field(default=Decimal("0"), description="Largest win")
    largest_loss_sol: Decimal = Field(default=Decimal("0"), description="Largest loss")
    gross_profit: Decimal = Field(default=Decimal("0"), description="Total profits")
    gross_loss: Decimal = Field(default=Decimal("0"), description="Total losses")
    total_volume_sol: Decimal = Field(
        default=Decimal("0"), description="Total volume traded"
    )
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

    start_date: datetime | None = Field(default=None, description="Start date filter")
    end_date: datetime | None = Field(default=None, description="End date filter")
    wallet_address: str | None = Field(default=None, description="Wallet filter")
    token_address: str | None = Field(default=None, description="Token filter")
    exit_reason: ExitReason | None = Field(
        default=None, description="Exit reason filter"
    )
    is_win: bool | None = Field(default=None, description="Win/loss filter")
    min_pnl: Decimal | None = Field(default=None, description="Minimum PnL filter")
    max_pnl: Decimal | None = Field(default=None, description="Maximum PnL filter")
    limit: int = Field(default=100, ge=1, le=1000, description="Result limit")
    offset: int = Field(default=0, ge=0, description="Pagination offset")


class TradeQueryResult(BaseModel):
    """Trade query results with pagination."""

    trades: list[TradeOutcome] = Field(default_factory=list)
    total_count: int = Field(default=0, description="Total matching trades")
    aggregates: AggregateMetrics = Field(default_factory=AggregateMetrics)
