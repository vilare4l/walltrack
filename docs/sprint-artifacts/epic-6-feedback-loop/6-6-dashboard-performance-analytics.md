# Story 6.6: Dashboard - Performance Metrics and Analytics

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: High
- **FR**: FR42

## User Story

**As an** operator,
**I want** comprehensive performance metrics in the dashboard,
**So that** I can monitor system profitability.

## Acceptance Criteria

### AC 1: Key Metrics Display
**Given** dashboard Performance tab
**When** operator views metrics
**Then** key metrics are displayed:
- Total PnL (absolute and %)
- Win rate (overall and rolling)
- Total trades (wins/losses)
- Average win / Average loss
- Profit factor (gross profit / gross loss)
- Sharpe ratio (if calculable)

### AC 2: Performance Charts
**Given** performance over time
**When** charts are displayed
**Then** PnL curve is shown (cumulative over time)
**And** daily/weekly PnL bars are shown
**And** win rate trend line is shown

### AC 3: Date Range Selection
**Given** date range selector
**When** operator selects range
**Then** all metrics recalculate for selected period
**And** comparison to previous period is available

### AC 4: Breakdown Views
**Given** breakdown views
**When** operator drills down
**Then** performance by wallet is available
**And** performance by exit strategy is available
**And** performance by time of day is available

### AC 5: Performance
**Given** dashboard loads
**When** data is fetched
**Then** response time is < 2 seconds (NFR3)
**And** charts render smoothly

## Technical Notes

- FR42: View performance metrics (PnL, win rate, trade count)
- Implement in `src/walltrack/ui/components/performance.py`
- Use plotly or similar for charts in Gradio

---

## Technical Specification

### 1. Pydantic Models

```python
# src/walltrack/core/feedback/models/performance_analytics.py
"""Performance analytics models for dashboard display."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
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
        from datetime import timedelta
        return self.start_date - timedelta(days=self.days_span)

    @computed_field
    @property
    def previous_period_end(self) -> date:
        """End of equivalent previous period for comparison."""
        from datetime import timedelta
        return self.start_date - timedelta(days=1)


class KeyMetrics(BaseModel):
    """Key performance metrics for display."""
    # PnL metrics
    total_pnl_sol: Decimal = Field(default=Decimal("0"), description="Total PnL in SOL")
    total_pnl_percent: Decimal = Field(default=Decimal("0"), description="Total PnL as percentage")
    gross_profit_sol: Decimal = Field(default=Decimal("0"), description="Sum of winning trades")
    gross_loss_sol: Decimal = Field(default=Decimal("0"), description="Sum of losing trades (absolute)")

    # Trade counts
    total_trades: int = Field(default=0, description="Total number of trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")

    # Averages
    average_win_sol: Decimal = Field(default=Decimal("0"), description="Average winning trade")
    average_loss_sol: Decimal = Field(default=Decimal("0"), description="Average losing trade (absolute)")
    average_trade_duration_seconds: int = Field(default=0, description="Average trade duration")

    # Risk metrics
    max_drawdown_sol: Decimal = Field(default=Decimal("0"), description="Maximum drawdown in SOL")
    max_drawdown_percent: Decimal = Field(default=Decimal("0"), description="Maximum drawdown as percentage")

    # Optional advanced metrics
    sharpe_ratio: Optional[Decimal] = Field(default=None, description="Sharpe ratio if calculable")
    sortino_ratio: Optional[Decimal] = Field(default=None, description="Sortino ratio if calculable")

    @computed_field
    @property
    def win_rate(self) -> Decimal:
        """Win rate as percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.total_trades) * 100).quantize(Decimal("0.01"))

    @computed_field
    @property
    def profit_factor(self) -> Optional[Decimal]:
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
        return (self.total_pnl_sol / Decimal(self.total_trades)).quantize(Decimal("0.0001"))

    @computed_field
    @property
    def risk_reward_ratio(self) -> Optional[Decimal]:
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
    def pnl_change_percent(self) -> Optional[Decimal]:
        """Percentage change in PnL."""
        if self.previous_metrics.total_pnl_sol == 0:
            return None
        return ((self.pnl_change_sol / abs(self.previous_metrics.total_pnl_sol)) * 100).quantize(Decimal("0.01"))

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
    cumulative_value: Optional[Decimal] = None
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

    @computed_field
    @property
    def contribution_percent(self) -> Decimal:
        """This category's PnL contribution to total (calculated externally)."""
        return Decimal("0")  # Set by parent


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
            # Direct assignment since computed_field returns 0
            cat.__dict__["contribution_percent"] = (
                (cat.pnl_sol / abs(self.total_pnl_sol)) * 100
            ).quantize(Decimal("0.01"))
        return self


class PerformanceDashboardData(BaseModel):
    """Complete data for performance dashboard."""
    date_range: DateRange
    key_metrics: KeyMetrics
    period_comparison: Optional[PeriodComparison] = None
    pnl_time_series: PnLTimeSeries
    win_rate_trend: WinRateTrend
    breakdowns: dict[BreakdownType, BreakdownView] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    load_time_ms: int = Field(default=0, description="Time to generate this data")


class DashboardQuery(BaseModel):
    """Query parameters for dashboard data."""
    date_range: DateRange
    include_comparison: bool = Field(default=True)
    time_granularity: TimeGranularity = Field(default=TimeGranularity.DAILY)
    breakdowns_requested: list[BreakdownType] = Field(default_factory=list)
```

### 2. Service Layer

