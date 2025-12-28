"""Unit tests for score-based strategy assignment."""

import pytest

from walltrack.models.strategy_assignment import (
    AssignmentSource,
    ManualOverride,
    ScoreRange,
    StrategyMappingConfig,
)
from walltrack.services.execution.strategy_assigner import StrategyAssigner


@pytest.fixture
def assigner() -> StrategyAssigner:
    """Create strategy assigner with default config."""
    return StrategyAssigner()


@pytest.fixture
def custom_config() -> StrategyMappingConfig:
    """Create custom mapping configuration."""
    return StrategyMappingConfig(
        mappings=[
            ScoreRange(min_score=0.80, max_score=1.00, strategy_id="custom-aggressive"),
        ],
        default_strategy_id="custom-conservative",
    )


class TestStrategyMappingConfig:
    """Tests for strategy mapping configuration."""

    def test_default_mappings(self) -> None:
        """Test default mapping configuration."""
        config = StrategyMappingConfig()

        assert len(config.mappings) == 3
        assert config.default_strategy_id == "preset-balanced"
        assert config.enabled is True

    def test_get_strategy_high_score(self) -> None:
        """Test getting strategy for high conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(0.95)

        assert strategy_id == "preset-diamond-hands"
        assert is_default is False

    def test_get_strategy_medium_score(self) -> None:
        """Test getting strategy for medium conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(0.85)

        assert strategy_id == "preset-moonbag-aggressive"
        assert is_default is False

    def test_get_strategy_standard_score(self) -> None:
        """Test getting strategy for standard conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(0.75)

        assert strategy_id == "preset-balanced"
        assert is_default is False

    def test_get_strategy_low_score_fallback(self) -> None:
        """Test default fallback for low scores."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(0.50)

        assert strategy_id == "preset-balanced"  # Default
        assert is_default is True

    def test_get_strategy_disabled(self) -> None:
        """Test always returns default when disabled."""
        config = StrategyMappingConfig(enabled=False)

        strategy_id, is_default = config.get_strategy_for_score(0.95)

        assert strategy_id == "preset-balanced"  # Default
        assert is_default is True

    def test_custom_mappings(self) -> None:
        """Test custom mapping configuration."""
        config = StrategyMappingConfig(
            mappings=[
                ScoreRange(
                    min_score=0.80,
                    max_score=1.00,
                    strategy_id="custom-aggressive",
                ),
            ],
            default_strategy_id="custom-conservative",
        )

        # High score gets custom aggressive
        strategy_id, is_default = config.get_strategy_for_score(0.90)
        assert strategy_id == "custom-aggressive"
        assert is_default is False

        # Low score gets custom conservative
        strategy_id, is_default = config.get_strategy_for_score(0.50)
        assert strategy_id == "custom-conservative"
        assert is_default is True


class TestScoreRange:
    """Tests for score range."""

    def test_contains_within_range(self) -> None:
        """Test score within range."""
        range_ = ScoreRange(
            min_score=0.80,
            max_score=0.89,
            strategy_id="test-strategy",
        )

        assert range_.contains(0.85) is True

    def test_contains_at_min_boundary(self) -> None:
        """Test score at minimum boundary."""
        range_ = ScoreRange(
            min_score=0.80,
            max_score=0.89,
            strategy_id="test-strategy",
        )

        assert range_.contains(0.80) is True
        assert range_.contains(0.79) is False

    def test_contains_at_max_boundary(self) -> None:
        """Test score at maximum boundary."""
        range_ = ScoreRange(
            min_score=0.80,
            max_score=0.89,
            strategy_id="test-strategy",
        )

        assert range_.contains(0.89) is True
        assert range_.contains(0.90) is False

    def test_contains_outside_range(self) -> None:
        """Test score outside range."""
        range_ = ScoreRange(
            min_score=0.80,
            max_score=0.89,
            strategy_id="test-strategy",
        )

        assert range_.contains(0.70) is False
        assert range_.contains(0.95) is False


