"""Multi-strategy comparison for positions."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)
from walltrack.services.exit.simulation_engine import SimulationResult
from walltrack.services.simulation.position_simulator import (
    PositionSimulator,
    get_position_simulator,
)

logger = structlog.get_logger(__name__)


@dataclass
class StrategyComparisonRow:
    """Single row in comparison results."""

    strategy_id: str
    strategy_name: str
    simulated_pnl_pct: Decimal
    simulated_pnl_sol: Decimal
    actual_pnl_pct: Decimal | None
    delta_pct: Decimal | None
    delta_sol: Decimal | None
    exit_time: datetime | None
    exit_types: list[str] = field(default_factory=list)
    is_best: bool = False


@dataclass
class ComparisonResult:
    """Full comparison result."""

    position_id: str
    entry_price: Decimal
    actual_exit_price: Decimal | None
    actual_pnl_pct: Decimal | None

    rows: list[StrategyComparisonRow]
    best_strategy_id: str
    best_strategy_name: str
    best_improvement_pct: Decimal | None


class StrategyComparator:
    """
    Compares multiple exit strategies on a position.

    Runs simulation for each strategy and produces
    comparison table with delta vs actual.
    """

    def __init__(self) -> None:
        self._simulator: PositionSimulator | None = None
        self._client = None
        self._strategy_service = None

    async def _get_simulator(self) -> PositionSimulator:
        """Get position simulator."""
        if self._simulator is None:
            self._simulator = await get_position_simulator()
        return self._simulator

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import (  # noqa: PLC0415
                get_supabase_client,
            )

            self._client = await get_supabase_client()
        return self._client

    async def _get_strategy_service(self):
        """Get strategy service."""
        if self._strategy_service is None:
            self._strategy_service = await get_exit_strategy_service()
        return self._strategy_service

    async def _get_position(self, position_id: str) -> dict | None:
        """Get position data."""
        client = await self._get_client()

        result = await (
            client.table("positions")
            .select("*")
            .eq("id", position_id)
            .single()
            .execute()
        )

        return result.data if result.data else None

    def _build_row(
        self,
        result: SimulationResult,
        actual_pnl_pct: Decimal | None,
        position_size: Decimal,
    ) -> StrategyComparisonRow:
        """Build comparison row from simulation result."""
        # Calculate delta vs actual
        delta_pct = None
        delta_sol = None
        if actual_pnl_pct is not None:
            delta_pct = result.final_pnl_pct - actual_pnl_pct
            delta_sol = result.final_pnl_sol - (position_size * actual_pnl_pct / 100)

        # Get exit types from triggers
        exit_types = list({t.rule_type for t in result.triggers})

        return StrategyComparisonRow(
            strategy_id=result.strategy_id,
            strategy_name=result.strategy_name,
            simulated_pnl_pct=result.final_pnl_pct,
            simulated_pnl_sol=result.final_pnl_sol,
            actual_pnl_pct=actual_pnl_pct,
            delta_pct=delta_pct,
            delta_sol=delta_sol,
            exit_time=result.final_exit_time,
            exit_types=exit_types,
        )

    async def compare(
        self,
        position_id: str,
        strategy_ids: list[str],
    ) -> ComparisonResult | None:
        """
        Compare multiple strategies on a position.

        Args:
            position_id: Position to simulate on
            strategy_ids: List of strategy IDs to compare

        Returns:
            ComparisonResult or None if position not found
        """
        # Get position data
        position = await self._get_position(position_id)
        if not position:
            logger.warning("position_not_found", position_id=position_id)
            return None

        # Position info
        entry_price = Decimal(str(position["entry_price"]))
        position_size = Decimal(str(position["size_sol"]))

        actual_exit_price = (
            Decimal(str(position["exit_price"]))
            if position.get("exit_price")
            else None
        )
        actual_pnl_pct = (
            Decimal(str(position["pnl_pct"])) if position.get("pnl_pct") else None
        )

        # Get strategies
        strategy_service = await self._get_strategy_service()
        strategies: list[ExitStrategy] = []

        for sid in strategy_ids:
            strategy = await strategy_service.get(sid)
            if strategy:
                strategies.append(strategy)

        if not strategies:
            logger.warning("no_strategies_found", ids=strategy_ids)
            return None

        # Run simulations using PositionSimulator
        simulator = await self._get_simulator()
        sim_results = await simulator.compare_strategies(position_id, strategies)

        if not sim_results:
            logger.warning("no_simulation_results", position_id=position_id)
            return None

        # Build rows and find best
        rows: list[StrategyComparisonRow] = []
        best_pnl = Decimal("-999999")
        best_strategy_id = ""
        best_strategy_name = ""

        for strategy_id, result in sim_results.items():
            row = self._build_row(result, actual_pnl_pct, position_size)
            rows.append(row)

            # Track best by PnL
            if result.final_pnl_pct > best_pnl:
                best_pnl = result.final_pnl_pct
                best_strategy_id = strategy_id
                best_strategy_name = result.strategy_name

        # Mark best row
        for row in rows:
            if row.strategy_id == best_strategy_id:
                row.is_best = True

        # Calculate improvement
        best_improvement = None
        if actual_pnl_pct is not None and best_strategy_id:
            best_improvement = best_pnl - actual_pnl_pct

        logger.info(
            "comparison_complete",
            position_id=position_id,
            strategies_compared=len(rows),
            best_strategy=best_strategy_name,
            best_improvement_pct=float(best_improvement) if best_improvement else None,
        )

        return ComparisonResult(
            position_id=position_id,
            entry_price=entry_price,
            actual_exit_price=actual_exit_price,
            actual_pnl_pct=actual_pnl_pct,
            rows=rows,
            best_strategy_id=best_strategy_id,
            best_strategy_name=best_strategy_name,
            best_improvement_pct=best_improvement,
        )

    async def compare_all_active_strategies(
        self,
        position_id: str,
    ) -> ComparisonResult | None:
        """Compare all active strategies on a position."""
        strategy_service = await self._get_strategy_service()
        strategies = await strategy_service.list_all()

        active_ids = [s.id for s in strategies if s.status == "active"]

        if not active_ids:
            logger.warning("no_active_strategies_found")
            return None

        return await self.compare(position_id, active_ids)


def format_comparison_table(result: ComparisonResult) -> str:
    """Format comparison as markdown table."""
    actual_str = (
        f"{result.actual_pnl_pct:+.2f}%"
        if result.actual_pnl_pct is not None
        else "N/A"
    )
    exit_str = (
        f"${result.actual_exit_price:.8f}"
        if result.actual_exit_price is not None
        else "N/A"
    )

    md = f"""## Strategy Comparison

