"""Configuration data models for dynamic configuration stored in Supabase."""

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Scoring factor weights for signal evaluation."""

    wallet: float = Field(default=0.30, ge=0.0, le=1.0, description="Wallet factor weight")
    cluster: float = Field(default=0.25, ge=0.0, le=1.0, description="Cluster factor weight")
    token: float = Field(default=0.25, ge=0.0, le=1.0, description="Token factor weight")
    context: float = Field(default=0.20, ge=0.0, le=1.0, description="Context factor weight")

    def validate_sum(self) -> bool:
        """Validate that weights sum to 1.0 (within tolerance)."""
        return abs(self.wallet + self.cluster + self.token + self.context - 1.0) < 0.01


class DynamicConfig(BaseModel):
    """Dynamic configuration stored in Supabase.

    These values can be modified at runtime through the dashboard
    without requiring an application restart.
    """

    scoring_weights: ScoringWeights = Field(
        default_factory=ScoringWeights,
        description="Scoring factor weights",
    )
    score_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Minimum score for trade eligibility",
    )
    high_conviction_threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Score threshold for high conviction trades",
    )
    drawdown_threshold_pct: float = Field(
        default=20.0,
        ge=5.0,
        le=50.0,
        description="Drawdown % to trigger circuit breaker",
    )
    win_rate_threshold_pct: float = Field(
        default=40.0,
        ge=20.0,
        le=60.0,
        description="Win rate % to trigger circuit breaker",
    )
    max_concurrent_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent open positions",
    )
