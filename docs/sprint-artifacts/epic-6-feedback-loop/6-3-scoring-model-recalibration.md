# Story 6.3: Scoring Model Weight Recalibration

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: Medium
- **FR**: FR36

## User Story

**As an** operator,
**I want** the scoring model to recalibrate based on results,
**So that** the system improves its predictions over time.

## Acceptance Criteria

### AC 1: Correlation Analysis
**Given** sufficient trade history (N trades, default 100)
**When** recalibration is triggered
**Then** correlation between each factor score and trade outcome is calculated:
- Wallet score vs actual PnL
- Cluster score vs actual PnL
- Token score vs actual PnL
- Context score vs actual PnL

### AC 2: Weight Suggestion
**Given** recalibration analysis complete
**When** new weights are suggested
**Then** suggested weights are displayed to operator
**And** comparison to current weights is shown
**And** expected improvement is estimated

### AC 3: Apply Weights
**Given** operator approves new weights
**When** weights are applied
**Then** scoring model uses new weights
**And** previous weights are archived
**And** recalibration timestamp is recorded

### AC 4: Manual Adjustment
**Given** recalibration suggestion
**When** operator rejects or modifies
**Then** operator can adjust weights manually
**And** custom weights are applied instead

### AC 5: Auto Recalibration (Optional)
**Given** automatic recalibration mode (optional)
**When** enabled
**Then** weights auto-adjust within bounds
**And** changes are logged for review

## Technical Notes

- FR36: Recalibrate scoring model weights based on results
- Implement in `src/walltrack/core/feedback/model_calibrator.py`
- Use simple correlation analysis initially (ML optimization in V2)

---

## Technical Specification

### Pydantic Models

```python
# src/walltrack/core/feedback/calibration_models.py
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from uuid import UUID


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
    avg_score_winners: Decimal = Field(..., ge=0, le=1, description="Average score for winning trades")
    avg_score_losers: Decimal = Field(..., ge=0, le=1, description="Average score for losing trades")
    p_value: Optional[Decimal] = Field(default=None, description="Statistical significance")

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
        return self.wallet_weight + self.cluster_weight + self.token_weight + self.context_weight

    @computed_field
    @property
    def is_normalized(self) -> bool:
        """Whether weights sum to approximately 1."""
        return abs(self.total_weight - Decimal("1")) < Decimal("0.01")


class CalibrationAnalysis(BaseModel):
    """Complete calibration analysis results."""
    id: UUID = Field(..., description="Analysis ID")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    trade_count: int = Field(..., ge=0, description="Total trades analyzed")
    min_trades_required: int = Field(default=100, description="Minimum trades for valid analysis")
    correlations: list[FactorCorrelation] = Field(default_factory=list)
    current_weights: WeightSet = Field(..., description="Current scoring weights")
    suggested_weights: WeightSet = Field(..., description="Suggested new weights")
    estimated_improvement: Decimal = Field(
        default=Decimal("0"),
        description="Estimated win rate improvement %"
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
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: CalibrationStatus = Field(default=CalibrationStatus.PENDING)
    current_weights: WeightSet = Field(..., description="Current weights")
    suggested_weights: WeightSet = Field(..., description="Suggested weights")
    suggestions: list[WeightSuggestion] = Field(default_factory=list)
    estimated_improvement: Decimal = Field(default=Decimal("0"))
    applied_at: Optional[datetime] = Field(default=None)
    applied_weights: Optional[WeightSet] = Field(default=None, description="Final applied weights")
    operator_notes: Optional[str] = Field(default=None)


class WeightArchive(BaseModel):
    """Archived weight configuration."""
    id: UUID = Field(..., description="Archive entry ID")
    weights: WeightSet = Field(..., description="Archived weights")
    active_from: datetime = Field(..., description="When weights became active")
    active_until: datetime = Field(..., description="When weights were replaced")
    suggestion_id: Optional[UUID] = Field(default=None, description="Associated suggestion")
    performance_during: Optional[Decimal] = Field(
        default=None,
        description="Win rate during this period"
    )


class ApplyWeightsRequest(BaseModel):
    """Request to apply new weights."""
    suggestion_id: UUID = Field(..., description="Suggestion to apply")
    modified_weights: Optional[WeightSet] = Field(
        default=None,
        description="Modified weights (if operator adjusted)"
    )
    operator_notes: Optional[str] = Field(default=None)


class AutoCalibrationConfig(BaseModel):
    """Configuration for automatic calibration."""
    enabled: bool = Field(default=False, description="Enable auto-calibration")
    min_trades_between: int = Field(
        default=100,
        ge=50,
        description="Minimum trades between calibrations"
    )
    max_weight_change: Decimal = Field(
        default=Decimal("0.1"),
        ge=0,
        le=Decimal("0.3"),
        description="Maximum weight change per calibration"
    )
    min_improvement_threshold: Decimal = Field(
        default=Decimal("2"),
        description="Minimum estimated improvement % to auto-apply"
    )
    log_all_changes: bool = Field(default=True, description="Log all auto changes")
```

