"""Tests for backtest service."""

from datetime import UTC, date, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.core.feedback.backtest_models import (
    BacktestConfig,
    BacktestProgress,
    BacktestResult,
    BacktestStatus,
    ExitStrategyConfig,
    HistoricalSignal,
    MetricsComparison,
    PerformanceMetrics,
    ScoringWeights,
    SimulatedTrade,
    TradeComparison,
)
from walltrack.core.feedback.backtester import BacktestService, get_backtest_service

# =============================================================================
# Model Tests
# =============================================================================


class TestScoringWeights:
    """Test ScoringWeights model."""

    def test_total_weight_valid(self):
        """Test valid weight sum."""
        weights = ScoringWeights(
            wallet_score_weight=Decimal("0.3"),
            token_metrics_weight=Decimal("0.25"),
            liquidity_weight=Decimal("0.2"),
            holder_distribution_weight=Decimal("0.15"),
            momentum_weight=Decimal("0.1"),
        )
        assert weights.is_valid is True
        assert weights.total_weight == Decimal("1.0")

    def test_total_weight_invalid(self):
        """Test invalid weight sum."""
        weights = ScoringWeights(
            wallet_score_weight=Decimal("0.5"),
            token_metrics_weight=Decimal("0.5"),
            liquidity_weight=Decimal("0.5"),
            holder_distribution_weight=Decimal("0.5"),
            momentum_weight=Decimal("0.5"),
        )
        assert weights.is_valid is False
        assert weights.total_weight == Decimal("2.5")

    def test_default_weights_valid(self):
        """Test default weights sum to 1."""
        weights = ScoringWeights()
        assert weights.is_valid is True


class TestBacktestConfig:
    """Test BacktestConfig model."""

    def test_date_range_days(self):
        """Test date range calculation."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
        )
        assert config.date_range_days == 31

    def test_default_values(self):
        """Test default configuration values."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
        )
        assert config.score_threshold == Decimal("70")
        assert config.slippage_percent == Decimal("1.0")
        assert config.include_gas_costs is True

    def test_single_day_range(self):
        """Test single day date range."""
        config = BacktestConfig(
            start_date=date(2024, 1, 15), end_date=date(2024, 1, 15)
        )
        assert config.date_range_days == 1


class TestSimulatedTrade:
    """Test SimulatedTrade model."""

    def test_net_pnl_calculation(self):
        """Test net PnL after costs."""
        trade = SimulatedTrade(
            signal_id="test",
            token_address="token123",
            source_wallet="wallet123",
            simulated_score=Decimal("80"),
            would_trade=True,
            entry_price=Decimal("1.0"),
            exit_price=Decimal("1.5"),
            exit_reason="take_profit",
            position_size_sol=Decimal("0.1"),
            gross_pnl_sol=Decimal("0.05"),
            slippage_cost_sol=Decimal("0.001"),
            gas_cost_sol=Decimal("0.0001"),
        )

        assert trade.net_pnl_sol == Decimal("0.0489")
        assert trade.is_win is True

    def test_pnl_percent(self):
        """Test PnL percentage calculation."""
        trade = SimulatedTrade(
            signal_id="test",
            token_address="token123",
            source_wallet="wallet123",
            simulated_score=Decimal("80"),
            would_trade=True,
            entry_price=Decimal("1.0"),
            exit_price=Decimal("1.1"),
            exit_reason="take_profit",
            position_size_sol=Decimal("0.1"),
            gross_pnl_sol=Decimal("0.01"),
            slippage_cost_sol=Decimal("0.001"),
            gas_cost_sol=Decimal("0.0001"),
        )
        # net_pnl = 0.01 - 0.001 - 0.0001 = 0.0089
        # pnl_percent = 0.0089 / 0.1 * 100 = 8.9%
        assert trade.pnl_percent == Decimal("8.90")

    def test_losing_trade(self):
        """Test losing trade detection."""
        trade = SimulatedTrade(
            signal_id="test",
            token_address="token123",
            source_wallet="wallet123",
            simulated_score=Decimal("70"),
            would_trade=True,
            entry_price=Decimal("1.0"),
            exit_price=Decimal("0.9"),
            exit_reason="stop_loss",
            position_size_sol=Decimal("0.1"),
            gross_pnl_sol=Decimal("-0.01"),
            slippage_cost_sol=Decimal("0.001"),
            gas_cost_sol=Decimal("0.0001"),
        )
        assert trade.is_win is False


