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


def _format_price(price: float | None) -> str:
    """Format price with appropriate decimals.

    Args:
        price: Price value in USD or None.

    Returns:
        Formatted price string with $ prefix.

    Examples:
        >>> _format_price(0.00001234)
        '$0.00001234'
        >>> _format_price(123.456)
        '$123.46'
        >>> _format_price(None)
        'N/A'
    """
    if price is None:
        return "N/A"
    if price < 0.0001:
        return f"${price:.8f}"
    if price < 0.01:
        return f"${price:.6f}"
    if price < 1:
        return f"${price:.4f}"
    return f"${price:.2f}"


def _format_market_cap(value: float | None) -> str:
    """Format large numbers with K/M/B suffix.

    Args:
        value: Numeric value or None.

    Returns:
        Formatted string with $ prefix and suffix.

    Examples:
        >>> _format_market_cap(1_500_000_000)
        '$1.5B'
        >>> _format_market_cap(2_500_000)
        '$2.5M'
        >>> _format_market_cap(None)
        'N/A'
    """
    if value is None:
        return "N/A"
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


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


def _fetch_tokens() -> list:
    """Fetch all tokens from database.

    Returns:
        List of Token objects, empty list if no tokens or on error.
    """
    try:
        from walltrack.data.supabase.repositories.token_repo import TokenRepository  # noqa: PLC0415

        async def _get_tokens(client):
            repo = TokenRepository(client)
            return await repo.get_all()

        return run_async_with_client(_get_tokens)

    except Exception as e:
        log.error("tokens_fetch_failed", error=str(e))
        return []


def _format_tokens_for_table(tokens: list) -> list[list[str]]:
    """Format tokens for table display.

    Args:
        tokens: List of Token objects.

    Returns:
        List of rows, each row is [Name, Symbol, Price, Market Cap, Age, Wallets].
    """
    if not tokens:
        return []

    # Format for table: [Name, Symbol, Price, Market Cap, Age, Wallets]
    # TODO (Story 3.1): Replace "N/A" with actual wallet count when Wallet Discovery is implemented
    rows = []
    for token in tokens:
        rows.append(
            [
                token.name or "Unknown",
                token.symbol or "???",
                _format_price(token.price_usd),
                _format_market_cap(token.market_cap),
                _format_age(token.age_minutes),
                "N/A",  # Wallet count - to be implemented in Story 3.1
            ]
        )

    return rows


def _fetch_wallets() -> list:
    """Fetch all wallets from database.

    Returns:
        List of Wallet objects, empty list if no wallets or on error.
    """
    try:
        from walltrack.data.repositories.wallet_repository import WalletRepository  # noqa: PLC0415

        async def _get_wallets(client):
            repo = WalletRepository(supabase_client=client.client)
            return await repo.list_wallets(limit=1000)

        return run_async_with_client(_get_wallets)

    except Exception as e:
        log.error("wallets_fetch_failed", error=str(e))
        return []


def _run_wallet_analysis_sync() -> str:
    """Run wallet performance analysis (sync wrapper for async operation).

    Returns:
        Status message string for display in UI.
    """
    try:
        from walltrack.data.repositories.wallet_repository import WalletRepository  # noqa: PLC0415
        from walltrack.services.helius.client import HeliusClient  # noqa: PLC0415

        async def _analyze(client):
            # Get Helius API key from environment
            import os  # noqa: PLC0415

            helius_api_key = os.getenv("HELIUS_API_KEY")
            if not helius_api_key:
                return "❌ Error: HELIUS_API_KEY not configured"

            # Initialize clients
            helius_client = HeliusClient(api_key=helius_api_key)
            wallet_repo = WalletRepository(supabase_client=client.client)

            # Run analysis
            log.info("starting_wallet_performance_analysis_from_ui")
            results = await analyze_all_wallets(
                helius_client=helius_client,
                wallet_repo=wallet_repo,
                max_concurrent=3,  # Limit concurrency to avoid API rate limits
            )

            success_count = len(results)
            log.info(
                "wallet_performance_analysis_complete",
                analyzed=success_count,
            )

            return f"✅ Analysis complete! Analyzed {success_count} wallets"

        return run_async_with_client(_analyze)

    except Exception as e:
        log.error("wallet_analysis_failed", error=str(e))
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
        "downgraded": "🟠 Downgraded",
        "dormant": "⚫ Dormant",
    }
    return status_map.get(status, status)


