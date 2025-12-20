"""Unit tests for exit strategies dashboard component."""

from walltrack.constants.exit_presets import DEFAULT_PRESETS
from walltrack.models.exit_strategy import (
    ExitStrategy,
    MoonbagConfig,
    TakeProfitLevel,
    TimeRulesConfig,
    TrailingStopConfig,
)
from walltrack.ui.components.exit_strategies import (
    format_strategy_detail,
    format_strategy_summary,
    get_all_strategies_df,
    get_preset_choices,
    get_strategy_by_id,
)


class TestFormatStrategySummary:
    """Tests for strategy summary formatting."""

    def test_format_basic_strategy(self) -> None:
        """Test formatting a basic strategy."""
        strategy = ExitStrategy(
            id="test-123",
            name="Test Strategy",
            stop_loss=0.5,
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),
            ],
            trailing_stop=TrailingStopConfig(enabled=False),
        )

        summary = format_strategy_summary(strategy)

        assert summary["Name"] == "Test Strategy"
        assert summary["Stop Loss"] == "50%"
        assert "2x→50%" in summary["Take Profits"]
        assert "3x→50%" in summary["Take Profits"]
        assert summary["Trailing"] == "Off"

    def test_format_with_trailing_stop(self) -> None:
        """Test formatting strategy with trailing stop."""
        strategy = ExitStrategy(
            id="test-trailing",
            name="Trailing Test",
            stop_loss=0.3,
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.5,
                distance_percentage=25,
            ),
        )

        summary = format_strategy_summary(strategy)

        assert "@2.5x" in summary["Trailing"]
        assert "25" in summary["Trailing"]

    def test_format_with_moonbag(self) -> None:
        """Test formatting strategy with moonbag."""
        strategy = ExitStrategy(
            id="test-moonbag",
            name="Moonbag Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=25, stop_loss=0.3),
        )

        summary = format_strategy_summary(strategy)

        assert "25" in summary["Moonbag"]
        assert "SL:30" in summary["Moonbag"]

    def test_format_moonbag_ride_to_zero(self) -> None:
        """Test formatting moonbag that rides to zero."""
        strategy = ExitStrategy(
            id="test-ride-zero",
            name="Ride Zero",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=None),
        )

        summary = format_strategy_summary(strategy)

        assert "ride to zero" in summary["Moonbag"]

    def test_format_no_moonbag(self) -> None:
        """Test formatting strategy without moonbag."""
        strategy = ExitStrategy(
            id="test-no-moonbag",
            name="No Moonbag",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=0),
        )

        summary = format_strategy_summary(strategy)

        assert summary["Moonbag"] == "None"

    def test_format_with_time_rules(self) -> None:
        """Test formatting strategy with time rules."""
        strategy = ExitStrategy(
            id="test-time",
            name="Time Rules",
            stop_loss=0.5,
            time_rules=TimeRulesConfig(
                max_hold_hours=48,
                stagnation_exit_enabled=True,
                stagnation_hours=12,
            ),
        )

        summary = format_strategy_summary(strategy)

        assert "Max:48h" in summary["Time Rules"]
        assert "Stag:12h" in summary["Time Rules"]

    def test_format_preset_vs_custom(self) -> None:
        """Test type field for preset vs custom."""
        preset = ExitStrategy(
            id="preset-test",
            name="Preset",
            stop_loss=0.5,
            is_default=True,
        )
        custom = ExitStrategy(
            id="custom-test",
            name="Custom",
            stop_loss=0.5,
            is_default=False,
        )

        assert format_strategy_summary(preset)["Type"] == "Preset"
        assert format_strategy_summary(custom)["Type"] == "Custom"


