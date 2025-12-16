# Story 8.7: Dashboard Backtest Multi-Scenarios

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: Medium
- **FR**: FR67

## User Story

**As an** operator,
**I want** a dashboard interface for backtest scenario management,
**So that** I can easily run and compare backtests.

## Acceptance Criteria

### AC 1: Dashboard Layout
**Given** dashboard backtest tab
**When** operator navigates to it
**Then** three sub-tabs are available:
  - Scenarios (create/edit/manage)
  - Run Backtest (single or batch)
  - Results & Comparison

### AC 2: Scenarios Tab
**Given** Scenarios tab
**When** operator views
**Then** list of saved scenarios is shown
**And** create new scenario button is available
**And** edit/delete/duplicate actions are available

### AC 3: Run Backtest Tab
**Given** Run Backtest tab
**When** operator configures run
**Then** date range selector is available
**And** scenario multi-select is available
**And** optimization toggle with parameter ranges is available
**And** "Start Backtest" button launches execution

### AC 4: Progress Display
**Given** backtest is running
**When** progress is displayed
**Then** real-time progress bar shows completion
**And** live results preview as scenarios complete
**And** cancel button is available

### AC 5: Results Tab
**Given** Results tab
**When** completed backtests exist
**Then** list of past batches is shown
**And** selecting a batch shows comparison view
**And** export to CSV/PDF is available

### AC 6: Apply Settings
**Given** comparison view in dashboard
**When** results are displayed
**Then** sortable comparison table is shown
**And** charts visualize key metrics
**And** "Apply Best Settings" action is available

## Technical Specifications

### Backtest Dashboard Component

