"""Tests for backtest engine."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestBacktestEngine:
    """Tests for BacktestEngine class."""

    @pytest.fixture
    def mock_collector(self) -> MagicMock:
        """Create mock historical collector."""
        mock = MagicMock()
        mock.get_signals_for_range = AsyncMock(return_value=[])
        mock.get_price_timeline = AsyncMock(return_value=[])
        return mock

    @pytest.fixture
    def sample_signal(self) -> dict:
        """Create a sample historical signal for testing."""
        from walltrack.core.backtest.models import HistoricalSignal

        return HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address="Wallet111",
            token_address="Token111",
            wallet_score=Decimal("0.85"),
            token_price_usd=Decimal("0.001"),
            computed_score=Decimal("0.80"),
            score_breakdown={"wallet": 0.85, "cluster": 0.80, "token": 0.75, "context": 0.70},
            trade_eligible=True,
        )


class TestEngineRun(TestBacktestEngine):
    """Tests for BacktestEngine.run method."""

    async def test_run_returns_result(
        self,
        mock_collector: MagicMock,
    ) -> None:
        """Test that run returns a BacktestResult."""
        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import BacktestParameters

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
            )

            engine = BacktestEngine(params)
            result = await engine.run(name="Test Run")

            assert result.name == "Test Run"
            assert result.metrics is not None

    async def test_run_processes_signals(
        self,
        mock_collector: MagicMock,
        sample_signal: MagicMock,
    ) -> None:
        """Test that run processes historical signals."""
        mock_collector.get_signals_for_range = AsyncMock(
            return_value=[sample_signal]
        )

        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import BacktestParameters

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
                score_threshold=Decimal("0.70"),
            )

            engine = BacktestEngine(params)
            result = await engine.run()

            assert result.metrics.signals_processed == 1
            # Signal score 0.80 >= threshold 0.70, should trade
            assert result.metrics.signals_traded == 1


class TestRescoreSignal(TestBacktestEngine):
    """Tests for signal rescoring."""

    async def test_rescore_uses_weights(
        self,
        mock_collector: MagicMock,
        sample_signal: MagicMock,
    ) -> None:
        """Test that rescoring uses the configured weights."""
        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import (
                BacktestParameters,
                ScoringWeights,
            )

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
                scoring_weights=ScoringWeights(
                    wallet_weight=Decimal("1.0"),
                    cluster_weight=Decimal("0.0"),
                    token_weight=Decimal("0.0"),
                    context_weight=Decimal("0.0"),
                ),
            )

            engine = BacktestEngine(params)
            score = engine._rescore_signal(sample_signal)

            # With wallet_weight=1.0 and wallet_score=0.85
            assert score == Decimal("0.85")


class TestCanOpenPosition(TestBacktestEngine):
    """Tests for position limit checking."""

    async def test_can_open_within_limit(
        self,
        mock_collector: MagicMock,
    ) -> None:
        """Test that positions can be opened within limit."""
        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import BacktestParameters

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
                max_concurrent_positions=5,
            )

            engine = BacktestEngine(params)

            assert engine._can_open_position() is True

    async def test_cannot_open_at_limit(
        self,
        mock_collector: MagicMock,
    ) -> None:
        """Test that positions cannot be opened at limit."""
        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import BacktestParameters

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
                max_concurrent_positions=2,
            )

            engine = BacktestEngine(params)
            # Simulate having 2 open positions
            engine._open_positions = {"token1": MagicMock(), "token2": MagicMock()}

            assert engine._can_open_position() is False


class TestCalculateMaxDrawdown(TestBacktestEngine):
    """Tests for max drawdown calculation."""

    async def test_max_drawdown_calculation(
        self,
        mock_collector: MagicMock,
    ) -> None:
        """Test max drawdown is calculated correctly."""
        with patch(
            "walltrack.core.backtest.engine.get_historical_collector",
            return_value=mock_collector,
        ):
            from walltrack.core.backtest.engine import BacktestEngine
            from walltrack.core.backtest.parameters import BacktestParameters

            params = BacktestParameters(
                start_date=datetime(2024, 1, 1, tzinfo=UTC),
                end_date=datetime(2024, 1, 31, tzinfo=UTC),
            )

            engine = BacktestEngine(params)
            engine._equity_curve = [
                {"equity": 1.0, "timestamp": "2024-01-01"},
                {"equity": 1.2, "timestamp": "2024-01-02"},  # Peak
                {"equity": 0.9, "timestamp": "2024-01-03"},  # 25% drawdown from 1.2
                {"equity": 1.1, "timestamp": "2024-01-04"},
            ]

            max_dd = engine._calculate_max_drawdown()

            # 25% drawdown = (1.2 - 0.9) / 1.2 = 0.25 = 25%
            assert max_dd == Decimal("25")
