"""Exit strategy simulator page with backtesting."""

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import gradio as gr
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyService,
    get_exit_strategy_service,
)
from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    SimulationResult,
    get_simulation_engine,
)
from walltrack.services.exit.what_if_calculator import WhatIfCalculator

logger = structlog.get_logger(__name__)


class ExitSimulatorPage:
    """Exit strategy simulator page."""

    def __init__(self) -> None:
        self.strategy_service: ExitStrategyService | None = None
        self.simulation_engine: ExitSimulationEngine | None = None
        self.what_if_calculator = WhatIfCalculator()

    async def initialize(self) -> None:
        """Initialize services."""
        self.strategy_service = await get_exit_strategy_service()
        self.simulation_engine = await get_simulation_engine()

    async def get_strategies_list(self) -> list[tuple[str, str]]:
        """Get strategies for dropdown."""
        if not self.strategy_service:
            await self.initialize()

        assert self.strategy_service is not None
        strategies = await self.strategy_service.list_all()
        return [(f"{s.name} (v{s.version}) - {s.status}", s.id) for s in strategies]

    async def run_simulation_on_sample(
        self,
        strategy_id: str,
        entry_price: float,
        position_size: float,
        price_history_json: str,
    ) -> SimulationResult | None:
        """Run simulation on sample price data."""
        if not self.simulation_engine or not self.strategy_service:
            await self.initialize()

        assert self.simulation_engine is not None
        assert self.strategy_service is not None

        try:
            strategy = await self.strategy_service.get(strategy_id)
            if not strategy:
                return None

            # Parse price history
            prices = json.loads(price_history_json)
            if not prices:
                return None

            # Format for simulation
            price_history = [
                {
                    "timestamp": datetime.fromisoformat(p["timestamp"]),
                    "price": float(p["price"]),
                }
                for p in prices
            ]

            entry_time = price_history[0]["timestamp"]

            result = await self.simulation_engine.simulate_position(
                strategy=strategy,
                position_id="sample-sim",
                entry_price=Decimal(str(entry_price)),
                entry_time=entry_time,
                position_size_sol=Decimal(str(position_size)),
                price_history=price_history,
            )

            return result

        except Exception as e:
            logger.error("simulation_error", error=str(e))
            return None

    def run_what_if(
        self,
        strategy: ExitStrategy,
        entry_price: float,
        current_price: float,
        position_size: float,
        entry_time: datetime,
    ) -> dict:
        """Run what-if analysis."""
        analysis = self.what_if_calculator.analyze(
            strategy=strategy,
            entry_price=Decimal(str(entry_price)),
            current_price=Decimal(str(current_price)),
            position_size_sol=Decimal(str(position_size)),
            entry_time=entry_time,
        )

        return {
            "position_id": analysis.position_id,
            "entry_price": float(analysis.entry_price),
            "current_price": float(analysis.current_price),
            "current_pnl_pct": float(analysis.current_pnl_pct),
            "current_pnl_sol": float(analysis.current_pnl_sol),
            "time_held_hours": float(analysis.time_held_hours),
            "stop_loss_price": (
                float(analysis.stop_loss_price) if analysis.stop_loss_price else None
            ),
            "first_tp_price": (
                float(analysis.first_tp_price) if analysis.first_tp_price else None
            ),
            "breakeven_price": float(analysis.breakeven_price),
            "scenarios": [
                {
                    "price": float(s.price),
                    "pnl_pct": float(s.pnl_pct),
                    "pnl_sol": float(s.pnl_sol),
                    "action": s.action,
                    "exit_pct": float(s.exit_pct),
                    "triggered_rules": s.triggered_rules,
                }
                for s in analysis.scenarios
            ],
        }


def build_timeline_chart(result: SimulationResult) -> plt.Figure:
    """Build timeline chart from simulation result."""
    fig, ax = plt.subplots(figsize=(12, 6))

    # Entry point
    ax.axhline(
        y=float(result.entry_price),
        color="blue",
        linestyle="-",
        label="Entry",
        alpha=0.5,
    )

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
            marker="o",
            color=color,
            markersize=10,
            label=f"{trigger.rule_type} ({trigger.pnl_pct:.1f}%)",
        )

        ax.annotate(
            f"{trigger.rule_type}\n{trigger.pnl_pct:+.1f}%",
            xy=(trigger.timestamp, float(trigger.price_at_trigger)),
            xytext=(10, 10),
            textcoords="offset points",
            fontsize=8,
            bbox={"boxstyle": "round", "facecolor": color, "alpha": 0.3},
        )

    ax.set_xlabel("Time")
    ax.set_ylabel("Price")
    ax.set_title(f"Simulation: {result.strategy_name}")

    # Format x-axis
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%m/%d %H:%M"))
    plt.xticks(rotation=45)

    ax.legend(loc="best")
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    return fig


