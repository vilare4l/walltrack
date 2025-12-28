# Story 12.11: API Endpoints - Positions & Simulation

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 5
- **Depends on**: All previous Epic 12 stories

## User Story

**As a** the system/external client,
**I want** des endpoints REST pour la gestion des positions et simulations,
**So that** je peux intégrer ces fonctionnalités dans d'autres systèmes.

## Acceptance Criteria

### AC 1: List Positions Endpoint
**Given** un appel GET /api/positions
**When** avec query params (status, limit, offset)
**Then** je reçois la liste paginée des positions

### AC 2: Position Details Endpoint
**Given** un appel GET /api/positions/{id}
**When** l'ID existe
**Then** je reçois les détails complets avec prix actuel

### AC 3: Change Strategy Endpoint
**Given** un appel PATCH /api/positions/{id}/strategy
**When** avec body {strategy_id}
**Then** la stratégie est changée
**And** les nouveaux niveaux sont recalculés

### AC 4: Simulate Endpoint
**Given** un appel POST /api/positions/{id}/simulate
**When** avec body {strategy_ids}
**Then** je reçois les résultats de simulation

### AC 5: Timeline Endpoint
**Given** un appel GET /api/positions/{id}/timeline
**When** avec query params (event_types, limit)
**Then** je reçois la timeline filtrée

### AC 6: Global Analysis Endpoint
**Given** un appel POST /api/analysis/global
**When** avec body {position_ids, strategy_ids}
**Then** je reçois l'analyse multi-positions

## Technical Specifications

### API Router

