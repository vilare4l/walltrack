"""Unit tests for exit manager and level calculator."""

import pytest

from walltrack.models.exit_strategy import (
    ExitStrategy,
    MoonbagConfig,
    TakeProfitLevel,
    TrailingStopConfig,
)
from walltrack.models.position import (
    CalculatedLevel,
    ExitReason,
    Position,
    PositionLevels,
    PositionStatus,
)
from walltrack.services.execution.exit_manager import ExitManager
from walltrack.services.execution.level_calculator import LevelCalculator


@pytest.fixture
def strategy() -> ExitStrategy:
    """Create test exit strategy."""
    return ExitStrategy(
        id="test-strategy",
        name="Test Strategy",
        take_profit_levels=[
            TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
        ],
        stop_loss=0.5,  # -50%
        trailing_stop=TrailingStopConfig(enabled=False),
        moonbag=MoonbagConfig(percentage=0),
    )


@pytest.fixture
def position_with_levels() -> Position:
    """Create test position with calculated levels."""
    levels = PositionLevels(
        entry_price=0.001,
        stop_loss_price=0.0005,  # -50%
        take_profit_levels=[
            CalculatedLevel(
                level_type="take_profit_1",
                trigger_price=0.002,  # 2x
                sell_percentage=50,
            ),
            CalculatedLevel(
                level_type="take_profit_2",
                trigger_price=0.003,  # 3x
                sell_percentage=100,
            ),
        ],
    )

    return Position(
        id="test-position",
        signal_id="test-signal",
        token_address="TokenAddress123456789012345678901234567890123",
        status=PositionStatus.OPEN,
        entry_price=0.001,
        entry_amount_sol=0.1,
        entry_amount_tokens=100,
        current_amount_tokens=100,
        exit_strategy_id="test-strategy",
        conviction_tier="standard",
        levels=levels,
    )


class TestLevelCalculator:
    """Tests for level calculator."""

    def test_calculate_stop_loss(self) -> None:
        """Test stop loss calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,  # -50%
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.stop_loss_price == 0.0005  # 50% of entry

    def test_calculate_take_profits(self) -> None:
        """Test take profit level calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
            ],
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert len(levels.take_profit_levels) == 2
        assert levels.take_profit_levels[0].trigger_price == 0.002  # 2x
        assert levels.take_profit_levels[1].trigger_price == 0.003  # 3x

    def test_calculate_trailing_stop_activation(self) -> None:
        """Test trailing stop activation price calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.trailing_stop_activation_price == 0.002  # 2x

    def test_calculate_moonbag_stop(self) -> None:
        """Test moonbag stop price calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            moonbag=MoonbagConfig(percentage=50, stop_loss=0.8),  # -80%
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.moonbag_stop_price == pytest.approx(0.0002, rel=0.01)  # 80% loss

    def test_no_moonbag_stop_when_ride_to_zero(self) -> None:
        """Test no moonbag stop when riding to zero."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            moonbag=MoonbagConfig(percentage=50, stop_loss=None),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.moonbag_stop_price is None


class TestExitManagerCheckConditions:
    """Tests for exit condition checking."""

    def test_stop_loss_triggered(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test stop loss detection."""
        manager = ExitManager()

        # Price at stop loss level
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0005,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.STOP_LOSS
        assert result.sell_percentage == 100
        assert result.is_full_exit is True

    def test_stop_loss_below_threshold(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test stop loss triggered below threshold."""
        manager = ExitManager()

        # Price below stop loss
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0003,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.STOP_LOSS

    def test_take_profit_triggered(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test take profit detection."""
        manager = ExitManager()

        # Price at first TP level
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.002,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TAKE_PROFIT
        assert result.level is not None
        assert result.level.level_type == "take_profit_1"
        assert result.is_full_exit is False

    def test_take_profit_above_level(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test take profit triggered above level."""
        manager = ExitManager()

        # Price above first TP level
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0025,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TAKE_PROFIT
        assert result.level.level_type == "take_profit_1"

    def test_no_exit_between_levels(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test no exit when price is between levels."""
        manager = ExitManager()

        # Price between entry and first TP
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0015,
            strategy=strategy,
        )

        assert result.should_exit is False

    def test_no_exit_at_entry_price(
        self, position_with_levels: Position, strategy: ExitStrategy
    ) -> None:
        """Test no exit at entry price."""
        manager = ExitManager()

        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.001,
            strategy=strategy,
        )

        assert result.should_exit is False

    def test_moonbag_not_sold_on_stop_loss(
        self, position_with_levels: Position
    ) -> None:
        """Test moonbag ignores normal stop loss."""
        position_with_levels.is_moonbag = True
        position_with_levels.levels.moonbag_stop_price = None  # Ride to zero

        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=None),
        )

        manager = ExitManager()

        # Price at stop loss
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0005,
            strategy=strategy,
        )

        assert result.should_exit is False  # Moonbag rides to zero

    def test_moonbag_sold_at_moonbag_stop(
        self, position_with_levels: Position
    ) -> None:
        """Test moonbag sold when moonbag stop hit."""
        position_with_levels.is_moonbag = True
        position_with_levels.levels.moonbag_stop_price = 0.0002  # -80%

        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=0.8),
        )

        manager = ExitManager()

        # Price at moonbag stop
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0001,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.MOONBAG_STOP

    def test_position_without_levels(self, strategy: ExitStrategy) -> None:
        """Test handling position without calculated levels."""
        position = Position(
            id="test-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            levels=None,  # No levels
        )

        manager = ExitManager()

        result = manager.check_exit_conditions(
            position,
            current_price=0.0001,
            strategy=strategy,
        )

        assert result.should_exit is False


