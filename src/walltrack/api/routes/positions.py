"""API routes for positions and simulation endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.data.supabase.client import get_supabase_client
from walltrack.services.exit.exit_strategy_service import get_exit_strategy_service
from walltrack.services.positions.timeline_service import (
    PositionEventType,
    get_timeline_service,
)
from walltrack.services.simulation.global_analyzer import get_global_analyzer
from walltrack.services.simulation.strategy_comparator import (
    format_comparison_table,
    get_strategy_comparator,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])
analysis_router = APIRouter(prefix="/analysis", tags=["analysis"])


# =============================================================================
# Request/Response Models
# =============================================================================


class PositionSummary(BaseModel):
    """Summary of a position for list view."""

    id: str
    token_address: str
    token_symbol: str | None
    entry_price: float
    current_price: float | None
    entry_time: datetime
    exit_time: datetime | None
    status: str
    pnl_pct: float | None
    pnl_sol: float | None
    size_sol: float
    exit_strategy_name: str | None


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
    token_symbol: str | None
    entry_price: float
    exit_price: float | None
    current_price: float | None
    entry_time: datetime
    exit_time: datetime | None
    status: str
    pnl_pct: float | None
    pnl_sol: float | None
    size_sol: float
    remaining_pct: float
    exit_strategy_id: str | None
    exit_strategy_name: str | None
    exit_type: str | None
    conviction_tier: str | None
    strategy_levels: dict | None
    price_history_count: int


class ChangeStrategyRequest(BaseModel):
    """Request to change position strategy."""

    strategy_id: str = Field(..., description="New strategy ID")
    reason: str | None = Field(None, description="Reason for change")


class ChangeStrategyResponse(BaseModel):
    """Response after changing strategy."""

    success: bool
    position_id: str
    old_strategy_id: str | None
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
    actual_pnl_pct: float | None
    delta_pct: float | None
    exit_time: datetime | None
    exit_types: list[str]
    is_best: bool


class SimulationResponse(BaseModel):
    """Simulation comparison response."""

    position_id: str
    entry_price: float
    actual_exit_price: float | None
    actual_pnl_pct: float | None
    rows: list[SimulationRowResponse]
    best_strategy_id: str
    best_strategy_name: str
    best_improvement_pct: float | None
    markdown_table: str


class TimelineEventResponse(BaseModel):
    """Single timeline event."""

    id: str
    event_type: str
    timestamp: datetime
    price_at_event: float | None
    data_before: dict | None
    data_after: dict | None
    metadata: dict
    comment: str | None


class TimelineResponse(BaseModel):
    """Position timeline response."""

    position_id: str
    token_symbol: str
    entry_time: datetime
    exit_time: datetime | None
    duration_hours: float
    events: list[TimelineEventResponse]
    total_events: int


class GlobalAnalysisRequest(BaseModel):
    """Request for global analysis."""

    position_ids: list[str] = Field(
        default=[], description="Position IDs (empty=all closed)"
    )
    strategy_ids: list[str] = Field(
        default=[], description="Strategy IDs (empty=all active)"
    )
    days_back: int = Field(default=30, ge=1, le=365)
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
    analysis_time_seconds: float
    strategy_stats: list[StrategyStatsResponse]
    recommended_strategy_id: str
    recommended_strategy_name: str
    summary_markdown: str


# =============================================================================
# Helper Functions
# =============================================================================


def _parse_datetime(value: str) -> datetime:
    """Parse ISO datetime string."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _calculate_strategy_levels(
    strategy_rules: list[dict],
    entry_price: Decimal,
) -> dict:
    """Calculate price levels from strategy rules."""
    levels = {}

    for rule in strategy_rules:
        if not rule.get("enabled"):
            continue

        trigger_pct = rule.get("trigger_pct")
        if trigger_pct is not None:
            price = entry_price * (1 + Decimal(str(trigger_pct)) / 100)
            levels[rule["rule_type"]] = {
                "price": float(price),
                "trigger_pct": trigger_pct,
                "exit_pct": rule.get("exit_pct"),
            }

    return levels


# =============================================================================
# Position Endpoints
# =============================================================================


