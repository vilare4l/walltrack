"""Unit tests for exit strategy models."""

import pytest
from pydantic import ValidationError

from walltrack.constants.exit_presets import (
    BALANCED_STRATEGY,
    CONSERVATIVE_STRATEGY,
    DEFAULT_PRESETS,
    get_preset_by_name,
)
from walltrack.models.exit_strategy import (
    ExitStrategy,
    MoonbagConfig,
    TakeProfitLevel,
    TimeRulesConfig,
    TrailingStopConfig,
)


class TestTakeProfitLevel:
    """Tests for TakeProfitLevel model."""

    def test_valid_take_profit(self) -> None:
        """Test valid take profit level."""
        tp = TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50)
        assert tp.trigger_multiplier == 2.0
        assert tp.sell_percentage == 50

    def test_multiplier_must_be_greater_than_one(self) -> None:
        """Test multiplier validation."""
        with pytest.raises(ValidationError):
            TakeProfitLevel(trigger_multiplier=0.8, sell_percentage=50)

    def test_sell_percentage_range(self) -> None:
        """Test sell percentage must be 0-100."""
        with pytest.raises(ValidationError):
            TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=150)


class TestTrailingStopConfig:
    """Tests for TrailingStopConfig model."""

    def test_default_disabled(self) -> None:
        """Test trailing stop disabled by default."""
        config = TrailingStopConfig()
        assert config.enabled is False

    def test_valid_config(self) -> None:
        """Test valid trailing stop config."""
        config = TrailingStopConfig(
            enabled=True,
            activation_multiplier=2.0,
            distance_percentage=30,
        )
        assert config.enabled is True
        assert config.activation_multiplier == 2.0


class TestMoonbagConfig:
    """Tests for MoonbagConfig model."""

    def test_no_moonbag_by_default(self) -> None:
        """Test no moonbag by default."""
        config = MoonbagConfig()
        assert config.percentage == 0
        assert config.has_moonbag is False

    def test_ride_to_zero(self) -> None:
        """Test ride to zero detection."""
        config = MoonbagConfig(percentage=50, stop_loss=None)
        assert config.has_moonbag is True
        assert config.ride_to_zero is True

    def test_moonbag_with_stop(self) -> None:
        """Test moonbag with stop loss."""
        config = MoonbagConfig(percentage=50, stop_loss=0.3)
        assert config.has_moonbag is True
        assert config.ride_to_zero is False


class TestExitStrategy:
    """Tests for ExitStrategy model."""

    def test_basic_strategy(self) -> None:
        """Test basic strategy creation."""
        strategy = ExitStrategy(
            name="Test Strategy",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            ],
        )
        assert strategy.name == "Test Strategy"
        assert len(strategy.take_profit_levels) == 1

    def test_take_profits_auto_sorted(self) -> None:
        """Test take profit levels are auto-sorted."""
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            ],
        )
        assert strategy.take_profit_levels[0].trigger_multiplier == 2.0
        assert strategy.take_profit_levels[1].trigger_multiplier == 3.0

    def test_properties(self) -> None:
        """Test strategy property checks."""
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=100),
            ],
            trailing_stop=TrailingStopConfig(
                enabled=True, activation_multiplier=2.0, distance_percentage=30
            ),
            time_rules=TimeRulesConfig(max_hold_hours=24),
        )

        assert strategy.has_take_profits is True
        assert strategy.has_trailing_stop is True
        assert strategy.has_time_limits is True


class TestDefaultPresets:
    """Tests for default preset strategies."""

    def test_five_presets_defined(self) -> None:
        """Test exactly five presets are defined."""
        assert len(DEFAULT_PRESETS) == 5

    def test_all_presets_valid(self) -> None:
        """Test all presets pass validation."""
        for preset in DEFAULT_PRESETS:
            assert preset.id.startswith("preset-")
            assert preset.is_default is True
            assert preset.name is not None

    def test_conservative_preset(self) -> None:
        """Test conservative preset configuration."""
        strategy = CONSERVATIVE_STRATEGY
        assert strategy.name == "Conservative"
        assert len(strategy.take_profit_levels) == 2
        assert strategy.trailing_stop.enabled is False
        assert strategy.moonbag.percentage == 0

    def test_balanced_preset(self) -> None:
        """Test balanced preset configuration."""
        strategy = BALANCED_STRATEGY
        assert strategy.name == "Balanced"
        assert strategy.trailing_stop.enabled is True
        assert strategy.moonbag.percentage == 34

    def test_get_preset_by_name(self) -> None:
        """Test preset lookup by name."""
        strategy = get_preset_by_name("Conservative")
        assert strategy is not None
        assert strategy.name == "Conservative"

    def test_get_preset_by_name_case_insensitive(self) -> None:
        """Test preset lookup is case insensitive."""
        strategy = get_preset_by_name("BALANCED")
        assert strategy is not None
        assert strategy.name == "Balanced"

    def test_get_preset_by_name_not_found(self) -> None:
        """Test preset lookup returns None for unknown."""
        strategy = get_preset_by_name("Unknown")
        assert strategy is None