class TestTrailingStopRecalculation:
    """Tests for trailing stop updates."""

    def test_trailing_stop_not_activated_below_threshold(self) -> None:
        """Test trailing stop not active below activation price."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # Price below activation (2x)
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.0015, strategy=strategy
        )

        assert levels.trailing_stop_current_price is None

    def test_trailing_stop_activates(self) -> None:
        """Test trailing stop activation at threshold."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # Price reaches activation (2x)
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.002, strategy=strategy
        )

        # Trailing stop should be 30% below 0.002 = 0.0014
        assert levels.trailing_stop_current_price == pytest.approx(0.0014, rel=0.01)

    def test_trailing_stop_moves_up(self) -> None:
        """Test trailing stop moves up with price."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # First activation
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.002, strategy=strategy
        )
        first_trailing = levels.trailing_stop_current_price

        # Price goes higher
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.003, strategy=strategy
        )

        # Trailing stop should have moved up
        assert levels.trailing_stop_current_price > first_trailing
        # Should be 30% below 0.003 = 0.0021
        assert levels.trailing_stop_current_price == pytest.approx(0.0021, rel=0.01)

    def test_trailing_stop_does_not_move_down(self) -> None:
        """Test trailing stop does not move down when price drops."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # Activate at 3x
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.003, strategy=strategy
        )
        high_trailing = levels.trailing_stop_current_price

        # Price drops but still above trailing
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.0025, strategy=strategy
        )

        # Trailing stop should stay the same
        assert levels.trailing_stop_current_price == high_trailing

    def test_trailing_stop_disabled(self) -> None:
        """Test trailing stop not updated when disabled."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(enabled=False),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.003, strategy=strategy
        )

        assert levels.trailing_stop_current_price is None


class TestTrailingStopTrigger:
    """Tests for trailing stop trigger conditions."""

    def test_trailing_stop_triggered(self) -> None:
        """Test trailing stop exit condition."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            trailing_stop_activation_price=0.002,
            trailing_stop_current_price=0.0021,  # Trailing stop set
        )

        position = Position(
            id="test-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            levels=levels,
        )

        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
            moonbag=MoonbagConfig(percentage=0),
        )

        manager = ExitManager()

        # Price drops below trailing stop
        result = manager.check_exit_conditions(
            position,
            current_price=0.002,  # Below 0.0021 trailing stop
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TRAILING_STOP
        assert result.sell_percentage == 100  # No moonbag

    def test_trailing_stop_with_moonbag(self) -> None:
        """Test trailing stop sells non-moonbag portion only."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            trailing_stop_activation_price=0.002,
            trailing_stop_current_price=0.0021,
        )

        position = Position(
            id="test-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            levels=levels,
        )

        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
            moonbag=MoonbagConfig(percentage=20),  # 20% moonbag
        )

        manager = ExitManager()

        result = manager.check_exit_conditions(
            position,
            current_price=0.002,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TRAILING_STOP
        assert result.sell_percentage == 80  # 100 - 20% moonbag
        assert result.is_full_exit is False  # Moonbag remains

    def test_stop_loss_takes_precedence_before_trailing_activation(self) -> None:
        """Test regular stop-loss applies when trailing stop not yet activated."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            trailing_stop_activation_price=0.002,  # Not yet reached
            trailing_stop_current_price=None,
        )

        position = Position(
            id="test-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            levels=levels,
        )

        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
            moonbag=MoonbagConfig(percentage=0),
        )

        manager = ExitManager()

        # Price drops to stop-loss before trailing activation
        result = manager.check_exit_conditions(
            position,
            current_price=0.0005,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.STOP_LOSS  # Not trailing stop
        assert result.is_full_exit is True

    def test_trailing_stop_not_triggered_above_level(self) -> None:
        """Test trailing stop not triggered when price is above level."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            trailing_stop_activation_price=0.002,
            trailing_stop_current_price=0.0021,
        )

        position = Position(
            id="test-position",
            signal_id="test-signal",
            token_address="TokenAddress123456789012345678901234567890123",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=0.1,
            entry_amount_tokens=100,
            current_amount_tokens=100,
            exit_strategy_id="test-strategy",
            conviction_tier="standard",
            levels=levels,
        )

        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
            moonbag=MoonbagConfig(percentage=0),
        )

        manager = ExitManager()

        # Price above trailing stop level
        result = manager.check_exit_conditions(
            position,
            current_price=0.0025,  # Above 0.0021
            strategy=strategy,
        )

        assert result.should_exit is False


class TestPositionLevelsProperties:
    """Tests for PositionLevels computed properties."""

    def test_next_take_profit_returns_first_untriggered(self) -> None:
        """Test next_take_profit returns first un-triggered level."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            take_profit_levels=[
                CalculatedLevel(
                    level_type="take_profit_1",
                    trigger_price=0.002,
                    sell_percentage=50,
                    is_triggered=True,  # Already triggered
                ),
                CalculatedLevel(
                    level_type="take_profit_2",
                    trigger_price=0.003,
                    sell_percentage=100,
                    is_triggered=False,
                ),
            ],
        )

        assert levels.next_take_profit is not None
        assert levels.next_take_profit.level_type == "take_profit_2"

    def test_next_take_profit_returns_none_when_all_triggered(self) -> None:
        """Test next_take_profit returns None when all triggered."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            take_profit_levels=[
                CalculatedLevel(
                    level_type="take_profit_1",
                    trigger_price=0.002,
                    sell_percentage=50,
                    is_triggered=True,
                ),
                CalculatedLevel(
                    level_type="take_profit_2",
                    trigger_price=0.003,
                    sell_percentage=100,
                    is_triggered=True,
                ),
            ],
        )

        assert levels.next_take_profit is None
        assert levels.all_take_profits_hit is True

    def test_all_take_profits_hit_false_when_some_remain(self) -> None:
        """Test all_take_profits_hit is False when some remain."""
        levels = PositionLevels(
            entry_price=0.001,
            stop_loss_price=0.0005,
            take_profit_levels=[
                CalculatedLevel(
                    level_type="take_profit_1",
                    trigger_price=0.002,
                    sell_percentage=50,
                    is_triggered=True,
                ),
                CalculatedLevel(
                    level_type="take_profit_2",
                    trigger_price=0.003,
                    sell_percentage=100,
                    is_triggered=False,
                ),
            ],
        )

        assert levels.all_take_profits_hit is False
