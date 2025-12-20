"""API routes for pattern analysis and insights."""

from fastapi import APIRouter, Depends, Query
from supabase import AsyncClient

from walltrack.core.feedback.pattern_analyzer import PatternAnalyzer, get_pattern_analyzer
from walltrack.core.feedback.pattern_models import PatternAlert, PatternAnalysisResult
from walltrack.data.supabase.client import get_supabase_client

router = APIRouter(prefix="/patterns", tags=["patterns"])


async def get_analyzer(
    client: AsyncClient = Depends(get_supabase_client),
) -> PatternAnalyzer:
    """Get pattern analyzer instance."""
    return get_pattern_analyzer(client)


@router.post("/analyze", response_model=PatternAnalysisResult)
async def run_pattern_analysis(
    days: int = Query(default=30, ge=7, le=90, description="Days of history to analyze"),
    analyzer: PatternAnalyzer = Depends(get_analyzer),
) -> PatternAnalysisResult:
    """Run full pattern analysis on trade history.

    Analyzes trading patterns across multiple dimensions:
    - Time of day patterns
    - Day of week patterns
    - Wallet performance patterns
    - Token characteristic patterns
    - Cluster vs solo trade patterns

    Returns identified patterns with statistical significance and actionable insights.
    """
    return await analyzer.run_full_analysis(days=days)


@router.get("/alerts", response_model=list[PatternAlert])
async def get_pattern_alerts(
    unacknowledged_only: bool = Query(
        default=True, description="Only return unacknowledged alerts"
    ),
    limit: int = Query(default=20, ge=1, le=100, description="Maximum alerts to return"),
    analyzer: PatternAnalyzer = Depends(get_analyzer),
) -> list[PatternAlert]:
    """Get pattern alerts.

    Returns alerts for significant patterns that may require attention.
    """
    return await analyzer.get_alerts(unacknowledged_only=unacknowledged_only, limit=limit)


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: str,
    analyzer: PatternAnalyzer = Depends(get_analyzer),
) -> dict:
    """Acknowledge a pattern alert.

    Marks the alert as acknowledged so it won't appear in unacknowledged lists.
    """
    await analyzer.acknowledge_alert(alert_id)
    return {"status": "acknowledged", "alert_id": alert_id}


@router.get("/top-patterns")
async def get_top_patterns(
    count: int = Query(default=5, ge=1, le=20, description="Number of patterns per category"),
    analyzer: PatternAnalyzer = Depends(get_analyzer),
) -> dict:
    """Get top positive and negative patterns.

    Returns the most significant patterns that are actionable.
    """
    result = await analyzer.run_full_analysis(days=30)
    return {
        "top_positive": result.top_positive_patterns[:count],
        "top_negative": result.top_negative_patterns[:count],
        "total_patterns": len(result.patterns),
        "trade_count": result.trade_count,
        "baseline_win_rate": result.baseline_win_rate,
    }
