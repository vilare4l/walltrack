"""Tests for signal accuracy tracking."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from walltrack.core.feedback.accuracy_models import (
    AccuracySnapshot,
    AccuracyTrend,
    AccuracyTrendAnalysis,
    FactorAccuracyBreakdown,
    RetrospectiveOutcome,
    SignalAccuracyMetrics,
    ThresholdAnalysis,
)
from walltrack.core.feedback.accuracy_tracker import AccuracyTracker


class ChainableMock:
    """Mock that supports method chaining for Supabase client."""

    def __init__(self, data=None, count=None):
        self._data = data if data is not None else []
        self._count = count

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    async def execute(self):
        return MagicMock(data=self._data, count=self._count)


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()
    client.table.return_value = ChainableMock()
    return client


@pytest.fixture
def tracker(mock_supabase):
    """Create AccuracyTracker instance."""
    return AccuracyTracker(mock_supabase)


class TestAccuracyModels:
    """Tests for accuracy models."""

    def test_signal_to_win_rate_calculation(self):
        """Test signal-to-win rate is calculated correctly."""
        metrics = SignalAccuracyMetrics(
            period_start=datetime.now(UTC) - timedelta(days=30),
            period_end=datetime.now(UTC),
            total_signals=100,
            traded_signals=50,
            winning_trades=35,
            losing_trades=15,
        )
        assert metrics.signal_to_win_rate == Decimal("70")

    def test_signal_to_trade_rate_calculation(self):
        """Test signal-to-trade rate is calculated correctly."""
        metrics = SignalAccuracyMetrics(
            period_start=datetime.now(UTC) - timedelta(days=30),
            period_end=datetime.now(UTC),
            total_signals=100,
            traded_signals=50,
            winning_trades=35,
            losing_trades=15,
        )
        assert metrics.signal_to_trade_rate == Decimal("50")

    def test_signal_to_win_rate_zero_trades(self):
        """Test win rate is zero when no trades."""
        metrics = SignalAccuracyMetrics(
            period_start=datetime.now(UTC) - timedelta(days=30),
            period_end=datetime.now(UTC),
            total_signals=100,
            traded_signals=0,
            winning_trades=0,
            losing_trades=0,
        )
        assert metrics.signal_to_win_rate == Decimal("0")

    def test_score_differential(self):
        """Test score differential calculation."""
        metrics = SignalAccuracyMetrics(
            period_start=datetime.now(UTC) - timedelta(days=30),
            period_end=datetime.now(UTC),
            avg_score_winners=Decimal("0.75"),
            avg_score_losers=Decimal("0.55"),
        )
        assert metrics.score_differential == Decimal("0.20")

    def test_threshold_analysis_model(self):
        """Test ThresholdAnalysis model."""
        analysis = ThresholdAnalysis(
            threshold=Decimal("0.65"),
            would_trade_count=100,
            would_win_count=70,
            would_lose_count=30,
            win_rate=Decimal("70"),
            total_pnl=Decimal("15.5"),
            profit_factor=Decimal("2.5"),
        )
        assert analysis.threshold == Decimal("0.65")
        assert analysis.win_rate == Decimal("70")


class TestAccuracyTrend:
    """Tests for accuracy trend analysis."""

    def test_trend_classification_improving(self):
        """Test improving trend classification."""
        analysis = AccuracyTrendAnalysis(
            period_start=datetime.now(UTC) - timedelta(weeks=8),
            period_end=datetime.now(UTC),
            snapshots=[],
            trend=AccuracyTrend.IMPROVING,
            trend_slope=Decimal("2.5"),
            start_win_rate=Decimal("55"),
            end_win_rate=Decimal("65"),
            confidence=Decimal("0.8"),
        )
        assert analysis.trend == AccuracyTrend.IMPROVING
        assert analysis.win_rate_change == Decimal("10")

    def test_trend_classification_declining(self):
        """Test declining trend classification."""
        analysis = AccuracyTrendAnalysis(
            period_start=datetime.now(UTC) - timedelta(weeks=8),
            period_end=datetime.now(UTC),
            snapshots=[],
            trend=AccuracyTrend.DECLINING,
            trend_slope=Decimal("-2.0"),
            start_win_rate=Decimal("65"),
            end_win_rate=Decimal("55"),
            confidence=Decimal("0.8"),
        )
        assert analysis.trend == AccuracyTrend.DECLINING
        assert analysis.win_rate_change == Decimal("-10")

    def test_trend_classification_stable(self):
        """Test stable trend classification."""
        analysis = AccuracyTrendAnalysis(
            period_start=datetime.now(UTC) - timedelta(weeks=8),
            period_end=datetime.now(UTC),
            snapshots=[],
            trend=AccuracyTrend.STABLE,
            trend_slope=Decimal("0.2"),
            start_win_rate=Decimal("60"),
            end_win_rate=Decimal("61"),
            confidence=Decimal("0.7"),
        )
        assert analysis.trend == AccuracyTrend.STABLE


class TestRetrospectivePnLEstimation:
    """Tests for retrospective PnL estimation."""

    def test_pnl_estimation_take_profit_hit(self, tracker):
        """Test PnL estimation when take profit is hit."""
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0.001"),
            peak_price=Decimal("0.0012"),  # 20% gain
            min_price=Decimal("0.00095"),
        )
        assert pnl == Decimal("0.2")

    def test_pnl_estimation_stop_loss_hit(self, tracker):
        """Test PnL estimation when stop loss is hit."""
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0.001"),
            peak_price=Decimal("0.00105"),
            min_price=Decimal("0.00085"),  # 15% loss
        )
        assert pnl == Decimal("-0.1")

    def test_pnl_estimation_neither_hit(self, tracker):
        """Test PnL when neither TP nor SL hit."""
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0.001"),
            peak_price=Decimal("0.00115"),  # 15% gain
            min_price=Decimal("0.00092"),  # 8% loss
        )
        # Returns peak gain (0.00115 - 0.001) / 0.001 = 0.15
        assert pnl == Decimal("0.15")

    def test_pnl_estimation_zero_entry_price(self, tracker):
        """Test PnL returns zero for zero entry price."""
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0"),
            peak_price=Decimal("0.001"),
            min_price=Decimal("0.0005"),
        )
        assert pnl == Decimal("0")


class TestFactorBreakdown:
    """Tests for factor accuracy breakdown."""

    def test_factor_breakdown_model(self):
        """Test FactorAccuracyBreakdown model."""
        breakdown = FactorAccuracyBreakdown(
            factor_name="wallet_score",
            high_score_win_rate=Decimal("75"),
            low_score_win_rate=Decimal("50"),
            is_predictive=True,
            correlation_with_outcome=Decimal("0.4"),
            recommended_weight_adjustment="increase",
        )
        assert breakdown.is_predictive is True
        assert breakdown.win_rate_lift == Decimal("25")

    def test_factor_breakdown_not_predictive(self):
        """Test factor breakdown when not predictive."""
        breakdown = FactorAccuracyBreakdown(
            factor_name="context_score",
            high_score_win_rate=Decimal("52"),
            low_score_win_rate=Decimal("50"),
            is_predictive=False,
            correlation_with_outcome=Decimal("0.02"),
            recommended_weight_adjustment="decrease",
        )
        assert breakdown.is_predictive is False
        assert breakdown.win_rate_lift == Decimal("2")


class TestAccuracyMetricsCalculation:
    """Tests for accuracy metrics calculation."""

    @pytest.mark.asyncio
    async def test_calculate_accuracy_empty_data(self, tracker, mock_supabase):
        """Test accuracy calculation with no data."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        metrics = await tracker.calculate_accuracy_metrics()

        assert metrics.total_signals == 0
        assert metrics.signal_to_win_rate == Decimal("0")

    @pytest.mark.asyncio
    async def test_calculate_accuracy_with_signals(self, tracker, mock_supabase):
        """Test accuracy calculation with signals and trades."""
        signals = [
            {"id": str(uuid4()), "score": 0.8, "created_at": datetime.now(UTC).isoformat()},
            {"id": str(uuid4()), "score": 0.7, "created_at": datetime.now(UTC).isoformat()},
            {"id": str(uuid4()), "score": 0.6, "created_at": datetime.now(UTC).isoformat()},
            {"id": str(uuid4()), "score": 0.5, "created_at": datetime.now(UTC).isoformat()},
        ]

        trades = [
            {"signal_id": signals[0]["id"], "is_win": True, "realized_pnl_sol": 0.5},
            {"signal_id": signals[1]["id"], "is_win": True, "realized_pnl_sol": 0.3},
            {"signal_id": signals[2]["id"], "is_win": False, "realized_pnl_sol": -0.2},
        ]

        # Mock signals query
        tracker._signals_cache = signals

        # Mock trades query
        tracker._trades_cache = {s["id"]: None for s in signals}
        for t in trades:
            tracker._trades_cache[t["signal_id"]] = t

        metrics = await tracker.calculate_accuracy_metrics()

        assert metrics.total_signals == 4
        assert metrics.traded_signals == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1


