"""Configuration management page with lifecycle support."""

from typing import Any

import gradio as gr
import structlog

from walltrack.ui.components.config_history import (
    create_audit_tab,
    create_history_tab,
)
from walltrack.ui.pages.config_handlers import (
    activate_draft_sync,
    create_draft_sync,
    delete_draft_sync,
    load_config_sync,
    update_draft_sync,
)

logger = structlog.get_logger(__name__)

# Config tables and their display names
CONFIG_TABLES = {
    "trading": "Trading",
    "scoring": "Scoring",
    "discovery": "Discovery",
    "cluster": "Cluster",
    "risk": "Risk",
    "exit": "Exit",
    "api": "API",
}


def create_config_page() -> None:
    """Create the configuration management page with lifecycle tabs."""
    gr.Markdown("## Configuration Management")
    gr.Markdown(
        "Manage system configurations with version control. "
        "Edit creates a draft, which must be activated to take effect."
    )

    with gr.Tabs(elem_id="config-tabs"):
        # Config domain tabs
        for table_key, table_name in CONFIG_TABLES.items():
            with gr.TabItem(table_name, id=f"tab-{table_key}"):
                _create_config_tab(table_key, table_name)

        # History tab
        with gr.TabItem("History", id="tab-history"):
            create_history_tab()

        # Audit Log tab
        with gr.TabItem("Audit Log", id="tab-audit"):
            create_audit_tab()


def _create_config_tab(table_key: str, _table_name: str) -> None:
    """Create a config tab with lifecycle controls."""
    # State for this tab
    current_config = gr.State(value={})
    is_editing = gr.State(value=False)
    has_draft = gr.State(value=False)

    # Status bar
    with gr.Row():
        status_badge = gr.Textbox(
            label="Status",
            value="Loading...",
            interactive=False,
            scale=1,
            elem_id=f"config-{table_key}-status",
        )
        version_display = gr.Number(
            label="Version",
            value=0,
            precision=0,
            interactive=False,
            scale=1,
        )
        last_updated = gr.Textbox(
            label="Last Updated",
            value="",
            interactive=False,
            scale=2,
        )

    # Config content based on table type
    if table_key == "trading":
        fields = _create_trading_fields()
    elif table_key == "scoring":
        fields = _create_scoring_fields()
    elif table_key == "discovery":
        fields = _create_discovery_fields()
    elif table_key == "cluster":
        fields = _create_cluster_fields()
    elif table_key == "risk":
        fields = _create_risk_fields()
    elif table_key == "exit":
        fields = _create_exit_fields()
    elif table_key == "api":
        fields = _create_api_fields()
    else:
        fields = {}

    # Action buttons
    with gr.Row():
        edit_btn = gr.Button(
            "Edit",
            variant="secondary",
            elem_id=f"config-{table_key}-edit",
        )
        save_btn = gr.Button(
            "Save Draft",
            variant="primary",
            visible=False,
            elem_id=f"config-{table_key}-save",
        )
        discard_btn = gr.Button(
            "Discard",
            variant="stop",
            visible=False,
            elem_id=f"config-{table_key}-discard",
        )
        activate_btn = gr.Button(
            "Activate",
            variant="primary",
            visible=False,
            elem_id=f"config-{table_key}-activate",
        )
        refresh_btn = gr.Button(
            "Refresh",
            variant="secondary",
            elem_id=f"config-{table_key}-refresh",
        )

    # Status message
    status_msg = gr.Textbox(
        label="",
        value="",
        interactive=False,
        visible=False,
        elem_id=f"config-{table_key}-msg",
    )

    # Wire up events
    _wire_tab_events(
        table_key=table_key,
        fields=fields,
        status_badge=status_badge,
        version_display=version_display,
        last_updated=last_updated,
        current_config=current_config,
        is_editing=is_editing,
        has_draft=has_draft,
        edit_btn=edit_btn,
        save_btn=save_btn,
        discard_btn=discard_btn,
        activate_btn=activate_btn,
        refresh_btn=refresh_btn,
        status_msg=status_msg,
    )