```python
# src/walltrack/core/feedback/services/performance_dashboard.py
"""Performance dashboard data aggregation service."""

import structlog
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional
import asyncio

from ..models.performance_analytics import (
    DateRange, KeyMetrics, PeriodComparison, TimeSeriesPoint,
    PnLTimeSeries, WinRateTrend, BreakdownCategory, BreakdownView,
    BreakdownType, TimeGranularity, PerformanceDashboardData, DashboardQuery
)
from ..models.trade_outcome import TradeOutcome
from ...db.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class PerformanceDashboardService:
    """Aggregates performance data for dashboard display."""

    def __init__(self):
        self._supabase = None
        self._cache: dict[str, tuple[datetime, PerformanceDashboardData]] = {}
        self._cache_ttl_seconds = 60  # Cache for 1 minute

    async def _get_supabase(self):
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    def _cache_key(self, query: DashboardQuery) -> str:
        """Generate cache key for query."""
        return f"{query.date_range.start_date}_{query.date_range.end_date}_{query.time_granularity}"

    async def get_dashboard_data(
        self,
        query: DashboardQuery
    ) -> PerformanceDashboardData:
        """
        Get complete dashboard data for the given query.

        Uses caching to ensure < 2s response time (NFR3).
        """
        start_time = datetime.utcnow()

        # Check cache
        cache_key = self._cache_key(query)
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.utcnow() - cached_time).seconds < self._cache_ttl_seconds:
                logger.debug("returning_cached_dashboard_data", cache_key=cache_key)
                return cached_data

        # Fetch trades for date range
        trades = await self._fetch_trades(query.date_range)

        # Calculate key metrics
        key_metrics = await self._calculate_key_metrics(trades)

        # Period comparison if requested
        period_comparison = None
        if query.include_comparison:
            previous_range = DateRange(
                start_date=query.date_range.previous_period_start,
                end_date=query.date_range.previous_period_end
            )
            previous_trades = await self._fetch_trades(previous_range)
            previous_metrics = await self._calculate_key_metrics(previous_trades)
            period_comparison = PeriodComparison(
                current_metrics=key_metrics,
                previous_metrics=previous_metrics
            )

        # Build time series (run in parallel)
        pnl_series_task = self._build_pnl_time_series(trades, query.time_granularity)
        win_rate_task = self._build_win_rate_trend(trades, query.time_granularity)

        pnl_time_series, win_rate_trend = await asyncio.gather(
            pnl_series_task, win_rate_task
        )

        # Build requested breakdowns
        breakdowns = {}
        for breakdown_type in query.breakdowns_requested:
            breakdowns[breakdown_type] = await self._build_breakdown(
                trades, breakdown_type, key_metrics.total_pnl_sol
            )

        load_time_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        result = PerformanceDashboardData(
            date_range=query.date_range,
            key_metrics=key_metrics,
            period_comparison=period_comparison,
            pnl_time_series=pnl_time_series,
            win_rate_trend=win_rate_trend,
            breakdowns=breakdowns,
            load_time_ms=load_time_ms
        )

        # Cache result
        self._cache[cache_key] = (datetime.utcnow(), result)

        logger.info(
            "dashboard_data_generated",
            date_range=f"{query.date_range.start_date} to {query.date_range.end_date}",
            trade_count=len(trades),
            load_time_ms=load_time_ms
        )

        return result

    async def _fetch_trades(self, date_range: DateRange) -> list[dict]:
        """Fetch trades within date range."""
        supabase = await self._get_supabase()

        response = await supabase.table("trade_outcomes").select("*").gte(
            "exit_timestamp", date_range.start_date.isoformat()
        ).lte(
            "exit_timestamp", f"{date_range.end_date}T23:59:59"
        ).execute()

        return response.data or []

    async def _calculate_key_metrics(self, trades: list[dict]) -> KeyMetrics:
        """Calculate key metrics from trades."""
        if not trades:
            return KeyMetrics()

        total_pnl = Decimal("0")
        gross_profit = Decimal("0")
        gross_loss = Decimal("0")
        winning_trades = 0
        losing_trades = 0
        win_pnls = []
        loss_pnls = []
        durations = []

        # Track for drawdown calculation
        cumulative_pnl = Decimal("0")
        peak_pnl = Decimal("0")
        max_drawdown = Decimal("0")

        for trade in trades:
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            total_pnl += pnl
            cumulative_pnl += pnl

            if pnl > 0:
                gross_profit += pnl
                winning_trades += 1
                win_pnls.append(pnl)
            else:
                gross_loss += abs(pnl)
                losing_trades += 1
                loss_pnls.append(abs(pnl))

            # Duration
            if trade.get("entry_timestamp") and trade.get("exit_timestamp"):
                entry = datetime.fromisoformat(trade["entry_timestamp"].replace("Z", "+00:00"))
                exit_t = datetime.fromisoformat(trade["exit_timestamp"].replace("Z", "+00:00"))
                durations.append((exit_t - entry).total_seconds())

            # Drawdown tracking
            if cumulative_pnl > peak_pnl:
                peak_pnl = cumulative_pnl
            drawdown = peak_pnl - cumulative_pnl
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Calculate averages
        average_win = sum(win_pnls) / len(win_pnls) if win_pnls else Decimal("0")
        average_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else Decimal("0")
        average_duration = int(sum(durations) / len(durations)) if durations else 0

        # Calculate total invested for percentage
        total_invested = sum(Decimal(str(t.get("entry_amount_sol", 0))) for t in trades)
        total_pnl_percent = (total_pnl / total_invested * 100) if total_invested else Decimal("0")
        max_drawdown_percent = (max_drawdown / peak_pnl * 100) if peak_pnl > 0 else Decimal("0")

        # Sharpe ratio (simplified - daily returns)
        sharpe_ratio = await self._calculate_sharpe_ratio(trades)

        return KeyMetrics(
            total_pnl_sol=total_pnl.quantize(Decimal("0.0001")),
            total_pnl_percent=total_pnl_percent.quantize(Decimal("0.01")),
            gross_profit_sol=gross_profit.quantize(Decimal("0.0001")),
            gross_loss_sol=gross_loss.quantize(Decimal("0.0001")),
            total_trades=len(trades),
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            average_win_sol=average_win.quantize(Decimal("0.0001")),
            average_loss_sol=average_loss.quantize(Decimal("0.0001")),
            average_trade_duration_seconds=average_duration,
            max_drawdown_sol=max_drawdown.quantize(Decimal("0.0001")),
            max_drawdown_percent=max_drawdown_percent.quantize(Decimal("0.01")),
            sharpe_ratio=sharpe_ratio
        )

    async def _calculate_sharpe_ratio(
        self,
        trades: list[dict],
        risk_free_rate: Decimal = Decimal("0.05")  # 5% annual
    ) -> Optional[Decimal]:
        """Calculate Sharpe ratio from daily returns."""
        if len(trades) < 10:
            return None

        # Group by day
        daily_returns: dict[date, Decimal] = {}
        for trade in trades:
            exit_ts = trade.get("exit_timestamp")
            if not exit_ts:
                continue
            trade_date = datetime.fromisoformat(exit_ts.replace("Z", "+00:00")).date()
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            daily_returns[trade_date] = daily_returns.get(trade_date, Decimal("0")) + pnl

        if len(daily_returns) < 5:
            return None

        returns = list(daily_returns.values())
        mean_return = sum(returns) / len(returns)

        # Standard deviation
        variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
        std_dev = variance ** Decimal("0.5")

        if std_dev == 0:
            return None

        # Annualized Sharpe (assuming 252 trading days)
        daily_risk_free = risk_free_rate / 252
        sharpe = ((mean_return - daily_risk_free) / std_dev) * (Decimal("252") ** Decimal("0.5"))

        return sharpe.quantize(Decimal("0.01"))

    async def _build_pnl_time_series(
        self,
        trades: list[dict],
        granularity: TimeGranularity
    ) -> PnLTimeSeries:
        """Build PnL time series for charting."""
        if not trades:
            return PnLTimeSeries(granularity=granularity)

        # Sort trades by exit timestamp
        sorted_trades = sorted(trades, key=lambda t: t.get("exit_timestamp", ""))

        # Group by time period
        periods: dict[str, list[dict]] = {}
        for trade in sorted_trades:
            exit_ts = trade.get("exit_timestamp")
            if not exit_ts:
                continue
            dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
            period_key = self._get_period_key(dt, granularity)
            if period_key not in periods:
                periods[period_key] = []
            periods[period_key].append(trade)

        # Build points
        points = []
        cumulative = Decimal("0")

        for period_key in sorted(periods.keys()):
            period_trades = periods[period_key]
            period_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in period_trades)
            cumulative += period_pnl

            points.append(TimeSeriesPoint(
                timestamp=self._period_key_to_datetime(period_key, granularity),
                value=period_pnl.quantize(Decimal("0.0001")),
                cumulative_value=cumulative.quantize(Decimal("0.0001")),
                trade_count=len(period_trades)
            ))

        return PnLTimeSeries(granularity=granularity, points=points)

    async def _build_win_rate_trend(
        self,
        trades: list[dict],
        granularity: TimeGranularity,
        rolling_window: int = 20
    ) -> WinRateTrend:
        """Build win rate trend with rolling window."""
        if not trades:
            return WinRateTrend(granularity=granularity, rolling_window_trades=rolling_window)

        # Sort trades by exit timestamp
        sorted_trades = sorted(trades, key=lambda t: t.get("exit_timestamp", ""))

        # Calculate rolling win rate
        points = []
        for i, trade in enumerate(sorted_trades):
            exit_ts = trade.get("exit_timestamp")
            if not exit_ts:
                continue

            # Get window of trades
            start_idx = max(0, i - rolling_window + 1)
            window = sorted_trades[start_idx:i + 1]

            wins = sum(1 for t in window if Decimal(str(t.get("realized_pnl_sol", 0))) > 0)
            win_rate = Decimal(wins) / Decimal(len(window)) * 100

            dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
            points.append(TimeSeriesPoint(
                timestamp=dt,
                value=win_rate.quantize(Decimal("0.01")),
                trade_count=len(window)
            ))

        return WinRateTrend(
            granularity=granularity,
            points=points,
            rolling_window_trades=rolling_window
        )

    async def _build_breakdown(
        self,
        trades: list[dict],
        breakdown_type: BreakdownType,
        total_pnl: Decimal
    ) -> BreakdownView:
        """Build breakdown view by category."""
        if not trades:
            return BreakdownView(breakdown_type=breakdown_type, total_pnl_sol=total_pnl)

        # Group by category
        groups: dict[str, list[dict]] = {}

        for trade in trades:
            category_value = self._get_category_value(trade, breakdown_type)
            if category_value not in groups:
                groups[category_value] = []
            groups[category_value].append(trade)

        # Build categories
        categories = []
        for cat_value, cat_trades in groups.items():
            pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in cat_trades)
            wins = sum(1 for t in cat_trades if Decimal(str(t.get("realized_pnl_sol", 0))) > 0)
            win_rate = Decimal(wins) / Decimal(len(cat_trades)) * 100 if cat_trades else Decimal("0")
            avg_pnl = pnl / len(cat_trades) if cat_trades else Decimal("0")

            categories.append(BreakdownCategory(
                category_name=breakdown_type.value,
                category_value=cat_value,
                trade_count=len(cat_trades),
                pnl_sol=pnl.quantize(Decimal("0.0001")),
                win_rate=win_rate.quantize(Decimal("0.01")),
                average_pnl_sol=avg_pnl.quantize(Decimal("0.0001"))
            ))

        # Sort by PnL descending
        categories.sort(key=lambda c: c.pnl_sol, reverse=True)

        breakdown = BreakdownView(
            breakdown_type=breakdown_type,
            categories=categories,
            total_pnl_sol=total_pnl
        )

        return breakdown.with_contributions()

    def _get_category_value(self, trade: dict, breakdown_type: BreakdownType) -> str:
        """Extract category value from trade based on breakdown type."""
        if breakdown_type == BreakdownType.BY_WALLET:
            return trade.get("source_wallet", "unknown")[:8] + "..."

        elif breakdown_type == BreakdownType.BY_EXIT_STRATEGY:
            return trade.get("exit_reason", "unknown")

        elif breakdown_type == BreakdownType.BY_TIME_OF_DAY:
            exit_ts = trade.get("exit_timestamp")
            if exit_ts:
                dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
                hour = dt.hour
                if 0 <= hour < 6:
                    return "Night (00-06)"
                elif 6 <= hour < 12:
                    return "Morning (06-12)"
                elif 12 <= hour < 18:
                    return "Afternoon (12-18)"
                else:
                    return "Evening (18-24)"
            return "unknown"

        elif breakdown_type == BreakdownType.BY_DAY_OF_WEEK:
            exit_ts = trade.get("exit_timestamp")
            if exit_ts:
                dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
                return dt.strftime("%A")
            return "unknown"

        elif breakdown_type == BreakdownType.BY_TOKEN_AGE:
            token_age_minutes = trade.get("token_age_minutes", 0)
            if token_age_minutes < 5:
                return "0-5 min"
            elif token_age_minutes < 15:
                return "5-15 min"
            elif token_age_minutes < 60:
                return "15-60 min"
            else:
                return "60+ min"

        return "unknown"

    def _get_period_key(self, dt: datetime, granularity: TimeGranularity) -> str:
        """Get period key for grouping."""
        if granularity == TimeGranularity.HOURLY:
            return dt.strftime("%Y-%m-%d-%H")
        elif granularity == TimeGranularity.DAILY:
            return dt.strftime("%Y-%m-%d")
        elif granularity == TimeGranularity.WEEKLY:
            return dt.strftime("%Y-W%W")
        elif granularity == TimeGranularity.MONTHLY:
            return dt.strftime("%Y-%m")
        return dt.strftime("%Y-%m-%d")

    def _period_key_to_datetime(self, key: str, granularity: TimeGranularity) -> datetime:
        """Convert period key back to datetime."""
        if granularity == TimeGranularity.HOURLY:
            return datetime.strptime(key, "%Y-%m-%d-%H")
        elif granularity == TimeGranularity.DAILY:
            return datetime.strptime(key, "%Y-%m-%d")
        elif granularity == TimeGranularity.WEEKLY:
            return datetime.strptime(key + "-1", "%Y-W%W-%w")
        elif granularity == TimeGranularity.MONTHLY:
            return datetime.strptime(key + "-01", "%Y-%m-%d")
        return datetime.strptime(key, "%Y-%m-%d")

    def clear_cache(self):
        """Clear the dashboard cache."""
        self._cache.clear()
        logger.info("dashboard_cache_cleared")


# Singleton instance
_dashboard_service: Optional[PerformanceDashboardService] = None


async def get_dashboard_service() -> PerformanceDashboardService:
    """Get the singleton dashboard service instance."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = PerformanceDashboardService()
    return _dashboard_service
```