**src/walltrack/ui/components/backtest_dashboard.py:**
```python
"""Backtest dashboard component for Gradio."""

from datetime import datetime, timedelta
from typing import Optional

import gradio as gr
import plotly.graph_objects as go
import plotly.express as px

from walltrack.core.backtest.batch import BatchRun, BatchStatus
from walltrack.core.backtest.batch_runner import get_batch_runner
from walltrack.core.backtest.comparison_service import get_comparison_service
from walltrack.core.backtest.scenario import Scenario, ScenarioCategory, PRESET_SCENARIOS
from walltrack.core.backtest.scenario_service import get_scenario_service


async def get_all_scenarios() -> list[dict]:
    """Get all scenarios for display."""
    service = await get_scenario_service()
    scenarios = await service.get_all_scenarios()

    return [
        {
            "ID": str(s.id)[:8],
            "Name": s.name,
            "Category": s.category.value,
            "Threshold": float(s.score_threshold),
            "Position Size": float(s.base_position_sol),
            "Stop Loss": f"{float(s.exit_strategy.stop_loss_pct) * 100:.0f}%",
            "Preset": "Yes" if s.is_preset else "No",
        }
        for s in scenarios
    ]


async def get_batch_history() -> list[dict]:
    """Get recent batch runs."""
    runner = await get_batch_runner()
    batches = await runner.list_batches(limit=20)

    return [
        {
            "ID": str(b.id)[:8],
            "Name": b.name,
            "Scenarios": len(b.scenario_ids),
            "Status": b.status.value,
            "Date Range": f"{b.start_date.date()} - {b.end_date.date()}",
            "Created": b.created_at.strftime("%Y-%m-%d %H:%M"),
        }
        for b in batches
    ]


def create_comparison_chart(results: list[dict]) -> go.Figure:
    """Create comparison bar chart."""
    if not results:
        return go.Figure()

    fig = go.Figure()

    names = [r["name"] for r in results]
    pnls = [r["total_pnl"] for r in results]
    win_rates = [r["win_rate"] * 100 for r in results]

    fig.add_trace(go.Bar(
        name="Total P&L",
        x=names,
        y=pnls,
        marker_color="rgb(55, 83, 109)",
    ))

    fig.add_trace(go.Bar(
        name="Win Rate %",
        x=names,
        y=win_rates,
        marker_color="rgb(26, 118, 255)",
        yaxis="y2",
    ))

    fig.update_layout(
        title="Scenario Comparison",
        xaxis_title="Scenario",
        yaxis=dict(title="P&L ($)"),
        yaxis2=dict(title="Win Rate %", overlaying="y", side="right"),
        barmode="group",
        template="plotly_dark",
    )

    return fig


def create_equity_chart(equity_curves: dict[str, list]) -> go.Figure:
    """Create equity curve comparison chart."""
    fig = go.Figure()

    colors = px.colors.qualitative.Plotly

    for i, (name, curve) in enumerate(equity_curves.items()):
        times = [c["timestamp"] for c in curve]
        values = [c["equity"] for c in curve]

        fig.add_trace(go.Scatter(
            x=times,
            y=values,
            mode="lines",
            name=name,
            line=dict(color=colors[i % len(colors)]),
        ))

    fig.update_layout(
        title="Equity Curves",
        xaxis_title="Time",
        yaxis_title="Equity",
        template="plotly_dark",
    )

    return fig


def create_backtest_panel() -> gr.Blocks:
    """Create the backtest dashboard panel."""

    with gr.Blocks() as panel:
        gr.Markdown("# Backtest & Scenario Analysis")

        with gr.Tabs():
            # Scenarios Tab
            with gr.Tab("Scenarios"):
                gr.Markdown("### Manage Backtest Scenarios")

                scenarios_table = gr.Dataframe(
                    headers=["ID", "Name", "Category", "Threshold",
                             "Position Size", "Stop Loss", "Preset"],
                    label="Saved Scenarios",
                    interactive=False,
                )

                with gr.Row():
                    refresh_scenarios = gr.Button("Refresh", size="sm")
                    create_scenario = gr.Button("Create New", variant="primary")
                    duplicate_btn = gr.Button("Duplicate Selected")
                    delete_btn = gr.Button("Delete", variant="stop")

                # Create/Edit Form
                with gr.Accordion("Scenario Configuration", open=False):
                    scenario_name = gr.Textbox(label="Name")
                    scenario_desc = gr.Textbox(label="Description", lines=2)
                    scenario_category = gr.Dropdown(
                        choices=[c.value for c in ScenarioCategory],
                        value="custom",
                        label="Category",
                    )

                    gr.Markdown("**Scoring Parameters**")
                    with gr.Row():
                        score_threshold = gr.Slider(
                            0.5, 0.95, value=0.70, step=0.05,
                            label="Score Threshold",
                        )
                        wallet_weight = gr.Slider(
                            0, 0.5, value=0.30, step=0.05,
                            label="Wallet Weight",
                        )
                        cluster_weight = gr.Slider(
                            0, 0.5, value=0.25, step=0.05,
                            label="Cluster Weight",
                        )

                    gr.Markdown("**Position Sizing**")
                    with gr.Row():
                        base_position = gr.Slider(
                            0.01, 0.5, value=0.1, step=0.01,
                            label="Base Position (SOL)",
                        )
                        high_conv_mult = gr.Slider(
                            1.0, 3.0, value=1.5, step=0.1,
                            label="High Conviction Multiplier",
                        )

                    gr.Markdown("**Exit Strategy**")
                    with gr.Row():
                        stop_loss = gr.Slider(
                            0.1, 0.8, value=0.5, step=0.05,
                            label="Stop Loss %",
                        )
                        moonbag = gr.Slider(
                            0, 0.8, value=0.34, step=0.01,
                            label="Moonbag %",
                        )

                    save_scenario = gr.Button("Save Scenario", variant="primary")

                async def load_scenarios():
                    return await get_all_scenarios()

                refresh_scenarios.click(fn=load_scenarios, outputs=[scenarios_table])

            # Run Backtest Tab
            with gr.Tab("Run Backtest"):
                gr.Markdown("### Configure and Run Backtests")

                with gr.Row():
                    start_date = gr.Textbox(
                        label="Start Date",
                        value=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
                    )
                    end_date = gr.Textbox(
                        label="End Date",
                        value=datetime.now().strftime("%Y-%m-%d"),
                    )

                scenario_select = gr.CheckboxGroup(
                    choices=[],
                    label="Select Scenarios to Run",
                )

                with gr.Accordion("Optimization Settings", open=False):
                    enable_optimization = gr.Checkbox(
                        label="Enable Parameter Optimization",
                        value=False,
                    )
                    opt_objective = gr.Dropdown(
                        choices=["total_pnl", "win_rate", "profit_factor", "sharpe_ratio"],
                        value="total_pnl",
                        label="Optimization Objective",
                    )
                    gr.Markdown("**Parameter Ranges (comma-separated)**")
                    with gr.Row():
                        threshold_range = gr.Textbox(
                            label="Threshold Range",
                            value="0.65, 0.70, 0.75, 0.80",
                        )
                        position_range = gr.Textbox(
                            label="Position Size Range",
                            value="0.1, 0.15, 0.2",
                        )

                with gr.Row():
                    run_backtest = gr.Button("Start Backtest", variant="primary")
                    cancel_backtest = gr.Button("Cancel", variant="stop")

                # Progress
                progress_bar = gr.Slider(
                    0, 100, value=0, label="Progress", interactive=False
                )
                progress_text = gr.Textbox(
                    label="Status", value="Ready", interactive=False
                )

                # Live results preview
                live_results = gr.Dataframe(
                    headers=["Scenario", "Status", "P&L", "Win Rate", "Trades"],
                    label="Results Preview",
                )

            # Results Tab
            with gr.Tab("Results & Comparison"):
                gr.Markdown("### Backtest Results")

                batch_history = gr.Dataframe(
                    headers=["ID", "Name", "Scenarios", "Status", "Date Range", "Created"],
                    label="Recent Batches",
                    interactive=False,
                )

                refresh_history = gr.Button("Refresh", size="sm")

                gr.Markdown("### Comparison View")

                with gr.Row():
                    comparison_chart = gr.Plot(label="Metrics Comparison")
                    equity_chart = gr.Plot(label="Equity Curves")

                comparison_table = gr.Dataframe(
                    headers=["Scenario", "Total P&L", "Win Rate", "Trades",
                             "Max DD", "Profit Factor", "Rank"],
                    label="Detailed Comparison",
                )

                with gr.Row():
                    export_csv = gr.Button("Export CSV")
                    apply_best = gr.Button("Apply Best Settings", variant="primary")

                async def load_history():
                    return await get_batch_history()

                refresh_history.click(fn=load_history, outputs=[batch_history])

        # Load initial data
        panel.load(fn=load_scenarios, outputs=[scenarios_table])
        panel.load(fn=load_history, outputs=[batch_history])

    return panel
```

