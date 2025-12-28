"""Strategy change modal for active positions.

Allows the operator to change the exit strategy of an active position,
with a preview of the new levels before applying.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any

import gradio as gr
import httpx
import structlog

from walltrack.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

log = structlog.get_logger(__name__)

# Type alias for modal component return tuple
ModalComponents = tuple[
    gr.Column, gr.Markdown, gr.Dropdown, gr.Markdown, gr.Button, gr.Button, gr.Textbox, gr.State
]


def _get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    host = settings.host if hasattr(settings, "host") else "localhost"
    port = settings.port if hasattr(settings, "port") else 8000
    return f"http://{host}:{port}"


async def fetch_strategies() -> list[tuple[str, str]]:
    """Fetch all active strategies for dropdown.

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


async def fetch_strategy(strategy_id: str) -> dict[str, Any] | None:
    """Fetch strategy details.

    Args:
        strategy_id: Strategy ID

    Returns:
        Strategy data or None
    """
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/exit-strategies/{strategy_id}",
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
            log.warning("fetch_strategy_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_strategy_error", error=str(e))
    return None


async def apply_strategy_change(position_id: str, new_strategy_id: str) -> tuple[bool, str]:
    """Apply strategy change to position.

    Args:
        position_id: Position ID
        new_strategy_id: New strategy ID

    Returns:
        Tuple of (success, message)
    """
    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.patch(
                f"{base_url}/api/positions/{position_id}/strategy",
                json={"strategy_id": new_strategy_id},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                return True, data.get("message", "Strategy changed successfully")
            log.warning("apply_strategy_change_failed", status=response.status_code)
            error = response.json().get("detail", "Failed to change strategy")
            return False, error
    except Exception as e:
        log.warning("apply_strategy_change_error", error=str(e))
        return False, f"Error: {e}"


def calculate_preview(
    strategy: dict[str, Any],
    entry_price: Decimal,
    executed_exits: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Calculate preview of strategy levels.

    Args:
        strategy: Strategy data
        entry_price: Position entry price
        executed_exits: List of already executed exits

    Returns:
        Dict with strategy name and levels
    """
    executed_exits = executed_exits or []

    # Get already executed exit types
    executed_types = set()
    for ex in executed_exits:
        key = f"{ex.get('exit_type')}_{ex.get('trigger_pct')}"
        executed_types.add(key)

    preview: dict[str, Any] = {
        "strategy_name": strategy.get("name", "Unknown"),
        "levels": [],
    }

    rules = strategy.get("rules", [])
    for rule in rules:
        if not rule.get("enabled", True):
            continue

        rule_type = rule.get("rule_type", "unknown")
        trigger_pct = rule.get("trigger_pct")

        # Calculate absolute price
        if trigger_pct is not None:
            abs_price = entry_price * (1 + Decimal(str(trigger_pct)) / 100)
        else:
            abs_price = None

        # Check if already executed
        key = f"{rule_type}_{trigger_pct}"
        already_executed = key in executed_types

        preview["levels"].append({
            "type": rule_type,
            "trigger_pct": trigger_pct,
            "exit_pct": rule.get("exit_pct", 100),
            "absolute_price": abs_price,
            "already_executed": already_executed,
        })

    return preview


def format_preview_markdown(preview: dict[str, Any], entry_price: Decimal) -> str:
    """Format preview as markdown table.

    Args:
        preview: Preview data
        entry_price: Entry price for reference

    Returns:
        Markdown string
    """
    md = f"""
### Preview: {preview['strategy_name']}

Entry Price: ${entry_price:.8f}

| Type | Trigger | Exit % | Price | Status |
|------|---------|--------|-------|--------|
"""
    for level in preview.get("levels", []):
        status = "✅ Executed" if level.get("already_executed") else "⏳ Pending"
        trigger_pct = level.get("trigger_pct")
        trigger = f"{trigger_pct:+}%" if trigger_pct is not None else "-"
        abs_price = level.get("absolute_price")
        price = f"${abs_price:.8f}" if abs_price else "-"

        level_type = level.get("type", "?")
        exit_pct = level.get("exit_pct", 100)
        md += f"| {level_type} | {trigger} | {exit_pct}% | {price} | {status} |\n"

    return md


def create_change_strategy_modal(
    on_strategy_changed: Callable[[str, str], None] | None = None,
) -> ModalComponents:
    """Create the change strategy modal component.

    Args:
        on_strategy_changed: Callback when strategy is changed (position_id, new_strategy_id)

    Returns:
        Tuple of modal UI components
    """
    with gr.Column(visible=False, elem_id="change-strategy-modal") as modal_container:
        gr.Markdown("## Change Exit Strategy", elem_id="modal-title")

        current_strategy_text = gr.Markdown(elem_id="current-strategy-text")

        strategy_dropdown = gr.Dropdown(
            label="Select New Strategy",
            choices=[],
            interactive=True,
            elem_id="strategy-dropdown",
        )

        preview_content = gr.Markdown(elem_id="preview-content")

        with gr.Row():
            cancel_btn = gr.Button("Cancel", variant="secondary", elem_id="cancel-btn")
            confirm_btn = gr.Button("Confirm Change", variant="primary", elem_id="confirm-btn")

        status_msg = gr.Textbox(
            label="Status", interactive=False, visible=True, elem_id="status-msg"
        )

        position_id_state = gr.State(None)
        entry_price_state = gr.State(None)

    # Close handler
    def close_modal() -> tuple:
        return (
            gr.update(visible=False),
            "",
            gr.update(choices=[], value=None),
            "",
            "",
            None,
            None,
        )

    cancel_btn.click(
        close_modal,
        outputs=[
            modal_container,
            current_strategy_text,
            strategy_dropdown,
            preview_content,
            status_msg,
            position_id_state,
            entry_price_state,
        ],
    )

    # Strategy selection handler
    async def on_strategy_select(
        strategy_value: str | None, position_id: str | None, entry_price: str | None
    ) -> str:
        if not strategy_value or not position_id or not entry_price:
            return ""

        # Extract strategy_id from dropdown value (format: "name (vX)", id)
        strategy_id = strategy_value

        strategy = await fetch_strategy(strategy_id)
        if not strategy:
            return "Strategy not found"

        position = await fetch_position(position_id)
        executed_exits = position.get("position_exits", []) if position else []

        preview = calculate_preview(
            strategy,
            Decimal(entry_price),
            executed_exits,
        )
        return format_preview_markdown(preview, Decimal(entry_price))

    strategy_dropdown.change(
        on_strategy_select,
        [strategy_dropdown, position_id_state, entry_price_state],
        [preview_content],
    )

    # Confirm handler
    async def on_confirm(
        strategy_value: str | None, position_id: str | None
    ) -> str:
        if not strategy_value or not position_id:
            return "Select a strategy first"

        strategy_id = strategy_value

        success, msg = await apply_strategy_change(position_id, strategy_id)

        if success and on_strategy_changed:
            on_strategy_changed(position_id, strategy_id)

        return msg

    confirm_btn.click(
        on_confirm,
        [strategy_dropdown, position_id_state],
        [status_msg],
    )

    return (
        modal_container,
        current_strategy_text,
        strategy_dropdown,
        preview_content,
        cancel_btn,
        confirm_btn,
        status_msg,
        position_id_state,
    )


async def open_modal(
    position_id: str,
) -> tuple[gr.update, str, gr.update, str, str, str | None, str | None]:
    """Open the change strategy modal.

    Args:
        position_id: Position ID to change strategy for

    Returns:
        Tuple of updates for modal components
    """
    if not position_id:
        return (
            gr.update(visible=False),
            "",
            gr.update(choices=[], value=None),
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
            gr.update(choices=[], value=None),
            "",
            "",
            None,
            None,
        )

    if position.get("status") != "open":
        return (
            gr.update(visible=False),
            "Cannot change strategy for closed position",
            gr.update(choices=[], value=None),
            "",
            "",
            None,
            None,
        )

    current_strategy = position.get("exit_strategies") or {}
    current_text = f"**Current Strategy:** {current_strategy.get('name', 'None')}"

    strategies = await fetch_strategies()

    entry_price = str(position.get("entry_price", 0))

    return (
        gr.update(visible=True),
        current_text,
        gr.update(choices=strategies, value=None),
        "",
        "",
        position_id,
        entry_price,
    )