@router.get("", response_model=PositionListResponse)
async def list_positions(
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status: active, closed"
    ),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> PositionListResponse:
    """
    List positions with pagination.

    - **status**: Filter by position status (active/closed)
    - **limit**: Max positions to return (1-100)
    - **offset**: Pagination offset
    """
    client = await get_supabase_client()

    query = (
        client.table("positions")
        .select(
            "id, token_address, token_symbol, entry_price, exit_price, "
            "entry_time, exit_time, status, pnl_pct, pnl_sol, size_sol, "
            "exit_strategies(name)",
            count="exact",
        )
    )

    if status_filter:
        query = query.eq("status", status_filter)

    query = query.order("entry_time", desc=True).range(offset, offset + limit - 1)

    result = await query.execute()

    positions = []
    for row in result.data:
        strategy = row.get("exit_strategies")
        positions.append(
            PositionSummary(
                id=row["id"],
                token_address=row["token_address"],
                token_symbol=row.get("token_symbol"),
                entry_price=float(row["entry_price"]),
                current_price=(
                    float(row["exit_price"]) if row.get("exit_price") else None
                ),
                entry_time=_parse_datetime(row["entry_time"]),
                exit_time=(
                    _parse_datetime(row["exit_time"]) if row.get("exit_time") else None
                ),
                status=row["status"],
                pnl_pct=float(row["pnl_pct"]) if row.get("pnl_pct") else None,
                pnl_sol=float(row["pnl_sol"]) if row.get("pnl_sol") else None,
                size_sol=float(row["size_sol"]),
                exit_strategy_name=strategy.get("name") if strategy else None,
            )
        )

    total = result.count or len(positions)

    return PositionListResponse(
        positions=positions,
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
    )


@router.get("/{position_id}", response_model=PositionDetails)
async def get_position(position_id: str) -> PositionDetails:
    """
    Get detailed position information.

    Includes current price, strategy levels, and price history count.
    """
    client = await get_supabase_client()

    result = await (
        client.table("positions")
        .select("*, exit_strategies(id, name, rules)")
        .eq("id", position_id)
        .single()
        .execute()
    )

    if not result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    row = result.data

    # Get price history count
    history_result = await (
        client.table("position_price_history")
        .select("id", count="exact")
        .eq("position_id", position_id)
        .execute()
    )

    price_history_count = history_result.count or 0

    # Calculate strategy levels if active
    strategy_levels = None
    strategy = row.get("exit_strategies")
    if strategy and row["status"] == "active":
        entry_price = Decimal(str(row["entry_price"]))
        strategy_levels = _calculate_strategy_levels(
            strategy.get("rules", []),
            entry_price,
        )

    return PositionDetails(
        id=row["id"],
        token_address=row["token_address"],
        token_symbol=row.get("token_symbol"),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]) if row.get("exit_price") else None,
        current_price=(
            float(row["current_price"]) if row.get("current_price") else None
        ),
        entry_time=_parse_datetime(row["entry_time"]),
        exit_time=_parse_datetime(row["exit_time"]) if row.get("exit_time") else None,
        status=row["status"],
        pnl_pct=float(row["pnl_pct"]) if row.get("pnl_pct") else None,
        pnl_sol=float(row["pnl_sol"]) if row.get("pnl_sol") else None,
        size_sol=float(row["size_sol"]),
        remaining_pct=float(row.get("remaining_pct", 100)),
        exit_strategy_id=row.get("exit_strategy_id"),
        exit_strategy_name=strategy["name"] if strategy else None,
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
) -> ChangeStrategyResponse:
    """
    Change the exit strategy for an active position.

    - Validates position is active
    - Validates strategy exists and is active
    - Recalculates exit levels
    - Logs the change event
    """
    client = await get_supabase_client()
    strategy_service = await get_exit_strategy_service()
    timeline_service = await get_timeline_service()

    # Get position
    pos_result = await (
        client.table("positions")
        .select("*, exit_strategies(id, name)")
        .eq("id", position_id)
        .single()
        .execute()
    )

    if not pos_result.data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Position not found",
        )

    position = pos_result.data

    if position["status"] != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Can only change strategy for active positions",
        )

    # Get new strategy
    new_strategy = await strategy_service.get(request.strategy_id)
    if not new_strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Strategy not found",
        )

    if new_strategy.status != "active":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Strategy is not active",
        )

    # Calculate new levels
    entry_price = Decimal(str(position["entry_price"]))
    new_levels = {}

    for rule in new_strategy.rules:
        if not rule.enabled:
            continue

        if rule.trigger_pct is not None:
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
    await (
        client.table("positions")
        .update({"exit_strategy_id": request.strategy_id})
        .eq("id", position_id)
        .execute()
    )

    # Log event in background
    async def log_change() -> None:
        await timeline_service.log_event(
            position_id=position_id,
            event_type=PositionEventType.STRATEGY_CHANGED,
            price_at_event=(
                Decimal(str(position["current_price"]))
                if position.get("current_price")
                else None
            ),
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
async def simulate_position(
    position_id: str,
    request: SimulateRequest,
) -> SimulationResponse:
    """
    Run what-if simulation on a position.

    Compares multiple exit strategies against the actual result.
    """
    comparator = await get_strategy_comparator()

    result = await comparator.compare(position_id, request.strategy_ids)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not simulate. Check if position has price history.",
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
        actual_exit_price=(
            float(result.actual_exit_price) if result.actual_exit_price else None
        ),
        actual_pnl_pct=(
            float(result.actual_pnl_pct) if result.actual_pnl_pct else None
        ),
        rows=rows,
        best_strategy_id=result.best_strategy_id,
        best_strategy_name=result.best_strategy_name,
        best_improvement_pct=(
            float(result.best_improvement_pct) if result.best_improvement_pct else None
        ),
        markdown_table=markdown_table,
    )


