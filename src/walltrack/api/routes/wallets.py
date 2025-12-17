"""Wallet API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from walltrack.api.dependencies import (
    BlacklistServiceDep,
    get_discovery_scanner,
    get_wallet_profiler,
    get_wallet_repo,
)
from walltrack.data.models.wallet import DiscoveryResult, TokenLaunch, Wallet, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.profiler import WalletProfiler
from walltrack.discovery.scanner import WalletDiscoveryScanner

router = APIRouter(prefix="/wallets", tags=["wallets"])


class DiscoveryRequest(BaseModel):
    """Request to discover wallets from token launches."""

    tokens: list[TokenLaunch] = Field(..., min_length=1, max_length=10)
    early_window_minutes: int = Field(default=30, ge=5, le=120)
    min_profit_pct: float = Field(default=50.0, ge=10.0, le=500.0)


class WalletListResponse(BaseModel):
    """Response for wallet list."""

    wallets: list[Wallet]
    total: int
    limit: int
    offset: int


class ProfileBatchRequest(BaseModel):
    """Request to profile multiple wallets."""

    addresses: list[str] = Field(..., min_length=1, max_length=50)
    lookback_days: int = Field(default=90, ge=7, le=365)
    force_update: bool = Field(default=False)


class ProfileResponse(BaseModel):
    """Response for batch profiling operation."""

    profiled: list[Wallet]
    total_requested: int
    successful: int
    failed: int


@router.post("/discover", response_model=list[DiscoveryResult])
async def discover_wallets(
    request: DiscoveryRequest,
    scanner: Annotated[WalletDiscoveryScanner, Depends(get_discovery_scanner)],
) -> list[DiscoveryResult]:
    """
    Discover wallets from successful token launches.

    Analyzes early buyers and filters to profitable exits.
    """
    results = await scanner.discover_from_multiple_tokens(
        token_launches=request.tokens,
        early_window_minutes=request.early_window_minutes,
        min_profit_pct=request.min_profit_pct,
    )
    return results


@router.post("/profile", response_model=ProfileResponse)
async def profile_wallets(
    request: ProfileBatchRequest,
    profiler: Annotated[WalletProfiler, Depends(get_wallet_profiler)],
) -> ProfileResponse:
    """
    Profile multiple wallets concurrently.

    Analyzes trading history and calculates performance metrics.
    """
    wallets = await profiler.profile_batch(
        addresses=request.addresses,
        lookback_days=request.lookback_days,
    )

    return ProfileResponse(
        profiled=wallets,
        total_requested=len(request.addresses),
        successful=len(wallets),
        failed=len(request.addresses) - len(wallets),
    )


@router.post("/{address}/profile", response_model=Wallet)
async def profile_single_wallet(
    address: str,
    profiler: Annotated[WalletProfiler, Depends(get_wallet_profiler)],
    lookback_days: Annotated[int, Query(ge=7, le=365)] = 90,
    force_update: Annotated[bool, Query()] = False,
) -> Wallet:
    """
    Profile a single wallet's performance.

    Fetches trading history and calculates metrics including
    win rate, PnL, timing percentile, and behavioral patterns.
    """
    wallet = await profiler.profile_wallet(
        address=address,
        lookback_days=lookback_days,
        force_update=force_update,
    )
    return wallet


@router.get("", response_model=WalletListResponse)
async def list_wallets(
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
    wallet_status: Annotated[WalletStatus | None, Query(alias="status")] = None,
    min_score: Annotated[float, Query(ge=0.0, le=1.0)] = 0.0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> WalletListResponse:
    """List wallets with filtering and pagination."""
    if wallet_status:
        wallets = await repo.get_by_status(wallet_status, limit=limit)
    else:
        wallets = await repo.get_active_wallets(
            min_score=min_score, limit=limit, offset=offset
        )

    total = await repo.count_by_status(wallet_status)

    return WalletListResponse(
        wallets=wallets,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{address}", response_model=Wallet)
async def get_wallet(
    address: str,
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
) -> Wallet:
    """Get wallet by address."""
    wallet = await repo.get_by_address(address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {address} not found",
        )
    return wallet


@router.patch("/{address}/status")
async def update_wallet_status(
    address: str,
    new_status: WalletStatus,
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
    reason: str | None = None,
) -> dict[str, str]:
    """Update wallet status."""
    wallet = await repo.get_by_address(address)
    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {address} not found",
        )

    await repo.set_status(address, new_status, reason)
    return {"message": f"Wallet status updated to {new_status.value}"}


@router.delete("/{address}")
async def delete_wallet(
    address: str,
    repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
) -> dict[str, str]:
    """Delete a wallet."""
    deleted = await repo.delete(address)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Wallet {address} not found",
        )
    return {"message": f"Wallet {address} deleted"}


@router.post("/{address}/blacklist", response_model=Wallet)
async def blacklist_wallet(
    address: str,
    service: BlacklistServiceDep,
    reason: str = Query(..., min_length=1),
) -> Wallet:
    """Blacklist a specific wallet."""
    try:
        return await service.add_to_blacklist(address=address, reason=reason)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        ) from None


@router.delete("/{address}/blacklist", response_model=Wallet)
async def unblacklist_wallet(
    address: str,
    service: BlacklistServiceDep,
) -> Wallet:
    """Remove wallet from blacklist."""
    try:
        return await service.remove_from_blacklist(address=address)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from None
