"""Multi-factor signal scoring engine."""

import time
from typing import Protocol

import structlog

from walltrack.constants.scoring import (
    CONSISTENCY_WEIGHT,
    HOLDER_DIST_WEIGHT,
    LEADER_BONUS,
    LIQUIDITY_WEIGHT,
    MARKET_CAP_WEIGHT,
    MAX_DECAY_PENALTY,
    MAX_NEW_TOKEN_PENALTY,
    MIN_LIQUIDITY_USD,
    MIN_MARKET_CAP_USD,
    NEW_TOKEN_PENALTY_MINUTES,
    OPTIMAL_LIQUIDITY_USD,
    OPTIMAL_MARKET_CAP_USD,
    PEAK_TRADING_HOURS_UTC,
    PNL_WEIGHT,
    SOLO_SIGNAL_BASE,
    TIMING_WEIGHT,
    VOLUME_WEIGHT,
    WIN_RATE_WEIGHT,
)
from walltrack.data.models.wallet import Wallet, WalletStatus
from walltrack.models.scoring import (
    ClusterScoreComponents,
    ContextScoreComponents,
    FactorScore,
    ScoreCategory,
    ScoredSignal,
    ScoringConfig,
    TokenScoreComponents,
    WalletScoreComponents,
)
from walltrack.models.signal_filter import SignalContext
from walltrack.models.token import TokenCharacteristics

logger = structlog.get_logger(__name__)


class ClusterAmplifierProtocol(Protocol):
    """Protocol for cluster amplifier (from Epic 2)."""

    async def calculate_amplification(
        self,
        cluster_id: str,
        token_address: str,
    ) -> "ClusterAmplificationResult | None":
        """Calculate amplification factor for cluster activity."""
        ...


class ClusterAmplificationResult:
    """Result from cluster amplification calculation."""

    amplification_factor: float
    cluster_activity: "ClusterActivity"


class ClusterActivity:
    """Cluster activity data."""

    member_count: int
    active_in_window: int
    participation_rate: float
    cluster_strength: float