### Service Implementation

```python
# src/walltrack/core/feedback/model_calibrator.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from statistics import correlation

from .calibration_models import (
    ScoringFactor,
    CalibrationStatus,
    FactorCorrelation,
    WeightSet,
    CalibrationAnalysis,
    WeightSuggestion,
    CalibrationSuggestion,
    WeightArchive,
    ApplyWeightsRequest,
    AutoCalibrationConfig,
)

logger = structlog.get_logger()


class ModelCalibrator:
    """Calibrates scoring model weights based on trade outcomes."""

    def __init__(
        self,
        supabase_client,
        auto_config: Optional[AutoCalibrationConfig] = None,
    ):
        self.supabase = supabase_client
        self.auto_config = auto_config or AutoCalibrationConfig()
        self._current_weights: Optional[WeightSet] = None

    async def run_analysis(
        self,
        min_trades: int = 100,
    ) -> CalibrationAnalysis:
        """
        Run calibration analysis on trade history.

        Args:
            min_trades: Minimum trades required for valid analysis

        Returns:
            CalibrationAnalysis with correlations and suggestions
        """
        analysis_id = uuid4()

        # Load trade data with factor scores
        trades = await self._load_trade_data()

        if len(trades) < min_trades:
            logger.warning(
                "insufficient_trades_for_calibration",
                trade_count=len(trades),
                min_required=min_trades,
            )

        # Calculate correlations for each factor
        correlations = []
        for factor in ScoringFactor:
            correlation_result = self._calculate_factor_correlation(trades, factor)
            correlations.append(correlation_result)

        # Get current weights
        current_weights = await self.get_current_weights()

        # Generate suggested weights
        suggested_weights = self._generate_suggested_weights(correlations, current_weights)

        # Estimate improvement
        improvement = self._estimate_improvement(trades, current_weights, suggested_weights)

        analysis = CalibrationAnalysis(
            id=analysis_id,
            trade_count=len(trades),
            min_trades_required=min_trades,
            correlations=correlations,
            current_weights=current_weights,
            suggested_weights=suggested_weights,
            estimated_improvement=improvement,
        )

        # Persist analysis
        await self._save_analysis(analysis)

        logger.info(
            "calibration_analysis_complete",
            analysis_id=str(analysis_id),
            trade_count=len(trades),
            estimated_improvement=float(improvement),
        )

        return analysis

    async def create_suggestion(
        self,
        analysis: CalibrationAnalysis,
    ) -> CalibrationSuggestion:
        """
        Create a calibration suggestion from analysis.

        Args:
            analysis: Completed calibration analysis

        Returns:
            CalibrationSuggestion for operator review
        """
        suggestion_id = uuid4()

        # Build individual factor suggestions
        suggestions = []
        factor_mapping = {
            ScoringFactor.WALLET_SCORE: ("wallet_weight", analysis.current_weights.wallet_weight, analysis.suggested_weights.wallet_weight),
            ScoringFactor.CLUSTER_SCORE: ("cluster_weight", analysis.current_weights.cluster_weight, analysis.suggested_weights.cluster_weight),
            ScoringFactor.TOKEN_SCORE: ("token_weight", analysis.current_weights.token_weight, analysis.suggested_weights.token_weight),
            ScoringFactor.CONTEXT_SCORE: ("context_weight", analysis.current_weights.context_weight, analysis.suggested_weights.context_weight),
        }

        for factor, (attr, current, suggested) in factor_mapping.items():
            if current != suggested:
                change_pct = ((suggested - current) / current * 100) if current > 0 else Decimal("100")
                correlation_info = next((c for c in analysis.correlations if c.factor == factor), None)

                rationale = self._generate_rationale(factor, correlation_info, change_pct)

                suggestions.append(WeightSuggestion(
                    factor=factor,
                    current_weight=current,
                    suggested_weight=suggested,
                    change_percent=change_pct,
                    rationale=rationale,
                ))

        suggestion = CalibrationSuggestion(
            id=suggestion_id,
            analysis_id=analysis.id,
            current_weights=analysis.current_weights,
            suggested_weights=analysis.suggested_weights,
            suggestions=suggestions,
            estimated_improvement=analysis.estimated_improvement,
        )

        await self._save_suggestion(suggestion)

        logger.info(
            "calibration_suggestion_created",
            suggestion_id=str(suggestion_id),
            num_changes=len(suggestions),
        )

        return suggestion

    async def apply_weights(
        self,
        request: ApplyWeightsRequest,
    ) -> CalibrationSuggestion:
        """
        Apply new weights from a suggestion.

        Args:
            request: Apply weights request

        Returns:
            Updated CalibrationSuggestion
        """
        # Load suggestion
        suggestion = await self.get_suggestion(request.suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion {request.suggestion_id} not found")

        if suggestion.status != CalibrationStatus.PENDING:
            raise ValueError(f"Suggestion already processed: {suggestion.status}")

        # Determine final weights
        if request.modified_weights:
            final_weights = request.modified_weights
            suggestion.status = CalibrationStatus.MODIFIED
        else:
            final_weights = suggestion.suggested_weights
            suggestion.status = CalibrationStatus.APPROVED

        # Archive current weights
        await self._archive_weights(suggestion.current_weights, suggestion.id)

        # Apply new weights
        await self._update_weights(final_weights)

        # Update suggestion
        suggestion.applied_at = datetime.utcnow()
        suggestion.applied_weights = final_weights
        suggestion.operator_notes = request.operator_notes

        await self._save_suggestion(suggestion)

        logger.info(
            "weights_applied",
            suggestion_id=str(suggestion.id),
            status=suggestion.status.value,
            weights=final_weights.model_dump(),
        )

        return suggestion

    async def reject_suggestion(
        self,
        suggestion_id: UUID,
        reason: Optional[str] = None,
    ) -> CalibrationSuggestion:
        """
        Reject a calibration suggestion.

        Args:
            suggestion_id: Suggestion to reject
            reason: Optional rejection reason

        Returns:
            Updated CalibrationSuggestion
        """
        suggestion = await self.get_suggestion(suggestion_id)
        if not suggestion:
            raise ValueError(f"Suggestion {suggestion_id} not found")

        suggestion.status = CalibrationStatus.REJECTED
        suggestion.operator_notes = reason

        await self._save_suggestion(suggestion)

        logger.info(
            "suggestion_rejected",
            suggestion_id=str(suggestion_id),
            reason=reason,
        )

        return suggestion

    async def get_current_weights(self) -> WeightSet:
        """Get current scoring weights."""
        if self._current_weights:
            return self._current_weights

        result = await self.supabase.table("scoring_weights").select("*").eq(
            "id", "current"
        ).single().execute()

        if result.data:
            self._current_weights = WeightSet(**result.data)
        else:
            # Default weights
            self._current_weights = WeightSet(
                wallet_weight=Decimal("0.35"),
                cluster_weight=Decimal("0.25"),
                token_weight=Decimal("0.25"),
                context_weight=Decimal("0.15"),
            )

        return self._current_weights

    async def get_suggestion(self, suggestion_id: UUID) -> Optional[CalibrationSuggestion]:
        """Get a calibration suggestion by ID."""
        result = await self.supabase.table("calibration_suggestions").select("*").eq(
            "id", str(suggestion_id)
        ).single().execute()

        if result.data:
            return CalibrationSuggestion(**result.data)
        return None

    async def get_weight_history(self, limit: int = 10) -> list[WeightArchive]:
        """Get archived weight configurations."""
        result = await self.supabase.table("weight_archive").select("*").order(
            "active_until", desc=True
        ).limit(limit).execute()

        return [WeightArchive(**w) for w in result.data]

    async def check_auto_calibration(self) -> Optional[CalibrationSuggestion]:
        """
        Check if auto-calibration should run.

        Returns:
            CalibrationSuggestion if auto-applied, None otherwise
        """
        if not self.auto_config.enabled:
            return None

        # Check trades since last calibration
        trades_since = await self._count_trades_since_calibration()

        if trades_since < self.auto_config.min_trades_between:
            return None

        # Run analysis
        analysis = await self.run_analysis()

        if not analysis.is_valid:
            return None

        if analysis.estimated_improvement < self.auto_config.min_improvement_threshold:
            logger.info(
                "auto_calibration_skipped",
                improvement=float(analysis.estimated_improvement),
                threshold=float(self.auto_config.min_improvement_threshold),
            )
            return None

        # Limit weight changes
        bounded_weights = self._bound_weight_changes(
            analysis.current_weights,
            analysis.suggested_weights,
            self.auto_config.max_weight_change,
        )

        # Create and apply suggestion
        suggestion = await self.create_suggestion(analysis)

        await self.apply_weights(ApplyWeightsRequest(
            suggestion_id=suggestion.id,
            modified_weights=bounded_weights,
            operator_notes="Auto-calibration applied",
        ))

        logger.info(
            "auto_calibration_applied",
            suggestion_id=str(suggestion.id),
            improvement=float(analysis.estimated_improvement),
        )

        return suggestion

    def _calculate_factor_correlation(
        self,
        trades: list[dict],
        factor: ScoringFactor,
    ) -> FactorCorrelation:
        """Calculate correlation between factor and trade outcome."""
        factor_key = f"{factor.value}"
        scores = [Decimal(str(t.get(factor_key, 0))) for t in trades]
        pnls = [Decimal(str(t.get("pnl_percent", 0))) for t in trades]

        # Calculate Pearson correlation
        if len(scores) > 2:
            corr = Decimal(str(correlation(
                [float(s) for s in scores],
                [float(p) for p in pnls]
            )))
        else:
            corr = Decimal("0")

        winners = [t for t in trades if t.get("is_win")]
        losers = [t for t in trades if not t.get("is_win")]

        avg_winners = (
            sum(Decimal(str(t.get(factor_key, 0))) for t in winners) / len(winners)
            if winners else Decimal("0")
        )
        avg_losers = (
            sum(Decimal(str(t.get(factor_key, 0))) for t in losers) / len(losers)
            if losers else Decimal("0")
        )

        return FactorCorrelation(
            factor=factor,
            correlation=corr,
            sample_size=len(trades),
            avg_score_winners=avg_winners,
            avg_score_losers=avg_losers,
        )

    def _generate_suggested_weights(
        self,
        correlations: list[FactorCorrelation],
        current: WeightSet,
    ) -> WeightSet:
        """Generate suggested weights based on correlations."""
        # Weight factors by correlation strength
        total_corr = sum(max(c.correlation, Decimal("0.01")) for c in correlations)

        weights = {}
        factor_to_attr = {
            ScoringFactor.WALLET_SCORE: "wallet_weight",
            ScoringFactor.CLUSTER_SCORE: "cluster_weight",
            ScoringFactor.TOKEN_SCORE: "token_weight",
            ScoringFactor.CONTEXT_SCORE: "context_weight",
        }

        for corr in correlations:
            attr = factor_to_attr[corr.factor]
            # Blend current weight with correlation-based weight
            corr_weight = max(corr.correlation, Decimal("0.01")) / total_corr
            current_weight = getattr(current, attr)
            # 70% correlation-based, 30% current (conservative)
            weights[attr] = (corr_weight * Decimal("0.7")) + (current_weight * Decimal("0.3"))

        # Normalize to sum to 1
        total = sum(weights.values())
        normalized = {k: v / total for k, v in weights.items()}

        return WeightSet(**normalized)

    def _estimate_improvement(
        self,
        trades: list[dict],
        current: WeightSet,
        suggested: WeightSet,
    ) -> Decimal:
        """Estimate win rate improvement from weight changes."""
        # Simple simulation: re-score trades with new weights
        current_wins = 0
        suggested_wins = 0

        threshold = Decimal("0.6")  # Assumed trading threshold

        for trade in trades:
            current_score = self._calculate_score(trade, current)
            suggested_score = self._calculate_score(trade, suggested)

            # Would have traded?
            if current_score >= threshold and trade.get("is_win"):
                current_wins += 1
            if suggested_score >= threshold and trade.get("is_win"):
                suggested_wins += 1

        if current_wins == 0:
            return Decimal("0")

        improvement = ((suggested_wins - current_wins) / current_wins) * 100
        return Decimal(str(improvement)).quantize(Decimal("0.01"))

    def _calculate_score(self, trade: dict, weights: WeightSet) -> Decimal:
        """Calculate composite score for a trade."""
        return (
            Decimal(str(trade.get("wallet_score", 0))) * weights.wallet_weight +
            Decimal(str(trade.get("cluster_score", 0))) * weights.cluster_weight +
            Decimal(str(trade.get("token_score", 0))) * weights.token_weight +
            Decimal(str(trade.get("context_score", 0))) * weights.context_weight
        )

    def _generate_rationale(
        self,
        factor: ScoringFactor,
        correlation: Optional[FactorCorrelation],
        change_pct: Decimal,
    ) -> str:
        """Generate human-readable rationale for weight change."""
        direction = "increase" if change_pct > 0 else "decrease"

        if not correlation:
            return f"Suggested {direction} based on overall model performance"

        if correlation.is_predictive:
            return (
                f"Strong predictor: winners avg {correlation.avg_score_winners:.2f} "
                f"vs losers {correlation.avg_score_losers:.2f}"
            )
        else:
            return f"Weak correlation ({correlation.correlation:.2f}), reducing weight"

    def _bound_weight_changes(
        self,
        current: WeightSet,
        suggested: WeightSet,
        max_change: Decimal,
    ) -> WeightSet:
        """Limit weight changes to maximum allowed."""
        return WeightSet(
            wallet_weight=self._bound_change(current.wallet_weight, suggested.wallet_weight, max_change),
            cluster_weight=self._bound_change(current.cluster_weight, suggested.cluster_weight, max_change),
            token_weight=self._bound_change(current.token_weight, suggested.token_weight, max_change),
            context_weight=self._bound_change(current.context_weight, suggested.context_weight, max_change),
        )

    def _bound_change(self, current: Decimal, suggested: Decimal, max_change: Decimal) -> Decimal:
        """Bound a single weight change."""
        change = suggested - current
        if abs(change) > max_change:
            return current + (max_change if change > 0 else -max_change)
        return suggested

    async def _load_trade_data(self) -> list[dict]:
        """Load trade data with factor scores."""
        result = await self.supabase.table("trade_outcomes").select(
            "*, signals(wallet_score, cluster_score, token_score, context_score)"
        ).order("exit_timestamp", desc=True).limit(1000).execute()

        return result.data

    async def _count_trades_since_calibration(self) -> int:
        """Count trades since last calibration."""
        last = await self.supabase.table("calibration_suggestions").select(
            "applied_at"
        ).eq("status", "approved").order("applied_at", desc=True).limit(1).execute()

        since = last.data[0]["applied_at"] if last.data else None

        query = self.supabase.table("trade_outcomes").select("*", count="exact")
        if since:
            query = query.gte("created_at", since)

        result = await query.execute()
        return result.count or 0

    async def _save_analysis(self, analysis: CalibrationAnalysis) -> None:
        """Save calibration analysis."""
        await self.supabase.table("calibration_analyses").insert(
            analysis.model_dump(mode="json")
        ).execute()

    async def _save_suggestion(self, suggestion: CalibrationSuggestion) -> None:
        """Save or update calibration suggestion."""
        await self.supabase.table("calibration_suggestions").upsert(
            suggestion.model_dump(mode="json")
        ).execute()

    async def _archive_weights(self, weights: WeightSet, suggestion_id: UUID) -> None:
        """Archive current weights before change."""
        archive = WeightArchive(
            id=uuid4(),
            weights=weights,
            active_from=datetime.utcnow(),  # Will be corrected from history
            active_until=datetime.utcnow(),
            suggestion_id=suggestion_id,
        )

        await self.supabase.table("weight_archive").insert(
            archive.model_dump(mode="json")
        ).execute()

    async def _update_weights(self, weights: WeightSet) -> None:
        """Update current scoring weights."""
        self._current_weights = weights

        await self.supabase.table("scoring_weights").upsert({
            "id": "current",
            **weights.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat(),
        }).execute()


# Singleton instance
_calibrator: Optional[ModelCalibrator] = None


async def get_model_calibrator(supabase_client) -> ModelCalibrator:
    """Get or create ModelCalibrator singleton."""
    global _calibrator
    if _calibrator is None:
        _calibrator = ModelCalibrator(supabase_client)
    return _calibrator
```

