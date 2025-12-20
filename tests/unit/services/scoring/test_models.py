"""Unit tests for scoring domain models."""

import pytest

from walltrack.models.scoring import (
    ClusterScoreComponents,
    ContextScoreComponents,
    FactorScore,
    ScoreCategory,
    ScoringConfig,
    ScoringWeights,
    TokenScoreComponents,
    WalletScoreComponents,
)


class TestScoreCategory:
    """Tests for ScoreCategory enum."""

    def test_category_values(self):
        """Test ScoreCategory has expected values."""
        assert ScoreCategory.WALLET.value == "wallet"
        assert ScoreCategory.CLUSTER.value == "cluster"
        assert ScoreCategory.TOKEN.value == "token"
        assert ScoreCategory.CONTEXT.value == "context"


class TestFactorScore:
    """Tests for FactorScore model."""

    def test_valid_factor_score(self):
        """Test valid factor score creation."""
        score = FactorScore(
            category=ScoreCategory.WALLET,
            score=0.75,
            weight=0.30,
            weighted_contribution=0.225,
            components={"win_rate": 0.8, "timing": 0.7},
            explanation="Good wallet score",
        )

        assert score.category == ScoreCategory.WALLET
        assert score.score == 0.75
        assert score.weighted_contribution == 0.225

    def test_score_bounds(self):
        """Test score must be between 0 and 1."""
        with pytest.raises(ValueError):
            FactorScore(
                category=ScoreCategory.WALLET,
                score=1.5,  # Invalid
                weight=0.30,
                weighted_contribution=0.225,
            )


class TestWalletScoreComponents:
    """Tests for WalletScoreComponents model."""

    def test_default_values(self):
        """Test default component values."""
        components = WalletScoreComponents()

        assert components.win_rate == 0.5
        assert components.timing_percentile == 0.5
        assert components.is_leader is False
        assert components.leader_bonus == 0.0
        assert components.decay_penalty == 0.0

    def test_custom_values(self):
        """Test custom component values."""
        components = WalletScoreComponents(
            win_rate=0.85,
            avg_pnl_percentage=120.0,
            timing_percentile=0.9,
            consistency_score=0.75,
            is_leader=True,
            leader_bonus=0.15,
            decay_penalty=0.0,
        )

        assert components.win_rate == 0.85
        assert components.is_leader is True
        assert components.leader_bonus == 0.15


class TestClusterScoreComponents:
    """Tests for ClusterScoreComponents model."""

    def test_default_values(self):
        """Test default cluster component values."""
        components = ClusterScoreComponents()

        assert components.cluster_size == 1
        assert components.is_solo_signal is True
        assert components.amplification_factor == 1.0

    def test_cluster_values(self):
        """Test cluster component values."""
        components = ClusterScoreComponents(
            cluster_size=5,
            active_members_count=3,
            participation_rate=0.6,
            amplification_factor=1.4,
            cluster_strength=0.8,
            is_solo_signal=False,
        )

        assert components.cluster_size == 5
        assert components.is_solo_signal is False
        assert components.amplification_factor == 1.4


class TestTokenScoreComponents:
    """Tests for TokenScoreComponents model."""

    def test_default_values(self):
        """Test default token component values."""
        components = TokenScoreComponents()

        assert components.liquidity_score == 0.5
        assert components.market_cap_score == 0.5
        assert components.age_penalty == 0.0
        assert components.honeypot_risk == 0.0

    def test_penalty_values(self):
        """Test penalty values."""
        components = TokenScoreComponents(
            liquidity_score=0.3,
            market_cap_score=0.4,
            holder_distribution_score=0.5,
            volume_score=0.6,
            age_penalty=0.2,
            honeypot_risk=0.3,
        )

        assert components.age_penalty == 0.2
        assert components.honeypot_risk == 0.3


class TestContextScoreComponents:
    """Tests for ContextScoreComponents model."""

    def test_default_values(self):
        """Test default context component values."""
        components = ContextScoreComponents()

        assert components.time_of_day_score == 0.5
        assert components.market_volatility_score == 0.5
        assert components.recent_activity_score == 0.5


class TestScoringWeights:
    """Tests for ScoringWeights model."""

    def test_default_weights(self):
        """Test default weights sum to 1.0."""
        weights = ScoringWeights()

        total = weights.wallet + weights.cluster + weights.token + weights.context
        assert abs(total - 1.0) < 0.001

    def test_custom_valid_weights(self):
        """Test custom weights that sum to 1.0."""
        weights = ScoringWeights(
            wallet=0.40,
            cluster=0.20,
            token=0.20,
            context=0.20,
        )

        assert weights.wallet == 0.40
        assert weights.cluster == 0.20

    def test_invalid_weights_rejected(self):
        """Test weights not summing to 1.0 are rejected."""
        with pytest.raises(ValueError) as exc_info:
            ScoringWeights(
                wallet=0.50,
                cluster=0.30,
                token=0.30,
                context=0.20,
            )

        assert "must sum to 1.0" in str(exc_info.value)


class TestScoringConfig:
    """Tests for ScoringConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ScoringConfig()

        assert config.leader_bonus_multiplier == 0.15
        assert config.decay_penalty_max == 0.3
        assert config.min_liquidity_usd == 1000.0
        assert config.solo_signal_base_score == 0.5

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScoringConfig(
            leader_bonus_multiplier=0.20,
            decay_penalty_max=0.25,
            min_liquidity_usd=2000.0,
            new_token_age_penalty_minutes=3,
        )

        assert config.leader_bonus_multiplier == 0.20
        assert config.min_liquidity_usd == 2000.0

    def test_peak_hours_default(self):
        """Test default peak hours."""
        config = ScoringConfig()

        assert 14 in config.peak_hours_utc
        assert 15 in config.peak_hours_utc
        assert 16 in config.peak_hours_utc
