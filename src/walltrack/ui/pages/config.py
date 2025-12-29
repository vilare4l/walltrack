"""Config page for WallTrack dashboard.

Provides configuration interface for system settings including:
- Trading Wallet connection
- Discovery settings (future)
- Signal settings (future)
- Risk management (future)
- Execution settings (future)

IMPORTANT: Gradio event handlers must be synchronous.
Use run_async_with_client() helper for async operations to avoid event loop conflicts.
"""

from typing import Any

import gradio as gr
import structlog

from walltrack.core.wallet import truncate_address
from walltrack.ui import run_async_with_client

log = structlog.get_logger(__name__)


def _get_stored_wallet_sync() -> str | None:
    """Get stored wallet address (sync wrapper).

    Returns:
        Wallet address if stored, None otherwise.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _get(client):
            repo = ConfigRepository(client)
            return await repo.get_trading_wallet()

        return run_async_with_client(_get)
    except Exception as e:
        log.warning("config_get_wallet_failed", error=str(e))
        return None


def _connect_wallet_sync(address: str) -> tuple[str, str, dict]:
    """Connect wallet (sync wrapper for Gradio handler).

    Args:
        address: Solana wallet address to validate and store.

    Returns:
        Tuple of (status_html, input_value, button_visibility_update dict).
    """
    if not address or not address.strip():
        return (
            '<span style="color: #ef4444;">⚠️ Please enter a wallet address</span>',
            address,
            gr.update(visible=True),  # Keep Connect visible
        )

    address = address.strip()

    try:
        from walltrack.core.wallet.validator import validate_wallet_on_chain  # noqa: PLC0415
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _validate_and_store(client):
            # Validate wallet
            result = await validate_wallet_on_chain(address)

            if not result.is_valid:
                return (
                    f'<span style="color: #ef4444;">❌ {result.error_message}</span>',
                    address,
                    gr.update(visible=True),  # Keep Connect visible
                )

            # Store in config
            repo = ConfigRepository(client)
            await repo.set_trading_wallet(address)

            truncated = truncate_address(address)
            return (
                f'<span style="color: #22c55e;">🟢 Connected: {truncated}</span>',
                address,
                gr.update(visible=False),  # Hide Connect, show Disconnect
            )

        return run_async_with_client(_validate_and_store)

    except Exception as e:
        log.error("config_connect_wallet_failed", error=str(e))
        return (
            f'<span style="color: #ef4444;">❌ Connection error: {e}</span>',
            address,
            gr.update(visible=True),
        )


def _disconnect_wallet_sync() -> tuple[str, str, Any]:
    """Disconnect wallet (sync wrapper for Gradio handler).

    Returns:
        Tuple of (status_html, cleared_input, button_visibility_update).
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _clear(client):
            repo = ConfigRepository(client)
            await repo.clear_trading_wallet()

        run_async_with_client(_clear)

        return (
            '<span style="color: #6b7280;">🔴 Not Connected</span>',
            "",  # Clear input
            gr.update(visible=True),  # Show Connect button
        )

    except Exception as e:
        log.error("config_disconnect_wallet_failed", error=str(e))
        return (
            f'<span style="color: #ef4444;">❌ Error disconnecting: {e}</span>',
            "",
            gr.update(visible=True),
        )


# Config keys for surveillance
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


def _run_discovery_sync() -> str:
    """Run token discovery (sync wrapper for Gradio handler).

    Returns:
        Status message string.
    """
    try:
        from walltrack.core.discovery.token_discovery import (  # noqa: PLC0415
            TokenDiscoveryService,
        )
        from walltrack.services.dexscreener.client import DexScreenerClient  # noqa: PLC0415

        async def _async(supabase):
            dex_client = DexScreenerClient()
            try:
                service = TokenDiscoveryService(supabase, dex_client)
                result = await service.run_discovery()

                if result.status == "error":
                    return f"❌ Error: {result.error_message}"

                if result.tokens_found > 0:
                    return (
                        f"✅ Complete: {result.tokens_found} tokens "
                        f"({result.new_tokens} new, {result.updated_tokens} updated)"
                    )
                return "ℹ️ No new tokens found"  # noqa: RUF001
            finally:
                await dex_client.close()

        return run_async_with_client(_async)

    except Exception as e:
        log.error("discovery_failed", error=str(e))
        return f"❌ Error: {e}"