class TestThresholdAnalysis:
    """Tests for threshold analysis."""

    @pytest.mark.asyncio
    async def test_analyze_thresholds_returns_list(self, tracker, mock_supabase):
        """Test that threshold analysis returns list of results."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        analyses = await tracker.analyze_thresholds()

        assert isinstance(analyses, list)
        # Should have analyses for thresholds 0.40, 0.45, ..., 0.85
        assert len(analyses) == 10

    @pytest.mark.asyncio
    async def test_threshold_analysis_structure(self, tracker, mock_supabase):
        """Test threshold analysis returns correct structure."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        analyses = await tracker.analyze_thresholds()

        for analysis in analyses:
            assert isinstance(analysis, ThresholdAnalysis)
            assert Decimal("0.40") <= analysis.threshold <= Decimal("0.85")


class TestOptimalThreshold:
    """Tests for optimal threshold calculation."""

    def test_find_optimal_threshold_empty_signals(self, tracker):
        """Test optimal threshold with no signals."""
        threshold = tracker._find_optimal_threshold([], [])
        assert threshold == Decimal("0.6")  # Default

    def test_find_optimal_threshold_with_data(self, tracker):
        """Test optimal threshold with data."""
        signals = [
            {"id": "1", "score": 0.8},
            {"id": "2", "score": 0.7},
            {"id": "3", "score": 0.6},
            {"id": "4", "score": 0.5},
        ]
        trades = [
            {"signal_id": "1", "realized_pnl_sol": 1.0},
            {"signal_id": "2", "realized_pnl_sol": 0.5},
            {"signal_id": "3", "realized_pnl_sol": -0.3},
            {"signal_id": "4", "realized_pnl_sol": -0.5},
        ]

        threshold = tracker._find_optimal_threshold(signals, trades)

        # Higher threshold should be optimal since high scores have positive PnL
        assert threshold >= Decimal("0.6")


