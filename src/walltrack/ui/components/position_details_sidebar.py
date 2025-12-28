"""Position details sidebar component.

Displays detailed information about a position in the sidebar,
including performance metrics, strategy details, and source info.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import gradio as gr
import httpx
import structlog

from walltrack.config.settings import get_settings

if TYPE_CHECKING:
    from collections.abc import Callable

log = structlog.get_logger(__name__)

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


async def fetch_position_details(position_id: str) -> dict[str, Any] | None:
    """Fetch full position details from API.

    Args:
        position_id: Position ID (can be truncated with ...)

    Returns:
        Position data dict or None if not found
    """
    # Handle truncated IDs
    if position_id.endswith("..."):
        position_id = position_id.replace("...", "")

    try:
        base_url = _get_api_base_url()
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{base_url}/api/positions/{position_id}",
                timeout=10.0,
            )
            if response.status_code == 200:
                return response.json()
            log.warning("fetch_position_details_failed", status=response.status_code)
    except Exception as e:
        log.warning("fetch_position_details_error", error=str(e))
    return None


def _calculate_next_tp(rules: list[dict[str, Any]], current_pnl_pct: float) -> str | None:
    """Calculate next take profit level.

    Args:
        rules: Exit strategy rules
        current_pnl_pct: Current P&L percentage

    Returns:
        String describing next TP or None
    """
    tp_rules = [r for r in rules if r.get("rule_type") == "take_profit"]
    tp_rules.sort(key=lambda r: r.get("trigger_pct", 0))

    for rule in tp_rules:
        trigger = rule.get("trigger_pct", 0)
        if trigger > current_pnl_pct:
            diff = trigger - current_pnl_pct
            return f"+{diff:.1f}% to TP ({trigger}%)"

    return None


def _format_duration(entry_time: str, exit_time: str | None = None) -> str:
    """Format duration between entry and exit/now.

    Args:
        entry_time: Entry time ISO string
        exit_time: Exit time ISO string or None for current time

    Returns:
        Duration string like "5.2 hours"
    """
    try:
        entry = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
        if exit_time:
            end = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))
        else:
            end = datetime.now(UTC)
        delta = end - entry
        hours = delta.total_seconds() / 3600
        return f"{hours:.1f} hours"
    except Exception:
        return "N/A"


def render_active_position(position: dict[str, Any]) -> str:
    """Render markdown for active position.

    Args:
        position: Position data dict

    Returns:
        Markdown content
    """
    entry_price = Decimal(str(position.get("entry_price", 0)))
    current_price = Decimal(str(position.get("current_price", entry_price)))

    # Calculate P&L
    if entry_price > 0:
        pnl_pct = float((current_price - entry_price) / entry_price * 100)
    else:
        pnl_pct = float(position.get("pnl_pct", 0))
    pnl_sol = float(position.get("pnl_sol", 0))
    size_sol = float(position.get("size_sol", 0))

    # Duration
    entry_time = position.get("entry_time", "")
    duration = _format_duration(entry_time) if entry_time else "N/A"

    # Strategy details
    strategy = position.get("exit_strategies") or {}
    strategy_name = strategy.get("name", "None")
    rules = strategy.get("rules", [])

    # Calculate next TP
    next_tp_info = _calculate_next_tp(rules, pnl_pct)

    # Signal info
    signal = position.get("signals") or {}
    wallet = signal.get("wallet_address", "Unknown")[:16]
    signal_score = signal.get("score", 0)
    signal_date = (signal.get("created_at") or "N/A")[:16]

    pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

    md = f"""
## 📊 Performance

| Metric | Value |
|--------|-------|
| Entry Price | ${entry_price:.8f} |
| Current Price | ${current_price:.8f} |
| P&L | {pnl_emoji} {pnl_pct:+.2f}% ({pnl_sol:+.4f} SOL) |
| Size | {size_sol:.4f} SOL |
| Duration | {duration} |

---

## 🎯 Active Strategy: {strategy_name}

"""
    if rules:
        md += "| Type | Trigger | Exit % | Status |\n"
        md += "|------|---------|--------|--------|\n"

        for rule in rules:
            rule_type = rule.get("rule_type", "?")
            trigger = rule.get("trigger_pct")
            exit_pct = rule.get("exit_pct", 100)

            if trigger is not None:
                status = "✅" if pnl_pct >= float(trigger) else "⏳"
                md += f"| {rule_type} | {trigger:+}% | {exit_pct}% | {status} |\n"
            else:
                md += f"| {rule_type} | - | {exit_pct}% | ⏳ |\n"

        if next_tp_info:
            md += f"\n**Next TP in:** {next_tp_info}\n"

    md += f"""
---

## 📈 Source