def _get_initial_wallet_status() -> tuple[str, str, bool]:
    """Get initial wallet status for page load.

    Returns:
        Tuple of (status_html, address_value, connect_button_visible).
    """
    stored = _get_stored_wallet_sync()
    if stored:
        truncated = truncate_address(stored)
        return (
            f'<span style="color: #22c55e;">🟢 Connected: {truncated}</span>',
            stored,
            False,  # Hide Connect, show Disconnect
        )
    return (
        '<span style="color: #6b7280;">🔴 Not Connected</span>',
        "",
        True,  # Show Connect, hide Disconnect
    )


def render() -> None:
    """Render the config page content.

    Creates accordion sections for various configuration areas.
    """
    with gr.Column():
        gr.Markdown(
            """
            # Configuration

            Manage WallTrack system settings.
            """
        )

        # Trading Wallet Section (Story 1.5)
        with gr.Accordion("Trading Wallet", open=True):
            gr.Markdown(
                """
                ### Connect Your Trading Wallet

                Enter your Solana wallet address to enable trading.
                The system will validate the address on the Solana network.
                """
            )

            # Get initial state
            initial_status, initial_address, connect_visible = _get_initial_wallet_status()

            address_input = gr.Textbox(
                label="Wallet Address",
                placeholder="Enter Solana wallet address (e.g., 9WzDX...xYz1)",
                value=initial_address,
                max_lines=1,
            )

            with gr.Row():
                connect_btn = gr.Button(
                    "Connect Wallet",
                    variant="primary",
                    visible=connect_visible,
                )
                disconnect_btn = gr.Button(
                    "Disconnect",
                    variant="secondary",
                    visible=not connect_visible,
                )

            status_display = gr.HTML(
                value=initial_status,
                label="Status",
            )

            gr.Markdown("**Balance:** SOL: 0.00 *(real balance coming in Story 8.1)*")

            # Wire up event handlers
            connect_btn.click(
                fn=_connect_wallet_sync,
                inputs=[address_input],
                outputs=[status_display, address_input, connect_btn],
            ).then(
                fn=lambda: gr.update(visible=True),
                outputs=[disconnect_btn],
            )

            disconnect_btn.click(
                fn=_disconnect_wallet_sync,
                outputs=[status_display, address_input, connect_btn],
            ).then(
                fn=lambda: gr.update(visible=False),
                outputs=[disconnect_btn],
            )

        # Token Discovery Section (Story 2.1 + 2.2)
        with gr.Accordion("Discovery", open=True):
            gr.Markdown(
                """
                ### Token Discovery

                Discover trending tokens from DexScreener.
                Fetches boosted tokens and latest profiles, then stores them in the database.
                """
            )

            discovery_status = gr.Textbox(
                value="Ready",
                label="Status",
                interactive=False,
            )

            run_discovery_btn = gr.Button("Run Discovery", variant="primary")

            # Wire up discovery button
            run_discovery_btn.click(
                fn=lambda: "🔄 Running discovery...",
                outputs=[discovery_status],
            ).then(
                fn=_run_discovery_sync,
                outputs=[discovery_status],
            )

            # Surveillance Schedule Section (Story 2.2)
            gr.Markdown("---")
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

        with gr.Accordion("Wallet Settings", open=False):
            gr.Markdown(
                """
                ### Wallet Configuration

                *Coming in Story 3.5 - Wallet Blacklist/Watchlist Management*

                Manage wallet lists:
                - Watchlist (priority wallets)
                - Blacklist (excluded wallets)
                - Decay thresholds
                """
            )

        with gr.Accordion("Signal Settings", open=False):
            gr.Markdown(
                """
                ### Signal Configuration

                *Coming in Story 5.4 - Threshold Application*

                Configure signal thresholds:
                - Minimum score threshold
                - Factor weights
                - Token characteristics
                """
            )

        with gr.Accordion("Risk Management", open=False):
            gr.Markdown(
                """
                ### Risk Settings

                *Coming in Story 7.5 - Risk Configuration*

                Configure risk parameters:
                - Drawdown limits
                - Position limits
                - Circuit breakers
                """
            )

        with gr.Accordion("Execution", open=False):
            gr.Markdown(
                """
                ### Execution Settings

                *Coming in Story 8.2 - Mode Toggle*

                Configure execution:
                - Simulation / Live mode
                - Jupiter settings
                - Slippage tolerance
                """
            )
