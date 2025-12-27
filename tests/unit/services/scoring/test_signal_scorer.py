"""Unit tests for signal scorer service."""

from datetime import UTC, datetime

import pytest

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.models.scoring import (
    ScoredSignal,
    ScoringConfig,
    ScoringWeights,
)
from walltrack.models.signal_filter import SignalContext
from walltrack.models.token import TokenCharacteristics, TokenLiquidity, TokenVolume
from walltrack.services.scoring.signal_scorer import SignalScorer, reset_scorer


@pytest.fixture
def sample_signal() -> SignalContext:
    """Sample signal context."""
    return SignalContext(
        wallet_address="Wallet12345678901234567890123456789012",
        token_address="Token123456789012345678901234567890123",
        direction="buy",
        amount_token=1000000,
        amount_sol=1.0,
        timestamp=datetime.now(UTC).replace(hour=15),  # Peak hour
        tx_signature="sig123456789",
        cluster_id="cluster-1",
        is_cluster_leader=True,
        wallet_reputation=0.8,
    )


@pytest.fixture
def sample_wallet() -> Wallet:
    """Sample wallet with good stats."""
    return Wallet(
        address="Wallet12345678901234567890123456789012",
        status=WalletStatus.ACTIVE,
        score=0.75,
        profile=WalletProfile(
            win_rate=0.75,
            total_pnl=1500.0,
            avg_pnl_per_trade=150.0,
            total_trades=25,
            timing_percentile=0.85,
            avg_hold_time_hours=2.5,
        ),
        consecutive_losses=0,
        rolling_win_rate=0.72,
    )


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Sample token with good characteristics."""
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
    )


@pytest.fixture(autouse=True)
def reset_scorer_fixture():
    """Reset scorer singleton before each test."""
    reset_scorer()
    yield
    reset_scorer()


class TestSignalScorerBasic:
    """Basic scoring tests."""

    @pytest.mark.asyncio
    async def test_score_produces_valid_result(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that scoring produces valid result."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert isinstance(result, ScoredSignal)
        assert 0.0 <= result.final_score <= 1.0
        assert result.wallet_score.score > 0
        assert result.token_score.score > 0

    @pytest.mark.asyncio
    async def test_weights_sum_to_one(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that weights sum to 1.0."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        weights = result.weights_used
        total = weights.wallet + weights.cluster + weights.token + weights.context
        assert abs(total - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_scoring_time_recorded(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that scoring time is recorded."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result.scoring_time_ms > 0


class TestWalletScoring:
    """Tests for wallet score calculation (AC2)."""

    @pytest.mark.asyncio
    async def test_leader_bonus_applied(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that leader bonus increases wallet score."""
        scorer = SignalScorer()

        # Score with leader status
        sample_signal.is_cluster_leader = True
        result_leader = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Score without leader status
        sample_signal.is_cluster_leader = False
        result_no_leader = await scorer.score(
            sample_signal, sample_wallet, sample_token
        )

        assert result_leader.wallet_score.score > result_no_leader.wallet_score.score
        assert result_leader.wallet_components.leader_bonus > 0
        assert result_no_leader.wallet_components.leader_bonus == 0

    @pytest.mark.asyncio
    async def test_decay_penalty_applied(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that decay penalty reduces wallet score."""
        scorer = SignalScorer()

        # Score without decay
        sample_wallet.status = WalletStatus.ACTIVE
        result_normal = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Score with decay
        sample_wallet.status = WalletStatus.DECAY_DETECTED
        result_decayed = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_decayed.wallet_score.score < result_normal.wallet_score.score
        assert result_decayed.wallet_components.decay_penalty > 0
        assert result_normal.wallet_components.decay_penalty == 0

    @pytest.mark.asyncio
    async def test_high_win_rate_increases_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that high win rate increases wallet score."""
        scorer = SignalScorer()

        # High win rate
        sample_wallet.profile.win_rate = 0.9
        result_high = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Low win rate
        sample_wallet.profile.win_rate = 0.3
        result_low = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_high.wallet_score.score > result_low.wallet_score.score

    @pytest.mark.asyncio
    async def test_timing_percentile_affects_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that timing percentile affects wallet score."""
        scorer = SignalScorer()

        # Early timer (high percentile)
        sample_wallet.profile.timing_percentile = 0.95
        result_early = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Late timer (low percentile)
        sample_wallet.profile.timing_percentile = 0.2
        result_late = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_early.wallet_score.score > result_late.wallet_score.score


class TestClusterScoring:
    """Tests for cluster score calculation (AC3)."""

    @pytest.mark.asyncio
    async def test_solo_signal_gets_base_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that solo signals get base cluster score."""
        scorer = SignalScorer()

        # No cluster
        sample_signal.cluster_id = None
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result.cluster_score.score == 0.5  # SOLO_SIGNAL_BASE
        assert result.cluster_components.is_solo_signal is True

    @pytest.mark.asyncio
    async def test_cluster_signal_without_amplifier(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test cluster signal without amplifier gets base score."""
        scorer = SignalScorer(cluster_amplifier=None)

        # Has cluster but no amplifier
        sample_signal.cluster_id = "cluster-123"
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result.cluster_score.score == 0.5
        assert result.cluster_components.is_solo_signal is True


class TestTokenScoring:
    """Tests for token score calculation (AC4)."""

    @pytest.mark.asyncio
    async def test_new_token_penalty(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that very new tokens get penalized."""
        scorer = SignalScorer()

        # Established token
        sample_token.is_new_token = False
        sample_token.age_minutes = 60
        result_established = await scorer.score(
            sample_signal, sample_wallet, sample_token
        )

        # Very new token
        sample_token.is_new_token = True
        sample_token.age_minutes = 2
        result_new = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_new.token_score.score < result_established.token_score.score
        assert result_new.token_components.age_penalty > 0
        assert result_established.token_components.age_penalty == 0

    @pytest.mark.asyncio
    async def test_low_liquidity_reduces_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that low liquidity reduces token score."""
        scorer = SignalScorer()

        # Good liquidity
        sample_token.liquidity = TokenLiquidity(usd=50000)
        result_good = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Low liquidity
        sample_token.liquidity = TokenLiquidity(usd=500)
        result_low = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_low.token_score.score < result_good.token_score.score
        assert result_low.token_components.liquidity_score == 0.0

    @pytest.mark.asyncio
    async def test_optimal_liquidity_maxes_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that optimal+ liquidity gives max liquidity score."""
        scorer = SignalScorer()

        sample_token.liquidity = TokenLiquidity(usd=100000)  # Above optimal
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result.token_components.liquidity_score == 1.0

    @pytest.mark.asyncio
    async def test_honeypot_reduces_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that honeypot flag reduces token score."""
        scorer = SignalScorer()

        # Normal token
        sample_token.is_honeypot = None
        result_normal = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Honeypot
        sample_token.is_honeypot = True
        result_honeypot = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_honeypot.token_score.score < result_normal.token_score.score
        assert result_honeypot.token_components.honeypot_risk == 0.5

    @pytest.mark.asyncio
    async def test_freeze_authority_reduces_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that freeze authority reduces token score."""
        scorer = SignalScorer()

        # Normal token
        sample_token.has_freeze_authority = None
        result_normal = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Has freeze authority
        sample_token.has_freeze_authority = True
        result_freeze = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_freeze.token_score.score < result_normal.token_score.score
        assert result_freeze.token_components.honeypot_risk == 0.2

    @pytest.mark.asyncio
    async def test_market_cap_affects_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that market cap affects token score."""
        scorer = SignalScorer()

        # High market cap
        sample_token.market_cap_usd = 1000000
        result_high = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Low market cap
        sample_token.market_cap_usd = 5000
        result_low = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_high.token_components.market_cap_score > result_low.token_components.market_cap_score

    @pytest.mark.asyncio
    async def test_volume_affects_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that volume affects token score."""
        scorer = SignalScorer()

        # High volume
        sample_token.volume = TokenVolume(h24=200000)
        result_high = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Low volume
        sample_token.volume = TokenVolume(h24=1000)
        result_low = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_high.token_components.volume_score > result_low.token_components.volume_score


class TestContextScoring:
    """Tests for context score calculation (AC5)."""

    @pytest.mark.asyncio
    async def test_peak_hours_increase_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that peak trading hours increase context score."""
        scorer = SignalScorer()

        # Peak hour (15 UTC)
        sample_signal.timestamp = datetime.now(UTC).replace(hour=15)
        result_peak = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Off-peak hour (3 UTC)
        sample_signal.timestamp = datetime.now(UTC).replace(hour=3)
        result_offpeak = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_peak.context_score.score > result_offpeak.context_score.score
        assert result_peak.context_components.time_of_day_score == 1.0
        assert result_offpeak.context_components.time_of_day_score == 0.6


class TestScoringConfig:
    """Tests for scoring configuration via ConfigService."""

    @pytest.mark.asyncio
    async def test_default_weights_from_fallback(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that default weights are applied from ScoringParams.defaults()."""
        reset_scorer()
        # Without ConfigService, scorer uses fallback defaults
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Check fallback default weights are applied
        assert result.weights_used.wallet == 0.30
        assert result.weights_used.cluster == 0.25
        assert result.weights_used.token == 0.25
        assert result.weights_used.context == 0.20

    @pytest.mark.asyncio
    async def test_update_config_is_deprecated(self):
        """Test that update_config() is deprecated and logs warning."""
        scorer = SignalScorer()

        new_config = ScoringConfig(
            weights=ScoringWeights(
                wallet=0.40,
                cluster=0.20,
                token=0.20,
                context=0.20,
            )
        )

        # update_config() should still work but is deprecated
        scorer.update_config(new_config)

        # Legacy config is stored but not used for scoring
        assert scorer._legacy_config is not None
        assert scorer._legacy_config.weights.wallet == 0.40


class TestScoringWeightsValidation:
    """Tests for scoring weights validation."""

    def test_valid_weights(self):
        """Test that valid weights are accepted."""
        weights = ScoringWeights(
            wallet=0.30,
            cluster=0.25,
            token=0.25,
            context=0.20,
        )

        assert weights.wallet == 0.30
        assert weights.cluster == 0.25

    def test_invalid_weights_sum(self):
        """Test that weights not summing to 1.0 raise error."""
        with pytest.raises(ValueError) as exc_info:
            ScoringWeights(
                wallet=0.40,
                cluster=0.30,
                token=0.30,
                context=0.20,
            )

        assert "must sum to 1.0" in str(exc_info.value)


class TestFinalScoreCalculation:
    """Tests for final score calculation (AC6)."""

    @pytest.mark.asyncio
    async def test_final_score_is_weighted_sum(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that final score equals weighted sum of factors."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        expected_final = (
            result.wallet_score.weighted_contribution
            + result.cluster_score.weighted_contribution
            + result.token_score.weighted_contribution
            + result.context_score.weighted_contribution
        )

        assert abs(result.final_score - expected_final) < 0.001

    @pytest.mark.asyncio
    async def test_final_score_clamped(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that final score is clamped to [0, 1]."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert 0.0 <= result.final_score <= 1.0

    @pytest.mark.asyncio
    async def test_factor_contributions_preserved(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that factor contributions are preserved for analysis."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        # All factor scores have components
        assert len(result.wallet_score.components) > 0
        assert len(result.token_score.components) > 0
        assert len(result.context_score.components) > 0

        # All detailed components are present
        assert result.wallet_components is not None
        assert result.token_components is not None
        assert result.context_components is not None
        assert result.cluster_components is not None