### 3. Database Schema (SQL)

```sql
-- Performance dashboard relies on existing trade_outcomes table
-- Add materialized views for performance optimization

-- Daily aggregates materialized view
CREATE MATERIALIZED VIEW IF NOT EXISTS daily_performance_summary AS
SELECT
    DATE(exit_timestamp) as trade_date,
    COUNT(*) as trade_count,
    SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(CASE WHEN realized_pnl_sol <= 0 THEN 1 ELSE 0 END) as losing_trades,
    SUM(realized_pnl_sol) as total_pnl_sol,
    SUM(CASE WHEN realized_pnl_sol > 0 THEN realized_pnl_sol ELSE 0 END) as gross_profit_sol,
    SUM(CASE WHEN realized_pnl_sol < 0 THEN ABS(realized_pnl_sol) ELSE 0 END) as gross_loss_sol,
    AVG(CASE WHEN realized_pnl_sol > 0 THEN realized_pnl_sol END) as avg_win_sol,
    AVG(CASE WHEN realized_pnl_sol < 0 THEN ABS(realized_pnl_sol) END) as avg_loss_sol,
    AVG(EXTRACT(EPOCH FROM (exit_timestamp - entry_timestamp))) as avg_duration_seconds
FROM trade_outcomes
WHERE exit_timestamp IS NOT NULL
GROUP BY DATE(exit_timestamp)
ORDER BY trade_date DESC;

-- Index for fast refresh
CREATE INDEX IF NOT EXISTS idx_trade_outcomes_exit_date
ON trade_outcomes (DATE(exit_timestamp));

-- Breakdown by wallet
CREATE MATERIALIZED VIEW IF NOT EXISTS wallet_performance_summary AS
SELECT
    source_wallet,
    COUNT(*) as trade_count,
    SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(realized_pnl_sol) as total_pnl_sol,
    ROUND(
        SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as win_rate
FROM trade_outcomes
WHERE exit_timestamp IS NOT NULL
GROUP BY source_wallet
ORDER BY total_pnl_sol DESC;

-- Breakdown by exit reason
CREATE MATERIALIZED VIEW IF NOT EXISTS exit_strategy_summary AS
SELECT
    exit_reason,
    COUNT(*) as trade_count,
    SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END) as winning_trades,
    SUM(realized_pnl_sol) as total_pnl_sol,
    AVG(realized_pnl_sol) as avg_pnl_sol,
    ROUND(
        SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as win_rate
FROM trade_outcomes
WHERE exit_timestamp IS NOT NULL
GROUP BY exit_reason
ORDER BY trade_count DESC;

-- Hourly performance pattern
CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_performance_pattern AS
SELECT
    EXTRACT(HOUR FROM exit_timestamp) as hour_of_day,
    COUNT(*) as trade_count,
    SUM(realized_pnl_sol) as total_pnl_sol,
    ROUND(
        SUM(CASE WHEN realized_pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC /
        NULLIF(COUNT(*), 0) * 100,
        2
    ) as win_rate
FROM trade_outcomes
WHERE exit_timestamp IS NOT NULL
GROUP BY EXTRACT(HOUR FROM exit_timestamp)
ORDER BY hour_of_day;

-- Function to refresh all materialized views
CREATE OR REPLACE FUNCTION refresh_performance_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY daily_performance_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY wallet_performance_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY exit_strategy_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY hourly_performance_pattern;
END;
$$ LANGUAGE plpgsql;

-- Schedule refresh (via pg_cron or application)
-- SELECT cron.schedule('refresh-perf-views', '*/5 * * * *', 'SELECT refresh_performance_views()');
```

