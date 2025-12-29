"""Explorer page for WallTrack dashboard.

Provides exploration views for tokens, signals, wallets, and clusters.
Story 2.3: Token Explorer View implementation.
"""

import gradio as gr
import structlog

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

        with gr.Accordion("Wallets", open=False):
            gr.Markdown(
                """
                ### Wallet Explorer

                *Coming in Story 3.2 - Wallet Performance Analysis*

                Explore tracked wallets with:
                - Performance metrics
                - Behavioral profile
                - Cluster membership
                - Watchlist/Blacklist status
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
