"""Unit tests for simplified threshold checker service.

Epic 14 Simplification: Tests updated for single-threshold model.
- Single threshold (0.65) instead of dual HIGH/STANDARD thresholds
- Token safety is handled in SignalScorer as binary gate
- position_multiplier equals cluster_boost when passing
"""

import pytest

from walltrack.models.scoring import ScoredSignal, ScoringConfig
from walltrack.services.scoring.threshold_checker import (
    ThresholdChecker,
    ThresholdResult,
    get_checker,
    reset_checker,
)


@pytest.fixture
def sample_scored_signal() -> ScoredSignal:
    """Sample scored signal that passed token safety gate."""
    return ScoredSignal(
        tx_signature="sig123456789",
        wallet_address="Wallet12345678901234567890123456789012",
        token_address="Token123456789012345678901234567890123",
        direction="buy",
        final_score=0.80,
        wallet_score=0.70,
        cluster_boost=1.2,
        token_safe=True,
        is_leader=False,
        cluster_id="cluster-1",
        should_trade=True,
        position_multiplier=1.2,
        explanation="Wallet: 0.70 | Cluster: 1.2x | Final: 0.80 | TRADE",
    )


@pytest.fixture(autouse=True)
def reset_checker_fixture():
    """Reset checker singleton before each test."""
    reset_checker()
    yield
    reset_checker()


class TestThresholdCheckerBasic:
    """Basic threshold check tests."""

    def test_above_threshold_passes(self, sample_scored_signal: ScoredSignal):
        """Test signal above threshold passes."""
        sample_scored_signal.final_score = 0.75
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert isinstance(result, ThresholdResult)
        assert result.passed is True
        assert result.score == 0.75
        assert result.threshold == 0.65

    def test_below_threshold_fails(self, sample_scored_signal: ScoredSignal):
        """Test signal below threshold fails."""
        sample_scored_signal.final_score = 0.50
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.score == 0.50

    def test_exactly_at_threshold_passes(self, sample_scored_signal: ScoredSignal):
        """Test signal exactly at threshold passes."""
        sample_scored_signal.final_score = 0.65
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is True

    def test_just_below_threshold_fails(self, sample_scored_signal: ScoredSignal):
        """Test signal just below threshold fails."""
        sample_scored_signal.final_score = 0.6499
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False


class TestTokenSafetyIntegration:
    """Tests for token safety gate integration."""

    def test_unsafe_token_fails_immediately(self, sample_scored_signal: ScoredSignal):
        """Test that unsafe token fails even with high score."""
        sample_scored_signal.final_score = 0.95
        sample_scored_signal.token_safe = False
        sample_scored_signal.token_reject_reason = "honeypot"
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.score == 0.0

    def test_safe_token_uses_score(self, sample_scored_signal: ScoredSignal):
        """Test that safe token is evaluated by score."""
        sample_scored_signal.final_score = 0.70
        sample_scored_signal.token_safe = True
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is True
        assert result.score == 0.70


class TestPositionMultiplier:
    """Tests for position multiplier calculation."""

    def test_multiplier_equals_boost_when_passing(
        self, sample_scored_signal: ScoredSignal
    ):
        """Test position multiplier equals cluster_boost when passing."""
        sample_scored_signal.final_score = 0.80
        sample_scored_signal.cluster_boost = 1.5
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is True
        assert result.position_multiplier == 1.5

    def test_multiplier_one_when_failing(self, sample_scored_signal: ScoredSignal):
        """Test position multiplier is 1.0 when failing."""
        sample_scored_signal.final_score = 0.50
        sample_scored_signal.cluster_boost = 1.8
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.position_multiplier == 1.0

    def test_high_boost_preserved(self, sample_scored_signal: ScoredSignal):
        """Test high cluster boost is preserved."""
        sample_scored_signal.final_score = 0.70
        sample_scored_signal.cluster_boost = 1.8
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.position_multiplier == 1.8

    def test_no_boost_gives_one(self, sample_scored_signal: ScoredSignal):
        """Test no cluster boost gives multiplier of 1.0."""
        sample_scored_signal.final_score = 0.70
        sample_scored_signal.cluster_boost = 1.0
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.position_multiplier == 1.0