### 4. API Routes

```python
# src/walltrack/api/routes/performance_dashboard.py
"""Performance dashboard API routes."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional

from ...core.feedback.models.performance_analytics import (
    DateRange, DashboardQuery, PerformanceDashboardData,
    TimeGranularity, BreakdownType, KeyMetrics
)
from ...core.feedback.services.performance_dashboard import (
    get_dashboard_service, PerformanceDashboardService
)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("/dashboard", response_model=PerformanceDashboardData)
async def get_dashboard_data(
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date"),
    include_comparison: bool = Query(True, description="Include period comparison"),
    granularity: TimeGranularity = Query(TimeGranularity.DAILY),
    breakdowns: Optional[str] = Query(None, description="Comma-separated breakdown types"),
    service: PerformanceDashboardService = Depends(get_dashboard_service)
) -> PerformanceDashboardData:
    """
    Get complete dashboard data for date range.

    Returns key metrics, time series, and breakdown views.
    Response time target: < 2 seconds (NFR3).
    """
    # Validate date range
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    if (end_date - start_date).days > 365:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 365 days")

    # Parse breakdowns
    breakdown_types = []
    if breakdowns:
        for b in breakdowns.split(","):
            try:
                breakdown_types.append(BreakdownType(b.strip()))
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid breakdown type: {b}")

    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=include_comparison,
        time_granularity=granularity,
        breakdowns_requested=breakdown_types
    )

    return await service.get_dashboard_data(query)


@router.get("/metrics", response_model=KeyMetrics)
async def get_key_metrics(
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    service: PerformanceDashboardService = Depends(get_dashboard_service)
) -> KeyMetrics:
    """Get key performance metrics only (lightweight endpoint)."""
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=False,
        breakdowns_requested=[]
    )

    data = await service.get_dashboard_data(query)
    return data.key_metrics


@router.get("/presets/{preset}")
async def get_preset_data(
    preset: str,
    service: PerformanceDashboardService = Depends(get_dashboard_service)
) -> PerformanceDashboardData:
    """
    Get dashboard data for common presets.

    Presets: today, week, month, quarter, year, all
    """
    today = date.today()

    presets = {
        "today": (today, today),
        "week": (today - timedelta(days=7), today),
        "month": (today - timedelta(days=30), today),
        "quarter": (today - timedelta(days=90), today),
        "year": (today - timedelta(days=365), today),
    }

    if preset not in presets:
        raise HTTPException(status_code=400, detail=f"Unknown preset: {preset}")

    start_date, end_date = presets[preset]

    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=True,
        time_granularity=TimeGranularity.DAILY if preset in ["today", "week"] else TimeGranularity.WEEKLY,
        breakdowns_requested=[BreakdownType.BY_EXIT_STRATEGY, BreakdownType.BY_TIME_OF_DAY]
    )

    return await service.get_dashboard_data(query)


@router.post("/cache/clear")
async def clear_cache(
    service: PerformanceDashboardService = Depends(get_dashboard_service)
) -> dict:
    """Clear dashboard cache (for manual refresh)."""
    service.clear_cache()
    return {"status": "cache_cleared"}
```

