"""Explorer page - Signals, Wallets, Clusters tabs."""

from typing import Any

import gradio as gr
import pandas as pd
import structlog

from walltrack.ui.components.clusters import (
    _sync_detect_leaders,
    _sync_fetch_clusters,
    _sync_run_cooccurrence,
    _sync_run_discovery,
    _sync_update_multipliers,
)
from walltrack.ui.components.signals import fetch_recent_signals, format_signals_table
from walltrack.ui.components.wallets import (
    _load_wallets,
    _on_add_wallet,
    _on_blacklist,
    _on_unblacklist,
    _on_wallet_select,
    fetch_wallet_detail,
)

log = structlog.get_logger()


def create_explorer_page(sidebar_state: gr.State) -> None:
    """Create the explorer page with tabs for Signals, Wallets, Clusters.

    Args:
        sidebar_state: Shared state for sidebar context
    """
    with gr.Tabs(elem_id="explorer-tabs"):
        # ========== SIGNALS TAB ==========
        with gr.Tab("Signals", id="signals", elem_id="explorer-signals-tab"):
            _create_signals_section(sidebar_state)

        # ========== WALLETS TAB ==========
        with gr.Tab("Wallets", id="wallets", elem_id="explorer-wallets-tab"):
            _create_wallets_section(sidebar_state)

        # ========== CLUSTERS TAB ==========
        with gr.Tab("Clusters", id="clusters", elem_id="explorer-clusters-tab"):
            _create_clusters_section(sidebar_state)


def _create_signals_section(sidebar_state: gr.State) -> None:
    """Create signals section."""
    gr.Markdown("### Signal Feed")
    gr.Markdown("Real-time trading signals from wallet analysis")

    with gr.Row():
        signals_refresh_btn = gr.Button("Refresh Signals", variant="primary")

    with gr.Row():
        with gr.Column(scale=3):
            signals_table = gr.Dataframe(
                headers=["Time", "Token", "Wallet", "Score", "Amount", "Type"],
                label="Recent Signals (24h)",
                interactive=False,
                elem_id="explorer-signals-table",
            )

        with gr.Column(scale=1):
            gr.Markdown("### Stats")
            total_signals = gr.Markdown("**Total:** -")
            avg_score = gr.Markdown("**Avg Score:** -")
            unique_tokens = gr.Markdown("**Tokens:** -")
            unique_wallets = gr.Markdown("**Wallets:** -")

    async def load_signals() -> tuple[pd.DataFrame, str, str, str, str]:
        """Load and format signals."""
        signals = await fetch_recent_signals()
        df = format_signals_table(signals)

        if signals and "error" not in signals[0]:
            total = len(signals)
            scores = [s.get("score", 0) for s in signals if s.get("score")]
            avg = sum(scores) / len(scores) if scores else 0
            tokens = len({s.get("token_address", "") for s in signals})
            wallets = len({s.get("wallet_address", "") for s in signals})

            return (
                df,
                f"**Total:** {total}",
                f"**Avg Score:** {avg:.2f}",
                f"**Tokens:** {tokens}",
                f"**Wallets:** {wallets}",
            )

        return df, "**Total:** -", "**Avg Score:** -", "**Tokens:** -", "**Wallets:** -"

    signals_refresh_btn.click(
        fn=load_signals,
        outputs=[signals_table, total_signals, avg_score, unique_tokens, unique_wallets],
    )

    # Signal selection -> sidebar
    def on_signal_select(evt: gr.SelectData, df: pd.DataFrame) -> dict[str, Any]:
        if evt.index[0] < len(df):
            row = df.iloc[evt.index[0]]
            signal_data = {
                "timestamp": row.get("Time", ""),
                "token_address": row.get("Token", ""),
                "wallet_address": row.get("Wallet", ""),
                "score": float(row.get("Score", "0")),
                "amount_sol": row.get("Amount", ""),
                "signal_type": row.get("Type", "buy"),
            }
            return {"type": "signal", "data": signal_data}
        return {"type": None, "data": None}

    signals_table.select(
        fn=on_signal_select,
        inputs=[signals_table],
        outputs=[sidebar_state],
    )