### Database Schema (SQL)

```sql
-- Scoring weights table
CREATE TABLE scoring_weights (
    id TEXT PRIMARY KEY DEFAULT 'current',
    wallet_weight DECIMAL(5, 4) NOT NULL DEFAULT 0.35,
    cluster_weight DECIMAL(5, 4) NOT NULL DEFAULT 0.25,
    token_weight DECIMAL(5, 4) NOT NULL DEFAULT 0.25,
    context_weight DECIMAL(5, 4) NOT NULL DEFAULT 0.15,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize default weights
INSERT INTO scoring_weights (id) VALUES ('current');

-- Calibration analyses table
CREATE TABLE calibration_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ DEFAULT NOW(),
    trade_count INTEGER NOT NULL,
    min_trades_required INTEGER DEFAULT 100,
    correlations JSONB NOT NULL,
    current_weights JSONB NOT NULL,
    suggested_weights JSONB NOT NULL,
    estimated_improvement DECIMAL(10, 4) DEFAULT 0
);

CREATE INDEX idx_calibration_analyses_date ON calibration_analyses(analyzed_at DESC);

-- Calibration suggestions table
CREATE TABLE calibration_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES calibration_analyses(id),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending', 'approved', 'rejected', 'modified'
    )),
    current_weights JSONB NOT NULL,
    suggested_weights JSONB NOT NULL,
    suggestions JSONB NOT NULL,
    estimated_improvement DECIMAL(10, 4) DEFAULT 0,
    applied_at TIMESTAMPTZ,
    applied_weights JSONB,
    operator_notes TEXT
);

CREATE INDEX idx_calibration_suggestions_status ON calibration_suggestions(status);
CREATE INDEX idx_calibration_suggestions_created ON calibration_suggestions(created_at DESC);

-- Weight archive table
CREATE TABLE weight_archive (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    weights JSONB NOT NULL,
    active_from TIMESTAMPTZ NOT NULL,
    active_until TIMESTAMPTZ NOT NULL,
    suggestion_id UUID REFERENCES calibration_suggestions(id),
    performance_during DECIMAL(10, 4)
);

CREATE INDEX idx_weight_archive_dates ON weight_archive(active_until DESC);

-- Auto-calibration configuration
CREATE TABLE auto_calibration_config (
    id TEXT PRIMARY KEY DEFAULT 'current',
    enabled BOOLEAN DEFAULT FALSE,
    min_trades_between INTEGER DEFAULT 100,
    max_weight_change DECIMAL(5, 4) DEFAULT 0.10,
    min_improvement_threshold DECIMAL(5, 2) DEFAULT 2.0,
    log_all_changes BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO auto_calibration_config (id) VALUES ('current');
```

