"""Exit strategies configuration UI component.

Displays and manages exit strategies in the dashboard.
Supports viewing, creating, editing, and assigning strategies.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import gradio as gr
import pandas as pd

from walltrack.constants.exit_presets import DEFAULT_PRESETS

if TYPE_CHECKING:
    from walltrack.models.exit_strategy import ExitStrategy


def format_strategy_summary(strategy: ExitStrategy) -> dict:
    """Format strategy for table display.

    Args:
        strategy: Exit strategy to format

    Returns:
        Dict with display-ready values
    """
    # Format take profit levels
    tp_summary = ", ".join(
        [
            f"{int(tp.trigger_multiplier)}x→{int(tp.sell_percentage)}%"
            for tp in strategy.take_profit_levels
        ]
    )
    if not tp_summary:
        tp_summary = "None"

    # Format trailing stop
    if strategy.trailing_stop.enabled:
        trailing_str = (
            f"@{strategy.trailing_stop.activation_multiplier}x "
            f"({strategy.trailing_stop.distance_percentage}%)"
        )
    else:
        trailing_str = "Off"

    # Format moonbag
    if strategy.moonbag.has_moonbag:
        if strategy.moonbag.stop_loss:
            moonbag_str = (
                f"{strategy.moonbag.percentage}% "
                f"(SL:{int(strategy.moonbag.stop_loss * 100)}%)"
            )
        else:
            moonbag_str = f"{strategy.moonbag.percentage}% (ride to zero)"
    else:
        moonbag_str = "None"

    # Format time rules
    time_parts = []
    if strategy.time_rules.max_hold_hours:
        time_parts.append(f"Max:{strategy.time_rules.max_hold_hours}h")
    if strategy.time_rules.stagnation_exit_enabled:
        time_parts.append(
            f"Stag:{strategy.time_rules.stagnation_hours}h"
        )
    time_str = ", ".join(time_parts) if time_parts else "None"

    return {
        "id": strategy.id,
        "Name": strategy.name,
        "Stop Loss": f"{int(strategy.stop_loss * 100)}%",
        "Take Profits": tp_summary,
        "Trailing": trailing_str,
        "Moonbag": moonbag_str,
        "Time Rules": time_str,
        "Type": "Preset" if strategy.is_default else "Custom",
    }


def format_strategy_detail(strategy: ExitStrategy) -> str:  # noqa: PLR0912
    """Format strategy detail for markdown display.

    Args:
        strategy: Exit strategy to format

    Returns:
        Markdown formatted string
    """
    lines = [
        f"## {strategy.name}",
        f"**ID:** `{strategy.id}`",
    ]

    if strategy.description:
        lines.append(f"*{strategy.description}*")

    lines.extend([
        "",
        "### Stop Loss",
        f"- **Threshold:** {int(strategy.stop_loss * 100)}% loss triggers exit",
        "",
        "### Take Profit Levels",
    ])

    if strategy.take_profit_levels:
        for i, tp in enumerate(strategy.take_profit_levels, 1):
            lines.append(
                f"{i}. **{tp.trigger_multiplier}x** → Sell {int(tp.sell_percentage)}%"
            )
    else:
        lines.append("- No take profit levels configured")

    lines.extend(["", "### Trailing Stop"])
    if strategy.trailing_stop.enabled:
        lines.append(
            f"- **Activation:** {strategy.trailing_stop.activation_multiplier}x"
        )
        lines.append(
            f"- **Distance:** {strategy.trailing_stop.distance_percentage}% from peak"
        )
    else:
        lines.append("- Disabled")

    lines.extend(["", "### Time Rules"])
    if strategy.has_time_limits:
        if strategy.time_rules.max_hold_hours:
            lines.append(f"- **Max Hold:** {strategy.time_rules.max_hold_hours} hours")
        if strategy.time_rules.stagnation_exit_enabled:
            lines.append(
                f"- **Stagnation Exit:** {strategy.time_rules.stagnation_hours}h "
                f"window, {strategy.time_rules.stagnation_threshold_pct}% threshold"
            )
    else:
        lines.append("- No time limits")

    lines.extend(["", "### Moonbag"])
    if strategy.moonbag.has_moonbag:
        lines.append(f"- **Keep:** {strategy.moonbag.percentage}% of position")
        if strategy.moonbag.stop_loss:
            lines.append(
                f"- **Stop Loss:** {int(strategy.moonbag.stop_loss * 100)}%"
            )
        else:
            lines.append("- **Ride to Zero:** Yes (no stop loss)")
    else:
        lines.append("- No moonbag")

    return "\n".join(lines)


def get_all_strategies_df() -> pd.DataFrame:
    """Get all strategies as DataFrame.

    Returns:
        DataFrame with all presets and custom strategies
    """
    data = [format_strategy_summary(s) for s in DEFAULT_PRESETS]
    return pd.DataFrame(data)


def get_strategy_by_id(strategy_id: str) -> ExitStrategy | None:
    """Get strategy by ID.

    Args:
        strategy_id: Strategy ID to look up

    Returns:
        ExitStrategy if found, None otherwise
    """
    for preset in DEFAULT_PRESETS:
        if preset.id == strategy_id:
            return preset
    return None


def get_preset_choices() -> list[str]:
    """Get list of preset strategy IDs for dropdown.

    Returns:
        List of preset strategy IDs
    """
    return [s.id for s in DEFAULT_PRESETS]


def create_exit_strategies_tab() -> None:
    """Create the exit strategies management tab UI."""
    with gr.Tabs():
        with gr.Tab("All Strategies"):
            _create_strategy_list_view()

        with gr.Tab("Create Strategy"):
            _create_strategy_form()

        with gr.Tab("Change Position Strategy"):
            _create_position_strategy_change_view()


def _create_strategy_list_view() -> None:
    """Create strategy list and detail view."""
    gr.Markdown("### Available Exit Strategies")

    with gr.Row():
        refresh_btn = gr.Button("Refresh", size="sm")

    strategies_table = gr.Dataframe(
        headers=[
            "Name",
            "Stop Loss",
            "Take Profits",
            "Trailing",
            "Moonbag",
            "Time Rules",
            "Type",
        ],
        interactive=False,
        wrap=True,
    )

    gr.Markdown("---")
    gr.Markdown("### Strategy Details")

    with gr.Row():
        strategy_select = gr.Dropdown(
            label="Select Strategy",
            choices=get_preset_choices(),
            scale=3,
        )
        load_btn = gr.Button("Load Details", scale=1)

    strategy_detail = gr.Markdown("*Select a strategy to view details*")

    def load_strategies() -> pd.DataFrame:
        """Load all strategies for display."""
        return get_all_strategies_df()

    def load_detail(strategy_id: str) -> str:
        """Load strategy detail."""
        if not strategy_id:
            return "*Select a strategy to view details*"
        strategy = get_strategy_by_id(strategy_id)
        if strategy:
            return format_strategy_detail(strategy)
        return "*Strategy not found*"

    refresh_btn.click(fn=load_strategies, outputs=strategies_table)
    load_btn.click(fn=load_detail, inputs=strategy_select, outputs=strategy_detail)


def _create_strategy_form() -> None:
    """Create custom strategy creation form."""
    gr.Markdown("""
    ### Create Custom Exit Strategy

    Define your own exit strategy with custom take profit levels,
    trailing stops, and moonbag configuration.
    """)

    with gr.Row():
        strategy_name = gr.Textbox(
            label="Strategy Name",
            placeholder="My Custom Strategy",
        )

    gr.Markdown("#### Stop Loss")
    with gr.Row():
        stop_loss_pct = gr.Slider(
            label="Stop Loss (%)",
            minimum=10,
            maximum=90,
            value=50,
            step=5,
        )

    gr.Markdown("#### Take Profit Levels")

    with gr.Row():
        gr.Markdown("**Level 1**")
        tp1_mult = gr.Number(label="Multiplier", value=2.0, minimum=1.1)
        tp1_pct = gr.Number(label="Sell %", value=33, minimum=0, maximum=100)

    with gr.Row():
        gr.Markdown("**Level 2**")
        tp2_mult = gr.Number(label="Multiplier", value=3.0, minimum=1.1)
        tp2_pct = gr.Number(label="Sell %", value=50, minimum=0, maximum=100)

    with gr.Row():
        gr.Markdown("**Level 3 (optional)**")
        tp3_mult = gr.Number(label="Multiplier", value=0, minimum=0)
        tp3_pct = gr.Number(label="Sell %", value=0, minimum=0, maximum=100)

    gr.Markdown("#### Trailing Stop")

    with gr.Row():
        trailing_enabled = gr.Checkbox(label="Enable Trailing Stop", value=True)
        trailing_activation = gr.Number(
            label="Activation Multiplier",
            value=2.0,
            minimum=1.1,
        )
        trailing_distance = gr.Number(
            label="Distance from Peak (%)",
            value=30,
            minimum=5,
            maximum=50,
        )

    gr.Markdown("#### Time Rules")

    with gr.Row():
        max_hold_hours = gr.Number(
            label="Max Hold Hours (0 = disabled)",
            value=0,
            minimum=0,
        )
        stagnation_enabled = gr.Checkbox(
            label="Stagnation Exit",
            value=False,
        )

    with gr.Row():
        stagnation_hours = gr.Number(
            label="Stagnation Window (hours)",
            value=6,
            minimum=1,
        )
        stagnation_threshold = gr.Number(
            label="Movement Threshold (%)",
            value=5,
            minimum=1,
        )

    gr.Markdown("#### Moonbag")

    with gr.Row():
        moonbag_pct = gr.Number(
            label="Keep % (0 = disabled)",
            value=0,
            minimum=0,
            maximum=50,
        )
        moonbag_sl = gr.Slider(
            label="Moonbag Stop Loss (0 = ride to zero)",
            minimum=0,
            maximum=0.9,
            value=0.3,
            step=0.1,
        )

    with gr.Row():
        save_btn = gr.Button("Save Strategy", variant="primary")

    save_status = gr.Markdown("")

    def save_strategy(
        name: str,
        _stop_loss: float,
        tp1_m: float,
        tp1_p: float,
        tp2_m: float,
        tp2_p: float,
        tp3_m: float,
        tp3_p: float,
        _trailing_en: bool,
        _trailing_act: float,
        _trailing_dist: float,
        _max_hold: int,
        _stag_en: bool,
        _stag_hours: int,
        _stag_thresh: float,
        _mb_pct: float,
        _mb_sl: float,
    ) -> str:
        """Validate and save strategy (placeholder)."""
        if not name:
            return "**Error:** Strategy name is required"
        if tp1_p + tp2_p + tp3_p > 100:
            return "**Error:** Total sell percentage cannot exceed 100%"
        if tp2_m > 0 and tp2_m <= tp1_m:
            return "**Error:** Level 2 multiplier must be higher than Level 1"
        if tp3_m > 0 and tp3_m <= tp2_m:
            return "**Error:** Level 3 multiplier must be higher than Level 2"

        # Note: Actual persistence would use repository here
        return f"**Success:** Strategy '{name}' configuration is valid"

    save_btn.click(
        fn=save_strategy,
        inputs=[
            strategy_name,
            stop_loss_pct,
            tp1_mult,
            tp1_pct,
            tp2_mult,
            tp2_pct,
            tp3_mult,
            tp3_pct,
            trailing_enabled,
            trailing_activation,
            trailing_distance,
            max_hold_hours,
            stagnation_enabled,
            stagnation_hours,
            stagnation_threshold,
            moonbag_pct,
            moonbag_sl,
        ],
        outputs=save_status,
    )


def _create_position_strategy_change_view() -> None:
    """Create view for changing position strategy."""
    gr.Markdown("""
    ### Change Exit Strategy for Active Position

    **Warning:** Changing strategy will recalculate all stop-loss
    and take-profit levels for the position.
    """)

    with gr.Row():
        position_id_input = gr.Textbox(
            label="Position ID",
            placeholder="Enter position ID",
            scale=2,
        )
        new_strategy_select = gr.Dropdown(
            label="New Strategy",
            choices=get_preset_choices(),
            scale=2,
        )

    change_reason = gr.Textbox(
        label="Reason for Change (optional)",
        placeholder="Why are you changing the strategy?",
    )

    with gr.Row():
        change_btn = gr.Button("Apply Strategy Change", variant="primary")

    change_status = gr.Markdown("")

    def apply_change(
        position_id: str,
        new_strategy_id: str,
        reason: str,
    ) -> str:
        """Apply strategy change (placeholder)."""
        if not position_id:
            return "**Error:** Position ID is required"
        if not new_strategy_id:
            return "**Error:** Select a new strategy"

        # Note: Actual implementation would use position manager
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
        return (
            f"**Change Logged**\n\n"
            f"- Position: `{position_id[:8]}...`\n"
            f"- New Strategy: `{new_strategy_id}`\n"
            f"- Reason: {reason or 'Not specified'}\n"
            f"- Time: {timestamp} UTC"
        )

    change_btn.click(
        fn=apply_change,
        inputs=[position_id_input, new_strategy_select, change_reason],
        outputs=change_status,
    )
