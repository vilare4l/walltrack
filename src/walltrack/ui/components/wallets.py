"""Wallet views and management for Gradio dashboard."""

from typing import Any

import gradio as gr
import httpx
import pandas as pd
import structlog

from walltrack.config.settings import get_settings

log = structlog.get_logger()


def get_api_client() -> httpx.AsyncClient:
    """Get async HTTP client for API calls."""
    settings = get_settings()
    return httpx.AsyncClient(
        base_url=f"http://localhost:{settings.port}",
        timeout=10.0,
    )


async def fetch_wallets(
    status_filter: str | None = None,
    min_score: float = 0.0,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Fetch wallets from API."""
    async with get_api_client() as client:
        params: dict[str, Any] = {"limit": limit, "min_score": min_score}
        if status_filter and status_filter != "all":
            params["status"] = status_filter

        response = await client.get("/api/wallets/wallets", params=params)
        response.raise_for_status()
        data: dict[str, Any] = response.json()
        wallets: list[dict[str, Any]] = data.get("wallets", [])
        return wallets


async def fetch_wallet_detail(address: str) -> dict[str, Any] | None:
    """Fetch wallet details from API."""
    async with get_api_client() as client:
        response = await client.get(f"/wallets/{address}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        result: dict[str, Any] = response.json()
        return result


async def add_wallet_to_watchlist(address: str) -> tuple[bool, str]:
    """Add wallet to watchlist and trigger profiling."""
    async with get_api_client() as client:
        try:
            response = await client.post(
                f"/wallets/{address}/profile",
                params={"force_update": True},
            )
            response.raise_for_status()
            return True, f"Wallet {address} added and profiled successfully"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to add wallet: {e.response.text}"


async def blacklist_wallet(address: str, reason: str) -> tuple[bool, str]:
    """Blacklist a wallet."""
    async with get_api_client() as client:
        try:
            response = await client.post(
                f"/wallets/{address}/blacklist",
                params={"reason": reason},
            )
            response.raise_for_status()
            return True, f"Wallet {address} blacklisted"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to blacklist: {e.response.text}"


async def unblacklist_wallet(address: str) -> tuple[bool, str]:
    """Remove wallet from blacklist."""
    async with get_api_client() as client:
        try:
            response = await client.delete(f"/wallets/{address}/blacklist")
            response.raise_for_status()
            return True, f"Wallet {address} removed from blacklist"
        except httpx.HTTPStatusError as e:
            return False, f"Failed to remove from blacklist: {e.response.text}"


def wallets_to_dataframe(wallets: list[dict[str, Any]]) -> pd.DataFrame:
    """Convert wallet list to pandas DataFrame for display."""
    if not wallets:
        return pd.DataFrame(
            columns=[
                "Address",
                "Status",
                "Score",
                "Win Rate",
                "Total PnL",
                "Trades",
                "Last Signal",
            ]
        )

    rows = []
    for w in wallets:
        profile = w.get("profile", {})
        last_signal = w.get("last_signal_at")
        rows.append(
            {
                "Address": w.get("address", "")[:12] + "...",
                "Full Address": w.get("address", ""),
                "Status": w.get("status", "active"),
                "Score": f"{w.get('score', 0):.2%}",
                "Win Rate": f"{profile.get('win_rate', 0):.1%}",
                "Total PnL": f"{profile.get('total_pnl', 0):.2f} SOL",
                "Trades": profile.get("total_trades", 0),
                "Last Signal": last_signal[:10] if last_signal else "-",
            }
        )

    return pd.DataFrame(rows)


def format_wallet_detail(wallet: dict[str, Any] | None) -> str:
    """Format wallet details for display."""
    if not wallet:
        return "No wallet selected"

    profile = wallet.get("profile", {})
    discovered_at = wallet.get("discovered_at")
    last_profiled_at = wallet.get("last_profiled_at")
    last_signal_at = wallet.get("last_signal_at")
    decay_detected_at = wallet.get("decay_detected_at")
    rolling_win_rate = wallet.get("rolling_win_rate")

    return f"""
## Wallet Details

**Address:** `{wallet.get('address', 'N/A')}`

**Status:** {wallet.get('status', 'N/A')}

**Score:** {wallet.get('score', 0):.2%}

---

### Performance Metrics

| Metric | Value |
|--------|-------|
| Win Rate | {profile.get('win_rate', 0):.1%} |
| Total PnL | {profile.get('total_pnl', 0):.2f} SOL |
| Avg PnL/Trade | {profile.get('avg_pnl_per_trade', 0):.4f} SOL |
| Total Trades | {profile.get('total_trades', 0)} |
| Avg Hold Time | {profile.get('avg_hold_time_hours', 0):.1f}h |
| Timing Percentile | {profile.get('timing_percentile', 0.5):.1%} |
| Avg Position | {profile.get('avg_position_size_sol', 0):.4f} SOL |

---

### Discovery Info

| Info | Value |
|------|-------|
| Discovered | {discovered_at[:10] if discovered_at else 'N/A'} |
| Discovery Count | {wallet.get('discovery_count', 0)} |
| Last Profiled | {last_profiled_at[:10] if last_profiled_at else 'Never'} |
| Last Signal | {last_signal_at[:10] if last_signal_at else 'Never'} |

---

### Decay Status

| Status | Value |
|--------|-------|
| Rolling Win Rate | {f'{rolling_win_rate:.1%}' if rolling_win_rate else 'N/A'} |
| Consecutive Losses | {wallet.get('consecutive_losses', 0)} |
| Decay Detected | {decay_detected_at[:10] if decay_detected_at else 'Never'} |
"""


# Event handler functions for UI


async def _load_wallets(status: str, score: float) -> pd.DataFrame:
    """Load wallets and return DataFrame."""
    try:
        status_val = None if status == "all" else status
        wallets = await fetch_wallets(status_filter=status_val, min_score=score)
        return wallets_to_dataframe(wallets)
    except Exception as e:
        log.error("wallet_load_error", error=str(e))
        return wallets_to_dataframe([])


async def _on_wallet_select(
    evt: gr.SelectData, df: pd.DataFrame
) -> tuple[str, str]:
    """Handle wallet selection."""
    try:
        if evt.index[0] < len(df):
            full_address = df.iloc[evt.index[0]].get("Full Address", "")
            if full_address:
                wallet = await fetch_wallet_detail(full_address)
                return full_address, format_wallet_detail(wallet)
    except Exception as e:
        log.error("wallet_select_error", error=str(e))
    return "", "No wallet selected"


async def _on_add_wallet(address: str) -> tuple[str, pd.DataFrame]:
    """Handle adding new wallet."""
    if not address or len(address) < 32:
        return "Invalid wallet address", pd.DataFrame()

    success, message = await add_wallet_to_watchlist(address)
    symbol = "Success:" if success else "Error:"

    # Refresh wallet list
    try:
        wallets = await fetch_wallets()
        df = wallets_to_dataframe(wallets)
    except Exception:
        df = pd.DataFrame()

    return f"{symbol} {message}", df


async def _on_blacklist(address: str, reason: str) -> tuple[str, str]:
    """Handle blacklisting wallet."""
    if not address:
        return "No wallet selected", ""
    if not reason:
        return "Please provide a reason", ""

    success, message = await blacklist_wallet(address, reason)

    wallet = await fetch_wallet_detail(address)
    status_msg = f"Success: {message}" if success else f"Error: {message}"
    return format_wallet_detail(wallet), status_msg


async def _on_unblacklist(address: str) -> tuple[str, str]:
    """Handle removing wallet from blacklist."""
    if not address:
        return "No wallet selected", ""

    success, message = await unblacklist_wallet(address)

    wallet = await fetch_wallet_detail(address)
    status_msg = f"Success: {message}" if success else f"Error: {message}"
    return format_wallet_detail(wallet), status_msg


def _create_wallet_list_ui() -> tuple[gr.Dropdown, gr.Slider, gr.Button, gr.Dataframe]:
    """Create the wallet list section UI components."""
    gr.Markdown("### Wallet Watchlist")

    with gr.Row():
        status_filter = gr.Dropdown(
            choices=["all", "active", "decay_detected", "blacklisted", "insufficient_data"],
            value="all",
            label="Status Filter",
            scale=1,
        )
        min_score = gr.Slider(
            minimum=0, maximum=1, value=0, step=0.05, label="Min Score", scale=1
        )
        refresh_btn = gr.Button("Refresh", scale=1)

    wallet_table = gr.Dataframe(
        headers=["Address", "Status", "Score", "Win Rate", "Total PnL", "Trades", "Last Signal"],
        datatype=["str", "str", "str", "str", "str", "number", "str"],
        interactive=False,
        row_count=20,
        col_count=(7, "fixed"),  # type: ignore[arg-type]
    )

    return status_filter, min_score, refresh_btn, wallet_table


def _create_wallet_detail_ui() -> tuple[gr.Textbox, gr.Markdown, gr.Textbox, gr.Button, gr.Button]:
    """Create the wallet detail section UI components."""
    gr.Markdown("### Wallet Details")

    selected_address = gr.Textbox(
        label="Selected Wallet",
        placeholder="Click a wallet to view details",
        interactive=False,
    )
    wallet_detail = gr.Markdown("Select a wallet to view details")

    with gr.Row():
        blacklist_reason = gr.Textbox(
            label="Blacklist Reason", placeholder="Enter reason...", scale=3
        )
        blacklist_btn = gr.Button("Blacklist", variant="stop", scale=1)

    unblacklist_btn = gr.Button("Remove from Blacklist", variant="secondary")

    return selected_address, wallet_detail, blacklist_reason, blacklist_btn, unblacklist_btn


def _create_add_wallet_ui() -> tuple[gr.Textbox, gr.Button, gr.Markdown]:
    """Create the add wallet section UI components."""
    gr.Markdown("---")
    with gr.Row():
        gr.Markdown("### Add Wallet to Watchlist")

    with gr.Row():
        new_wallet_address = gr.Textbox(
            label="Wallet Address",
            placeholder="Enter Solana wallet address...",
            scale=4,
        )
        add_wallet_btn = gr.Button("Add & Profile", variant="primary", scale=1)

    add_wallet_result = gr.Markdown("")

    return new_wallet_address, add_wallet_btn, add_wallet_result


def create_wallets_tab() -> None:
    """Create the wallets tab UI."""
    # Create UI sections
    with gr.Row():
        with gr.Column(scale=3):
            status_filter, min_score, refresh_btn, wallet_table = _create_wallet_list_ui()

        with gr.Column(scale=2):
            selected_address, wallet_detail, blacklist_reason, blacklist_btn, unblacklist_btn = (
                _create_wallet_detail_ui()
            )

    new_wallet_address, add_wallet_btn, add_wallet_result = _create_add_wallet_ui()

    # Wire up events
    load_inputs = [status_filter, min_score]
    refresh_btn.click(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])
    status_filter.change(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])
    min_score.change(fn=_load_wallets, inputs=load_inputs, outputs=[wallet_table])
    wallet_table.select(
        fn=_on_wallet_select, inputs=[wallet_table], outputs=[selected_address, wallet_detail]
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
