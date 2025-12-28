"""API routes for positions endpoints."""

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

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/positions", tags=["positions"])


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