def _create_trading_fields() -> dict[str, Any]:
    """Create trading configuration fields."""
    fields = {}

    gr.Markdown("### Position Sizing")
    with gr.Row():
        fields["base_position_pct"] = gr.Number(
            label="Base Position %",
            info="Percentage of capital per trade",
            precision=2,
            interactive=False,
        )
        fields["max_position_sol"] = gr.Number(
            label="Max Position (SOL)",
            info="Maximum position size",
            precision=4,
            interactive=False,
        )
        fields["min_position_sol"] = gr.Number(
            label="Min Position (SOL)",
            info="Minimum position size",
            precision=4,
            interactive=False,
        )

    with gr.Row():
        fields["sizing_mode"] = gr.Dropdown(
            choices=["risk_based", "fixed_percent"],
            label="Sizing Mode",
            interactive=False,
        )
        fields["risk_per_trade_pct"] = gr.Number(
            label="Risk Per Trade %",
            info="For risk-based sizing",
            precision=2,
            interactive=False,
        )
        fields["high_conviction_mult"] = gr.Number(
            label="High Conviction Multiplier",
            precision=2,
            interactive=False,
        )

    gr.Markdown("### Thresholds")
    with gr.Row():
        fields["score_threshold"] = gr.Number(
            label="Score Threshold",
            info="Minimum score to trade",
            precision=3,
            interactive=False,
        )
        fields["high_conviction_threshold"] = gr.Number(
            label="High Conviction Threshold",
            info="Score for high conviction",
            precision=3,
            interactive=False,
        )

    gr.Markdown("### Limits")
    with gr.Row():
        fields["max_concurrent"] = gr.Number(
            label="Max Concurrent Positions",
            precision=0,
            interactive=False,
        )
        fields["daily_loss_limit"] = gr.Number(
            label="Daily Loss Limit %",
            precision=2,
            interactive=False,
        )
        fields["daily_loss_enabled"] = gr.Checkbox(
            label="Daily Loss Limit Enabled",
            interactive=False,
        )

    gr.Markdown("### Concentration Limits")
    with gr.Row():
        fields["max_token_pct"] = gr.Number(
            label="Max Token %",
            precision=2,
            interactive=False,
        )
        fields["max_cluster_pct"] = gr.Number(
            label="Max Cluster %",
            precision=2,
            interactive=False,
        )
        fields["max_pos_per_cluster"] = gr.Number(
            label="Max Positions/Cluster",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Slippage")
    with gr.Row():
        fields["slippage_entry_bps"] = gr.Number(
            label="Entry Slippage (bps)",
            precision=0,
            interactive=False,
        )
        fields["slippage_exit_bps"] = gr.Number(
            label="Exit Slippage (bps)",
            precision=0,
            interactive=False,
        )

    return fields


def _create_scoring_fields() -> dict[str, Any]:
    """Create scoring configuration fields."""
    fields = {}

    gr.Markdown("### Score Weights")
    with gr.Row():
        fields["wallet_weight"] = gr.Number(
            label="Wallet Weight",
            precision=3,
            interactive=False,
        )
        fields["cluster_weight"] = gr.Number(
            label="Cluster Weight",
            precision=3,
            interactive=False,
        )
        fields["token_weight"] = gr.Number(
            label="Token Weight",
            precision=3,
            interactive=False,
        )
        fields["context_weight"] = gr.Number(
            label="Context Weight",
            precision=3,
            interactive=False,
        )

    gr.Markdown("### Wallet Scoring")
    with gr.Row():
        fields["win_rate_weight"] = gr.Number(
            label="Win Rate Weight",
            precision=3,
            interactive=False,
        )
        fields["avg_pnl_weight"] = gr.Number(
            label="Avg PnL Weight",
            precision=3,
            interactive=False,
        )
        fields["consistency_weight"] = gr.Number(
            label="Consistency Weight",
            precision=3,
            interactive=False,
        )

    gr.Markdown("### Thresholds")
    with gr.Row():
        fields["trade_threshold"] = gr.Number(
            label="Trade Threshold",
            info="Minimum score to trade",
            precision=3,
            interactive=False,
        )
        fields["high_conviction_threshold"] = gr.Number(
            label="High Conviction Threshold",
            precision=3,
            interactive=False,
        )

    return fields


def _create_discovery_fields() -> dict[str, Any]:
    """Create discovery configuration fields."""
    fields = {}

    gr.Markdown("### Discovery Runs")
    with gr.Row():
        fields["run_interval_minutes"] = gr.Number(
            label="Run Interval (min)",
            precision=0,
            interactive=False,
        )
        fields["max_wallets_per_run"] = gr.Number(
            label="Max Wallets/Run",
            precision=0,
            interactive=False,
        )
        fields["min_wallet_age_days"] = gr.Number(
            label="Min Wallet Age (days)",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Wallet Criteria")
    with gr.Row():
        fields["min_win_rate"] = gr.Number(
            label="Min Win Rate",
            precision=3,
            interactive=False,
        )
        fields["min_trades"] = gr.Number(
            label="Min Trades",
            precision=0,
            interactive=False,
        )
        fields["min_avg_pnl_pct"] = gr.Number(
            label="Min Avg PnL %",
            precision=2,
            interactive=False,
        )

    gr.Markdown("### Token Filters")
    with gr.Row():
        fields["min_price_change_pct"] = gr.Number(
            label="Min Price Change %",
            precision=0,
            interactive=False,
        )
        fields["min_volume_usd"] = gr.Number(
            label="Min Volume USD",
            precision=0,
            interactive=False,
        )
        fields["max_tokens"] = gr.Number(
            label="Max Tokens to Analyze",
            precision=0,
            interactive=False,
        )

    return fields


def _create_cluster_fields() -> dict[str, Any]:
    """Create cluster configuration fields."""
    fields = {}

    gr.Markdown("### Clustering")
    with gr.Row():
        fields["min_cluster_size"] = gr.Number(
            label="Min Cluster Size",
            precision=0,
            interactive=False,
        )
        fields["max_cluster_size"] = gr.Number(
            label="Max Cluster Size",
            precision=0,
            interactive=False,
        )
        fields["similarity_threshold"] = gr.Number(
            label="Similarity Threshold",
            precision=3,
            interactive=False,
        )

    gr.Markdown("### Sync Detection")
    with gr.Row():
        fields["sync_window_minutes"] = gr.Number(
            label="Sync Window (min)",
            precision=0,
            interactive=False,
        )
        fields["token_overlap_threshold"] = gr.Number(
            label="Token Overlap Threshold",
            precision=3,
            interactive=False,
        )
        fields["min_sync_trades"] = gr.Number(
            label="Min Sync Trades",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Scoring")
    with gr.Row():
        fields["leader_bonus"] = gr.Number(
            label="Leader Bonus",
            precision=3,
            interactive=False,
        )
        fields["cluster_score_boost"] = gr.Number(
            label="Cluster Score Boost",
            precision=3,
            interactive=False,
        )

    return fields


def _create_risk_fields() -> dict[str, Any]:
    """Create risk configuration fields."""
    fields = {}

    gr.Markdown("### Circuit Breaker")
    with gr.Row():
        fields["circuit_breaker_enabled"] = gr.Checkbox(
            label="Enabled",
            interactive=False,
        )
        fields["loss_threshold_pct"] = gr.Number(
            label="Loss Threshold %",
            precision=2,
            interactive=False,
        )
        fields["cooldown_minutes"] = gr.Number(
            label="Cooldown (min)",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Drawdown")
    with gr.Row():
        fields["max_drawdown_pct"] = gr.Number(
            label="Max Drawdown %",
            precision=2,
            interactive=False,
        )
        fields["drawdown_lookback_days"] = gr.Number(
            label="Lookback (days)",
            precision=0,
            interactive=False,
        )
        fields["size_reduction_enabled"] = gr.Checkbox(
            label="Size Reduction Enabled",
            interactive=False,
        )

    gr.Markdown("### Order Retry")
    with gr.Row():
        fields["max_retry_attempts"] = gr.Number(
            label="Max Attempts",
            precision=0,
            interactive=False,
        )
        fields["base_retry_delay_s"] = gr.Number(
            label="Base Delay (s)",
            precision=0,
            interactive=False,
        )
        fields["retry_delay_multiplier"] = gr.Number(
            label="Delay Multiplier",
            precision=2,
            interactive=False,
        )

    gr.Markdown("### Daily Limits")
    with gr.Row():
        fields["daily_loss_limit_pct"] = gr.Number(
            label="Daily Loss Limit %",
            precision=2,
            interactive=False,
        )
        fields["daily_trade_limit"] = gr.Number(
            label="Max Trades/Day",
            precision=0,
            interactive=False,
        )

    return fields


def _create_exit_fields() -> dict[str, Any]:
    """Create exit strategy configuration fields."""
    fields = {}

    gr.Markdown("### Default Strategy Assignments")
    with gr.Row():
        fields["standard_strategy"] = gr.Textbox(
            label="Standard Strategy",
            interactive=False,
        )
        fields["high_conviction_strategy"] = gr.Textbox(
            label="High Conviction Strategy",
            interactive=False,
        )

    gr.Markdown("### Time Limits")
    with gr.Row():
        fields["max_hold_hours"] = gr.Number(
            label="Max Hold (hours)",
            precision=0,
            interactive=False,
        )
        fields["stagnation_hours"] = gr.Number(
            label="Stagnation (hours)",
            precision=0,
            interactive=False,
        )
        fields["stagnation_threshold_pct"] = gr.Number(
            label="Stagnation %",
            precision=2,
            interactive=False,
        )

    gr.Markdown("### Price History")
    with gr.Row():
        fields["collection_interval_s"] = gr.Number(
            label="Collection Interval (s)",
            precision=0,
            interactive=False,
        )
        fields["retention_days"] = gr.Number(
            label="Retention (days)",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Stop Loss / Take Profit")
    with gr.Row():
        fields["default_stop_loss_pct"] = gr.Number(
            label="Default Stop Loss %",
            precision=2,
            interactive=False,
        )
        fields["default_take_profit_pct"] = gr.Number(
            label="Default Take Profit %",
            precision=2,
            interactive=False,
        )
        fields["trailing_stop_enabled"] = gr.Checkbox(
            label="Trailing Stop Enabled",
            interactive=False,
        )

    return fields


def _create_api_fields() -> dict[str, Any]:
    """Create API configuration fields."""
    fields = {}

    gr.Markdown("### Rate Limits (requests/min)")
    with gr.Row():
        fields["dexscreener_rpm"] = gr.Number(
            label="DexScreener",
            precision=0,
            interactive=False,
        )
        fields["birdeye_rpm"] = gr.Number(
            label="Birdeye",
            precision=0,
            interactive=False,
        )
        fields["jupiter_rpm"] = gr.Number(
            label="Jupiter",
            precision=0,
            interactive=False,
        )
        fields["helius_rpm"] = gr.Number(
            label="Helius",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Timeouts")
    with gr.Row():
        fields["api_timeout_s"] = gr.Number(
            label="API Timeout (s)",
            precision=0,
            interactive=False,
        )
        fields["rpc_timeout_s"] = gr.Number(
            label="RPC Timeout (s)",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Caching")
    with gr.Row():
        fields["price_cache_ttl_s"] = gr.Number(
            label="Price Cache TTL (s)",
            precision=0,
            interactive=False,
        )
        fields["token_info_cache_ttl_s"] = gr.Number(
            label="Token Info TTL (s)",
            precision=0,
            interactive=False,
        )
        fields["wallet_cache_ttl_s"] = gr.Number(
            label="Wallet Cache TTL (s)",
            precision=0,
            interactive=False,
        )

    gr.Markdown("### Retry")
    with gr.Row():
        fields["max_retries"] = gr.Number(
            label="Max Retries",
            precision=0,
            interactive=False,
        )
        fields["retry_backoff_s"] = gr.Number(
            label="Retry Backoff (s)",
            precision=1,
            interactive=False,
        )

    return fields


def _wire_tab_events(
    table_key: str,
    fields: dict[str, gr.components.Component],
    status_badge: gr.Textbox,
    version_display: gr.Number,
    last_updated: gr.Textbox,
    current_config: gr.State,
    is_editing: gr.State,
    has_draft: gr.State,
    edit_btn: gr.Button,
    save_btn: gr.Button,
    discard_btn: gr.Button,
    activate_btn: gr.Button,
    refresh_btn: gr.Button,
    status_msg: gr.Textbox,
) -> None:
    """Wire up event handlers for a config tab."""

    def load_and_display():
        """Load config and return display values."""
        config = load_config_sync(table_key)
        if not config:
            return (
                "Error loading",
                0,
                "",
                {},
                False,
                False,
                gr.update(visible=True),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(visible=False),
                gr.update(value="Failed to load configuration", visible=True),
                *[gr.update(value=None) for _ in fields],
            )

        data = config.get("data", {})
        status = config.get("status", "unknown")
        version = config.get("version", 0)
        updated = config.get("updated_at", "")

        # Update field values
        field_updates = []
        for field_name in fields:
            value = data.get(field_name)
            field_updates.append(gr.update(value=value))

        is_draft = status == "draft"
        return (
            status.capitalize(),
            version,
            updated[:19] if updated else "",
            data,
            is_draft,
            is_draft,
            gr.update(visible=not is_draft),
            gr.update(visible=is_draft),
            gr.update(visible=is_draft),
            gr.update(visible=is_draft),
            gr.update(value="", visible=False),
            *field_updates,
        )

    def enter_edit_mode(_current_cfg: dict, editing: bool, draft: bool):
        """Enter edit mode - creates draft if needed."""
        if draft:
            # Already have a draft, just enable fields
            return (
                True,
                True,
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(value="Editing draft...", visible=True),
                *[gr.update(interactive=True) for _ in fields],
            )

        # Create a new draft
        result = create_draft_sync(table_key)
        if result:
            return (
                True,
                True,
                gr.update(visible=False),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(visible=True),
                gr.update(value="Draft created. Make your changes.", visible=True),
                *[gr.update(interactive=True) for _ in fields],
            )
        else:
            return (
                editing,
                draft,
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(),
                gr.update(value="Failed to create draft", visible=True),
                *[gr.update() for _ in fields],
            )

    def save_draft_changes(*field_values):
        """Save current field values to draft."""
        data = {}
        for (field_name, _), value in zip(fields.items(), field_values, strict=False):
            if value is not None:
                data[field_name] = value

        result = update_draft_sync(table_key, data)
        if result:
            return gr.update(value="Draft saved successfully!", visible=True)
        return gr.update(value="Failed to save draft", visible=True)

    def discard_changes():
        """Discard draft and reload active config."""
        success = delete_draft_sync(table_key)
        if success:
            # Reload will happen via refresh
            return (
                False,
                False,
                gr.update(value="Draft discarded", visible=True),
            )
        return (
            gr.update(),
            gr.update(),
            gr.update(value="Failed to discard draft", visible=True),
        )

    def activate_changes():
        """Activate the draft configuration."""
        result = activate_draft_sync(table_key)
        if result:
            return (
                False,
                False,
                gr.update(value="Configuration activated!", visible=True),
            )
        return (
            gr.update(),
            gr.update(),
            gr.update(value="Failed to activate", visible=True),
        )

    # Initial load on page
    field_outputs = list(fields.values())

    refresh_btn.click(
        fn=load_and_display,
        outputs=[
            status_badge,
            version_display,
            last_updated,
            current_config,
            is_editing,
            has_draft,
            edit_btn,
            save_btn,
            discard_btn,
            activate_btn,
            status_msg,
            *field_outputs,
        ],
    )

    edit_btn.click(
        fn=enter_edit_mode,
        inputs=[current_config, is_editing, has_draft],
        outputs=[
            is_editing,
            has_draft,
            edit_btn,
            save_btn,
            discard_btn,
            activate_btn,
            status_msg,
            *field_outputs,
        ],
    )

    save_btn.click(
        fn=save_draft_changes,
        inputs=field_outputs,
        outputs=[status_msg],
    )

    discard_btn.click(
        fn=discard_changes,
        outputs=[is_editing, has_draft, status_msg],
    ).then(
        fn=load_and_display,
        outputs=[
            status_badge,
            version_display,
            last_updated,
            current_config,
            is_editing,
            has_draft,
            edit_btn,
            save_btn,
            discard_btn,
            activate_btn,
            status_msg,
            *field_outputs,
        ],
    )

    activate_btn.click(
        fn=activate_changes,
        outputs=[is_editing, has_draft, status_msg],
    ).then(
        fn=load_and_display,
        outputs=[
            status_badge,
            version_display,
            last_updated,
            current_config,
            is_editing,
            has_draft,
            edit_btn,
            save_btn,
            discard_btn,
            activate_btn,
            status_msg,
            *field_outputs,
        ],
    )