| | |
|---|---|
| Wallet | `{wallet}...` |
| Signal Score | {signal_score:.2f} |
| Signal Date | {signal_date} |
"""

    return md


def render_closed_position(position: dict[str, Any]) -> str:
    """Render markdown for closed position.

    Args:
        position: Position data dict

    Returns:
        Markdown content
    """
    entry_price = Decimal(str(position.get("entry_price", 0)))
    exit_price = Decimal(str(position.get("exit_price", entry_price)))
    pnl_pct = float(position.get("pnl_pct", 0))
    pnl_sol = float(position.get("pnl_sol", 0))

    # Duration
    entry_time = position.get("entry_time", "")
    exit_time = position.get("exit_time")
    duration = _format_duration(entry_time, exit_time) if entry_time else "N/A"

    # Exit type
    exit_type = position.get("exit_type", "unknown")
    exit_emoji = EXIT_TYPE_EMOJI.get(exit_type, "❓")

    # Strategy details
    strategy = position.get("exit_strategies") or {}
    strategy_name = strategy.get("name", "None")
    rules = strategy.get("rules", [])

    # Signal info
    signal = position.get("signals") or {}
    wallet = signal.get("wallet_address", "Unknown")[:16]
    signal_score = signal.get("score", 0)
    signal_date = (signal.get("created_at") or "N/A")[:16]

    pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

    md = f"""
## 📊 Final Result

| Metric | Value |
|--------|-------|
| Entry Price | ${entry_price:.8f} |
| Exit Price | ${exit_price:.8f} |
| P&L | {pnl_emoji} {pnl_pct:+.2f}% ({pnl_sol:+.4f} SOL) |
| Exit Type | {exit_emoji} {exit_type} |
| Duration | {duration} |

---

## 🎯 Strategy Used: {strategy_name}

"""
    if rules:
        md += "| Type | Trigger | Exit % | Reached |\n"
        md += "|------|---------|--------|----------|\n"

        # Determine what was reached based on final pnl
        for rule in rules:
            rule_type = rule.get("rule_type", "?")
            trigger = rule.get("trigger_pct")
            exit_pct = rule.get("exit_pct", 100)

            if trigger is not None:
                reached = "✅" if pnl_pct >= float(trigger) else "❌"
                md += f"| {rule_type} | {trigger:+}% | {exit_pct}% | {reached} |\n"
            else:
                md += f"| {rule_type} | - | {exit_pct}% | - |\n"

    md += f"""
---

## 📈 Source

| | |
|---|---|
| Wallet | `{wallet}...` |
| Signal Score | {signal_score:.2f} |
| Signal Date | {signal_date} |

"""

    return md


def create_position_details_sidebar(
    on_change_strategy: Callable[[str], None] | None = None,
) -> tuple[gr.Column, gr.Markdown, gr.Button, gr.State]:
    """Create the position details sidebar component.

    Args:
        on_change_strategy: Callback when Change Strategy button clicked

    Returns:
        Tuple of (sidebar_container, details_content, strategy_btn, position_id_state)
    """
    with gr.Column(visible=False, elem_id="position-details-sidebar") as sidebar_container:
        with gr.Row():
            gr.Markdown("## Position Details", elem_id="sidebar-title")
            close_btn = gr.Button("✕", size="sm", elem_id="sidebar-close-btn")

        details_content = gr.Markdown(elem_id="sidebar-content")

        position_id_state = gr.State(None)

        with gr.Row(visible=False, elem_id="strategy-row") as strategy_row:
            strategy_btn = gr.Button(
                "⚙️ Change Strategy", variant="secondary", elem_id="sidebar-strategy-btn"
            )

    # Close handler
    def close_sidebar() -> tuple[gr.update, str, gr.update, None]:
        return (
            gr.update(visible=False),
            "",
            gr.update(visible=False),
            None,
        )

    close_btn.click(
        close_sidebar,
        outputs=[sidebar_container, details_content, strategy_row, position_id_state],
    )

    # Strategy handler
    def handle_strategy(position_id: str | None) -> None:
        if position_id and on_change_strategy:
            on_change_strategy(position_id)

    strategy_btn.click(handle_strategy, [position_id_state])

    return sidebar_container, details_content, strategy_btn, position_id_state


async def open_sidebar(
    position_id: str,
) -> tuple[gr.update, str, gr.update, str | None]:
    """Open sidebar with position details.

    Args:
        position_id: Position ID to display

    Returns:
        Tuple of updates for (container, content, strategy_row, position_id_state)
    """
    if not position_id:
        return (
            gr.update(visible=False),
            "",
            gr.update(visible=False),
            None,
        )

    position = await fetch_position_details(position_id)
    if not position:
        return (
            gr.update(visible=True),
            "**Position not found**",
            gr.update(visible=False),
            None,
        )

    is_active = position.get("status") == "open"

    if is_active:
        content = render_active_position(position)
        return (
            gr.update(visible=True),
            content,
            gr.update(visible=True),  # strategy visible for active
            position.get("id"),
        )
    else:
        content = render_closed_position(position)
        return (
            gr.update(visible=True),
            content,
            gr.update(visible=False),  # strategy hidden for closed
            position.get("id"),
        )
