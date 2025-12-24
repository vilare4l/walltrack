"""Tests for backtest scenario model."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestScenarioCategory:
    """Tests for ScenarioCategory enum."""

    def test_category_values(self) -> None:
        """Test all category enum values exist."""
        from walltrack.core.backtest.scenario import ScenarioCategory

        assert ScenarioCategory.CONSERVATIVE.value == "conservative"
        assert ScenarioCategory.MODERATE.value == "moderate"
        assert ScenarioCategory.AGGRESSIVE.value == "aggressive"
        assert ScenarioCategory.EXPERIMENTAL.value == "experimental"
        assert ScenarioCategory.CUSTOM.value == "custom"


class TestScenario:
    """Tests for Scenario model."""

    def test_scenario_creation(self) -> None:
        """Test creating a scenario with required fields."""
        from walltrack.core.backtest.scenario import Scenario

        scenario = Scenario(name="Test Scenario")

        assert scenario.name == "Test Scenario"
        assert scenario.score_threshold == Decimal("0.70")
        assert scenario.base_position_sol == Decimal("0.1")
        assert scenario.max_concurrent_positions == 5

    def test_scenario_with_custom_params(self) -> None:
        """Test scenario with custom parameters."""
        from walltrack.core.backtest.parameters import ScoringWeights
        from walltrack.core.backtest.scenario import Scenario, ScenarioCategory

        scenario = Scenario(
            name="Custom Scenario",
            description="A test scenario",
            category=ScenarioCategory.AGGRESSIVE,
            score_threshold=Decimal("0.80"),
            base_position_sol=Decimal("0.2"),
            max_concurrent_positions=10,
            scoring_weights=ScoringWeights(
                wallet_weight=Decimal("0.40"),
                cluster_weight=Decimal("0.20"),
                token_weight=Decimal("0.20"),
                context_weight=Decimal("0.20"),
            ),
        )

        assert scenario.category == ScenarioCategory.AGGRESSIVE
        assert scenario.score_threshold == Decimal("0.80")
        assert scenario.scoring_weights.wallet_weight == Decimal("0.40")

    def test_score_threshold_validation(self) -> None:
        """Test score threshold must be between 0 and 1."""
        from walltrack.core.backtest.scenario import Scenario

        with pytest.raises(ValueError):
            Scenario(name="Invalid", score_threshold=Decimal("1.5"))

        with pytest.raises(ValueError):
            Scenario(name="Invalid", score_threshold=Decimal("-0.1"))

    def test_max_positions_validation(self) -> None:
        """Test max concurrent positions validation."""
        from walltrack.core.backtest.scenario import Scenario

        with pytest.raises(ValueError):
            Scenario(name="Invalid", max_concurrent_positions=0)

        with pytest.raises(ValueError):
            Scenario(name="Invalid", max_concurrent_positions=100)

    def test_to_backtest_params(self) -> None:
        """Test converting scenario to backtest parameters."""
        from walltrack.core.backtest.scenario import Scenario

        scenario = Scenario(
            name="Test",
            score_threshold=Decimal("0.75"),
            base_position_sol=Decimal("0.15"),
        )

        params = scenario.to_backtest_params(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )

        assert params.score_threshold == Decimal("0.75")
        assert params.base_position_sol == Decimal("0.15")
        assert params.start_date == datetime(2024, 1, 1, tzinfo=UTC)
        assert params.end_date == datetime(2024, 6, 30, tzinfo=UTC)

    def test_to_json_and_from_json(self) -> None:
        """Test JSON export and import."""
        from walltrack.core.backtest.scenario import Scenario

        original = Scenario(
            name="Export Test",
            description="Testing export",
            score_threshold=Decimal("0.80"),
        )

        json_str = original.to_json()
        imported = Scenario.from_json(json_str)

        assert imported.name == original.name
        assert imported.description == original.description
        assert imported.score_threshold == original.score_threshold


class TestPresetScenarios:
    """Tests for preset scenarios."""

    def test_preset_scenarios_exist(self) -> None:
        """Test that preset scenarios are defined."""
        from walltrack.core.backtest.scenario import PRESET_SCENARIOS

        assert len(PRESET_SCENARIOS) == 5

    def test_preset_conservative(self) -> None:
        """Test conservative preset configuration."""
        from walltrack.core.backtest.scenario import PRESET_SCENARIOS, ScenarioCategory

        conservative = next(s for s in PRESET_SCENARIOS if s.name == "Conservative")

        assert conservative.category == ScenarioCategory.CONSERVATIVE
        assert conservative.score_threshold == Decimal("0.80")
        assert conservative.base_position_sol == Decimal("0.05")
        assert conservative.is_preset is True

    def test_preset_balanced(self) -> None:
        """Test balanced preset configuration."""
        from walltrack.core.backtest.scenario import PRESET_SCENARIOS, ScenarioCategory

        balanced = next(s for s in PRESET_SCENARIOS if s.name == "Balanced")

        assert balanced.category == ScenarioCategory.MODERATE
        assert balanced.score_threshold == Decimal("0.70")
        assert balanced.exit_strategy.trailing_stop_enabled is True

    def test_all_presets_are_valid(self) -> None:
        """Test all preset scenarios pass validation."""
        from walltrack.core.backtest.scenario import PRESET_SCENARIOS

        for preset in PRESET_SCENARIOS:
            assert preset.is_preset is True
            assert 0 <= preset.score_threshold <= 1
            assert 1 <= preset.max_concurrent_positions <= 50
            assert preset.scoring_weights.validate_weights() is True
