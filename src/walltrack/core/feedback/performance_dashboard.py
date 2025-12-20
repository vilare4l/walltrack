"""Performance dashboard data aggregation service."""

import asyncio
from datetime import UTC, date, datetime
from decimal import Decimal

import structlog
from supabase import AsyncClient

from walltrack.core.feedback.performance_models import (
    BreakdownCategory,
    BreakdownType,
    BreakdownView,
    DashboardQuery,
    DateRange,
    KeyMetrics,
    PerformanceDashboardData,
    PeriodComparison,
    PnLTimeSeries,
    TimeGranularity,
    TimeSeriesPoint,
    WinRateTrend,
)

logger = structlog.get_logger(__name__)


class PerformanceDashboardService:
    """Aggregates performance data for dashboard display."""

    CACHE_TTL_SECONDS = 60  # Cache for 1 minute

    def __init__(self, supabase_client: AsyncClient):
        self.supabase = supabase_client
        self._cache: dict[str, tuple[datetime, PerformanceDashboardData]] = {}

    def _cache_key(self, query: DashboardQuery) -> str:
        """Generate cache key for query."""
        return (
            f"{query.date_range.start_date}_{query.date_range.end_date}"
            f"_{query.time_granularity}"
        )

    async def get_dashboard_data(
        self,
        query: DashboardQuery,
    ) -> PerformanceDashboardData:
        """Get complete dashboard data for the given query.

        Uses caching to ensure < 2s response time (NFR3).
        """
        start_time = datetime.now(UTC)

        # Check cache
        cache_key = self._cache_key(query)
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if (datetime.now(UTC) - cached_time).seconds < self.CACHE_TTL_SECONDS:
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
                end_date=query.date_range.previous_period_end,
            )
            previous_trades = await self._fetch_trades(previous_range)
            previous_metrics = await self._calculate_key_metrics(previous_trades)
            period_comparison = PeriodComparison(
                current_metrics=key_metrics,
                previous_metrics=previous_metrics,
            )

        # Build time series (run in parallel)
        pnl_series_task = self._build_pnl_time_series(trades, query.time_granularity)
        win_rate_task = self._build_win_rate_trend(trades, query.time_granularity)

        pnl_time_series, win_rate_trend = await asyncio.gather(
            pnl_series_task, win_rate_task
        )

        # Build requested breakdowns
        breakdowns: dict[BreakdownType, BreakdownView] = {}
        for breakdown_type in query.breakdowns_requested:
            breakdowns[breakdown_type] = await self._build_breakdown(
                trades, breakdown_type, key_metrics.total_pnl_sol
            )

        load_time_ms = int((datetime.now(UTC) - start_time).total_seconds() * 1000)

        result = PerformanceDashboardData(
            date_range=query.date_range,
            key_metrics=key_metrics,
            period_comparison=period_comparison,
            pnl_time_series=pnl_time_series,
            win_rate_trend=win_rate_trend,
            breakdowns=breakdowns,
            load_time_ms=load_time_ms,
        )

        # Cache result
        self._cache[cache_key] = (datetime.now(UTC), result)

        logger.info(
            "dashboard_data_generated",
            date_range=f"{query.date_range.start_date} to {query.date_range.end_date}",
            trade_count=len(trades),
            load_time_ms=load_time_ms,
        )

        return result

    async def _fetch_trades(self, date_range: DateRange) -> list[dict]:
        """Fetch trades within date range."""
        response = (
            await self.supabase.table("trade_outcomes")
            .select("*")
            .gte("exit_timestamp", date_range.start_date.isoformat())
            .lte("exit_timestamp", f"{date_range.end_date}T23:59:59")
            .execute()
        )

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
        win_pnls: list[Decimal] = []
        loss_pnls: list[Decimal] = []
        durations: list[float] = []

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
                entry = datetime.fromisoformat(
                    trade["entry_timestamp"].replace("Z", "+00:00")
                )
                exit_t = datetime.fromisoformat(
                    trade["exit_timestamp"].replace("Z", "+00:00")
                )
                durations.append((exit_t - entry).total_seconds())

            # Drawdown tracking
            peak_pnl = max(peak_pnl, cumulative_pnl)
            drawdown = peak_pnl - cumulative_pnl
            max_drawdown = max(max_drawdown, drawdown)

        # Calculate averages
        average_win = sum(win_pnls) / len(win_pnls) if win_pnls else Decimal("0")
        average_loss = sum(loss_pnls) / len(loss_pnls) if loss_pnls else Decimal("0")
        average_duration = int(sum(durations) / len(durations)) if durations else 0

        # Calculate total invested for percentage
        total_invested = sum(
            Decimal(str(t.get("entry_amount_sol", 0))) for t in trades
        )
        total_pnl_percent = (
            (total_pnl / total_invested * 100) if total_invested else Decimal("0")
        )
        max_drawdown_percent = (
            (max_drawdown / peak_pnl * 100) if peak_pnl > 0 else Decimal("0")
        )

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
            sharpe_ratio=sharpe_ratio,
        )

    async def _calculate_sharpe_ratio(
        self,
        trades: list[dict],
        risk_free_rate: Decimal = Decimal("0.05"),
    ) -> Decimal | None:
        """Calculate Sharpe ratio from daily returns."""
        if len(trades) < 10:
            return None

        # Group by day
        daily_returns: dict[date, Decimal] = {}
        for trade in trades:
            exit_ts = trade.get("exit_timestamp")
            if not exit_ts:
                continue
            trade_date = datetime.fromisoformat(
                exit_ts.replace("Z", "+00:00")
            ).date()
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
        sharpe = ((mean_return - daily_risk_free) / std_dev) * (
            Decimal("252") ** Decimal("0.5")
        )

        return sharpe.quantize(Decimal("0.01"))

    async def _build_pnl_time_series(
        self,
        trades: list[dict],
        granularity: TimeGranularity,
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
            period_pnl = sum(
                Decimal(str(t.get("realized_pnl_sol", 0))) for t in period_trades
            )
            cumulative += period_pnl

            points.append(
                TimeSeriesPoint(
                    timestamp=self._period_key_to_datetime(period_key, granularity),
                    value=period_pnl.quantize(Decimal("0.0001")),
                    cumulative_value=cumulative.quantize(Decimal("0.0001")),
                    trade_count=len(period_trades),
                )
            )

        return PnLTimeSeries(granularity=granularity, points=points)

    async def _build_win_rate_trend(
        self,
        trades: list[dict],
        granularity: TimeGranularity,
        rolling_window: int = 20,
    ) -> WinRateTrend:
        """Build win rate trend with rolling window."""
        if not trades:
            return WinRateTrend(
                granularity=granularity, rolling_window_trades=rolling_window
            )

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
            window = sorted_trades[start_idx : i + 1]

            wins = sum(
                1 for t in window if Decimal(str(t.get("realized_pnl_sol", 0))) > 0
            )
            win_rate = Decimal(wins) / Decimal(len(window)) * 100

            dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
            points.append(
                TimeSeriesPoint(
                    timestamp=dt,
                    value=win_rate.quantize(Decimal("0.01")),
                    trade_count=len(window),
                )
            )

        return WinRateTrend(
            granularity=granularity,
            points=points,
            rolling_window_trades=rolling_window,
        )

    async def _build_breakdown(
        self,
        trades: list[dict],
        breakdown_type: BreakdownType,
        total_pnl: Decimal,
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
            wins = sum(
                1 for t in cat_trades if Decimal(str(t.get("realized_pnl_sol", 0))) > 0
            )
            win_rate = (
                Decimal(wins) / Decimal(len(cat_trades)) * 100
                if cat_trades
                else Decimal("0")
            )
            avg_pnl = pnl / len(cat_trades) if cat_trades else Decimal("0")

            categories.append(
                BreakdownCategory(
                    category_name=breakdown_type.value,
                    category_value=cat_value,
                    trade_count=len(cat_trades),
                    pnl_sol=pnl.quantize(Decimal("0.0001")),
                    win_rate=win_rate.quantize(Decimal("0.01")),
                    average_pnl_sol=avg_pnl.quantize(Decimal("0.0001")),
                )
            )

        # Sort by PnL descending
        categories.sort(key=lambda c: c.pnl_sol, reverse=True)

        breakdown = BreakdownView(
            breakdown_type=breakdown_type,
            categories=categories,
            total_pnl_sol=total_pnl,
        )

        return breakdown.with_contributions()

    def _get_category_value(self, trade: dict, breakdown_type: BreakdownType) -> str:
        """Extract category value from trade based on breakdown type."""
        handlers = {
            BreakdownType.BY_WALLET: self._get_wallet_category,
            BreakdownType.BY_EXIT_STRATEGY: self._get_exit_strategy_category,
            BreakdownType.BY_TIME_OF_DAY: self._get_time_of_day_category,
            BreakdownType.BY_DAY_OF_WEEK: self._get_day_of_week_category,
            BreakdownType.BY_TOKEN_AGE: self._get_token_age_category,
        }
        handler = handlers.get(breakdown_type)
        return handler(trade) if handler else "unknown"

    def _get_wallet_category(self, trade: dict) -> str:
        """Get wallet category value."""
        wallet = trade.get("source_wallet", "unknown")
        return wallet[:8] + "..." if len(wallet) > 8 else wallet

    def _get_exit_strategy_category(self, trade: dict) -> str:
        """Get exit strategy category value."""
        return trade.get("exit_reason", "unknown")

    def _get_time_of_day_category(self, trade: dict) -> str:
        """Get time of day category value."""
        exit_ts = trade.get("exit_timestamp")
        if not exit_ts:
            return "unknown"
        dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
        hour = dt.hour
        time_ranges = [
            (0, 6, "Night (00-06)"),
            (6, 12, "Morning (06-12)"),
            (12, 18, "Afternoon (12-18)"),
            (18, 24, "Evening (18-24)"),
        ]
        for start, end, label in time_ranges:
            if start <= hour < end:
                return label
        return "unknown"

    def _get_day_of_week_category(self, trade: dict) -> str:
        """Get day of week category value."""
        exit_ts = trade.get("exit_timestamp")
        if not exit_ts:
            return "unknown"
        dt = datetime.fromisoformat(exit_ts.replace("Z", "+00:00"))
        return dt.strftime("%A")

    def _get_token_age_category(self, trade: dict) -> str:
        """Get token age category value."""
        token_age_minutes = trade.get("token_age_minutes", 0)
        age_ranges = [
            (0, 5, "0-5 min"),
            (5, 15, "5-15 min"),
            (15, 60, "15-60 min"),
        ]
        for start, end, label in age_ranges:
            if start <= token_age_minutes < end:
                return label
        return "60+ min"

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

    def _period_key_to_datetime(
        self, key: str, granularity: TimeGranularity
    ) -> datetime:
        """Convert period key back to datetime."""
        if granularity == TimeGranularity.HOURLY:
            return datetime.strptime(key, "%Y-%m-%d-%H").replace(tzinfo=UTC)
        elif granularity == TimeGranularity.DAILY:
            return datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=UTC)
        elif granularity == TimeGranularity.WEEKLY:
            return datetime.strptime(key + "-1", "%Y-W%W-%w").replace(tzinfo=UTC)
        elif granularity == TimeGranularity.MONTHLY:
            return datetime.strptime(key + "-01", "%Y-%m-%d").replace(tzinfo=UTC)
        return datetime.strptime(key, "%Y-%m-%d").replace(tzinfo=UTC)

    def clear_cache(self) -> None:
        """Clear the dashboard cache."""
        self._cache.clear()
        logger.info("dashboard_cache_cleared")


# Singleton instance
_dashboard_service: PerformanceDashboardService | None = None


def get_dashboard_service(supabase_client: AsyncClient) -> PerformanceDashboardService:
    """Get the singleton dashboard service instance."""
    global _dashboard_service
    if _dashboard_service is None:
        _dashboard_service = PerformanceDashboardService(supabase_client)
    return _dashboard_service
