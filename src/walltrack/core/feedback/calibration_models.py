"""Models for scoring model calibration."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class ScoringFactor(str, Enum):
    """Scoring model factors."""

    WALLET_SCORE = "wallet_score"
    CLUSTER_SCORE = "cluster_score"
    TOKEN_SCORE = "token_score"
    CONTEXT_SCORE = "context_score"


class CalibrationStatus(str, Enum):
    """Status of calibration suggestion."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    MODIFIED = "modified"


class FactorCorrelation(BaseModel):
    """Correlation analysis for a single factor."""

    factor: ScoringFactor = Field(..., description="The scoring factor")
    correlation: Decimal = Field(..., ge=-1, le=1, description="Pearson correlation with PnL")
    sample_size: int = Field(..., ge=0, description="Number of trades analyzed")
    avg_score_winners: Decimal = Field(
        ..., ge=0, le=1, description="Average score for winning trades"
    )
    avg_score_losers: Decimal = Field(
        ..., ge=0, le=1, description="Average score for losing trades"
    )
    p_value: Decimal | None = Field(default=None, description="Statistical significance")

    @computed_field
    @property
    def score_difference(self) -> Decimal:
        """Difference in average scores between winners and losers."""
        return self.avg_score_winners - self.avg_score_losers

    @computed_field
    @property
    def is_predictive(self) -> bool:
        """Whether factor shows predictive power."""
        return self.score_difference > Decimal("0.05") and self.correlation > Decimal("0.1")


class WeightSet(BaseModel):
    """Set of scoring weights."""

    wallet_weight: Decimal = Field(..., ge=0, le=1, description="Wallet score weight")
    cluster_weight: Decimal = Field(..., ge=0, le=1, description="Cluster score weight")
    token_weight: Decimal = Field(..., ge=0, le=1, description="Token score weight")
    context_weight: Decimal = Field(..., ge=0, le=1, description="Context score weight")

    @computed_field
    @property
    def total_weight(self) -> Decimal:
        """Sum of all weights."""
        return (
            self.wallet_weight + self.cluster_weight + self.token_weight + self.context_weight
        )

    @computed_field
    @property
    def is_normalized(self) -> bool:
        """Whether weights sum to approximately 1."""
        return abs(self.total_weight - Decimal("1")) < Decimal("0.01")


class CalibrationAnalysis(BaseModel):
    """Complete calibration analysis results."""

    id: UUID = Field(..., description="Analysis ID")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trade_count: int = Field(..., ge=0, description="Total trades analyzed")
    min_trades_required: int = Field(default=100, description="Minimum trades for valid analysis")
    correlations: list[FactorCorrelation] = Field(default_factory=list)
    current_weights: WeightSet = Field(..., description="Current scoring weights")
    suggested_weights: WeightSet = Field(..., description="Suggested new weights")
    estimated_improvement: Decimal = Field(
        default=Decimal("0"),
        description="Estimated win rate improvement %",
    )

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Whether analysis has sufficient data."""
        return self.trade_count >= self.min_trades_required


class WeightSuggestion(BaseModel):
    """A weight change suggestion."""

    factor: ScoringFactor = Field(..., description="Factor to adjust")
    current_weight: Decimal = Field(..., description="Current weight")
    suggested_weight: Decimal = Field(..., description="Suggested weight")
    change_percent: Decimal = Field(..., description="Percentage change")
    rationale: str = Field(..., description="Reason for suggestion")


class CalibrationSuggestion(BaseModel):
    """Complete calibration suggestion for operator review."""

    id: UUID = Field(..., description="Suggestion ID")
    analysis_id: UUID = Field(..., description="Source analysis ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    status: CalibrationStatus = Field(default=CalibrationStatus.PENDING)
    current_weights: WeightSet = Field(..., description="Current weights")
    suggested_weights: WeightSet = Field(..., description="Suggested weights")
    suggestions: list[WeightSuggestion] = Field(default_factory=list)
    estimated_improvement: Decimal = Field(default=Decimal("0"))
    applied_at: datetime | None = Field(default=None)
    applied_weights: WeightSet | None = Field(
        default=None, description="Final applied weights"
    )
    operator_notes: str | None = Field(default=None)


class WeightArchive(BaseModel):
    """Archived weight configuration."""

    id: UUID = Field(..., description="Archive entry ID")
    weights: WeightSet = Field(..., description="Archived weights")
    active_from: datetime = Field(..., description="When weights became active")
    active_until: datetime = Field(..., description="When weights were replaced")
    suggestion_id: UUID | None = Field(default=None, description="Associated suggestion")
    performance_during: Decimal | None = Field(
        default=None,
        description="Win rate during this period",
    )


class ApplyWeightsRequest(BaseModel):
    """Request to apply new weights."""

    suggestion_id: UUID = Field(..., description="Suggestion to apply")
    modified_weights: WeightSet | None = Field(
        default=None,
        description="Modified weights (if operator adjusted)",
    )
    operator_notes: str | None = Field(default=None)


class AutoCalibrationConfig(BaseModel):
    """Configuration for automatic calibration."""

    enabled: bool = Field(default=False, description="Enable auto-calibration")
    min_trades_between: int = Field(
        default=100,
        ge=50,
        description="Minimum trades between calibrations",
    )
    max_weight_change: Decimal = Field(
        default=Decimal("0.1"),
        ge=0,
        le=Decimal("0.3"),
        description="Maximum weight change per calibration",
    )
    min_improvement_threshold: Decimal = Field(
        default=Decimal("2"),
        description="Minimum estimated improvement % to auto-apply",
    )
    log_all_changes: bool = Field(default=True, description="Log all auto changes")