class TestTrendAnalysis:
    """Tests for trend analysis."""

    @pytest.mark.asyncio
    async def test_trend_insufficient_data(self, tracker, mock_supabase):
        """Test trend analysis with insufficient snapshots."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        trend = await tracker.analyze_trend()

        assert trend.trend == AccuracyTrend.STABLE
        assert trend.confidence == Decimal("0")

    @pytest.mark.asyncio
    async def test_trend_with_improving_data(self, tracker, mock_supabase):
        """Test trend analysis with improving snapshots."""
        now = datetime.now(UTC)
        # Create snapshots from oldest to newest with increasing win rate
        snapshots = [
            {
                "id": str(uuid4()),
                "snapshot_date": (now - timedelta(weeks=i)).isoformat(),
                "signal_to_win_rate": str(50 + (9 - i) * 2),  # Increases as i decreases
                "sample_size": 100,
                "avg_signal_score": "0.65",
                "score_differential": "0.15",
            }
            for i in range(8, 0, -1)
        ]

        mock_supabase.table.return_value = ChainableMock(data=snapshots)

        trend = await tracker.analyze_trend()

        assert trend.trend == AccuracyTrend.IMPROVING
        assert trend.trend_slope > Decimal("0")


class TestSnapshotSaving:
    """Tests for accuracy snapshot saving."""

    @pytest.mark.asyncio
    async def test_snapshot_created_on_calculation(self, tracker, mock_supabase):
        """Test that snapshot is saved when metrics are calculated."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        # Track if insert was called
        insert_called = False
        original_insert = mock_supabase.table.return_value.insert

        def track_insert(*args, **kwargs):
            nonlocal insert_called
            insert_called = True
            return ChainableMock()

        mock_supabase.table.return_value.insert = track_insert

        await tracker.calculate_accuracy_metrics()

        # Snapshot should be saved
        assert insert_called
