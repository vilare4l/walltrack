"""Tests for performance dashboard service."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.core.feedback.performance_models import (
    BreakdownCategory,
    BreakdownType,
    BreakdownView,
    DashboardQuery,
    DateRange,
    KeyMetrics,
    PeriodComparison,
    PnLTimeSeries,
    TimeGranularity,
    TimeSeriesPoint,
)


class ChainableMock:
    """Mock that supports method chaining for Supabase client."""

    def __init__(self, data=None):
        self._data = data if data is not None else []

    def __getattr__(self, name):
        return lambda *_args, **_kwargs: self

    async def execute(self):
        return MagicMock(data=self._data)


class TestDateRange:
    """Test DateRange model."""

    def test_days_span(self):
        """Test days_span calculation."""
        dr = DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 1, 10))
        assert dr.days_span == 10

    def test_previous_period(self):
        """Test previous period calculation."""
        dr = DateRange(start_date=date(2024, 1, 11), end_date=date(2024, 1, 20))
        assert dr.previous_period_start == date(2024, 1, 1)
        assert dr.previous_period_end == date(2024, 1, 10)

    def test_single_day_range(self):
        """Test single day range."""
        dr = DateRange(start_date=date(2024, 1, 15), end_date=date(2024, 1, 15))
        assert dr.days_span == 1


class TestKeyMetrics:
    """Test KeyMetrics model."""

    def test_win_rate_calculation(self):
        """Test win rate computed field."""
        metrics = KeyMetrics(total_trades=100, winning_trades=65, losing_trades=35)
        assert metrics.win_rate == Decimal("65.00")

    def test_win_rate_zero_trades(self):
        """Test win rate with no trades."""
        metrics = KeyMetrics()
        assert metrics.win_rate == Decimal("0")

    def test_profit_factor_calculation(self):
        """Test profit factor computed field."""
        metrics = KeyMetrics(
            gross_profit_sol=Decimal("10.0"), gross_loss_sol=Decimal("5.0")
        )
        assert metrics.profit_factor == Decimal("2.00")

    def test_profit_factor_zero_loss(self):
        """Test profit factor with no losses."""
        metrics = KeyMetrics(
            gross_profit_sol=Decimal("10.0"), gross_loss_sol=Decimal("0")
        )
        assert metrics.profit_factor is None

    def test_expectancy_calculation(self):
        """Test expectancy computed field."""
        metrics = KeyMetrics(total_trades=10, total_pnl_sol=Decimal("2.5"))
        assert metrics.expectancy == Decimal("0.2500")

    def test_risk_reward_ratio(self):
        """Test risk/reward ratio calculation."""
        metrics = KeyMetrics(
            average_win_sol=Decimal("0.5"), average_loss_sol=Decimal("0.25")
        )
        assert metrics.risk_reward_ratio == Decimal("2.00")

    def test_risk_reward_ratio_zero_loss(self):
        """Test risk/reward ratio with zero loss."""
        metrics = KeyMetrics(
            average_win_sol=Decimal("0.5"), average_loss_sol=Decimal("0")
        )
        assert metrics.risk_reward_ratio is None


class TestPeriodComparison:
    """Test PeriodComparison model."""

    def test_pnl_change(self):
        """Test PnL change calculation."""
        current = KeyMetrics(total_pnl_sol=Decimal("15.0"))
        previous = KeyMetrics(total_pnl_sol=Decimal("10.0"))

        comparison = PeriodComparison(
            current_metrics=current, previous_metrics=previous
        )

        assert comparison.pnl_change_sol == Decimal("5.0")
        assert comparison.pnl_change_percent == Decimal("50.00")

    def test_win_rate_change(self):
        """Test win rate change calculation."""
        current = KeyMetrics(total_trades=100, winning_trades=70, losing_trades=30)
        previous = KeyMetrics(total_trades=100, winning_trades=60, losing_trades=40)

        comparison = PeriodComparison(
            current_metrics=current, previous_metrics=previous
        )

        assert comparison.win_rate_change == Decimal("10.00")

    def test_trade_count_change(self):
        """Test trade count change."""
        current = KeyMetrics(total_trades=50)
        previous = KeyMetrics(total_trades=30)

        comparison = PeriodComparison(
            current_metrics=current, previous_metrics=previous
        )

        assert comparison.trade_count_change == 20

    def test_pnl_change_percent_zero_previous(self):
        """Test PnL change percent with zero previous."""
        current = KeyMetrics(total_pnl_sol=Decimal("15.0"))
        previous = KeyMetrics(total_pnl_sol=Decimal("0"))

        comparison = PeriodComparison(
            current_metrics=current, previous_metrics=previous
        )

        assert comparison.pnl_change_percent is None


class TestPnLTimeSeries:
    """Test PnL time series model."""

    def test_cumulative_final(self):
        """Test cumulative final value."""
        series = PnLTimeSeries(
            granularity=TimeGranularity.DAILY,
            points=[
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                    value=Decimal("1"),
                    cumulative_value=Decimal("1"),
                ),
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                    value=Decimal("2"),
                    cumulative_value=Decimal("3"),
                ),
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                    value=Decimal("-1"),
                    cumulative_value=Decimal("2"),
                ),
            ],
        )

        assert series.cumulative_final == Decimal("2")

    def test_peak_and_trough(self):
        """Test peak and trough values."""
        series = PnLTimeSeries(
            granularity=TimeGranularity.DAILY,
            points=[
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 1, tzinfo=UTC),
                    value=Decimal("1"),
                    cumulative_value=Decimal("1"),
                ),
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 2, tzinfo=UTC),
                    value=Decimal("4"),
                    cumulative_value=Decimal("5"),
                ),
                TimeSeriesPoint(
                    timestamp=datetime(2024, 1, 3, tzinfo=UTC),
                    value=Decimal("-3"),
                    cumulative_value=Decimal("2"),
                ),
            ],
        )

        assert series.peak_value == Decimal("5")
        assert series.trough_value == Decimal("1")

    def test_empty_series(self):
        """Test empty series defaults."""
        series = PnLTimeSeries(granularity=TimeGranularity.DAILY)

        assert series.cumulative_final == Decimal("0")
        assert series.peak_value == Decimal("0")
        assert series.trough_value == Decimal("0")


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
                    average_pnl_sol=Decimal("0.8"),
                ),
                BreakdownCategory(
                    category_name="exit_reason",
                    category_value="stop_loss",
                    trade_count=5,
                    pnl_sol=Decimal("2.0"),
                    win_rate=Decimal("0.0"),
                    average_pnl_sol=Decimal("-0.4"),
                ),
            ],
            total_pnl_sol=Decimal("10.0"),
        )

        result = breakdown.with_contributions()

        assert len(result.categories) == 2
        assert result.categories[0].contribution_percent == Decimal("80.00")
        assert result.categories[1].contribution_percent == Decimal("20.00")

    def test_with_contributions_zero_total(self):
        """Test contribution with zero total."""
        breakdown = BreakdownView(
            breakdown_type=BreakdownType.BY_WALLET,
            categories=[
                BreakdownCategory(
                    category_name="wallet",
                    category_value="abc...",
                    trade_count=5,
                    pnl_sol=Decimal("0"),
                    win_rate=Decimal("50.0"),
                    average_pnl_sol=Decimal("0"),
                ),
            ],
            total_pnl_sol=Decimal("0"),
        )

        result = breakdown.with_contributions()
        assert result.categories[0].contribution_percent == Decimal("0")


class TestPerformanceDashboardService:
    """Test performance dashboard service."""

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.table.return_value = ChainableMock()
        return client

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
                "token_age_minutes": 10,
            },
            {
                "id": "trade-2",
                "entry_timestamp": "2024-01-15T14:00:00Z",
                "exit_timestamp": "2024-01-15T15:00:00Z",
                "realized_pnl_sol": "-0.2",
                "entry_amount_sol": "1.0",
                "source_wallet": "wallet456def",
                "exit_reason": "stop_loss",
                "token_age_minutes": 5,
            },
            {
                "id": "trade-3",
                "entry_timestamp": "2024-01-16T09:00:00Z",
                "exit_timestamp": "2024-01-16T11:00:00Z",
                "realized_pnl_sol": "0.3",
                "entry_amount_sol": "1.0",
                "source_wallet": "wallet123abc",
                "exit_reason": "take_profit",
                "token_age_minutes": 20,
            },
        ]

    @pytest.mark.asyncio
    async def test_calculate_key_metrics(self, mock_supabase, sample_trades):
        """Test key metrics calculation."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        metrics = await service._calculate_key_metrics(sample_trades)

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.total_pnl_sol == Decimal("0.6000")
        assert metrics.win_rate == Decimal("66.67")

    @pytest.mark.asyncio
    async def test_calculate_key_metrics_empty(self, mock_supabase):
        """Test key metrics with no trades."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        metrics = await service._calculate_key_metrics([])

        assert metrics.total_trades == 0
        assert metrics.total_pnl_sol == Decimal("0")
        assert metrics.win_rate == Decimal("0")

    @pytest.mark.asyncio
    async def test_build_pnl_time_series(self, mock_supabase, sample_trades):
        """Test PnL time series building."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        series = await service._build_pnl_time_series(
            sample_trades, TimeGranularity.DAILY
        )

        assert series.granularity == TimeGranularity.DAILY
        assert len(series.points) == 2  # Two different days

    @pytest.mark.asyncio
    async def test_build_win_rate_trend(self, mock_supabase, sample_trades):
        """Test win rate trend building."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        trend = await service._build_win_rate_trend(
            sample_trades, TimeGranularity.DAILY, rolling_window=2
        )

        assert len(trend.points) == 3
        assert trend.rolling_window_trades == 2

    @pytest.mark.asyncio
    async def test_build_breakdown_by_wallet(self, mock_supabase, sample_trades):
        """Test wallet breakdown."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        breakdown = await service._build_breakdown(
            sample_trades, BreakdownType.BY_WALLET, Decimal("0.6")
        )

        assert breakdown.breakdown_type == BreakdownType.BY_WALLET
        assert len(breakdown.categories) == 2

    @pytest.mark.asyncio
    async def test_build_breakdown_by_exit_strategy(self, mock_supabase, sample_trades):
        """Test exit strategy breakdown."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        breakdown = await service._build_breakdown(
            sample_trades, BreakdownType.BY_EXIT_STRATEGY, Decimal("0.6")
        )

        assert breakdown.breakdown_type == BreakdownType.BY_EXIT_STRATEGY
        categories = {c.category_value for c in breakdown.categories}
        assert "take_profit" in categories
        assert "stop_loss" in categories

    @pytest.mark.asyncio
    async def test_get_dashboard_data_caching(self, mock_supabase):
        """Test that dashboard data is cached."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        service._fetch_trades = AsyncMock(return_value=[])

        query = DashboardQuery(
            date_range=DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)),
            include_comparison=False,
            breakdowns_requested=[],
        )

        # First call
        await service.get_dashboard_data(query)
        assert service._fetch_trades.call_count == 1

        # Second call should use cache
        await service.get_dashboard_data(query)
        assert service._fetch_trades.call_count == 1

    @pytest.mark.asyncio
    async def test_clear_cache(self, mock_supabase):
        """Test cache clearing."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        service._cache["test_key"] = (datetime.now(UTC), None)
        assert len(service._cache) == 1

        service.clear_cache()
        assert len(service._cache) == 0

    def test_get_period_key_daily(self, mock_supabase):
        """Test daily period key generation."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        key = service._get_period_key(dt, TimeGranularity.DAILY)
        assert key == "2024-01-15"

    def test_get_period_key_weekly(self, mock_supabase):
        """Test weekly period key generation."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        dt = datetime(2024, 1, 15, 14, 30, tzinfo=UTC)
        key = service._get_period_key(dt, TimeGranularity.WEEKLY)
        assert key.startswith("2024-W")

    def test_get_category_value_time_of_day(self, mock_supabase):
        """Test time of day categorization."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        morning_trade = {"exit_timestamp": "2024-01-15T08:00:00Z"}
        afternoon_trade = {"exit_timestamp": "2024-01-15T14:00:00Z"}
        evening_trade = {"exit_timestamp": "2024-01-15T20:00:00Z"}
        night_trade = {"exit_timestamp": "2024-01-15T02:00:00Z"}

        assert (
            "Morning"
            in service._get_category_value(morning_trade, BreakdownType.BY_TIME_OF_DAY)
        )
        assert (
            "Afternoon"
            in service._get_category_value(
                afternoon_trade, BreakdownType.BY_TIME_OF_DAY
            )
        )
        assert (
            "Evening"
            in service._get_category_value(evening_trade, BreakdownType.BY_TIME_OF_DAY)
        )
        assert (
            "Night"
            in service._get_category_value(night_trade, BreakdownType.BY_TIME_OF_DAY)
        )

    def test_get_category_value_token_age(self, mock_supabase):
        """Test token age categorization."""
        from walltrack.core.feedback.performance_dashboard import (
            PerformanceDashboardService,
        )

        service = PerformanceDashboardService(mock_supabase)
        young = {"token_age_minutes": 3}
        medium = {"token_age_minutes": 10}
        older = {"token_age_minutes": 30}
        old = {"token_age_minutes": 120}

        assert "0-5" in service._get_category_value(young, BreakdownType.BY_TOKEN_AGE)
        assert "5-15" in service._get_category_value(medium, BreakdownType.BY_TOKEN_AGE)
        assert "15-60" in service._get_category_value(older, BreakdownType.BY_TOKEN_AGE)
        assert "60+" in service._get_category_value(old, BreakdownType.BY_TOKEN_AGE)


class TestDashboardQuery:
    """Test DashboardQuery model."""

    def test_default_values(self):
        """Test default query values."""
        query = DashboardQuery(
            date_range=DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))
        )

        assert query.include_comparison is True
        assert query.time_granularity == TimeGranularity.DAILY
        assert query.breakdowns_requested == []

    def test_with_breakdowns(self):
        """Test query with breakdowns."""
        query = DashboardQuery(
            date_range=DateRange(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)),
            breakdowns_requested=[BreakdownType.BY_WALLET, BreakdownType.BY_EXIT_STRATEGY],
        )

        assert len(query.breakdowns_requested) == 2