class TestCustomThreshold:
    """Tests for custom threshold configuration."""

    def test_custom_threshold(self, sample_scored_signal: ScoredSignal):
        """Test using custom threshold value."""
        config = ScoringConfig(trade_threshold=0.80)
        checker = ThresholdChecker(config)

        sample_scored_signal.final_score = 0.75
        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.threshold == 0.80

    def test_low_threshold(self, sample_scored_signal: ScoredSignal):
        """Test using low threshold value."""
        config = ScoringConfig(trade_threshold=0.50)
        checker = ThresholdChecker(config)

        sample_scored_signal.final_score = 0.55
        result = checker.check(sample_scored_signal)

        assert result.passed is True
        assert result.threshold == 0.50

    def test_config_update(self, sample_scored_signal: ScoredSignal):
        """Test threshold config hot-reload."""
        checker = ThresholdChecker()

        # Initially below default threshold 0.65
        sample_scored_signal.final_score = 0.60
        result1 = checker.check(sample_scored_signal)
        assert result1.passed is False

        # Update to lower threshold
        new_config = ScoringConfig(trade_threshold=0.50)
        checker.update_config(new_config)

        # Now above new threshold
        result2 = checker.check(sample_scored_signal)
        assert result2.passed is True
        assert result2.threshold == 0.50


class TestThresholdResult:
    """Tests for ThresholdResult class."""

    def test_result_attributes(self, sample_scored_signal: ScoredSignal):
        """Test ThresholdResult has correct attributes."""
        sample_scored_signal.final_score = 0.80
        sample_scored_signal.cluster_boost = 1.3
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert hasattr(result, "passed")
        assert hasattr(result, "score")
        assert hasattr(result, "threshold")
        assert hasattr(result, "position_multiplier")
        assert result.passed is True
        assert result.score == 0.80
        assert result.threshold == 0.65
        assert result.position_multiplier == 1.3


class TestCheckerSingleton:
    """Tests for checker singleton pattern."""

    def test_get_checker_returns_same_instance(self):
        """Test that get_checker returns same instance."""
        checker1 = get_checker()
        checker2 = get_checker()

        assert checker1 is checker2

    def test_reset_checker_clears_instance(self):
        """Test that reset_checker clears the instance."""
        checker1 = get_checker()
        reset_checker()
        checker2 = get_checker()

        assert checker1 is not checker2

    def test_get_checker_with_config(self):
        """Test get_checker with custom config."""
        config = ScoringConfig(trade_threshold=0.80)
        checker = get_checker(config)

        assert checker.config.trade_threshold == 0.80


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_score(self, sample_scored_signal: ScoredSignal):
        """Test handling of zero score."""
        sample_scored_signal.final_score = 0.0
        sample_scored_signal.token_safe = True
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.score == 0.0

    def test_perfect_score(self, sample_scored_signal: ScoredSignal):
        """Test handling of perfect score."""
        sample_scored_signal.final_score = 1.0
        sample_scored_signal.cluster_boost = 1.0
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is True
        assert result.score == 1.0

    def test_high_boost_with_unsafe_token(self, sample_scored_signal: ScoredSignal):
        """Test that high boost doesn't bypass token safety."""
        sample_scored_signal.final_score = 0.0
        sample_scored_signal.token_safe = False
        sample_scored_signal.cluster_boost = 1.8
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.passed is False
        assert result.position_multiplier == 1.0


class TestScoringConfigDefaults:
    """Tests for ScoringConfig defaults."""

    def test_default_threshold(self):
        """Test default threshold is 0.65."""
        config = ScoringConfig()
        assert config.trade_threshold == 0.65

    def test_checker_uses_default_config(self):
        """Test checker uses default config when none provided."""
        checker = ThresholdChecker()
        assert checker.config.trade_threshold == 0.65
