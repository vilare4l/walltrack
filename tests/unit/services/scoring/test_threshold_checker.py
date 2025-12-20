"""Unit tests for threshold checker service."""

import pytest

from walltrack.models.scoring import (
    ClusterScoreComponents,
    ContextScoreComponents,
    FactorScore,
    ScoreCategory,
    ScoredSignal,
    ScoringWeights,
    TokenScoreComponents,
    WalletScoreComponents,
)
from walltrack.models.threshold import (
    ConvictionTier,
    EligibilityStatus,
    ThresholdConfig,
)
from walltrack.models.token import TokenCharacteristics, TokenLiquidity
from walltrack.services.scoring.threshold_checker import (
    ThresholdChecker,
    reset_checker,
)


def create_factor_score(score: float = 0.8) -> FactorScore:
    """Create a factor score for testing."""
    return FactorScore(
        category=ScoreCategory.WALLET,
        score=score,
        weight=0.25,
        weighted_contribution=score * 0.25,
    )


@pytest.fixture
def sample_scored_signal() -> ScoredSignal:
    """Sample scored signal."""
    factor = create_factor_score(0.8)
    return ScoredSignal(
        tx_signature="sig123456789",
        wallet_address="Wallet12345678901234567890123456789012",
        token_address="Token123456789012345678901234567890123",
        direction="buy",
        final_score=0.80,
        wallet_score=factor,
        cluster_score=factor,
        token_score=factor,
        context_score=factor,
        wallet_components=WalletScoreComponents(),
        cluster_components=ClusterScoreComponents(),
        token_components=TokenScoreComponents(),
        context_components=ContextScoreComponents(),
        weights_used=ScoringWeights(),
    )


@pytest.fixture(autouse=True)
def reset_checker_fixture():
    """Reset checker singleton before each test."""
    reset_checker()
    yield
    reset_checker()


class TestThresholdCheckerBasic:
    """Basic threshold check tests."""

    def test_above_threshold_standard(self, sample_scored_signal: ScoredSignal):
        """Test signal above threshold gets standard tier."""
        sample_scored_signal.final_score = 0.75
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.conviction_tier == ConvictionTier.STANDARD
        assert result.position_multiplier == 1.0

    def test_high_conviction_tier(self, sample_scored_signal: ScoredSignal):
        """Test high score gets high conviction tier."""
        sample_scored_signal.final_score = 0.90
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.HIGH_CONVICTION
        assert result.conviction_tier == ConvictionTier.HIGH
        assert result.position_multiplier == 1.5

    def test_below_threshold(self, sample_scored_signal: ScoredSignal):
        """Test signal below threshold is rejected."""
        sample_scored_signal.final_score = 0.60
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD
        assert result.conviction_tier == ConvictionTier.NONE
        assert result.position_multiplier == 0.0

    def test_exactly_at_threshold(self, sample_scored_signal: ScoredSignal):
        """Test signal exactly at threshold is eligible."""
        sample_scored_signal.final_score = 0.70
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.conviction_tier == ConvictionTier.STANDARD

    def test_exactly_at_high_conviction(self, sample_scored_signal: ScoredSignal):
        """Test signal exactly at high conviction threshold."""
        sample_scored_signal.final_score = 0.85
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.HIGH_CONVICTION
        assert result.conviction_tier == ConvictionTier.HIGH


class TestThresholdFilters:
    """Tests for additional safety filters."""

    def test_liquidity_filter_fails(self, sample_scored_signal: ScoredSignal):
        """Test low liquidity fails filter."""
        sample_scored_signal.final_score = 0.80
        checker = ThresholdChecker()

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=500),  # Below min
        )

        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD
        assert result.passed_liquidity_check is False
        assert "liquidity_below_min" in result.filter_failures[0]

    def test_liquidity_filter_passes(self, sample_scored_signal: ScoredSignal):
        """Test sufficient liquidity passes filter."""
        sample_scored_signal.final_score = 0.80
        checker = ThresholdChecker()

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=5000),
        )

        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.passed_liquidity_check is True

    def test_honeypot_filter_fails(self, sample_scored_signal: ScoredSignal):
        """Test honeypot token fails filter."""
        sample_scored_signal.final_score = 0.85
        checker = ThresholdChecker()

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=50000),
            is_honeypot=True,
        )

        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD
        assert result.passed_honeypot_check is False
        assert "honeypot_detected" in result.filter_failures

    def test_multiple_filter_failures(self, sample_scored_signal: ScoredSignal):
        """Test multiple filter failures are recorded."""
        sample_scored_signal.final_score = 0.90
        checker = ThresholdChecker()

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=100),  # Too low
            is_honeypot=True,
        )

        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.BELOW_THRESHOLD
        assert len(result.filter_failures) == 2

    def test_no_token_skips_filters(self, sample_scored_signal: ScoredSignal):
        """Test that no token means filters are skipped."""
        sample_scored_signal.final_score = 0.80
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal, token=None)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.passed_liquidity_check is True
        assert result.passed_honeypot_check is True


