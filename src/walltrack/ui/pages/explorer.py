"""Explorer page for WallTrack dashboard.

Provides exploration views for tokens, signals, wallets, and clusters.
Story 2.3: Token Explorer View implementation.
"""

import gradio as gr
import structlog

from walltrack.core.analysis import analyze_all_wallets
from walltrack.ui import run_async_with_client

log = structlog.get_logger(__name__)


# =============================================================================
# Formatting Utilities
# =============================================================================


def _format_age(age_minutes: int | None) -> str:
    """Format age in minutes to relative time.

    Args:
        age_minutes: Age in minutes or None.

    Returns:
        Formatted relative time string.

    Examples:
        >>> _format_age(45)
        '45m'
        >>> _format_age(180)
        '3h'
        >>> _format_age(2880)
        '2d'
        >>> _format_age(3000)
        '2d 2h'
    """
    if age_minutes is None:
        return "N/A"
    if age_minutes < 60:
        return f"{age_minutes}m"
    if age_minutes < 1440:  # 24 hours
        hours = age_minutes // 60
        return f"{hours}h"
    days = age_minutes // 1440
    hours = (age_minutes % 1440) // 60
    if hours > 0:
        return f"{days}d {hours}h"
    return f"{days}d"


# =============================================================================
# Data Fetching
# =============================================================================


def _fetch_wallets() -> list:
    """Fetch all wallets from database.

    Returns:
        List of Wallet objects, empty list if no wallets or on error.
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository  # noqa: PLC0415

        async def _get_wallets(client):
            repo = WalletRepository(client=client)
            return await repo.get_all(limit=1000)

        return run_async_with_client(_get_wallets)

    except Exception as e:
        log.error("wallets_fetch_failed", error=str(e))
        return []


def _fetch_wallets_by_status(status_filter: str | None = None) -> list:
    """Fetch wallets filtered by status from database (DB-level filtering for performance).

    Story 3.5 Task 7.3 - Database-level filtering instead of client-side filtering.

    Args:
        status_filter: Status filter value ("All", "Watchlisted", "Profiled", etc.) or None.

    Returns:
        List of Wallet objects matching the status filter, empty list if no wallets or on error.
    """
    try:
        from walltrack.data.models.wallet import WalletStatus  # noqa: PLC0415
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository  # noqa: PLC0415

        # Map UI filter value to WalletStatus enum
        status_map = {
            "Watchlisted": WalletStatus.WATCHLISTED,
            "Profiled": WalletStatus.PROFILED,
            "Ignored": WalletStatus.IGNORED,
            "Blacklisted": WalletStatus.BLACKLISTED,
            "Flagged": WalletStatus.FLAGGED,
            "Removed": WalletStatus.REMOVED,
            "Discovered": WalletStatus.DISCOVERED,
        }

        async def _get_wallets_filtered(client):
            repo = WalletRepository(client=client)

            # "All" or None - fetch all wallets
            if not status_filter or status_filter == "All":
                return await repo.get_all(limit=1000)

            # Specific status - use database filtering for performance
            wallet_status = status_map.get(status_filter)
            if not wallet_status:
                # Unknown status - return all
                return await repo.get_all(limit=1000)

            # DB-level filtering (20-100x performance gain)
            return await repo.get_wallets_by_status(wallet_status)

        return run_async_with_client(_get_wallets_filtered)

    except Exception as e:
        log.error("wallets_fetch_by_status_failed", status_filter=status_filter, error=str(e))
        return []


def _add_to_watchlist(wallet_address: str) -> str:
    """Add wallet to watchlist manually (Story 3.5 Task 8.2).

    Args:
        wallet_address: Solana wallet address.

    Returns:
        Status message string.
    """
    try:
        from decimal import Decimal  # noqa: PLC0415
        from datetime import datetime  # noqa: PLC0415
        from walltrack.data.models.wallet import WalletStatus, WatchlistDecision  # noqa: PLC0415
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository  # noqa: PLC0415

        async def _async(client):
            wallet_repo = WalletRepository(client)

            # Create manual watchlist decision
            decision = WatchlistDecision(
                status=WalletStatus.WATCHLISTED,
                score=Decimal("1.0000"),  # Max score for manual addition
                reason="Manually added by operator",
                timestamp=datetime.utcnow(),
            )

            # Update wallet with manual override
            await wallet_repo.update_watchlist_status(
                wallet_address=wallet_address,
                decision=decision,
                manual=True,
            )

            log.info(
                "wallet_manually_added_to_watchlist",
                wallet_address=wallet_address[:8] + "...",
            )

            return "✅ Wallet added to watchlist"

        return run_async_with_client(_async)

    except Exception as e:
        log.error("manual_watchlist_add_failed", wallet_address=wallet_address[:8] + "...", error=str(e))
        return f"❌ Error: {str(e)}"


def _remove_from_watchlist(wallet_address: str) -> str:
    """Remove wallet from watchlist manually (Story 3.5 Task 8.2).

    Args:
        wallet_address: Solana wallet address.

    Returns:
        Status message string.
    """
    try:
        from decimal import Decimal  # noqa: PLC0415
        from datetime import datetime  # noqa: PLC0415
        from walltrack.data.models.wallet import WalletStatus, WatchlistDecision  # noqa: PLC0415
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository  # noqa: PLC0415

        async def _async(client):
            wallet_repo = WalletRepository(client)

            # Create manual ignore decision
            decision = WatchlistDecision(
                status=WalletStatus.IGNORED,
                score=Decimal("0.0000"),
                reason="Manually removed by operator",
                timestamp=datetime.utcnow(),
            )

            # Update wallet with manual override
            await wallet_repo.update_watchlist_status(
                wallet_address=wallet_address,
                decision=decision,
                manual=True,
            )

            log.info(
                "wallet_manually_removed_from_watchlist",
                wallet_address=wallet_address[:8] + "...",
            )

            return "✅ Wallet removed from watchlist"

        return run_async_with_client(_async)

    except Exception as e:
        log.error("manual_watchlist_remove_failed", wallet_address=wallet_address[:8] + "...", error=str(e))
        return f"❌ Error: {str(e)}"


def _blacklist_wallet(wallet_address: str, reason: str = "Manually blacklisted") -> str:
    """Blacklist wallet manually (Story 3.5 Task 8.2).

    Args:
        wallet_address: Solana wallet address.
        reason: Reason for blacklisting.

    Returns:
        Status message string.
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository  # noqa: PLC0415

        async def _async(client):
            wallet_repo = WalletRepository(client)

            # Blacklist wallet
            await wallet_repo.blacklist_wallet(
                wallet_address=wallet_address,
                reason=reason,
            )

            log.warning(
                "wallet_manually_blacklisted",
                wallet_address=wallet_address[:8] + "...",
                reason=reason,
            )

            return f"✅ Wallet blacklisted: {reason}"

        return run_async_with_client(_async)

    except Exception as e:
        log.error("manual_blacklist_failed", wallet_address=wallet_address[:8] + "...", error=str(e))
        return f"❌ Error: {str(e)}"