### 5. Gradio UI Component

```python
# src/walltrack/ui/components/performance.py
"""Performance dashboard Gradio component."""

import gradio as gr
import plotly.graph_objects as go
import plotly.express as px
from datetime import date, timedelta
from decimal import Decimal
import pandas as pd
from typing import Optional

from ...core.feedback.services.performance_dashboard import get_dashboard_service
from ...core.feedback.models.performance_analytics import (
    DateRange, DashboardQuery, TimeGranularity, BreakdownType,
    PerformanceDashboardData, KeyMetrics
)


async def fetch_dashboard_data(
    start_date: str,
    end_date: str,
    granularity: str,
    breakdowns: list[str]
) -> PerformanceDashboardData:
    """Fetch dashboard data from service."""
    service = await get_dashboard_service()

    query = DashboardQuery(
        date_range=DateRange(
            start_date=date.fromisoformat(start_date),
            end_date=date.fromisoformat(end_date)
        ),
        include_comparison=True,
        time_granularity=TimeGranularity(granularity),
        breakdowns_requested=[BreakdownType(b) for b in breakdowns]
    )

    return await service.get_dashboard_data(query)


def format_sol(value: Decimal) -> str:
    """Format SOL value for display."""
    return f"{float(value):,.4f} SOL"


def format_percent(value: Decimal) -> str:
    """Format percentage for display."""
    return f"{float(value):,.2f}%"


def create_metrics_display(metrics: KeyMetrics) -> str:
    """Create HTML display for key metrics."""
    pnl_color = "green" if metrics.total_pnl_sol >= 0 else "red"

    return f"""
    <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 16px;">
        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <div style="color: #888; font-size: 12px;">Total PnL</div>
            <div style="color: {pnl_color}; font-size: 24px; font-weight: bold;">
                {format_sol(metrics.total_pnl_sol)}
            </div>
            <div style="color: {pnl_color}; font-size: 14px;">
                ({format_percent(metrics.total_pnl_percent)})
            </div>
        </div>

        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <div style="color: #888; font-size: 12px;">Win Rate</div>
            <div style="color: #4ade80; font-size: 24px; font-weight: bold;">
                {format_percent(metrics.win_rate)}
            </div>
            <div style="color: #888; font-size: 14px;">
                {metrics.winning_trades}W / {metrics.losing_trades}L
            </div>
        </div>

        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <div style="color: #888; font-size: 12px;">Profit Factor</div>
            <div style="color: #60a5fa; font-size: 24px; font-weight: bold;">
                {float(metrics.profit_factor or 0):.2f}
            </div>
            <div style="color: #888; font-size: 14px;">
                Avg Win: {format_sol(metrics.average_win_sol)}
            </div>
        </div>

        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <div style="color: #888; font-size: 12px;">Trades</div>
            <div style="color: white; font-size: 24px; font-weight: bold;">
                {metrics.total_trades}
            </div>
            <div style="color: #888; font-size: 14px;">
                Max DD: {format_percent(metrics.max_drawdown_percent)}
            </div>
        </div>
    </div>
    """


def create_pnl_chart(data: PerformanceDashboardData) -> go.Figure:
    """Create cumulative PnL chart."""
    fig = go.Figure()

    if data.pnl_time_series.points:
        timestamps = [p.timestamp for p in data.pnl_time_series.points]
        cumulative = [float(p.cumulative_value or 0) for p in data.pnl_time_series.points]
        daily = [float(p.value) for p in data.pnl_time_series.points]

        # Cumulative line
        fig.add_trace(go.Scatter(
            x=timestamps,
            y=cumulative,
            mode='lines',
            name='Cumulative PnL',
            line=dict(color='#4ade80', width=2),
            fill='tozeroy',
            fillcolor='rgba(74, 222, 128, 0.1)'
        ))

        # Daily bars
        colors = ['#4ade80' if v >= 0 else '#f87171' for v in daily]
        fig.add_trace(go.Bar(
            x=timestamps,
            y=daily,
            name='Daily PnL',
            marker_color=colors,
            opacity=0.5,
            yaxis='y2'
        ))

    fig.update_layout(
        title='PnL Over Time',
        template='plotly_dark',
        height=400,
        yaxis=dict(title='Cumulative PnL (SOL)', side='left'),
        yaxis2=dict(title='Daily PnL (SOL)', side='right', overlaying='y'),
        legend=dict(x=0, y=1.1, orientation='h'),
        hovermode='x unified'
    )

    return fig


def create_win_rate_chart(data: PerformanceDashboardData) -> go.Figure:
    """Create win rate trend chart."""
    fig = go.Figure()

    if data.win_rate_trend.points:
        timestamps = [p.timestamp for p in data.win_rate_trend.points]
        win_rates = [float(p.value) for p in data.win_rate_trend.points]

        fig.add_trace(go.Scatter(
            x=timestamps,
            y=win_rates,
            mode='lines+markers',
            name=f'Win Rate ({data.win_rate_trend.rolling_window_trades} trade rolling)',
            line=dict(color='#60a5fa', width=2),
            marker=dict(size=4)
        ))

        # 50% reference line
        fig.add_hline(y=50, line_dash="dash", line_color="#888",
                      annotation_text="50%", annotation_position="right")

    fig.update_layout(
        title='Win Rate Trend',
        template='plotly_dark',
        height=300,
        yaxis=dict(title='Win Rate (%)', range=[0, 100]),
        hovermode='x unified'
    )

    return fig


def create_breakdown_chart(data: PerformanceDashboardData, breakdown_type: BreakdownType) -> go.Figure:
    """Create breakdown pie/bar chart."""
    if breakdown_type not in data.breakdowns:
        return go.Figure()

    breakdown = data.breakdowns[breakdown_type]

    if not breakdown.categories:
        return go.Figure()

    categories = [c.category_value for c in breakdown.categories]
    pnls = [float(c.pnl_sol) for c in breakdown.categories]
    win_rates = [float(c.win_rate) for c in breakdown.categories]
    counts = [c.trade_count for c in breakdown.categories]

    fig = go.Figure()

    # Bar chart for PnL
    colors = ['#4ade80' if p >= 0 else '#f87171' for p in pnls]
    fig.add_trace(go.Bar(
        x=categories,
        y=pnls,
        name='PnL (SOL)',
        marker_color=colors,
        text=[f'{p:.4f}' for p in pnls],
        textposition='outside'
    ))

    # Win rate line overlay
    fig.add_trace(go.Scatter(
        x=categories,
        y=win_rates,
        mode='lines+markers',
        name='Win Rate %',
        yaxis='y2',
        line=dict(color='#fbbf24', width=2),
        marker=dict(size=8)
    ))

    fig.update_layout(
        title=f'Performance by {breakdown_type.value.replace("_", " ").title()}',
        template='plotly_dark',
        height=350,
        yaxis=dict(title='PnL (SOL)', side='left'),
        yaxis2=dict(title='Win Rate (%)', side='right', overlaying='y', range=[0, 100]),
        legend=dict(x=0, y=1.1, orientation='h'),
        hovermode='x unified'
    )

    return fig


def create_comparison_display(data: PerformanceDashboardData) -> str:
    """Create period comparison display."""
    if not data.period_comparison:
        return ""

    comp = data.period_comparison

    pnl_arrow = "▲" if comp.pnl_change_sol >= 0 else "▼"
    pnl_color = "green" if comp.pnl_change_sol >= 0 else "red"

    wr_arrow = "▲" if comp.win_rate_change >= 0 else "▼"
    wr_color = "green" if comp.win_rate_change >= 0 else "red"

    return f"""
    <div style="background: #1a1a2e; padding: 16px; border-radius: 8px; margin-top: 16px;">
        <div style="color: #888; font-size: 14px; margin-bottom: 8px;">vs Previous Period</div>
        <div style="display: flex; gap: 32px;">
            <div>
                <span style="color: {pnl_color};">{pnl_arrow} {format_sol(comp.pnl_change_sol)}</span>
                <span style="color: #888;"> PnL</span>
            </div>
            <div>
                <span style="color: {wr_color};">{wr_arrow} {float(comp.win_rate_change):.1f}pp</span>
                <span style="color: #888;"> Win Rate</span>
            </div>
            <div>
                <span style="color: white;">{comp.trade_count_change:+d}</span>
                <span style="color: #888;"> Trades</span>
            </div>
        </div>
    </div>
    """


def create_performance_panel() -> gr.Blocks:
    """Create the complete performance dashboard panel."""

    with gr.Blocks() as panel:
        gr.Markdown("## 📊 Performance Analytics")

        # Date range controls
        with gr.Row():
            start_date = gr.Textbox(
                label="Start Date",
                value=(date.today() - timedelta(days=30)).isoformat(),
                placeholder="YYYY-MM-DD"
            )
            end_date = gr.Textbox(
                label="End Date",
                value=date.today().isoformat(),
                placeholder="YYYY-MM-DD"
            )
            granularity = gr.Dropdown(
                choices=["daily", "weekly", "monthly"],
                value="daily",
                label="Granularity"
            )

        # Preset buttons
        with gr.Row():
            preset_week = gr.Button("Last 7 Days", size="sm")
            preset_month = gr.Button("Last 30 Days", size="sm")
            preset_quarter = gr.Button("Last 90 Days", size="sm")
            refresh_btn = gr.Button("🔄 Refresh", variant="primary", size="sm")

        # Key metrics display
        metrics_html = gr.HTML(label="Key Metrics")
        comparison_html = gr.HTML(label="Period Comparison")

        # Charts
        with gr.Tabs():
            with gr.Tab("PnL"):
                pnl_chart = gr.Plot(label="PnL Chart")

            with gr.Tab("Win Rate"):
                win_rate_chart = gr.Plot(label="Win Rate Trend")

            with gr.Tab("By Exit Strategy"):
                exit_breakdown_chart = gr.Plot(label="Exit Strategy Breakdown")

            with gr.Tab("By Time of Day"):
                time_breakdown_chart = gr.Plot(label="Time of Day Breakdown")

            with gr.Tab("By Wallet"):
                wallet_breakdown_chart = gr.Plot(label="Wallet Performance")

        # Load time indicator
        load_time = gr.Textbox(label="Load Time", interactive=False, visible=False)

        async def load_dashboard(start: str, end: str, gran: str):
            """Load dashboard data and update all components."""
            try:
                data = await fetch_dashboard_data(
                    start, end, gran,
                    ["by_exit_strategy", "by_time_of_day", "by_wallet"]
                )

                return (
                    create_metrics_display(data.key_metrics),
                    create_comparison_display(data),
                    create_pnl_chart(data),
                    create_win_rate_chart(data),
                    create_breakdown_chart(data, BreakdownType.BY_EXIT_STRATEGY),
                    create_breakdown_chart(data, BreakdownType.BY_TIME_OF_DAY),
                    create_breakdown_chart(data, BreakdownType.BY_WALLET),
                    f"Loaded in {data.load_time_ms}ms"
                )
            except Exception as e:
                error_html = f'<div style="color: red;">Error: {str(e)}</div>'
                empty_fig = go.Figure()
                return error_html, "", empty_fig, empty_fig, empty_fig, empty_fig, empty_fig, "Error"

        # Event handlers
        refresh_btn.click(
            fn=load_dashboard,
            inputs=[start_date, end_date, granularity],
            outputs=[
                metrics_html, comparison_html,
                pnl_chart, win_rate_chart,
                exit_breakdown_chart, time_breakdown_chart, wallet_breakdown_chart,
                load_time
            ]
        )

        def set_preset_week():
            return (date.today() - timedelta(days=7)).isoformat(), date.today().isoformat()

        def set_preset_month():
            return (date.today() - timedelta(days=30)).isoformat(), date.today().isoformat()

        def set_preset_quarter():
            return (date.today() - timedelta(days=90)).isoformat(), date.today().isoformat()

        preset_week.click(fn=set_preset_week, outputs=[start_date, end_date])
        preset_month.click(fn=set_preset_month, outputs=[start_date, end_date])
        preset_quarter.click(fn=set_preset_quarter, outputs=[start_date, end_date])

        # Auto-load on page load
        panel.load(
            fn=load_dashboard,
            inputs=[start_date, end_date, granularity],
            outputs=[
                metrics_html, comparison_html,
                pnl_chart, win_rate_chart,
                exit_breakdown_chart, time_breakdown_chart, wallet_breakdown_chart,
                load_time
            ]
        )

    return panel
```

