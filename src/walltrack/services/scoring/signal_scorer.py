"""Simplified 2-component signal scoring engine.

Epic 14 Simplification:
- Token safety: Binary gate (honeypot, freeze, mint)
- Wallet score: win_rate (60%) + pnl_normalized (40%) + leader_bonus
- Cluster boost: Direct multiplier 1.0x to 1.8x
- Single threshold: 0.65

Epic 14 Story 14-5: Cluster info now comes from ClusterService.ClusterInfo,
not from WalletCacheEntry (which no longer caches cluster data).
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import structlog

from walltrack.models.scoring import ScoredSignal, ScoringConfig
from walltrack.models.signal_filter import WalletCacheEntry
from walltrack.models.token import TokenCharacteristics
from walltrack.services.cluster import ClusterInfo

logger = structlog.get_logger(__name__)


@dataclass
class SimpleScoringParams:
    """Runtime scoring parameters (simplified).

    Only 8 parameters instead of 30+.
    """

    trade_threshold: float
    wallet_win_rate_weight: float
    wallet_pnl_weight: float
    leader_bonus: float
    pnl_normalize_min: float
    pnl_normalize_max: float
    min_cluster_boost: float
    max_cluster_boost: float

    @classmethod
    def from_config(cls, config: ScoringConfig) -> "SimpleScoringParams":
        """Create params from ScoringConfig."""
        return cls(
            trade_threshold=config.trade_threshold,
            wallet_win_rate_weight=config.wallet_win_rate_weight,
            wallet_pnl_weight=config.wallet_pnl_weight,
            leader_bonus=config.leader_bonus,
            pnl_normalize_min=config.pnl_normalize_min,
            pnl_normalize_max=config.pnl_normalize_max,
            min_cluster_boost=config.min_cluster_boost,
            max_cluster_boost=config.max_cluster_boost,
        )

    @classmethod
    def defaults(cls) -> "SimpleScoringParams":
        """Create default params."""
        return cls.from_config(ScoringConfig())


class SignalScorer:
    """Simplified 2-component signal scorer.

    Scoring formula:
    1. Token Safety: Binary gate (honeypot, freeze, mint) -> reject or pass
    2. Wallet Score: win_rate * 0.6 + pnl_norm * 0.4 (* leader_bonus if leader)
    3. Cluster Boost: 1.0x to 1.8x multiplier
    4. Final: wallet_score * cluster_boost >= threshold -> TRADE

    This replaces the complex 4-factor weighted system with a simple,
    understandable model that can be tuned with ~8 parameters.
    """

    def __init__(self, config: ScoringConfig | None = None) -> None:
        """Initialize signal scorer.

        Args:
            config: Scoring configuration (uses defaults if None)
        """
        self.config = config or ScoringConfig()
        self._params = SimpleScoringParams.from_config(self.config)

    def score(
        self,
        wallet: WalletCacheEntry,
        token: TokenCharacteristics,
        tx_signature: str,
        direction: str = "buy",
        cluster_info: ClusterInfo | None = None,
    ) -> ScoredSignal:
        """Score a signal using simplified 2-component model.

        Args:
            wallet: Wallet cache entry with metrics
            token: Token characteristics including safety flags
            tx_signature: Transaction signature
            direction: Trade direction ("buy" or "sell")
            cluster_info: Cluster info from ClusterService (Epic 14-5)

        Returns:
            ScoredSignal with decision and explanation

        Epic 14 Story 14-5: Cluster data now comes from ClusterInfo parameter,
        fetched from Neo4j via ClusterService, not from WalletCacheEntry.
        """
        # Extract cluster info (with defaults for solo wallets)
        if cluster_info is None:
            cluster_info = ClusterInfo(
                cluster_id=None,
                is_leader=False,
                amplification_factor=1.0,
                cluster_size=0,
            )
        cluster_boost = cluster_info.amplification_factor
        is_leader = cluster_info.is_leader
        cluster_id = cluster_info.cluster_id
        start_time = time.perf_counter()
        params = self._params

        # Step 1: Token Safety Gate (binary)
        if not self._is_token_safe(token):
            reject_reason = self._get_token_reject_reason(token)
            scoring_time_ms = (time.perf_counter() - start_time) * 1000

            logger.info(
                "signal_token_rejected",
                wallet=wallet.wallet_address[:8] + "...",
                token=token.token_address[:8] + "...",
                reason=reject_reason,
            )

            return ScoredSignal(
                tx_signature=tx_signature,
                wallet_address=wallet.wallet_address,
                token_address=token.token_address,
                direction=direction,
                final_score=0.0,
                wallet_score=0.0,
                cluster_boost=cluster_boost,
                token_safe=False,
                token_reject_reason=reject_reason,
                is_leader=is_leader,
                cluster_id=cluster_id,
                should_trade=False,
                position_multiplier=1.0,
                explanation=f"Token rejected: {reject_reason}",
                scoring_time_ms=scoring_time_ms,
            )

        # Step 2: Calculate Wallet Score
        wallet_score = self._calculate_wallet_score(wallet, params, is_leader)

        # Step 3: Apply Cluster Boost (clamped to range)
        clamped_boost = max(
            params.min_cluster_boost,
            min(params.max_cluster_boost, cluster_boost),
        )
        final_score = min(1.0, wallet_score * clamped_boost)

        # Step 4: Threshold Decision
        should_trade = final_score >= params.trade_threshold

        # Build explanation
        explanation = self._build_explanation(
            wallet, wallet_score, clamped_boost, final_score, should_trade, params,
            is_leader=is_leader,
        )

        scoring_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "signal_scored",
            wallet=wallet.wallet_address[:8] + "...",
            token=token.token_address[:8] + "...",
            final_score=round(final_score, 4),
            wallet_score=round(wallet_score, 4),
            cluster_boost=round(clamped_boost, 2),
            is_leader=is_leader,
            should_trade=should_trade,
            scoring_time_ms=round(scoring_time_ms, 2),
        )

        return ScoredSignal(
            tx_signature=tx_signature,
            wallet_address=wallet.wallet_address,
            token_address=token.token_address,
            direction=direction,
            final_score=final_score,
            wallet_score=wallet_score,
            cluster_boost=clamped_boost,
            token_safe=True,
            is_leader=is_leader,
            cluster_id=cluster_id,
            should_trade=should_trade,
            position_multiplier=clamped_boost if should_trade else 1.0,
            explanation=explanation,
            scoring_time_ms=scoring_time_ms,
        )

    def _is_token_safe(self, token: TokenCharacteristics) -> bool:
        """Binary token safety check.

        Rejects tokens with:
        - is_honeypot = True
        - has_freeze_authority = True
        - has_mint_authority = True
        """
        if token.is_honeypot:
            return False
        if token.has_freeze_authority:
            return False
        if token.has_mint_authority:
            return False
        return True

    def _get_token_reject_reason(self, token: TokenCharacteristics) -> str:
        """Get reason for token rejection."""
        if token.is_honeypot:
            return "honeypot"
        if token.has_freeze_authority:
            return "freeze_authority"
        if token.has_mint_authority:
            return "mint_authority"
        return "unknown"

    def _calculate_wallet_score(
        self,
        wallet: WalletCacheEntry,
        params: SimpleScoringParams,
        is_leader: bool = False,
    ) -> float:
        """Calculate wallet score from win_rate and PnL.

        Formula: (win_rate * 0.6 + pnl_norm * 0.4) * leader_bonus

        Args:
            wallet: Wallet cache entry
            params: Scoring parameters
            is_leader: Whether wallet is a cluster leader (from ClusterInfo)

        Returns:
            Wallet score between 0.0 and 1.0
        """
        # Win rate component (already 0-1)
        win_rate = wallet.reputation_score if wallet.reputation_score is not None else 0.5

        # PnL normalized to 0-1 range
        # Note: WalletCacheEntry doesn't have avg_pnl, use reputation_score
        # In a full implementation, this would come from wallet profile
        pnl_norm = 0.5  # Default middle value

        # Base score using configurable weights
        base_score = (
            win_rate * params.wallet_win_rate_weight
            + pnl_norm * params.wallet_pnl_weight
        )

        # Apply leader bonus (multiplier, not additive)
        if is_leader:
            base_score *= params.leader_bonus

        return min(1.0, base_score)

    def _normalize_pnl(self, pnl: float, params: SimpleScoringParams) -> float:
        """Normalize PnL to 0-1 range.

        Args:
            pnl: Raw PnL value
            params: Scoring parameters with normalization range

        Returns:
            Normalized PnL between 0.0 and 1.0
        """
        pnl_min = params.pnl_normalize_min
        pnl_max = params.pnl_normalize_max

        if pnl <= pnl_min:
            return 0.0
        if pnl >= pnl_max:
            return 1.0

        return (pnl - pnl_min) / (pnl_max - pnl_min)

    def _build_explanation(
        self,
        wallet: WalletCacheEntry,
        wallet_score: float,
        cluster_boost: float,
        final_score: float,
        should_trade: bool,
        params: SimpleScoringParams,
        *,
        is_leader: bool = False,
    ) -> str:
        """Build human-readable explanation.

        Args:
            wallet: Wallet cache entry
            wallet_score: Calculated wallet score
            cluster_boost: Applied cluster boost
            final_score: Final calculated score
            should_trade: Whether threshold was passed
            params: Scoring parameters
            is_leader: Whether wallet is a cluster leader (from ClusterInfo)

        Returns:
            Human-readable explanation string
        """
        rep_display = wallet.reputation_score if wallet.reputation_score is not None else 0.5
        parts = [
            f"Wallet: {wallet_score:.2f} (rep:{rep_display:.2f})",
        ]

        if is_leader:
            parts.append(f"Leader: {params.leader_bonus:.2f}x")

        if cluster_boost > 1.0:
            parts.append(f"Cluster: {cluster_boost:.2f}x")

        parts.append(f"Final: {final_score:.2f}")

        if should_trade:
            parts.append(f"TRADE (>={params.trade_threshold})")
        else:
            parts.append(f"NO TRADE (<{params.trade_threshold})")

        return " | ".join(parts)

    def update_config(self, config: ScoringConfig) -> None:
        """Update scoring configuration.

        Args:
            config: New scoring configuration
        """
        self.config = config
        self._params = SimpleScoringParams.from_config(config)
        logger.info(
            "scoring_config_updated",
            threshold=config.trade_threshold,
            leader_bonus=config.leader_bonus,
            max_cluster_boost=config.max_cluster_boost,
        )


# Module-level singleton
_scorer: SignalScorer | None = None


def get_scorer(config: ScoringConfig | None = None) -> SignalScorer:
    """Get or create signal scorer singleton.

    Args:
        config: Optional scoring configuration

    Returns:
        SignalScorer singleton instance
    """
    global _scorer
    if _scorer is None:
        _scorer = SignalScorer(config=config)
    return _scorer


def reset_scorer() -> None:
    """Reset scorer singleton (for testing)."""
    global _scorer
    _scorer = None