def _format_wallet_address(address: str) -> str:
    """Format wallet address for display (truncate to 8...8).

    Args:
        address: Full Solana wallet address.

    Returns:
        Truncated address string (8 first + 8 last chars).

    Example:
        >>> _format_wallet_address("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
        '9xQeWvG8...9PusVFin'
    """
    if len(address) > 16:
        return f"{address[:8]}...{address[-8:]}"
    return address


def _format_decay_status(status: str) -> str:
    """Format decay status with emoji.

    Args:
        status: Decay status value (ok, flagged, downgraded, dormant).

    Returns:
        Formatted status string with emoji prefix.

    Examples:
        >>> _format_decay_status("ok")
        '🟢 OK'
        >>> _format_decay_status("flagged")
        '🟡 Flagged'
    """
    status_map = {
        "ok": "🟢 OK",
        "flagged": "🟡 Flagged",
        "downgraded": "🔴 Downgraded",
        "dormant": "⚪ Dormant",
    }
    return status_map.get(status, status)


def _filter_wallets_by_status(wallets: list, status_filter: str) -> list:
    """Filter wallets by status for display.

    Story 3.5 Task 7.3 - Filter wallets by wallet_status.

    Args:
        wallets: List of Wallet objects.
        status_filter: Status filter value ("All", "Watchlisted", "Profiled", etc.).

    Returns:
        Filtered list of Wallet objects.
    """
    if status_filter == "All":
        return wallets

    # Map UI filter value to database status value
    status_map = {
        "Watchlisted": "watchlisted",
        "Profiled": "profiled",
        "Ignored": "ignored",
        "Blacklisted": "blacklisted",
        "Flagged": "flagged",
        "Removed": "removed",
        "Discovered": "discovered",
    }

    target_status = status_map.get(status_filter)
    if not target_status:
        return wallets

    # Filter wallets by status
    return [
        wallet
        for wallet in wallets
        if (
            wallet.wallet_status.value if hasattr(wallet.wallet_status, "value") else wallet.wallet_status
        )
        == target_status
    ]


