"""Unit tests for simplified 2-component signal scorer.

Epic 14 Simplification: Tests updated for 2-component scoring model.
- Token safety: Binary gate (honeypot, freeze, mint)
- Wallet score: win_rate (60%) + pnl_normalized (40%) + leader_bonus
- Cluster boost: Direct multiplier 1.0x to 1.8x
- Single threshold: 0.65

Epic 14 Story 14-5: Tests updated to use ClusterInfo parameter.
Cluster data is no longer on WalletCacheEntry.
"""

import pytest

from walltrack.models.scoring import ScoredSignal, ScoringConfig
from walltrack.models.signal_filter import WalletCacheEntry
from walltrack.models.token import TokenCharacteristics, TokenLiquidity, TokenVolume
from walltrack.services.cluster import ClusterInfo
from walltrack.services.scoring.signal_scorer import (
    SignalScorer,
    SimpleScoringParams,
    get_scorer,
    reset_scorer,
)


@pytest.fixture
def sample_wallet() -> WalletCacheEntry:
    """Sample wallet cache entry with good stats.

    Epic 14 Story 14-5: No longer has cluster_id/is_leader.
    Use ClusterInfo parameter for cluster data.
    """
    return WalletCacheEntry(
        wallet_address="Wallet12345678901234567890123456789012",
        reputation_score=0.75,
    )


