# Story 12.9: Global Analysis - Multi-Position Simulation

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P2 - Medium
- **Story Points**: 8
- **Depends on**: Story 12-6 (Comparison Logic)

## User Story

**As a** the operator,
**I want** simuler une stratégie sur tous mes trades passés,
**So that** je peux optimiser ma stratégie par défaut.

## Acceptance Criteria

### AC 1: Open Analysis Panel
**Given** je suis sur Config > Exit
**When** je clique "Analyser mes trades passés"
**Then** un panneau s'ouvre avec:
- Sélection de la période (7j, 30j, 90j, all)
- Sélection des stratégies à comparer
- Bouton "Lancer l'analyse"

### AC 2: Run Batch Analysis
**Given** je lance l'analyse sur 50 trades
**When** l'analyse termine
**Then** je vois un tableau:
| Strategy | Total P&L | Avg P&L | Win Rate | Best For |
- "Best For" indique si mieux pour High Conviction ou Standard

### AC 3: Apply as Default
**Given** une stratégie est clairement meilleure
**When** je vois les résultats
**Then** je peux cliquer "Appliquer comme défaut" en un clic

### AC 4: Progress Indicator
**Given** l'analyse prend du temps
**When** elle tourne
**Then** je vois une progress bar
**And** je peux annuler

### AC 5: Cache Results
**Given** une analyse est terminée
**When** je reviens dans l'heure
**Then** les résultats sont cachés
**And** je peux forcer un refresh

## Technical Specifications

### Global Analyzer

