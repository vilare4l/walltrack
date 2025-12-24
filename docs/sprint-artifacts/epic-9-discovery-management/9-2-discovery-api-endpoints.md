# Story 9.2: Discovery API Endpoints

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: Story 9.1 (Discovery Runs History)

## User Story

**As an** operator or external system,
**I want** API endpoints to manage discovery,
**So that** I can trigger, monitor, and configure discovery programmatically.

## Acceptance Criteria

### AC 1: Trigger Discovery
**Given** valid discovery parameters
**When** POST /api/discovery/run is called
**Then** a new discovery run is started
**And** run ID is returned immediately
**And** discovery executes in background

### AC 2: Get Run Status
**Given** a discovery run ID
**When** GET /api/discovery/runs/{id} is called
**Then** current run status is returned
**And** includes progress if running
**And** includes results if completed

### AC 3: List Runs History
**Given** history query parameters
**When** GET /api/discovery/runs is called
**Then** paginated list of runs is returned
**And** can filter by date range
**And** can filter by status

### AC 4: Get Discovery Stats
**Given** stats request
**When** GET /api/discovery/stats is called
**Then** aggregated statistics are returned
**And** includes counts and averages
**And** can filter by date range

### AC 5: Get/Update Config
**Given** config request
**When** GET/PUT /api/discovery/config is called
**Then** current scheduler config is returned/updated
**And** includes schedule, enabled flag, parameters

## Technical Specifications

### API Routes

**src/walltrack/api/routes/discovery.py:**
```python
"""Discovery management API endpoints."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunParams,
    DiscoveryStats,
    TriggerType,
)
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
    """Discovery scheduler configuration."""
    enabled: bool = True
    schedule_hours: int = Field(default=6, ge=1, le=24)
    params: DiscoveryRunParams = Field(default_factory=DiscoveryRunParams)


class DiscoveryConfig(BaseModel):
    """Current discovery configuration."""
    enabled: bool
    schedule_hours: int
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
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

    # Create run record
    run = await repo.create_run(
        trigger_type=TriggerType.API,
        params=request.model_dump(),
        triggered_by="api",
    )

    # Run in background
    background_tasks.add_task(
        _execute_discovery,
        run.id,
        request,
        repo,
    )

    return TriggerDiscoveryResponse(
        run_id=run.id,
        status="started",
        message="Discovery run started in background",
    )


async def _execute_discovery(
    run_id: UUID,
    params: TriggerDiscoveryRequest,
    repo: DiscoveryRepository,
) -> None:
    """Execute discovery and update run record."""
    import time
    start = time.time()

    try:
        result = await run_discovery_task(
            min_price_change_pct=params.min_price_change_pct,
            min_volume_usd=params.min_volume_usd,
            max_token_age_hours=params.max_token_age_hours,
            early_window_minutes=params.early_window_minutes,
            min_profit_pct=params.min_profit_pct,
            max_tokens=params.max_tokens,
            profile_immediately=params.profile_immediately,
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
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> RunsListResponse:
    """List discovery runs with optional filters."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    offset = (page - 1) * page_size
    runs = await repo.get_runs(
        start_date=start_date,
        end_date=end_date,
        limit=page_size + 1,  # +1 to check has_more
        offset=offset,
    )

    has_more = len(runs) > page_size
    if has_more:
        runs = runs[:page_size]

    return RunsListResponse(
        runs=runs,
        total=len(runs),  # Would need count query for real total
        page=page,
        page_size=page_size,
        has_more=has_more,
    )


@router.get("/stats", response_model=DiscoveryStats)
async def get_stats(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> DiscoveryStats:
    """Get discovery statistics."""
    supabase = await get_supabase_client()
    repo = DiscoveryRepository(supabase)

    return await repo.get_stats(start_date, end_date)


@router.get("/config", response_model=DiscoveryConfig)
async def get_config() -> DiscoveryConfig:
    """Get current discovery scheduler configuration."""
    # TODO: Load from database or settings
    from walltrack.config.settings import get_settings
    settings = get_settings()

    return DiscoveryConfig(
        enabled=True,  # TODO: Store in DB
        schedule_hours=6,  # TODO: Store in DB
        next_run_at=None,  # TODO: Get from scheduler
        last_run_at=None,  # TODO: Get from repo
        params=DiscoveryRunParams(),
    )


@router.put("/config", response_model=DiscoveryConfig)
async def update_config(request: DiscoveryConfigRequest) -> DiscoveryConfig:
    """Update discovery scheduler configuration."""
    # TODO: Save to database
    # TODO: Update scheduler

    return DiscoveryConfig(
        enabled=request.enabled,
        schedule_hours=request.schedule_hours,
        params=request.params,
    )
```

### Register Routes

**Update src/walltrack/api/app.py:**
```python
from walltrack.api.routes.discovery import router as discovery_router

app.include_router(discovery_router, prefix="/api")
```

## Implementation Tasks

- [ ] Create discovery router with all endpoints
- [ ] Implement trigger endpoint with background execution
- [ ] Implement run status endpoint
- [ ] Implement runs list with pagination
- [ ] Implement stats endpoint
- [ ] Implement config get/update endpoints
- [ ] Register routes in app
- [ ] Write API tests

## Definition of Done

- [ ] All endpoints return correct responses
- [ ] Discovery runs in background
- [ ] Pagination works correctly
- [ ] Stats are calculated accurately
- [ ] Config can be updated
- [ ] API tests pass

## File List

### New Files
- `src/walltrack/api/routes/discovery.py` - API endpoints
- `tests/api/test_discovery_api.py` - API tests

### Modified Files
- `src/walltrack/api/app.py` - Register routes