@pytest.fixture
def sample_cluster_info() -> ClusterInfo:
    """Sample cluster info for tests."""
    return ClusterInfo(
        cluster_id="cluster-1",
        is_leader=False,
        amplification_factor=1.0,
        cluster_size=3,
    )


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Sample safe token with good characteristics."""
    return TokenCharacteristics(
        token_address="Token123456789012345678901234567890123",
        name="Good Token",
        symbol="GOOD",
        price_usd=0.001,
        market_cap_usd=200000,
        liquidity=TokenLiquidity(usd=30000),
        volume=TokenVolume(h24=75000),
        holder_count=250,
        age_minutes=60,
        is_new_token=False,
        is_honeypot=False,
        has_freeze_authority=False,
        has_mint_authority=False,
    )


@pytest.fixture(autouse=True)
def reset_scorer_fixture():
    """Reset scorer singleton before each test."""
    reset_scorer()
    yield
    reset_scorer()


class TestSimpleScoringParams:
    """Tests for SimpleScoringParams dataclass."""

    def test_from_config(self):
        """Test creating params from config."""
        config = ScoringConfig(
            trade_threshold=0.70,
            leader_bonus=1.20,
        )
        params = SimpleScoringParams.from_config(config)

        assert params.trade_threshold == 0.70
        assert params.leader_bonus == 1.20

    def test_defaults(self):
        """Test default params creation."""
        params = SimpleScoringParams.defaults()

        assert params.trade_threshold == 0.65
        assert params.wallet_win_rate_weight == 0.6
        assert params.wallet_pnl_weight == 0.4
        assert params.leader_bonus == 1.15


class TestTokenSafetyGate:
    """Tests for binary token safety check."""

    def test_safe_token_passes(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that safe token passes gate."""
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result.token_safe is True
        assert result.token_reject_reason is None
        assert result.final_score > 0

    def test_honeypot_rejected(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that honeypot token is rejected."""
        sample_token.is_honeypot = True
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result.token_safe is False
        assert result.token_reject_reason == "honeypot"
        assert result.final_score == 0.0
        assert result.should_trade is False

    def test_freeze_authority_rejected(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that freeze authority token is rejected."""
        sample_token.has_freeze_authority = True
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result.token_safe is False
        assert result.token_reject_reason == "freeze_authority"
        assert result.final_score == 0.0

    def test_mint_authority_rejected(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that mint authority token is rejected."""
        sample_token.has_mint_authority = True
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result.token_safe is False
        assert result.token_reject_reason == "mint_authority"
        assert result.final_score == 0.0


class TestWalletScoring:
    """Tests for wallet score calculation."""

    def test_high_reputation_gives_high_score(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that high reputation gives high wallet score."""
        sample_wallet.reputation_score = 0.9
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        # Expected: 0.9 * 0.6 + 0.5 * 0.4 = 0.54 + 0.20 = 0.74
        assert result.wallet_score > 0.7

    def test_low_reputation_gives_low_score(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that low reputation gives low wallet score."""
        sample_wallet.reputation_score = 0.2
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        # Expected: 0.2 * 0.6 + 0.5 * 0.4 = 0.12 + 0.20 = 0.32
        assert result.wallet_score < 0.4

    def test_leader_bonus_increases_score(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that leader bonus increases wallet score."""
        scorer = SignalScorer()

        # Non-leader (via ClusterInfo)
        cluster_info_no_leader = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=1.0, cluster_size=3
        )
        result_no_leader = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info_no_leader,
        )

        # Leader (via ClusterInfo)
        cluster_info_leader = ClusterInfo(
            cluster_id="c1", is_leader=True, amplification_factor=1.0, cluster_size=3
        )
        result_leader = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info_leader,
        )

        assert result_leader.wallet_score > result_no_leader.wallet_score
        assert result_leader.is_leader is True

    def test_wallet_score_clamped_to_one(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that wallet score is clamped to 1.0."""
        # Very high reputation + leader bonus could exceed 1.0
        sample_wallet.reputation_score = 1.0
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=True, amplification_factor=1.0, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.wallet_score <= 1.0


class TestClusterBoost:
    """Tests for cluster boost multiplier.

    Epic 14 Story 14-5: Cluster boost now comes from ClusterInfo.amplification_factor.
    """

    def test_cluster_boost_increases_final_score(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that cluster boost increases final score."""
        scorer = SignalScorer()

        # No boost
        cluster_info_no_boost = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=1.0, cluster_size=3
        )
        result_no_boost = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info_no_boost,
        )

        # With boost
        cluster_info_with_boost = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=1.5, cluster_size=3
        )
        result_with_boost = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info_with_boost,
        )

        assert result_with_boost.final_score > result_no_boost.final_score
        assert result_with_boost.cluster_boost == 1.5

    def test_cluster_boost_clamped_to_max(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that cluster boost is clamped to max."""
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=3.0, cluster_size=3
        )  # Above max of 1.8
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.cluster_boost == 1.8  # Clamped

    def test_cluster_boost_clamped_to_min(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that cluster boost is clamped to min."""
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=0.5, cluster_size=3
        )  # Below min of 1.0
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.cluster_boost == 1.0  # Clamped

    def test_final_score_clamped_to_one(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that final score is clamped to 1.0."""
        sample_wallet.reputation_score = 0.9
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=True, amplification_factor=1.8, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.final_score <= 1.0


class TestThresholdDecision:
    """Tests for threshold-based trade decision."""

    def test_above_threshold_should_trade(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that score above threshold triggers trade."""
        sample_wallet.reputation_score = 0.9
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=True, amplification_factor=1.5, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.should_trade is True
        assert result.final_score >= 0.65

    def test_below_threshold_no_trade(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that score below threshold doesn't trigger trade."""
        sample_wallet.reputation_score = 0.3
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result.should_trade is False
        assert result.final_score < 0.65

    def test_position_multiplier_equals_boost_when_trading(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that position multiplier equals cluster boost when trading."""
        sample_wallet.reputation_score = 0.9
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=True, amplification_factor=1.5, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.should_trade is True
        assert result.position_multiplier == 1.5

    def test_position_multiplier_one_when_not_trading(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that position multiplier is 1.0 when not trading."""
        sample_wallet.reputation_score = 0.3
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=1.5, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.should_trade is False
        assert result.position_multiplier == 1.0


class TestScoredSignalOutput:
    """Tests for ScoredSignal output fields."""

    def test_all_required_fields_populated(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that all required fields are populated."""
        cluster_info = ClusterInfo(
            cluster_id="c1", is_leader=False, amplification_factor=1.2, cluster_size=3
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123456",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert isinstance(result, ScoredSignal)
        assert result.tx_signature == "sig123456"
        assert result.wallet_address == sample_wallet.wallet_address
        assert result.token_address == sample_token.token_address
        assert result.direction == "buy"
        assert result.scoring_time_ms >= 0

    def test_explanation_contains_key_info(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that explanation contains key information."""
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert "Wallet:" in result.explanation
        assert "Final:" in result.explanation

    def test_cluster_info_preserved(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that cluster info from ClusterInfo is preserved in result."""
        cluster_info = ClusterInfo(
            cluster_id="test-cluster-123",
            is_leader=True,
            amplification_factor=1.5,
            cluster_size=5,
        )
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=cluster_info,
        )

        assert result.cluster_id == "test-cluster-123"
        assert result.is_leader is True


class TestScorerSingleton:
    """Tests for scorer singleton pattern."""

    def test_get_scorer_returns_same_instance(self):
        """Test that get_scorer returns same instance."""
        scorer1 = get_scorer()
        scorer2 = get_scorer()

        assert scorer1 is scorer2

    def test_reset_scorer_clears_instance(self):
        """Test that reset_scorer clears the instance."""
        scorer1 = get_scorer()
        reset_scorer()
        scorer2 = get_scorer()

        assert scorer1 is not scorer2

    def test_get_scorer_with_config(self):
        """Test get_scorer with custom config."""
        config = ScoringConfig(trade_threshold=0.70)
        scorer = get_scorer(config)

        assert scorer._params.trade_threshold == 0.70


class TestConfigUpdate:
    """Tests for config update functionality."""

    def test_update_config_changes_params(self):
        """Test that update_config changes scoring params."""
        scorer = SignalScorer()

        new_config = ScoringConfig(
            trade_threshold=0.80,
            leader_bonus=1.25,
        )
        scorer.update_config(new_config)

        assert scorer._params.trade_threshold == 0.80
        assert scorer._params.leader_bonus == 1.25

    def test_update_config_affects_scoring(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that config update affects scoring."""
        scorer = SignalScorer()

        # Score with default threshold
        result1 = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        # Update to very high threshold
        scorer.update_config(ScoringConfig(trade_threshold=0.99))

        # Same score but different decision
        result2 = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        assert result1.final_score == result2.final_score
        assert result2.should_trade is False  # High threshold


class TestEdgeCases:
    """Tests for edge cases."""

    def test_zero_reputation(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test scoring with zero reputation."""
        sample_wallet.reputation_score = 0.0
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        # 0.0 * 0.6 + 0.5 * 0.4 = 0.20
        assert result.wallet_score == 0.2
        assert result.should_trade is False

    def test_none_reputation_uses_default(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that None reputation uses default 0.5."""
        sample_wallet.reputation_score = None
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
        )

        # Default 0.5 * 0.6 + 0.5 * 0.4 = 0.30 + 0.20 = 0.50
        assert result.wallet_score == 0.5

    def test_sell_direction(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test scoring with sell direction."""
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="sell",
        )

        assert result.direction == "sell"
        assert result.final_score > 0  # Still scores normally

    def test_no_cluster_info_uses_defaults(
        self,
        sample_wallet: WalletCacheEntry,
        sample_token: TokenCharacteristics,
    ):
        """Test that None cluster_info uses safe defaults.

        Epic 14 Story 14-5: When no cluster info is provided,
        defaults to is_leader=False, cluster_id=None, boost=1.0.
        """
        scorer = SignalScorer()
        result = scorer.score(
            wallet=sample_wallet,
            token=sample_token,
            tx_signature="sig123",
            direction="buy",
            cluster_info=None,
        )

        assert result.cluster_id is None
        assert result.is_leader is False
        assert result.cluster_boost == 1.0
