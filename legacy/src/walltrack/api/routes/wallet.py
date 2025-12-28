"""Wallet API routes for trading wallet management.

Provides endpoints for:
- Wallet status monitoring
- Balance retrieval
- Signing validation
- Safe mode management
"""

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from walltrack.models.trading_wallet import (
    SigningResult,
    WalletConnectionStatus,
)
from walltrack.services.solana.wallet_client import (
    WalletClient,
    WalletConnectionError,
    get_wallet_client,
)

# Dependency type annotation for cleaner function signatures
WalletDep = Annotated[WalletClient, Depends(get_wallet_client)]

router = APIRouter(prefix="/wallet", tags=["wallet"])


class WalletStatusResponse(BaseModel):
    """Wallet status for dashboard display."""

    public_key: str
    status: WalletConnectionStatus
    safe_mode: bool
    safe_mode_reason: str | None
    error_message: str | None
    last_validated: datetime | None
    is_ready_for_trading: bool


class BalanceResponse(BaseModel):
    """Wallet balance response."""

    sol_balance: float
    sol_balance_ui: float
    token_count: int
    total_value_sol: float
    tokens: list[dict]
    last_updated: datetime
    has_sufficient_sol: bool


class SafeModeRequest(BaseModel):
    """Request to change safe mode."""

    enabled: bool


@router.get("/status", response_model=WalletStatusResponse)
async def get_wallet_status(wallet: WalletDep) -> WalletStatusResponse:
    """Get current wallet connection status."""
    state = wallet.state
    return WalletStatusResponse(
        public_key=state.public_key,
        status=state.status,
        safe_mode=state.safe_mode,
        safe_mode_reason=state.safe_mode_reason.value if state.safe_mode_reason else None,
        error_message=state.error_message,
        last_validated=state.last_validated,
        is_ready_for_trading=wallet.is_ready_for_trading,
    )


@router.get("/balance", response_model=BalanceResponse)
async def get_wallet_balance(wallet: WalletDep, refresh: bool = False) -> BalanceResponse:
    """Get wallet balance (SOL + tokens)."""
    try:
        if refresh:
            await wallet.refresh_balance()

        balance = wallet.state.balance
        if not balance:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Balance not available - wallet may not be connected",
            )

        return BalanceResponse(
            sol_balance=balance.sol_balance,
            sol_balance_ui=balance.sol_balance_ui,
            token_count=len(balance.token_balances),
            total_value_sol=balance.total_value_sol,
            tokens=[tb.model_dump() for tb in balance.token_balances],
            last_updated=balance.last_updated,
            has_sufficient_sol=balance.has_sufficient_sol,
        )
    except WalletConnectionError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e),
        ) from e


@router.post("/validate", response_model=SigningResult)
async def validate_signing(wallet: WalletDep) -> SigningResult:
    """Validate wallet can sign transactions."""
    return await wallet.validate_signing()


@router.post("/safe-mode")
async def set_safe_mode(request: SafeModeRequest, wallet: WalletDep) -> dict:
    """Manually enable/disable safe mode."""
    wallet.set_manual_safe_mode(request.enabled)
    return {
        "safe_mode": wallet.state.safe_mode,
        "reason": wallet.state.safe_mode_reason.value if wallet.state.safe_mode_reason else None,
    }


@router.post("/safe-mode/exit")
async def exit_safe_mode(wallet: WalletDep) -> dict:
    """Attempt to exit safe mode by re-validating connectivity."""
    success = await wallet.exit_safe_mode()
    return {
        "success": success,
        "safe_mode": wallet.state.safe_mode,
        "error": wallet.state.error_message if not success else None,
    }


@router.get("/ready")
async def check_trading_ready(wallet: WalletDep) -> dict:
    """Quick check if wallet is ready for trading."""
    return {
        "ready": wallet.is_ready_for_trading,
        "status": wallet.state.status.value,
        "safe_mode": wallet.state.safe_mode,
    }
