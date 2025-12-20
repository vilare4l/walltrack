"""Scoring domain models for multi-factor signal scoring."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class ScoreCategory(str, Enum):
    """Categories of signal scoring factors."""

    WALLET = "wallet"
    CLUSTER = "cluster"
    TOKEN = "token"
    CONTEXT = "context"


class FactorScore(BaseModel):
    """Individual factor score with breakdown."""

    category: ScoreCategory
    score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    weighted_contribution: float = Field(..., ge=0.0)
    components: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class WalletScoreComponents(BaseModel):
    """Components of wallet score calculation."""

    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_pnl_percentage: float = Field(default=0.0)
    timing_percentile: float = Field(default=0.5, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_leader: bool = False
    leader_bonus: float = Field(default=0.0, ge=0.0)
    decay_penalty: float = Field(default=0.0, ge=0.0, le=0.5)


class ClusterScoreComponents(BaseModel):
    """Components of cluster score calculation."""

    cluster_size: int = Field(default=1, ge=1)
    active_members_count: int = Field(default=0, ge=0)
    participation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    amplification_factor: float = Field(default=1.0, ge=1.0)
    cluster_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    is_solo_signal: bool = True


class TokenScoreComponents(BaseModel):
    """Components of token score calculation."""

    liquidity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_cap_score: float = Field(default=0.5, ge=0.0, le=1.0)
    holder_distribution_score: float = Field(default=0.5, ge=0.0, le=1.0)
    volume_score: float = Field(default=0.5, ge=0.0, le=1.0)
    age_penalty: float = Field(default=0.0, ge=0.0, le=0.5)
    honeypot_risk: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextScoreComponents(BaseModel):
    """Components of context score calculation."""

    time_of_day_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_volatility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_activity_score: float = Field(default=0.5, ge=0.0, le=1.0)


class ScoringWeights(BaseModel):
    """Configurable weights for scoring factors."""

    wallet: float = Field(default=0.30, ge=0.0, le=1.0)
    cluster: float = Field(default=0.25, ge=0.0, le=1.0)
    token: float = Field(default=0.25, ge=0.0, le=1.0)
    context: float = Field(default=0.20, ge=0.0, le=1.0)

    @field_validator("context")
    @classmethod
    def validate_weights_sum(cls, v: float, info) -> float:
        """Ensure weights sum to 1.0."""
        values = info.data
        total = (
            values.get("wallet", 0.3)
            + values.get("cluster", 0.25)
            + values.get("token", 0.25)
            + v
        )
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class ScoredSignal(BaseModel):
    """Signal with complete scoring breakdown."""

    # Signal identification
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str

    # Final score
    final_score: float = Field(..., ge=0.0, le=1.0)

    # Factor breakdowns
    wallet_score: FactorScore
    cluster_score: FactorScore
    token_score: FactorScore
    context_score: FactorScore

    # Detailed components (for analysis)
    wallet_components: WalletScoreComponents
    cluster_components: ClusterScoreComponents
    token_components: TokenScoreComponents
    context_components: ContextScoreComponents

    # Metadata
    weights_used: ScoringWeights
    scored_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    scoring_time_ms: float = 0.0


class ScoringConfig(BaseModel):
    """Complete scoring configuration from database."""

    weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Wallet scoring params
    leader_bonus_multiplier: float = 0.15
    decay_penalty_max: float = 0.3
    min_trades_for_stats: int = 5

    # Token scoring params
    min_liquidity_usd: float = 1000.0
    optimal_liquidity_usd: float = 50000.0
    new_token_age_penalty_minutes: int = 5
    max_age_penalty: float = 0.3

    # Cluster scoring params
    solo_signal_base_score: float = 0.5
    min_cluster_participation: float = 0.3

    # Context scoring params
    peak_hours_utc: list[int] = Field(default_factory=lambda: [14, 15, 16, 17, 18])
    high_volatility_threshold: float = 0.1

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
