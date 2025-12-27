"""Position-level wrapper around ExitSimulationEngine."""

from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.services.exit.exit_strategy_service import ExitStrategy
from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    SimulationResult,
    get_simulation_engine,
)

logger = structlog.get_logger(__name__)


class PositionSimulator:
    """
    Position-level wrapper around ExitSimulationEngine.

    This is a convenience wrapper that:
    1. Loads position data from database
    2. Fetches price history
    3. Delegates to ExitSimulationEngine for actual simulation
    """

    def __init__(self) -> None:
        self._engine: ExitSimulationEngine | None = None
        self._client = None

    async def _get_engine(self) -> ExitSimulationEngine:
        """Get simulation engine."""
        if self._engine is None:
            self._engine = await get_simulation_engine()
        return self._engine

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import (  # noqa: PLC0415
                get_supabase_client,
            )

            self._client = await get_supabase_client()
        return self._client

    def _parse_datetime(self, value: str) -> datetime:
        """Parse datetime string from database."""
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)

    async def simulate_by_id(
        self,
        position_id: str,
        strategy: ExitStrategy,
    ) -> SimulationResult:
        """
        Simulate a strategy on a position by ID.

        Loads position from database and runs simulation.

        Args:
            position_id: The position ID to simulate
            strategy: The exit strategy to use

        Returns:
            SimulationResult with simulated outcomes
        """
        client = await self._get_client()

        # Load position
        result = await (
            client.table("positions")
            .select("*")
            .eq("id", position_id)
            .single()
            .execute()
        )

        if not result.data:
            raise ValueError(f"Position not found: {position_id}")

        pos = result.data

        # Parse optional actual exit
        actual_exit = None
        if pos.get("exit_price") and pos.get("exit_time"):
            actual_exit = (
                Decimal(str(pos["exit_price"])),
                self._parse_datetime(pos["exit_time"]),
            )

        # Delegate to engine
        engine = await self._get_engine()
        return await engine.simulate_position(
            strategy=strategy,
            position_id=position_id,
            entry_price=Decimal(str(pos["entry_price"])),
            entry_time=self._parse_datetime(pos["entry_time"]),
            position_size_sol=Decimal(str(pos["size_sol"])),
            token_address=pos.get("token_address"),
            actual_exit=actual_exit,
        )

    async def batch_simulate_positions(
        self,
        position_ids: list[str],
        strategy: ExitStrategy,
    ) -> list[SimulationResult]:
        """
        Simulate strategy on multiple positions.

        Args:
            position_ids: List of position IDs to simulate
            strategy: The exit strategy to use

        Returns:
            List of SimulationResult for each successful position
        """
        results = []
        for pos_id in position_ids:
            try:
                result = await self.simulate_by_id(pos_id, strategy)
                results.append(result)
            except Exception as e:
                logger.warning(
                    "position_simulation_error",
                    position=pos_id,
                    error=str(e),
                )
        return results

    async def compare_strategies(
        self,
        position_id: str,
        strategies: list[ExitStrategy],
    ) -> dict[str, SimulationResult]:
        """
        Compare multiple strategies on a single position.

        Args:
            position_id: The position ID to simulate
            strategies: List of strategies to compare

        Returns:
            Dict mapping strategy ID to SimulationResult
        """
        results = {}
        for strategy in strategies:
            try:
                result = await self.simulate_by_id(position_id, strategy)
                results[strategy.id] = result
            except Exception as e:
                logger.warning(
                    "strategy_comparison_error",
                    position=position_id,
                    strategy=strategy.id,
                    error=str(e),
                )
        return results


# Singleton
_position_simulator: PositionSimulator | None = None


async def get_position_simulator() -> PositionSimulator:
    """Get position simulator instance."""
    global _position_simulator
    if _position_simulator is None:
        _position_simulator = PositionSimulator()
    return _position_simulator


def reset_position_simulator() -> None:
    """Reset the singleton (for testing)."""
    global _position_simulator
    _position_simulator = None