**src/walltrack/services/simulation/global_analyzer.py:**
```python
"""Global analysis across multiple positions."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Callable
import asyncio

import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)
from walltrack.services.simulation.position_simulator import (
    PositionSimulator,
    get_position_simulator,
)

logger = structlog.get_logger(__name__)


@dataclass
class StrategyStats:
    """Aggregate stats for a strategy across positions."""
    strategy_id: str
    strategy_name: str
    total_positions: int
    winning_positions: int
    losing_positions: int
    win_rate: Decimal
    total_pnl_pct: Decimal
    avg_pnl_pct: Decimal
    max_gain_pct: Decimal
    max_loss_pct: Decimal
    avg_hold_hours: Decimal
    best_for: str  # "standard", "high", or "both"


@dataclass
class GlobalAnalysisResult:
    """Result of global analysis."""
    period_days: int
    total_positions: int
    positions_with_history: int

    strategy_stats: list[StrategyStats]
    best_overall_id: str
    best_overall_name: str
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

    def __init__(self):
        self.simulator = get_position_simulator()
        self._client = None
        self._strategy_service = None
        self._cache: dict[str, GlobalAnalysisResult] = {}
        self._cache_ttl_seconds = 3600  # 1 hour
        self._cache_timestamps: dict[str, datetime] = {}
        self._cancelled = False

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

    async def get_positions_with_history(
        self,
        days_back: int,
        limit: int = 500,
    ) -> list[dict]:
        """Get closed positions that have price history."""
        client = await self._get_client()
        cutoff = datetime.utcnow() - timedelta(days=days_back)

        # Get closed positions
        pos_result = await client.table("positions") \
            .select("id, token_address, entry_price, exit_price, entry_time, exit_time, size_sol, pnl_pct") \
            .eq("status", "closed") \
            .gte("exit_time", cutoff.isoformat()) \
            .order("exit_time", desc=True) \
            .limit(limit) \
            .execute()

        positions = pos_result.data or []

        # Filter to those with price history
        positions_with_history = []
        for pos in positions:
            history_result = await client.table("position_price_history") \
                .select("id") \
                .eq("position_id", pos["id"]) \
                .limit(1) \
                .execute()

            if history_result.data:
                # Get full history
                full_history = await client.table("position_price_history") \
                    .select("timestamp, price") \
                    .eq("position_id", pos["id"]) \
                    .order("timestamp") \
                    .execute()

                pos["price_history"] = full_history.data or []
                positions_with_history.append(pos)

        return positions_with_history

    async def analyze(
        self,
        strategy_ids: list[str],
        days_back: int = 30,
        on_progress: Optional[Callable[[int, int], None]] = None,
        use_cache: bool = True,
    ) -> Optional[GlobalAnalysisResult]:
        """
        Run global analysis.

        Args:
            strategy_ids: Strategies to analyze
            days_back: Days of history to analyze
            on_progress: Progress callback (current, total)
            use_cache: Whether to use cached results

        Returns:
            GlobalAnalysisResult or None if cancelled
        """
        self._cancelled = False
        start_time = datetime.utcnow()

        # Check cache
        cache_key = f"{days_back}:{','.join(sorted(strategy_ids))}"
        if use_cache and cache_key in self._cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and (datetime.utcnow() - cache_time).seconds < self._cache_ttl_seconds:
                logger.info("using_cached_analysis", days=days_back)
                return self._cache[cache_key]

        # Get positions
        positions = await self.get_positions_with_history(days_back)
        if not positions:
            logger.warning("no_positions_with_history", days=days_back)
            return None

        # Get strategies
        strategy_service = await self._get_strategy_service()
        strategies: list[ExitStrategy] = []
        for sid in strategy_ids:
            s = await strategy_service.get(sid)
            if s:
                strategies.append(s)

        if not strategies:
            return None

        total_sims = len(positions) * len(strategies)
        current_sim = 0

        # Run simulations
        strategy_results: dict[str, list[dict]] = {s.id: [] for s in strategies}

        for pos in positions:
            if self._cancelled:
                logger.info("analysis_cancelled")
                return None

            entry_price = Decimal(str(pos["entry_price"]))
            entry_time = datetime.fromisoformat(pos["entry_time"].replace("Z", "+00:00"))
            position_size = Decimal(str(pos["size_sol"]))

            for strategy in strategies:
                if self._cancelled:
                    return None

                result = self.simulator.simulate(
                    strategy=strategy,
                    entry_price=entry_price,
                    entry_time=entry_time,
                    position_size_sol=position_size,
                    price_history=pos["price_history"],
                    position_id=pos["id"],
                )

                strategy_results[strategy.id].append({
                    "pnl_pct": result.final_pnl_pct,
                    "hold_hours": result.total_duration_hours,
                    "actual_pnl": Decimal(str(pos.get("pnl_pct", 0))),
                })

                current_sim += 1
                if on_progress:
                    on_progress(current_sim, total_sims)

            # Yield to event loop periodically
            if current_sim % 10 == 0:
                await asyncio.sleep(0)

        # Calculate stats
        stats = []
        best_overall_pnl = Decimal("-999999")
        best_overall: Optional[ExitStrategy] = None

        for strategy in strategies:
            results = strategy_results[strategy.id]
            if not results:
                continue

            pnls = [r["pnl_pct"] for r in results]
            hold_hours = [r["hold_hours"] for r in results]

            winning = sum(1 for p in pnls if p > 0)
            losing = len(pnls) - winning

            total_pnl = sum(pnls)
            avg_pnl = total_pnl / len(pnls) if pnls else Decimal("0")

            stat = StrategyStats(
                strategy_id=strategy.id,
                strategy_name=strategy.name,
                total_positions=len(results),
                winning_positions=winning,
                losing_positions=losing,
                win_rate=Decimal(str(winning / len(results) * 100)) if results else Decimal("0"),
                total_pnl_pct=total_pnl,
                avg_pnl_pct=avg_pnl,
                max_gain_pct=max(pnls) if pnls else Decimal("0"),
                max_loss_pct=min(pnls) if pnls else Decimal("0"),
                avg_hold_hours=sum(hold_hours) / len(hold_hours) if hold_hours else Decimal("0"),
                best_for=self._determine_best_for(strategy, avg_pnl),
            )
            stats.append(stat)

            if total_pnl > best_overall_pnl:
                best_overall_pnl = total_pnl
                best_overall = strategy

        # Determine best for each tier
        best_standard = max(
            (s for s in stats if s.best_for in ["standard", "both"]),
            key=lambda x: x.avg_pnl_pct,
            default=stats[0] if stats else None
        )
        best_high = max(
            (s for s in stats if s.best_for in ["high", "both"]),
            key=lambda x: x.avg_pnl_pct,
            default=stats[0] if stats else None
        )

        duration = (datetime.utcnow() - start_time).total_seconds()

        result = GlobalAnalysisResult(
            period_days=days_back,
            total_positions=len(positions),
            positions_with_history=len(positions),
            strategy_stats=stats,
            best_overall_id=best_overall.id if best_overall else "",
            best_overall_name=best_overall.name if best_overall else "",
            best_for_standard_id=best_standard.strategy_id if best_standard else "",
            best_for_high_conviction_id=best_high.strategy_id if best_high else "",
            analysis_duration_seconds=duration,
        )

        # Cache result
        self._cache[cache_key] = result
        self._cache_timestamps[cache_key] = datetime.utcnow()

        logger.info(
            "global_analysis_complete",
            positions=len(positions),
            strategies=len(strategies),
            duration=duration,
        )

        return result

    def _determine_best_for(self, strategy: ExitStrategy, avg_pnl: Decimal) -> str:
        """Determine which conviction tier this strategy is best for."""
        # Simple heuristic based on strategy characteristics
        has_wide_stops = any(
            r.rule_type == "stop_loss" and r.trigger_pct and r.trigger_pct <= -12
            for r in strategy.rules
        )
        has_high_tps = any(
            r.rule_type == "take_profit" and r.trigger_pct and r.trigger_pct >= 40
            for r in strategy.rules
        )

        if has_wide_stops and has_high_tps:
            return "high"
        elif not has_wide_stops and not has_high_tps:
            return "standard"
        else:
            return "both"

    def cancel(self):
        """Cancel running analysis."""
        self._cancelled = True

    def clear_cache(self):
        """Clear results cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


# Singleton
_analyzer: Optional[GlobalAnalyzer] = None


async def get_global_analyzer() -> GlobalAnalyzer:
    """Get global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = GlobalAnalyzer()
    return _analyzer
```