**Position:** {result.position_id[:8]}...
**Entry:** ${result.entry_price:.8f}
**Actual P&L:** {actual_str} ({exit_str})

| Strategy | Simulated P&L | Delta vs Actual | Exit Types | |
|----------|---------------|-----------------|------------|---|
"""
    for row in result.rows:
        star = " * " if row.is_best else ""

        if row.delta_pct is not None:
            delta_str = f"{row.delta_pct:+.2f}%"
            # Color hint (green/red indicators)
            if row.delta_pct > 0:
                delta_str = f"[+] {delta_str}"
            elif row.delta_pct < 0:
                delta_str = f"[-] {delta_str}"
        else:
            delta_str = "-"

        exits = ", ".join(row.exit_types) if row.exit_types else "none"

        md += (
            f"| {row.strategy_name} | {row.simulated_pnl_pct:+.2f}% | "
            f"{delta_str} | {exits} | {star} |\n"
        )

    if result.best_improvement_pct:
        md += (
            f"\n**Best strategy would have improved P&L "
            f"by {result.best_improvement_pct:+.2f}%**"
        )

    return md


# Singleton
_comparator: StrategyComparator | None = None


async def get_strategy_comparator() -> StrategyComparator:
    """Get strategy comparator instance."""
    global _comparator
    if _comparator is None:
        _comparator = StrategyComparator()
    return _comparator


def reset_strategy_comparator() -> None:
    """Reset the singleton (for testing)."""
    global _comparator
    _comparator = None
