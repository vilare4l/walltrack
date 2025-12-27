"""What-If simulation modal component.

Allows the operator to compare different exit strategies
on a closed position to see which would have performed better.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import gradio as gr
import httpx
import structlog

from walltrack.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

log = structlog.get_logger(__name__)


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    host = settings.host if hasattr(settings, "host") else "localhost"
    port = settings.port if hasattr(settings, "port") else 8000
    return f"http://{host}:{port}"


async def fetch_position(position_id: str) -> dict[str, Any] | None:
    """Fetch position details.

    Args:
        position_id: Position ID

    Returns:
        Position data or None
    """
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/positions/{position_id}",
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
            log.warning("fetch_position_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_position_error", error=str(e))
    return None


async def fetch_strategies() -> list[tuple[str, str]]:
    """Fetch all active strategies for checkboxes.

    Returns:
        List of (display_name, id) tuples
    """
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/exit-strategies",
                params={"status": "active"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                strategies = data.get("strategies", [])
                return [
                    (f"{s['name']} (v{s.get('version', 1)})", s["id"])
                    for s in strategies
                    if s.get("status") == "active"
                ]
            log.warning("fetch_strategies_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_strategies_error", error=str(e))
    return []


async def run_comparison(
    position_id: str,
    strategy_ids: list[str],
) -> dict[str, Any] | None:
    """Run strategy comparison via API.

    Args:
        position_id: Position ID to compare
        strategy_ids: List of strategy IDs to compare

    Returns:
        Comparison result or None
    """
    if not strategy_ids:
        return None

    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/analysis/positions/{position_id}/compare-all",
                timeout=30.0,
            )
            if response.status_code == 200:
                return response.json()
            log.warning("run_comparison_failed", status=response.status_code)
    except Exception as e:
        log.warning("run_comparison_error", error=str(e))
    return None


def format_comparison_result(result: dict[str, Any]) -> str:
    """Format comparison result as markdown table.

    Args:
        result: Comparison result dict

    Returns:
        Markdown table string
    """
    if not result:
        return "No comparison results available."

    rows = result.get("rows", [])
    if not rows:
        return "No strategies to compare."

    md = """
### Strategy Comparison Results

| Strategy | Simulated P&L | Exit Types | Duration |
|----------|--------------|------------|----------|
"""
    for row in rows:
        strategy_name = row.get("strategy_name", "Unknown")
        pnl = row.get("simulated_pnl_pct", 0)
        pnl_str = f"{'🟢' if pnl >= 0 else '🔴'} {pnl:+.2f}%"
        exit_types = ", ".join(row.get("exit_types", []))
        duration = row.get("duration_hours", 0)
        duration_str = f"{duration:.1f}h" if duration else "N/A"

        md += f"| {strategy_name} | {pnl_str} | {exit_types} | {duration_str} |\n"

    # Add best strategy info
    best_name = result.get("best_strategy_name")
    improvement = result.get("best_improvement_pct", 0)
    if best_name:
        md += f"\n**Best Strategy:** {best_name} ({improvement:+.2f}% improvement)"

    return md


def format_position_info(position: dict[str, Any]) -> str:
    """Format position info as markdown.

    Args:
        position: Position data

    Returns:
        Markdown string
    """
    token = position.get("token_symbol") or position.get("token_address", "")[:12]
    entry_price = position.get("entry_price", 0)
    exit_price = position.get("exit_price", 0)
    exit_type = position.get("exit_type", "N/A")
    pnl_pct = position.get("pnl_pct", 0)
    entry_time = (position.get("entry_time") or "N/A")[:16]

    pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

    return f"""
