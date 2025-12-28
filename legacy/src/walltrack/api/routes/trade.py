"""Trade execution API routes.

Provides endpoints for:
- Trade execution via Jupiter/Raydium
- Quote preview without execution
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from walltrack.constants.solana import LAMPORTS_PER_SOL, WSOL_MINT
from walltrack.models.trade import SwapDirection, TradeRequest
from walltrack.services.jupiter.client import get_jupiter_client
from walltrack.services.trade.executor import TradeExecutor, get_trade_executor

router = APIRouter(prefix="/trade", tags=["trade"])

# Dependency type annotation
ExecutorDep = Annotated[TradeExecutor, Depends(get_trade_executor)]


class ExecuteTradeRequest(BaseModel):
    """API request to execute trade."""

    signal_id: str
    token_address: str
    direction: SwapDirection
    amount_sol: float
    slippage_bps: int = 100


class TradeResponse(BaseModel):
    """API response for trade execution."""

    success: bool
    tx_signature: str | None
    input_amount: int
    output_amount: int | None
    entry_price: float | None
    execution_time_ms: float
    quote_source: str
    error_message: str | None


class QuoteResponse(BaseModel):
    """API response for quote preview."""

    input_amount: int
    output_amount: int
    output_amount_min: int
    price_impact_pct: float
    effective_price: float
    route_count: int
    expires_at: str | None


@router.post("/execute", response_model=TradeResponse)
async def execute_trade(
    request: ExecuteTradeRequest,
    executor: ExecutorDep,
) -> TradeResponse:
    """Execute a trade via Jupiter/Raydium."""
    trade_request = TradeRequest(
        signal_id=request.signal_id,
        token_address=request.token_address,
        direction=request.direction,
        amount_sol=request.amount_sol,
        slippage_bps=request.slippage_bps,
    )

    result = await executor.execute(trade_request)

    return TradeResponse(
        success=result.success,
        tx_signature=result.tx_signature,
        input_amount=result.input_amount,
        output_amount=result.output_amount,
        entry_price=result.entry_price,
        execution_time_ms=result.execution_time_ms,
        quote_source=result.quote_source,
        error_message=result.error_message,
    )


@router.get("/quote", response_model=QuoteResponse)
async def get_quote(
    token_address: str,
    direction: SwapDirection,
    amount_sol: float,
    slippage_bps: int = 100,
) -> QuoteResponse:
    """Get quote without executing trade."""
    jupiter = await get_jupiter_client()

    if direction == SwapDirection.BUY:
        input_mint = WSOL_MINT
        output_mint = token_address
    else:
        input_mint = token_address
        output_mint = WSOL_MINT

    amount = int(amount_sol * LAMPORTS_PER_SOL)

    quote = await jupiter.get_quote(
        input_mint=input_mint,
        output_mint=output_mint,
        amount=amount,
        slippage_bps=slippage_bps,
    )

    return QuoteResponse(
        input_amount=quote.input_amount,
        output_amount=quote.output_amount,
        output_amount_min=quote.output_amount_min,
        price_impact_pct=quote.price_impact_pct,
        effective_price=quote.effective_price,
        route_count=len(quote.route_plan),
        expires_at=quote.expires_at.isoformat() if quote.expires_at else None,
    )
