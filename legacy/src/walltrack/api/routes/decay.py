"""Decay detection API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from walltrack.api.dependencies import (
    get_decay_detector,
    get_decay_event_repo,
    get_wallet_repo,
)
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.decay_detector import DecayDetector

router = APIRouter(prefix="/decay", tags=["decay"])


class DecayCheckResponse(BaseModel):
    """Response from decay check."""

    events_detected: int
    decay_detected: int
    recoveries: int
    consecutive_losses: int


class DecayEventResponse(BaseModel):
    """Decay event response model."""

    id: str
    wallet_address: str
    event_type: str
    rolling_win_rate: float
    lifetime_win_rate: float
    consecutive_losses: int
    score_before: float
    score_after: float
    created_at: str


class WalletDecayStatus(BaseModel):
    """Response for single wallet decay status."""

    wallet: str
    event: dict[str, Any] | None
    current_status: str
    rolling_win_rate: float | None
    consecutive_losses: int


@router.post("/check", response_model=DecayCheckResponse)
async def run_decay_check(
    detector: Annotated[DecayDetector, Depends(get_decay_detector)],
) -> DecayCheckResponse:
    """
    Manually trigger decay check for all wallets.

    This is normally run on a schedule, but can be triggered manually.
    """
    events = await detector.check_all_wallets()

    return DecayCheckResponse(
        events_detected=len(events),
        decay_detected=sum(1 for e in events if e.event_type == "decay_detected"),
        recoveries=sum(1 for e in events if e.event_type == "recovery"),
        consecutive_losses=sum(1 for e in events if e.event_type == "consecutive_losses"),
    )


@router.post("/check/{address}", response_model=WalletDecayStatus)
async def check_wallet_decay(
    address: str,
    detector: Annotated[DecayDetector, Depends(get_decay_detector)],
    wallet_repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
) -> WalletDecayStatus:
    """Check decay for a specific wallet."""
    wallet = await wallet_repo.get_by_address(address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {address} not found",
        )

    event = await detector.check_wallet_decay(wallet)

    return WalletDecayStatus(
        wallet=address,
        event=event.to_dict() if event else None,
        current_status=wallet.status.value,
        rolling_win_rate=wallet.rolling_win_rate,
        consecutive_losses=wallet.consecutive_losses,
    )


@router.get("/events", response_model=list[DecayEventResponse])
async def get_decay_events(
    repo: Annotated[DecayEventRepository, Depends(get_decay_event_repo)],
    event_type: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[DecayEventResponse]:
    """Get recent decay events."""
    events = await repo.get_recent_events(event_type=event_type, limit=limit)
    return [DecayEventResponse(**e) for e in events]


@router.get("/events/{address}", response_model=list[DecayEventResponse])
async def get_wallet_decay_events(
    address: str,
    repo: Annotated[DecayEventRepository, Depends(get_decay_event_repo)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[DecayEventResponse]:
    """Get decay events for a specific wallet."""
    events = await repo.get_wallet_events(wallet_address=address, limit=limit)
    return [DecayEventResponse(**e) for e in events]
