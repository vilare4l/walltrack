"""Order executor with retry logic."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from walltrack.models.order import Order, OrderStatus

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.order_repo import OrderRepository
    from walltrack.services.jupiter.client import JupiterClient
    from solders.keypair import Keypair

logger = structlog.get_logger(__name__)

# SOL mint address
SOL_MINT = "So11111111111111111111111111111111111111112"


@dataclass
class OrderResult:
    """Result of order execution attempt."""

    success: bool
    order: Order
    tx_signature: str | None = None
    actual_price: Decimal | None = None
    amount_tokens: Decimal | None = None
    error: str | None = None


class OrderExecutor:
    """
    Executes orders against Jupiter DEX.

    Handles the full lifecycle:
    - Quote fetching
    - Transaction creation
    - Signing and sending
    - Confirmation waiting
    - Retry on failure
    """

    def __init__(
        self,
        repository: OrderRepository,
        jupiter_client: JupiterClient,
        keypair: Keypair,
        confirmation_timeout: int = 60,
        max_concurrent: int = 1,
    ) -> None:
        """
        Initialize OrderExecutor.

        Args:
            repository: OrderRepository for persistence
            jupiter_client: Jupiter API client
            keypair: Wallet keypair for signing
            confirmation_timeout: Max seconds to wait for confirmation
            max_concurrent: Max concurrent order executions
        """
        self.repository = repository
        self.jupiter = jupiter_client
        self.keypair = keypair
        self.confirmation_timeout = confirmation_timeout
        self.max_concurrent = max_concurrent
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, order: Order) -> OrderResult:
        """
        Execute a single order.

        Handles the full flow from PENDING to FILLED/FAILED.
        """
        async with self._semaphore:
            if order.is_simulated:
                return await self._execute_simulated(order)
            else:
                return await self._execute_real(order)

    async def _execute_real(self, order: Order) -> OrderResult:
        """Execute order against Jupiter."""
        log = logger.bind(
            order_id=str(order.id)[:8],
            token=order.token_address[:8],
            type=order.order_type.value,
        )

        try:
            # Step 1: Mark as submitted
            order.mark_submitted()
            await self.repository.update(order)
            log.info("order_submitted")

            # Step 2: Get quote from Jupiter
            quote = await self._get_quote(order)
            log.info(
                "quote_received",
                output_amount=quote.output_amount,
                price_impact=quote.price_impact_pct,
            )

            # Step 3: Build swap transaction
            swap_tx = await self.jupiter.build_swap_transaction(
                quote=quote,
                user_public_key=str(self.keypair.pubkey()),
            )
            log.info("swap_tx_built")

            # Step 4: Execute swap
            result = await self.jupiter.execute_swap(swap_tx, self.keypair)

            if result.success:
                # Mark as confirming then filled
                order.mark_confirming(result.tx_signature)

                # Calculate actual price
                actual_price = self._calculate_price(order, quote, result)
                amount_tokens = Decimal(str(quote.output_amount)) / Decimal("1e9")

                order.mark_filled(actual_price, amount_tokens)
                await self.repository.update(order)

                log.info(
                    "order_filled",
                    tx_signature=result.tx_signature[:16] if result.tx_signature else None,
                    actual_price=str(actual_price),
                    slippage_bps=order.slippage_bps,
                )

                return OrderResult(
                    success=True,
                    order=order,
                    tx_signature=result.tx_signature,
                    actual_price=actual_price,
                    amount_tokens=amount_tokens,
                )
            else:
                raise Exception(result.error_message or "Swap failed")

        except Exception as e:
            error_msg = str(e)
            log.warning(
                "order_failed",
                error=error_msg,
                attempt=order.attempt_count + 1,
            )

            order.mark_failed(error_msg)
            await self.repository.update(order)

            return OrderResult(
                success=False,
                order=order,
                error=error_msg,
            )

    async def _execute_simulated(self, order: Order) -> OrderResult:
        """Execute in simulation mode (no real transaction)."""
        log = logger.bind(
            order_id=str(order.id)[:8],
            simulated=True,
        )

        try:
            # Simulate execution delay
            await asyncio.sleep(0.3)

            order.mark_submitted()
            await self.repository.update(order)

            # Simulate confirmation delay
            await asyncio.sleep(0.5)

            fake_signature = f"sim_{order.id}_{int(datetime.utcnow().timestamp())}"
            order.mark_confirming(fake_signature)

            # Calculate simulated amount tokens from expected price
            if order.amount_tokens is None:
                amount_tokens = order.amount_sol / order.expected_price
            else:
                amount_tokens = order.amount_tokens

            # Use expected price as actual (no slippage in simulation)
            order.mark_filled(order.expected_price, amount_tokens)
            await self.repository.update(order)

            log.info(
                "simulated_order_filled",
                price=str(order.expected_price),
            )

            return OrderResult(
                success=True,
                order=order,
                tx_signature=fake_signature,
                actual_price=order.expected_price,
                amount_tokens=amount_tokens,
            )

        except Exception as e:
            error_msg = str(e)
            log.warning("simulated_order_failed", error=error_msg)

            order.mark_failed(error_msg)
            await self.repository.update(order)

            return OrderResult(
                success=False,
                order=order,
                error=error_msg,
            )

    async def _get_quote(self, order: Order):
        """Get quote from Jupiter."""
        # Determine input/output based on order side
        if order.side.value == "buy":
            input_mint = SOL_MINT
            output_mint = order.token_address
            # Convert SOL to lamports
            amount = int(order.amount_sol * Decimal("1e9"))
        else:
            input_mint = order.token_address
            output_mint = SOL_MINT
            # Convert tokens (assuming 9 decimals for now)
            amount = int(order.amount_tokens * Decimal("1e9")) if order.amount_tokens else 0

        quote = await self.jupiter.get_quote(
            input_mint=input_mint,
            output_mint=output_mint,
            amount=amount,
            slippage_bps=order.max_slippage_bps,
        )

        return quote

    def _calculate_price(self, order: Order, quote, result) -> Decimal:
        """Calculate actual execution price from quote."""
        if order.side.value == "buy":
            # BUY: price = input_amount (SOL) / output_amount (tokens)
            if quote.output_amount > 0:
                return Decimal(str(quote.input_amount)) / Decimal(str(quote.output_amount))
        else:
            # SELL: price = output_amount (SOL) / input_amount (tokens)
            if quote.input_amount > 0:
                return Decimal(str(quote.output_amount)) / Decimal(str(quote.input_amount))

        # Fallback to expected price
        return order.expected_price

    async def execute_batch(self, orders: list[Order]) -> list[OrderResult]:
        """Execute multiple orders (respects max_concurrent)."""
        tasks = [self.execute(order) for order in orders]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                final_results.append(
                    OrderResult(
                        success=False,
                        order=orders[i],
                        error=str(result),
                    )
                )
            else:
                final_results.append(result)

        return final_results


# Singleton instance
_executor: OrderExecutor | None = None


async def get_order_executor() -> OrderExecutor:
    """Get or create order executor singleton."""
    global _executor

    if _executor is None:
        from walltrack.config.wallet_settings import get_wallet_settings
        from walltrack.data.supabase.repositories.order_repo import (
            get_order_repository,
        )
        from walltrack.services.jupiter.client import get_jupiter_client
        from solders.keypair import Keypair

        wallet_settings = get_wallet_settings()
        keypair = Keypair.from_base58_string(wallet_settings.private_key)

        _executor = OrderExecutor(
            repository=await get_order_repository(),
            jupiter_client=await get_jupiter_client(),
            keypair=keypair,
        )

    return _executor
