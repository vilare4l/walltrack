"""Positions and trade history dashboard component.

Displays active positions, trade history, and pending signals
in the dashboard UI.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import gradio as gr
import pandas as pd

if TYPE_CHECKING:
    from walltrack.models.position import Position
    from walltrack.services.execution.position_status import PositionMetrics


def format_pnl(pnl_pct: float) -> str:
    """Format PnL percentage for display."""
    sign = "+" if pnl_pct >= 0 else ""
    return f"{sign}{pnl_pct:.1f}%"


def format_time_held(hours: float) -> str:
    """Format time held for display."""
    if hours < 1:
        return f"{int(hours * 60)}m"
    if hours < 24:
        return f"{hours:.1f}h"
    return f"{hours / 24:.1f}d"


def format_position_row(
    position: Position,
    metrics: PositionMetrics,
) -> dict:
    """Format position data for table display."""
    return {
        "id": position.id[:8],
        "Token": position.token_symbol or position.token_address[:8],
        "Entry Price": f"{position.entry_price:.8f}",
        "Current Price": f"{metrics.current_price:.8f}",
        "PnL %": format_pnl(metrics.unrealized_pnl_pct),
        "Multiplier": f"x{metrics.multiplier:.2f}",
        "Time Held": format_time_held(metrics.hours_held),
        "Strategy": position.exit_strategy_id.replace("preset-", ""),
        "Status": "Moonbag" if position.is_moonbag else position.status.value,
    }


def format_position_detail(
    position: Position,
    metrics: PositionMetrics,
) -> str:
    """Format position detail markdown."""
    lines = [
        f"## {position.token_symbol or position.token_address[:12]}",
        f"**Position ID:** `{position.id}`",
        f"**Token Address:** `{position.token_address}`",
        "",
        "### Entry",
        f"- **Price:** {position.entry_price:.8f} SOL",
        f"- **Amount:** {position.entry_amount_tokens:.4f} tokens",
        f"- **Cost:** {position.entry_amount_sol:.4f} SOL",
        f"- **Time:** {position.entry_time.strftime('%Y-%m-%d %H:%M')} UTC",
        "",
        "### Current Status",
        f"- **Current Price:** {metrics.current_price:.8f} SOL",
        f"- **Remaining:** {position.current_amount_tokens:.4f} tokens",
        f"- **Multiplier:** x{metrics.multiplier:.2f}",
        f"- **Time Held:** {format_time_held(metrics.hours_held)}",
        "",
        "### PnL",
        f"- **Unrealized:** {metrics.unrealized_pnl_sol:+.4f} SOL "
        f"({format_pnl(metrics.unrealized_pnl_pct)})",
        f"- **Realized:** {metrics.realized_pnl_sol:+.4f} SOL",
        "",
        "### Exit Strategy",
        f"- **Strategy:** {position.exit_strategy_id}",
    ]

    if metrics.stop_loss_price:
        lines.append(f"- **Stop Loss:** {metrics.stop_loss_price:.8f} SOL")

    if metrics.next_take_profit_price:
        lines.append(f"- **Next TP:** {metrics.next_take_profit_price:.8f} SOL")

    if metrics.trailing_stop_active:
        lines.append(f"- **Trailing Stop:** Active at {metrics.trailing_stop_price:.8f} SOL")

    return "\n".join(lines)


def create_positions_tab() -> None:
    """Create the positions tab UI with active positions and trade history."""
    with gr.Tabs():
        with gr.Tab("Active Positions"):
            _create_active_positions_view()

        with gr.Tab("Trade History"):
            _create_trade_history_view()


def _create_active_positions_view() -> None:
    """Create active positions view."""
    gr.Markdown("### Open Positions")

    with gr.Row():
        refresh_btn = gr.Button("Refresh", size="sm")

    positions_table = gr.Dataframe(
        headers=[
            "Token",
            "Entry Price",
            "Current Price",
            "PnL %",
            "Multiplier",
            "Time Held",
            "Strategy",
            "Status",
        ],
        interactive=False,
        wrap=True,
    )

    gr.Markdown("---")
    gr.Markdown("### Position Detail")

    with gr.Row():
        _position_id_input = gr.Textbox(
            label="Position ID",
            placeholder="Enter position ID to view details",
            scale=3,
        )
        _load_btn = gr.Button("Load", scale=1)

    _position_detail = gr.Markdown("*Select a position to view details*")

    # Note: Actual data loading would be connected here
    # Using placeholder data for UI structure

    def get_sample_positions() -> pd.DataFrame:
        """Return sample positions data for UI display."""
        return pd.DataFrame(
            [
                {
                    "Token": "SAMPLE",
                    "Entry Price": "0.00100000",
                    "Current Price": "0.00150000",
                    "PnL %": "+50.0%",
                    "Multiplier": "x1.50",
                    "Time Held": "5.2h",
                    "Strategy": "balanced",
                    "Status": "open",
                }
            ]
        )

    refresh_btn.click(fn=get_sample_positions, outputs=positions_table)


def _create_trade_history_view() -> None:
    """Create trade history view."""
    gr.Markdown("### Trade History")

    with gr.Row():
        date_from = gr.Textbox(label="From", placeholder="YYYY-MM-DD", scale=1)
        date_to = gr.Textbox(label="To", placeholder="YYYY-MM-DD", scale=1)
        pnl_filter = gr.Dropdown(
            label="PnL Filter",
            choices=["All", "Profitable", "Loss"],
            value="All",
            scale=1,
        )
        search_btn = gr.Button("Search", scale=1)

    history_table = gr.Dataframe(
        headers=[
            "Token",
            "Entry",
            "Exit",
            "PnL %",
            "Duration",
            "Exit Reason",
            "Date",
        ],
        interactive=False,
        wrap=True,
    )

    with gr.Row():
        _page_info = gr.Markdown("Page 1 of 1")

    # Sample history data
    def get_sample_history(
        _date_from: str,
        _date_to: str,
        _pnl_filter: str,
    ) -> pd.DataFrame:
        """Return sample trade history for UI display."""
        return pd.DataFrame(
            [
                {
                    "Token": "EXAMPLE",
                    "Entry": "0.00100000",
                    "Exit": "0.00200000",
                    "PnL %": "+100.0%",
                    "Duration": "2.5h",
                    "Exit Reason": "take_profit",
                    "Date": datetime.now().strftime("%Y-%m-%d"),
                }
            ]
        )

    search_btn.click(
        fn=get_sample_history,
        inputs=[date_from, date_to, pnl_filter],
        outputs=history_table,
    )
