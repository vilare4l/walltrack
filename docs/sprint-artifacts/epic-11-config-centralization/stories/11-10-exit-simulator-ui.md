# Story 11.10: UI - Exit Strategy Simulator

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 5
- **Depends on**: Story 11-8 (Simulation Engine), Story 11-9 (Exit Strategy Editor UI)

## User Story

**As a** trader,
**I want** a visual simulator to backtest exit strategies,
**So that** I can compare performance before deploying.

## Acceptance Criteria

### AC 1: Select Position for Simulation
**Given** I navigate to the Simulator page
**When** I select a closed position
**Then** position details are loaded
**And** price history is available for simulation

### AC 2: Run Single Simulation
**Given** I have selected a position and strategy
**When** I click "Simulate"
**Then** I see simulation results
**And** triggered rules are shown on timeline

### AC 3: Compare Strategies
**Given** I select multiple strategies
**When** I click "Compare"
**Then** I see side-by-side results
**And** best strategy is highlighted

### AC 4: Batch Simulation
**Given** I want to test on multiple positions
**When** I select date range and click "Batch Simulate"
**Then** aggregate statistics are calculated
**And** I see win rate, avg P&L, etc.

### AC 5: Visual Timeline
**Given** simulation results exist
**When** I view the timeline
**Then** I see price chart with entry/exit points
**And** rule triggers are marked

### AC 6: What-If on Open Position
**Given** I have an open position
**When** I select it for what-if analysis
**Then** I see projected outcomes at different prices
**And** key levels (SL, TP) are shown

## Technical Specifications

### Exit Simulator Page

