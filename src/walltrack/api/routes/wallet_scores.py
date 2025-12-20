"""API routes for wallet scores."""

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from walltrack.core.feedback.score_models import (
    BatchUpdateRequest,
    BatchUpdateResult,
    ScoreUpdateInput,
    ScoreUpdateResult,
    WalletMetrics,
    WalletScoreHistory,
)
from walltrack.core.feedback.score_updater import get_score_updater
from walltrack.data.supabase.client import get_supabase_client

router = APIRouter(prefix="/wallet-scores", tags=["wallet-scores"])


@router.post("/update", response_model=ScoreUpdateResult)
async def update_from_trade(
    update_input: ScoreUpdateInput,
    supabase=Depends(get_supabase_client),
):
    """Update wallet score from trade outcome."""
    updater = await get_score_updater(supabase)
    return await updater.update_from_trade(update_input)


@router.post("/batch", response_model=BatchUpdateResult)
async def batch_update(
    request: BatchUpdateRequest,
    supabase=Depends(get_supabase_client),
):
    """Process batch of score updates."""
    updater = await get_score_updater(supabase)
    return await updater.batch_update(request)


@router.post("/{wallet_address}/adjust", response_model=ScoreUpdateResult)
async def manual_adjust(
    wallet_address: str,
    adjustment: float = Query(..., ge=-1, le=1),
    reason: str = Query(..., min_length=3),
    supabase=Depends(get_supabase_client),
):
    """Manually adjust wallet score."""
    updater = await get_score_updater(supabase)
    try:
        return await updater.manual_adjust(
            wallet_address=wallet_address,
            adjustment=Decimal(str(adjustment)),
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from None


@router.get("/{wallet_address}", response_model=WalletMetrics)
async def get_wallet_metrics(
    wallet_address: str,
    supabase=Depends(get_supabase_client),
):
    """Get current metrics for a wallet."""
    updater = await get_score_updater(supabase)
    metrics = await updater.get_wallet_metrics(wallet_address)
    if not metrics:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return metrics


@router.get("/{wallet_address}/history", response_model=list[WalletScoreHistory])
async def get_score_history(
    wallet_address: str,
    limit: int = Query(default=50, ge=1, le=500),
    supabase=Depends(get_supabase_client),
):
    """Get score history for a wallet."""
    updater = await get_score_updater(supabase)
    return await updater.get_score_history(wallet_address, limit=limit)


@router.get("/flagged/all", response_model=list[WalletMetrics])
async def get_flagged_wallets(
    supabase=Depends(get_supabase_client),
):
    """Get all wallets flagged for decay."""
    updater = await get_score_updater(supabase)
    return await updater.get_flagged_wallets()
