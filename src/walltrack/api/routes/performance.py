"""Performance analytics API routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from walltrack.core.feedback.performance_dashboard import PerformanceDashboardService
from walltrack.core.feedback.performance_models import (
    BreakdownType,
    BreakdownView,
    DashboardQuery,
    DateRange,
    KeyMetrics,
    PerformanceDashboardData,
    PnLTimeSeries,
    TimeGranularity,
    WinRateTrend,
)
from walltrack.data.supabase.client import get_supabase_client

router = APIRouter(prefix="/performance", tags=["performance"])

_service_instance: PerformanceDashboardService | None = None


async def get_service() -> PerformanceDashboardService:
    """Get or create performance dashboard service singleton."""
    global _service_instance
    if _service_instance is None:
        client = await get_supabase_client()
        _service_instance = PerformanceDashboardService(client)
    return _service_instance


@router.get("/dashboard", response_model=PerformanceDashboardData)
async def get_dashboard_data(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    include_comparison: bool = Query(default=True),
    granularity: TimeGranularity = Query(default=TimeGranularity.DAILY),
    breakdowns: list[BreakdownType] = Query(default=[]),
    service: PerformanceDashboardService = Depends(get_service),
) -> PerformanceDashboardData:
    """Get complete performance dashboard data.

    Returns key metrics, time series, win rate trends, and optional breakdowns
    for the specified date range.
    """
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=include_comparison,
        time_granularity=granularity,
        breakdowns_requested=breakdowns,
    )
    return await service.get_dashboard_data(query)


@router.get("/metrics", response_model=KeyMetrics)
async def get_key_metrics(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    service: PerformanceDashboardService = Depends(get_service),
) -> KeyMetrics:
    """Get key performance metrics only (lightweight endpoint)."""
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=False,
        breakdowns_requested=[],
    )
    data = await service.get_dashboard_data(query)
    return data.key_metrics


@router.get("/pnl-series", response_model=PnLTimeSeries)
async def get_pnl_time_series(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    granularity: TimeGranularity = Query(default=TimeGranularity.DAILY),
    service: PerformanceDashboardService = Depends(get_service),
) -> PnLTimeSeries:
    """Get PnL time series for charting."""
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=False,
        time_granularity=granularity,
        breakdowns_requested=[],
    )
    data = await service.get_dashboard_data(query)
    return data.pnl_time_series


@router.get("/win-rate-trend", response_model=WinRateTrend)
async def get_win_rate_trend(
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    granularity: TimeGranularity = Query(default=TimeGranularity.DAILY),
    service: PerformanceDashboardService = Depends(get_service),
) -> WinRateTrend:
    """Get win rate trend over time."""
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=False,
        time_granularity=granularity,
        breakdowns_requested=[],
    )
    data = await service.get_dashboard_data(query)
    return data.win_rate_trend


@router.get("/breakdown/{breakdown_type}", response_model=BreakdownView)
async def get_breakdown(
    breakdown_type: BreakdownType,
    start_date: date = Query(..., description="Start date (inclusive)"),
    end_date: date = Query(..., description="End date (inclusive)"),
    service: PerformanceDashboardService = Depends(get_service),
) -> BreakdownView:
    """Get performance breakdown by specific category."""
    query = DashboardQuery(
        date_range=DateRange(start_date=start_date, end_date=end_date),
        include_comparison=False,
        breakdowns_requested=[breakdown_type],
    )
    data = await service.get_dashboard_data(query)
    return data.breakdowns.get(breakdown_type, BreakdownView(breakdown_type=breakdown_type))


@router.post("/cache/clear")
async def clear_cache(
    service: PerformanceDashboardService = Depends(get_service),
) -> dict[str, str]:
    """Clear the performance dashboard cache."""
    service.clear_cache()
    return {"status": "cache_cleared"}
