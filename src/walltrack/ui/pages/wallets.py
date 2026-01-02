"""Wallets page for WallTrack dashboard.

Provides wallet management interface including:
- Wallet list with details sidebar
- Wallet analysis trigger
- Watchlist management controls
- Status filtering

Created as dedicated page following Tokens page pattern.
"""

import gradio as gr
import structlog

from walltrack.ui import run_async_with_client

log = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions - Wallet Display
# =============================================================================


def _fetch_wallets() -> list:
    """Fetch all wallets from database (sync wrapper).

    Returns:
        List of Wallet objects from database.
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )

        async def _async(client):
            repo = WalletRepository(client)
            return await repo.get_all(limit=1000)

        return run_async_with_client(_async) or []
    except Exception as e:
        log.error("wallets_fetch_failed", error=str(e))
        return []


def _fetch_wallets_by_status(status_filter: str | None = None) -> list:
    """Fetch wallets filtered by status from database.

    Args:
        status_filter: Status filter value ("All", "Watchlisted", "Profiled", etc.) or None.

    Returns:
        List of Wallet objects matching the status filter, empty list if no wallets or on error.
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )

        async def _get_filtered(client):
            repo = WalletRepository(client=client)

            # Map UI filter to DB status value
            if not status_filter or status_filter == "All":
                return await repo.get_all(limit=1000)

            # Map UI names to WalletStatus enum values
            status_map = {
                "Watchlisted": "watchlisted",
                "Profiled": "profiled",
                "Ignored": "ignored",
                "Blacklisted": "blacklisted",
                "Flagged": "flagged",
            }

            db_status = status_map.get(status_filter)
            if not db_status:
                return await repo.get_all(limit=1000)

            return await repo.get_by_status(db_status, limit=1000)

        return run_async_with_client(_get_filtered)

    except Exception as e:
        log.error("wallets_fetch_by_status_failed", status=status_filter, error=str(e))
        return []


def _format_entry_delay(entry_delay_minutes: int | None) -> str:
    """Format entry delay for display.

    Args:
        entry_delay_minutes: Entry delay in minutes.

    Returns:
        Human-readable string like "5m", "2h 30m", "3d 4h".
    """
    if entry_delay_minutes is None:
        return "N/A"

    if entry_delay_minutes < 60:
        return f"{entry_delay_minutes}m"

    hours = entry_delay_minutes // 60
    minutes = entry_delay_minutes % 60

    if hours < 24:
        return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"

    days = hours // 24
    remaining_hours = hours % 24

    if remaining_hours > 0:
        return f"{days}d {remaining_hours}h"
    return f"{days}d"


def _format_decay_status(decay_status: str | None) -> str:
    """Format decay status for display with emoji indicators.

    Args:
        decay_status: Decay status value.

    Returns:
        Formatted string with emoji.
    """
    if not decay_status:
        return "N/A"

    # AC5: Correct badge colors (Code Review Fix 2026-01-01)
    status_map = {
        "ok": "🟢 OK",
        "flagged": "🟡 Flagged",
        "downgraded": "🔴 Downgraded",
        "dormant": "⚪ Dormant",
    }

    return status_map.get(decay_status.lower(), decay_status)


