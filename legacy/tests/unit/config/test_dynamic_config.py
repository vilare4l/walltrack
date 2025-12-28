"""Unit tests for dynamic configuration models.

Test ID: 1.2-UNIT-002
"""

import pytest
from pydantic import ValidationError

from walltrack.data.models.config import DynamicConfig, ScoringWeights


class TestScoringWeights:
    """Tests for ScoringWeights model."""

    def test_default_weights_sum_to_one(self) -> None:
        """Default weights should sum to 1.0."""
        weights = ScoringWeights()
        assert weights.validate_sum() is True

    def test_validate_sum_with_valid_weights(self) -> None:
        """Weights that sum to 1.0 should validate."""
        weights = ScoringWeights(
            wallet=0.25,
            cluster=0.25,
            token=0.25,
            context=0.25,
        )
        assert weights.validate_sum() is True

    def test_validate_sum_with_invalid_weights(self) -> None:
        """Weights that don't sum to 1.0 should fail validation."""
        weights = ScoringWeights(
            wallet=0.50,
            cluster=0.50,
            token=0.50,
            context=0.50,
        )
        assert weights.validate_sum() is False

    def test_validate_sum_tolerance(self) -> None:
        """Validation should allow small floating point differences."""
        # Sum is 0.999 which should pass within tolerance
        weights = ScoringWeights(
            wallet=0.30,
            cluster=0.249,
            token=0.25,
            context=0.20,
        )
        # This should be close enough to 1.0
        assert weights.validate_sum() is True

    def test_weight_range_validation(self) -> None:
        """Each weight must be between 0 and 1."""
        with pytest.raises(ValidationError):
            ScoringWeights(wallet=-0.1)

        with pytest.raises(ValidationError):
            ScoringWeights(wallet=1.1)


class TestDynamicConfig:
    """Tests for DynamicConfig model."""

    def test_default_config_is_valid(self) -> None:
        """Default configuration should be valid."""
        config = DynamicConfig()
        assert config.score_threshold == 0.70
        assert config.high_conviction_threshold == 0.85
        assert config.max_concurrent_positions == 5

    def test_scoring_weights_nested(self) -> None:
        """Scoring weights should be properly nested."""
        config = DynamicConfig()
        assert isinstance(config.scoring_weights, ScoringWeights)
        assert config.scoring_weights.wallet == 0.30

    def test_threshold_range_validation(self) -> None:
        """Threshold values must be within valid ranges."""
        # Valid thresholds
        DynamicConfig(score_threshold=0.0)
        DynamicConfig(score_threshold=1.0)

        # Invalid thresholds
        with pytest.raises(ValidationError):
            DynamicConfig(score_threshold=-0.1)

        with pytest.raises(ValidationError):
            DynamicConfig(score_threshold=1.5)

    def test_max_positions_range(self) -> None:
        """Max concurrent positions must be within range."""
        DynamicConfig(max_concurrent_positions=1)
        DynamicConfig(max_concurrent_positions=20)

        with pytest.raises(ValidationError):
            DynamicConfig(max_concurrent_positions=0)

        with pytest.raises(ValidationError):
            DynamicConfig(max_concurrent_positions=50)

    def test_config_from_dict(self) -> None:
        """Config should be creatable from dictionary."""
        data = {
            "scoring_weights": {
                "wallet": 0.40,
                "cluster": 0.30,
                "token": 0.20,
                "context": 0.10,
            },
            "score_threshold": 0.75,
            "max_concurrent_positions": 10,
        }
        config = DynamicConfig(**data)
        assert config.scoring_weights.wallet == 0.40
        assert config.score_threshold == 0.75
        assert config.max_concurrent_positions == 10
