"""Enhanced positions list with contextual actions.

Displays active and closed positions with action buttons for
Details, Strategy change, and What-If simulation.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

log = structlog.get_logger(__name__)

# Type alias for tab UI elements tuple
TabElements = tuple[gr.Dataframe, gr.Button, gr.Button, gr.Button, gr.State, gr.Textbox]

# Exit type emoji mapping
EXIT_TYPE_EMOJI: dict[str, str] = {
    "take_profit": "🎯",
    "stop_loss": "🛑",
    "trailing_stop": "📉",
    "time_based": "⏰",
    "manual": "✋",
    "stagnation": "😴",
}


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    host = settings.host if hasattr(settings, "host") else "localhost"
    port = settings.port if hasattr(settings, "port") else 8000
    return f"http://{host}:{port}"


def format_pnl_colored(pnl_pct: float) -> str:
    """Format P&L with color indicator emoji."""
    if pnl_pct > 0:
        return f"🟢 +{pnl_pct:.2f}%"
    elif pnl_pct < 0:
        return f"🔴 {pnl_pct:.2f}%"
    return f"⚪ {pnl_pct:.2f}%"


def format_duration(entry_time: str | None) -> str:
    """Format duration since entry time."""
    if not entry_time:
        return "-"

    try:
        entry = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        delta = now - entry

        hours = delta.total_seconds() / 3600

        if hours < 1:
            return f"{int(delta.total_seconds() / 60)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        return f"{hours / 24:.1f}d"
    except Exception:
        return "-"


def format_exit_type(exit_type: str | None) -> str:
    """Format exit type with emoji."""
    if not exit_type:
        return "❓ unknown"
    emoji = EXIT_TYPE_EMOJI.get(exit_type, "❓")
    return f"{emoji} {exit_type}"


async def fetch_active_positions() -> list[dict[str, Any]]:
    """Fetch active positions from API."""
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/positions",
                params={"status": "open", "limit": 50},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("positions", [])
            log.warning("fetch_active_positions_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_active_positions_error", error=str(e))
    return []


async def fetch_closed_positions(limit: int = 10) -> list[dict[str, Any]]:
    """Fetch recently closed positions from API."""
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/positions",
                params={"status": "closed", "limit": limit},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("positions", [])
            log.warning("fetch_closed_positions_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_closed_positions_error", error=str(e))
    return []


def format_active_positions(positions: list[dict[str, Any]]) -> pd.DataFrame:
    """Format active positions for dataframe display."""
    if not positions:
        return pd.DataFrame(
            columns=["ID", "Token", "Entry", "Current", "P&L", "Size", "Strategy", "Duration"]
        )

    rows = []
    for p in positions:
        strategy_name = "None"
        if p.get("exit_strategies"):
            strategy_name = p["exit_strategies"].get("name", "None")
        elif p.get("exit_strategy_id"):
            strategy_name = p["exit_strategy_id"][:12]

        rows.append({
            "ID": p.get("id", "")[:8] + "...",
            "Token": p.get("token_symbol") or (p.get("token_address", "")[:8] + "..."),
            "Entry": f"${p.get('entry_price', 0):.8f}",
            "Current": f"${p.get('current_price', p.get('entry_price', 0)):.8f}",
            "P&L": format_pnl_colored(float(p.get("pnl_pct", 0))),
            "Size": f"{p.get('size_sol', 0):.4f} SOL",
            "Strategy": strategy_name,
            "Duration": format_duration(p.get("entry_time")),
            "_full_id": p.get("id", ""),  # Hidden for selection
        })

    return pd.DataFrame(rows)


def format_closed_positions(positions: list[dict[str, Any]]) -> pd.DataFrame:
    """Format closed positions for dataframe display."""
    if not positions:
        return pd.DataFrame(
            columns=["ID", "Token", "Entry", "Exit", "P&L", "Exit Type", "Strategy", "Date"]
        )

    rows = []
    for p in positions:
        strategy_name = "None"
        if p.get("exit_strategies"):
            strategy_name = p["exit_strategies"].get("name", "None")
        elif p.get("exit_strategy_id"):
            strategy_name = p["exit_strategy_id"][:12]

        exit_time = p.get("exit_time", "")
        date_str = exit_time[:10] if exit_time else ""

        rows.append({
            "ID": p.get("id", "")[:8] + "...",
            "Token": p.get("token_symbol") or (p.get("token_address", "")[:8] + "..."),
            "Entry": f"${p.get('entry_price', 0):.8f}",
            "Exit": f"${p.get('exit_price', 0):.8f}",
            "P&L": format_pnl_colored(float(p.get("pnl_pct", 0))),
            "Exit Type": format_exit_type(p.get("exit_type")),
            "Strategy": strategy_name,
            "Date": date_str,
            "_full_id": p.get("id", ""),  # Hidden for selection
        })

    return pd.DataFrame(rows)


async def _load_active_positions() -> pd.DataFrame:
    """Load and format active positions."""
    positions = await fetch_active_positions()
    return format_active_positions(positions)


async def _load_closed_positions() -> pd.DataFrame:
    """Load and format closed positions."""
    positions = await fetch_closed_positions()
    return format_closed_positions(positions)


def _handle_row_select(
    evt: gr.SelectData, table_data: pd.DataFrame, status: str
) -> tuple[str | None, dict[str, Any]]:
    """Handle position row selection."""
    if evt.index[0] < len(table_data):
        row = table_data.iloc[evt.index[0]]
        full_id = row.get("_full_id", row.get("ID", "").replace("...", ""))
        return full_id, {"type": "position", "id": full_id, "status": status}
    return None, {"type": None, "data": None}


def _make_action_handler(
    action_name: str, callback: Callable[[str], None] | None
) -> Callable[[str | None], str]:
    """Create an action button handler."""
    def handler(position_id: str | None) -> str:
        if not position_id:
            return "Select a position first"
        if callback:
            callback(position_id)
        return f"{action_name} for {position_id[:8]}..."
    return handler


def _create_active_tab() -> TabElements:
    """Create active positions tab UI elements."""
    active_table = gr.Dataframe(
        headers=["ID", "Token", "Entry", "Current", "P&L", "Size", "Strategy", "Duration"],
        datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
        label="Active Positions",
        interactive=False,
        wrap=True,
        elem_id="active-positions-table",
    )
    with gr.Row():
        view_btn = gr.Button("👁️ Details", size="sm", elem_id="view-active-btn")
        strategy_btn = gr.Button("⚙️ Strategy", size="sm", elem_id="change-strategy-btn")
        refresh_btn = gr.Button("🔄 Refresh", size="sm", elem_id="refresh-active-btn")
    selected_id = gr.State(None)
    status_msg = gr.Textbox(label="Status", interactive=False, visible=False)
    return active_table, view_btn, strategy_btn, refresh_btn, selected_id, status_msg


def _create_closed_tab() -> TabElements:
    """Create closed positions tab UI elements."""
    closed_table = gr.Dataframe(
        headers=["ID", "Token", "Entry", "Exit", "P&L", "Exit Type", "Strategy", "Date"],
        datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
        label="Closed Positions",
        interactive=False,
        wrap=True,
        elem_id="closed-positions-table",
    )
    with gr.Row():
        view_btn = gr.Button("👁️ Details", size="sm", elem_id="view-closed-btn")
        whatif_btn = gr.Button("📊 What-If", size="sm", elem_id="whatif-btn")
        refresh_btn = gr.Button("🔄 Refresh", size="sm", elem_id="refresh-closed-btn")
    selected_id = gr.State(None)
    status_msg = gr.Textbox(label="Status", interactive=False, visible=False)
    return closed_table, view_btn, whatif_btn, refresh_btn, selected_id, status_msg


def create_positions_list(
    sidebar_state: gr.State,
    on_view_details: Callable[[str], None] | None = None,
    on_change_strategy: Callable[[str], None] | None = None,
    on_whatif: Callable[[str], None] | None = None,
) -> tuple[gr.Dataframe, gr.Dataframe, gr.State, gr.State]:
    """Create the enhanced positions list UI component.

    Args:
        sidebar_state: Shared state for sidebar context
        on_view_details: Callback when Details button clicked
        on_change_strategy: Callback when Strategy button clicked
        on_whatif: Callback when What-If button clicked

    Returns:
        Tuple of (active_table, closed_table, selected_active_id, selected_closed_id)
    """
    gr.Markdown("## Positions")

    with gr.Tabs():
        with gr.Tab("Active"):
            active_table, view_active, strategy_btn, refresh_active, sel_active, status_active = (
                _create_active_tab()
            )

        with gr.Tab("Closed (Recent)"):
            closed_table, view_closed, whatif_btn, refresh_closed, sel_closed, status_closed = (
                _create_closed_tab()
            )

    # Create action handlers
    view_handler = _make_action_handler("Viewing details", on_view_details)
    strategy_handler = _make_action_handler("Opening strategy selector", on_change_strategy)
    whatif_handler = _make_action_handler("Opening What-If simulator", on_whatif)

    # Wire selection events
    active_table.select(
        lambda e, t: _handle_row_select(e, t, "open"),
        [active_table], [sel_active, sidebar_state]
    )
    closed_table.select(
        lambda e, t: _handle_row_select(e, t, "closed"),
        [closed_table], [sel_closed, sidebar_state]
    )

    # Wire button events
    refresh_active.click(_load_active_positions, outputs=[active_table])
    refresh_closed.click(_load_closed_positions, outputs=[closed_table])
    view_active.click(view_handler, [sel_active], [status_active])
    view_closed.click(view_handler, [sel_closed], [status_closed])
    strategy_btn.click(strategy_handler, [sel_active], [status_active])
    whatif_btn.click(whatif_handler, [sel_closed], [status_closed])

    return active_table, closed_table, sel_active, sel_closed


async def load_positions_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load both active and closed positions data.

    Returns:
        Tuple of (active_positions_df, closed_positions_df)
    """
    active = await fetch_active_positions()
    closed = await fetch_closed_positions()

    return format_active_positions(active), format_closed_positions(closed)
