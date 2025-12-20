"""Signal accuracy tracking API routes."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from walltrack.core.feedback.accuracy_models import (
    AccuracyTrendAnalysis,
    FactorAccuracyBreakdown,
    RetrospectiveAnalysis,
    SignalAccuracyMetrics,
    ThresholdAnalysis,
)
from walltrack.core.feedback.accuracy_tracker import get_accuracy_tracker

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


class AccuracyMetricsResponse(BaseModel):
    """Response for accuracy metrics."""

    metrics: SignalAccuracyMetrics
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ThresholdAnalysisResponse(BaseModel):
    """Response for threshold analysis."""

    analyses: list[ThresholdAnalysis]
    optimal_threshold: Decimal
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TrendAnalysisResponse(BaseModel):
    """Response for trend analysis."""

    trend: AccuracyTrendAnalysis
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class FactorBreakdownResponse(BaseModel):
    """Response for factor breakdown."""

    factors: list[FactorAccuracyBreakdown]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RetrospectiveResponse(BaseModel):
    """Response for retrospective analysis."""

    analysis: RetrospectiveAnalysis
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


@router.get("/metrics", response_model=AccuracyMetricsResponse)
async def get_accuracy_metrics(
    days: int = Query(default=30, ge=1, le=365, description="Lookback period in days")
) -> AccuracyMetricsResponse:
    """Get signal accuracy metrics.

    Returns win rate, trade rate, and score statistics for the period.
    """
    tracker = get_accuracy_tracker()

    start_date = datetime.now(UTC) - timedelta(days=days)
    end_date = datetime.now(UTC)

    metrics = await tracker.calculate_accuracy_metrics(
        start_date=start_date, end_date=end_date
    )

    return AccuracyMetricsResponse(metrics=metrics)


@router.get("/thresholds", response_model=ThresholdAnalysisResponse)
async def analyze_thresholds(
    min_threshold: Decimal = Query(
        default=Decimal("0.40"), ge=0, le=1, description="Minimum threshold"
    ),
    max_threshold: Decimal = Query(
        default=Decimal("0.85"), ge=0, le=1, description="Maximum threshold"
    ),
    step: Decimal = Query(
        default=Decimal("0.05"), ge=Decimal("0.01"), le=Decimal("0.1"), description="Step size"
    ),
) -> ThresholdAnalysisResponse:
    """Analyze different threshold effectiveness.

    Returns win rates and PnL for different score thresholds.
    """
    tracker = get_accuracy_tracker()

    analyses = await tracker.analyze_thresholds(
        min_threshold=min_threshold, max_threshold=max_threshold, step=step
    )

    # Find optimal threshold (highest profit factor with reasonable sample)
    optimal = Decimal("0.6")  # Default
    if analyses:
        valid_analyses = [a for a in analyses if a.would_trade_count >= 10]
        if valid_analyses:
            best = max(valid_analyses, key=lambda a: a.profit_factor)
            optimal = best.threshold

    return ThresholdAnalysisResponse(analyses=analyses, optimal_threshold=optimal)


@router.get("/trend", response_model=TrendAnalysisResponse)
async def get_accuracy_trend(
    weeks: int = Query(default=8, ge=2, le=52, description="Trend period in weeks")
) -> TrendAnalysisResponse:
    """Analyze accuracy trend over time.

    Returns trend direction, slope, and confidence.
    """
    tracker = get_accuracy_tracker()

    trend = await tracker.analyze_trend(weeks=weeks)

    return TrendAnalysisResponse(trend=trend)


@router.get("/factors", response_model=FactorBreakdownResponse)
async def get_factor_breakdown(
    days: int = Query(default=30, ge=7, le=365, description="Analysis period in days")
) -> FactorBreakdownResponse:
    """Break down accuracy by scoring factors.

    Returns which factors are predictive and weight recommendations.
    """
    tracker = get_accuracy_tracker()

    factors = await tracker.breakdown_by_factor(days=days)

    return FactorBreakdownResponse(factors=factors)


@router.get("/retrospective", response_model=RetrospectiveResponse)
async def run_retrospective(
    days: int = Query(default=7, ge=1, le=30, description="Lookback period in days"),
    window_hours: int = Query(
        default=24, ge=1, le=168, description="Price tracking window in hours"
    ),
) -> RetrospectiveResponse:
    """Run retrospective analysis on non-traded signals.

    Identifies missed opportunities and bullets dodged.
    """
    tracker = get_accuracy_tracker()

    start_date = datetime.now(UTC) - timedelta(days=days)
    end_date = datetime.now(UTC)

    analysis = await tracker.run_retrospective_analysis(
        start_date=start_date, end_date=end_date, window_hours=window_hours
    )

    return RetrospectiveResponse(analysis=analysis)