class TestFormatStrategyDetail:
    """Tests for strategy detail formatting."""

    def test_format_includes_header(self) -> None:
        """Test that detail includes name and ID."""
        strategy = ExitStrategy(
            id="test-detail",
            name="Detail Test",
            stop_loss=0.5,
        )

        detail = format_strategy_detail(strategy)

        assert "## Detail Test" in detail
        assert "`test-detail`" in detail

    def test_format_includes_description(self) -> None:
        """Test that detail includes description."""
        strategy = ExitStrategy(
            id="test-desc",
            name="Desc Test",
            description="A test strategy for testing",
            stop_loss=0.5,
        )

        detail = format_strategy_detail(strategy)

        assert "A test strategy for testing" in detail

    def test_format_includes_stop_loss(self) -> None:
        """Test that detail includes stop loss."""
        strategy = ExitStrategy(
            id="test-sl",
            name="SL Test",
            stop_loss=0.3,
        )

        detail = format_strategy_detail(strategy)

        assert "30%" in detail
        assert "Stop Loss" in detail

    def test_format_includes_take_profits(self) -> None:
        """Test that detail includes take profit levels."""
        strategy = ExitStrategy(
            id="test-tp",
            name="TP Test",
            stop_loss=0.5,
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=33),
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),
            ],
        )

        detail = format_strategy_detail(strategy)

        assert "Take Profit" in detail
        assert "2.0x" in detail
        assert "33%" in detail
        assert "3.0x" in detail

    def test_format_trailing_enabled(self) -> None:
        """Test detail for enabled trailing stop."""
        strategy = ExitStrategy(
            id="test-trailing",
            name="Trailing Test",
            stop_loss=0.5,
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.5,
                distance_percentage=30,
            ),
        )

        detail = format_strategy_detail(strategy)

        assert "Trailing Stop" in detail
        assert "2.5x" in detail
        assert "30" in detail  # 30.0%

    def test_format_trailing_disabled(self) -> None:
        """Test detail for disabled trailing stop."""
        strategy = ExitStrategy(
            id="test-no-trailing",
            name="No Trailing",
            stop_loss=0.5,
            trailing_stop=TrailingStopConfig(enabled=False),
        )

        detail = format_strategy_detail(strategy)

        assert "Disabled" in detail

    def test_format_time_rules(self) -> None:
        """Test detail includes time rules."""
        strategy = ExitStrategy(
            id="test-time",
            name="Time Test",
            stop_loss=0.5,
            time_rules=TimeRulesConfig(
                max_hold_hours=72,
                stagnation_exit_enabled=True,
                stagnation_hours=24,
                stagnation_threshold_pct=5,
            ),
        )

        detail = format_strategy_detail(strategy)

        assert "Time Rules" in detail
        assert "72 hours" in detail
        assert "Stagnation" in detail
        assert "24h" in detail

    def test_format_moonbag_with_sl(self) -> None:
        """Test detail for moonbag with stop loss."""
        strategy = ExitStrategy(
            id="test-mb",
            name="Moonbag Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=30, stop_loss=0.4),
        )

        detail = format_strategy_detail(strategy)

        assert "Moonbag" in detail
        assert "30" in detail  # 30.0%
        assert "40%" in detail

    def test_format_moonbag_ride_to_zero(self) -> None:
        """Test detail for moonbag that rides to zero."""
        strategy = ExitStrategy(
            id="test-zero",
            name="Zero Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=None),
        )

        detail = format_strategy_detail(strategy)

        assert "Ride to Zero" in detail


class TestGetAllStrategiesDF:
    """Tests for getting strategies dataframe."""

    def test_returns_dataframe(self) -> None:
        """Test that function returns a DataFrame."""
        df = get_all_strategies_df()

        assert len(df) == len(DEFAULT_PRESETS)

    def test_contains_expected_columns(self) -> None:
        """Test that DataFrame has expected columns."""
        df = get_all_strategies_df()

        expected_columns = [
            "Name",
            "Stop Loss",
            "Take Profits",
            "Trailing",
            "Moonbag",
            "Time Rules",
            "Type",
        ]
        for col in expected_columns:
            assert col in df.columns

    def test_contains_preset_strategies(self) -> None:
        """Test that DataFrame contains preset strategies."""
        df = get_all_strategies_df()

        names = df["Name"].tolist()
        assert "Conservative" in names
        assert "Balanced" in names
        assert "Diamond Hands" in names


class TestGetStrategyById:
    """Tests for getting strategy by ID."""

    def test_get_existing_preset(self) -> None:
        """Test getting existing preset strategy."""
        strategy = get_strategy_by_id("preset-balanced")

        assert strategy is not None
        assert strategy.name == "Balanced"

    def test_get_nonexistent(self) -> None:
        """Test getting nonexistent strategy."""
        strategy = get_strategy_by_id("nonexistent-id")

        assert strategy is None

    def test_get_all_presets(self) -> None:
        """Test getting all preset strategies."""
        for preset in DEFAULT_PRESETS:
            strategy = get_strategy_by_id(preset.id)
            assert strategy is not None
            assert strategy.id == preset.id


class TestGetPresetChoices:
    """Tests for preset choices list."""

    def test_returns_list(self) -> None:
        """Test that function returns a list."""
        choices = get_preset_choices()

        assert isinstance(choices, list)
        assert len(choices) == len(DEFAULT_PRESETS)

    def test_contains_preset_ids(self) -> None:
        """Test that list contains preset IDs."""
        choices = get_preset_choices()

        assert "preset-conservative" in choices
        assert "preset-balanced" in choices
        assert "preset-moonbag-aggressive" in choices
        assert "preset-quick-flip" in choices
        assert "preset-diamond-hands" in choices
