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


def _run_wallet_discovery_sync() -> str:
    """Run wallet discovery (sync wrapper for Gradio handler).

    Returns:
        Status message string.
    """
    try:
        from walltrack.core.discovery.wallet_discovery import (  # noqa: PLC0415
            WalletDiscoveryService,
        )

        async def _async(supabase):
            service = WalletDiscoveryService()
            result = await service.run_wallet_discovery()

            tokens_processed = result.get("tokens_processed", 0)
            wallets_new = result.get("wallets_new", 0)
            wallets_existing = result.get("wallets_existing", 0)
            errors = result.get("errors", 0)

            if errors > 0 and wallets_new == 0:
                return f"❌ Error: {errors} errors encountered"

            if tokens_processed == 0:
                return "ℹ️ No tokens to discover wallets from (run token discovery first)"  # noqa: RUF001

            if wallets_new > 0:
                return (
                    f"✅ Complete: {wallets_new} new wallets discovered "
                    f"from {tokens_processed} tokens "
                    f"({wallets_existing} already existed)"
                )

            return f"ℹ️ No new wallets found from {tokens_processed} tokens"  # noqa: RUF001

        return run_async_with_client(_async)

    except Exception as e:
        log.error("wallet_discovery_failed", error=str(e))
        return f"❌ Error: {e}"


def _run_behavioral_profiling_sync() -> str:
    """Run behavioral profiling for all wallets (sync wrapper for Gradio handler).

    Profiles all wallets in database that have sufficient transaction history.
    Story 3.3 - Manual trigger for batch profiling.

    Returns:
        Status message string with profiling results.
    """
    try:
        from walltrack.core.behavioral.profiler import BehavioralProfiler  # noqa: PLC0415
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )
        from walltrack.services.helius.client import HeliusClient  # noqa: PLC0415

        async def _async(supabase):
            helius_client = HeliusClient()
            try:
                # Get dependencies
                config_repo = ConfigRepository(supabase)
                wallet_repo = WalletRepository(supabase)
                profiler = BehavioralProfiler(helius_client, config_repo)

                # Get all wallets
                wallets = await wallet_repo.get_all(limit=1000)

                if not wallets:
                    return "ℹ️ No wallets found in database"  # noqa: RUF001

                # Profile each wallet
                profiled_count = 0
                skipped_count = 0
                error_count = 0

                for wallet in wallets:
                    try:
                        # Analyze wallet behavior
                        profile = await profiler.analyze(wallet.wallet_address)

                        # Skip if insufficient data (AC4 compliance)
                        if profile is None:
                            skipped_count += 1
                            continue

                        # Update wallet with behavioral data
                        success = await wallet_repo.update_behavioral_profile(
                            wallet_address=wallet.wallet_address,
                            position_size_style=profile.position_size_style or "unknown",
                            position_size_avg=float(profile.position_size_avg),
                            hold_duration_avg=profile.hold_duration_avg,
                            hold_duration_style=profile.hold_duration_style or "unknown",
                            behavioral_confidence=profile.confidence,
                        )

                        if success:
                            profiled_count += 1
                        else:
                            error_count += 1

                    except Exception as e:
                        log.warning(
                            "wallet_profiling_failed",
                            wallet_address=wallet.wallet_address[:8] + "...",
                            error=str(e),
                        )
                        error_count += 1

                # Build result message
                total = len(wallets)
                if profiled_count > 0:
                    msg = f"✅ Profiled {profiled_count}/{total} wallets"
                    if skipped_count > 0:
                        msg += f" ({skipped_count} skipped - insufficient data)"
                    if error_count > 0:
                        msg += f" ({error_count} errors)"
                    return msg
                elif skipped_count > 0:
                    return f"ℹ️ All {total} wallets have insufficient data (< 10 trades)"  # noqa: RUF001
                else:
                    return f"❌ Profiling failed for all {total} wallets"

            finally:
                await helius_client.close()

        return run_async_with_client(_async)

    except Exception as e:
        log.error("behavioral_profiling_failed", error=str(e))
        return f"❌ Error: {e}"