def _format_wallets_for_table(wallets: list) -> list[list[str]]:
    """Format wallets for table display with performance metrics and watchlist status.

    Args:
        wallets: List of Wallet objects.

    Returns:
        List of rows, each row is [Address, First Seen, Discovered From, Status, Watchlist Score, Score, Win Rate, PnL, Entry Delay, Trades, Confidence, Decay Status].
    """
    if not wallets:
        return []

    # Format for table with performance metrics + watchlist status (Story 3.5 Task 7.1)
    # Story 3.1 Task 5: Added discovery_date and token_source columns
    rows = []
    for wallet in wallets:
        # Format discovery_date (Story 3.1 Task 5)
        if hasattr(wallet, "discovery_date") and wallet.discovery_date:
            # discovery_date is either a string or datetime object
            if isinstance(wallet.discovery_date, str):
                # Parse ISO format string (e.g., "2024-12-20T12:00:00+00:00")
                from datetime import datetime  # noqa: PLC0415
                try:
                    dt = datetime.fromisoformat(wallet.discovery_date.replace("Z", "+00:00"))
                    first_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    first_seen_str = wallet.discovery_date[:16]  # Fallback: truncate
            else:
                # Datetime object
                first_seen_str = wallet.discovery_date.strftime("%Y-%m-%d %H:%M")
        else:
            first_seen_str = "N/A"

        # Format token_source (Story 3.1 Task 5)
        if hasattr(wallet, "token_source") and wallet.token_source:
            # Truncate token address for readability (first 4 + last 4 chars)
            token_addr = wallet.token_source
            discovered_from_str = f"{token_addr[:4]}...{token_addr[-4:]}"
        else:
            discovered_from_str = "N/A"

        # Format wallet_status with emoji (Story 3.5 Task 7.1)
        status_emoji_map = {
            "watchlisted": "🟢",
            "profiled": "⚪",
            "ignored": "🔴",
            "blacklisted": "⚫",
            "flagged": "🟡",
            "removed": "🟤",
            "discovered": "🔵",
        }
        status_value = wallet.wallet_status.value if hasattr(wallet.wallet_status, "value") else wallet.wallet_status
        status_emoji = status_emoji_map.get(status_value, "⚪")
        status_str = f"{status_emoji} {status_value.capitalize()}"

        # Format watchlist_score (Story 3.5 Task 7.1)
        if wallet.watchlist_score is not None:
            watchlist_score_str = f"{float(wallet.watchlist_score):.4f}"
        else:
            watchlist_score_str = "N/A"

        # Format PnL with color coding
        pnl_value = wallet.pnl_total if wallet.pnl_total is not None else 0.0
        if pnl_value > 0:
            pnl_str = f"+{pnl_value:.4f} SOL"
        elif pnl_value < 0:
            pnl_str = f"{pnl_value:.4f} SOL"
        else:
            pnl_str = "0.0000 SOL"

        # Format entry delay (convert seconds to human-readable)
        entry_delay = wallet.entry_delay_seconds if wallet.entry_delay_seconds is not None else 0
        if entry_delay >= 3600:
            delay_str = f"{entry_delay // 3600}h"
        elif entry_delay >= 60:
            delay_str = f"{entry_delay // 60}min"
        elif entry_delay > 0:
            delay_str = f"{entry_delay}s"
        else:
            delay_str = "-"

        # Format confidence with emoji
        confidence_emoji_map = {
            "high": "🟢",
            "medium": "🟡",
            "low": "🟠",
            "unknown": "⚪",
        }
        confidence_emoji = confidence_emoji_map.get(wallet.metrics_confidence, "⚪")
        confidence_str = f"{confidence_emoji} {wallet.metrics_confidence.capitalize()}"

        rows.append(
            [
                _format_wallet_address(wallet.wallet_address),
                first_seen_str,  # First seen date (Story 3.1 Task 5)
                discovered_from_str,  # Discovered from token (Story 3.1 Task 5)
                status_str,  # Wallet status (watchlisted/profiled/ignored/etc) - Story 3.5
                watchlist_score_str,  # Watchlist score (0.0000-1.0000 or N/A) - Story 3.5
                f"{wallet.score:.2f}",  # Overall score (0.0-1.0)
                f"{wallet.win_rate:.1f}%",  # Win rate (0.0-100.0)
                pnl_str,  # Total PnL in SOL
                delay_str,  # Entry delay (human-readable)
                str(wallet.total_trades),  # Total trades count
                confidence_str,  # Confidence level with emoji
                _format_decay_status(wallet.decay_status),  # Decay status (ok/flagged/etc)
            ]
        )

    return rows