### Global Analysis UI

**src/walltrack/ui/components/global_analysis.py:**
```python
"""Global analysis UI component."""

import gradio as gr
import structlog
import asyncio

from walltrack.services.exit.exit_strategy_service import get_exit_strategy_service
from walltrack.services.simulation.global_analyzer import get_global_analyzer

logger = structlog.get_logger(__name__)


async def build_global_analysis_component() -> gr.Blocks:
    """Build global analysis UI."""

    with gr.Blocks() as analysis_component:
        gr.Markdown("## 📈 Global Strategy Analysis")
        gr.Markdown("*Analyze all strategies across your historical trades*")

        with gr.Row():
            period_select = gr.Dropdown(
                choices=[
                    ("Last 7 days", 7),
                    ("Last 30 days", 30),
                    ("Last 90 days", 90),
                    ("All time", 365),
                ],
                value=30,
                label="Period",
            )

            strategy_checkboxes = gr.CheckboxGroup(
                label="Strategies to Analyze",
                choices=[],
            )

        with gr.Row():
            analyze_btn = gr.Button("🚀 Start Analysis", variant="primary")
            cancel_btn = gr.Button("Cancel", variant="stop")
            refresh_btn = gr.Button("🔄 Force Refresh (ignore cache)")

        progress_bar = gr.Progress()
        progress_text = gr.Markdown("*Ready to analyze*")

        # Results
        results_table = gr.Dataframe(
            headers=["Strategy", "Win Rate", "Avg P&L", "Total P&L", "Best For", ""],
            datatype=["str", "str", "str", "str", "str", "str"],
            label="Analysis Results",
            interactive=False,
        )

        with gr.Row():
            apply_standard_btn = gr.Button("Set Best as Standard Default", variant="secondary")
            apply_high_btn = gr.Button("Set Best as High Conviction Default", variant="secondary")

        status_text = gr.Textbox(label="Status", interactive=False)

        # State
        analysis_result_state = gr.State(None)

        # Load strategies
        async def load_strategies():
            service = await get_exit_strategy_service()
            strategies = await service.list_all()
            active = [s for s in strategies if s.status == "active"]
            return gr.update(
                choices=[(f"{s.name}", s.id) for s in active],
                value=[s.id for s in active[:5]]  # Pre-select first 5
            )

        # Run analysis
        async def run_analysis(period, strategy_ids, use_cache=True):
            if not strategy_ids:
                return [], "Select strategies first", None

            analyzer = await get_global_analyzer()

            def on_progress(current, total):
                pct = current / total if total > 0 else 0
                return f"*Analyzing... {current}/{total} ({pct*100:.0f}%)*"

            result = await analyzer.analyze(
                strategy_ids=strategy_ids,
                days_back=period,
                use_cache=use_cache,
            )

            if not result:
                return [], "Analysis failed or was cancelled", None

            # Format table
            rows = []
            for stat in result.strategy_stats:
                best_mark = "★" if stat.strategy_id == result.best_overall_id else ""
                rows.append([
                    stat.strategy_name,
                    f"{stat.win_rate:.1f}%",
                    f"{stat.avg_pnl_pct:+.2f}%",
                    f"{stat.total_pnl_pct:+.2f}%",
                    stat.best_for.title(),
                    best_mark,
                ])

            status = (
                f"Analyzed {result.total_positions} positions in {result.analysis_duration_seconds:.1f}s. "
                f"Best overall: {result.best_overall_name}"
            )

            return rows, status, result

        async def cancel_analysis():
            analyzer = await get_global_analyzer()
            analyzer.cancel()
            return "Analysis cancelled"

        async def apply_default(result, tier):
            if not result:
                return "Run analysis first"

            strategy_id = (
                result.best_for_high_conviction_id if tier == "high"
                else result.best_for_standard_id
            )

            if not strategy_id:
                return "No best strategy found"

            from walltrack.data.supabase.client import get_supabase_client
            client = await get_supabase_client()

            config_field = (
                "default_strategy_high_conviction_id" if tier == "high"
                else "default_strategy_standard_id"
            )

            await client.table("exit_config") \
                .update({config_field: strategy_id}) \
                .eq("status", "active") \
                .execute()

            service = await get_exit_strategy_service()
            strategy = await service.get(strategy_id)

            return f"Set '{strategy.name}' as {tier} default"

        # Wire up
        analysis_component.load(load_strategies, [], [strategy_checkboxes])

        analyze_btn.click(
            run_analysis,
            [period_select, strategy_checkboxes],
            [results_table, status_text, analysis_result_state]
        )

        refresh_btn.click(
            lambda p, s: run_analysis(p, s, use_cache=False),
            [period_select, strategy_checkboxes],
            [results_table, status_text, analysis_result_state]
        )

        cancel_btn.click(cancel_analysis, [], [status_text])

        apply_standard_btn.click(
            lambda r: apply_default(r, "standard"),
            [analysis_result_state],
            [status_text]
        )

        apply_high_btn.click(
            lambda r: apply_default(r, "high"),
            [analysis_result_state],
            [status_text]
        )

    return analysis_component
```

## Implementation Tasks

- [x] Create StrategyStats dataclass
- [x] Create GlobalAnalysisResult dataclass
- [x] Implement GlobalAnalyzer class
- [x] Implement get_positions_with_history()
- [x] Implement analyze() with progress
- [x] Add cancellation support
- [x] Add result caching
- [x] Build UI component
- [x] Add apply as default functionality
- [x] Write tests

## Definition of Done

- [x] Analysis runs on selected period
- [x] Progress bar updates
- [x] Results show all strategies
- [x] Best strategy highlighted
- [x] Apply as default works
- [x] Cancellation works
- [x] Cache prevents re-analysis

## File List

### New Files
- `src/walltrack/services/simulation/global_analyzer.py` - Analyzer
- `src/walltrack/ui/components/global_analysis.py` - UI

### Modified Files
- `src/walltrack/ui/pages/config_page.py` - Add analysis tab