def _create_wallets_section(sidebar_state: gr.State) -> None:
    """Create wallets section."""
    gr.Markdown("### Wallet Watchlist")

    with gr.Row():
        with gr.Column(scale=3):
            with gr.Row():
                status_filter = gr.Dropdown(
                    choices=["all", "active", "decay_detected", "blacklisted", "insufficient_data"],
                    value="all",
                    label="Status Filter",
                    scale=1,
                    elem_id="explorer-wallets-status-filter",
                )
                min_score = gr.Slider(
                    minimum=0, maximum=1, value=0, step=0.05, label="Min Score", scale=1,
                    elem_id="explorer-wallets-min-score",
                )
                wallets_refresh_btn = gr.Button(
                    "Refresh", scale=1, elem_id="explorer-wallets-refresh-btn"
                )

            wallet_table = gr.Dataframe(
                headers=[
                    "Address", "Status", "Score", "Win Rate",
                    "Total PnL", "Trades", "Last Signal",
                ],
                datatype=["str", "str", "str", "str", "str", "number", "str"],
                interactive=False,
                row_count=15,
                elem_id="explorer-wallets-table",
            )

        with gr.Column(scale=2):
            gr.Markdown("### Wallet Details")
            selected_address = gr.Textbox(
                label="Selected Wallet",
                placeholder="Click a wallet to view details",
                interactive=False,
                elem_id="explorer-wallets-selected",
            )
            wallet_detail = gr.Markdown(
                "Select a wallet to view details", elem_id="explorer-wallet-detail"
            )

            with gr.Row():
                blacklist_reason = gr.Textbox(
                    label="Blacklist Reason", placeholder="Enter reason...", scale=3,
                    elem_id="explorer-blacklist-reason",
                )
                blacklist_btn = gr.Button(
                    "Blacklist", variant="stop", scale=1, elem_id="explorer-blacklist-btn"
                )

            unblacklist_btn = gr.Button(
                "Remove from Blacklist", variant="secondary", elem_id="explorer-unblacklist-btn"
            )

    # Add wallet section
    gr.Markdown("---")
    with gr.Row():
        new_wallet_address = gr.Textbox(
            label="Add Wallet",
            placeholder="Enter Solana wallet address...",
            scale=4,
            elem_id="explorer-new-wallet",
        )
        add_wallet_btn = gr.Button(
            "Add & Profile", variant="primary", scale=1, elem_id="explorer-add-wallet-btn"
        )

    add_wallet_result = gr.Markdown("", elem_id="explorer-add-result")

    # Event handlers
    load_inputs = [status_filter, min_score]
    wallets_refresh_btn.click(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])
    status_filter.change(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])
    min_score.change(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])

    # Wallet selection
    async def on_wallet_select_with_sidebar(
        evt: gr.SelectData, df: pd.DataFrame
    ) -> tuple[str, str, dict[str, Any]]:
        address, detail = await _on_wallet_select(evt, df)
        wallet_data = {}
        if address:
            wallet = await fetch_wallet_detail(address)
            if wallet:
                wallet_data = wallet
        return address, detail, {"type": "wallet", "data": wallet_data}

    wallet_table.select(
        fn=on_wallet_select_with_sidebar,
        inputs=[wallet_table],
        outputs=[selected_address, wallet_detail, sidebar_state],
    )

    add_wallet_btn.click(
        fn=_on_add_wallet, inputs=[new_wallet_address], outputs=[add_wallet_result, wallet_table]
    )
    blacklist_btn.click(
        fn=_on_blacklist,
        inputs=[selected_address, blacklist_reason],
        outputs=[wallet_detail, add_wallet_result],
    )
    unblacklist_btn.click(
        fn=_on_unblacklist, inputs=[selected_address], outputs=[wallet_detail, add_wallet_result]
    )