class TestPerformanceMetrics:
    """Test PerformanceMetrics model."""

    def test_win_rate(self):
        """Test win rate calculation."""
        metrics = PerformanceMetrics(
            total_trades=100, winning_trades=65, losing_trades=35
        )
        assert metrics.win_rate == Decimal("65.00")

    def test_profit_factor(self):
        """Test profit factor calculation."""
        metrics = PerformanceMetrics(
            gross_profit_sol=Decimal("10.0"), gross_loss_sol=Decimal("5.0")
        )
        assert metrics.profit_factor == Decimal("2.00")

    def test_profit_factor_no_loss(self):
        """Test profit factor with no losses."""
        metrics = PerformanceMetrics(
            gross_profit_sol=Decimal("10.0"), gross_loss_sol=Decimal("0")
        )
        assert metrics.profit_factor is None

    def test_expectancy(self):
        """Test expectancy calculation."""
        metrics = PerformanceMetrics(total_trades=10, total_pnl_sol=Decimal("1.0"))
        assert metrics.expectancy == Decimal("0.1000")

    def test_zero_trades(self):
        """Test metrics with no trades."""
        metrics = PerformanceMetrics()
        assert metrics.win_rate == Decimal("0")
        assert metrics.expectancy == Decimal("0")


class TestMetricsComparison:
    """Test MetricsComparison model."""

    def test_improvement_detection(self):
        """Test improvement detection."""
        actual = PerformanceMetrics(
            total_trades=100,
            winning_trades=50,
            losing_trades=50,
            total_pnl_sol=Decimal("1.0"),
        )

        simulated = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            total_pnl_sol=Decimal("2.0"),
        )

        comparison = MetricsComparison(actual=actual, simulated=simulated)

        assert comparison.pnl_difference_sol == Decimal("1.0")
        assert comparison.is_improvement is True

    def test_no_improvement(self):
        """Test when simulated is worse."""
        actual = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            total_pnl_sol=Decimal("2.0"),
        )

        simulated = PerformanceMetrics(
            total_trades=100,
            winning_trades=40,
            losing_trades=60,
            total_pnl_sol=Decimal("0.5"),
        )

        comparison = MetricsComparison(actual=actual, simulated=simulated)

        assert comparison.pnl_difference_sol == Decimal("-1.5")
        assert comparison.is_improvement is False

    def test_win_rate_difference(self):
        """Test win rate difference calculation."""
        actual = PerformanceMetrics(total_trades=100, winning_trades=50)
        simulated = PerformanceMetrics(total_trades=100, winning_trades=60)

        comparison = MetricsComparison(actual=actual, simulated=simulated)
        assert comparison.win_rate_difference == Decimal("10.00")


class TestTradeComparison:
    """Test TradeComparison model."""

    def test_outcome_changed_new_trade(self):
        """Test detecting new trade that would be made."""
        comparison = TradeComparison(
            signal_id="test",
            token_address="token123",
            timestamp=datetime.now(UTC),
            actual_traded=False,
            actual_pnl_sol=None,
            simulated_traded=True,
            simulated_pnl_sol=Decimal("0.05"),
        )

        assert comparison.outcome_changed is True
        assert "NEW TRADE" in comparison.change_description

    def test_outcome_changed_skipped(self):
        """Test detecting trade that would be skipped."""
        comparison = TradeComparison(
            signal_id="test",
            token_address="token123",
            timestamp=datetime.now(UTC),
            actual_traded=True,
            actual_pnl_sol=Decimal("-0.02"),
            simulated_traded=False,
            simulated_pnl_sol=None,
        )

        assert comparison.outcome_changed is True
        assert "SKIPPED" in comparison.change_description

    def test_no_change(self):
        """Test when no change in outcome."""
        comparison = TradeComparison(
            signal_id="test",
            token_address="token123",
            timestamp=datetime.now(UTC),
            actual_traded=True,
            actual_pnl_sol=Decimal("0.02"),
            simulated_traded=True,
            simulated_pnl_sol=Decimal("0.02"),
        )

        assert comparison.outcome_changed is False
        assert comparison.pnl_changed is False
        assert comparison.change_description == "No change"