### FastAPI Routes

```python
# src/walltrack/api/routes/calibration.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from uuid import UUID

from walltrack.core.feedback.calibration_models import (
    CalibrationAnalysis,
    CalibrationSuggestion,
    WeightSet,
    WeightArchive,
    ApplyWeightsRequest,
    AutoCalibrationConfig,
)
from walltrack.core.feedback.model_calibrator import get_model_calibrator
from walltrack.core.database import get_supabase_client

router = APIRouter(prefix="/calibration", tags=["calibration"])


@router.post("/analyze", response_model=CalibrationAnalysis)
async def run_analysis(
    min_trades: int = Query(default=100, ge=50),
    supabase=Depends(get_supabase_client),
):
    """Run calibration analysis on trade history."""
    calibrator = await get_model_calibrator(supabase)
    return await calibrator.run_analysis(min_trades=min_trades)


@router.post("/suggest", response_model=CalibrationSuggestion)
async def create_suggestion(
    analysis_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Create weight suggestion from analysis."""
    calibrator = await get_model_calibrator(supabase)

    # Load analysis
    result = await supabase.table("calibration_analyses").select("*").eq(
        "id", str(analysis_id)
    ).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Analysis not found")

    analysis = CalibrationAnalysis(**result.data)
    return await calibrator.create_suggestion(analysis)


@router.post("/apply", response_model=CalibrationSuggestion)
async def apply_weights(
    request: ApplyWeightsRequest,
    supabase=Depends(get_supabase_client),
):
    """Apply weights from a suggestion."""
    calibrator = await get_model_calibrator(supabase)
    return await calibrator.apply_weights(request)


@router.post("/reject/{suggestion_id}", response_model=CalibrationSuggestion)
async def reject_suggestion(
    suggestion_id: UUID,
    reason: Optional[str] = Query(default=None),
    supabase=Depends(get_supabase_client),
):
    """Reject a calibration suggestion."""
    calibrator = await get_model_calibrator(supabase)
    return await calibrator.reject_suggestion(suggestion_id, reason)


@router.get("/weights", response_model=WeightSet)
async def get_current_weights(
    supabase=Depends(get_supabase_client),
):
    """Get current scoring weights."""
    calibrator = await get_model_calibrator(supabase)
    return await calibrator.get_current_weights()


@router.get("/suggestion/{suggestion_id}", response_model=CalibrationSuggestion)
async def get_suggestion(
    suggestion_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get a calibration suggestion by ID."""
    calibrator = await get_model_calibrator(supabase)
    suggestion = await calibrator.get_suggestion(suggestion_id)
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return suggestion


@router.get("/history", response_model=list[WeightArchive])
async def get_weight_history(
    limit: int = Query(default=10, ge=1, le=100),
    supabase=Depends(get_supabase_client),
):
    """Get archived weight configurations."""
    calibrator = await get_model_calibrator(supabase)
    return await calibrator.get_weight_history(limit=limit)
```

