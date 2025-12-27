# Story 12.6: Exit Simulator - Comparison Logic

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 3
- **Depends on**: Story 12-5 (Position Simulator)

## User Story

**As a** the operator,
**I want** comparer plusieurs stratégies sur une même position,
**So that** je peux identifier la meilleure.

## Acceptance Criteria

### AC 1: Compare Multiple Strategies
**Given** une position clôturée avec historique
**When** je lance une comparaison multi-stratégies
**Then** je reçois un tableau:
| Strategy | Simulated P&L | Actual P&L | Delta | Exit Point |

### AC 2: Highlight Best Strategy
**Given** les résultats
**When** je les affiche
**Then** la meilleure stratégie est mise en évidence (★)
**And** les deltas positifs sont en vert, négatifs en rouge

### AC 3: Show Exit Points
**Given** plusieurs stratégies
**When** je compare
**Then** je vois aussi les exit points sur un graphique commun

### AC 4: Compare vs Actual
**Given** une position avec sortie réelle
**When** je compare des stratégies
**Then** chaque résultat montre le delta vs le résultat réel

## Technical Specifications

### Strategy Comparator

**src/walltrack/services/simulation/strategy_comparator.py:**
```python
"""Multi-strategy comparison for positions."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)
from walltrack.services.simulation.position_simulator import (
    PositionSimulator,
    PositionSimulationResult,
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
    actual_pnl_pct: Optional[Decimal]
    delta_pct: Optional[Decimal]
    delta_sol: Optional[Decimal]
    exit_time: Optional[datetime]
    exit_types: list[str]  # e.g., ["take_profit", "trailing_stop"]
    is_best: bool = False


@dataclass
class ComparisonResult:
    """Full comparison result."""
    position_id: str
    entry_price: Decimal
    actual_exit_price: Optional[Decimal]
    actual_pnl_pct: Optional[Decimal]

    rows: list[StrategyComparisonRow]
    best_strategy_id: str
    best_strategy_name: str
    best_improvement_pct: Optional[Decimal]


class StrategyComparator:
    """
    Compares multiple exit strategies on a position.

    Runs simulation for each strategy and produces
    comparison table with delta vs actual.
    """

    def __init__(self):
        self.simulator = get_position_simulator()
        self._client = None
        self._strategy_service = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def _get_strategy_service(self):
        """Get strategy service."""
        if self._strategy_service is None:
            self._strategy_service = await get_exit_strategy_service()
        return self._strategy_service

    async def get_position_with_history(self, position_id: str) -> Optional[dict]:
        """Get position with price history."""
        client = await self._get_client()

        # Get position
        pos_result = await client.table("positions") \
            .select("*") \
            .eq("id", position_id) \
            .single() \
            .execute()

        if not pos_result.data:
            return None

        position = pos_result.data

        # Get price history
        history_result = await client.table("position_price_history") \
            .select("timestamp, price") \
            .eq("position_id", position_id) \
            .order("timestamp") \
            .execute()

        position["price_history"] = history_result.data or []

        return position

    async def compare(
        self,
        position_id: str,
        strategy_ids: list[str],
    ) -> Optional[ComparisonResult]:
        """
        Compare multiple strategies on a position.

        Args:
            position_id: Position to simulate on
            strategy_ids: List of strategy IDs to compare

        Returns:
            ComparisonResult or None if position not found
        """
        # Get position with history
        position = await self.get_position_with_history(position_id)
        if not position:
            logger.warning("position_not_found", position_id=position_id)
            return None

        if not position.get("price_history"):
            logger.warning("no_price_history", position_id=position_id)
            return None

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

        # Position info
        entry_price = Decimal(str(position["entry_price"]))
        entry_time = datetime.fromisoformat(position["entry_time"].replace("Z", "+00:00"))
        position_size = Decimal(str(position["size_sol"]))

        actual_exit_price = Decimal(str(position["exit_price"])) if position.get("exit_price") else None
        actual_pnl_pct = Decimal(str(position["pnl_pct"])) if position.get("pnl_pct") else None

        # Run simulations
        rows: list[StrategyComparisonRow] = []
        best_pnl = Decimal("-999999")
        best_strategy: Optional[ExitStrategy] = None

        for strategy in strategies:
            result = self.simulator.simulate(
                strategy=strategy,
                entry_price=entry_price,
                entry_time=entry_time,
                position_size_sol=position_size,
                price_history=position["price_history"],
                position_id=position_id,
            )

            # Calculate delta vs actual
            delta_pct = None
            delta_sol = None
            if actual_pnl_pct is not None:
                delta_pct = result.final_pnl_pct - actual_pnl_pct
                delta_sol = result.final_pnl_sol - (position_size * actual_pnl_pct / 100)

            # Get exit types from events
            exit_types = list(set(e.event_type for e in result.exit_events))

            row = StrategyComparisonRow(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                simulated_pnl_pct=result.final_pnl_pct,
                simulated_pnl_sol=result.final_pnl_sol,
                actual_pnl_pct=actual_pnl_pct,
                delta_pct=delta_pct,
                delta_sol=delta_sol,
                exit_time=result.last_exit_time,
                exit_types=exit_types,
            )
            rows.append(row)

            # Track best
            if result.final_pnl_pct > best_pnl:
                best_pnl = result.final_pnl_pct
                best_strategy = strategy

        # Mark best
        for row in rows:
            if best_strategy and row.strategy_id == best_strategy.id:
                row.is_best = True

        # Calculate improvement
        best_improvement = None
        if actual_pnl_pct is not None and best_strategy:
            best_improvement = best_pnl - actual_pnl_pct

        return ComparisonResult(
            position_id=position_id,
            entry_price=entry_price,
            actual_exit_price=actual_exit_price,
            actual_pnl_pct=actual_pnl_pct,
            rows=rows,
            best_strategy_id=best_strategy.id if best_strategy else "",
            best_strategy_name=best_strategy.name if best_strategy else "",
            best_improvement_pct=best_improvement,
        )

    async def compare_all_active_strategies(
        self,
        position_id: str,
    ) -> Optional[ComparisonResult]:
        """Compare all active strategies on a position."""
        strategy_service = await self._get_strategy_service()
        strategies = await strategy_service.list_all()

        active_ids = [s.id for s in strategies if s.status == "active"]

        return await self.compare(position_id, active_ids)


def format_comparison_table(result: ComparisonResult) -> str:
    """Format comparison as markdown table."""
    md = f"""
## Strategy Comparison

**Position:** {result.position_id[:8]}...
**Entry:** ${result.entry_price:.8f}
**Actual P&L:** {result.actual_pnl_pct:+.2f}% (${result.actual_exit_price:.8f})

| Strategy | Simulated P&L | Delta vs Actual | Exit Types | |
|----------|---------------|-----------------|------------|---|
"""
    for row in result.rows:
        star = "★" if row.is_best else ""
        delta_str = f"{row.delta_pct:+.2f}%" if row.delta_pct is not None else "-"

        # Color hint
        if row.delta_pct and row.delta_pct > 0:
            delta_str = f"🟢 {delta_str}"
        elif row.delta_pct and row.delta_pct < 0:
            delta_str = f"🔴 {delta_str}"

        exits = ", ".join(row.exit_types) if row.exit_types else "none"

        md += f"| {row.strategy_name} | {row.simulated_pnl_pct:+.2f}% | {delta_str} | {exits} | {star} |\n"

    if result.best_improvement_pct:
        md += f"\n**Best strategy would have improved P&L by {result.best_improvement_pct:+.2f}%**"

    return md


# Singleton
_comparator: Optional[StrategyComparator] = None


async def get_strategy_comparator() -> StrategyComparator:
    """Get strategy comparator instance."""
    global _comparator
    if _comparator is None:
        _comparator = StrategyComparator()
    return _comparator
```

## Implementation Tasks

- [x] Create StrategyComparisonRow dataclass
- [x] Create ComparisonResult dataclass
- [x] Implement StrategyComparator class
- [x] Implement compare() method
- [x] Implement compare_all_active_strategies()
- [x] Calculate delta vs actual
- [x] Identify best strategy
- [x] Format as markdown table
- [x] Write tests

## Definition of Done

- [x] Comparison runs for multiple strategies
- [x] Delta calculated correctly
- [x] Best strategy identified
- [x] Table formatted with colors
- [x] Tests pass

## File List

### New Files
- `src/walltrack/services/simulation/strategy_comparator.py` - Comparator

### Modified Files
- `src/walltrack/services/simulation/__init__.py` - Export