def _run_decay_check_sync() -> str:
    """Run decay detection for all wallets (sync wrapper for Gradio handler).

    Checks all wallets for decay conditions (rolling window, consecutive losses, dormancy).
    Story 3.4 - Manual trigger for batch decay detection.

    Returns:
        Status message string with decay check results.
    """
    try:
        from walltrack.core.wallets.decay_detector import DecayConfig, DecayDetector  # noqa: PLC0415
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )
        from walltrack.data.supabase.repositories.decay_event_repo import (  # noqa: PLC0415
            DecayEventRepository,
        )
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )
        from walltrack.services.helius.client import HeliusClient  # noqa: PLC0415

        async def _async(supabase):
            helius_client = HeliusClient()
            try:
                # Get dependencies
                config_repo = ConfigRepository(supabase)
                wallet_repo = WalletRepository(supabase)
                event_repo = DecayEventRepository(supabase)

                # Load decay configuration from database
                decay_config = await DecayConfig.from_db(config_repo)
                detector = DecayDetector(decay_config, wallet_repo, helius_client)

                # Get all wallets
                wallets = await wallet_repo.get_all(limit=1000)

                if not wallets:
                    return "ℹ️ No wallets found in database"  # noqa: RUF001

                # Check each wallet for decay
                checked_count = 0
                event_count = 0
                skipped_count = 0
                error_count = 0

                for wallet in wallets:
                    try:
                        # Check wallet for decay conditions
                        event = await detector.check_wallet_decay(wallet.wallet_address)

                        checked_count += 1

                        # If decay event occurred, log it
                        if event:
                            await event_repo.create(event)
                            event_count += 1

                    except Exception as e:
                        log.warning(
                            "wallet_decay_check_failed",
                            wallet_address=wallet.wallet_address[:8] + "...",
                            error=str(e),
                        )
                        error_count += 1

                # Build result message
                total = len(wallets)
                if checked_count > 0:
                    msg = f"✅ Checked {checked_count}/{total} wallets"
                    if event_count > 0:
                        msg += f" ({event_count} decay events detected)"
                    if error_count > 0:
                        msg += f" ({error_count} errors)"
                    return msg
                else:
                    return f"❌ Decay check failed for all {total} wallets"

            finally:
                await helius_client.close()

        return run_async_with_client(_async)

    except Exception as e:
        log.error("decay_check_failed", error=str(e))
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

            # Wallet Discovery Section (Story 3.1)
            gr.Markdown("---")
            gr.Markdown(
                """
                ### Wallet Discovery

                Discover smart money wallets from token holders.
                Requires tokens to be discovered first.
                """
            )

            wallet_discovery_status = gr.Textbox(
                value="Ready",
                label="Status",
                interactive=False,
            )

            run_wallet_discovery_btn = gr.Button("Run Wallet Discovery", variant="primary")

            # Wire up wallet discovery button
            run_wallet_discovery_btn.click(
                fn=lambda: "🔄 Discovering wallets...",
                outputs=[wallet_discovery_status],
            ).then(
                fn=_run_wallet_discovery_sync,
                outputs=[wallet_discovery_status],
            )

            # Behavioral Profiling Section (Story 3.3)
            gr.Markdown("---")
            gr.Markdown("### Behavioral Profiling")
            gr.Markdown(
                "Analyze trading behavior patterns for all wallets. "
                "Profiles position sizing and hold duration styles. "
                "Requires minimum 10 trades per wallet."
            )

            profiling_status = gr.Textbox(
                value="Ready",
                label="Status",
                interactive=False,
            )

            run_profiling_btn = gr.Button("Run Behavioral Profiling", variant="primary")

            # Wire up profiling button
            run_profiling_btn.click(
                fn=lambda: "🔄 Profiling wallets...",
                outputs=[profiling_status],
            ).then(
                fn=_run_behavioral_profiling_sync,
                outputs=[profiling_status],
            )

            # Decay Detection Section (Story 3.4)
            gr.Markdown("---")
            gr.Markdown("### Wallet Decay Detection")
            gr.Markdown(
                "Check wallets for performance decay (low win rate, consecutive losses, dormancy). "
                "Updates wallet status and generates decay events."
            )

            decay_check_status = gr.Textbox(
                value="Ready",
                label="Status",
                interactive=False,
            )

            run_decay_check_btn = gr.Button("🔍 Check Wallet Decay", variant="primary")

            # Wire up decay check button
            run_decay_check_btn.click(
                fn=lambda: "🔄 Checking wallets for decay...",
                outputs=[decay_check_status],
            ).then(
                fn=_run_decay_check_sync,
                outputs=[decay_check_status],
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
