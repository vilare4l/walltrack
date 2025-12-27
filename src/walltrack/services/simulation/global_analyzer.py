"""Global analysis across multiple positions."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)
from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    get_simulation_engine,
)

if TYPE_CHECKING:
    from collections.abc import Callable

logger = structlog.get_logger(__name__)


@dataclass
class StrategyStats:
    """Aggregate stats for a strategy across positions."""

    strategy_id: str
    strategy_name: str
    positions_analyzed: int
    winning_positions: int
    losing_positions: int
    win_rate_pct: Decimal
    total_pnl_pct: Decimal
    total_pnl_sol: Decimal
    avg_pnl_pct: Decimal
    median_pnl_pct: Decimal
    max_gain_pct: Decimal
    max_loss_pct: Decimal
    avg_hold_hours: Decimal
    best_for: str  # "standard", "high", or "both"
    avg_improvement_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    best_position_id: str = ""
    best_improvement_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    worst_position_id: str = ""
    worst_improvement_pct: Decimal = field(default_factory=lambda: Decimal("0"))


@dataclass
class GlobalAnalysisResult:
    """Result of global analysis."""

    period_days: int
    total_positions: int
    strategies_compared: int

    strategy_stats: list[StrategyStats]
    recommended_strategy_id: str
    recommended_strategy_name: str
    best_for_standard_id: str
    best_for_high_conviction_id: str

    analysis_duration_seconds: float


class GlobalAnalyzer:
    """
    Analyzes multiple strategies across historical positions.

    Supports:
    - Batch simulation
    - Progress tracking
    - Result caching
    - Cancellation
    """

    def __init__(self) -> None:
        self._engine: ExitSimulationEngine | None = None
        self._client = None
        self._strategy_service = None
        self._cache: dict[str, GlobalAnalysisResult] = {}
        self._cache_ttl_seconds = 3600  # 1 hour
        self._cache_timestamps: dict[str, datetime] = {}
        self._cancelled = False

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

    async def _get_strategy_service(self):
        """Get strategy service."""
        if self._strategy_service is None:
            self._strategy_service = await get_exit_strategy_service()
        return self._strategy_service

    async def get_positions_for_analysis(
        self,
        days_back: int,
        limit: int = 500,
    ) -> list[dict]:
        """
        Get closed positions suitable for analysis.

        Returns positions with their price history.
        """
        client = await self._get_client()
        cutoff = datetime.now(UTC) - timedelta(days=days_back)

        pos_result = await (
            client.table("positions")
            .select(
                "id, token_address, entry_price, exit_price, "
                "entry_time, exit_time, size_sol, pnl_pct"
            )
            .eq("status", "closed")
            .gte("exit_time", cutoff.isoformat())
            .order("exit_time", desc=True)
            .limit(limit)
            .execute()
        )

        positions = pos_result.data or []

        logger.info(
            "found_positions_for_analysis",
            count=len(positions),
            days_back=days_back,
        )

        return positions

    def _check_cache(self, cache_key: str) -> GlobalAnalysisResult | None:
        """Check if a valid cached result exists."""
        if cache_key not in self._cache:
            return None

        cache_time = self._cache_timestamps.get(cache_key)
        if not cache_time:
            return None

        if (datetime.now(UTC) - cache_time).total_seconds() >= self._cache_ttl_seconds:
            return None

        return self._cache[cache_key]

    async def _fetch_positions(
        self,
        position_ids: list[str] | None,
        days_back: int,
        limit: int,
    ) -> list[dict]:
        """Fetch positions for analysis."""
        if position_ids:
            client = await self._get_client()
            result = await (
                client.table("positions")
                .select("*")
                .in_("id", position_ids)
                .limit(limit)
                .execute()
            )
            return result.data or []
        return await self.get_positions_for_analysis(days_back, limit)

    async def _fetch_strategies(
        self,
        strategy_ids: list[str] | None,
    ) -> list[ExitStrategy]:
        """Fetch strategies for analysis."""
        strategy_service = await self._get_strategy_service()

        if strategy_ids:
            strategies = []
            for sid in strategy_ids:
                s = await strategy_service.get(sid)
                if s:
                    strategies.append(s)
            return strategies

        all_strategies = await strategy_service.list_all()
        return [s for s in all_strategies if s.status == "active"]

    async def _run_simulations(
        self,
        positions: list[dict],
        strategies: list[ExitStrategy],
        on_progress: Callable[[int, int], None] | None,
    ) -> dict[str, list[dict]]:
        """Run simulations for all position-strategy combinations."""
        engine = await self._get_engine()
        total_sims = len(positions) * len(strategies)
        current_sim = 0
        strategy_results: dict[str, list[dict]] = {s.id: [] for s in strategies}

        for pos in positions:
            if self._cancelled:
                return strategy_results

            entry_price = Decimal(str(pos["entry_price"]))
            entry_time = datetime.fromisoformat(
                pos["entry_time"].replace("Z", "+00:00")
            )
            position_size = Decimal(str(pos["size_sol"]))
            actual_pnl = (
                Decimal(str(pos["pnl_pct"])) if pos.get("pnl_pct") else Decimal("0")
            )

            for strategy in strategies:
                if self._cancelled:
                    return strategy_results

                current_sim += 1
                await self._simulate_one(
                    engine, strategy, pos, entry_price, entry_time,
                    position_size, actual_pnl, strategy_results,
                )

                if on_progress:
                    on_progress(current_sim, total_sims)

            if current_sim % 10 == 0:
                await asyncio.sleep(0)

        return strategy_results

    async def _simulate_one(
        self,
        engine: ExitSimulationEngine,
        strategy: ExitStrategy,
        pos: dict,
        entry_price: Decimal,
        entry_time: datetime,
        position_size: Decimal,
        actual_pnl: Decimal,
        strategy_results: dict[str, list[dict]],
    ) -> None:
        """Simulate one position with one strategy."""
        try:
            result = await engine.simulate_position(
                strategy=strategy,
                position_id=pos["id"],
                entry_price=entry_price,
                entry_time=entry_time,
                position_size_sol=position_size,
                token_address=pos.get("token_address"),
            )

            improvement = result.final_pnl_pct - actual_pnl

            strategy_results[strategy.id].append({
                "position_id": pos["id"],
                "pnl_pct": result.final_pnl_pct,
                "pnl_sol": result.final_pnl_sol,
                "hold_hours": result.hold_duration_hours,
                "actual_pnl": actual_pnl,
                "improvement": improvement,
            })
        except Exception as e:
            logger.warning(
                "simulation_error_in_analysis",
                position_id=pos["id"],
                strategy_id=strategy.id,
                error=str(e),
            )

    def _calculate_strategy_stats(
        self,
        strategy: ExitStrategy,
        results: list[dict],
    ) -> StrategyStats:
        """Calculate stats for a single strategy."""
        pnls = [r["pnl_pct"] for r in results]
        pnl_sols = [r["pnl_sol"] for r in results]
        hold_hours = [r["hold_hours"] for r in results]
        improvements = [r["improvement"] for r in results]

        winning = sum(1 for p in pnls if p > 0)
        total_pnl = sum(pnls)
        avg_pnl = total_pnl / len(pnls) if pnls else Decimal("0")

        sorted_pnls = sorted(pnls)
        mid = len(sorted_pnls) // 2
        median_pnl = self._calculate_median(sorted_pnls, mid)

        best_result = max(results, key=lambda r: r["improvement"])
        worst_result = min(results, key=lambda r: r["improvement"])

        return StrategyStats(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            positions_analyzed=len(results),
            winning_positions=winning,
            losing_positions=len(results) - winning,
            win_rate_pct=(
                Decimal(str(winning / len(results) * 100)) if results else Decimal("0")
            ),
            total_pnl_pct=total_pnl,
            total_pnl_sol=sum(pnl_sols),
            avg_pnl_pct=avg_pnl,
            median_pnl_pct=median_pnl,
            max_gain_pct=max(pnls) if pnls else Decimal("0"),
            max_loss_pct=min(pnls) if pnls else Decimal("0"),
            avg_hold_hours=(
                sum(hold_hours) / len(hold_hours) if hold_hours else Decimal("0")
            ),
            best_for=self._determine_best_for(strategy),
            avg_improvement_pct=(
                sum(improvements) / len(improvements) if improvements else Decimal("0")
            ),
            best_position_id=best_result["position_id"],
            best_improvement_pct=best_result["improvement"],
            worst_position_id=worst_result["position_id"],
            worst_improvement_pct=worst_result["improvement"],
        )

    def _calculate_median(self, sorted_pnls: list[Decimal], mid: int) -> Decimal:
        """Calculate median from sorted list."""
        if not sorted_pnls:
            return Decimal("0")
        if len(sorted_pnls) % 2:
            return sorted_pnls[mid]
        return (sorted_pnls[mid - 1] + sorted_pnls[mid]) / 2

    async def analyze(
        self,
        position_ids: list[str] | None = None,
        strategy_ids: list[str] | None = None,
        days_back: int = 30,
        limit: int = 100,
        on_progress: Callable[[int, int], None] | None = None,
        use_cache: bool = True,
    ) -> GlobalAnalysisResult | None:
        """
        Run global analysis.

        Args:
            position_ids: Specific positions (None=all closed)
            strategy_ids: Strategies to analyze (None=all active)
            days_back: Days of history to analyze
            limit: Max positions to analyze
            on_progress: Progress callback (current, total)
            use_cache: Whether to use cached results

        Returns:
            GlobalAnalysisResult or None if cancelled/no data
        """
        self._cancelled = False
        start_time = datetime.now(UTC)

        # Build cache key
        pos_key = ",".join(sorted(position_ids)) if position_ids else "all"
        strat_key = ",".join(sorted(strategy_ids)) if strategy_ids else "active"
        cache_key = f"{days_back}:{pos_key}:{strat_key}"

        # Check cache
        if use_cache:
            cached = self._check_cache(cache_key)
            if cached:
                logger.info("using_cached_analysis", days=days_back)
                return cached

        # Get data
        positions = await self._fetch_positions(position_ids, days_back, limit)
        if not positions:
            logger.warning("no_positions_for_analysis", days=days_back)
            return None

        strategies = await self._fetch_strategies(strategy_ids)
        if not strategies:
            logger.warning("no_strategies_for_analysis")
            return None

        # Run simulations
        strategy_results = await self._run_simulations(
            positions, strategies, on_progress
        )

        if self._cancelled:
            logger.info("analysis_cancelled")
            return None

        # Build stats
        result = self._build_result(
            strategies, strategy_results, positions, days_back, start_time
        )

        if result:
            self._cache[cache_key] = result
            self._cache_timestamps[cache_key] = datetime.now(UTC)

        return result

    def _build_result(
        self,
        strategies: list[ExitStrategy],
        strategy_results: dict[str, list[dict]],
        positions: list[dict],
        days_back: int,
        start_time: datetime,
    ) -> GlobalAnalysisResult | None:
        """Build the final analysis result."""
        stats = []
        best_overall_pnl = Decimal("-999999")
        best_overall: ExitStrategy | None = None

        for strategy in strategies:
            results = strategy_results[strategy.id]
            if not results:
                continue

            stat = self._calculate_strategy_stats(strategy, results)
            stats.append(stat)

            if stat.total_pnl_pct > best_overall_pnl:
                best_overall_pnl = stat.total_pnl_pct
                best_overall = strategy

        if not stats:
            return None

        # Determine best for each tier
        standard_stats = [s for s in stats if s.best_for in ["standard", "both"]]
        high_stats = [s for s in stats if s.best_for in ["high", "both"]]

        best_standard = (
            max(standard_stats, key=lambda x: x.avg_pnl_pct)
            if standard_stats
            else stats[0]
        )
        best_high = (
            max(high_stats, key=lambda x: x.avg_pnl_pct) if high_stats else stats[0]
        )

        duration = (datetime.now(UTC) - start_time).total_seconds()

        result = GlobalAnalysisResult(
            period_days=days_back,
            total_positions=len(positions),
            strategies_compared=len(strategies),
            strategy_stats=stats,
            recommended_strategy_id=best_overall.id if best_overall else "",
            recommended_strategy_name=best_overall.name if best_overall else "",
            best_for_standard_id=best_standard.strategy_id,
            best_for_high_conviction_id=best_high.strategy_id,
            analysis_duration_seconds=duration,
        )

        logger.info(
            "global_analysis_complete",
            positions=len(positions),
            strategies=len(strategies),
            duration=f"{duration:.2f}s",
            recommended=result.recommended_strategy_name,
        )

        return result

    def _determine_best_for(self, strategy: ExitStrategy) -> str:
        """Determine which conviction tier this strategy is best for."""
        has_wide_stops = any(
            r.rule_type == "stop_loss"
            and r.trigger_pct is not None
            and r.trigger_pct <= Decimal("-12")
            for r in strategy.rules
        )
        has_high_tps = any(
            r.rule_type == "take_profit"
            and r.trigger_pct is not None
            and r.trigger_pct >= Decimal("40")
            for r in strategy.rules
        )

        if has_wide_stops and has_high_tps:
            return "high"
        if not has_wide_stops and not has_high_tps:
            return "standard"
        return "both"

    def cancel(self) -> None:
        """Cancel running analysis."""
        self._cancelled = True

    def clear_cache(self) -> None:
        """Clear results cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


# Singleton
_analyzer: GlobalAnalyzer | None = None


async def get_global_analyzer() -> GlobalAnalyzer:
    """Get global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = GlobalAnalyzer()
    return _analyzer


def reset_global_analyzer() -> None:
    """Reset the singleton (for testing)."""
    global _analyzer
    _analyzer = None
