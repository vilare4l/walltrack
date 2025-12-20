"""Backtest preview API routes."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query

from walltrack.core.feedback.backtest_models import (
    ApplySettingsRequest,
    ApplySettingsResult,
    BacktestConfig,
    BacktestProgress,
    BacktestResult,
)
from walltrack.core.feedback.backtester import BacktestService, get_backtest_service
from walltrack.data.supabase.client import get_supabase_client

router = APIRouter(prefix="/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
async def run_backtest(
    config: BacktestConfig,
    service: BacktestService = Depends(get_backtest_service),
) -> BacktestResult:
    """Run a backtest with the given configuration.

    Target completion time: < 30 seconds for 6 months of data.
    """
    # Validate date range
    if config.end_date < config.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    if config.date_range_days > 180:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 180 days for performance reasons",
        )

    # Validate weights
    if not config.scoring_weights.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Scoring weights must sum to 1.0, got {config.scoring_weights.total_weight}",
        )

    return await service.run_backtest(config)


@router.get("/progress/{backtest_id}", response_model=BacktestProgress | None)
async def get_backtest_progress(
    backtest_id: str,
    service: BacktestService = Depends(get_backtest_service),
) -> BacktestProgress | None:
    """Get progress of a running backtest."""
    progress = service.get_progress(backtest_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Backtest not found or completed")
    return progress


@router.get("/result/{backtest_id}", response_model=BacktestResult)
async def get_backtest_result(
    backtest_id: str,
) -> BacktestResult:
    """Get result of a completed backtest."""
    supabase = await get_supabase_client()
    response = (
        await supabase.table("backtest_results")
        .select("*")
        .eq("id", backtest_id)
        .single()
        .execute()
    )

    if not response.data:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    data = response.data
    return BacktestResult(
        id=data["id"],
        config=BacktestConfig(**data["config"]),
        status=data["status"],
        started_at=data["started_at"],
        completed_at=data.get("completed_at"),
        duration_seconds=data.get("duration_seconds"),
        total_signals_analyzed=data.get("total_signals_analyzed", 0),
        error_message=data.get("error_message"),
    )


@router.get("/history")
async def list_backtest_history(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[dict]:
    """List recent backtest results."""
    supabase = await get_supabase_client()
    response = (
        await supabase.table("backtest_results")
        .select(
            "id, status, started_at, completed_at, duration_seconds, "
            "total_signals_analyzed, metrics_comparison"
        )
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data or []


@router.post("/apply", response_model=ApplySettingsResult)
async def apply_backtest_settings(
    request: ApplySettingsRequest,
    service: BacktestService = Depends(get_backtest_service),
) -> ApplySettingsResult:
    """Apply settings from a successful backtest to production.

    Requires confirm_apply=True for safety.
    """
    return await service.apply_settings(request)


@router.get("/defaults", response_model=BacktestConfig)
async def get_default_config() -> BacktestConfig:
    """Get default backtest configuration."""
    return BacktestConfig(
        start_date=date.today() - timedelta(days=30), end_date=date.today()
    )


@router.post("/cache/clear")
async def clear_cache(
    service: BacktestService = Depends(get_backtest_service),
) -> dict[str, str]:
    """Clear the signal cache for fresh data."""
    service.clear_cache()
    return {"status": "cache_cleared"}
