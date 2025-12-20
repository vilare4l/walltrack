"""Unit tests for position status service."""

from datetime import datetime, timedelta

import pytest

from walltrack.models.position import (
    CalculatedLevel,
    Position,
    PositionLevels,
    PositionStatus,
)
from walltrack.services.execution.position_status import PositionStatusService


@pytest.fixture
def position_service() -> PositionStatusService:
    """Create position status service."""
    return PositionStatusService()


@pytest.fixture
def open_position() -> Position:
    """Create test open position."""
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
        exit_strategy_id="test-strategy",
        conviction_tier="standard",
        entry_time=datetime.utcnow() - timedelta(hours=5),
        levels=PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            take_profit_levels=[
                CalculatedLevel(
                    level_type="take_profit_1",
                    trigger_price=0.002,
                    sell_percentage=50,
                ),
            ],
        ),
    )


class TestUnrealizedPnL:
    """Tests for unrealized PnL calculation."""

    def test_profit_calculation(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test unrealized PnL when profitable."""
        metrics = position_service.calculate_metrics(open_position, 0.0015)

        assert metrics.unrealized_pnl_sol > 0
        assert metrics.unrealized_pnl_pct == pytest.approx(50, rel=0.01)
        assert metrics.is_profitable is True

    def test_loss_calculation(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test unrealized PnL when at loss."""
        metrics = position_service.calculate_metrics(open_position, 0.0007)

        assert metrics.unrealized_pnl_sol < 0
        assert metrics.unrealized_pnl_pct == pytest.approx(-30, rel=0.01)
        assert metrics.is_profitable is False

    def test_breakeven(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test unrealized PnL at breakeven."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.unrealized_pnl_sol == pytest.approx(0, abs=0.0001)
        assert metrics.unrealized_pnl_pct == pytest.approx(0, abs=0.01)

    def test_partial_position_pnl(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test PnL with partial position remaining."""
        open_position.current_amount_tokens = 50  # Half sold
        open_position.realized_pnl_sol = 0.025  # From previous exit

        metrics = position_service.calculate_metrics(open_position, 0.002)

        # Unrealized on remaining 50 tokens: 50 * (0.002 - 0.001) = 0.05
        assert metrics.unrealized_pnl_sol == pytest.approx(0.05, rel=0.01)
        assert metrics.realized_pnl_sol == 0.025


class TestMultiplier:
    """Tests for multiplier calculation."""

    def test_2x_multiplier(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test 2x multiplier."""
        metrics = position_service.calculate_metrics(open_position, 0.002)

        assert metrics.multiplier == pytest.approx(2.0, rel=0.01)

    def test_fractional_multiplier(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test fractional multiplier (loss)."""
        metrics = position_service.calculate_metrics(open_position, 0.0005)

        assert metrics.multiplier == pytest.approx(0.5, rel=0.01)

    def test_high_multiplier(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test high multiplier."""
        metrics = position_service.calculate_metrics(open_position, 0.01)

        assert metrics.multiplier == pytest.approx(10.0, rel=0.01)


class TestTimeHeld:
    """Tests for time held calculation."""

    def test_hours_held(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test hours held calculation."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.hours_held >= 5

    def test_new_position_time(
        self,
        position_service: PositionStatusService,
    ) -> None:
        """Test time held for new position."""
        position = Position(
            id="new-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(minutes=30),
        )

        metrics = position_service.calculate_metrics(position, 0.001)

        assert metrics.hours_held < 1
        assert metrics.hours_held >= 0.5


class TestExitLevelInfo:
    """Tests for exit level information."""

    def test_stop_loss_price(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test stop loss price is returned."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.stop_loss_price == 0.0005

    def test_next_take_profit(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test next take profit is returned."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.next_take_profit_price == 0.002

    def test_trailing_stop_inactive(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test trailing stop inactive."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.trailing_stop_active is False
        assert metrics.trailing_stop_price is None

    def test_trailing_stop_active(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test trailing stop active."""
        open_position.levels.trailing_stop_current_price = 0.0021

        metrics = position_service.calculate_metrics(open_position, 0.003)

        assert metrics.trailing_stop_active is True
        assert metrics.trailing_stop_price == 0.0021

    def test_no_levels(
        self,
        position_service: PositionStatusService,
    ) -> None:
        """Test position without levels."""
        position = Position(
            id="no-levels",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow(),
        )

        metrics = position_service.calculate_metrics(position, 0.001)

        assert metrics.stop_loss_price is None
        assert metrics.next_take_profit_price is None


class TestFormatSummary:
    """Tests for summary formatting."""

    def test_format_profit(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test formatting profitable position."""
        metrics = position_service.calculate_metrics(open_position, 0.002)
        summary = position_service.format_summary(open_position, metrics)

        assert summary["pnl"] == "+100.0%"
        assert summary["multiplier"] == "x2.00"
        assert summary["token"] == "TEST"

    def test_format_loss(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test formatting position at loss."""
        metrics = position_service.calculate_metrics(open_position, 0.0005)
        summary = position_service.format_summary(open_position, metrics)

        assert summary["pnl"] == "-50.0%"
        assert summary["multiplier"] == "x0.50"

    def test_format_time_minutes(
        self,
        position_service: PositionStatusService,
    ) -> None:
        """Test time formatting for minutes."""
        position = Position(
            id="new-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(minutes=30),
        )

        metrics = position_service.calculate_metrics(position, 0.001)
        summary = position_service.format_summary(position, metrics)

        assert "m" in summary["time_held"]

    def test_format_time_hours(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test time formatting for hours."""
        metrics = position_service.calculate_metrics(open_position, 0.001)
        summary = position_service.format_summary(open_position, metrics)

        assert "h" in summary["time_held"]

    def test_format_time_days(
        self,
        position_service: PositionStatusService,
    ) -> None:
        """Test time formatting for days."""
        position = Position(
            id="old-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=48),
        )

        metrics = position_service.calculate_metrics(position, 0.001)
        summary = position_service.format_summary(position, metrics)

        assert "d" in summary["time_held"]


class TestMoonbagStatus:
    """Tests for moonbag status."""

    def test_regular_position_not_moonbag(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test regular position is not moonbag."""
        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.is_moonbag is False

    def test_moonbag_position(
        self,
        position_service: PositionStatusService,
        open_position: Position,
    ) -> None:
        """Test position marked as moonbag."""
        open_position.is_moonbag = True
        open_position.status = PositionStatus.MOONBAG

        metrics = position_service.calculate_metrics(open_position, 0.001)

        assert metrics.is_moonbag is True
