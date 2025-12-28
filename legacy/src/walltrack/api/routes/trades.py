"""API routes for trade outcomes."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from walltrack.core.feedback.models import (
    AggregateMetrics,
    ExitReason,
    TradeOutcome,
    TradeOutcomeCreate,
    TradeQuery,
    TradeQueryResult,
)
from walltrack.core.feedback.trade_recorder import get_trade_recorder
from walltrack.data.supabase.client import get_supabase_client

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/", response_model=TradeOutcome)
async def record_trade(
    trade: TradeOutcomeCreate,
    supabase=Depends(get_supabase_client),
):
    """Record a new trade outcome."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.record_trade(trade)


@router.post("/{parent_trade_id}/partial", response_model=TradeOutcome)
async def record_partial_exit(
    parent_trade_id: UUID,
    exit_price: float = Query(..., gt=0),
    amount_tokens: float = Query(..., gt=0),
    exit_reason: ExitReason = Query(default=ExitReason.PARTIAL_TP),
    supabase=Depends(get_supabase_client),
):
    """Record a partial exit for an existing trade."""
    recorder = await get_trade_recorder(supabase)
    try:
        return await recorder.record_partial_exit(
            parent_trade_id=parent_trade_id,
            exit_price=Decimal(str(exit_price)),
            amount_tokens=Decimal(str(amount_tokens)),
            exit_reason=exit_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.get("/{trade_id}", response_model=TradeOutcome)
async def get_trade(
    trade_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get a single trade by ID."""
    recorder = await get_trade_recorder(supabase)
    trade = await recorder.get_trade(trade_id)
    if not trade:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


@router.get("/", response_model=TradeQueryResult)
async def query_trades(
    start_date: datetime | None = Query(default=None),
    end_date: datetime | None = Query(default=None),
    wallet_address: str | None = Query(default=None),
    token_address: str | None = Query(default=None),
    exit_reason: ExitReason | None = Query(default=None),
    is_win: bool | None = Query(default=None),
    min_pnl: float | None = Query(default=None),
    max_pnl: float | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    supabase=Depends(get_supabase_client),
):
    """Query trade history with filters."""
    recorder = await get_trade_recorder(supabase)
    query = TradeQuery(
        start_date=start_date,
        end_date=end_date,
        wallet_address=wallet_address,
        token_address=token_address,
        exit_reason=exit_reason,
        is_win=is_win,
        min_pnl=Decimal(str(min_pnl)) if min_pnl is not None else None,
        max_pnl=Decimal(str(max_pnl)) if max_pnl is not None else None,
        limit=limit,
        offset=offset,
    )
    return await recorder.query_trades(query)


@router.get("/aggregates/current", response_model=AggregateMetrics)
async def get_aggregates(
    force_refresh: bool = Query(default=False),
    supabase=Depends(get_supabase_client),
):
    """Get current aggregate trading metrics."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.get_aggregates(force_refresh=force_refresh)


@router.get("/position/{position_id}", response_model=list[TradeOutcome])
async def get_trades_for_position(
    position_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get all trades for a position."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.get_trades_for_position(position_id)


@router.get("/partials/{parent_trade_id}", response_model=list[TradeOutcome])
async def get_partial_trades(
    parent_trade_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Get all partial trades for a parent trade."""
    recorder = await get_trade_recorder(supabase)
    return await recorder.get_partial_trades(parent_trade_id)