def build_comparison_chart(comparison: dict) -> plt.Figure:
    """Build comparison chart for multiple strategies."""
    strategies = list(comparison["results"].keys())
    results = comparison["results"]

    # Metrics to compare
    metrics = ["win_rate", "avg_pnl", "total_pnl"]
    metric_labels = ["Win Rate (%)", "Avg P&L (%)", "Total P&L (%)"]

    x = np.arange(len(strategies))
    width = 0.25

    fig, ax = plt.subplots(figsize=(12, 6))

    for i, (metric, label) in enumerate(zip(metrics, metric_labels, strict=False)):
        values = [results.get(sid, {}).get(metric, 0) for sid in strategies]
        bars = ax.bar(x + i * width, values, width, label=label)

        # Highlight best
        if values:
            best_idx = values.index(max(values))
            bars[best_idx].set_edgecolor("gold")
            bars[best_idx].set_linewidth(3)

    ax.set_xlabel("Strategy")
    ax.set_ylabel("Value")
    ax.set_title("Strategy Comparison")
    ax.set_xticks(x + width)
    ax.set_xticklabels(strategies, rotation=45, ha="right")
    ax.legend()
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    return fig


SAMPLE_PRICE_HISTORY = """[
  {"timestamp": "2024-01-01T10:00:00+00:00", "price": 1.00},
  {"timestamp": "2024-01-01T11:00:00+00:00", "price": 1.02},
  {"timestamp": "2024-01-01T12:00:00+00:00", "price": 1.05},
  {"timestamp": "2024-01-01T13:00:00+00:00", "price": 1.08},
  {"timestamp": "2024-01-01T14:00:00+00:00", "price": 1.12},
  {"timestamp": "2024-01-01T15:00:00+00:00", "price": 1.18},
  {"timestamp": "2024-01-01T16:00:00+00:00", "price": 1.22},
  {"timestamp": "2024-01-01T17:00:00+00:00", "price": 1.15},
  {"timestamp": "2024-01-01T18:00:00+00:00", "price": 1.10},
  {"timestamp": "2024-01-01T19:00:00+00:00", "price": 1.05}
]"""


