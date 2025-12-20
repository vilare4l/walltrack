"""Threshold domain models for trade eligibility."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class EligibilityStatus(str, Enum):
    """Trade eligibility status based on score."""

    TRADE_ELIGIBLE = "trade_eligible"
    BELOW_THRESHOLD = "below_threshold"
    HIGH_CONVICTION = "high_conviction"


class ConvictionTier(str, Enum):
    """Conviction tier for position sizing."""

    HIGH = "high"  # Score >= 0.85
    STANDARD = "standard"  # Score 0.70-0.84
    NONE = "none"  # Score < 0.70


class ThresholdConfig(BaseModel):
    """Threshold configuration for trade eligibility."""

    # Base threshold (AC1)
    trade_threshold: float = Field(default=0.70, ge=0.0, le=1.0)

    # Position sizing tiers (AC4)
    high_conviction_threshold: float = Field(default=0.85, ge=0.0, le=1.0)

    # Position sizing multipliers
    high_conviction_multiplier: float = Field(default=1.5, ge=0.0)
    standard_multiplier: float = Field(default=1.0, ge=0.0)

    # Optional filters
    require_min_liquidity: bool = True
    min_liquidity_usd: float = Field(default=1000.0, ge=0)

    require_non_honeypot: bool = True

    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("high_conviction_threshold")
    @classmethod
    def validate_high_above_trade(cls, v: float, info) -> float:
        """High conviction must be above trade threshold."""
        trade_threshold = info.data.get("trade_threshold", 0.70)
        if v <= trade_threshold:
            raise ValueError(
                f"high_conviction_threshold ({v}) must be > trade_threshold ({trade_threshold})"
            )
        return v


class ThresholdResult(BaseModel):
    """Result of threshold check."""

    # Signal identification
    tx_signature: str
    wallet_address: str
    token_address: str

    # Score and status
    final_score: float = Field(..., ge=0.0, le=1.0)
    eligibility_status: EligibilityStatus
    conviction_tier: ConvictionTier

    # Position sizing
    position_multiplier: float = Field(..., ge=0.0)

    # Threshold used
    threshold_used: float
    margin_above_threshold: float | None = None

    # Additional checks
    passed_liquidity_check: bool = True
    passed_honeypot_check: bool = True
    filter_failures: list[str] = Field(default_factory=list)

    # Timing
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TradeEligibleSignal(BaseModel):
    """Signal that passed threshold and is ready for execution."""

    # From scored signal
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"
    amount_sol: float

    # Scoring
    final_score: float
    conviction_tier: ConvictionTier
    position_multiplier: float

    # Factor scores (for logging/analysis)
    wallet_score: float
    cluster_score: float
    token_score: float
    context_score: float

    # Ready for execution
    ready_for_execution: bool = True
    queued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