class TestStrategyAssigner:
    """Tests for strategy assigner service."""

    def test_assign_score_based_high(self, assigner: StrategyAssigner) -> None:
        """Test score-based strategy assignment for high score."""
        assignment = assigner.assign_strategy(
            position_id="pos-001",
            signal_id="sig-001",
            signal_score=0.92,
        )

        assert assignment.position_id == "pos-001"
        assert assignment.signal_score == 0.92
        assert assignment.assigned_strategy_id == "preset-diamond-hands"
        assert assignment.assignment_source == AssignmentSource.SCORE_BASED

    def test_assign_score_based_medium(self, assigner: StrategyAssigner) -> None:
        """Test score-based strategy assignment for medium score."""
        assignment = assigner.assign_strategy(
            position_id="pos-002",
            signal_id="sig-002",
            signal_score=0.83,
        )

        assert assignment.assigned_strategy_id == "preset-moonbag-aggressive"
        assert assignment.assignment_source == AssignmentSource.SCORE_BASED

    def test_assign_default_fallback(self, assigner: StrategyAssigner) -> None:
        """Test default fallback for unmatched scores."""
        assignment = assigner.assign_strategy(
            position_id="pos-003",
            signal_id="sig-003",
            signal_score=0.50,
        )

        assert assignment.assigned_strategy_id == "preset-balanced"
        assert assignment.assignment_source == AssignmentSource.DEFAULT_FALLBACK

    def test_manual_override(self, assigner: StrategyAssigner) -> None:
        """Test manual strategy override."""
        override = ManualOverride(
            position_id="pos-004",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
            reason="Customer requested conservative approach",
        )

        log = assigner.apply_manual_override(override, "preset-balanced")

        assert log.position_id == "pos-004"
        assert log.previous_strategy_id == "preset-balanced"
        assert log.new_strategy_id == "preset-conservative"
        assert log.override_by == "operator-1"

    def test_override_takes_precedence(self, assigner: StrategyAssigner) -> None:
        """Test manual override takes precedence over score-based."""
        # First apply override
        override = ManualOverride(
            position_id="pos-005",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
        )
        assigner.apply_manual_override(override, "preset-balanced")

        # Now assign - should use override
        assignment = assigner.assign_strategy(
            position_id="pos-005",
            signal_id="sig-005",
            signal_score=0.95,  # Would be diamond hands without override
        )

        assert assignment.assigned_strategy_id == "preset-conservative"
        assert assignment.assignment_source == AssignmentSource.MANUAL_OVERRIDE

    def test_clear_override(self, assigner: StrategyAssigner) -> None:
        """Test clearing override."""
        # Apply override
        override = ManualOverride(
            position_id="pos-006",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
        )
        assigner.apply_manual_override(override, "preset-balanced")

        assert assigner.has_override("pos-006") is True

        # Clear it
        assigner.clear_override("pos-006")

        assert assigner.has_override("pos-006") is False

        # Now assign - should use score-based
        assignment = assigner.assign_strategy(
            position_id="pos-006",
            signal_id="sig-006",
            signal_score=0.95,
        )

        assert assignment.assigned_strategy_id == "preset-diamond-hands"
        assert assignment.assignment_source == AssignmentSource.SCORE_BASED

    def test_set_mapping_config(
        self, assigner: StrategyAssigner, custom_config: StrategyMappingConfig
    ) -> None:
        """Test updating mapping configuration."""
        assigner.set_mapping_config(custom_config)

        # High score gets custom strategy
        assignment = assigner.assign_strategy(
            position_id="pos-007",
            signal_id="sig-007",
            signal_score=0.90,
        )

        assert assignment.assigned_strategy_id == "custom-aggressive"

    def test_get_override_logs(self, assigner: StrategyAssigner) -> None:
        """Test getting override logs."""
        # Apply some overrides
        for i in range(3):
            override = ManualOverride(
                position_id=f"pos-{i:03d}",
                new_strategy_id="preset-conservative",
                override_by="operator-1",
            )
            assigner.apply_manual_override(override, "preset-balanced")

        # Get all logs
        all_logs = assigner.get_override_logs()
        assert len(all_logs) == 3

        # Get logs for specific position
        pos_logs = assigner.get_override_logs("pos-001")
        assert len(pos_logs) == 1
        assert pos_logs[0].position_id == "pos-001"

    def test_preview_assignment(self, assigner: StrategyAssigner) -> None:
        """Test previewing strategy assignment."""
        # High score
        strategy_id, is_default, source = assigner.preview_assignment(0.95)
        assert strategy_id == "preset-diamond-hands"
        assert is_default is False
        assert "0.90" in source

        # Low score (fallback)
        strategy_id, is_default, source = assigner.preview_assignment(0.50)
        assert strategy_id == "preset-balanced"
        assert is_default is True
        assert "fallback" in source

    def test_preview_assignment_disabled(self) -> None:
        """Test previewing when score-based is disabled."""
        config = StrategyMappingConfig(enabled=False)
        assigner = StrategyAssigner(mapping_config=config)

        strategy_id, is_default, source = assigner.preview_assignment(0.95)

        assert strategy_id == "preset-balanced"
        assert is_default is True
        assert "disabled" in source


class TestOverlappingRanges:
    """Tests for overlapping score ranges."""

    def test_first_matching_range_wins(self) -> None:
        """Test that first matching range is used when ranges overlap."""
        config = StrategyMappingConfig(
            mappings=[
                ScoreRange(
                    min_score=0.85,
                    max_score=1.00,
                    strategy_id="strategy-a",
                ),
                ScoreRange(
                    min_score=0.80,
                    max_score=0.90,
                    strategy_id="strategy-b",
                ),
            ]
        )

        # 0.88 matches both - first wins
        strategy_id, is_default = config.get_strategy_for_score(0.88)

        assert strategy_id == "strategy-a"
        assert is_default is False