def _format_wallets_for_table(wallets: list) -> list[list[str]]:
    """Format wallets for table display.

    Returns:
        List of rows, each row is [Address, First Seen, Discovered From, Status, Watchlist Score, Score, Win Rate, PnL, Entry Delay, Trades, Confidence, Decay Status].
    """
    if not wallets:
        return []

    rows = []
    for wallet in wallets:
        # Format wallet address (truncated for display)
        address = wallet.wallet_address
        address_display = f"{address[:8]}...{address[-6:]}"

        # Format first seen timestamp
        first_seen = (
            wallet.discovery_date.strftime("%Y-%m-%d %H:%M")
            if wallet.discovery_date
            else "N/A"
        )

        # Format discovered from (token source)
        discovered_from = (
            f"{wallet.token_source[:8]}...{wallet.token_source[-6:]}"
            if wallet.token_source
            else "N/A"
        )

        # Format status (capitalize)
        status = (
            wallet.wallet_status.value.capitalize()
            if hasattr(wallet.wallet_status, "value")
            else str(wallet.wallet_status).capitalize()
        )

        # Format watchlist score
        watchlist_score = (
            f"{wallet.watchlist_score:.2f}"
            if wallet.watchlist_score is not None
            else "N/A"
        )

        # Format score
        score = f"{wallet.score:.2f}" if wallet.score is not None else "N/A"

        # Format win rate
        win_rate = (
            f"{wallet.win_rate * 100:.1f}%"
            if wallet.win_rate is not None
            else "N/A"
        )

        # Format PnL
        pnl = f"${wallet.pnl_total:.2f}" if wallet.pnl_total is not None else "N/A"

        # Format entry delay (Story 3.3 behavioral metric) - convert seconds to minutes
        entry_delay_mins = wallet.entry_delay_seconds // 60 if wallet.entry_delay_seconds else None
        delay_str = _format_entry_delay(entry_delay_mins)

        # Format confidence level (Story 3.3 behavioral metric)
        if wallet.behavioral_confidence:
            conf_map = {
                "high": "🟢 High",
                "medium": "🟡 Medium",
                "low": "🔴 Low",
                "unknown": "⚪ Unknown",
            }
            confidence_str = conf_map.get(wallet.behavioral_confidence, wallet.behavioral_confidence.capitalize())
        else:
            confidence_str = "N/A"

        rows.append(
            [
                address_display,  # Wallet address (truncated)
                first_seen,  # First seen timestamp
                discovered_from,  # Token source
                status,  # Wallet status
                watchlist_score,  # Watchlist score
                score,  # Overall score
                win_rate,  # Win rate percentage
                pnl,  # Total PnL
                delay_str,  # Entry delay (human-readable)
                str(wallet.total_trades),  # Total trades count
                confidence_str,  # Confidence level with emoji
                _format_decay_status(wallet.decay_status),  # Decay status
            ]
        )

    return rows


def _load_wallets(status_filter: str = "All") -> tuple[list[list[str]], list]:
    """Reload wallets from database and format for table display.

    Args:
        status_filter: Status filter value ("All", "Watchlisted", etc.).

    Returns:
        Tuple of (formatted wallet data for table, list of Wallet objects).
    """
    wallets = _fetch_wallets_by_status(status_filter)
    formatted_data = _format_wallets_for_table(wallets)
    return formatted_data, wallets


# =============================================================================
# Helper Functions - Wallet Actions
# =============================================================================




# =============================================================================
# Page Render
# =============================================================================