def create_exit_simulator_page() -> None:  # noqa: PLR0915
    """Build the exit simulator page."""
    page = ExitSimulatorPage()

    with gr.Tabs():
        # Single Simulation Tab
        with gr.Tab("Single Simulation"):  # noqa: SIM117
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Simulation Configuration")

                    strategy_dropdown = gr.Dropdown(
                        label="Strategy",
                        choices=[],
                    )
                    refresh_strategies_btn = gr.Button("Refresh Strategies", size="sm")

                    entry_price_input = gr.Number(
                        label="Entry Price",
                        value=1.0,
                    )
                    position_size_input = gr.Number(
                        label="Position Size (SOL)",
                        value=10.0,
                    )

                    gr.Markdown("### Price History (JSON)")
                    price_history_input = gr.Code(
                        language="json",
                        label="Price History",
                        value=SAMPLE_PRICE_HISTORY,
                        lines=12,
                    )

                    simulate_btn = gr.Button("Run Simulation", variant="primary")

                with gr.Column(scale=2):
                    gr.Markdown("### Results")

                    result_summary = gr.Markdown(value="*Run simulation to see results*")
                    timeline_chart = gr.Plot(label="Timeline")
                    triggers_table = gr.Dataframe(
                        headers=[
                            "Time",
                            "Rule",
                            "Trigger %",
                            "Price",
                            "P&L %",
                            "Exit %",
                        ],
                        datatype=["str", "str", "number", "number", "number", "number"],
                        label="Triggered Rules",
                    )

        # What-If Tab
        with gr.Tab("What-If Analysis"):  # noqa: SIM117
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### Position Parameters")

                    whatif_strategy = gr.Dropdown(
                        label="Strategy",
                        choices=[],
                    )
                    refresh_whatif_btn = gr.Button("Refresh Strategies", size="sm")

                    whatif_entry = gr.Number(
                        label="Entry Price",
                        value=1.0,
                    )
                    whatif_current = gr.Number(
                        label="Current Price",
                        value=1.05,
                    )
                    whatif_size = gr.Number(
                        label="Position Size (SOL)",
                        value=10.0,
                    )
                    whatif_hours = gr.Number(
                        label="Hours Held",
                        value=2,
                    )

                    whatif_btn = gr.Button("Analyze", variant="primary")

                with gr.Column(scale=2):
                    gr.Markdown("### Projected Outcomes")

                    whatif_summary = gr.Markdown(value="*Click Analyze to see projections*")
                    whatif_scenarios = gr.Dataframe(
                        headers=[
                            "Price",
                            "P&L %",
                            "P&L SOL",
                            "Action",
                            "Exit %",
                            "Rules",
                        ],
                        datatype=[
                            "number",
                            "number",
                            "number",
                            "str",
                            "number",
                            "str",
                        ],
                        label="Scenarios",
                    )

    # Event handlers
    async def load_strategies() -> gr.Dropdown:
        strategies = await page.get_strategies_list()
        return gr.update(choices=strategies)

    async def run_single_simulation(
        strategy_id: str | None,
        entry_price: float,
        position_size: float,
        price_history_json: str,
    ) -> tuple[str, plt.Figure | None, list]:
        if not strategy_id:
            return "Select a strategy", None, []

        result = await page.run_simulation_on_sample(
            strategy_id, entry_price, position_size, price_history_json
        )
        if not result:
            return "Simulation failed - check price history JSON format", None, []

        summary = f"""
### Simulation Results

**Strategy:** {result.strategy_name}

| Metric | Value |
|--------|-------|
| Final Exit Price | {result.final_exit_price:.6f} |
| Final P&L % | {result.final_pnl_pct:+.2f}% |
| Final P&L SOL | {result.final_pnl_sol:+.4f} |
| Max Unrealized Gain | {result.max_unrealized_gain_pct:+.2f}% |
| Max Unrealized Loss | {result.max_unrealized_loss_pct:.2f}% |
| Hold Duration | {result.hold_duration_hours:.1f} hours |
| Triggers Count | {len(result.triggers)} |
"""

        chart = build_timeline_chart(result) if result.triggers else None

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

    async def run_whatif(
        strategy_id: str | None,
        entry_price: float,
        current_price: float,
        position_size: float,
        hours_held: float,
    ) -> tuple[str, list]:
        if not strategy_id:
            return "Select a strategy", []

        if not page.strategy_service:
            await page.initialize()

        assert page.strategy_service is not None
        strategy = await page.strategy_service.get(strategy_id)

        if not strategy:
            return "Strategy not found", []

        entry_time = datetime.now(UTC) - timedelta(hours=hours_held)

        analysis = page.run_what_if(
            strategy=strategy,
            entry_price=entry_price,
            current_price=current_price,
            position_size=position_size,
            entry_time=entry_time,
        )

        summary = f"""
### Position Analysis

**Entry:** {analysis['entry_price']:.6f} | **Current:** {analysis['current_price']:.6f}
**Current P&L:** {analysis['current_pnl_pct']:+.2f}% ({analysis['current_pnl_sol']:+.4f} SOL)
**Time Held:** {analysis['time_held_hours']:.1f} hours

**Key Levels:**
- Breakeven: {analysis['breakeven_price']:.6f}
- Stop Loss: {analysis['stop_loss_price']:.6f if analysis['stop_loss_price'] else 'Not set'}
- First TP: {analysis['first_tp_price']:.6f if analysis['first_tp_price'] else 'Not set'}
"""

        scenarios = [
            [
                s["price"],
                s["pnl_pct"],
                s["pnl_sol"],
                s["action"],
                s["exit_pct"],
                ", ".join(s["triggered_rules"]) or "-",
            ]
            for s in analysis["scenarios"]
        ]

        return summary, scenarios

    # Wire up events
    refresh_strategies_btn.click(load_strategies, [], [strategy_dropdown])
    refresh_whatif_btn.click(load_strategies, [], [whatif_strategy])

    simulate_btn.click(
        run_single_simulation,
        [strategy_dropdown, entry_price_input, position_size_input, price_history_input],
        [result_summary, timeline_chart, triggers_table],
    )

    whatif_btn.click(
        run_whatif,
        [whatif_strategy, whatif_entry, whatif_current, whatif_size, whatif_hours],
        [whatif_summary, whatif_scenarios],
    )