@router.get("/{position_id}/timeline", response_model=TimelineResponse)
async def get_position_timeline(
    position_id: str,
    event_types: str | None = Query(
        None, description="Comma-separated event types"
    ),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> TimelineResponse:
    """
    Get position event timeline.

    - **event_types**: Filter by event types (comma-separated)
    - **limit**: Max events to return
    - **offset**: Pagination offset
    """
    timeline_service = await get_timeline_service()

    types: list[PositionEventType] | None = None
    if event_types:
        valid_values = [e.value for e in PositionEventType]
        types = [
            PositionEventType(t.strip())
            for t in event_types.split(",")
            if t.strip() in valid_values
        ]

    try:
        timeline = await timeline_service.get_timeline(
            position_id=position_id,
            event_types=types,
            limit=limit,
            offset=offset,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from e

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
    format_type: str = Query(
        "json", alias="format", description="Export format: json or csv"
    ),
) -> dict:
    """Export position timeline to JSON or CSV."""
    timeline_service = await get_timeline_service()

    try:
        data = await timeline_service.export_timeline(position_id, format_type)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e

    return {"data": data, "format": format_type}


# =============================================================================
# Analysis Endpoints
# =============================================================================


@analysis_router.post("/global", response_model=GlobalAnalysisResponse)
async def run_global_analysis(request: GlobalAnalysisRequest) -> GlobalAnalysisResponse:
    """
    Run global analysis across multiple positions.

    Compares strategies and identifies the best performer.
    """
    analyzer = await get_global_analyzer()

    result = await analyzer.analyze(
        position_ids=request.position_ids or None,
        strategy_ids=request.strategy_ids or None,
        days_back=request.days_back,
        limit=request.limit,
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not run analysis. No valid positions found.",
        )

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

    # Build summary markdown
    summary_md = f"""## Global Analysis Summary

**Positions Analyzed:** {result.total_positions}
**Strategies Compared:** {result.strategies_compared}
**Analysis Time:** {result.analysis_duration_seconds:.2f}s

### Recommended Strategy
**{result.recommended_strategy_name}**

### Strategy Performance

| Strategy | Avg P&L | Win Rate | Avg Improvement |
|----------|---------|----------|-----------------|
"""
    for s in stats:
        summary_md += (
            f"| {s.strategy_name} | {s.avg_pnl_pct:+.2f}% | "
            f"{s.win_rate_pct:.1f}% | {s.avg_improvement_pct:+.2f}% |\n"
        )

    return GlobalAnalysisResponse(
        total_positions=result.total_positions,
        strategies_compared=result.strategies_compared,
        analysis_time_seconds=result.analysis_duration_seconds,
        strategy_stats=stats,
        recommended_strategy_id=result.recommended_strategy_id,
        recommended_strategy_name=result.recommended_strategy_name,
        summary_markdown=summary_md,
    )


@analysis_router.get("/positions/{position_id}/compare-all")
async def compare_all_strategies(position_id: str) -> dict:
    """Quick endpoint to compare all active strategies on a single position."""
    comparator = await get_strategy_comparator()

    result = await comparator.compare_all_active_strategies(position_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not compare. Check if position has price history.",
        )

    return {
        "position_id": position_id,
        "best_strategy": result.best_strategy_name,
        "best_improvement_pct": (
            float(result.best_improvement_pct) if result.best_improvement_pct else None
        ),
        "comparison_table": format_comparison_table(result),
    }
