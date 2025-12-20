"""Backtest preview models for parameter optimization."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class BacktestStatus(str, Enum):
    """Status of a backtest run."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExitStrategyType(str, Enum):
    """Exit strategy options for backtest."""

    TRAILING_STOP = "trailing_stop"
    FIXED_TARGETS = "fixed_targets"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


class ScoringWeights(BaseModel):
    """Scoring weights for backtest configuration."""

    wallet_score_weight: Decimal = Field(default=Decimal("0.3"), ge=0, le=1)
    token_metrics_weight: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    liquidity_weight: Decimal = Field(default=Decimal("0.2"), ge=0, le=1)
    holder_distribution_weight: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    momentum_weight: Decimal = Field(default=Decimal("0.1"), ge=0, le=1)

    @computed_field
    @property
    def total_weight(self) -> Decimal:
        """Sum of all weights."""
        return (
            self.wallet_score_weight
            + self.token_metrics_weight
            + self.liquidity_weight
            + self.holder_distribution_weight
            + self.momentum_weight
        )

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if weights sum to 1.0."""
        return abs(self.total_weight - Decimal("1.0")) < Decimal("0.01")


class PositionSizingConfig(BaseModel):
    """Position sizing configuration."""

    base_position_sol: Decimal = Field(default=Decimal("0.1"), gt=0)
    max_position_sol: Decimal = Field(default=Decimal("0.5"), gt=0)
    scale_with_confidence: bool = Field(default=True)
    confidence_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1)


class ExitStrategyConfig(BaseModel):
    """Exit strategy configuration."""

    strategy: ExitStrategyType = Field(default=ExitStrategyType.TRAILING_STOP)
    stop_loss_percent: Decimal = Field(default=Decimal("15"), ge=1, le=50)
    take_profit_percent: Decimal = Field(default=Decimal("50"), ge=5, le=500)
    trailing_stop_percent: Decimal = Field(default=Decimal("10"), ge=1, le=30)
    max_hold_minutes: int = Field(default=60, ge=5, le=1440)


class BacktestConfig(BaseModel):
    """Complete backtest configuration."""

    start_date: date
    end_date: date
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: Decimal = Field(default=Decimal("70"), ge=0, le=100)
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)
    exit_strategy: ExitStrategyConfig = Field(default_factory=ExitStrategyConfig)
    slippage_percent: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    include_gas_costs: bool = Field(default=True)
    gas_cost_sol: Decimal = Field(default=Decimal("0.0001"))

    @computed_field
    @property
    def date_range_days(self) -> int:
        """Number of days in backtest range."""
        return (self.end_date - self.start_date).days + 1


class HistoricalSignal(BaseModel):
    """Historical signal for backtesting."""

    id: str
    timestamp: datetime
    token_address: str
    source_wallet: str
    original_score: Decimal
    original_factors: dict[str, float] = Field(default_factory=dict)
    was_traded: bool
    actual_entry_price: Decimal | None = None
    actual_exit_price: Decimal | None = None
    actual_pnl_sol: Decimal | None = None
    price_at_signal: Decimal
    price_history: list[tuple[datetime, Decimal]] = Field(default_factory=list)
    max_price_after: Decimal | None = None
    min_price_after: Decimal | None = None


class SimulatedTrade(BaseModel):
    """Simulated trade from backtest."""

    signal_id: str
    token_address: str
    source_wallet: str
    simulated_score: Decimal
    would_trade: bool
    entry_price: Decimal
    exit_price: Decimal
    exit_reason: str
    position_size_sol: Decimal
    gross_pnl_sol: Decimal
    slippage_cost_sol: Decimal
    gas_cost_sol: Decimal

    @computed_field
    @property
    def net_pnl_sol(self) -> Decimal:
        """Net PnL after costs."""
        return self.gross_pnl_sol - self.slippage_cost_sol - self.gas_cost_sol

    @computed_field
    @property
    def pnl_percent(self) -> Decimal:
        """PnL as percentage of position."""
        if self.position_size_sol == 0:
            return Decimal("0")
        return (self.net_pnl_sol / self.position_size_sol * 100).quantize(
            Decimal("0.01")
        )

    @computed_field
    @property
    def is_win(self) -> bool:
        """Whether the trade was profitable."""
        return self.net_pnl_sol > 0


class PerformanceMetrics(BaseModel):
    """Performance metrics for a backtest or actual period."""

    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)
    total_pnl_sol: Decimal = Field(default=Decimal("0"))
    gross_profit_sol: Decimal = Field(default=Decimal("0"))
    gross_loss_sol: Decimal = Field(default=Decimal("0"))
    average_win_sol: Decimal = Field(default=Decimal("0"))
    average_loss_sol: Decimal = Field(default=Decimal("0"))
    max_drawdown_sol: Decimal = Field(default=Decimal("0"))
    max_consecutive_losses: int = Field(default=0)

    @computed_field
    @property
    def win_rate(self) -> Decimal:
        """Win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (
            Decimal(self.winning_trades) / Decimal(self.total_trades) * 100
        ).quantize(Decimal("0.01"))

    @computed_field
    @property
    def profit_factor(self) -> Decimal | None:
        """Profit factor (gross profit / gross loss)."""
        if self.gross_loss_sol == 0:
            return None
        return (self.gross_profit_sol / self.gross_loss_sol).quantize(Decimal("0.01"))

    @computed_field
    @property
    def expectancy(self) -> Decimal:
        """Expected value per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return (self.total_pnl_sol / Decimal(self.total_trades)).quantize(
            Decimal("0.0001")
        )


class MetricsComparison(BaseModel):
    """Comparison between actual and simulated metrics."""

    actual: PerformanceMetrics
    simulated: PerformanceMetrics

    @computed_field
    @property
    def pnl_difference_sol(self) -> Decimal:
        """Difference in PnL (simulated - actual)."""
        return self.simulated.total_pnl_sol - self.actual.total_pnl_sol

    @computed_field
    @property
    def pnl_improvement_percent(self) -> Decimal | None:
        """Percentage improvement in PnL."""
        if self.actual.total_pnl_sol == 0:
            return None
        return ((self.pnl_difference_sol / abs(self.actual.total_pnl_sol)) * 100).quantize(
            Decimal("0.01")
        )

    @computed_field
    @property
    def trade_count_difference(self) -> int:
        """Difference in trade count."""
        return self.simulated.total_trades - self.actual.total_trades

    @computed_field
    @property
    def win_rate_difference(self) -> Decimal:
        """Difference in win rate (percentage points)."""
        return self.simulated.win_rate - self.actual.win_rate

    @computed_field
    @property
    def is_improvement(self) -> bool:
        """Whether simulated performance is better."""
        pnl_better = self.pnl_difference_sol > Decimal("0.01")
        win_rate_acceptable = self.win_rate_difference > Decimal("-5")
        return pnl_better and win_rate_acceptable


class TradeComparison(BaseModel):
    """Comparison of a single trade between actual and simulated."""

    signal_id: str
    token_address: str
    timestamp: datetime
    actual_traded: bool
    actual_pnl_sol: Decimal | None = None
    simulated_traded: bool
    simulated_pnl_sol: Decimal | None = None

    @computed_field
    @property
    def outcome_changed(self) -> bool:
        """Whether the trading decision changed."""
        return self.actual_traded != self.simulated_traded

    @computed_field
    @property
    def pnl_changed(self) -> bool:
        """Whether PnL changed significantly."""
        if self.actual_pnl_sol is None and self.simulated_pnl_sol is None:
            return False
        if self.actual_pnl_sol is None or self.simulated_pnl_sol is None:
            return True
        return abs(self.simulated_pnl_sol - self.actual_pnl_sol) > Decimal("0.001")

    @computed_field
    @property
    def change_description(self) -> str:
        """Human-readable description of change."""
        if not self.actual_traded and self.simulated_traded:
            return f"NEW TRADE: Would gain {self.simulated_pnl_sol:.4f} SOL"
        elif self.actual_traded and not self.simulated_traded:
            if self.actual_pnl_sol and self.actual_pnl_sol < 0:
                return f"SKIPPED: Would avoid {abs(self.actual_pnl_sol):.4f} SOL loss"
            return "SKIPPED"
        elif self.pnl_changed:
            diff = (self.simulated_pnl_sol or Decimal("0")) - (
                self.actual_pnl_sol or Decimal("0")
            )
            return f"PnL changed by {diff:+.4f} SOL"
        return "No change"


class BacktestProgress(BaseModel):
    """Progress update during backtest execution."""

    backtest_id: str
    status: BacktestStatus
    signals_processed: int
    total_signals: int
    current_phase: str
    elapsed_seconds: int
    estimated_remaining_seconds: int | None = None

    @computed_field
    @property
    def progress_percent(self) -> Decimal:
        """Progress as percentage."""
        if self.total_signals == 0:
            return Decimal("0")
        return (
            Decimal(self.signals_processed) / Decimal(self.total_signals) * 100
        ).quantize(Decimal("0.1"))


class BacktestResult(BaseModel):
    """Complete result of a backtest run."""

    id: str
    config: BacktestConfig
    status: BacktestStatus
    started_at: datetime
    completed_at: datetime | None = None
    duration_seconds: int | None = None
    total_signals_analyzed: int = Field(default=0)
    signals_above_threshold: int = Field(default=0)
    metrics_comparison: MetricsComparison | None = None
    simulated_trades: list[SimulatedTrade] = Field(default_factory=list)
    trade_comparisons: list[TradeComparison] = Field(default_factory=list)
    error_message: str | None = None

    @computed_field
    @property
    def is_successful(self) -> bool:
        """Whether backtest completed successfully."""
        return self.status == BacktestStatus.COMPLETED and self.error_message is None

    @computed_field
    @property
    def trades_changed_count(self) -> int:
        """Number of trades with changed outcomes."""
        return sum(1 for tc in self.trade_comparisons if tc.outcome_changed or tc.pnl_changed)


class ApplySettingsRequest(BaseModel):
    """Request to apply backtest settings to production."""

    backtest_id: str
    confirm_apply: bool = Field(default=False)
    apply_scoring_weights: bool = Field(default=True)
    apply_threshold: bool = Field(default=True)
    apply_position_sizing: bool = Field(default=True)
    apply_exit_strategy: bool = Field(default=True)


class ApplySettingsResult(BaseModel):
    """Result of applying backtest settings."""

    success: bool
    backtest_id: str
    applied_at: datetime
    changes_applied: list[str] = Field(default_factory=list)
    previous_values: dict = Field(default_factory=dict)
    error_message: str | None = None
