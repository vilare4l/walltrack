"""Simulated trade executor for paper trading."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from walltrack.config.settings import get_settings
from walltrack.services.dexscreener.client import DexScreenerClient

log = structlog.get_logger()

# SOL mint address on Solana
SOL_MINT = "So11111111111111111111111111111111111111112"


class SimulatedTradeExecutor:
    """Execute simulated trades using real market prices.

    Used in simulation mode for paper trading and testing.
    Fetches real-time prices from DexScreener and applies configurable slippage.
    """

    def __init__(self) -> None:
        self._settings = get_settings()
        self._slippage_bps = self._settings.simulation_slippage_bps
        self._dex_client: DexScreenerClient | None = None

    async def _get_dex_client(self) -> DexScreenerClient:
        """Get or create DexScreener client."""
        if self._dex_client is None:
            self._dex_client = DexScreenerClient()
        return self._dex_client

    async def _get_token_price(self, token_address: str) -> Decimal | None:
        """Get current token price in USD from DexScreener."""
        client = await self._get_dex_client()
        result = await client.fetch_token(token_address)

        if result.success and result.token and result.token.price_usd:
            return Decimal(str(result.token.price_usd))
        return None

    async def _get_sol_price(self) -> Decimal:
        """Get current SOL price in USD."""
        price = await self._get_token_price(SOL_MINT)
        if price:
            return price
        # Fallback price if API fails
        return Decimal("100")

    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        slippage_bps: int | None = None,
    ) -> dict:
        """Simulate a buy trade using real market prices.

        Args:
            token_address: Token mint address to buy
            amount_sol: Amount of SOL to spend
            slippage_bps: Slippage tolerance in basis points (None uses default)

        Returns:
            Simulated trade result dict with execution details
        """
        slippage = slippage_bps if slippage_bps is not None else self._slippage_bps

        # Get current market price from DexScreener
        market_price = await self._get_token_price(token_address)
        if market_price is None:
            log.warning(
                "simulated_buy_no_price",
                token_address=token_address[:8],
                message="Using fallback price calculation",
            )
            # Fallback: assume a generic price for testing
            market_price = Decimal("0.0001")

        # Apply slippage (worse price for buyer - price goes up)
        slippage_multiplier = Decimal(1) + Decimal(slippage) / Decimal(10000)
        execution_price = market_price * slippage_multiplier

        # Get SOL price to calculate USD value
        sol_price_usd = await self._get_sol_price()
        usd_amount = Decimal(str(amount_sol)) * sol_price_usd

        # Calculate tokens received
        tokens_received = usd_amount / execution_price if execution_price > 0 else Decimal(0)

        # Create trade record
        trade_id = str(uuid4())
        trade_record = {
            "id": trade_id,
            "token_address": token_address,
            "side": "buy",
            "amount_sol": amount_sol,
            "amount_tokens": float(tokens_received),
            "price_usd": float(execution_price),
            "slippage_bps": slippage,
            "simulated": True,
            "tx_signature": f"SIM_{trade_id[:8]}",
            "executed_at": datetime.now(UTC).isoformat(),
            "market_price_at_execution": float(market_price),
            "success": True,
        }

        log.info(
            "simulated_buy_executed",
            token=token_address[:8],
            amount_sol=amount_sol,
            tokens_received=float(tokens_received),
            price=float(execution_price),
            market_price=float(market_price),
            slippage_bps=slippage,
        )

        return trade_record

    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_bps: int | None = None,
    ) -> dict:
        """Simulate a sell trade using real market prices.

        Args:
            token_address: Token mint address to sell
            amount_tokens: Amount of tokens to sell
            slippage_bps: Slippage tolerance in basis points (None uses default)

        Returns:
            Simulated trade result dict with execution details
        """
        slippage = slippage_bps if slippage_bps is not None else self._slippage_bps

        # Get current market price from DexScreener
        market_price = await self._get_token_price(token_address)
        if market_price is None:
            log.warning(
                "simulated_sell_no_price",
                token_address=token_address[:8],
                message="Using fallback price calculation",
            )
            market_price = Decimal("0.0001")

        # Apply slippage (worse price for seller - price goes down)
        slippage_multiplier = Decimal(1) - Decimal(slippage) / Decimal(10000)
        execution_price = market_price * slippage_multiplier

        # Calculate USD value and SOL received
        usd_amount = Decimal(str(amount_tokens)) * execution_price
        sol_price_usd = await self._get_sol_price()
        sol_received = usd_amount / sol_price_usd if sol_price_usd > 0 else Decimal(0)

        # Create trade record
        trade_id = str(uuid4())
        trade_record = {
            "id": trade_id,
            "token_address": token_address,
            "side": "sell",
            "amount_sol": float(sol_received),
            "amount_tokens": amount_tokens,
            "price_usd": float(execution_price),
            "slippage_bps": slippage,
            "simulated": True,
            "tx_signature": f"SIM_{trade_id[:8]}",
            "executed_at": datetime.now(UTC).isoformat(),
            "market_price_at_execution": float(market_price),
            "success": True,
        }

        log.info(
            "simulated_sell_executed",
            token=token_address[:8],
            amount_tokens=amount_tokens,
            sol_received=float(sol_received),
            price=float(execution_price),
            market_price=float(market_price),
            slippage_bps=slippage,
        )

        return trade_record