def _create_clusters_section(sidebar_state: gr.State) -> None:
    """Create clusters section."""
    gr.Markdown("### Cluster Analysis")
    gr.Markdown(
        "Analyze wallet relationships to identify coordinated groups."
    )

    with gr.Row():
        with gr.Column(scale=2):
            cluster_table = gr.Dataframe(
                headers=["ID", "Size", "Cohesion", "Multiplier", "Leader", "Members"],
                label="Detected Clusters",
                interactive=False,
                elem_id="explorer-clusters-table",
            )

        with gr.Column(scale=1):
            gr.Markdown("### Actions")

            discover_btn = gr.Button("Discover Clusters", variant="primary")
            cooccurrence_btn = gr.Button("Analyze Co-occurrence")
            leader_btn = gr.Button("Detect Leaders")
            multiplier_btn = gr.Button("Update Multipliers")
            clusters_refresh_btn = gr.Button("Refresh")

            action_status = gr.Textbox(
                label="Status",
                interactive=False,
                lines=2,
                elem_id="explorer-clusters-status",
            )

    with gr.Row():
        total_clusters = gr.Number(label="Total Clusters", value=0, interactive=False)
        avg_cohesion = gr.Number(label="Avg Cohesion", value=0.0, interactive=False, precision=2)
        avg_size = gr.Number(label="Avg Size", value=0.0, interactive=False, precision=1)
        with_leader = gr.Number(label="With Leader", value=0, interactive=False)

    def update_stats(df: pd.DataFrame) -> tuple[int, float, float, int]:
        if df.empty:
            return 0, 0.0, 0.0, 0
        total = len(df)
        avg_coh = df["Cohesion"].astype(float).mean() if "Cohesion" in df else 0.0
        avg_sz = df["Size"].mean() if "Size" in df else 0.0
        leaders = sum(1 for ldr in df["Leader"] if ldr != "None") if "Leader" in df else 0
        return total, avg_coh, avg_sz, leaders

    def on_refresh() -> tuple[pd.DataFrame, int, float, float, int]:
        df = _sync_fetch_clusters()
        stats = update_stats(df)
        return df, *stats

    def on_discover() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_run_discovery()
        stats = update_stats(df)
        return status, df, *stats

    def on_cooccurrence() -> str:
        return _sync_run_cooccurrence()

    def on_detect_leaders() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_detect_leaders()
        stats = update_stats(df)
        return status, df, *stats

    def on_update_multipliers() -> tuple[str, pd.DataFrame, int, float, float, int]:
        status, df = _sync_update_multipliers()
        stats = update_stats(df)
        return status, df, *stats

    # Wire up events
    clusters_refresh_btn.click(
        fn=on_refresh,
        outputs=[cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )
    discover_btn.click(
        fn=on_discover,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )
    cooccurrence_btn.click(fn=on_cooccurrence, outputs=[action_status])
    leader_btn.click(
        fn=on_detect_leaders,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )
    multiplier_btn.click(
        fn=on_update_multipliers,
        outputs=[action_status, cluster_table, total_clusters, avg_cohesion, avg_size, with_leader],
    )

    # Cluster selection -> sidebar
    def on_cluster_select(evt: gr.SelectData, df: pd.DataFrame) -> dict[str, Any]:
        if evt.index[0] < len(df):
            row = df.iloc[evt.index[0]]
            cluster_data = {
                "id": row.get("ID", ""),
                "size": row.get("Size", 0),
                "cohesion_score": float(row.get("Cohesion", "0")),
                "signal_multiplier": float(row.get("Multiplier", "1.0").replace("x", "")),
                "leader_address": row.get("Leader", "None"),
                "members": [],  # Would need full data for this
            }
            return {"type": "cluster", "data": cluster_data}
        return {"type": None, "data": None}

    cluster_table.select(
        fn=on_cluster_select,
        inputs=[cluster_table],
        outputs=[sidebar_state],
    )
