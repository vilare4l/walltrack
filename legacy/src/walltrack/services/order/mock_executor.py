"""Mock order executor for testing and simulation."""

from __future__ import annotations

import asyncio
import random
from decimal import Decimal

from walltrack.models.order import Order
from walltrack.services.order.executor import OrderResult


class MockOrderExecutor:
    """
    Mock executor for testing.

    Simulates order execution with configurable behavior.
    """

    def __init__(
        self,
        success_rate: float = 1.0,
        avg_slippage_bps: int = 50,
        execution_delay: float = 0.1,
    ) -> None:
        """
        Initialize MockOrderExecutor.

        Args:
            success_rate: Probability of successful execution (0.0 to 1.0)
            avg_slippage_bps: Average slippage in basis points
            execution_delay: Simulated execution delay in seconds
        """
        self.success_rate = success_rate
        self.avg_slippage_bps = avg_slippage_bps
        self.execution_delay = execution_delay
        self.executed_orders: list[Order] = []

    async def execute(self, order: Order) -> OrderResult:
        """Simulate order execution."""
        await asyncio.sleep(self.execution_delay)

        self.executed_orders.append(order)

        # Simulate random failures based on success rate
        if random.random() > self.success_rate:
            order.mark_submitted()
            order.mark_failed("Simulated failure")
            return OrderResult(
                success=False,
                order=order,
                error="Simulated failure",
            )

        # Simulate slippage
        slippage_factor = 1 + (self.avg_slippage_bps / 10000 * random.uniform(0.5, 1.5))

        if order.side.value == "buy":
            actual_price = order.expected_price * Decimal(str(slippage_factor))
        else:
            actual_price = order.expected_price / Decimal(str(slippage_factor))

        # Calculate amount tokens
        if order.amount_tokens is None:
            amount_tokens = order.amount_sol / actual_price
        else:
            amount_tokens = order.amount_tokens

        order.mark_submitted()
        order.mark_confirming(f"mock_tx_{order.id}")
        order.mark_filled(actual_price, amount_tokens)

        return OrderResult(
            success=True,
            order=order,
            tx_signature=f"mock_tx_{order.id}",
            actual_price=actual_price,
            amount_tokens=amount_tokens,
        )

    async def execute_batch(self, orders: list[Order]) -> list[OrderResult]:
        """Execute multiple orders."""
        results = []
        for order in orders:
            result = await self.execute(order)
            results.append(result)
        return results

    def reset(self) -> None:
        """Reset execution history."""
        self.executed_orders = []