**src/walltrack/api/positions_router.py:**
```python
"""API router for positions and simulation endpoints."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel, Field

import structlog

from walltrack.services.positions.timeline_service import (
    get_timeline_service,
    PositionEventType,
)
from walltrack.services.simulation.strategy_comparator import (
    get_strategy_comparator,
    format_comparison_table,
)
from walltrack.services.simulation.global_analyzer import (
    get_global_analyzer,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/positions", tags=["positions"])
analysis_router = APIRouter(prefix="/api/analysis", tags=["analysis"])


# =============================================================================
# Request/Response Models
# =============================================================================

class PositionSummary(BaseModel):
    """Summary of a position for list view."""
    id: str
    token_address: str
    token_symbol: Optional[str]
    entry_price: float
    current_price: Optional[float]
    entry_time: datetime
    exit_time: Optional[datetime]
    status: str
    pnl_pct: Optional[float]
    pnl_sol: Optional[float]
    size_sol: float
    exit_strategy_name: Optional[str]


class PositionListResponse(BaseModel):
    """Paginated position list response."""
    positions: list[PositionSummary]
    total: int
    limit: int
    offset: int
    has_more: bool


class PositionDetails(BaseModel):
    """Full position details."""
    id: str
    token_address: str
    token_symbol: Optional[str]
    entry_price: float
    exit_price: Optional[float]
    current_price: Optional[float]
    entry_time: datetime
    exit_time: Optional[datetime]
    status: str
    pnl_pct: Optional[float]
    pnl_sol: Optional[float]
    size_sol: float
    remaining_pct: float
    exit_strategy_id: Optional[str]
    exit_strategy_name: Optional[str]
    exit_type: Optional[str]
    conviction_tier: Optional[str]
    strategy_levels: Optional[dict]
    price_history_count: int


class ChangeStrategyRequest(BaseModel):
    """Request to change position strategy."""
    strategy_id: str = Field(..., description="New strategy ID")
    reason: Optional[str] = Field(None, description="Reason for change")


class ChangeStrategyResponse(BaseModel):
    """Response after changing strategy."""
    success: bool
    position_id: str
    old_strategy_id: Optional[str]
    new_strategy_id: str
    new_levels: dict
    message: str


class SimulateRequest(BaseModel):
    """Request for position simulation."""
    strategy_ids: list[str] = Field(..., min_length=1, max_length=10)


class SimulationRowResponse(BaseModel):
    """Single simulation row."""
    strategy_id: str
    strategy_name: str
    simulated_pnl_pct: float
    actual_pnl_pct: Optional[float]
    delta_pct: Optional[float]
    exit_time: Optional[datetime]
    exit_types: list[str]
    is_best: bool


class SimulationResponse(BaseModel):
    """Simulation comparison response."""
    position_id: str
    entry_price: float
    actual_exit_price: Optional[float]
    actual_pnl_pct: Optional[float]
    rows: list[SimulationRowResponse]
    best_strategy_id: str
    best_strategy_name: str
    best_improvement_pct: Optional[float]
    markdown_table: str


class TimelineEventResponse(BaseModel):
    """Single timeline event."""
    id: str
    event_type: str
    timestamp: datetime
    price_at_event: Optional[float]
    data_before: Optional[dict]
    data_after: Optional[dict]
    metadata: dict
    comment: Optional[str]


class TimelineResponse(BaseModel):
    """Position timeline response."""
    position_id: str
    token_symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    duration_hours: float
    events: list[TimelineEventResponse]
    total_events: int


class GlobalAnalysisRequest(BaseModel):
    """Request for global analysis."""
    position_ids: list[str] = Field(default=[], description="Position IDs (empty=all closed)")
    strategy_ids: list[str] = Field(default=[], description="Strategy IDs (empty=all active)")
    limit: int = Field(default=100, ge=1, le=500)


class StrategyStatsResponse(BaseModel):
    """Strategy statistics."""
    strategy_id: str
    strategy_name: str
    positions_analyzed: int
    avg_pnl_pct: float
    median_pnl_pct: float
    total_pnl_sol: float
    win_rate_pct: float
    avg_improvement_pct: float
    best_position_id: str
    best_improvement_pct: float
    worst_position_id: str
    worst_improvement_pct: float


class GlobalAnalysisResponse(BaseModel):
    """Global analysis response."""
    total_positions: int
    strategies_compared: int
    analysis_time_ms: float
    strategy_stats: list[StrategyStatsResponse]
    recommended_strategy_id: str
    recommended_strategy_name: str
    summary_markdown: str


# =============================================================================
# Position Endpoints
# =============================================================================

@router.get("", response_model=PositionListResponse)
async def list_positions(
    status: Optional[str] = Query(None, description="Filter by status: active, closed"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    List positions with pagination.

    - **status**: Filter by position status (active/closed)
    - **limit**: Max positions to return (1-100)
    - **offset**: Pagination offset
    """
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Build query
    query = client.table("positions") \
        .select("""
            id, token_address, token_symbol, entry_price, exit_price,
            entry_time, exit_time, status, pnl_pct, pnl_sol, size_sol,
            exit_strategies(name)
        """, count="exact")

    if status:
        query = query.eq("status", status)

    query = query.order("entry_time", desc=True) \
        .range(offset, offset + limit - 1)

    result = await query.execute()

    positions = []
    for row in result.data:
        positions.append(PositionSummary(
            id=row["id"],
            token_address=row["token_address"],
            token_symbol=row.get("token_symbol"),
            entry_price=float(row["entry_price"]),
            current_price=float(row["exit_price"]) if row.get("exit_price") else None,
            entry_time=datetime.fromisoformat(row["entry_time"].replace("Z", "+00:00")),
            exit_time=datetime.fromisoformat(row["exit_time"].replace("Z", "+00:00"))
                if row.get("exit_time") else None,
            status=row["status"],
            pnl_pct=float(row["pnl_pct"]) if row.get("pnl_pct") else None,
            pnl_sol=float(row["pnl_sol"]) if row.get("pnl_sol") else None,
            size_sol=float(row["size_sol"]),
            exit_strategy_name=row.get("exit_strategies", {}).get("name")
                if row.get("exit_strategies") else None,
        ))

    total = result.count or len(positions)

    return PositionListResponse(
        positions=positions,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{position_id}", response_model=PositionDetails)
async def get_position(position_id: str):
    """
    Get detailed position information.

    Includes current price, strategy levels, and price history count.
    """
    from walltrack.data.supabase.client import get_supabase_client
    client = await get_supabase_client()

    # Get position with strategy
    result = await client.table("positions") \
        .select("""
            *,
            exit_strategies(id, name, rules)
        """) \
        .eq("id", position_id) \
        .single() \
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Position not found")

    row = result.data

    # Get price history count
    history_result = await client.table("position_price_history") \
        .select("id", count="exact") \
        .eq("position_id", position_id) \
        .execute()

    price_history_count = history_result.count or 0

    # Calculate strategy levels if active
    strategy_levels = None
    if row.get("exit_strategies") and row["status"] == "active":
        strategy = row["exit_strategies"]
        entry_price = Decimal(str(row["entry_price"]))
        levels = {}

        for rule in strategy.get("rules", []):
            if not rule.get("enabled"):
                continue

            trigger_pct = rule.get("trigger_pct")
            if trigger_pct:
                price = entry_price * (1 + Decimal(str(trigger_pct)) / 100)
                levels[rule["rule_type"]] = {
                    "price": float(price),
                    "trigger_pct": trigger_pct,
                    "exit_pct": rule.get("exit_pct"),
                }

        strategy_levels = levels

    return PositionDetails(
        id=row["id"],
        token_address=row["token_address"],
        token_symbol=row.get("token_symbol"),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]) if row.get("exit_price") else None,
        current_price=float(row.get("current_price")) if row.get("current_price") else None,
        entry_time=datetime.fromisoformat(row["entry_time"].replace("Z", "+00:00")),
        exit_time=datetime.fromisoformat(row["exit_time"].replace("Z", "+00:00"))
            if row.get("exit_time") else None,
        status=row["status"],
        pnl_pct=float(row["pnl_pct"]) if row.get("pnl_pct") else None,
        pnl_sol=float(row["pnl_sol"]) if row.get("pnl_sol") else None,
        size_sol=float(row["size_sol"]),
        remaining_pct=float(row.get("remaining_pct", 100)),
        exit_strategy_id=row.get("exit_strategy_id"),
        exit_strategy_name=row["exit_strategies"]["name"] if row.get("exit_strategies") else None,
        exit_type=row.get("exit_type"),
        conviction_tier=row.get("conviction_tier"),
        strategy_levels=strategy_levels,
        price_history_count=price_history_count,
    )


@router.patch("/{position_id}/strategy", response_model=ChangeStrategyResponse)
async def change_position_strategy(
    position_id: str,
    request: ChangeStrategyRequest,
    background_tasks: BackgroundTasks,
):
    """
    Change the exit strategy for an active position.

    - Validates position is active
    - Validates strategy exists and is active
    - Recalculates exit levels
    - Logs the change event
    """
    from walltrack.data.supabase.client import get_supabase_client
    from walltrack.services.exit.exit_strategy_service import get_exit_strategy_service
    from walltrack.services.positions.timeline_service import (
        get_timeline_service,
        PositionEventType,
    )

    client = await get_supabase_client()
    strategy_service = await get_exit_strategy_service()
    timeline_service = await get_timeline_service()

    # Get position
    pos_result = await client.table("positions") \
        .select("*, exit_strategies(id, name)") \
        .eq("id", position_id) \
        .single() \
        .execute()

    if not pos_result.data:
        raise HTTPException(status_code=404, detail="Position not found")

    position = pos_result.data

    if position["status"] != "active":
        raise HTTPException(
            status_code=400,
            detail="Can only change strategy for active positions"
        )

    # Get new strategy
    new_strategy = await strategy_service.get(request.strategy_id)
    if not new_strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if new_strategy.status != "active":
        raise HTTPException(status_code=400, detail="Strategy is not active")

    # Calculate new levels
    entry_price = Decimal(str(position["entry_price"]))
    new_levels = {}

    for rule in new_strategy.rules:
        if not rule.enabled:
            continue

        if rule.trigger_pct:
            price = entry_price * (1 + rule.trigger_pct / 100)
            new_levels[rule.rule_type] = {
                "price": float(price),
                "trigger_pct": float(rule.trigger_pct),
                "exit_pct": float(rule.exit_pct),
            }

    # Get old strategy info
    old_strategy = position.get("exit_strategies")
    old_strategy_id = old_strategy["id"] if old_strategy else None
    old_strategy_name = old_strategy["name"] if old_strategy else None

    # Update position
    await client.table("positions") \
        .update({"exit_strategy_id": request.strategy_id}) \
        .eq("id", position_id) \
        .execute()

    # Log event in background
    async def log_change():
        await timeline_service.log_event(
            position_id=position_id,
            event_type=PositionEventType.STRATEGY_CHANGED,
            price_at_event=Decimal(str(position.get("current_price")))
                if position.get("current_price") else None,
            data_before={
                "strategy_id": old_strategy_id,
                "strategy_name": old_strategy_name,
            },
            data_after={
                "strategy_id": request.strategy_id,
                "strategy_name": new_strategy.name,
            },
            metadata={"new_levels": new_levels},
            comment=request.reason,
        )

    background_tasks.add_task(log_change)

    logger.info(
        "position_strategy_changed",
        position_id=position_id,
        old_strategy=old_strategy_name,
        new_strategy=new_strategy.name,
    )

    return ChangeStrategyResponse(
        success=True,
        position_id=position_id,
        old_strategy_id=old_strategy_id,
        new_strategy_id=request.strategy_id,
        new_levels=new_levels,
        message=f"Strategy changed to '{new_strategy.name}'",
    )


@router.post("/{position_id}/simulate", response_model=SimulationResponse)
async def simulate_position(position_id: str, request: SimulateRequest):
    """
    Run what-if simulation on a position.

    Compares multiple exit strategies against the actual result.
    """
    comparator = await get_strategy_comparator()

    result = await comparator.compare(position_id, request.strategy_ids)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not simulate. Check if position has price history."
        )

    rows = [
        SimulationRowResponse(
            strategy_id=r.strategy_id,
            strategy_name=r.strategy_name,
            simulated_pnl_pct=float(r.simulated_pnl_pct),
            actual_pnl_pct=float(r.actual_pnl_pct) if r.actual_pnl_pct else None,
            delta_pct=float(r.delta_pct) if r.delta_pct else None,
            exit_time=r.exit_time,
            exit_types=r.exit_types,
            is_best=r.is_best,
        )
        for r in result.rows
    ]

    markdown_table = format_comparison_table(result)

    return SimulationResponse(
        position_id=result.position_id,
        entry_price=float(result.entry_price),
        actual_exit_price=float(result.actual_exit_price) if result.actual_exit_price else None,
        actual_pnl_pct=float(result.actual_pnl_pct) if result.actual_pnl_pct else None,
        rows=rows,
        best_strategy_id=result.best_strategy_id,
        best_strategy_name=result.best_strategy_name,
        best_improvement_pct=float(result.best_improvement_pct)
            if result.best_improvement_pct else None,
        markdown_table=markdown_table,
    )


@router.get("/{position_id}/timeline", response_model=TimelineResponse)
async def get_position_timeline(
    position_id: str,
    event_types: Optional[str] = Query(None, description="Comma-separated event types"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    Get position event timeline.

    - **event_types**: Filter by event types (comma-separated)
    - **limit**: Max events to return
    - **offset**: Pagination offset
    """
    timeline_service = await get_timeline_service()

    # Parse event types
    types = None
    if event_types:
        types = [
            PositionEventType(t.strip())
            for t in event_types.split(",")
            if t.strip() in [e.value for e in PositionEventType]
        ]

    try:
        timeline = await timeline_service.get_timeline(
            position_id=position_id,
            event_types=types,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    events = [
        TimelineEventResponse(
            id=e.id,
            event_type=e.event_type.value,
            timestamp=e.timestamp,
            price_at_event=float(e.price_at_event) if e.price_at_event else None,
            data_before=e.data_before,
            data_after=e.data_after,
            metadata=e.metadata,
            comment=e.comment,
        )
        for e in timeline.events
    ]

    return TimelineResponse(
        position_id=timeline.position_id,
        token_symbol=timeline.token_symbol,
        entry_time=timeline.entry_time,
        exit_time=timeline.exit_time,
        duration_hours=timeline.duration_hours,
        events=events,
        total_events=timeline.total_events,
    )


@router.get("/{position_id}/timeline/export")
async def export_position_timeline(
    position_id: str,
    format: str = Query("json", description="Export format: json or csv"),
):
    """
    Export position timeline to JSON or CSV.
    """
    timeline_service = await get_timeline_service()

    try:
        data = await timeline_service.export_timeline(position_id, format)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if format == "json":
        return {"data": data, "format": "json"}
    else:
        return {"data": data, "format": "csv"}


# =============================================================================
# Analysis Endpoints
# =============================================================================

@analysis_router.post("/global", response_model=GlobalAnalysisResponse)
async def run_global_analysis(request: GlobalAnalysisRequest):
    """
    Run global analysis across multiple positions.

    Compares strategies and identifies the best performer.
    """
    import time
    start = time.time()

    analyzer = await get_global_analyzer()

    result = await analyzer.analyze(
        position_ids=request.position_ids or None,
        strategy_ids=request.strategy_ids or None,
        limit=request.limit,
    )

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not run analysis. No valid positions found."
        )

    elapsed_ms = (time.time() - start) * 1000

    # Build strategy stats
    stats = [
        StrategyStatsResponse(
            strategy_id=s.strategy_id,
            strategy_name=s.strategy_name,
            positions_analyzed=s.positions_analyzed,
            avg_pnl_pct=float(s.avg_pnl_pct),
            median_pnl_pct=float(s.median_pnl_pct),
            total_pnl_sol=float(s.total_pnl_sol),
            win_rate_pct=float(s.win_rate_pct),
            avg_improvement_pct=float(s.avg_improvement_pct),
            best_position_id=s.best_position_id,
            best_improvement_pct=float(s.best_improvement_pct),
            worst_position_id=s.worst_position_id,
            worst_improvement_pct=float(s.worst_improvement_pct),
        )
        for s in result.strategy_stats
    ]

    # Build summary
    summary_md = f"""
## Global Analysis Summary

**Positions Analyzed:** {result.total_positions}
**Strategies Compared:** {result.strategies_compared}
**Analysis Time:** {elapsed_ms:.1f}ms

### Recommended Strategy
**{result.recommended_strategy_name}**

### Strategy Performance

| Strategy | Avg P&L | Win Rate | Avg Improvement |
|----------|---------|----------|-----------------|
"""
    for s in stats:
        summary_md += f"| {s.strategy_name} | {s.avg_pnl_pct:+.2f}% | {s.win_rate_pct:.1f}% | {s.avg_improvement_pct:+.2f}% |\n"

    return GlobalAnalysisResponse(
        total_positions=result.total_positions,
        strategies_compared=result.strategies_compared,
        analysis_time_ms=elapsed_ms,
        strategy_stats=stats,
        recommended_strategy_id=result.recommended_strategy_id,
        recommended_strategy_name=result.recommended_strategy_name,
        summary_markdown=summary_md,
    )


@analysis_router.get("/positions/{position_id}/compare-all")
async def compare_all_strategies(position_id: str):
    """
    Quick endpoint to compare all active strategies on a single position.
    """
    comparator = await get_strategy_comparator()

    result = await comparator.compare_all_active_strategies(position_id)

    if not result:
        raise HTTPException(
            status_code=400,
            detail="Could not compare. Check if position has price history."
        )

    return {
        "position_id": position_id,
        "best_strategy": result.best_strategy_name,
        "best_improvement_pct": float(result.best_improvement_pct)
            if result.best_improvement_pct else None,
        "comparison_table": format_comparison_table(result),
    }


# =============================================================================
# Router Registration Helper
# =============================================================================

def register_routers(app):
    """Register position and analysis routers with FastAPI app."""
    app.include_router(router)
    app.include_router(analysis_router)
```

