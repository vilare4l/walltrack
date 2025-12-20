"""Performance analytics models for dashboard display."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class TimeGranularity(str, Enum):
    """Time granularity for aggregations."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class BreakdownType(str, Enum):
    """Type of performance breakdown."""

    BY_WALLET = "by_wallet"
    BY_EXIT_STRATEGY = "by_exit_strategy"
    BY_TIME_OF_DAY = "by_time_of_day"
    BY_DAY_OF_WEEK = "by_day_of_week"
    BY_TOKEN_AGE = "by_token_age"


class DateRange(BaseModel):
    """Date range for filtering metrics."""

    start_date: date = Field(..., description="Start date (inclusive)")
    end_date: date = Field(..., description="End date (inclusive)")

    @computed_field
    @property
    def days_span(self) -> int:
        """Number of days in the range."""
        return (self.end_date - self.start_date).days + 1

    @computed_field
    @property
    def previous_period_start(self) -> date:
        """Start of equivalent previous period for comparison."""
        return self.start_date - timedelta(days=self.days_span)

    @computed_field
    @property
    def previous_period_end(self) -> date:
        """End of equivalent previous period for comparison."""
        return self.start_date - timedelta(days=1)


class KeyMetrics(BaseModel):
    """Key performance metrics for display."""

    # PnL metrics
    total_pnl_sol: Decimal = Field(default=Decimal("0"), description="Total PnL in SOL")
    total_pnl_percent: Decimal = Field(
        default=Decimal("0"), description="Total PnL as percentage"
    )
    gross_profit_sol: Decimal = Field(
        default=Decimal("0"), description="Sum of winning trades"
    )
    gross_loss_sol: Decimal = Field(
        default=Decimal("0"), description="Sum of losing trades (absolute)"
    )

    # Trade counts
    total_trades: int = Field(default=0, description="Total number of trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")

    # Averages
    average_win_sol: Decimal = Field(
        default=Decimal("0"), description="Average winning trade"
    )
    average_loss_sol: Decimal = Field(
        default=Decimal("0"), description="Average losing trade (absolute)"
    )
    average_trade_duration_seconds: int = Field(
        default=0, description="Average trade duration"
    )

    # Risk metrics
    max_drawdown_sol: Decimal = Field(
        default=Decimal("0"), description="Maximum drawdown in SOL"
    )
    max_drawdown_percent: Decimal = Field(
        default=Decimal("0"), description="Maximum drawdown as percentage"
    )

    # Optional advanced metrics
    sharpe_ratio: Decimal | None = Field(
        default=None, description="Sharpe ratio if calculable"
    )
    sortino_ratio: Decimal | None = Field(
        default=None, description="Sortino ratio if calculable"
    )

    @computed_field
    @property
    def win_rate(self) -> Decimal:
        """Win rate as percentage."""
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

    @computed_field
    @property
    def risk_reward_ratio(self) -> Decimal | None:
        """Average win / Average loss ratio."""
        if self.average_loss_sol == 0:
            return None
        return (self.average_win_sol / self.average_loss_sol).quantize(Decimal("0.01"))


class PeriodComparison(BaseModel):
    """Comparison between current and previous period."""

    current_metrics: KeyMetrics
    previous_metrics: KeyMetrics

    @computed_field
    @property
    def pnl_change_sol(self) -> Decimal:
        """Change in PnL between periods."""
        return self.current_metrics.total_pnl_sol - self.previous_metrics.total_pnl_sol

    @computed_field
    @property
    def pnl_change_percent(self) -> Decimal | None:
        """Percentage change in PnL."""
        if self.previous_metrics.total_pnl_sol == 0:
            return None
        return (
            (self.pnl_change_sol / abs(self.previous_metrics.total_pnl_sol)) * 100
        ).quantize(Decimal("0.01"))

    @computed_field
    @property
    def win_rate_change(self) -> Decimal:
        """Change in win rate (percentage points)."""
        return self.current_metrics.win_rate - self.previous_metrics.win_rate

    @computed_field
    @property
    def trade_count_change(self) -> int:
        """Change in number of trades."""
        return self.current_metrics.total_trades - self.previous_metrics.total_trades


class TimeSeriesPoint(BaseModel):
    """Single point in a time series."""

    timestamp: datetime
    value: Decimal
    cumulative_value: Decimal | None = None
    trade_count: int = Field(default=0)


class PnLTimeSeries(BaseModel):
    """PnL data over time for charting."""

    granularity: TimeGranularity
    points: list[TimeSeriesPoint] = Field(default_factory=list)

    @computed_field
    @property
    def cumulative_final(self) -> Decimal:
        """Final cumulative value."""
        if not self.points:
            return Decimal("0")
        return self.points[-1].cumulative_value or Decimal("0")

    @computed_field
    @property
    def peak_value(self) -> Decimal:
        """Peak cumulative value."""
        if not self.points:
            return Decimal("0")
        return max(p.cumulative_value or Decimal("0") for p in self.points)

    @computed_field
    @property
    def trough_value(self) -> Decimal:
        """Trough cumulative value."""
        if not self.points:
            return Decimal("0")
        return min(p.cumulative_value or Decimal("0") for p in self.points)


class WinRateTrend(BaseModel):
    """Win rate trend over time."""

    granularity: TimeGranularity
    points: list[TimeSeriesPoint] = Field(default_factory=list)
    rolling_window_trades: int = Field(default=20, description="Rolling window size")


class BreakdownCategory(BaseModel):
    """Single category in a breakdown view."""

    category_name: str
    category_value: str
    trade_count: int
    pnl_sol: Decimal
    win_rate: Decimal
    average_pnl_sol: Decimal
    contribution_percent: Decimal = Field(
        default=Decimal("0"), description="PnL contribution to total"
    )


class BreakdownView(BaseModel):
    """Performance breakdown by category."""

    breakdown_type: BreakdownType
    categories: list[BreakdownCategory] = Field(default_factory=list)
    total_pnl_sol: Decimal = Field(default=Decimal("0"))

    def with_contributions(self) -> "BreakdownView":
        """Calculate contribution percentages for each category."""
        if self.total_pnl_sol == 0:
            return self
        for cat in self.categories:
            cat.contribution_percent = (
                (cat.pnl_sol / abs(self.total_pnl_sol)) * 100
            ).quantize(Decimal("0.01"))
        return self


class PerformanceDashboardData(BaseModel):
    """Complete data for performance dashboard."""

    date_range: DateRange
    key_metrics: KeyMetrics
    period_comparison: PeriodComparison | None = None
    pnl_time_series: PnLTimeSeries
    win_rate_trend: WinRateTrend
    breakdowns: dict[BreakdownType, BreakdownView] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    load_time_ms: int = Field(default=0, description="Time to generate this data")


class DashboardQuery(BaseModel):
    """Query parameters for dashboard data."""

    date_range: DateRange
    include_comparison: bool = Field(default=True)
    time_granularity: TimeGranularity = Field(default=TimeGranularity.DAILY)
    breakdowns_requested: list[BreakdownType] = Field(default_factory=list)
