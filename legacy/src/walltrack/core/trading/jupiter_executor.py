"""Jupiter trade executor wrapper for live trading."""

import time
from datetime import datetime

import structlog

from walltrack.config.settings import get_settings
from walltrack.services.jupiter.client import get_jupiter_client

log = structlog.get_logger()

# SOL mint address
SOL_MINT = "So11111111111111111111111111111111111111112"


class JupiterExecutor:
    """Live trade executor using Jupiter V6 API.

    Wraps the JupiterClient to provide a consistent interface
    matching the TradeExecutor protocol.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a live buy trade via Jupiter.

        Args:
            token_address: Token mint address to buy
            amount_sol: Amount of SOL to spend
            slippage_bps: Slippage tolerance in basis points

        Returns:
            Trade result dict
        """
        start_time = time.perf_counter()

        try:
            client = await get_jupiter_client()

            # Convert SOL to lamports
            amount_lamports = int(amount_sol * 1e9)

            # Get quote (SOL -> Token)
            quote = await client.get_quote(
                input_mint=SOL_MINT,
                output_mint=token_address,
                amount=amount_lamports,
                slippage_bps=slippage_bps,
            )

            log.info(
                "jupiter_buy_quote_received",
                token_address=token_address[:8],
                input_amount=amount_sol,
                output_amount=quote.output_amount,
                price_impact=quote.price_impact_pct,
            )

            # For actual execution, we need wallet keypair
            # This will be handled by the position manager
            execution_time_ms = (time.perf_counter() - start_time) * 1000

            return {
                "success": True,
                "simulated": False,
                "quote": {
                    "input_amount": quote.input_amount,
                    "output_amount": quote.output_amount,
                    "output_amount_min": quote.output_amount_min,
                    "price_impact_pct": quote.price_impact_pct,
                    "slippage_bps": quote.slippage_bps,
                },
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            log.error("jupiter_buy_error", error=str(e))

            return {
                "success": False,
                "simulated": False,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a live sell trade via Jupiter.

        Args:
            token_address: Token mint address to sell
            amount_tokens: Amount of tokens to sell
            slippage_bps: Slippage tolerance in basis points

        Returns:
            Trade result dict
        """
        start_time = time.perf_counter()

        try:
            client = await get_jupiter_client()

            # Amount in smallest unit (assuming 6 decimals)
            amount_smallest = int(amount_tokens)

            # Get quote (Token -> SOL)
            quote = await client.get_quote(
                input_mint=token_address,
                output_mint=SOL_MINT,
                amount=amount_smallest,
                slippage_bps=slippage_bps,
            )

            log.info(
                "jupiter_sell_quote_received",
                token_address=token_address[:8],
                input_amount=amount_tokens,
                output_amount=quote.output_amount,
                price_impact=quote.price_impact_pct,
            )

            execution_time_ms = (time.perf_counter() - start_time) * 1000

            return {
                "success": True,
                "simulated": False,
                "quote": {
                    "input_amount": quote.input_amount,
                    "output_amount": quote.output_amount,
                    "output_amount_min": quote.output_amount_min,
                    "price_impact_pct": quote.price_impact_pct,
                    "slippage_bps": quote.slippage_bps,
                },
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            execution_time_ms = (time.perf_counter() - start_time) * 1000
            log.error("jupiter_sell_error", error=str(e))

            return {
                "success": False,
                "simulated": False,
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.utcnow().isoformat(),
            }