def _load_wallets() -> tuple[list[list[str]], list]:
    """Reload wallets from database and format for table display.

    Used after watchlist operations to refresh the UI.
    Story 3.5 Task 8.1 - Manual override controls.

    Returns:
        Tuple of (formatted wallet data for table, list of Wallet objects).
    """
    wallets = _fetch_wallets()
    formatted_data = _format_wallets_for_table(wallets)
    return formatted_data, wallets


# =============================================================================
# Page Render
# =============================================================================


def render() -> None:
    """Render the explorer page content.

    Story 3.1 Task 8: Refactored from Accordions to Tabs + Sidebar (UX Design aligned).

    Creates tabbed views for exploring:
    - Signals
    - Wallets
    - Clusters

    Note: Token management has been moved to the dedicated Tokens page.
    """
    with gr.Column():
        gr.Markdown(
            """
            # Explorer

            Explore signals, wallets, and clusters.

            *Token management is now available in the **Tokens** page.*
            """
        )

        # Story 3.1 Task 8: Dedicated Sidebar for Wallet Context (UX Design)
        # Pattern: gr.Sidebar(position="right", open=False) - same as Tokens page
        # UX Design: Sidebar shows origin discovery, metrics, cluster relations, manual controls
        with gr.Sidebar(position="right", open=False) as wallet_sidebar:
            gr.Markdown("## 👛 Wallet Details")
            wallet_detail_display = gr.Markdown("*Select a wallet to view details*")

            # Story 3.5 Task 8.1: Manual override controls (moved from inline panel to sidebar)
            gr.Markdown("---")
            gr.Markdown("### Manual Controls")

            selected_wallet_addr = gr.State(value="")  # Store selected wallet address

            add_watchlist_btn = gr.Button(
                "Add to Watchlist",
                variant="primary",
                visible=False,
            )
            remove_watchlist_btn = gr.Button(
                "Remove from Watchlist",
                variant="secondary",
                visible=False,
            )
            blacklist_btn = gr.Button(
                "Blacklist Wallet",
                variant="stop",
                visible=False,
            )

            manual_control_status = gr.Textbox(
                label="Status",
                interactive=False,
                placeholder="Select an action",
                visible=False,
            )

        # Story 3.1 Task 8: Tabs structure (replaces Accordions)
        # UX Design: Explorer page uses gr.Tabs for Signals, Wallets, Clusters
        with gr.Tabs() as explorer_tabs:
            # Tab 1: Signals - Story 5.5
            with gr.Tab("Signals"):
                gr.Markdown(
                    """
                    ### Signal Explorer

                    *Coming in Story 5.5 - Signal Logging & Explorer View*

                    View and filter trading signals with:
                    - Signal score breakdown
                    - Wallet attribution
                    - Token details
                    - Timestamp and status
                    """
                )

            # Tab 2: Wallets - Story 3.2 Task 6 (Updated with performance metrics)
            with gr.Tab("Wallets"):
                # Fetch wallets once and cache in State (same pattern as Tokens)
                wallets = _fetch_wallets()
                wallets_state = gr.State(value=wallets)
                wallets_data = _format_wallets_for_table(wallets)

                if wallets_data:
                    # Story 3.5 Task 7.2: Add status filter dropdown
                    status_filter = gr.Dropdown(
                        choices=["All", "Watchlisted", "Profiled", "Ignored", "Blacklisted", "Flagged"],
                        value="All",
                        label="Filter by Status",
                        interactive=True,
                    )

                    wallets_table = gr.Dataframe(
                        value=wallets_data,
                        headers=["Address", "First Seen", "Discovered From", "Status", "Watchlist Score", "Score", "Win Rate", "PnL", "Entry Delay", "Trades", "Confidence", "Decay Status"],
                        datatype=["str", "str", "str", "str", "str", "str", "str", "str", "str", "str", "str", "str"],
                        interactive=False,
                        wrap=True,
                    )

                    # NOTE: Performance analysis now runs automatically via WalletProfilingWorker
                    # No manual "Analyze" button needed - workers handle this autonomously

                    # Story 3.1 Task 8: Event handler refactored for Sidebar (replaced inline detail panel)
                    def _on_wallet_select(
                        evt: gr.SelectData,
                        cached_wallets: list,
                    ) -> tuple[dict, str, str, dict, dict, dict, dict]:
                        """Handle wallet row selection - display details in sidebar (Story 3.1 Task 8).
    
                        Args:
                            evt: Gradio SelectData event.
                            cached_wallets: List of Wallet objects from State.
    
                        Returns:
                            Tuple of (sidebar open, detail markdown, wallet address, add_btn visibility, remove_btn visibility, blacklist_btn visibility, status_visibility).
                        """
                        if evt.index is None:
                            return (
                                gr.update(open=False),  # Close sidebar
                                "*Select a wallet to view details*",
                                "",
                                gr.update(visible=False),
                                gr.update(visible=False),
                                gr.update(visible=False),
                                gr.update(visible=False),
                            )
    
                        row_idx = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index
    
                        try:
                            if row_idx >= len(cached_wallets):
                                return (
                                    gr.update(open=False),  # Close sidebar
                                    "*Select a wallet to view details*",
                                    "",
                                    gr.update(visible=False),
                                    gr.update(visible=False),
                                    gr.update(visible=False),
                                    gr.update(visible=False),
                                )
    
                            wallet = cached_wallets[row_idx]
    
                            if wallet:
                                # Story 3.5 Task 8.1: Determine button visibility based on wallet_status
                                wallet_status = (
                                    wallet.wallet_status.value
                                    if hasattr(wallet.wallet_status, "value")
                                    else wallet.wallet_status
                                )
                                is_watchlisted = wallet_status == "watchlisted"
    
                                # Add button visible if NOT watchlisted
                                # Remove button visible if watchlisted
                                add_btn_visible = not is_watchlisted
                                remove_btn_visible = is_watchlisted
                                # Build detail markdown with performance metrics
                                full_address = wallet.wallet_address
                                discovery_date = (
                                    wallet.discovery_date.strftime("%Y-%m-%d %H:%M")
                                    if wallet.discovery_date
                                    else "N/A"
                                )
                                token_source_display = (
                                    f"`{wallet.token_source[:8]}...{wallet.token_source[-4:]}`"
                                    if len(wallet.token_source) > 12
                                    else f"`{wallet.token_source}`"
                                )
                                
                                # Format performance metrics
                                pnl_value = wallet.pnl_total if wallet.pnl_total is not None else 0.0
                                pnl_display = f"{pnl_value:+.4f} SOL" if pnl_value != 0 else "0.0000 SOL"
                                
                                entry_delay = wallet.entry_delay_seconds if wallet.entry_delay_seconds is not None else 0
                                if entry_delay >= 3600:
                                    delay_display = f"{entry_delay // 3600}h"
                                elif entry_delay >= 60:
                                    delay_display = f"{entry_delay // 60}min"
                                elif entry_delay > 0:
                                    delay_display = f"{entry_delay}s"
                                else:
                                    delay_display = "-"
                                
                                metrics_updated = (
                                    wallet.metrics_last_updated.strftime("%Y-%m-%d %H:%M")
                                    if wallet.metrics_last_updated
                                    else "Never"
                                )
    
                                # Format confidence with low-data warning (AC4)
                                confidence_display = wallet.metrics_confidence.capitalize() if wallet.metrics_confidence else "Unknown"
                                if wallet.metrics_confidence == "low":
                                    total_trades = wallet.total_trades if wallet.total_trades is not None else 0
                                    confidence_display += f" ⚠️ Limited data ({total_trades} trades)"

                                # Story 3.3 Task 5: Format behavioral profile metrics
                                # Position Size
                                pos_size_avg = wallet.position_size_avg if wallet.position_size_avg else 0.0
                                pos_size_display = f"{pos_size_avg:.2f} SOL"
                                pos_size_style = wallet.position_size_style or "unknown"
                                if pos_size_style == "small":
                                    pos_size_badge = "🟢 Small"
                                elif pos_size_style == "medium":
                                    pos_size_badge = "🟡 Medium"
                                elif pos_size_style == "large":
                                    pos_size_badge = "🔴 Large"
                                else:
                                    pos_size_badge = "⚪ Unknown"

                                # Hold Duration
                                hold_duration_avg = wallet.hold_duration_avg if wallet.hold_duration_avg else 0
                                if hold_duration_avg >= 86400:  # >= 1 day
                                    days = hold_duration_avg // 86400
                                    hours = (hold_duration_avg % 86400) // 3600
                                    if hours > 0:
                                        hold_duration_display = f"{days}d {hours}h"
                                    else:
                                        hold_duration_display = f"{days}d"
                                elif hold_duration_avg >= 3600:  # >= 1 hour
                                    hours = hold_duration_avg // 3600
                                    minutes = (hold_duration_avg % 3600) // 60
                                    if minutes > 0:
                                        hold_duration_display = f"{hours}h {minutes}m"
                                    else:
                                        hold_duration_display = f"{hours}h"
                                elif hold_duration_avg >= 60:  # >= 1 minute
                                    minutes = hold_duration_avg // 60
                                    hold_duration_display = f"{minutes}m"
                                elif hold_duration_avg > 0:
                                    hold_duration_display = f"{hold_duration_avg}s"
                                else:
                                    hold_duration_display = "-"

                                hold_duration_style = wallet.hold_duration_style or "unknown"
                                if hold_duration_style == "scalper":
                                    hold_style_badge = "⚡ Scalper"
                                elif hold_duration_style == "day_trader":
                                    hold_style_badge = "📊 Day Trader"
                                elif hold_duration_style == "swing_trader":
                                    hold_style_badge = "📈 Swing Trader"
                                elif hold_duration_style == "position_trader":
                                    hold_style_badge = "💎 Position Trader"
                                else:
                                    hold_style_badge = "⚪ Unknown"

                                # Behavioral Confidence
                                behavioral_conf = wallet.behavioral_confidence or "unknown"
                                behavioral_conf_display = behavioral_conf.capitalize()

                                behavioral_updated = (
                                    wallet.behavioral_last_updated.strftime("%Y-%m-%d %H:%M")
                                    if wallet.behavioral_last_updated
                                    else "Never"
                                )

                                # Story 3.1 Task 8: Sidebar content (UX Design aligned)
                                # Sections: Header, Performance, Behavioral Profile, Cluster, Manual Controls
                                detail_md = f"""
    ### 👛 Wallet: `{full_address[:4]}...{full_address[-4:]}`

    **Score:** {wallet.score:.2f} | **Win Rate:** {wallet.win_rate:.1f}% | **Decay:** {_format_decay_status(wallet.decay_status)}

    ---

    ### 📊 Performance Metrics
    
    | Metric | Value |
    |--------|-------|
    | **Win Rate** | {wallet.win_rate:.1f}% |
    | **Total PnL** | {pnl_display} |
    | **Entry Delay** | {delay_display} |
    | **Total Trades** | {wallet.total_trades if wallet.total_trades is not None else 0} |
    | **Confidence** | {confidence_display} |
    | **Last Updated** | {metrics_updated} |

    ---

    ### 🧠 Behavioral Profile

    | Metric | Value |
    |--------|-------|
    | **Position Size** | {pos_size_badge} - {pos_size_display} |
    | **Hold Duration** | {hold_style_badge} - {hold_duration_display} |
    | **Confidence** | {behavioral_conf_display} |
    | **Last Analyzed** | {behavioral_updated} |

    ---

    ### 🔗 Cluster
    
    **Status:** _Coming in Story 4.5_
    
    ---
    """
                                return (
                                    gr.update(open=True),  # Open sidebar
                                    detail_md,
                                    full_address,
                                    gr.update(visible=add_btn_visible),
                                    gr.update(visible=remove_btn_visible),
                                    gr.update(visible=True),  # Blacklist button always visible
                                    gr.update(visible=True),  # Status textbox visible
                                )
    
                        except Exception as e:
                            log.error("wallet_select_failed", error=str(e))
                            error_msg = (
                                "⚠️ **Error loading wallet details**\n\n"
                                "Please try again or refresh the page."
                            )
                            return (
                                gr.update(open=True),  # Open sidebar to show error
                                error_msg,
                                "",
                                gr.update(visible=False),
                                gr.update(visible=False),
                                gr.update(visible=False),
                                gr.update(visible=False),
                            )
    
                        return (
                            gr.update(open=False),  # Close sidebar
                            "*Select a wallet to view details*",
                            "",
                            gr.update(visible=False),
                            gr.update(visible=False),
                            gr.update(visible=False),
                            gr.update(visible=False),
                        )
    
                    # Story 3.5 Task 7.3: Wire up status filter
                    def _on_status_filter_change(filter_value: str, cached_wallets: list) -> tuple[list[list[str]], list]:
                        """Filter wallets table by status using database-level filtering.
    
                        Story 3.5 Task 7.3 - DB-level filtering for 20-100x performance gain.
    
                        Args:
                            filter_value: Selected filter value ("All", "Watchlisted", etc.).
                            cached_wallets: Unused (kept for backward compatibility with event handler).
    
                        Returns:
                            Tuple of (formatted wallet data for table, refreshed wallet list for State).
                        """
                        # DB-level filtering (not client-side) for performance
                        refreshed_wallets = _fetch_wallets_by_status(filter_value)
                        formatted_data = _format_wallets_for_table(refreshed_wallets)
                        return formatted_data, refreshed_wallets
    
                    status_filter.change(
                        fn=_on_status_filter_change,
                        inputs=[status_filter, wallets_state],
                        outputs=[wallets_table, wallets_state],  # Update both table and state with DB-filtered wallets
                    )
    
                    # Story 3.1 Task 8: Updated select handler for Sidebar (7 outputs)
                    wallets_table.select(
                        fn=_on_wallet_select,
                        inputs=[wallets_state],
                        outputs=[
                            wallet_sidebar,  # Sidebar open/close
                            wallet_detail_display,  # Markdown content
                            selected_wallet_addr,  # Wallet address state
                            add_watchlist_btn,  # Add button visibility
                            remove_watchlist_btn,  # Remove button visibility
                            blacklist_btn,  # Blacklist button visibility
                            manual_control_status,  # Status textbox visibility
                        ],
                    )
    
                    # Story 3.5 Task 8.1: Manual override button handlers
                    add_watchlist_btn.click(
                        fn=_add_to_watchlist,
                        inputs=[selected_wallet_addr],
                        outputs=[manual_control_status],
                    ).then(
                        fn=_load_wallets,
                        inputs=[],
                        outputs=[wallets_table, wallets_state],
                    )
    
                    remove_watchlist_btn.click(
                        fn=_remove_from_watchlist,
                        inputs=[selected_wallet_addr],
                        outputs=[manual_control_status],
                    ).then(
                        fn=_load_wallets,
                        inputs=[],
                        outputs=[wallets_table, wallets_state],
                    )
    
                    blacklist_btn.click(
                        fn=_blacklist_wallet,
                        inputs=[selected_wallet_addr],
                        outputs=[manual_control_status],
                    ).then(
                        fn=_load_wallets,
                        inputs=[],
                        outputs=[wallets_table, wallets_state],
                    )
                else:
                    # Empty state
                    gr.Markdown(
                        """
                        ### No wallets discovered yet

                        Wallets are discovered automatically from tokens.

                        **Autonomous workflow:**
                        1. Add tokens via **Tokens** tab > **Discovery Settings**
                        2. Wallet discovery runs automatically (~2 min intervals)
                        3. Wallets appear here once discovered and profiled

                        **No manual intervention required** ✅
                        """
                    )

            # Tab 3: Clusters - Story 4.5
            with gr.Tab("Clusters"):
                gr.Markdown(
                    """
                    ### Cluster Explorer

                    *Coming in Story 4.5 - Cluster Drill-Down & Score Amplification*

                    Analyze wallet clusters:
                    - Funding relationships
                    - Synchronized behavior
                    - Leader identification
                    - Cluster scores
                    """
                )