**src/walltrack/ui/pages/exit_simulator_page.py:**
```python
"""Exit strategy simulator page with backtesting."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import gradio as gr
import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)
from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    SimulationResult,
    AggregateStats,
    get_simulation_engine,
)
from walltrack.services.exit.what_if_calculator import WhatIfCalculator

logger = structlog.get_logger(__name__)


class ExitSimulatorPage:
    """Exit strategy simulator page."""

    def __init__(self):
        self.strategy_service = None
        self.simulation_engine = None
        self.what_if_calculator = WhatIfCalculator()

    async def initialize(self):
        """Initialize services."""
        self.strategy_service = await get_exit_strategy_service()
        self.simulation_engine = await get_simulation_engine()

    async def get_strategies_dropdown(self) -> list[tuple[str, str]]:
        """Get strategies for dropdown."""
        if not self.strategy_service:
            await self.initialize()

        strategies = await self.strategy_service.list_all()
        return [(f"{s.name} (v{s.version}) - {s.status}", s.id) for s in strategies]

    async def get_closed_positions(
        self,
        days_back: int = 30,
        limit: int = 50,
    ) -> list[dict]:
        """Get closed positions for simulation."""
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()
        start_date = datetime.utcnow() - timedelta(days=days_back)

        result = await client.table("positions") \
            .select("id, token_address, entry_price, exit_price, entry_time, exit_time, size_sol, pnl_pct") \
            .eq("status", "closed") \
            .gte("exit_time", start_date.isoformat()) \
            .order("exit_time", desc=True) \
            .limit(limit) \
            .execute()

        return result.data or []

    async def get_open_positions(self) -> list[dict]:
        """Get open positions for what-if analysis."""
        from walltrack.data.supabase.client import get_supabase_client

        client = await get_supabase_client()

        result = await client.table("positions") \
            .select("id, token_address, entry_price, entry_time, size_sol, current_price") \
            .eq("status", "open") \
            .execute()

        return result.data or []

    async def run_simulation(
        self,
        strategy_id: str,
        position_id: str,
    ) -> Optional[SimulationResult]:
        """Run simulation on single position."""
        if not self.simulation_engine:
            await self.initialize()

        # Get position data
        from walltrack.data.supabase.client import get_supabase_client
        client = await get_supabase_client()

        pos_result = await client.table("positions") \
            .select("*") \
            .eq("id", position_id) \
            .single() \
            .execute()

        if not pos_result.data:
            return None

        pos = pos_result.data

        # Get strategy
        strategy = await self.strategy_service.get(strategy_id)
        if not strategy:
            return None

        # Run simulation
        result = await self.simulation_engine.simulate_position(
            strategy=strategy,
            position_id=position_id,
            entry_price=Decimal(str(pos["entry_price"])),
            entry_time=datetime.fromisoformat(pos["entry_time"].replace("Z", "+00:00")),
            position_size_sol=Decimal(str(pos["size_sol"])),
            token_address=pos["token_address"],
            actual_exit=(
                Decimal(str(pos["exit_price"])),
                datetime.fromisoformat(pos["exit_time"].replace("Z", "+00:00"))
            ) if pos.get("exit_price") else None,
        )

        return result

    async def run_comparison(
        self,
        strategy_ids: list[str],
        position_ids: list[str],
    ) -> dict:
        """Compare multiple strategies on positions."""
        if not self.simulation_engine:
            await self.initialize()

        # Get strategies
        strategies = []
        for sid in strategy_ids:
            s = await self.strategy_service.get(sid)
            if s:
                strategies.append(s)

        # Get positions
        from walltrack.data.supabase.client import get_supabase_client
        client = await get_supabase_client()

        positions = []
        for pid in position_ids:
            pos_result = await client.table("positions") \
                .select("*") \
                .eq("id", pid) \
                .single() \
                .execute()

            if pos_result.data:
                p = pos_result.data
                positions.append({
                    "id": p["id"],
                    "token_address": p["token_address"],
                    "entry_price": p["entry_price"],
                    "entry_time": datetime.fromisoformat(p["entry_time"].replace("Z", "+00:00")),
                    "size_sol": p["size_sol"],
                    "exit_price": p.get("exit_price"),
                    "exit_time": datetime.fromisoformat(p["exit_time"].replace("Z", "+00:00")) if p.get("exit_time") else None,
                })

        # Run comparison
        comparison = await self.simulation_engine.compare_strategies(strategies, positions)

        return {
            "strategies": [s.name for s in strategies],
            "results": {
                sid: {
                    "win_rate": float(stats.win_rate),
                    "avg_pnl": float(stats.avg_pnl_pct),
                    "total_pnl": float(stats.total_pnl_pct),
                    "max_gain": float(stats.max_gain_pct),
                    "max_loss": float(stats.max_loss_pct),
                }
                for sid, stats in comparison.results.items()
            },
            "best_strategy": comparison.best_strategy_id,
        }

    async def run_batch_simulation(
        self,
        strategy_id: str,
        days_back: int = 30,
    ) -> tuple[list[SimulationResult], AggregateStats]:
        """Run batch simulation on recent closed positions."""
        if not self.simulation_engine:
            await self.initialize()

        positions = await self.get_closed_positions(days_back=days_back)
        strategy = await self.strategy_service.get(strategy_id)

        if not strategy or not positions:
            return [], AggregateStats(
                total_positions=0, winning_positions=0, losing_positions=0,
                win_rate=Decimal("0"), total_pnl_pct=Decimal("0"),
                avg_pnl_pct=Decimal("0"), max_gain_pct=Decimal("0"),
                max_loss_pct=Decimal("0"), avg_hold_hours=Decimal("0"),
            )

        # Format positions
        formatted = [
            {
                "id": p["id"],
                "token_address": p["token_address"],
                "entry_price": p["entry_price"],
                "entry_time": datetime.fromisoformat(p["entry_time"].replace("Z", "+00:00")),
                "size_sol": p["size_sol"],
                "exit_price": p.get("exit_price"),
                "exit_time": datetime.fromisoformat(p["exit_time"].replace("Z", "+00:00")) if p.get("exit_time") else None,
            }
            for p in positions
        ]

        return await self.simulation_engine.batch_simulate(strategy, formatted)

    def run_what_if(
        self,
        strategy: ExitStrategy,
        entry_price: float,
        current_price: float,
        position_size: float,
        entry_time: datetime,
    ):
        """Run what-if analysis."""
        return self.what_if_calculator.analyze(
            strategy=strategy,
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(current_price)),
            position_size_sol=Decimal(str(position_size)),
            entry_time=entry_time,
        )


def build_timeline_chart(result: SimulationResult):
    """Build timeline chart from simulation result."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(12, 6))

    # Entry point
    ax.axhline(y=float(result.entry_price), color='blue', linestyle='-', label='Entry', alpha=0.5)

    # Plot triggers
    for trigger in result.triggers:
        color = {
            "take_profit": "green",
            "stop_loss": "red",
            "trailing_stop": "orange",
            "stagnation": "purple",
            "max_hold_time": "gray",
        }.get(trigger.rule_type, "gray")

        ax.plot(
            trigger.timestamp,
            float(trigger.price_at_trigger),
            marker='o',
            color=color,
            markersize=10,
            label=f"{trigger.rule_type} ({trigger.pnl_pct:.1f}%)"
        )

        ax.annotate(
            f"{trigger.rule_type}\n{trigger.pnl_pct:+.1f}%",
            xy=(trigger.timestamp, float(trigger.price_at_trigger)),
            xytext=(10, 10),
            textcoords='offset points',
            fontsize=8,
            bbox=dict(boxstyle='round', facecolor=color, alpha=0.3),
        )

    ax.set_xlabel('Time')
    ax.set_ylabel('Price')
    ax.set_title(f"Simulation: {result.strategy_name}")

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%m/%d %H:%M'))
    plt.xticks(rotation=45)

    ax.legend(loc='best')
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def build_comparison_chart(comparison: dict):
    """Build comparison chart for multiple strategies."""
    import matplotlib.pyplot as plt
    import numpy as np

    strategies = comparison["strategies"]
    results = comparison["results"]

    # Metrics to compare
    metrics = ["win_rate", "avg_pnl", "total_pnl"]
    metric_labels = ["Win Rate (%)", "Avg P&L (%)", "Total P&L (%)"]

    x = np.arange(len(strategies))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))

    for i, (metric, label) in enumerate(zip(metrics, metric_labels)):
        values = [results.get(sid, {}).get(metric, 0) for sid in results.keys()]
        bars = ax.bar(x + i * width, values, width, label=label)

        # Highlight best
        best_idx = values.index(max(values)) if values else 0
        bars[best_idx].set_edgecolor('gold')
        bars[best_idx].set_linewidth(3)

    ax.set_xlabel('Strategy')
    ax.set_ylabel('Value')
    ax.set_title('Strategy Comparison')
    ax.set_xticks(x + width)
    ax.set_xticklabels(strategies, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    return fig


async def build_exit_simulator_page() -> gr.Blocks:
    """Build the exit simulator page."""
    page = ExitSimulatorPage()
    await page.initialize()

    with gr.Blocks() as simulator_page:
        gr.Markdown("# Exit Strategy Simulator")

        with gr.Tabs():
            # Single Simulation Tab
            with gr.Tab("Single Simulation"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Select Position & Strategy")

                        # Position selector
                        position_days = gr.Slider(
                            minimum=7, maximum=90, value=30, step=1,
                            label="Days Back"
                        )
                        position_dropdown = gr.Dropdown(
                            label="Position",
                            choices=[],
                        )
                        refresh_positions_btn = gr.Button("Refresh Positions", size="sm")

                        # Strategy selector
                        strategy_dropdown = gr.Dropdown(
                            label="Strategy",
                            choices=[],
                        )
                        refresh_strategies_btn = gr.Button("Refresh Strategies", size="sm")

                        simulate_btn = gr.Button("Run Simulation", variant="primary")

                    with gr.Column(scale=2):
                        gr.Markdown("### Results")

                        result_summary = gr.Markdown()
                        timeline_chart = gr.Plot(label="Timeline")
                        triggers_table = gr.Dataframe(
                            headers=["Time", "Rule", "Trigger %", "Price", "P&L %", "Exit %"],
                            datatype=["str", "str", "number", "number", "number", "number"],
                            label="Triggered Rules",
                        )

            # Comparison Tab
            with gr.Tab("Strategy Comparison"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Select Strategies")

                        compare_strategies = gr.CheckboxGroup(
                            label="Strategies to Compare",
                            choices=[],
                        )
                        compare_days = gr.Slider(
                            minimum=7, maximum=90, value=30, step=1,
                            label="Days Back"
                        )
                        compare_btn = gr.Button("Compare", variant="primary")

                    with gr.Column(scale=2):
                        gr.Markdown("### Comparison Results")

                        comparison_chart = gr.Plot(label="Comparison")
                        comparison_table = gr.Dataframe(
                            headers=["Strategy", "Win Rate", "Avg P&L", "Total P&L", "Max Gain", "Max Loss"],
                            datatype=["str", "number", "number", "number", "number", "number"],
                            label="Stats",
                        )
                        best_strategy_text = gr.Textbox(label="Best Strategy", interactive=False)

            # Batch Simulation Tab
            with gr.Tab("Batch Simulation"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Configuration")

                        batch_strategy = gr.Dropdown(
                            label="Strategy",
                            choices=[],
                        )
                        batch_days = gr.Slider(
                            minimum=7, maximum=90, value=30, step=1,
                            label="Days Back"
                        )
                        batch_btn = gr.Button("Run Batch", variant="primary")

                    with gr.Column(scale=2):
                        gr.Markdown("### Aggregate Results")

                        batch_stats = gr.Markdown()
                        batch_results_table = gr.Dataframe(
                            headers=["Position", "Entry", "Simulated Exit", "P&L %", "Actual P&L %", "Diff"],
                            datatype=["str", "number", "number", "number", "number", "number"],
                            label="Individual Results",
                        )

            # What-If Tab
            with gr.Tab("What-If Analysis"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Open Position")

                        open_position_dropdown = gr.Dropdown(
                            label="Position",
                            choices=[],
                        )
                        refresh_open_btn = gr.Button("Refresh", size="sm")

                        whatif_strategy = gr.Dropdown(
                            label="Strategy",
                            choices=[],
                        )
                        whatif_btn = gr.Button("Analyze", variant="primary")

                    with gr.Column(scale=2):
                        gr.Markdown("### Projected Outcomes")

                        whatif_summary = gr.Markdown()
                        whatif_scenarios = gr.Dataframe(
                            headers=["Price", "P&L %", "P&L SOL", "Action", "Exit %", "Rules"],
                            datatype=["number", "number", "number", "str", "number", "str"],
                            label="Scenarios",
                        )

        # Event handlers
        async def load_positions(days):
            positions = await page.get_closed_positions(days_back=int(days))
            choices = [
                (f"{p['token_address'][:8]}... ({p['pnl_pct']:+.1f}%) - {p['exit_time'][:10]}", p["id"])
                for p in positions
            ]
            return gr.update(choices=choices)

        async def load_strategies():
            strategies = await page.get_strategies_dropdown()
            return gr.update(choices=strategies)

        async def run_single_simulation(strategy_id, position_id):
            if not strategy_id or not position_id:
                return "Select both position and strategy", None, []

            result = await page.run_simulation(strategy_id, position_id)
            if not result:
                return "Simulation failed", None, []

            summary = f"""
### Simulation Results

**Strategy:** {result.strategy_name}

| Metric | Simulated | Actual | Difference |
|--------|-----------|--------|------------|
| Exit Price | {result.final_exit_price:.6f} | {result.actual_exit_price or 'N/A'} | - |
| P&L % | {result.final_pnl_pct:+.2f}% | {result.actual_pnl_pct or 'N/A'} | {result.pnl_difference or 'N/A'} |
| P&L SOL | {result.final_pnl_sol:+.4f} | - | - |

**Max Unrealized Gain:** {result.max_unrealized_gain_pct:+.2f}%
**Max Unrealized Loss:** {result.max_unrealized_loss_pct:.2f}%
**Hold Duration:** {result.hold_duration_hours:.1f} hours
"""

            chart = build_timeline_chart(result)

            triggers = [
                [
                    t.timestamp.strftime("%Y-%m-%d %H:%M"),
                    t.rule_type,
                    float(t.trigger_pct) if t.trigger_pct else None,
                    float(t.price_at_trigger),
                    float(t.pnl_pct),
                    float(t.exit_pct),
                ]
                for t in result.triggers
            ]

            return summary, chart, triggers

        async def run_comparison(strategy_ids, days):
            if not strategy_ids or len(strategy_ids) < 2:
                return None, [], "Select at least 2 strategies"

            positions = await page.get_closed_positions(days_back=int(days))
            position_ids = [p["id"] for p in positions]

            comparison = await page.run_comparison(strategy_ids, position_ids)

            chart = build_comparison_chart(comparison)

            table_data = []
            for sid, stats in comparison["results"].items():
                strategy = await page.strategy_service.get(sid)
                name = strategy.name if strategy else sid[:8]
                table_data.append([
                    name,
                    stats["win_rate"],
                    stats["avg_pnl"],
                    stats["total_pnl"],
                    stats["max_gain"],
                    stats["max_loss"],
                ])

            best = await page.strategy_service.get(comparison["best_strategy"])
            best_text = f"Best: {best.name}" if best else "N/A"

            return chart, table_data, best_text

        async def run_batch(strategy_id, days):
            if not strategy_id:
                return "Select a strategy", []

            results, stats = await page.run_batch_simulation(strategy_id, int(days))

            summary = f"""
### Aggregate Statistics

| Metric | Value |
|--------|-------|
| Total Positions | {stats.total_positions} |
| Winning | {stats.winning_positions} |
| Losing | {stats.losing_positions} |
| **Win Rate** | **{stats.win_rate:.1f}%** |
| Avg P&L | {stats.avg_pnl_pct:+.2f}% |
| Total P&L | {stats.total_pnl_pct:+.2f}% |
| Max Gain | {stats.max_gain_pct:+.2f}% |
| Max Loss | {stats.max_loss_pct:.2f}% |
| Avg Hold | {stats.avg_hold_hours:.1f}h |
"""

            table_data = [
                [
                    r.position_id[:8],
                    float(r.entry_price),
                    float(r.final_exit_price),
                    float(r.final_pnl_pct),
                    float(r.actual_pnl_pct) if r.actual_pnl_pct else None,
                    float(r.pnl_difference) if r.pnl_difference else None,
                ]
                for r in results[:50]  # Limit display
            ]

            return summary, table_data

        async def load_open_positions():
            positions = await page.get_open_positions()
            choices = [
                (f"{p['token_address'][:8]}... @ {p['entry_price']}", p["id"])
                for p in positions
            ]
            return gr.update(choices=choices)

        async def run_whatif(position_id, strategy_id):
            if not position_id or not strategy_id:
                return "Select position and strategy", []

            # Get position
            from walltrack.data.supabase.client import get_supabase_client
            client = await get_supabase_client()

            pos = await client.table("positions") \
                .select("*") \
                .eq("id", position_id) \
                .single() \
                .execute()

            if not pos.data:
                return "Position not found", []

            p = pos.data
            strategy = await page.strategy_service.get(strategy_id)

            if not strategy:
                return "Strategy not found", []

            analysis = page.run_what_if(
                strategy=strategy,
                entry_price=float(p["entry_price"]),
                current_price=float(p.get("current_price", p["entry_price"])),
                position_size=float(p["size_sol"]),
                entry_time=datetime.fromisoformat(p["entry_time"].replace("Z", "+00:00")),
            )

            summary = f"""
### Position Analysis

**Entry:** {analysis.entry_price} | **Current:** {analysis.current_price}
**Current P&L:** {analysis.current_pnl_pct:+.2f}% ({analysis.current_pnl_sol:+.4f} SOL)
**Time Held:** {analysis.time_held_hours:.1f} hours

**Key Levels:**
- Breakeven: {analysis.breakeven_price}
- Stop Loss: {analysis.stop_loss_price or 'Not set'}
- First TP: {analysis.first_tp_price or 'Not set'}
"""

            scenarios = [
                [
                    float(s.price),
                    float(s.pnl_pct),
                    float(s.pnl_sol),
                    s.action,
                    float(s.exit_pct),
                    ", ".join(s.triggered_rules) or "-",
                ]
                for s in analysis.scenarios
            ]

            return summary, scenarios

        # Wire up events
        refresh_positions_btn.click(load_positions, [position_days], [position_dropdown])
        position_days.change(load_positions, [position_days], [position_dropdown])
        refresh_strategies_btn.click(load_strategies, [], [strategy_dropdown])

        simulate_btn.click(
            run_single_simulation,
            [strategy_dropdown, position_dropdown],
            [result_summary, timeline_chart, triggers_table]
        )

        compare_btn.click(
            run_comparison,
            [compare_strategies, compare_days],
            [comparison_chart, comparison_table, best_strategy_text]
        )

        batch_btn.click(
            run_batch,
            [batch_strategy, batch_days],
            [batch_stats, batch_results_table]
        )

        refresh_open_btn.click(load_open_positions, [], [open_position_dropdown])
        whatif_btn.click(
            run_whatif,
            [open_position_dropdown, whatif_strategy],
            [whatif_summary, whatif_scenarios]
        )

        # Initial loads
        simulator_page.load(load_positions, [position_days], [position_dropdown])
        simulator_page.load(load_strategies, [], [strategy_dropdown])
        simulator_page.load(load_strategies, [], [batch_strategy])
        simulator_page.load(load_strategies, [], [whatif_strategy])
        simulator_page.load(load_open_positions, [], [open_position_dropdown])

        async def load_compare_strategies():
            strategies = await page.get_strategies_dropdown()
            return gr.update(choices=strategies)

        simulator_page.load(load_compare_strategies, [], [compare_strategies])

    return simulator_page
```

## Implementation Tasks

- [ ] Create ExitSimulatorPage class
- [ ] Implement single simulation UI
- [ ] Build timeline chart visualization
- [ ] Implement strategy comparison UI
- [ ] Build comparison chart
- [ ] Implement batch simulation UI
- [ ] Implement what-if analysis UI
- [ ] Add position and strategy selectors
- [ ] Connect to simulation engine
- [ ] Add to main navigation

## Definition of Done

- [ ] Single simulation displays results
- [ ] Timeline chart shows triggers
- [ ] Strategy comparison works
- [ ] Batch simulation calculates stats
- [ ] What-if shows projected outcomes
- [ ] All tabs functional
- [ ] Charts render correctly

## File List

### New Files
- `src/walltrack/ui/pages/exit_simulator_page.py` - Simulator page

### Modified Files
- `src/walltrack/ui/app.py` - Add simulator to navigation
