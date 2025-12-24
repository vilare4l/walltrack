"""Tests for backtest result models."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestBacktestTrade:
    """Tests for BacktestTrade model."""

    def test_trade_creation(self) -> None:
        """Test creating a backtest trade."""
        from walltrack.core.backtest.results import BacktestTrade

        trade = BacktestTrade(
            id=uuid4(),
            signal_id=uuid4(),
            token_address="Token111",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("0.001"),
            position_size_sol=Decimal("0.1"),
            tokens_bought=Decimal("1000"),
        )

        assert trade.is_open is True
        assert trade.is_winner is None  # No P&L yet

    def test_closed_winning_trade(self) -> None:
        """Test a closed winning trade."""
        from walltrack.core.backtest.results import BacktestTrade

        trade = BacktestTrade(
            id=uuid4(),
            signal_id=uuid4(),
            token_address="Token111",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("0.001"),
            position_size_sol=Decimal("0.1"),
            tokens_bought=Decimal("1000"),
            exit_time=datetime.now(UTC),
            exit_price=Decimal("0.002"),
            exit_reason="take_profit",
            realized_pnl=Decimal("10.00"),
            is_open=False,
        )

        assert trade.is_open is False
        assert trade.is_winner is True

    def test_closed_losing_trade(self) -> None:
        """Test a closed losing trade."""
        from walltrack.core.backtest.results import BacktestTrade

        trade = BacktestTrade(
            id=uuid4(),
            signal_id=uuid4(),
            token_address="Token111",
            entry_time=datetime.now(UTC),
            entry_price=Decimal("0.001"),
            position_size_sol=Decimal("0.1"),
            tokens_bought=Decimal("1000"),
            exit_time=datetime.now(UTC),
            exit_price=Decimal("0.0005"),
            exit_reason="stop_loss",
            realized_pnl=Decimal("-5.00"),
            is_open=False,
        )

        assert trade.is_winner is False


class TestBacktestMetrics:
    """Tests for BacktestMetrics model."""

    def test_metrics_default_values(self) -> None:
        """Test default metric values."""
        from walltrack.core.backtest.results import BacktestMetrics

        metrics = BacktestMetrics()
        assert metrics.total_trades == 0
        assert metrics.win_rate == Decimal("0")
        assert metrics.total_pnl == Decimal("0")

    def test_calculate_from_trades(self) -> None:
        """Test calculating metrics from trades."""
        from walltrack.core.backtest.results import BacktestMetrics, BacktestTrade

        # Create 3 winning and 1 losing trade
        trades = [
            BacktestTrade(
                id=uuid4(),
                signal_id=uuid4(),
                token_address="Token1",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("0.001"),
                position_size_sol=Decimal("0.1"),
                tokens_bought=Decimal("100"),
                exit_price=Decimal("0.002"),
                realized_pnl=Decimal("10"),
                is_open=False,
            ),
            BacktestTrade(
                id=uuid4(),
                signal_id=uuid4(),
                token_address="Token2",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("0.001"),
                position_size_sol=Decimal("0.1"),
                tokens_bought=Decimal("100"),
                exit_price=Decimal("0.003"),
                realized_pnl=Decimal("20"),
                is_open=False,
            ),
            BacktestTrade(
                id=uuid4(),
                signal_id=uuid4(),
                token_address="Token3",
                entry_time=datetime.now(UTC),
                entry_price=Decimal("0.001"),
                position_size_sol=Decimal("0.1"),
                tokens_bought=Decimal("100"),
                exit_price=Decimal("0.0005"),
                realized_pnl=Decimal("-5"),
                is_open=False,
            ),
        ]

        metrics = BacktestMetrics()
        metrics.calculate_from_trades(trades)

        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1
        assert metrics.total_pnl == Decimal("25")  # 10 + 20 - 5


class TestBacktestResult:
    """Tests for BacktestResult model."""

    def test_result_creation(self) -> None:
        """Test creating a backtest result."""
        from walltrack.core.backtest.results import (
            BacktestMetrics,
            BacktestResult,
        )

        now = datetime.now(UTC)
        result = BacktestResult(
            id=uuid4(),
            name="Test Backtest",
            parameters={"score_threshold": 0.70},
            started_at=now,
            completed_at=now,
            duration_seconds=10.5,
            trades=[],
            metrics=BacktestMetrics(),
        )

        assert result.name == "Test Backtest"
        assert result.duration_seconds == 10.5
        assert len(result.trades) == 0
