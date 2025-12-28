"""Unit tests for time-based exit manager."""

from datetime import datetime, timedelta

import pytest

from walltrack.models.exit_strategy import TimeRulesConfig
from walltrack.models.position import ExitReason, Position, PositionStatus
from walltrack.services.execution.time_exit_manager import (
    StagnationWindow,
    TimeExitManager,
)


@pytest.fixture
def time_manager() -> TimeExitManager:
    """Create fresh time exit manager for each test."""
    return TimeExitManager()


@pytest.fixture
def position() -> Position:
    """Create test position opened now."""
    return Position(
        id="test-position-123",
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


@pytest.fixture
def old_position() -> Position:
    """Create test position opened 25 hours ago."""
    return Position(
        id="old-position-123",
        signal_id="test-signal",
        token_address="TokenAddress123456789012345678901234567890123",
        status=PositionStatus.OPEN,
        entry_price=0.001,
        entry_amount_sol=0.1,
        entry_amount_tokens=100,
        current_amount_tokens=100,
        exit_strategy_id="test-strategy",
        conviction_tier="standard",
        entry_time=datetime.utcnow() - timedelta(hours=25),
    )


@pytest.fixture
def time_config() -> TimeRulesConfig:
    """Create time rules config with both max hold and stagnation."""
    return TimeRulesConfig(
        max_hold_hours=24,
        stagnation_exit_enabled=True,
        stagnation_hours=6,
        stagnation_threshold_pct=5.0,
    )


class TestMaxHoldDuration:
    """Tests for max hold duration exits."""

    def test_no_exit_before_max_hold(
        self,
        time_manager: TimeExitManager,
        position: Position,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test no exit when within max hold duration."""
        result = time_manager.check_time_exits(position, time_config, 0.0015)

        assert result.should_exit is False
        assert result.hours_held < 24

    def test_exit_at_max_hold(
        self,
        time_manager: TimeExitManager,
        old_position: Position,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test exit when max hold duration exceeded."""
        result = time_manager.check_time_exits(old_position, time_config, 0.0015)

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TIME_LIMIT
        assert result.hours_held >= 24

    def test_profitable_max_hold_exit(
        self,
        time_manager: TimeExitManager,
        old_position: Position,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test max hold exit captures profit info."""
        # Price is up 50%
        result = time_manager.check_time_exits(old_position, time_config, 0.0015)

        assert result.should_exit is True
        assert result.unrealized_pnl_pct == pytest.approx(50, rel=0.01)

    def test_no_max_hold_when_disabled(
        self,
        time_manager: TimeExitManager,
        old_position: Position,
    ) -> None:
        """Test no max hold check when not configured."""
        config = TimeRulesConfig(max_hold_hours=None)

        result = time_manager.check_time_exits(old_position, config, 0.001)

        assert result.should_exit is False


class TestStagnationDetection:
    """Tests for stagnation-based exits."""

    def test_no_stagnation_before_window(
        self,
        time_manager: TimeExitManager,
        position: Position,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test no stagnation exit before window completes."""
        time_manager.initialize_for_position(position, time_config)

        result = time_manager.check_time_exits(position, time_config, 0.001)

        assert result.should_exit is False
        assert result.is_stagnant is False

    def test_stagnation_detected(
        self,
        time_manager: TimeExitManager,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test stagnation detected when price movement < threshold."""
        # Position opened 7 hours ago (past 6-hour window)
        stale_position = Position(
            id="stale-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=7),
        )

        time_manager.initialize_for_position(stale_position, time_config)

        # Manually set window start to be in the past
        window = time_manager._stagnation_windows[stale_position.id]
        window.window_start = datetime.utcnow() - timedelta(hours=7)

        # Price only moved 2% (below 5% threshold)
        result = time_manager.check_time_exits(stale_position, time_config, 0.00102)

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.STAGNATION
        assert result.is_stagnant is True
        assert result.price_movement_pct is not None
        assert result.price_movement_pct < 5.0

    def test_no_stagnation_with_movement(
        self,
        time_manager: TimeExitManager,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test no stagnation when price moves enough."""
        stale_position = Position(
            id="moving-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=7),
        )

        time_manager.initialize_for_position(stale_position, time_config)
        window = time_manager._stagnation_windows[stale_position.id]
        window.window_start = datetime.utcnow() - timedelta(hours=7)

        # Price moved 10% (above 5% threshold)
        result = time_manager.check_time_exits(stale_position, time_config, 0.0011)

        assert result.should_exit is False
        assert result.is_stagnant is False

    def test_stagnation_with_profit(
        self,
        time_manager: TimeExitManager,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test stagnation exit can still be profitable."""
        # Position opened 10 hours ago, already up
        stale_position = Position(
            id="profitable-stale-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,  # Entry was 0.001
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=10),
        )

        time_manager.initialize_for_position(stale_position, time_config)
        window = time_manager._stagnation_windows[stale_position.id]
        # Window starts at a higher price (position was already up)
        window.window_start = datetime.utcnow() - timedelta(hours=7)
        window.price_at_start = 0.00148  # Was up 48%

        # Now at 0.0015 (only ~1.35% move in window - stagnant)
        result = time_manager.check_time_exits(stale_position, time_config, 0.0015)

        assert result.should_exit is True
        assert result.is_stagnant is True
        # Still profitable from entry
        assert result.unrealized_pnl_pct == pytest.approx(50, rel=0.01)

    def test_stagnation_disabled(
        self,
        time_manager: TimeExitManager,
        position: Position,
    ) -> None:
        """Test no stagnation check when disabled."""
        config = TimeRulesConfig(
            stagnation_exit_enabled=False,
            stagnation_hours=6,
        )

        result = time_manager.check_time_exits(position, config, 0.001)

        assert result.should_exit is False
        assert result.is_stagnant is False


class TestStagnationWindow:
    """Tests for stagnation window calculations."""

    def test_window_not_complete(self) -> None:
        """Test window not complete before elapsed time."""
        window = StagnationWindow(
            position_id="test",
            window_start=datetime.utcnow(),
            window_hours=6,
            price_at_start=0.001,
        )

        assert window.is_complete() is False

    def test_window_complete(self) -> None:
        """Test window complete after elapsed time."""
        window = StagnationWindow(
            position_id="test",
            window_start=datetime.utcnow() - timedelta(hours=7),
            window_hours=6,
            price_at_start=0.001,
        )

        assert window.is_complete() is True

    def test_movement_calculation(self) -> None:
        """Test price movement percentage calculation."""
        window = StagnationWindow(
            position_id="test",
            window_start=datetime.utcnow() - timedelta(hours=7),
            window_hours=6,
            price_at_start=0.001,
        )

        # 10% move up
        assert window.calculate_movement_pct(0.0011) == pytest.approx(10.0, rel=0.01)

        # 10% move down
        assert window.calculate_movement_pct(0.0009) == pytest.approx(10.0, rel=0.01)

        # No move
        assert window.calculate_movement_pct(0.001) == pytest.approx(0.0, rel=0.01)

    def test_movement_with_zero_start_price(self) -> None:
        """Test movement calculation with zero start price."""
        window = StagnationWindow(
            position_id="test",
            window_start=datetime.utcnow(),
            window_hours=6,
            price_at_start=0.0,
        )

        assert window.calculate_movement_pct(0.001) == 0.0


class TestTimeExitManagerUtilities:
    """Tests for utility methods."""

    def test_get_hours_held(
        self,
        time_manager: TimeExitManager,
    ) -> None:
        """Test hours held calculation."""
        position = Position(
            id="test-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=12),
        )

        hours = time_manager.get_hours_held(position)

        assert hours >= 12

    def test_get_time_remaining(
        self,
        time_manager: TimeExitManager,
    ) -> None:
        """Test time remaining calculation."""
        position = Position(
            id="test-position-123",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=12),
        )

        remaining = time_manager.get_time_remaining(position, 24)

        assert remaining is not None
        assert remaining <= 12

    def test_get_time_remaining_no_limit(
        self,
        time_manager: TimeExitManager,
        position: Position,
    ) -> None:
        """Test time remaining when no max hold."""
        remaining = time_manager.get_time_remaining(position, None)

        assert remaining is None

    def test_remove_position(
        self,
        time_manager: TimeExitManager,
        position: Position,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test removing position tracking."""
        time_manager.initialize_for_position(position, time_config)

        assert position.id in time_manager._stagnation_windows

        time_manager.remove_position(position.id)

        assert position.id not in time_manager._stagnation_windows


class TestExitManagerTimeIntegration:
    """Tests for ExitManager integration with time exits."""

    def test_time_exit_with_exit_manager(
        self,
        time_config: TimeRulesConfig,
    ) -> None:
        """Test time-based exit through ExitManager."""
        from walltrack.models.exit_strategy import (
            ExitStrategy,
            MoonbagConfig,
            TrailingStopConfig,
        )
        from walltrack.models.position import PositionLevels
        from walltrack.services.execution.exit_manager import ExitManager

        old_position = Position(
            id="old-position-time-test",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=25),
            levels=PositionLevels(
                entry_price=0.001,
                stop_loss_price=0.0005,
            ),
        )

        strategy = ExitStrategy(
            name="Test Strategy",
            stop_loss=0.5,
            time_rules=time_config,
            trailing_stop=TrailingStopConfig(enabled=False),
            moonbag=MoonbagConfig(percentage=0),
        )

        manager = ExitManager()
        result = manager.check_exit_conditions(old_position, 0.001, strategy)

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TIME_LIMIT
        assert result.is_full_exit is True

    def test_no_time_exit_when_not_configured(self) -> None:
        """Test no time exit when time rules not configured."""
        from walltrack.models.exit_strategy import (
            ExitStrategy,
            MoonbagConfig,
            TrailingStopConfig,
        )
        from walltrack.models.position import PositionLevels
        from walltrack.services.execution.exit_manager import ExitManager

        old_position = Position(
            id="old-position-no-time",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            entry_time=datetime.utcnow() - timedelta(hours=100),
            levels=PositionLevels(
                entry_price=0.001,
                stop_loss_price=0.0005,
            ),
        )

        # No time rules configured
        strategy = ExitStrategy(
            name="Test Strategy",
            stop_loss=0.5,
            trailing_stop=TrailingStopConfig(enabled=False),
            moonbag=MoonbagConfig(percentage=0),
        )

        manager = ExitManager()
        result = manager.check_exit_conditions(old_position, 0.0008, strategy)

        # Should not exit for time - price is above stop loss
        assert result.should_exit is False
