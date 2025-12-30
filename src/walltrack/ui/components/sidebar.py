"""Sidebar component for contextual information.

Provides a right-side panel for displaying:
- Selected item details
- Context-specific actions
- Quick actions
- Behavioral profiling metrics (Story 3.3)
"""

from decimal import Decimal

import gradio as gr

from walltrack.core.behavioral.hold_duration import format_duration_human
from walltrack.data.models.wallet import Wallet


def create_sidebar() -> tuple[gr.Sidebar, gr.State, gr.Markdown]:
    """Create the sidebar with context display area.

    Returns:
        Tuple of (sidebar, context_state, context_display).
    """
    context_state = gr.State(value=None)

    with gr.Sidebar(
        position="right",
        open=False,
    ) as sidebar:
        gr.Markdown("## Context")

        context_display = gr.Markdown(
            value="*Select an element to view details*",
            elem_id="sidebar-context",
        )

        gr.Markdown("---")
        gr.Markdown("### Actions")
        gr.Markdown("*Actions will appear based on selection*")

    return sidebar, context_state, context_display


def update_sidebar_context(context: dict[str, object] | None) -> str:
    """Update sidebar context display.

    Args:
        context: Dictionary with context information or None.

    Returns:
        Markdown string for display.
    """
    if context is None:
        return "*Select an element to view details*"

    lines = []
    for key, value in context.items():
        lines.append(f"**{key}**: {value}")

    return "\n\n".join(lines) if lines else "*No details available*"


def format_behavioral_profile_display(wallet: Wallet) -> str:
    """Format behavioral profiling data for sidebar display (AC2, AC3).

    Args:
        wallet: Wallet model with behavioral profiling data.

    Returns:
        Markdown string with formatted behavioral profile.

    Example:
        >>> wallet = Wallet(wallet_address="9xQ...", position_size_style="medium", ...)
        >>> markdown = format_behavioral_profile_display(wallet)
        >>> print(markdown)
        ### 🎯 Behavioral Profile
        ...
    """
    if wallet.behavioral_confidence is None or wallet.behavioral_confidence == "unknown":
        return """### 🎯 Behavioral Profile

*Insufficient data for behavioral analysis (requires 10+ trades)*

**Status**: No profile available"""

    lines = ["### 🎯 Behavioral Profile\n"]

    # AC2: Position Size Display
    if wallet.position_size_style:
        # Badge visual according to style
        badge_map = {
            "small": "🟢",   # Green for small
            "medium": "🟡",  # Yellow for medium
            "large": "🔴",   # Red for large
        }
        badge = badge_map.get(wallet.position_size_style, "⚪")

        lines.append(f"**Position Sizing** {badge} `{wallet.position_size_style.upper()}`")

        if wallet.position_size_avg:
            lines.append(f"• Avg Size: **{wallet.position_size_avg:.4f} SOL**")

        lines.append(f"• Total Trades: **{wallet.total_trades or 0}**")
        lines.append("")

    # AC3: Hold Duration Display
    if wallet.hold_duration_style:
        # Badge visual according to style
        badge_map = {
            "scalper": "⚡",          # Lightning for scalper
            "day_trader": "📊",      # Chart for day trader
            "swing_trader": "📈",    # Trending up for swing
            "position_trader": "🎯", # Target for position
        }
        badge = badge_map.get(wallet.hold_duration_style, "⚪")

        # Human-readable style names
        style_names = {
            "scalper": "Scalper",
            "day_trader": "Day Trader",
            "swing_trader": "Swing Trader",
            "position_trader": "Position Trader",
        }
        style_display = style_names.get(wallet.hold_duration_style, wallet.hold_duration_style)

        lines.append(f"**Trading Style** {badge} `{style_display.upper()}`")

        if wallet.hold_duration_avg:
            formatted_duration = format_duration_human(wallet.hold_duration_avg)
            lines.append(f"• Avg Hold Time: **{formatted_duration}**")

        lines.append("")

    # Confidence level
    confidence_badge_map = {
        "high": "✅",
        "medium": "⚠️",
        "low": "❌",
        "unknown": "❓",
    }
    confidence_badge = confidence_badge_map.get(
        wallet.behavioral_confidence or "unknown", "❓"
    )
    lines.append(
        f"**Confidence**: {confidence_badge} `{(wallet.behavioral_confidence or 'unknown').upper()}`"
    )

    # Last updated
    if wallet.behavioral_last_updated:
        lines.append(
            f"*Updated: {wallet.behavioral_last_updated.strftime('%Y-%m-%d %H:%M UTC')}*"
        )

    return "\n".join(lines)
