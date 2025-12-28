"""Simplified scoring models for 2-component signal scoring.

Epic 14 Simplification: Reduced from 4 weighted factors (30+ params)
to 2-component model with binary token gate (~8 params).
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ScoreCategory(str, Enum):
    """Categories of signal scoring factors (simplified)."""

    WALLET = "wallet"
    CLUSTER = "cluster"


class ScoringConfig(BaseModel):
    """Simplified scoring configuration (~8 parameters).

    Replaces the complex 30+ parameter configuration with a lean,
    understandable set of tuning knobs.
    """

    # Single trade threshold (replaces dual HIGH/STANDARD thresholds)
    trade_threshold: float = Field(default=0.65, ge=0.0, le=1.0)

    # Wallet score weights (must sum to 1.0)
    wallet_win_rate_weight: float = Field(default=0.60, ge=0.0, le=1.0)
    wallet_pnl_weight: float = Field(default=0.40, ge=0.0, le=1.0)

    # Leader bonus (multiplier for cluster leaders)
    leader_bonus: float = Field(default=1.15, ge=1.0, le=2.0)

    # PnL normalization range
    pnl_normalize_min: float = Field(default=-100.0)
    pnl_normalize_max: float = Field(default=500.0)

    # Cluster boost range
    min_cluster_boost: float = Field(default=1.0, ge=1.0)
    max_cluster_boost: float = Field(default=1.8, ge=1.0, le=3.0)

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ScoredSignal(BaseModel):
    """Simplified scored signal result.

    Flat structure replacing the complex nested FactorScore structures.
    All fields are directly accessible without traversing nested objects.
    """

    # Signal identification
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"

    # Core scores (flat, not nested)
    final_score: float = Field(default=0.0, ge=0.0, le=1.0)
    wallet_score: float = Field(default=0.0, ge=0.0, le=1.0)
    cluster_boost: float = Field(default=1.0, ge=1.0)

    # Token safety (binary gate)
    token_safe: bool = True
    token_reject_reason: str | None = None

    # Context
    is_leader: bool = False
    cluster_id: str | None = None

    # Decision
    should_trade: bool = False
    position_multiplier: float = Field(default=1.0, ge=0.0)

    # Human-readable explanation
    explanation: str = ""

    # Metadata
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scoring_time_ms: float = 0.0

    @property
    def passed_threshold(self) -> bool:
        """Check if signal passed trade threshold."""
        return self.token_safe and self.should_trade


# ============================================================================
# Legacy Compatibility Layer
# ============================================================================
# The following classes are DEPRECATED but kept for backward compatibility
# during migration. They will be removed in a future version.


class FactorScore(BaseModel):
    """DEPRECATED: Individual factor score with breakdown.

    Kept for backward compatibility. Use ScoredSignal directly.
    """

    category: ScoreCategory
    score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, le=1.0)
    weighted_contribution: float = Field(default=0.0, ge=0.0)
    components: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class ScoringWeights(BaseModel):
    """DEPRECATED: Configurable weights for scoring factors.

    No longer used - wallet score is now the only factor.
    Cluster is a multiplier, not a weighted component.
    """

    wallet: float = Field(default=1.0, ge=0.0, le=1.0)
    cluster: float = Field(default=0.0, ge=0.0, le=1.0)
    token: float = Field(default=0.0, ge=0.0, le=1.0)
    context: float = Field(default=0.0, ge=0.0, le=1.0)


class WalletScoreComponents(BaseModel):
    """DEPRECATED: Components of wallet score calculation.

    Simplified to just win_rate and pnl_normalized.
    """

    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_pnl_percentage: float = Field(default=0.0)
    timing_percentile: float = Field(default=0.5, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_leader: bool = False
    leader_bonus: float = Field(default=0.0, ge=0.0)
    decay_penalty: float = Field(default=0.0, ge=0.0, le=0.5)


class ClusterScoreComponents(BaseModel):
    """DEPRECATED: Components of cluster score calculation.

    Cluster is now a simple boost multiplier (1.0-1.8x).
    """

    cluster_size: int = Field(default=1, ge=1)
    active_members_count: int = Field(default=0, ge=0)
    participation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    amplification_factor: float = Field(default=1.0, ge=1.0)
    cluster_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    is_solo_signal: bool = True


class TokenScoreComponents(BaseModel):
    """DEPRECATED: Components of token score calculation.

    Token is now a binary safety gate (honeypot, freeze, mint).
    """

    liquidity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_cap_score: float = Field(default=0.5, ge=0.0, le=1.0)
    holder_distribution_score: float = Field(default=0.5, ge=0.0, le=1.0)
    volume_score: float = Field(default=0.5, ge=0.0, le=1.0)
    age_penalty: float = Field(default=0.0, ge=0.0, le=0.5)
    honeypot_risk: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextScoreComponents(BaseModel):
    """DEPRECATED: Components of context score calculation.

    Context score has been removed (was 2/3 placeholder values).
    """

    time_of_day_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_volatility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_activity_score: float = Field(default=0.5, ge=0.0, le=1.0)