### Gradio UI Component

```python
# src/walltrack/ui/components/calibration.py
import gradio as gr
from decimal import Decimal


def create_calibration_panel(api_client) -> gr.Blocks:
    """Create calibration management panel."""

    with gr.Blocks() as panel:
        gr.Markdown("## Scoring Model Calibration")

        with gr.Tabs():
            # Current Weights Tab
            with gr.Tab("Current Weights"):
                with gr.Row():
                    wallet_weight = gr.Number(label="Wallet Weight", precision=4)
                    cluster_weight = gr.Number(label="Cluster Weight", precision=4)
                    token_weight = gr.Number(label="Token Weight", precision=4)
                    context_weight = gr.Number(label="Context Weight", precision=4)

                refresh_weights_btn = gr.Button("Refresh", variant="secondary")

            # Analysis Tab
            with gr.Tab("Run Analysis"):
                min_trades_input = gr.Slider(
                    minimum=50,
                    maximum=500,
                    value=100,
                    step=10,
                    label="Minimum Trades Required",
                )
                run_analysis_btn = gr.Button("Run Analysis", variant="primary")

                analysis_output = gr.JSON(label="Analysis Results")

                with gr.Row(visible=False) as suggestion_row:
                    create_suggestion_btn = gr.Button("Create Suggestion", variant="primary")

            # Suggestions Tab
            with gr.Tab("Pending Suggestions"):
                suggestions_table = gr.Dataframe(
                    headers=["ID", "Created", "Est. Improvement", "Status"],
                    label="Pending Suggestions",
                )
                refresh_suggestions_btn = gr.Button("Refresh", variant="secondary")

                with gr.Row():
                    selected_suggestion = gr.Textbox(label="Selected Suggestion ID")
                    view_suggestion_btn = gr.Button("View Details")

                suggestion_details = gr.JSON(label="Suggestion Details", visible=False)

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Adjust Weights (Optional)")
                        adj_wallet = gr.Slider(0, 1, step=0.01, label="Wallet")
                        adj_cluster = gr.Slider(0, 1, step=0.01, label="Cluster")
                        adj_token = gr.Slider(0, 1, step=0.01, label="Token")
                        adj_context = gr.Slider(0, 1, step=0.01, label="Context")

                    with gr.Column():
                        operator_notes = gr.Textbox(
                            label="Operator Notes",
                            lines=3,
                        )
                        with gr.Row():
                            apply_btn = gr.Button("Apply Suggestion", variant="primary")
                            apply_modified_btn = gr.Button("Apply Modified", variant="secondary")
                            reject_btn = gr.Button("Reject", variant="stop")

            # History Tab
            with gr.Tab("Weight History"):
                history_table = gr.Dataframe(
                    headers=["Active From", "Active Until", "Wallet", "Cluster", "Token", "Context", "Performance"],
                    label="Weight History",
                )
                refresh_history_btn = gr.Button("Refresh", variant="secondary")

        # Event handlers
        async def load_weights():
            weights = await api_client.get("/calibration/weights")
            return (
                weights["wallet_weight"],
                weights["cluster_weight"],
                weights["token_weight"],
                weights["context_weight"],
            )

        async def run_analysis(min_trades):
            result = await api_client.post(
                "/calibration/analyze",
                params={"min_trades": int(min_trades)}
            )
            return result, gr.update(visible=True)

        async def apply_suggestion(suggestion_id, notes):
            result = await api_client.post("/calibration/apply", json={
                "suggestion_id": suggestion_id,
                "operator_notes": notes,
            })
            return result

        refresh_weights_btn.click(
            load_weights,
            outputs=[wallet_weight, cluster_weight, token_weight, context_weight],
        )

        run_analysis_btn.click(
            run_analysis,
            inputs=[min_trades_input],
            outputs=[analysis_output, suggestion_row],
        )

    return panel
```

