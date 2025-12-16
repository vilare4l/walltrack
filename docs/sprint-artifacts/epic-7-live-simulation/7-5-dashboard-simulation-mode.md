# Story 7.5: Dashboard Simulation Mode

## Story Info
- **Epic**: Epic 7 - Live Simulation (Paper Trading)
- **Status**: ready
- **Priority**: High
- **FR**: FR59

## User Story

**As an** operator,
**I want** a dedicated dashboard view for simulation mode,
**So that** I can monitor simulated trading performance.

## Acceptance Criteria

### AC 1: Mode Banner
**Given** simulation mode is active
**When** dashboard loads
**Then** "SIMULATION MODE" banner is prominently displayed
**And** all metrics are labeled as simulated
**And** simulation-specific tabs are available

### AC 2: Positions View
**Given** simulation dashboard
**When** operator views positions tab
**Then** only simulated positions are shown
**And** real-time P&L for each position is displayed
**And** simulated trade history is accessible

### AC 3: Performance View
**Given** simulation dashboard
**When** operator views performance tab
**Then** simulated win rate is calculated
**And** simulated total P&L is shown
**And** simulated vs actual comparison (if both exist) is available

### AC 4: Signals View
**Given** simulation mode
**When** operator views signals
**Then** signal processing is identical to live
**And** "Would have traded" indicators are shown
**And** simulation decisions are logged

## Technical Specifications

### Simulation Dashboard Component

**src/walltrack/ui/components/simulation_dashboard.py:**
```python
"""Simulation mode dashboard component."""

import gradio as gr
import plotly.graph_objects as go
from datetime import datetime, timedelta

from walltrack.core.simulation.context import is_simulation_mode, get_execution_mode
from walltrack.core.simulation.pnl_calculator import get_pnl_calculator
from walltrack.services.position_service import get_position_service


def create_simulation_banner() -> gr.HTML:
    """Create simulation mode banner."""
    return gr.HTML(
        value="""
        <div style="
            background: linear-gradient(90deg, #ff6b6b, #ffa500);
            color: white;
            padding: 15px;
            text-align: center;
            font-size: 18px;
            font-weight: bold;
            border-radius: 8px;
            margin-bottom: 20px;
        ">
            SIMULATION MODE - Trades are NOT real
        </div>
        """,
        visible=True,
    )


async def get_simulation_positions_data() -> list[dict]:
    """Get simulated positions for display."""
    position_service = await get_position_service()
    pnl_calc = await get_pnl_calculator()

    positions = await position_service.get_active_positions(simulated=True)

    result = []
    for pos in positions:
        pos_with_pnl = await pnl_calc.get_position_with_pnl(pos)
        result.append({
            "Token": pos.token_address[:8] + "...",
            "Entry Price": f"${pos.entry_price:.6f}",
            "Current Price": f"${pos_with_pnl.current_price:.6f}",
            "Amount": f"{pos.amount_tokens:.2f}",
            "Unrealized P&L": f"${pos_with_pnl.unrealized_pnl:.2f}",
            "P&L %": f"{pos_with_pnl.unrealized_pnl_percent:.1f}%",
            "Status": "SIMULATED",
        })

    return result


async def get_simulation_summary() -> dict:
    """Get simulation performance summary."""
    pnl_calc = await get_pnl_calculator()
    portfolio = await pnl_calc.calculate_portfolio_pnl(simulated=True)

    return {
        "total_pnl": float(portfolio.total_pnl),
        "unrealized_pnl": float(portfolio.total_unrealized_pnl),
        "realized_pnl": float(portfolio.total_realized_pnl),
        "position_count": portfolio.position_count,
        "stale_prices": portfolio.positions_with_stale_prices,
    }


def create_pnl_chart(history: list[dict]) -> go.Figure:
    """Create P&L history chart."""
    fig = go.Figure()

    times = [h["recorded_at"] for h in history]
    pnls = [h["total_pnl"] for h in history]

    fig.add_trace(go.Scatter(
        x=times,
        y=pnls,
        mode="lines+markers",
        name="Simulated P&L",
        line=dict(color="#ff6b6b", width=2),
    ))

    fig.update_layout(
        title="Simulation P&L Over Time",
        xaxis_title="Time",
        yaxis_title="P&L (USD)",
        template="plotly_dark",
    )

    return fig


def create_simulation_panel() -> gr.Blocks:
    """Create simulation dashboard panel."""

    with gr.Blocks() as panel:
        # Banner
        create_simulation_banner()

        # Summary metrics
        with gr.Row():
            total_pnl = gr.Number(
                label="Total P&L (Simulated)",
                value=0,
                interactive=False,
            )
            unrealized_pnl = gr.Number(
                label="Unrealized P&L",
                value=0,
                interactive=False,
            )
            realized_pnl = gr.Number(
                label="Realized P&L",
                value=0,
                interactive=False,
            )
            position_count = gr.Number(
                label="Open Positions",
                value=0,
                interactive=False,
            )

        # Tabs
        with gr.Tabs():
            with gr.Tab("Positions"):
                positions_table = gr.Dataframe(
                    headers=["Token", "Entry Price", "Current Price",
                             "Amount", "Unrealized P&L", "P&L %", "Status"],
                    label="Simulated Positions",
                )

            with gr.Tab("Performance"):
                pnl_chart = gr.Plot(label="P&L Chart")

            with gr.Tab("Trade History"):
                trade_history = gr.Dataframe(
                    headers=["Time", "Token", "Side", "Amount",
                             "Price", "P&L", "Status"],
                    label="Simulated Trades",
                )

        # Refresh button
        refresh_btn = gr.Button("Refresh Data", variant="primary")

        async def refresh_all():
            summary = await get_simulation_summary()
            positions = await get_simulation_positions_data()
            return [
                summary["total_pnl"],
                summary["unrealized_pnl"],
                summary["realized_pnl"],
                summary["position_count"],
                positions,
            ]

        refresh_btn.click(
            fn=refresh_all,
            outputs=[total_pnl, unrealized_pnl, realized_pnl,
                     position_count, positions_table],
        )

    return panel
```

### Mode Indicator Component

**src/walltrack/ui/components/mode_indicator.py:**
```python
"""Execution mode indicator for dashboard."""

import gradio as gr

from walltrack.core.simulation.context import get_execution_mode, ExecutionMode


def get_mode_html() -> str:
    """Get HTML for mode indicator."""
    mode = get_execution_mode()

    if mode == ExecutionMode.SIMULATION:
        return """
        <div style="
            display: inline-block;
            background: #ff6b6b;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        ">
            SIMULATION
        </div>
        """
    else:
        return """
        <div style="
            display: inline-block;
            background: #4caf50;
            color: white;
            padding: 5px 15px;
            border-radius: 20px;
            font-weight: bold;
        ">
            LIVE
        </div>
        """


def create_mode_indicator() -> gr.HTML:
    """Create mode indicator component."""
    return gr.HTML(value=get_mode_html())
```

## Implementation Tasks

- [ ] Create simulation_dashboard.py component
- [ ] Create mode_indicator.py component
- [ ] Implement positions table with P&L
- [ ] Implement P&L chart with history
- [ ] Add trade history tab
- [ ] Integrate with main dashboard
- [ ] Add auto-refresh functionality
- [ ] Write component tests

## Definition of Done

- [ ] Simulation banner clearly visible
- [ ] All data labeled as simulated
- [ ] Real-time P&L updates work
- [ ] Charts display correctly
- [ ] Mode indicator shows current mode
- [ ] Dashboard loads in < 2s (NFR3)