### API Integration in Main App

**src/walltrack/api/main.py (modifications):**
```python
"""Main FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from walltrack.api.positions_router import register_routers as register_positions
# ... other router imports

app = FastAPI(
    title="Walltrack API",
    description="Solana memecoin trading system API",
    version="1.0.0",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
register_positions(app)
# ... other routers


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
```

## Implementation Tasks

- [x] Create Pydantic request/response models
- [x] Implement GET /api/positions endpoint
- [x] Implement GET /api/positions/{id} endpoint
- [x] Implement PATCH /api/positions/{id}/strategy endpoint
- [x] Implement POST /api/positions/{id}/simulate endpoint
- [x] Implement GET /api/positions/{id}/timeline endpoint
- [x] Implement timeline export endpoint
- [x] Implement POST /api/analysis/global endpoint
- [x] Implement GET /api/analysis/positions/{id}/compare-all endpoint
- [x] Add proper error handling
- [x] Add request validation
- [x] Add logging
- [x] Register routers in main app
- [x] Write API tests
- [x] Add OpenAPI documentation

## Definition of Done

- [x] All endpoints return correct responses
- [x] Validation works correctly
- [x] Errors return proper status codes
- [x] Pagination works
- [x] Filtering works
- [x] Background tasks work
- [x] API docs generated
- [x] Tests pass

## File List

### New Files
- `src/walltrack/api/positions_router.py` - Position & analysis API router

### Modified Files
- `src/walltrack/api/main.py` - Register new routers
- `src/walltrack/api/__init__.py` - Export routers

## API Summary

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | /api/positions | List positions with pagination |
| GET | /api/positions/{id} | Get position details |
| PATCH | /api/positions/{id}/strategy | Change position strategy |
| POST | /api/positions/{id}/simulate | Run what-if simulation |
| GET | /api/positions/{id}/timeline | Get event timeline |
| GET | /api/positions/{id}/timeline/export | Export timeline |
| POST | /api/analysis/global | Run multi-position analysis |
| GET | /api/analysis/positions/{id}/compare-all | Compare all strategies |
