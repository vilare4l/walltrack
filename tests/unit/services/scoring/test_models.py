"""Unit tests for simplified scoring domain models.

Epic 14 Simplification: Tests updated for 2-component scoring model.
"""

import pytest

from walltrack.models.scoring import ScoredSignal, ScoringConfig


class TestScoringConfig:
    """Tests for simplified ScoringConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ScoringConfig()

        assert config.trade_threshold == 0.65
        assert config.wallet_win_rate_weight == 0.6
        assert config.wallet_pnl_weight == 0.4
        assert config.leader_bonus == 1.15
        assert config.pnl_normalize_min == -100.0
        assert config.pnl_normalize_max == 500.0
        assert config.min_cluster_boost == 1.0
        assert config.max_cluster_boost == 1.8

    def test_custom_config(self):
        """Test custom configuration values."""
        config = ScoringConfig(
            trade_threshold=0.70,
            leader_bonus=1.25,
            max_cluster_boost=2.0,
        )

        assert config.trade_threshold == 0.70
        assert config.leader_bonus == 1.25
        assert config.max_cluster_boost == 2.0

    def test_wallet_weights_preserved(self):
        """Test wallet weight customization."""
        config = ScoringConfig(
            wallet_win_rate_weight=0.7,
            wallet_pnl_weight=0.3,
        )

        assert config.wallet_win_rate_weight == 0.7
        assert config.wallet_pnl_weight == 0.3

    def test_pnl_normalization_range(self):
        """Test PnL normalization range customization."""
        config = ScoringConfig(
            pnl_normalize_min=-100.0,
            pnl_normalize_max=500.0,
        )

        assert config.pnl_normalize_min == -100.0
        assert config.pnl_normalize_max == 500.0


class TestScoredSignal:
    """Tests for simplified ScoredSignal model."""

    def test_required_fields(self):
        """Test required fields for ScoredSignal."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.75,
            wallet_score=0.70,
            cluster_boost=1.2,
            token_safe=True,
            is_leader=False,
            should_trade=True,
            position_multiplier=1.2,
            explanation="Test explanation",
        )

        assert signal.tx_signature == "sig123"
        assert signal.final_score == 0.75
        assert signal.token_safe is True

    def test_token_rejected(self):
        """Test signal with rejected token."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.0,
            wallet_score=0.0,
            cluster_boost=1.0,
            token_safe=False,
            token_reject_reason="honeypot",
            is_leader=False,
            should_trade=False,
            position_multiplier=1.0,
            explanation="Token rejected: honeypot",
        )

        assert signal.token_safe is False
        assert signal.token_reject_reason == "honeypot"
        assert signal.final_score == 0.0

    def test_optional_cluster_id(self):
        """Test optional cluster_id field."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.75,
            wallet_score=0.70,
            cluster_boost=1.5,
            token_safe=True,
            is_leader=True,
            cluster_id="cluster-abc",
            should_trade=True,
            position_multiplier=1.5,
            explanation="Test",
        )

        assert signal.cluster_id == "cluster-abc"
        assert signal.is_leader is True

    def test_scoring_time_optional(self):
        """Test scoring_time_ms is optional with default."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.75,
            wallet_score=0.70,
            cluster_boost=1.0,
            token_safe=True,
            is_leader=False,
            should_trade=True,
            position_multiplier=1.0,
            explanation="Test",
        )

        # Should have default value
        assert hasattr(signal, "scoring_time_ms")

    def test_direction_values(self):
        """Test direction field accepts buy/sell."""
        buy_signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.75,
            wallet_score=0.70,
            cluster_boost=1.0,
            token_safe=True,
            is_leader=False,
            should_trade=True,
            position_multiplier=1.0,
            explanation="Test",
        )
        assert buy_signal.direction == "buy"

        sell_signal = ScoredSignal(
            tx_signature="sig456",
            wallet_address="wallet123",
            token_address="token123",
            direction="sell",
            final_score=0.75,
            wallet_score=0.70,
            cluster_boost=1.0,
            token_safe=True,
            is_leader=False,
            should_trade=True,
            position_multiplier=1.0,
            explanation="Test",
        )
        assert sell_signal.direction == "sell"


class TestScoringConfigDefaults:
    """Tests for ScoringConfig default constants."""

    def test_wallet_weights_sum_to_one(self):
        """Test wallet weights sum to 1.0."""
        config = ScoringConfig()
        total = config.wallet_win_rate_weight + config.wallet_pnl_weight
        assert abs(total - 1.0) < 0.001

    def test_threshold_in_valid_range(self):
        """Test threshold is between 0 and 1."""
        config = ScoringConfig()
        assert 0 < config.trade_threshold < 1

    def test_leader_bonus_multiplier(self):
        """Test leader bonus is >= 1.0 (multiplicative)."""
        config = ScoringConfig()
        assert config.leader_bonus >= 1.0

    def test_cluster_boost_range(self):
        """Test cluster boost range is valid."""
        config = ScoringConfig()
        assert config.min_cluster_boost >= 1.0
        assert config.max_cluster_boost >= config.min_cluster_boost


class TestScoredSignalScoreBounds:
    """Tests for score value bounds."""

    def test_high_score(self):
        """Test high scoring signal."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=1.0,
            wallet_score=1.0,
            cluster_boost=1.8,
            token_safe=True,
            is_leader=True,
            should_trade=True,
            position_multiplier=1.8,
            explanation="Perfect score",
        )

        assert signal.final_score == 1.0
        assert signal.should_trade is True

    def test_low_score(self):
        """Test low scoring signal."""
        signal = ScoredSignal(
            tx_signature="sig123",
            wallet_address="wallet123",
            token_address="token123",
            direction="buy",
            final_score=0.2,
            wallet_score=0.2,
            cluster_boost=1.0,
            token_safe=True,
            is_leader=False,
            should_trade=False,
            position_multiplier=1.0,
            explanation="Low score",
        )

        assert signal.final_score == 0.2
        assert signal.should_trade is False