class TestThresholdConfig:
    """Tests for threshold configuration."""

    def test_custom_thresholds(self, sample_scored_signal: ScoredSignal):
        """Test custom threshold configuration."""
        config = ThresholdConfig(
            trade_threshold=0.60,
            high_conviction_threshold=0.80,
        )
        checker = ThresholdChecker(config)

        sample_scored_signal.final_score = 0.65
        result = checker.check(sample_scored_signal)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.threshold_used == 0.60

    def test_custom_multipliers(self, sample_scored_signal: ScoredSignal):
        """Test custom position multipliers."""
        config = ThresholdConfig(
            trade_threshold=0.60,
            high_conviction_threshold=0.80,
            high_conviction_multiplier=2.0,
            standard_multiplier=0.75,
        )
        checker = ThresholdChecker(config)

        sample_scored_signal.final_score = 0.85
        result = checker.check(sample_scored_signal)

        assert result.position_multiplier == 2.0

    def test_config_update(self, sample_scored_signal: ScoredSignal):
        """Test config hot-reload."""
        checker = ThresholdChecker()

        # Initially below threshold
        sample_scored_signal.final_score = 0.65
        result1 = checker.check(sample_scored_signal)
        assert result1.eligibility_status == EligibilityStatus.BELOW_THRESHOLD

        # Update config
        new_config = ThresholdConfig(
            trade_threshold=0.60,
            high_conviction_threshold=0.80,
        )
        checker.update_config(new_config)

        # Now above threshold
        result2 = checker.check(sample_scored_signal)
        assert result2.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE

    def test_disabled_liquidity_filter(self, sample_scored_signal: ScoredSignal):
        """Test disabling liquidity filter."""
        config = ThresholdConfig(require_min_liquidity=False)
        checker = ThresholdChecker(config)

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=100),  # Would fail if enabled
        )

        sample_scored_signal.final_score = 0.80
        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.passed_liquidity_check is True

    def test_disabled_honeypot_filter(self, sample_scored_signal: ScoredSignal):
        """Test disabling honeypot filter."""
        config = ThresholdConfig(require_non_honeypot=False)
        checker = ThresholdChecker(config)

        token = TokenCharacteristics(
            token_address="Token123456789012345678901234567890123",
            liquidity=TokenLiquidity(usd=50000),
            is_honeypot=True,  # Would fail if enabled
        )

        sample_scored_signal.final_score = 0.80
        result = checker.check(sample_scored_signal, token)

        assert result.eligibility_status == EligibilityStatus.TRADE_ELIGIBLE
        assert result.passed_honeypot_check is True


class TestMarginCalculation:
    """Tests for margin above threshold calculation."""

    def test_margin_calculation(self, sample_scored_signal: ScoredSignal):
        """Test margin above threshold is calculated."""
        sample_scored_signal.final_score = 0.78
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.margin_above_threshold is not None
        assert abs(result.margin_above_threshold - 0.08) < 0.001

    def test_no_margin_for_below_threshold(self, sample_scored_signal: ScoredSignal):
        """Test no margin calculated for below threshold."""
        sample_scored_signal.final_score = 0.60
        checker = ThresholdChecker()

        result = checker.check(sample_scored_signal)

        assert result.margin_above_threshold is None


class TestTradeEligibleSignalCreation:
    """Tests for creating trade-eligible signals."""

    def test_create_eligible_signal(self, sample_scored_signal: ScoredSignal):
        """Test creating trade-eligible signal."""
        sample_scored_signal.final_score = 0.80
        checker = ThresholdChecker()

        threshold_result = checker.check(sample_scored_signal)
        eligible = checker.create_trade_eligible_signal(
            sample_scored_signal, threshold_result, amount_sol=1.5
        )

        assert eligible is not None
        assert eligible.tx_signature == sample_scored_signal.tx_signature
        assert eligible.amount_sol == 1.5
        assert eligible.conviction_tier == ConvictionTier.STANDARD
        assert eligible.ready_for_execution is True

    def test_create_high_conviction_signal(self, sample_scored_signal: ScoredSignal):
        """Test creating high conviction signal."""
        sample_scored_signal.final_score = 0.90
        checker = ThresholdChecker()

        threshold_result = checker.check(sample_scored_signal)
        eligible = checker.create_trade_eligible_signal(
            sample_scored_signal, threshold_result, amount_sol=2.0
        )

        assert eligible is not None
        assert eligible.conviction_tier == ConvictionTier.HIGH
        assert eligible.position_multiplier == 1.5

    def test_no_signal_for_below_threshold(self, sample_scored_signal: ScoredSignal):
        """Test no signal created for below threshold."""
        sample_scored_signal.final_score = 0.50
        checker = ThresholdChecker()

        threshold_result = checker.check(sample_scored_signal)
        eligible = checker.create_trade_eligible_signal(
            sample_scored_signal, threshold_result, amount_sol=1.0
        )

        assert eligible is None

    def test_factor_scores_preserved(self, sample_scored_signal: ScoredSignal):
        """Test factor scores are preserved in eligible signal."""
        sample_scored_signal.final_score = 0.80
        checker = ThresholdChecker()

        threshold_result = checker.check(sample_scored_signal)
        eligible = checker.create_trade_eligible_signal(
            sample_scored_signal, threshold_result, amount_sol=1.0
        )

        assert eligible is not None
        assert eligible.wallet_score == sample_scored_signal.wallet_score.score
        assert eligible.cluster_score == sample_scored_signal.cluster_score.score
        assert eligible.token_score == sample_scored_signal.token_score.score
        assert eligible.context_score == sample_scored_signal.context_score.score


class TestThresholdConfigValidation:
    """Tests for threshold config validation."""

    def test_valid_config(self):
        """Test valid config creation."""
        config = ThresholdConfig(
            trade_threshold=0.65,
            high_conviction_threshold=0.80,
        )
        assert config.trade_threshold == 0.65
        assert config.high_conviction_threshold == 0.80

    def test_high_must_exceed_trade(self):
        """Test high conviction must exceed trade threshold."""
        with pytest.raises(ValueError) as exc_info:
            ThresholdConfig(
                trade_threshold=0.80,
                high_conviction_threshold=0.75,
            )

        assert "must be > trade_threshold" in str(exc_info.value)

    def test_equal_thresholds_rejected(self):
        """Test equal thresholds are rejected."""
        with pytest.raises(ValueError):
            ThresholdConfig(
                trade_threshold=0.80,
                high_conviction_threshold=0.80,
            )