### 6. Unit Tests

```python
# tests/unit/feedback/test_performance_dashboard.py
"""Tests for performance dashboard service."""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from src.walltrack.core.feedback.models.performance_analytics import (
    DateRange, KeyMetrics, PeriodComparison, TimeSeriesPoint,
    PnLTimeSeries, WinRateTrend, BreakdownCategory, BreakdownView,
    BreakdownType, TimeGranularity, PerformanceDashboardData, DashboardQuery
)
from src.walltrack.core.feedback.services.performance_dashboard import (
    PerformanceDashboardService, get_dashboard_service
)


class TestDateRange:
    """Test DateRange model."""

    def test_days_span(self):
        """Test days_span calculation."""
        dr = DateRange(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 10)
        )
        assert dr.days_span == 10

    def test_previous_period(self):
        """Test previous period calculation."""
        dr = DateRange(
            start_date=date(2024, 1, 11),
            end_date=date(2024, 1, 20)
        )
        assert dr.previous_period_start == date(2024, 1, 1)
        assert dr.previous_period_end == date(2024, 1, 10)

    def test_single_day_range(self):
        """Test single day range."""
        dr = DateRange(
            start_date=date(2024, 1, 15),
            end_date=date(2024, 1, 15)
        )
        assert dr.days_span == 1


class TestKeyMetrics:
    """Test KeyMetrics model."""

    def test_win_rate_calculation(self):
        """Test win rate computed field."""
        metrics = KeyMetrics(
            total_trades=100,
            winning_trades=65,
            losing_trades=35
        )
        assert metrics.win_rate == Decimal("65.00")

    def test_win_rate_zero_trades(self):
        """Test win rate with no trades."""
        metrics = KeyMetrics()
        assert metrics.win_rate == Decimal("0")

    def test_profit_factor_calculation(self):
        """Test profit factor computed field."""
        metrics = KeyMetrics(
            gross_profit_sol=Decimal("10.0"),
            gross_loss_sol=Decimal("5.0")
        )
        assert metrics.profit_factor == Decimal("2.00")

    def test_profit_factor_zero_loss(self):
        """Test profit factor with no losses."""
        metrics = KeyMetrics(
            gross_profit_sol=Decimal("10.0"),
            gross_loss_sol=Decimal("0")
        )
        assert metrics.profit_factor is None

    def test_expectancy_calculation(self):
        """Test expectancy computed field."""
        metrics = KeyMetrics(
            total_trades=10,
            total_pnl_sol=Decimal("2.5")
        )
        assert metrics.expectancy == Decimal("0.2500")

    def test_risk_reward_ratio(self):
        """Test risk/reward ratio calculation."""
        metrics = KeyMetrics(
            average_win_sol=Decimal("0.5"),
            average_loss_sol=Decimal("0.25")
        )
        assert metrics.risk_reward_ratio == Decimal("2.00")


class TestPeriodComparison:
    """Test PeriodComparison model."""

    def test_pnl_change(self):
        """Test PnL change calculation."""
        current = KeyMetrics(total_pnl_sol=Decimal("15.0"))
        previous = KeyMetrics(total_pnl_sol=Decimal("10.0"))

        comparison = PeriodComparison(
            current_metrics=current,
            previous_metrics=previous
        )

        assert comparison.pnl_change_sol == Decimal("5.0")
        assert comparison.pnl_change_percent == Decimal("50.00")

    def test_win_rate_change(self):
        """Test win rate change calculation."""
        current = KeyMetrics(total_trades=100, winning_trades=70, losing_trades=30)
        previous = KeyMetrics(total_trades=100, winning_trades=60, losing_trades=40)

        comparison = PeriodComparison(
            current_metrics=current,
            previous_metrics=previous
        )

        assert comparison.win_rate_change == Decimal("10.00")

    def test_trade_count_change(self):
        """Test trade count change."""
        current = KeyMetrics(total_trades=50)
        previous = KeyMetrics(total_trades=30)

        comparison = PeriodComparison(
            current_metrics=current,
            previous_metrics=previous
        )

        assert comparison.trade_count_change == 20


class TestPnLTimeSeries:
    """Test PnL time series model."""

    def test_cumulative_final(self):
        """Test cumulative final value."""
        series = PnLTimeSeries(
            granularity=TimeGranularity.DAILY,
            points=[
                TimeSeriesPoint(timestamp=datetime(2024, 1, 1), value=Decimal("1"), cumulative_value=Decimal("1")),
                TimeSeriesPoint(timestamp=datetime(2024, 1, 2), value=Decimal("2"), cumulative_value=Decimal("3")),
                TimeSeriesPoint(timestamp=datetime(2024, 1, 3), value=Decimal("-1"), cumulative_value=Decimal("2")),
            ]
        )

        assert series.cumulative_final == Decimal("2")

    def test_peak_and_trough(self):
        """Test peak and trough values."""
        series = PnLTimeSeries(
            granularity=TimeGranularity.DAILY,
            points=[
                TimeSeriesPoint(timestamp=datetime(2024, 1, 1), value=Decimal("1"), cumulative_value=Decimal("1")),
                TimeSeriesPoint(timestamp=datetime(2024, 1, 2), value=Decimal("4"), cumulative_value=Decimal("5")),
                TimeSeriesPoint(timestamp=datetime(2024, 1, 3), value=Decimal("-3"), cumulative_value=Decimal("2")),
            ]
        )

        assert series.peak_value == Decimal("5")
        assert series.trough_value == Decimal("1")

    def test_empty_series(self):
        """Test empty series defaults."""
        series = PnLTimeSeries(granularity=TimeGranularity.DAILY)

        assert series.cumulative_final == Decimal("0")
        assert series.peak_value == Decimal("0")


class TestBreakdownView:
    """Test breakdown view model."""

    def test_with_contributions(self):
        """Test contribution percentage calculation."""
        breakdown = BreakdownView(
            breakdown_type=BreakdownType.BY_EXIT_STRATEGY,
            categories=[
                BreakdownCategory(
                    category_name="exit_reason",
                    category_value="take_profit",
                    trade_count=10,
                    pnl_sol=Decimal("8.0"),
                    win_rate=Decimal("90.0"),
                    average_pnl_sol=Decimal("0.8")
                ),
                BreakdownCategory(
                    category_name="exit_reason",
                    category_value="stop_loss",
                    trade_count=5,
                    pnl_sol=Decimal("2.0"),
                    win_rate=Decimal("0.0"),
                    average_pnl_sol=Decimal("-0.4")
                ),
            ],
            total_pnl_sol=Decimal("10.0")
        )

        result = breakdown.with_contributions()

        # Contributions should be calculated
        assert len(result.categories) == 2


class TestPerformanceDashboardService:
    """Test performance dashboard service."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return PerformanceDashboardService()

    @pytest.fixture
    def sample_trades(self):
        """Create sample trade data."""
        return [
            {
                "id": "trade-1",
                "entry_timestamp": "2024-01-15T10:00:00Z",
                "exit_timestamp": "2024-01-15T12:00:00Z",
                "realized_pnl_sol": "0.5",
                "entry_amount_sol": "1.0",
                "source_wallet": "wallet123abc",
                "exit_reason": "take_profit",
                "token_age_minutes": 10
            },
            {
                "id": "trade-2",
                "entry_timestamp": "2024-01-15T14:00:00Z",
                "exit_timestamp": "2024-01-15T15:00:00Z",
                "realized_pnl_sol": "-0.2",
                "entry_amount_sol": "1.0",
                "source_wallet": "wallet456def",
                "exit_reason": "stop_loss",
                "token_age_minutes": 5
            },
            {
                "id": "trade-3",
                "entry_timestamp": "2024-01-16T09:00:00Z",
                "exit_timestamp": "2024-01-16T11:00:00Z",
                "realized_pnl_sol": "0.3",
                "entry_amount_sol": "1.0",
                "source_wallet": "wallet123abc",
                "exit_reason": "take_profit",
                "token_age_minutes": 20
            },
        ]

    @pytest.mark.asyncio
    async def test_calculate_key_metrics(self, service, sample_trades):
        """Test key metrics calculation."""
        metrics = await service._calculate_key_metrics(sample_trades)

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.total_pnl_sol == Decimal("0.6000")
        assert metrics.win_rate == Decimal("66.67")

    @pytest.mark.asyncio
    async def test_calculate_key_metrics_empty(self, service):
        """Test key metrics with no trades."""
        metrics = await service._calculate_key_metrics([])

        assert metrics.total_trades == 0
        assert metrics.total_pnl_sol == Decimal("0")
        assert metrics.win_rate == Decimal("0")

    @pytest.mark.asyncio
    async def test_build_pnl_time_series(self, service, sample_trades):
        """Test PnL time series building."""
        series = await service._build_pnl_time_series(
            sample_trades, TimeGranularity.DAILY
        )

        assert series.granularity == TimeGranularity.DAILY
        assert len(series.points) == 2  # Two different days

    @pytest.mark.asyncio
    async def test_build_win_rate_trend(self, service, sample_trades):
        """Test win rate trend building."""
        trend = await service._build_win_rate_trend(
            sample_trades, TimeGranularity.DAILY, rolling_window=2
        )

        assert len(trend.points) == 3
        assert trend.rolling_window_trades == 2

    @pytest.mark.asyncio
    async def test_build_breakdown_by_wallet(self, service, sample_trades):
        """Test wallet breakdown."""
        breakdown = await service._build_breakdown(
            sample_trades, BreakdownType.BY_WALLET, Decimal("0.6")
        )

        assert breakdown.breakdown_type == BreakdownType.BY_WALLET
        assert len(breakdown.categories) == 2

    @pytest.mark.asyncio
    async def test_build_breakdown_by_exit_strategy(self, service, sample_trades):
        """Test exit strategy breakdown."""
        breakdown = await service._build_breakdown(
            sample_trades, BreakdownType.BY_EXIT_STRATEGY, Decimal("0.6")
        )

        assert breakdown.breakdown_type == BreakdownType.BY_EXIT_STRATEGY
        # Should have take_profit and stop_loss
        categories = {c.category_value for c in breakdown.categories}
        assert "take_profit" in categories
        assert "stop_loss" in categories

    @pytest.mark.asyncio
    async def test_get_dashboard_data_caching(self, service):
        """Test that dashboard data is cached."""
        with patch.object(service, '_fetch_trades', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = []

            query = DashboardQuery(
                date_range=DateRange(
                    start_date=date(2024, 1, 1),
                    end_date=date(2024, 1, 31)
                ),
                include_comparison=False,
                breakdowns_requested=[]
            )

            # First call
            await service.get_dashboard_data(query)
            assert mock_fetch.call_count == 1

            # Second call should use cache
            await service.get_dashboard_data(query)
            assert mock_fetch.call_count == 1  # Still 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, service):
        """Test cache clearing."""
        # Add something to cache
        service._cache["test_key"] = (datetime.utcnow(), None)
        assert len(service._cache) == 1

        service.clear_cache()
        assert len(service._cache) == 0

    def test_get_period_key_daily(self, service):
        """Test daily period key generation."""
        dt = datetime(2024, 1, 15, 14, 30)
        key = service._get_period_key(dt, TimeGranularity.DAILY)
        assert key == "2024-01-15"

    def test_get_period_key_weekly(self, service):
        """Test weekly period key generation."""
        dt = datetime(2024, 1, 15, 14, 30)
        key = service._get_period_key(dt, TimeGranularity.WEEKLY)
        assert key.startswith("2024-W")

    def test_get_category_value_time_of_day(self, service):
        """Test time of day categorization."""
        morning_trade = {"exit_timestamp": "2024-01-15T08:00:00Z"}
        afternoon_trade = {"exit_timestamp": "2024-01-15T14:00:00Z"}
        evening_trade = {"exit_timestamp": "2024-01-15T20:00:00Z"}
        night_trade = {"exit_timestamp": "2024-01-15T02:00:00Z"}

        assert "Morning" in service._get_category_value(morning_trade, BreakdownType.BY_TIME_OF_DAY)
        assert "Afternoon" in service._get_category_value(afternoon_trade, BreakdownType.BY_TIME_OF_DAY)
        assert "Evening" in service._get_category_value(evening_trade, BreakdownType.BY_TIME_OF_DAY)
        assert "Night" in service._get_category_value(night_trade, BreakdownType.BY_TIME_OF_DAY)

    def test_get_category_value_token_age(self, service):
        """Test token age categorization."""
        young = {"token_age_minutes": 3}
        medium = {"token_age_minutes": 10}
        older = {"token_age_minutes": 30}
        old = {"token_age_minutes": 120}

        assert "0-5" in service._get_category_value(young, BreakdownType.BY_TOKEN_AGE)
        assert "5-15" in service._get_category_value(medium, BreakdownType.BY_TOKEN_AGE)
        assert "15-60" in service._get_category_value(older, BreakdownType.BY_TOKEN_AGE)
        assert "60+" in service._get_category_value(old, BreakdownType.BY_TOKEN_AGE)


@pytest.mark.asyncio
async def test_get_dashboard_service_singleton():
    """Test singleton pattern for dashboard service."""
    service1 = await get_dashboard_service()
    service2 = await get_dashboard_service()

    assert service1 is service2
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/feedback/models/performance_analytics.py`
- [ ] Create `src/walltrack/core/feedback/services/performance_dashboard.py`
- [ ] Create `src/walltrack/ui/components/performance.py`
- [ ] Create `src/walltrack/api/routes/performance_dashboard.py`
- [ ] Add materialized views for performance optimization
- [ ] Implement caching to ensure < 2s response time
- [ ] Create Plotly charts for Gradio display
- [ ] Implement all breakdown views
- [ ] Add tests for all components

## Definition of Done

- [ ] Key metrics displayed accurately
- [ ] Performance charts render smoothly
- [ ] Date range selection works
- [ ] Breakdown views available
- [ ] Response time < 2 seconds (NFR3)
- [ ] All unit tests pass