### Unit Tests

```python
# tests/core/feedback/test_model_calibrator.py
import pytest
from decimal import Decimal
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.feedback.calibration_models import (
    ScoringFactor,
    FactorCorrelation,
    WeightSet,
    CalibrationAnalysis,
    ApplyWeightsRequest,
)
from walltrack.core.feedback.model_calibrator import ModelCalibrator


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data=None)
    )
    client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    client.table.return_value.insert.return_value.execute = AsyncMock()
    client.table.return_value.upsert.return_value.execute = AsyncMock()
    return client


@pytest.fixture
def calibrator(mock_supabase):
    """Create ModelCalibrator instance."""
    return ModelCalibrator(mock_supabase)


@pytest.fixture
def sample_trades():
    """Create sample trade data."""
    return [
        {"wallet_score": 0.8, "cluster_score": 0.7, "token_score": 0.6, "context_score": 0.5, "pnl_percent": 50, "is_win": True},
        {"wallet_score": 0.9, "cluster_score": 0.8, "token_score": 0.7, "context_score": 0.6, "pnl_percent": 30, "is_win": True},
        {"wallet_score": 0.3, "cluster_score": 0.4, "token_score": 0.5, "context_score": 0.3, "pnl_percent": -20, "is_win": False},
        {"wallet_score": 0.4, "cluster_score": 0.3, "token_score": 0.4, "context_score": 0.4, "pnl_percent": -30, "is_win": False},
    ] * 25  # 100 trades


class TestFactorCorrelation:
    """Tests for factor correlation calculation."""

    def test_correlation_calculation(self, calibrator, sample_trades):
        """Test correlation is calculated correctly."""
        corr = calibrator._calculate_factor_correlation(
            sample_trades,
            ScoringFactor.WALLET_SCORE
        )

        assert corr.factor == ScoringFactor.WALLET_SCORE
        assert corr.sample_size == 100
        assert corr.correlation > 0  # Positive correlation expected

    def test_winner_loser_averages(self, calibrator, sample_trades):
        """Test winner/loser average calculation."""
        corr = calibrator._calculate_factor_correlation(
            sample_trades,
            ScoringFactor.WALLET_SCORE
        )

        assert corr.avg_score_winners > corr.avg_score_losers

    def test_is_predictive(self):
        """Test is_predictive computed field."""
        predictive = FactorCorrelation(
            factor=ScoringFactor.WALLET_SCORE,
            correlation=Decimal("0.3"),
            sample_size=100,
            avg_score_winners=Decimal("0.75"),
            avg_score_losers=Decimal("0.45"),
        )

        assert predictive.is_predictive is True

        not_predictive = FactorCorrelation(
            factor=ScoringFactor.CONTEXT_SCORE,
            correlation=Decimal("0.05"),
            sample_size=100,
            avg_score_winners=Decimal("0.5"),
            avg_score_losers=Decimal("0.48"),
        )

        assert not_predictive.is_predictive is False


class TestWeightGeneration:
    """Tests for weight suggestion generation."""

    def test_generated_weights_normalized(self, calibrator):
        """Test that generated weights sum to 1."""
        correlations = [
            FactorCorrelation(factor=ScoringFactor.WALLET_SCORE, correlation=Decimal("0.4"), sample_size=100, avg_score_winners=Decimal("0.7"), avg_score_losers=Decimal("0.4")),
            FactorCorrelation(factor=ScoringFactor.CLUSTER_SCORE, correlation=Decimal("0.3"), sample_size=100, avg_score_winners=Decimal("0.6"), avg_score_losers=Decimal("0.4")),
            FactorCorrelation(factor=ScoringFactor.TOKEN_SCORE, correlation=Decimal("0.2"), sample_size=100, avg_score_winners=Decimal("0.5"), avg_score_losers=Decimal("0.4")),
            FactorCorrelation(factor=ScoringFactor.CONTEXT_SCORE, correlation=Decimal("0.1"), sample_size=100, avg_score_winners=Decimal("0.5"), avg_score_losers=Decimal("0.45")),
        ]

        current = WeightSet(
            wallet_weight=Decimal("0.35"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.15"),
        )

        suggested = calibrator._generate_suggested_weights(correlations, current)

        assert suggested.is_normalized

    def test_higher_correlation_gets_higher_weight(self, calibrator):
        """Test that factors with higher correlation get higher weights."""
        correlations = [
            FactorCorrelation(factor=ScoringFactor.WALLET_SCORE, correlation=Decimal("0.5"), sample_size=100, avg_score_winners=Decimal("0.8"), avg_score_losers=Decimal("0.3")),
            FactorCorrelation(factor=ScoringFactor.CLUSTER_SCORE, correlation=Decimal("0.1"), sample_size=100, avg_score_winners=Decimal("0.5"), avg_score_losers=Decimal("0.45")),
            FactorCorrelation(factor=ScoringFactor.TOKEN_SCORE, correlation=Decimal("0.1"), sample_size=100, avg_score_winners=Decimal("0.5"), avg_score_losers=Decimal("0.45")),
            FactorCorrelation(factor=ScoringFactor.CONTEXT_SCORE, correlation=Decimal("0.1"), sample_size=100, avg_score_winners=Decimal("0.5"), avg_score_losers=Decimal("0.45")),
        ]

        current = WeightSet(
            wallet_weight=Decimal("0.25"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.25"),
        )

        suggested = calibrator._generate_suggested_weights(correlations, current)

        assert suggested.wallet_weight > suggested.cluster_weight


class TestWeightBounding:
    """Tests for weight change bounding."""

    def test_bounds_large_changes(self, calibrator):
        """Test that large changes are bounded."""
        current = WeightSet(
            wallet_weight=Decimal("0.25"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.25"),
        )

        suggested = WeightSet(
            wallet_weight=Decimal("0.50"),  # +0.25 change
            cluster_weight=Decimal("0.20"),
            token_weight=Decimal("0.20"),
            context_weight=Decimal("0.10"),
        )

        bounded = calibrator._bound_weight_changes(
            current, suggested, Decimal("0.10")
        )

        assert bounded.wallet_weight == Decimal("0.35")  # Only +0.10


class TestWeightApplication:
    """Tests for weight application."""

    @pytest.mark.asyncio
    async def test_apply_suggestion(self, calibrator, mock_supabase):
        """Test applying a suggestion."""
        suggestion_id = uuid4()

        # Mock existing suggestion
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "id": str(suggestion_id),
                "analysis_id": str(uuid4()),
                "status": "pending",
                "current_weights": {"wallet_weight": "0.35", "cluster_weight": "0.25", "token_weight": "0.25", "context_weight": "0.15"},
                "suggested_weights": {"wallet_weight": "0.40", "cluster_weight": "0.25", "token_weight": "0.20", "context_weight": "0.15"},
                "suggestions": [],
                "estimated_improvement": "5.0",
            })
        )

        result = await calibrator.apply_weights(ApplyWeightsRequest(
            suggestion_id=suggestion_id,
        ))

        assert result.status.value == "approved"
        assert result.applied_at is not None
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/feedback/model_calibrator.py`
- [ ] Implement factor-to-outcome correlation analysis
- [ ] Generate weight suggestions
- [ ] Compare to current weights
- [ ] Apply approved weights
- [ ] Archive previous weights
- [ ] (Optional) Implement auto-recalibration mode

## Definition of Done

- [ ] Correlation analysis calculates factor effectiveness
- [ ] Weight suggestions generated
- [ ] Operator can approve or modify suggestions
- [ ] Previous weights archived