class TestBacktestProgress:
    """Test BacktestProgress model."""

    def test_progress_percent(self):
        """Test progress percentage calculation."""
        progress = BacktestProgress(
            backtest_id="test",
            status=BacktestStatus.RUNNING,
            signals_processed=50,
            total_signals=100,
            current_phase="Rescoring",
            elapsed_seconds=10,
        )
        assert progress.progress_percent == Decimal("50.0")

    def test_zero_signals(self):
        """Test progress with no signals."""
        progress = BacktestProgress(
            backtest_id="test",
            status=BacktestStatus.RUNNING,
            signals_processed=0,
            total_signals=0,
            current_phase="Loading",
            elapsed_seconds=0,
        )
        assert progress.progress_percent == Decimal("0")


class TestBacktestResult:
    """Test BacktestResult model."""

    def test_successful_result(self):
        """Test successful backtest result."""
        result = BacktestResult(
            id="test",
            config=BacktestConfig(
                start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
            ),
            status=BacktestStatus.COMPLETED,
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
        )
        assert result.is_successful is True

    def test_failed_result(self):
        """Test failed backtest result."""
        result = BacktestResult(
            id="test",
            config=BacktestConfig(
                start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
            ),
            status=BacktestStatus.FAILED,
            started_at=datetime.now(UTC),
            error_message="Database error",
        )
        assert result.is_successful is False

    def test_trades_changed_count(self):
        """Test trades changed count."""
        result = BacktestResult(
            id="test",
            config=BacktestConfig(
                start_date=date(2024, 1, 1), end_date=date(2024, 1, 31)
            ),
            status=BacktestStatus.COMPLETED,
            started_at=datetime.now(UTC),
            trade_comparisons=[
                TradeComparison(
                    signal_id="1",
                    token_address="t1",
                    timestamp=datetime.now(UTC),
                    actual_traded=False,
                    simulated_traded=True,
                    simulated_pnl_sol=Decimal("0.01"),
                ),
                TradeComparison(
                    signal_id="2",
                    token_address="t2",
                    timestamp=datetime.now(UTC),
                    actual_traded=True,
                    simulated_traded=True,
                    actual_pnl_sol=Decimal("0.01"),
                    simulated_pnl_sol=Decimal("0.01"),
                ),
            ],
        )
        assert result.trades_changed_count == 1


# =============================================================================
# Service Tests
# =============================================================================


class ChainableMock:
    """Mock that supports method chaining for Supabase client."""

    def __init__(self, data=None):
        self._data = data if data is not None else []

    def __getattr__(self, name):
        return lambda *_args, **_kwargs: self

    async def execute(self):
        return MagicMock(data=self._data)