def render() -> None:
    """Render the wallets page content.

    Creates wallet management interface with:
    - Wallet list table with sidebar details
    - Analysis trigger
    - Status filtering
    - Manual watchlist controls
    """
    with gr.Column():
        gr.Markdown(
            """
            # 👛 Wallets

            Smart money wallet tracking and analysis.
            """
        )

        # Wallet details sidebar (right side)
        with gr.Sidebar(position="right", open=False) as wallet_sidebar:
            gr.Markdown("## 👛 Wallet Details")
            wallet_detail_display = gr.Markdown("*Select a wallet to view details*")


        # Wallet List Section
        with gr.Accordion("Wallet List", open=True):
            # Fetch wallets once and cache in State
            wallets = _fetch_wallets()
            wallets_state = gr.State(value=wallets)
            wallets_data = _format_wallets_for_table(wallets)

            if wallets_data:
                # Controls row: Refresh + Status Filter
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                    status_filter = gr.Dropdown(
                        choices=["All", "Watchlisted", "Profiled", "Ignored", "Blacklisted", "Flagged"],
                        value="All",
                        label="Filter by Status",
                        scale=2,
                    )
                    wallets_info = gr.Markdown(f"*Showing {len(wallets_data)} wallets*")

                wallets_table = gr.Dataframe(
                    value=wallets_data,
                    headers=[
                        "Address",
                        "First Seen",
                        "Discovered From",
                        "Status",
                        "Watchlist Score",
                        "Score",
                        "Win Rate",
                        "PnL",
                        "Entry Delay",
                        "Trades",
                        "Confidence",
                        "Decay Status",
                    ],
                    datatype=["str"] * 12,
                    interactive=False,
                    wrap=True,
                )

                def _on_wallet_select(
                    evt: gr.SelectData,
                    cached_wallets: list,
                ) -> tuple[dict, str]:  # gr.update() returns dict
                    """Handle wallet row selection - display details in sidebar."""
                    if evt.index is None:
                        return gr.update(open=False), "*Select a wallet to view details*"

                    # BUG FIX: evt.index can be list or tuple [row, col]
                    row_idx = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index

                    try:
                        if row_idx >= len(cached_wallets):
                            return gr.update(open=False), "*Select a wallet to view details*"

                        wallet = cached_wallets[row_idx]

                        if wallet:
                            first_seen = (
                                wallet.discovery_date.strftime("%Y-%m-%d %H:%M")
                                if wallet.discovery_date
                                else "N/A"
                            )
                            last_analyzed = (
                                wallet.metrics_last_updated.strftime("%Y-%m-%d %H:%M")
                                if wallet.metrics_last_updated
                                else "N/A"
                            )

                            # Full address for display
                            full_address = wallet.wallet_address

                            detail_md = f"""
### Wallet {wallet.wallet_address[:8]}...{wallet.wallet_address[-6:]}

**Status:** {wallet.wallet_status.value.capitalize() if hasattr(wallet.wallet_status, 'value') else str(wallet.wallet_status).capitalize()}
**Decay:** {_format_decay_status(wallet.decay_status)}

**Note:** Watchlist status is managed automatically by the Profiling Worker.

---

### 🔗 Actions

[📊 **View on Solscan**](https://solscan.io/account/{wallet.wallet_address})

[🔍 **View on Solana Explorer**](https://explorer.solana.com/address/{wallet.wallet_address})

---

#### Performance Metrics
| Metric | Value |
|--------|-------|
| **Win Rate** | {f"{wallet.win_rate * 100:.1f}%" if wallet.win_rate is not None else "N/A"} |
| **Total PnL** | {f"${wallet.pnl_total:.2f}" if wallet.pnl_total is not None else "N/A"} |
| **Score** | {f"{wallet.score:.2f}" if wallet.score is not None else "N/A"} |
| **Watchlist Score** | {f"{wallet.watchlist_score:.2f}" if wallet.watchlist_score is not None else "N/A"} |
| **Total Trades** | {wallet.total_trades or 0} |

#### Behavioral Patterns
| Metric | Value |
|--------|-------|
| **Entry Delay** | {_format_entry_delay(wallet.entry_delay_seconds // 60 if wallet.entry_delay_seconds else None)} |
| **Confidence** | {wallet.behavioral_confidence.capitalize() if wallet.behavioral_confidence else "N/A"} |

#### Info
| Field | Value |
|-------|-------|
| **Address** | `{full_address[:12]}...{full_address[-8:]}` |
| **Discovered From** | `{wallet.token_source[:8]}...{wallet.token_source[-6:] if wallet.token_source else "N/A"}` |
| **First Seen** | {first_seen} |
| **Last Analyzed** | {last_analyzed} |
"""
                            return gr.update(open=True), detail_md

                    except Exception as e:
                        log.error("wallet_select_failed", error=str(e))
                        error_msg = (
                            "⚠️ **Error loading wallet details**\n\n"
                            "Please try again or click on another wallet."
                        )
                        return gr.update(open=True), error_msg

                    return gr.update(open=False), "*Select a wallet to view details*"

                wallets_table.select(
                    fn=_on_wallet_select,
                    inputs=[wallets_state],
                    outputs=[wallet_sidebar, wallet_detail_display],
                )

                # Wire up refresh button
                def _refresh_wallets(current_filter: str):
                    """Refresh wallets with current filter."""
                    new_data, new_wallets = _load_wallets(current_filter)
                    return new_data, new_wallets, f"*Showing {len(new_data)} wallets*"

                refresh_btn.click(
                    fn=_refresh_wallets,
                    inputs=[status_filter],
                    outputs=[wallets_table, wallets_state, wallets_info],
                )

                # Wire up status filter
                status_filter.change(
                    fn=_refresh_wallets,
                    inputs=[status_filter],
                    outputs=[wallets_table, wallets_state, wallets_info],
                )

            else:
                # Empty state
                gr.Markdown(
                    """
                    ### No wallets discovered yet

                    Wallets will appear here after token discovery and analysis.
                    """
                )

        # Analysis Status Section - Workers run autonomously
        with gr.Accordion("Autonomous Workers Status", open=False):
            gr.Markdown(
                """
                ### Autonomous Wallet Processing

                All wallet analysis is performed automatically by background workers:

                - **Profiling Worker** (60s poll): Analyzes discovered wallets
                  - Performance metrics (win rate, PnL, score)
                  - Behavioral profiling (entry patterns, confidence)
                  - Auto-watchlist evaluation

                - **Decay Worker** (4h poll): Monitors profiled wallets
                  - Rolling window decay detection
                  - Consecutive loss tracking
                  - Dormancy detection

                Check the **Status Bar** (top of page) for real-time worker status.
                """
            )
