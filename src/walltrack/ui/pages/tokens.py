"""Tokens page for WallTrack dashboard.

Provides token management interface including:
- Token list with details sidebar
- Token discovery trigger
- Surveillance schedule configuration

Created from Explorer accordion to provide dedicated token management.
"""

import gradio as gr
import structlog

from walltrack.ui import run_async_with_client

log = structlog.get_logger(__name__)


# =============================================================================
# Helper Functions - Token Display
# =============================================================================


def _fetch_tokens() -> list:
    """Fetch all tokens from database (sync wrapper).

    Returns:
        List of Token objects from database.
    """
    try:
        from walltrack.data.supabase.repositories.token_repo import (  # noqa: PLC0415
            TokenRepository,
        )

        async def _async(client):
            repo = TokenRepository(client)
            return await repo.get_all(limit=1000)

        return run_async_with_client(_async) or []
    except Exception as e:
        log.error("tokens_fetch_failed", error=str(e))
        return []


def _count_wallets_by_token() -> dict[str, int]:
    """Count wallets discovered for each token.

    Returns:
        Dict mapping token_mint to wallet count.
        Empty dict if no wallets or on error.
    """
    try:
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )

        async def _count(client):
            repo = WalletRepository(client=client)
            wallets = await repo.get_all(limit=10000)

            # Count wallets by token_source
            counts: dict[str, int] = {}
            for wallet in wallets:
                if wallet.token_source:
                    counts[wallet.token_source] = counts.get(wallet.token_source, 0) + 1

            return counts

        return run_async_with_client(_count)

    except Exception as e:
        log.error("wallet_count_by_token_failed", error=str(e))
        return {}


def _format_tokens_for_table(tokens: list) -> list[list[str]]:
    """Format tokens for table display.

    Returns:
        List of rows, each row is [Name, Symbol, Price, Market Cap, Discovered, Wallets].
    """
    if not tokens:
        return []

    # Get wallet counts by token (Story 3.1 implementation)
    wallet_counts = _count_wallets_by_token()

    rows = []
    for token in tokens:
        # Get wallet count for this token mint
        wallet_count = wallet_counts.get(token.mint, 0)
        wallet_display = str(wallet_count) if wallet_count > 0 else "0"

        # Format discovery date
        discovered_display = (
            token.created_at.strftime("%Y-%m-%d %H:%M")
            if token.created_at
            else "N/A"
        )

        rows.append([
            token.name or "Unknown",
            token.symbol or "???",
            _format_price(token.price_usd),
            _format_market_cap(token.market_cap),
            discovered_display,  # Discovery date/time
            wallet_display,  # Real wallet count from database
        ])

    return rows


def _format_price(price: float | None) -> str:
    """Format price for display."""
    if price is None:
        return "N/A"
    if price < 0.01:
        return f"${price:.6f}"
    return f"${price:.4f}"


def _format_market_cap(value: float | None) -> str:
    """Format market cap for display."""
    if value is None:
        return "N/A"
    if value >= 1_000_000:
        return f"${value/1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value/1_000:.2f}K"
    return f"${value:.2f}"


def _load_tokens() -> tuple[list[list[str]], list]:
    """Reload tokens from database and format for table display.

    Used to refresh the token list when new tokens are discovered.

    Returns:
        Tuple of (formatted token data for table, list of Token objects).
    """
    tokens = _fetch_tokens()
    formatted_data = _format_tokens_for_table(tokens)
    return formatted_data, tokens


# =============================================================================
# Helper Functions - Surveillance
# =============================================================================


CONFIG_KEY_SURVEILLANCE_ENABLED = "surveillance_enabled"
CONFIG_KEY_SURVEILLANCE_INTERVAL = "surveillance_interval_hours"

# Interval choices for dropdown (label, value)
INTERVAL_CHOICES = [
    ("1 hour", 1),
    ("2 hours", 2),
    ("4 hours (recommended)", 4),
    ("8 hours", 8),
]


def _get_surveillance_enabled() -> bool:
    """Check if surveillance is enabled.

    Returns:
        True if enabled (default), False otherwise.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            value = await repo.get_value(CONFIG_KEY_SURVEILLANCE_ENABLED)
            return value == "true" if value else True  # Default enabled

        return run_async_with_client(_async)
    except Exception as e:
        log.debug("config_get_surveillance_enabled_failed", error=str(e))
        return True  # Default enabled


def _get_surveillance_interval() -> int:
    """Get current surveillance interval from config.

    Returns:
        Interval in hours (default 4).
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            value = await repo.get_value(CONFIG_KEY_SURVEILLANCE_INTERVAL)
            return int(value) if value else 4  # Default 4 hours

        return run_async_with_client(_async)
    except Exception as e:
        log.debug("config_get_surveillance_interval_failed", error=str(e))
        return 4  # Default