class SignalScorer:
    """Multi-factor signal scoring engine.

    Calculates weighted score from:
    - Wallet score (30%): performance, timing, leader status
    - Cluster score (25%): activity amplification
    - Token score (25%): liquidity, market cap, holder distribution
    - Context score (20%): timing, market conditions
    """

    def __init__(
        self,
        config: ScoringConfig | None = None,
        cluster_amplifier: ClusterAmplifierProtocol | None = None,
    ) -> None:
        """Initialize signal scorer.

        Args:
            config: Scoring configuration
            cluster_amplifier: Optional cluster amplifier from Epic 2
        """
        self.config = config or ScoringConfig()
        self.cluster_amplifier = cluster_amplifier

    async def score(
        self,
        signal: SignalContext,
        wallet: Wallet,
        token: TokenCharacteristics,
    ) -> ScoredSignal:
        """Calculate multi-factor score for a signal.

        Args:
            signal: Filtered signal context
            wallet: Wallet data with performance metrics
            token: Token characteristics

        Returns:
            ScoredSignal with complete breakdown
        """
        start_time = time.perf_counter()

        # Calculate individual factor scores
        wallet_score, wallet_components = self._calculate_wallet_score(
            wallet, signal.is_cluster_leader
        )
        cluster_score, cluster_components = await self._calculate_cluster_score(
            signal
        )
        token_score, token_components = self._calculate_token_score(token)
        context_score, context_components = self._calculate_context_score(signal)

        # Get weights
        weights = self.config.weights

        # Calculate weighted final score (AC6)
        final_score = (
            wallet_score.weighted_contribution
            + cluster_score.weighted_contribution
            + token_score.weighted_contribution
            + context_score.weighted_contribution
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        scoring_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "signal_scored",
            wallet=signal.wallet_address[:8] + "...",
            token=signal.token_address[:8] + "...",
            final_score=round(final_score, 4),
            wallet_score=round(wallet_score.score, 4),
            cluster_score=round(cluster_score.score, 4),
            token_score=round(token_score.score, 4),
            context_score=round(context_score.score, 4),
            scoring_time_ms=round(scoring_time_ms, 2),
        )

        return ScoredSignal(
            tx_signature=signal.tx_signature,
            wallet_address=signal.wallet_address,
            token_address=signal.token_address,
            direction=signal.direction,
            final_score=final_score,
            wallet_score=wallet_score,
            cluster_score=cluster_score,
            token_score=token_score,
            context_score=context_score,
            wallet_components=wallet_components,
            cluster_components=cluster_components,
            token_components=token_components,
            context_components=context_components,
            weights_used=weights,
            scoring_time_ms=scoring_time_ms,
        )

    def _calculate_wallet_score(
        self,
        wallet: Wallet,
        is_leader: bool,
    ) -> tuple[FactorScore, WalletScoreComponents]:
        """Calculate wallet score (AC2).

        Components:
        - Win rate (35%)
        - PnL history (25%)
        - Timing percentile (25%)
        - Consistency (15%)
        + Leader bonus
        - Decay penalty
        """
        # Component scores from wallet profile
        win_rate = wallet.profile.win_rate if wallet.profile.win_rate else 0.5
        avg_pnl = wallet.profile.avg_pnl_per_trade if wallet.profile.avg_pnl_per_trade else 0.0
        timing = wallet.profile.timing_percentile if wallet.profile.timing_percentile else 0.5

        # Calculate consistency from available data
        # Higher consistency = more consistent trading pattern
        consistency = self._calculate_consistency(wallet)

        # Normalize PnL to [0, 1] range (assuming -100 to +500 USD range)
        pnl_normalized = max(0.0, min(1.0, (avg_pnl + 100) / 600))

        # Base score calculation
        base_score = (
            win_rate * WIN_RATE_WEIGHT
            + pnl_normalized * PNL_WEIGHT
            + timing * TIMING_WEIGHT
            + consistency * CONSISTENCY_WEIGHT
        )

        # Leader bonus (AC2)
        leader_bonus = LEADER_BONUS if is_leader else 0.0

        # Decay penalty (AC2)
        decay_penalty = 0.0
        if wallet.status == WalletStatus.DECAY_DETECTED:
            decay_penalty = MAX_DECAY_PENALTY

        # Final wallet score
        final_score = max(0.0, min(1.0, base_score + leader_bonus - decay_penalty))

        weight = self.config.weights.wallet
        weighted_contribution = final_score * weight

        components = WalletScoreComponents(
            win_rate=win_rate,
            avg_pnl_percentage=avg_pnl,
            timing_percentile=timing,
            consistency_score=consistency,
            is_leader=is_leader,
            leader_bonus=leader_bonus,
            decay_penalty=decay_penalty,
        )

        return (
            FactorScore(
                category=ScoreCategory.WALLET,
                score=final_score,
                weight=weight,
                weighted_contribution=weighted_contribution,
                components={
                    "win_rate": win_rate,
                    "pnl_normalized": pnl_normalized,
                    "timing": timing,
                    "consistency": consistency,
                    "leader_bonus": leader_bonus,
                    "decay_penalty": decay_penalty,
                },
                explanation=f"Wallet: {final_score:.2f} (win={win_rate:.2f}, lead={is_leader})",
            ),
            components,
        )

    def _calculate_consistency(self, wallet: Wallet) -> float:
        """Calculate wallet consistency score.

        Based on trade count and rolling win rate stability.
        """
        # Base consistency on trade count
        if wallet.profile.total_trades < 5:
            return 0.3  # Low consistency for insufficient data

        if wallet.profile.total_trades < 20:
            return 0.5  # Medium consistency

        # High trade count = more reliable stats
        trade_consistency = min(1.0, wallet.profile.total_trades / 100)

        # Rolling win rate vs overall win rate stability
        if wallet.rolling_win_rate is not None:
            diff = abs(wallet.rolling_win_rate - wallet.profile.win_rate)
            stability = 1.0 - min(1.0, diff * 2)  # Penalize large differences
        else:
            stability = 0.5

        return (trade_consistency * 0.6 + stability * 0.4)

    async def _calculate_cluster_score(
        self,
        signal: SignalContext,
    ) -> tuple[FactorScore, ClusterScoreComponents]:
        """Calculate cluster score (AC3).

        Uses amplification factor from Story 2.6 if cluster activity detected.
        Solo signals get base cluster score.
        """
        weight = self.config.weights.cluster

        # Check if wallet is in a cluster and we have amplifier
        if not signal.cluster_id or self.cluster_amplifier is None:
            # Solo signal (AC3)
            components = ClusterScoreComponents(
                cluster_size=1,
                is_solo_signal=True,
            )

            return (
                FactorScore(
                    category=ScoreCategory.CLUSTER,
                    score=SOLO_SIGNAL_BASE,
                    weight=weight,
                    weighted_contribution=SOLO_SIGNAL_BASE * weight,
                    components={"is_solo": 1.0, "base_score": SOLO_SIGNAL_BASE},
                    explanation="Solo signal - base cluster score applied",
                ),
                components,
            )

        # Get cluster amplification (from Story 2.6)
        try:
            amplification = await self.cluster_amplifier.calculate_amplification(
                cluster_id=signal.cluster_id,
                token_address=signal.token_address,
            )
        except Exception as e:
            logger.warning(
                "cluster_amplification_error",
                cluster_id=signal.cluster_id,
                error=str(e),
            )
            amplification = None

        if not amplification:
            components = ClusterScoreComponents(is_solo_signal=True)
            return (
                FactorScore(
                    category=ScoreCategory.CLUSTER,
                    score=SOLO_SIGNAL_BASE,
                    weight=weight,
                    weighted_contribution=SOLO_SIGNAL_BASE * weight,
                    components={"is_solo": 1.0},
                    explanation="No cluster amplification data",
                ),
                components,
            )

        # Calculate cluster score from amplification
        # Amplification factor is typically 1.0-1.8
        # Map to score: (factor - 1.0) / 0.8 for 1.0-1.8 range
        factor = amplification.amplification_factor
        cluster_score = min(1.0, (factor - 1.0) / 0.8 + SOLO_SIGNAL_BASE)

        components = ClusterScoreComponents(
            cluster_size=amplification.cluster_activity.member_count,
            active_members_count=amplification.cluster_activity.active_in_window,
            participation_rate=amplification.cluster_activity.participation_rate,
            amplification_factor=factor,
            cluster_strength=amplification.cluster_activity.cluster_strength,
            is_solo_signal=False,
        )

        return (
            FactorScore(
                category=ScoreCategory.CLUSTER,
                score=cluster_score,
                weight=weight,
                weighted_contribution=cluster_score * weight,
                components={
                    "amplification_factor": factor,
                    "participation_rate": components.participation_rate,
                    "cluster_strength": components.cluster_strength,
                },
                explanation=f"Cluster amplification: {factor:.2f}x",
            ),
            components,
        )

    def _calculate_token_score(
        self,
        token: TokenCharacteristics,
    ) -> tuple[FactorScore, TokenScoreComponents]:
        """Calculate token score (AC4).

        Components:
        - Liquidity (30%)
        - Market cap (25%)
        - Holder distribution (20%)
        - Volume (25%)
        - New token penalty
        - Honeypot risk
        """
        # Liquidity score (higher is better, with optimal ceiling)
        liquidity_usd = token.liquidity.usd if token.liquidity else 0
        if liquidity_usd < MIN_LIQUIDITY_USD:
            liquidity_score = 0.0
        elif liquidity_usd >= OPTIMAL_LIQUIDITY_USD:
            liquidity_score = 1.0
        else:
            liquidity_score = (liquidity_usd - MIN_LIQUIDITY_USD) / (
                OPTIMAL_LIQUIDITY_USD - MIN_LIQUIDITY_USD
            )

        # Market cap score
        mcap = token.market_cap_usd or 0
        if mcap < MIN_MARKET_CAP_USD:
            mcap_score = 0.2  # Low but not zero
        elif mcap >= OPTIMAL_MARKET_CAP_USD:
            mcap_score = 1.0
        else:
            mcap_score = 0.2 + 0.8 * (mcap - MIN_MARKET_CAP_USD) / (
                OPTIMAL_MARKET_CAP_USD - MIN_MARKET_CAP_USD
            )

        # Holder distribution score
        holder_score = 0.5  # Default
        if token.holder_count:
            # More holders is better
            holder_score = min(1.0, token.holder_count / 500)

        if token.top_10_holder_percentage:
            # Penalize concentrated holdings
            concentration_penalty = max(0, (token.top_10_holder_percentage - 30) / 70)
            holder_score -= concentration_penalty * 0.3

        holder_score = max(0.0, holder_score)  # Ensure non-negative

        # Volume score (24h)
        volume = token.volume.h24 if token.volume else 0
        volume_score = min(1.0, volume / 100000) if volume > 0 else 0.3

        # Base token score
        base_score = (
            liquidity_score * LIQUIDITY_WEIGHT
            + mcap_score * MARKET_CAP_WEIGHT
            + holder_score * HOLDER_DIST_WEIGHT
            + volume_score * VOLUME_WEIGHT
        )

        # Age penalty for very new tokens (AC4)
        age_penalty = 0.0
        if token.is_new_token and token.age_minutes < NEW_TOKEN_PENALTY_MINUTES:
            age_penalty = MAX_NEW_TOKEN_PENALTY * (
                1 - token.age_minutes / NEW_TOKEN_PENALTY_MINUTES
            )

        # Honeypot risk (AC4)
        honeypot_risk = 0.0
        if token.is_honeypot:
            honeypot_risk = 0.5
        elif token.has_freeze_authority or token.has_mint_authority:
            honeypot_risk = 0.2

        # Final token score
        final_score = max(0.0, min(1.0, base_score - age_penalty - honeypot_risk))

        weight = self.config.weights.token
        weighted_contribution = final_score * weight

        components = TokenScoreComponents(
            liquidity_score=liquidity_score,
            market_cap_score=mcap_score,
            holder_distribution_score=holder_score,
            volume_score=volume_score,
            age_penalty=age_penalty,
            honeypot_risk=honeypot_risk,
        )

        return (
            FactorScore(
                category=ScoreCategory.TOKEN,
                score=final_score,
                weight=weight,
                weighted_contribution=weighted_contribution,
                components={
                    "liquidity": liquidity_score,
                    "market_cap": mcap_score,
                    "holders": holder_score,
                    "volume": volume_score,
                    "age_penalty": age_penalty,
                    "honeypot_risk": honeypot_risk,
                },
                explanation=f"Token score: {final_score:.2f} (liq={liquidity_score:.2f})",
            ),
            components,
        )

    def _calculate_context_score(
        self,
        signal: SignalContext,
    ) -> tuple[FactorScore, ContextScoreComponents]:
        """Calculate context score (AC5).

        Components:
        - Time of day patterns
        - Market volatility (placeholder)
        - Recent activity (placeholder)
        """
        # Time of day score
        current_hour = signal.timestamp.hour
        if current_hour in PEAK_TRADING_HOURS_UTC:
            time_score = 1.0
        elif abs(current_hour - 16) <= 2:  # Near peak
            time_score = 0.8
        else:
            time_score = 0.6

        # Market volatility (placeholder - would integrate with market data)
        volatility_score = 0.7  # Default moderate

        # Recent activity score (placeholder)
        activity_score = 0.6

        # Combined context score
        final_score = (
            time_score * 0.4 + volatility_score * 0.35 + activity_score * 0.25
        )

        weight = self.config.weights.context
        weighted_contribution = final_score * weight

        components = ContextScoreComponents(
            time_of_day_score=time_score,
            market_volatility_score=volatility_score,
            recent_activity_score=activity_score,
        )

        return (
            FactorScore(
                category=ScoreCategory.CONTEXT,
                score=final_score,
                weight=weight,
                weighted_contribution=weighted_contribution,
                components={
                    "time_of_day": time_score,
                    "volatility": volatility_score,
                    "activity": activity_score,
                },
                explanation=f"Context score: {final_score:.2f} (hour={current_hour})",
            ),
            components,
        )

    def update_config(self, config: ScoringConfig) -> None:
        """Update scoring configuration (hot-reload)."""
        self.config = config
        logger.info(
            "scoring_config_updated",
            weights=config.weights.model_dump(),
        )


# Module-level singleton
_scorer: SignalScorer | None = None


def get_scorer(config: ScoringConfig | None = None) -> SignalScorer:
    """Get or create signal scorer singleton."""
    global _scorer
    if _scorer is None:
        _scorer = SignalScorer(config=config)
    return _scorer


def reset_scorer() -> None:
    """Reset scorer singleton (for testing)."""
    global _scorer
    _scorer = None
