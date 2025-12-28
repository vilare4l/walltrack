"""Blacklist management API routes."""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.api.dependencies import (
    BlacklistHistoryRepoDep,
    BlacklistServiceDep,
)
from walltrack.data.models.wallet import Wallet

router = APIRouter(prefix="/blacklist", tags=["blacklist"])


class BlacklistRequest(BaseModel):
    """Request to blacklist a wallet."""

    address: str = Field(..., min_length=32, max_length=44)
    reason: str = Field(..., min_length=1, max_length=500)


class UnblacklistRequest(BaseModel):
    """Request to remove wallet from blacklist."""

    address: str = Field(..., min_length=32, max_length=44)


class BlacklistResponse(BaseModel):
    """Response from blacklist operation."""

    success: bool
    wallet: Wallet
    message: str


class BlacklistHistoryEntry(BaseModel):
    """Blacklist history entry."""

    id: str
    wallet_address: str
    action: str
    reason: str | None
    operator_id: str | None
    previous_status: str | None
    created_at: str


@router.post("/add", response_model=BlacklistResponse)
async def add_to_blacklist(
    request: BlacklistRequest,
    service: BlacklistServiceDep,
    history_repo: BlacklistHistoryRepoDep,
) -> BlacklistResponse:
    """
    Add a wallet to the blacklist.

    Blacklisted wallets are excluded from all signal processing.
    """
    try:
        wallet = await service.add_to_blacklist(
            address=request.address,
            reason=request.reason,
        )

        # Record in history
        await history_repo.record_blacklist(
            wallet_address=request.address,
            reason=request.reason,
            previous_status="active",  # Simplified
        )

        return BlacklistResponse(
            success=True,
            wallet=wallet,
            message=f"Wallet {request.address} has been blacklisted",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


@router.post("/remove", response_model=BlacklistResponse)
async def remove_from_blacklist(
    request: UnblacklistRequest,
    service: BlacklistServiceDep,
    history_repo: BlacklistHistoryRepoDep,
) -> BlacklistResponse:
    """
    Remove a wallet from the blacklist.

    Wallet will resume normal signal processing.
    """
    try:
        wallet = await service.remove_from_blacklist(address=request.address)

        # Record in history
        await history_repo.record_unblacklist(wallet_address=request.address)

        return BlacklistResponse(
            success=True,
            wallet=wallet,
            message=f"Wallet {request.address} has been removed from blacklist",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None


@router.get("/check/{address}")
async def check_blacklist_status(
    address: str,
    service: BlacklistServiceDep,
) -> dict[str, str | bool]:
    """Check if a wallet is blacklisted."""
    is_blacklisted = await service.is_blacklisted(address)
    return {
        "address": address,
        "is_blacklisted": is_blacklisted,
    }


@router.get("/list", response_model=list[Wallet])
async def list_blacklisted_wallets(
    service: BlacklistServiceDep,
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Wallet]:
    """Get all blacklisted wallets."""
    return await service.get_blacklisted_wallets(limit=limit)


@router.get("/history", response_model=list[BlacklistHistoryEntry])
async def get_blacklist_history(
    history_repo: BlacklistHistoryRepoDep,
    action: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[BlacklistHistoryEntry]:
    """Get recent blacklist actions."""
    history = await history_repo.get_recent_actions(action=action, limit=limit)
    return [BlacklistHistoryEntry(**h) for h in history]


@router.get("/history/{address}", response_model=list[BlacklistHistoryEntry])
async def get_wallet_blacklist_history(
    address: str,
    history_repo: BlacklistHistoryRepoDep,
    limit: int = Query(default=20, ge=1, le=100),
) -> list[BlacklistHistoryEntry]:
    """Get blacklist history for a specific wallet."""
    history = await history_repo.get_wallet_history(
        wallet_address=address, limit=limit
    )
    return [BlacklistHistoryEntry(**h) for h in history]
