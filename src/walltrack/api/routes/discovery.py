"""Discovery management API endpoints."""

import time
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunParams,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)
from walltrack.scheduler.discovery_scheduler import get_discovery_scheduler
from walltrack.scheduler.tasks.discovery_task import run_discovery_task

router = APIRouter(prefix="/discovery", tags=["discovery"])


class TriggerDiscoveryRequest(BaseModel):
    """Request to trigger a discovery run."""

    min_price_change_pct: float = Field(default=100.0, ge=0, le=1000)
    min_volume_usd: float = Field(default=50000.0, ge=0)
    max_token_age_hours: int = Field(default=72, ge=1, le=168)
    early_window_minutes: int = Field(default=30, ge=5, le=120)
    min_profit_pct: float = Field(default=50.0, ge=0, le=500)
    max_tokens: int = Field(default=20, ge=1, le=100)
    profile_immediately: bool = True


class TriggerDiscoveryResponse(BaseModel):
    """Response from triggering discovery."""

    run_id: UUID
    status: str
    message: str


class RunsListResponse(BaseModel):
    """Paginated list of runs."""

    runs: list[DiscoveryRun]
    total: int
    page: int
    page_size: int
    has_more: bool


class DiscoveryConfigRequest(BaseModel):
    """Discovery scheduler configuration request."""

    enabled: bool = True
    schedule_hours: int = Field(default=6, ge=1, le=24)
    params: DiscoveryRunParams = Field(default_factory=DiscoveryRunParams)


class DiscoveryConfigResponse(BaseModel):
    """Current discovery configuration."""

    enabled: bool
    schedule_hours: int
    next_run_at: datetime | None = None
    last_run_at: datetime | None = None
    params: DiscoveryRunParams


@router.post("/run", response_model=TriggerDiscoveryResponse)
async def trigger_discovery(
    request: TriggerDiscoveryRequest,
    background_tasks: BackgroundTasks,
) -> TriggerDiscoveryResponse:
    """
    Trigger a new discovery run.

    The discovery runs in the background. Use the returned run_id
    to check status via GET /discovery/runs/{run_id}.
    """
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    # Create run record upfront so we can return the ID immediately
    run = await repo.create_run(
        trigger_type=TriggerType.API,
        params=request.model_dump(exclude={"profile_immediately"}),
        triggered_by="api",
    )

    # Run in background
    background_tasks.add_task(
        _execute_discovery,
        run.id,
        request,
    )

    return TriggerDiscoveryResponse(
        run_id=run.id,
        status="started",
        message="Discovery run started in background",
    )


async def _execute_discovery(
    run_id: UUID,
    params: TriggerDiscoveryRequest,
) -> None:
    """Execute discovery and update run record."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    start = time.time()

    try:
        # Run discovery without tracking (we already created the run record)
        result = await run_discovery_task(
            min_price_change_pct=params.min_price_change_pct,
            min_volume_usd=params.min_volume_usd,
            max_token_age_hours=params.max_token_age_hours,
            early_window_minutes=params.early_window_minutes,
            min_profit_pct=params.min_profit_pct,
            max_tokens=params.max_tokens,
            profile_immediately=params.profile_immediately,
            trigger_type=TriggerType.API,
            triggered_by="api",
            track_run=False,  # We already created the run record
        )

        await repo.complete_run(
            run_id=run_id,
            tokens_analyzed=result["tokens_analyzed"],
            new_wallets=result["new_wallets"],
            updated_wallets=result["updated_wallets"],
            profiled_wallets=result.get("profiled_wallets", 0),
            duration_seconds=time.time() - start,
            errors=result.get("errors", []),
        )

    except Exception as e:
        await repo.fail_run(run_id, str(e))


@router.get("/runs/{run_id}", response_model=DiscoveryRun)
async def get_run(run_id: UUID) -> DiscoveryRun:
    """Get details of a specific discovery run."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    run = await repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return run


@router.get("/runs", response_model=RunsListResponse)
async def list_runs(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    status: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> RunsListResponse:
    """List discovery runs with optional filters."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    # Convert status string to enum if provided
    status_filter = None
    if status:
        try:
            status_filter = RunStatus(status)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status. Valid values: {[s.value for s in RunStatus]}",
            ) from e

    offset = (page - 1) * page_size
    runs = await repo.get_runs(
        start_date=start_date,
        end_date=end_date,
        status=status_filter,
        limit=page_size + 1,  # +1 to check has_more
        offset=offset,
    )

    has_more = len(runs) > page_size
    if has_more:
        runs = runs[:page_size]

    return RunsListResponse(
        runs=runs,
        total=len(runs),  # Note: Would need count query for accurate total
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/stats", response_model=DiscoveryStats)
async def get_stats(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
) -> DiscoveryStats:
    """Get discovery statistics."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    return await repo.get_stats(start_date, end_date)


@router.get("/config", response_model=DiscoveryConfigResponse)
async def get_config() -> DiscoveryConfigResponse:
    """Get current discovery scheduler configuration."""
    scheduler = await get_discovery_scheduler()

    return DiscoveryConfigResponse(
        enabled=scheduler.enabled,
        schedule_hours=scheduler.schedule_hours,
        next_run_at=scheduler.next_run,
        last_run_at=scheduler.last_run,
        params=scheduler.params,
    )


@router.put("/config", response_model=DiscoveryConfigResponse)
async def update_config(request: DiscoveryConfigRequest) -> DiscoveryConfigResponse:
    """Update discovery scheduler configuration."""
    scheduler = await get_discovery_scheduler()

    await scheduler.save_config(
        enabled=request.enabled,
        schedule_hours=request.schedule_hours,
        params=request.params,
        updated_by="api",
    )

    return DiscoveryConfigResponse(
        enabled=scheduler.enabled,
        schedule_hours=scheduler.schedule_hours,
        next_run_at=scheduler.next_run,
        last_run_at=scheduler.last_run,
        params=scheduler.params,
    )