def _format_wallets_for_table(wallets: list) -> list[list[str]]:
    """Format wallets for table display with performance metrics.

    Args:
        wallets: List of Wallet objects.

    Returns:
        List of rows, each row is [Address, Score, Win Rate, PnL, Entry Delay, Trades, Confidence, Status].
    """
    if not wallets:
        return []

    # Format for table with performance metrics
    rows = []
    for wallet in wallets:
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
                f"{wallet.score:.2f}",  # Score (0.0-1.0)
                f"{wallet.win_rate:.1f}%",  # Win rate (0.0-100.0)
                pnl_str,  # Total PnL in SOL
                delay_str,  # Entry delay (human-readable)
                str(wallet.total_trades),  # Total trades count
                confidence_str,  # Confidence level with emoji
                _format_decay_status(wallet.decay_status),  # Decay status (ok/flagged/etc)
            ]
        )

    return rows


# =============================================================================
# Page Render
# =============================================================================


def render() -> None:
    """Render the explorer page content.

    Creates tabbed views for exploring:
    - Tokens (new - Story 2.3)
    - Signals
    - Wallets
    - Clusters
    """
    with gr.Column():
        gr.Markdown(
            """
            # Explorer

            Explore tokens, signals, wallets, and clusters.
            """
        )

        # Tokens accordion (first position, open by default) - Story 2.3
        with gr.Accordion("Tokens", open=True):
            # Fetch tokens once and cache in State (Issue #3 fix)
            tokens = _fetch_tokens()
            tokens_state = gr.State(value=tokens)
            tokens_data = _format_tokens_for_table(tokens)

            if tokens_data:
                tokens_table = gr.Dataframe(
                    value=tokens_data,
                    headers=["Token", "Symbol", "Price", "Market Cap", "Age", "Wallets"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

                # Inline detail panel (shown on select)
                with gr.Row(visible=False) as detail_row:
                    detail_display = gr.Markdown("*Select a token for details*")

                def _on_token_select(
                    evt: gr.SelectData,
                    cached_tokens: list,
                ) -> tuple[dict, str]:  # gr.update() returns dict
                    """Handle token row selection.

                    Args:
                        evt: Gradio SelectData event.
                        cached_tokens: List of Token objects from State (no re-fetch needed).

                    Returns:
                        Tuple of (row visibility update, detail markdown).
                    """
                    if evt.index is None:
                        return gr.update(visible=False), "*Select a token for details*"

                    row_idx = evt.index[0] if isinstance(evt.index, tuple) else evt.index

                    try:
                        # Use cached tokens from State (Issue #3 fix - no double fetch)
                        if row_idx >= len(cached_tokens):
                            return gr.update(visible=False), "*Select a token for details*"

                        token = cached_tokens[row_idx]

                        if token:
                            # Build detail markdown
                            mint_display = (
                                f"`{token.mint[:8]}...{token.mint[-4:]}`"
                                if len(token.mint) > 12
                                else f"`{token.mint}`"
                            )
                            last_checked = (
                                token.last_checked.strftime("%Y-%m-%d %H:%M")
                                if token.last_checked
                                else "N/A"
                            )

                            detail_md = f"""
### Token Details

| Field | Value |
|-------|-------|
| **Name** | {token.name or 'Unknown'} |
| **Symbol** | {token.symbol or '???'} |
| **Mint** | {mint_display} |
| **Price** | {_format_price(token.price_usd)} |
| **Market Cap** | {_format_market_cap(token.market_cap)} |
| **24h Volume** | {_format_market_cap(token.volume_24h)} |
| **Liquidity** | {_format_market_cap(token.liquidity_usd)} |
| **Age** | {_format_age(token.age_minutes)} |
| **Last Checked** | {last_checked} |
"""
                            return gr.update(visible=True), detail_md

                    except Exception as e:
                        log.error("token_select_failed", error=str(e))
                        # Issue #5 fix: User-visible error feedback
                        error_msg = (
                            "⚠️ **Error loading token details**\n\n"
                            "Please try again or refresh the page."
                        )
                        return gr.update(visible=True), error_msg

                    return gr.update(visible=False), "*Select a token for details*"

                tokens_table.select(
                    fn=_on_token_select,
                    inputs=[tokens_state],
                    outputs=[detail_row, detail_display],
                )
            else:
                # Empty state
                gr.Markdown(
                    """
                    ### No tokens discovered yet

                    Run discovery from the **Config** page to find tokens.

                    1. Navigate to **Config** > **Discovery Settings**
                    2. Click **Run Discovery**
                    3. Return here to see discovered tokens
                    """
                )

        # Existing accordions (unchanged)
        with gr.Accordion("Signals", open=False):
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

        # Wallets accordion - Story 3.2 Task 6 (Updated with performance metrics)
        with gr.Accordion("Wallets", open=False):
            # Fetch wallets once and cache in State (same pattern as Tokens)
            wallets = _fetch_wallets()
            wallets_state = gr.State(value=wallets)
            wallets_data = _format_wallets_for_table(wallets)

            if wallets_data:
                wallets_table = gr.Dataframe(
                    value=wallets_data,
                    headers=["Address", "Score", "Win Rate", "PnL", "Entry Delay", "Trades", "Confidence", "Status"],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

                # Performance Analysis Section (Story 3.2 Task 8)
                gr.Markdown("---")
                gr.Markdown(
                    """
                    ### Performance Analysis

                    Analyze wallet trading performance using Helius transaction history.
                    Calculates win rate, PnL, entry timing, and confidence metrics.
                    """
                )

                analysis_status = gr.Textbox(
                    value="Ready",
                    label="Status",
                    interactive=False,
                )

                analyze_btn = gr.Button("Analyze All Wallets", variant="primary")

                # Wire up analysis button
                analyze_btn.click(
                    fn=lambda: "🔄 Analyzing wallets...",
                    outputs=[analysis_status],
                ).then(
                    fn=_run_wallet_analysis_sync,
                    outputs=[analysis_status],
                )

                # Inline detail panel (shown on select)
                with gr.Row(visible=False) as wallet_detail_row:
                    wallet_detail_display = gr.Markdown("*Select a wallet for details*")

                def _on_wallet_select(
                    evt: gr.SelectData,
                    cached_wallets: list,
                ) -> tuple[dict, str]:
                    """Handle wallet row selection.

                    Args:
                        evt: Gradio SelectData event.
                        cached_wallets: List of Wallet objects from State.

                    Returns:
                        Tuple of (row visibility update, detail markdown).
                    """
                    if evt.index is None:
                        return gr.update(visible=False), "*Select a wallet for details*"

                    row_idx = evt.index[0] if isinstance(evt.index, tuple) else evt.index

                    try:
                        if row_idx >= len(cached_wallets):
                            return gr.update(visible=False), "*Select a wallet for details*"

                        wallet = cached_wallets[row_idx]

                        if wallet:
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

                            detail_md = f"""
### Wallet Details

#### Identification
| Field | Value |
|-------|-------|
| **Address** | `{full_address}` |
| **Score** | {wallet.score:.4f} |
| **Discovery Date** | {discovery_date} |
| **Token Source** | {token_source_display} |
| **Blacklisted** | {"Yes" if wallet.is_blacklisted else "No"} |

#### Performance Metrics
| Field | Value |
|-------|-------|
| **Win Rate** | {wallet.win_rate:.1f}% |
| **Total PnL** | {pnl_display} |
| **Entry Delay** | {delay_display} |
| **Total Trades** | {wallet.total_trades if wallet.total_trades is not None else 0} |
| **Confidence** | {confidence_display} |
| **Last Updated** | {metrics_updated} |

#### Status
| Field | Value |
|-------|-------|
| **Decay Status** | {_format_decay_status(wallet.decay_status)} |
| **Signals** | 0 *(Story 5.5)* |
| **Cluster** | none *(Story 4.5)* |
"""
                            return gr.update(visible=True), detail_md

                    except Exception as e:
                        log.error("wallet_select_failed", error=str(e))
                        error_msg = (
                            "⚠️ **Error loading wallet details**\n\n"
                            "Please try again or refresh the page."
                        )
                        return gr.update(visible=True), error_msg

                    return gr.update(visible=False), "*Select a wallet for details*"

                wallets_table.select(
                    fn=_on_wallet_select,
                    inputs=[wallets_state],
                    outputs=[wallet_detail_row, wallet_detail_display],
                )
            else:
                # Empty state
                gr.Markdown(
                    """
                    ### No wallets discovered yet

                    Run wallet discovery from the **Config** page.

                    1. Navigate to **Config** > **Discovery Settings**
                    2. Click **Run Token Discovery** first (if no tokens yet)
                    3. Click **Run Wallet Discovery**
                    4. Return here to see discovered wallets
                    """
                )

        with gr.Accordion("Clusters", open=False):
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
