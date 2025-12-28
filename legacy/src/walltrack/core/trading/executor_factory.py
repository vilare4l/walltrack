"""Factory for creating trade executors based on mode."""

from typing import Protocol

import structlog

from walltrack.core.simulation.context import is_simulation_mode

log = structlog.get_logger()


class TradeExecutor(Protocol):
    """Protocol for trade executors."""

    async def execute_buy(
        self,
        token_address: str,
        amount_sol: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a buy trade."""
        ...

    async def execute_sell(
        self,
        token_address: str,
        amount_tokens: float,
        slippage_bps: int,
    ) -> dict:
        """Execute a sell trade."""
        ...


def get_trade_executor() -> TradeExecutor:
    """Get appropriate trade executor based on execution mode."""
    if is_simulation_mode():
        from walltrack.core.simulation.simulated_executor import SimulatedTradeExecutor

        log.info("using_simulated_executor")
        return SimulatedTradeExecutor()
    else:
        from walltrack.core.trading.jupiter_executor import JupiterExecutor

        log.info("using_live_executor")
        return JupiterExecutor()