class TestBacktestService:
    """Test BacktestService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        svc = BacktestService()
        svc._supabase = ChainableMock()
        return svc

    @pytest.fixture
    def sample_config(self):
        """Create sample backtest config."""
        return BacktestConfig(start_date=date(2024, 1, 1), end_date=date(2024, 1, 31))

    @pytest.fixture
    def sample_signal(self):
        """Create sample historical signal."""
        return HistoricalSignal(
            id="signal-1",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={
                "wallet_score": 0.8,
                "token_metrics": 0.7,
                "liquidity": 0.6,
                "holder_distribution": 0.5,
                "momentum": 0.4,
            },
            was_traded=True,
            actual_entry_price=Decimal("1.0"),
            actual_exit_price=Decimal("1.2"),
            actual_pnl_sol=Decimal("0.02"),
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), Decimal("1.1")),
                (datetime(2024, 1, 15, 10, 10, tzinfo=UTC), Decimal("1.2")),
                (datetime(2024, 1, 15, 10, 15, tzinfo=UTC), Decimal("1.15")),
            ],
            max_price_after=Decimal("1.2"),
            min_price_after=Decimal("1.0"),
        )

    @pytest.mark.asyncio
    async def test_rescore_signal(self, service, sample_signal):
        """Test signal rescoring with new weights."""
        new_weights = ScoringWeights(
            wallet_score_weight=Decimal("0.4"),
            token_metrics_weight=Decimal("0.3"),
            liquidity_weight=Decimal("0.15"),
            holder_distribution_weight=Decimal("0.1"),
            momentum_weight=Decimal("0.05"),
        )

        rescored = await service._rescore_signal(sample_signal, new_weights)

        # Score should be recalculated
        assert rescored.id == sample_signal.id
        assert rescored.token_address == sample_signal.token_address

    def test_simulate_exit_stop_loss(self, service, sample_config):
        """Test exit simulation hitting stop loss."""
        signal = HistoricalSignal(
            id="signal-sl",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), Decimal("0.9")),
                (datetime(2024, 1, 15, 10, 10, tzinfo=UTC), Decimal("0.8")),
            ],
            max_price_after=Decimal("1.0"),
            min_price_after=Decimal("0.8"),
        )

        exit_price, exit_reason = service._simulate_exit(signal, sample_config)

        assert exit_reason == "stop_loss"
        assert exit_price == Decimal("0.85")

    def test_simulate_exit_take_profit(self, service, sample_config):
        """Test exit simulation hitting take profit."""
        signal = HistoricalSignal(
            id="signal-tp",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), Decimal("1.3")),
                (datetime(2024, 1, 15, 10, 10, tzinfo=UTC), Decimal("1.6")),
            ],
            max_price_after=Decimal("1.6"),
            min_price_after=Decimal("1.0"),
        )

        exit_price, exit_reason = service._simulate_exit(signal, sample_config)

        assert exit_reason == "take_profit"
        assert exit_price == Decimal("1.50")  # 50% take profit

    def test_simulate_exit_time_limit(self, service):
        """Test exit simulation hitting time limit."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31),
            exit_strategy=ExitStrategyConfig(max_hold_minutes=10),
        )

        signal = HistoricalSignal(
            id="signal-time",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), Decimal("1.05")),
                (datetime(2024, 1, 15, 10, 15, tzinfo=UTC), Decimal("1.10")),
            ],
            max_price_after=Decimal("1.10"),
            min_price_after=Decimal("1.0"),
        )

        exit_price, exit_reason = service._simulate_exit(signal, config)

        assert exit_reason == "time_limit"
        assert exit_price == Decimal("1.10")

    def test_simulate_exit_trailing_stop(self, service, sample_config):
        """Test exit simulation hitting trailing stop."""
        signal = HistoricalSignal(
            id="signal-ts",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0, tzinfo=UTC), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5, tzinfo=UTC), Decimal("1.20")),
                (datetime(2024, 1, 15, 10, 10, tzinfo=UTC), Decimal("1.15")),
                (datetime(2024, 1, 15, 10, 15, tzinfo=UTC), Decimal("1.05")),
            ],
            max_price_after=Decimal("1.20"),
            min_price_after=Decimal("1.0"),
        )

        exit_price, exit_reason = service._simulate_exit(signal, sample_config)

        assert exit_reason == "trailing_stop"
        # Trailing stop at 10% below peak (1.20)
        assert exit_price == Decimal("1.08")

    def test_simulate_exit_no_price_data(self, service, sample_config):
        """Test exit simulation with no price data."""
        signal = HistoricalSignal(
            id="signal-no-data",
            timestamp=datetime(2024, 1, 15, 10, 0, tzinfo=UTC),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[],
            max_price_after=None,
            min_price_after=None,
        )

        exit_price, exit_reason = service._simulate_exit(signal, sample_config)

        assert exit_reason == "no_data"
        assert exit_price == Decimal("1.0")

    def test_calculate_simulated_metrics(self, service):
        """Test simulated metrics calculation."""
        trades = [
            SimulatedTrade(
                signal_id="1",
                token_address="t1",
                source_wallet="w1",
                simulated_score=Decimal("80"),
                would_trade=True,
                entry_price=Decimal("1.0"),
                exit_price=Decimal("1.2"),
                exit_reason="take_profit",
                position_size_sol=Decimal("0.1"),
                gross_pnl_sol=Decimal("0.02"),
                slippage_cost_sol=Decimal("0.001"),
                gas_cost_sol=Decimal("0.0001"),
            ),
            SimulatedTrade(
                signal_id="2",
                token_address="t2",
                source_wallet="w1",
                simulated_score=Decimal("75"),
                would_trade=True,
                entry_price=Decimal("1.0"),
                exit_price=Decimal("0.9"),
                exit_reason="stop_loss",
                position_size_sol=Decimal("0.1"),
                gross_pnl_sol=Decimal("-0.01"),
                slippage_cost_sol=Decimal("0.001"),
                gas_cost_sol=Decimal("0.0001"),
            ),
        ]

        metrics = service._calculate_simulated_metrics(trades)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("50.00")

    def test_calculate_simulated_metrics_empty(self, service):
        """Test simulated metrics with no trades."""
        metrics = service._calculate_simulated_metrics([])
        assert metrics.total_trades == 0

    def test_calculate_max_drawdown(self, service):
        """Test max drawdown calculation."""
        trades = [
            {"exit_timestamp": "2024-01-01T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-02T10:00:00Z", "realized_pnl_sol": "0.2"},
            {"exit_timestamp": "2024-01-03T10:00:00Z", "realized_pnl_sol": "-0.25"},
            {"exit_timestamp": "2024-01-04T10:00:00Z", "realized_pnl_sol": "-0.1"},
            {"exit_timestamp": "2024-01-05T10:00:00Z", "realized_pnl_sol": "0.15"},
        ]

        max_dd = service._calculate_max_drawdown(trades)

        # Peak at 0.3, trough at -0.05, drawdown = 0.35
        assert max_dd == Decimal("0.35")

    def test_calculate_max_consecutive_losses(self, service):
        """Test max consecutive losses calculation."""
        trades = [
            {"exit_timestamp": "2024-01-01T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-02T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-03T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-04T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-05T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-06T10:00:00Z", "realized_pnl_sol": "-0.02"},
        ]

        max_consecutive = service._calculate_max_consecutive_losses(trades)

        assert max_consecutive == 3

    def test_get_progress(self, service):
        """Test progress tracking."""
        # No progress initially
        assert service.get_progress("nonexistent") is None

    def test_clear_cache(self, service):
        """Test cache clearing."""
        service._signal_cache["test_key"] = []
        assert len(service._signal_cache) == 1

        service.clear_cache()
        assert len(service._signal_cache) == 0

    @pytest.mark.asyncio
    async def test_run_backtest_success(self, service, sample_config):
        """Test running backtest successfully."""
        # Mock data loading
        service._load_historical_signals = AsyncMock(return_value=[])
        service._calculate_actual_metrics = AsyncMock(
            return_value=PerformanceMetrics()
        )
        service._store_backtest_result = AsyncMock()

        result = await service.run_backtest(sample_config)

        assert result.status == BacktestStatus.COMPLETED
        assert result.is_successful is True

    @pytest.mark.asyncio
    async def test_run_backtest_with_signals(self, service, sample_config, sample_signal):
        """Test backtest with actual signals."""
        service._load_historical_signals = AsyncMock(return_value=[sample_signal])
        service._calculate_actual_metrics = AsyncMock(
            return_value=PerformanceMetrics(
                total_trades=1,
                winning_trades=1,
                total_pnl_sol=Decimal("0.02"),
            )
        )
        service._store_backtest_result = AsyncMock()

        result = await service.run_backtest(sample_config)

        assert result.status == BacktestStatus.COMPLETED
        assert result.total_signals_analyzed == 1

    @pytest.mark.asyncio
    async def test_run_backtest_failure(self, service, sample_config):
        """Test backtest failure handling."""
        service._load_historical_signals = AsyncMock(
            side_effect=Exception("Database error")
        )

        result = await service.run_backtest(sample_config)

        assert result.status == BacktestStatus.FAILED
        assert result.error_message == "Database error"


@pytest.mark.asyncio
async def test_get_backtest_service_singleton():
    """Test singleton pattern for backtest service."""
    # Reset singleton
    import walltrack.core.feedback.backtester as backtester_module

    backtester_module._backtest_service = None

    service1 = await get_backtest_service()
    service2 = await get_backtest_service()

    assert service1 is service2