**Token:** {token}...
**Entry:** ${entry_price:.8f} @ {entry_time}
**Exit:** ${exit_price:.8f} ({exit_type})
**Actual P&L:** {pnl_emoji} {pnl_pct:+.2f}%
"""


# Type alias for modal components
WhatIfModalComponents = tuple[
    gr.Column, gr.Markdown, gr.CheckboxGroup, gr.Markdown, gr.Button, gr.Button, gr.State
]


def create_whatif_modal(
    on_set_default: Callable[[str, str], None] | None = None,
) -> WhatIfModalComponents:
    """Create the What-If simulation modal component.

    Args:
        on_set_default: Callback when setting default strategy (strategy_id, tier)

    Returns:
        Tuple of modal UI components
    """
    with gr.Column(visible=False, elem_id="whatif-modal") as modal_container:
        gr.Markdown("## 📊 What-If Simulator", elem_id="whatif-title")

        position_info = gr.Markdown(elem_id="position-info")

        gr.Markdown("### Select Strategies to Compare")

        strategy_checkboxes = gr.CheckboxGroup(
            label="Strategies",
            choices=[],
            interactive=True,
            elem_id="strategy-checkboxes",
        )

        with gr.Row():
            simulate_btn = gr.Button("Simulate", variant="primary", elem_id="simulate-btn")
            close_btn = gr.Button("Close", variant="secondary", elem_id="close-btn")

        gr.Markdown("---")

        result_markdown = gr.Markdown(elem_id="result-markdown")

        # Set as default section
        with gr.Accordion("Set as Default Strategy", open=False, elem_id="default-accordion"):
            best_strategy_text = gr.Markdown(elem_id="best-strategy-text")

            with gr.Row():
                set_standard_btn = gr.Button("Set as Standard Default", size="sm")
                set_high_btn = gr.Button("Set as High Conviction Default", size="sm")

            default_status = gr.Textbox(
                label="Status", interactive=False, visible=True, elem_id="default-status"
            )

        position_id_state = gr.State(None)
        comparison_result_state = gr.State(None)

    # Close handler
    def close_modal() -> tuple:
        return (
            gr.update(visible=False),
            "",
            gr.update(choices=[], value=[]),
            "",
            "",
            "",
            None,
            None,
        )

    close_btn.click(
        close_modal,
        outputs=[
            modal_container,
            position_info,
            strategy_checkboxes,
            result_markdown,
            best_strategy_text,
            default_status,
            position_id_state,
            comparison_result_state,
        ],
    )

    # Simulate handler
    async def on_simulate(
        position_id: str | None, selected_strategies: list[str]
    ) -> tuple[str, str, dict[str, Any] | None]:
        if not position_id:
            return "Select a position first", "", None

        if not selected_strategies:
            return "Select at least one strategy", "", None

        result = await run_comparison(position_id, selected_strategies)
        if not result:
            return "Simulation failed. Please try again.", "", None

        table_md = format_comparison_result(result)

        best_name = result.get("best_strategy_name")
        improvement = result.get("best_improvement_pct", 0)
        best_md = ""
        if best_name:
            best_md = f"**Best Strategy:** {best_name} ({improvement:+.2f}% improvement)"

        return table_md, best_md, result

    simulate_btn.click(
        on_simulate,
        [position_id_state, strategy_checkboxes],
        [result_markdown, best_strategy_text, comparison_result_state],
    )

    # Set as default handlers
    def handle_set_default(result: dict[str, Any] | None, tier: str) -> str:
        if not result:
            return "No comparison result available"

        best_id = result.get("best_strategy_id")
        best_name = result.get("best_strategy_name")

        if not best_id:
            return "No best strategy identified"

        if on_set_default:
            on_set_default(best_id, tier)

        tier_label = "High Conviction" if tier == "high" else "Standard"
        return f"'{best_name}' set as default for {tier_label}"

    set_standard_btn.click(
        lambda r: handle_set_default(r, "standard"),
        [comparison_result_state],
        [default_status],
    )

    set_high_btn.click(
        lambda r: handle_set_default(r, "high"),
        [comparison_result_state],
        [default_status],
    )

    return (
        modal_container,
        position_info,
        strategy_checkboxes,
        result_markdown,
        simulate_btn,
        close_btn,
        position_id_state,
    )


async def open_whatif_modal(
    position_id: str,
) -> tuple[gr.update, str, gr.update, str, str, str, str | None, None]:
    """Open the What-If modal.

    Args:
        position_id: Position ID to simulate

    Returns:
        Tuple of updates for modal components
    """
    if not position_id:
        return (
            gr.update(visible=False),
            "",
            gr.update(choices=[], value=[]),
            "",
            "",
            "",
            None,
            None,
        )

    position = await fetch_position(position_id)
    if not position:
        return (
            gr.update(visible=False),
            "Position not found",
            gr.update(choices=[], value=[]),
            "",
            "",
            "",
            None,
            None,
        )

    if position.get("status") != "closed":
        return (
            gr.update(visible=False),
            "What-If is only available for closed positions",
            gr.update(choices=[], value=[]),
            "",
            "",
            "",
            None,
            None,
        )

    info_md = format_position_info(position)
    strategies = await fetch_strategies()

    # Pre-select first 3 strategies
    pre_selected = [s[1] for s in strategies[:3]]

    return (
        gr.update(visible=True),
        info_md,
        gr.update(choices=strategies, value=pre_selected),
        "",  # result markdown
        "",  # best strategy text
        "",  # default status
        position_id,
        None,  # comparison result
    )