def _set_surveillance_interval(hours: int) -> str:
    """Set surveillance interval and reschedule job.

    Args:
        hours: Interval in hours.

    Returns:
        Status message.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.scheduler.jobs import schedule_surveillance_job  # noqa: PLC0415

        async def _async(client):
            repo = ConfigRepository(client)
            await repo.set_value(CONFIG_KEY_SURVEILLANCE_INTERVAL, str(hours))

        run_async_with_client(_async)

        # Reschedule with new interval (only if enabled)
        if _get_surveillance_enabled():
            schedule_surveillance_job(interval_hours=hours)

        return f"✅ Interval set to {hours}h"

    except Exception as e:
        log.error("config_set_surveillance_interval_failed", error=str(e))
        return f"❌ Error: {e}"


def _toggle_surveillance(enabled: bool) -> str:
    """Enable or disable surveillance scheduler.

    Args:
        enabled: Whether to enable surveillance.

    Returns:
        Status message.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.scheduler.jobs import (  # noqa: PLC0415
            schedule_surveillance_job,
            unschedule_surveillance_job,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            await repo.set_value(CONFIG_KEY_SURVEILLANCE_ENABLED, str(enabled).lower())

        run_async_with_client(_async)

        if enabled:
            interval = _get_surveillance_interval()
            schedule_surveillance_job(interval_hours=interval)
            return "✅ Surveillance enabled"
        else:
            unschedule_surveillance_job()
            return "⏸️ Surveillance disabled"

    except Exception as e:
        log.error("config_toggle_surveillance_failed", error=str(e))
        return f"❌ Error: {e}"


def _get_next_run_display() -> str:
    """Get next scheduled run time for display.

    Returns:
        Human-readable next run time.
    """
    try:
        from datetime import UTC, datetime  # noqa: PLC0415

        from walltrack.scheduler.jobs import get_next_run_time  # noqa: PLC0415

        next_run = get_next_run_time()
        if next_run:
            # Parse ISO datetime and calculate relative time
            dt = datetime.fromisoformat(next_run.replace("Z", "+00:00"))
            now = datetime.now(UTC)
            diff = dt - now

            if diff.total_seconds() > 0:
                total_seconds = diff.total_seconds()
                hours = int(total_seconds / 3600)
                minutes = int((total_seconds % 3600) / 60)
                if hours > 0:
                    return f"in {hours}h {minutes}m"
                return f"in {minutes}m"
        return "Not scheduled"

    except Exception as e:
        log.debug("config_get_next_run_failed", error=str(e))
        return "Unknown"


# =============================================================================
# Page Render
# =============================================================================


def render() -> None:
    """Render the tokens page content.

    Creates token management interface with:
    - Token list table with sidebar details
    - Discovery trigger
    - Surveillance configuration
    """
    with gr.Column():
        gr.Markdown(
            """
            # 🪙 Tokens

            Manage token discovery and monitoring.
            """
        )

        # Token details sidebar (right side)
        with gr.Sidebar(position="right", open=False) as token_sidebar:
            gr.Markdown("## 🪙 Token Details")
            token_detail_display = gr.Markdown("*Select a token to view details*")

        # Token List Section
        with gr.Accordion("Token List", open=True):
            # Fetch tokens once and cache in State
            tokens = _fetch_tokens()
            tokens_state = gr.State(value=tokens)
            tokens_data = _format_tokens_for_table(tokens)

            if tokens_data:
                # Refresh button for reloading token list
                with gr.Row():
                    refresh_btn = gr.Button("🔄 Refresh", size="sm", variant="secondary")
                    tokens_info = gr.Markdown(f"*Showing {len(tokens_data)} tokens*")

                tokens_table = gr.Dataframe(
                    value=tokens_data,
                    headers=["Token", "Symbol", "Price", "Market Cap", "Discovered", "Wallets"],
                    datatype=["str", "str", "str", "str", "str", "str"],
                    interactive=False,
                    wrap=True,
                )

                def _on_token_select(
                    evt: gr.SelectData,
                    cached_tokens: list,
                ) -> tuple[dict, str]:  # gr.update() returns dict
                    """Handle token row selection - display details in sidebar."""
                    if evt.index is None:
                        return gr.update(open=False), "*Select a token to view details*"

                    # BUG FIX: evt.index can be list or tuple [row, col]
                    row_idx = evt.index[0] if isinstance(evt.index, (tuple, list)) else evt.index

                    try:
                        if row_idx >= len(cached_tokens):
                            return gr.update(open=False), "*Select a token to view details*"

                        token = cached_tokens[row_idx]

                        if token:
                            last_checked = (
                                token.last_checked.strftime("%Y-%m-%d %H:%M")
                                if token.last_checked
                                else "N/A"
                            )
                            discovered = (
                                token.created_at.strftime("%Y-%m-%d %H:%M")
                                if token.created_at
                                else "N/A"
                            )

                            detail_md = f"""
### {token.name or 'Unknown'}
**{token.symbol or '???'}**

---

### 🔗 Actions

[📊 **View on Dexscreener**](https://dexscreener.com/solana/{token.mint})

[🐦 **View on Birdeye**](https://birdeye.so/token/{token.mint}?chain=solana)

[🔍 **View on Solscan**](https://solscan.io/token/{token.mint})

---

#### Market Data
| Field | Value |
|-------|-------|
| **Price** | {_format_price(token.price_usd)} |
| **Market Cap** | {_format_market_cap(token.market_cap)} |
| **24h Volume** | {_format_market_cap(token.volume_24h)} |
| **Liquidity** | {_format_market_cap(token.liquidity_usd)} |

#### Info
| Field | Value |
|-------|-------|
| **Mint** | `{token.mint[:8]}...{token.mint[-4:]}` |
| **Discovered** | {discovered} |
| **Last Checked** | {last_checked} |
"""
                            return gr.update(open=True), detail_md

                    except Exception as e:
                        log.error("token_select_failed", error=str(e))
                        error_msg = (
                            "⚠️ **Error loading token details**\n\n"
                            "Please try again or click on another token."
                        )
                        return gr.update(open=True), error_msg

                    return gr.update(open=False), "*Select a token to view details*"

                tokens_table.select(
                    fn=_on_token_select,
                    inputs=[tokens_state],
                    outputs=[token_sidebar, token_detail_display],
                )

                # Wire up refresh button to reload tokens
                refresh_btn.click(
                    fn=_load_tokens,
                    inputs=[],
                    outputs=[tokens_table, tokens_state],
                ).then(
                    fn=lambda tokens: f"*Showing {len(tokens)} tokens*",
                    inputs=[tokens_state],
                    outputs=[tokens_info],
                )

            else:
                # Empty state
                gr.Markdown(
                    """
                    ### No tokens discovered yet

                    Run discovery below to find tokens.
                    """
                )

        # Discovery Settings Section - Surveillance only (Discovery Worker runs autonomously)
        with gr.Accordion("Discovery Settings", open=True):
            gr.Markdown(
                """
                ### Token Discovery & Surveillance

                **Token discovery runs automatically** via the Discovery Worker.
                Configure surveillance schedule below to automatically refresh token data.
                """
            )

            # Surveillance Schedule Section
            gr.Markdown("### Surveillance Schedule")
            gr.Markdown(
                "Automatically refresh token data at regular intervals. "
                "Changes take effect immediately."
            )

            with gr.Row():
                surveillance_enabled = gr.Checkbox(
                    value=_get_surveillance_enabled,
                    label="Enable Surveillance",
                    elem_id="surveillance-enabled",
                )

                current_interval = _get_surveillance_interval()
                interval_dropdown = gr.Dropdown(
                    choices=[(label, val) for label, val in INTERVAL_CHOICES],
                    value=current_interval,
                    label="Refresh Interval",
                    interactive=True,
                    elem_id="surveillance-interval",
                )

            with gr.Row():
                gr.Textbox(
                    value=_get_next_run_display,
                    label="Next Scheduled Run",
                    interactive=False,
                    every=30,  # Update every 30s
                    elem_id="next-run-display",
                )

                schedule_status = gr.Textbox(
                    value="",
                    label="Schedule Status",
                    interactive=False,
                    elem_id="schedule-status",
                )

            # Wire up surveillance controls
            surveillance_enabled.change(
                fn=_toggle_surveillance,
                inputs=[surveillance_enabled],
                outputs=[schedule_status],
            )

            interval_dropdown.change(
                fn=_set_surveillance_interval,
                inputs=[interval_dropdown],
                outputs=[schedule_status],
            )