### Main Dashboard Integration

**src/walltrack/ui/dashboard.py (addition):**
```python
"""Main dashboard with backtest integration."""

import gradio as gr

from walltrack.ui.components.backtest_dashboard import create_backtest_panel


def create_dashboard() -> gr.Blocks:
    """Create the main dashboard."""
    with gr.Blocks(title="WallTrack Dashboard") as dashboard:
        gr.Markdown("# WallTrack Trading Dashboard")

        with gr.Tabs():
            # ... existing tabs ...

            with gr.Tab("Backtest"):
                create_backtest_panel()

    return dashboard
```

## Scenario Form Handler

**src/walltrack/ui/handlers/backtest_handlers.py:**
```python
"""Handlers for backtest dashboard interactions."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from walltrack.core.backtest.batch_runner import get_batch_runner
from walltrack.core.backtest.comparison_service import get_comparison_service
from walltrack.core.backtest.parameters import ScoringWeights, ExitStrategyParams
from walltrack.core.backtest.scenario import Scenario, ScenarioCategory
from walltrack.core.backtest.scenario_service import get_scenario_service


async def save_scenario_handler(
    name: str,
    description: str,
    category: str,
    score_threshold: float,
    wallet_weight: float,
    cluster_weight: float,
    base_position: float,
    high_conv_mult: float,
    stop_loss: float,
    moonbag: float,
) -> str:
    """Handle saving a scenario."""
    try:
        # Calculate remaining weights (simplified)
        token_weight = (1.0 - wallet_weight - cluster_weight) / 2
        context_weight = token_weight

        scenario = Scenario(
            name=name,
            description=description,
            category=ScenarioCategory(category),
            scoring_weights=ScoringWeights(
                wallet_weight=Decimal(str(wallet_weight)),
                cluster_weight=Decimal(str(cluster_weight)),
                token_weight=Decimal(str(token_weight)),
                context_weight=Decimal(str(context_weight)),
            ),
            score_threshold=Decimal(str(score_threshold)),
            base_position_sol=Decimal(str(base_position)),
            high_conviction_multiplier=Decimal(str(high_conv_mult)),
            exit_strategy=ExitStrategyParams(
                stop_loss_pct=Decimal(str(stop_loss)),
                moonbag_pct=Decimal(str(moonbag)),
            ),
        )

        service = await get_scenario_service()
        await service.create_scenario(scenario)

        return f"Scenario '{name}' saved successfully!"
    except Exception as e:
        return f"Error saving scenario: {str(e)}"


async def run_batch_handler(
    start_date: str,
    end_date: str,
    selected_scenarios: list[str],
    batch_name: Optional[str] = None,
) -> tuple[int, str, list]:
    """Handle running a batch backtest."""
    try:
        start = datetime.fromisoformat(start_date)
        end = datetime.fromisoformat(end_date)

        # Get scenario IDs from names
        service = await get_scenario_service()
        all_scenarios = await service.get_all_scenarios()
        scenario_ids = [
            s.id for s in all_scenarios
            if s.name in selected_scenarios
        ]

        if not scenario_ids:
            return 0, "No scenarios selected", []

        runner = await get_batch_runner()

        def progress_callback(progress):
            # Would need websocket for real-time updates
            pass

        batch = await runner.start_batch(
            name=batch_name or f"Batch {datetime.now().strftime('%Y%m%d_%H%M')}",
            scenario_ids=scenario_ids,
            start_date=start,
            end_date=end,
            on_progress=progress_callback,
        )

        return 0, f"Batch {batch.id} started", []

    except Exception as e:
        return 0, f"Error: {str(e)}", []


async def load_comparison_handler(batch_id: str) -> tuple:
    """Load comparison data for a batch."""
    try:
        runner = await get_batch_runner()
        batch = await runner.get_batch(UUID(batch_id))

        if not batch:
            return None, None, []

        results = batch.get_successful_results()
        if len(results) < 2:
            return None, None, []

        # Compare scenarios
        comparison_service = get_comparison_service()
        comparison = comparison_service.compare_scenarios(results)

        # Build data for display
        table_data = [
            {
                "Scenario": s.scenario_name,
                "Total P&L": float(s.metrics.total_pnl),
                "Win Rate": float(s.metrics.win_rate),
                "Trades": s.metrics.total_trades,
                "Max DD": float(s.metrics.max_drawdown_pct),
                "Profit Factor": float(s.metrics.profit_factor),
                "Rank": s.overall_rank,
            }
            for s in comparison.scenarios
        ]

        # Build charts
        from walltrack.ui.components.backtest_dashboard import (
            create_comparison_chart,
            create_equity_chart,
        )

        chart_data = [
            {
                "name": s.scenario_name,
                "total_pnl": float(s.metrics.total_pnl),
                "win_rate": float(s.metrics.win_rate),
            }
            for s in comparison.scenarios
        ]

        comparison_fig = create_comparison_chart(chart_data)

        equity_curves = {
            r.name: r.equity_curve
            for r in results
        }
        equity_fig = create_equity_chart(equity_curves)

        return comparison_fig, equity_fig, table_data

    except Exception as e:
        print(f"Error loading comparison: {e}")
        return None, None, []


async def apply_best_settings_handler(batch_id: str) -> str:
    """Apply the best performing scenario settings to live config."""
    try:
        runner = await get_batch_runner()
        batch = await runner.get_batch(UUID(batch_id))

        if not batch:
            return "Batch not found"

        results = batch.get_successful_results()
        if not results:
            return "No successful results found"

        # Compare and get best
        comparison_service = get_comparison_service()
        comparison = comparison_service.compare_scenarios(results)

        best_id = comparison.best_scenario_id
        scenario_service = await get_scenario_service()
        best_scenario = await scenario_service.get_scenario(best_id)

        if not best_scenario:
            return "Best scenario not found"

        # Would update live config here
        return f"Settings from '{best_scenario.name}' ready to apply. Confirm in Settings tab."

    except Exception as e:
        return f"Error: {str(e)}"
```

## Implementation Tasks

- [ ] Create backtest_dashboard.py component
- [ ] Implement scenarios table and form
- [ ] Implement batch run interface
- [ ] Implement progress display
- [ ] Implement comparison charts
- [ ] Implement results table
- [ ] Add export functionality
- [ ] Add apply settings functionality
- [ ] Integrate with main dashboard
- [ ] Write component tests

## Definition of Done

- [ ] All three tabs are functional
- [ ] Scenarios can be created and managed
- [ ] Batch backtests can be started
- [ ] Progress displays in real-time
- [ ] Comparison charts render correctly
- [ ] Export produces valid CSV
- [ ] Apply settings workflow works
- [ ] Dashboard loads in < 2s (NFR3)
