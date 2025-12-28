"""Unit tests for positions dashboard component."""

from datetime import datetime, timedelta

import pytest

from walltrack.models.position import (
    Position,
    PositionStatus,
)
from walltrack.services.execution.position_status import PositionMetrics
from walltrack.ui.components.positions import (
    format_pnl,
    format_position_detail,
    format_position_row,
    format_time_held,
)


class TestFormatPnL:
    """Tests for PnL formatting."""

    def test_positive_pnl(self) -> None:
        """Test positive PnL formatting."""
        assert format_pnl(50.0) == "+50.0%"
        assert format_pnl(100.0) == "+100.0%"
        assert format_pnl(0.5) == "+0.5%"

    def test_negative_pnl(self) -> None:
        """Test negative PnL formatting."""
        assert format_pnl(-25.0) == "-25.0%"
        assert format_pnl(-50.0) == "-50.0%"

    def test_zero_pnl(self) -> None:
        """Test zero PnL formatting."""
        assert format_pnl(0.0) == "+0.0%"


class TestFormatTimeHeld:
    """Tests for time held formatting."""

    def test_minutes(self) -> None:
        """Test formatting for minutes."""
        assert format_time_held(0.5) == "30m"
        assert format_time_held(0.25) == "15m"

    def test_hours(self) -> None:
        """Test formatting for hours."""
        assert format_time_held(5.0) == "5.0h"
        assert format_time_held(12.5) == "12.5h"

    def test_days(self) -> None:
        """Test formatting for days."""
        assert format_time_held(48.0) == "2.0d"
        assert format_time_held(72.0) == "3.0d"


class TestFormatPositionRow:
    """Tests for position row formatting."""

    @pytest.fixture
    def position(self) -> Position:
        """Create test position."""
        return Position(
            id="test-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            token_symbol="TEST",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="preset-balanced",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=5),
        )

    @pytest.fixture
    def metrics(self) -> PositionMetrics:
        """Create test metrics."""
        return PositionMetrics(
            unrealized_pnl_sol=0.05,
            unrealized_pnl_pct=50.0,
            realized_pnl_sol=0.0,
            current_price=0.0015,
            entry_price=0.001,
            peak_price=0.0015,
            multiplier=1.5,
            hours_held=5.0,
            is_profitable=True,
            is_moonbag=False,
            stop_loss_price=0.0005,
            next_take_profit_price=0.002,
            trailing_stop_active=False,
            trailing_stop_price=None,
        )

    def test_format_row(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test row formatting."""
        row = format_position_row(position, metrics)

        assert row["Token"] == "TEST"
        assert row["PnL %"] == "+50.0%"
        assert row["Multiplier"] == "x1.50"
        assert row["Time Held"] == "5.0h"
        assert row["Strategy"] == "balanced"
        assert row["Status"] == "open"

    def test_format_moonbag_row(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test moonbag position row."""
        position.is_moonbag = True
        row = format_position_row(position, metrics)

        assert row["Status"] == "Moonbag"


class TestFormatPositionDetail:
    """Tests for position detail formatting."""

    @pytest.fixture
    def position(self) -> Position:
        """Create test position."""
        return Position(
            id="test-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            token_symbol="TEST",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="preset-balanced",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=5),
        )

    @pytest.fixture
    def metrics(self) -> PositionMetrics:
        """Create test metrics."""
        return PositionMetrics(
            unrealized_pnl_sol=0.05,
            unrealized_pnl_pct=50.0,
            realized_pnl_sol=0.0,
            current_price=0.0015,
            entry_price=0.001,
            peak_price=0.0015,
            multiplier=1.5,
            hours_held=5.0,
            is_profitable=True,
            is_moonbag=False,
            stop_loss_price=0.0005,
            next_take_profit_price=0.002,
            trailing_stop_active=False,
            trailing_stop_price=None,
        )

    def test_basic_detail(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test basic detail formatting."""
        detail = format_position_detail(position, metrics)

        assert "## TEST" in detail
        assert "Position ID" in detail
        assert "Entry" in detail
        assert "PnL" in detail
        assert "+50.0%" in detail

    def test_detail_with_trailing_stop(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test detail with trailing stop."""
        metrics.trailing_stop_active = True
        metrics.trailing_stop_price = 0.0021

        detail = format_position_detail(position, metrics)

        assert "Trailing Stop" in detail
        assert "Active" in detail

    def test_detail_with_stop_loss(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test detail includes stop loss."""
        detail = format_position_detail(position, metrics)

        assert "Stop Loss" in detail
        assert "0.00050000" in detail

    def test_detail_with_take_profit(
        self, position: Position, metrics: PositionMetrics
    ) -> None:
        """Test detail includes next TP."""
        detail = format_position_detail(position, metrics)

        assert "Next TP" in detail
        assert "0.00200000" in detail
