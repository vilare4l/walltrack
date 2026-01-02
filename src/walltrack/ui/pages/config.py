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

                            # Story 3.5: Trigger watchlist evaluation after profiling
                            try:
                                from walltrack.core.wallets.watchlist import (  # noqa: PLC0415
                                    WatchlistEvaluator,
                                )
                                from walltrack.data.models.wallet import WalletStatus  # noqa: PLC0415

                                # Step 1: Mark wallet as 'profiled' (from 'discovered')
                                # (Status is actually updated by watchlist decision below)

                                # Step 2: Evaluate wallet against watchlist criteria
                                evaluator = WatchlistEvaluator(config_repo)
                                decision = await evaluator.evaluate_wallet(wallet)

                                # Step 3: Update wallet with watchlist decision (with transition logging)
                                await wallet_repo.update_watchlist_status(
                                    wallet_address=wallet.wallet_address,
                                    decision=decision,
                                    manual=False,
                                    previous_status=WalletStatus.PROFILED,  # AC1: Log status transition
                                )

                            except Exception as watchlist_error:
                                # Error handling: Don't block profiling if watchlist evaluation fails
                                log.warning(
                                    "wallet_watchlist_evaluation_failed",
                                    wallet_address=wallet.wallet_address[:8] + "...",
                                    error=str(watchlist_error),
                                )
                                # Still count as profiled even if watchlist eval failed

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


def _get_discovery_criteria_values() -> tuple[float, float]:
    """Get current discovery criteria values from config.

    Story 3.1 - Task 4b-4: Load discovery criteria for UI display.

    Returns:
        Tuple of (early_entry_minutes, min_profit_percent).
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            criteria = await repo.get_discovery_criteria()
            return (
                criteria.get("early_entry_minutes", 30.0),
                criteria.get("min_profit_percent", 50.0),
            )

        return run_async_with_client(_async)
    except Exception as e:
        log.debug("config_get_discovery_criteria_failed", error=str(e))
        return (30.0, 50.0)  # Defaults


def _update_discovery_criteria(
    early_entry_minutes: float,
    min_profit_percent: float,
) -> str:
    """Update wallet discovery criteria in config table.

    Story 3.1 - Task 4b-4: Save discovery criteria to config.

    Args:
        early_entry_minutes: Maximum minutes after token launch (5-120).
        min_profit_percent: Minimum profit percentage for profitable exit (10-200).

    Returns:
        Status message string.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(supabase):
            config_repo = ConfigRepository(supabase)

            # Save criteria to config table with dot-notation keys
            await config_repo.set_value("discovery.early_entry_minutes", str(int(early_entry_minutes)))
            await config_repo.set_value("discovery.min_profit_percent", str(int(min_profit_percent)))

            # Clear cache to force reload on next discovery run
            config_repo.clear_cache()

            log.info(
                "discovery_criteria_updated",
                early_entry_minutes=int(early_entry_minutes),
                min_profit_percent=int(min_profit_percent),
            )

        run_async_with_client(_async)

        return (
            f"✅ Discovery criteria updated:\n"
            f"  • Early Entry Window: {int(early_entry_minutes)} minutes\n"
            f"  • Min Profit: {int(min_profit_percent)}%"
        )

    except Exception as e:
        log.error("discovery_criteria_update_failed", error=str(e))
        return f"❌ Error: {e}"


def _update_watchlist_criteria(
    min_winrate: float,
    min_pnl: float,
    min_trades: float,
    max_decay: float,
) -> str:
    """Update watchlist evaluation criteria in config table.

    Story 3.5 - Task 6.2: Save watchlist criteria to config.

    Args:
        min_winrate: Minimum win rate (0.0-1.0).
        min_pnl: Minimum total PnL in SOL.
        min_trades: Minimum number of trades.
        max_decay: Maximum decay score (0.0-1.0).

    Returns:
        Status message string.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(supabase):
            config_repo = ConfigRepository(supabase)

            # Save each criterion to config table with dot-notation keys
            await config_repo.set_value("watchlist.min_winrate", str(min_winrate))
            await config_repo.set_value("watchlist.min_pnl", str(min_pnl))
            await config_repo.set_value("watchlist.min_trades", str(int(min_trades)))
            await config_repo.set_value("watchlist.max_decay_score", str(max_decay))

            # Clear cache to force reload on next evaluation
            config_repo.clear_cache()

            log.info(
                "watchlist_criteria_updated",
                min_winrate=min_winrate,
                min_pnl=min_pnl,
                min_trades=int(min_trades),
                max_decay=max_decay,
            )

        run_async_with_client(_async)

        return (
            f"✅ Watchlist criteria updated:\n"
            f"  • Min Win Rate: {min_winrate:.0%}\n"
            f"  • Min PnL: {min_pnl:.1f} SOL\n"
            f"  • Min Trades: {int(min_trades)}\n"
            f"  • Max Decay: {max_decay:.0%}"
        )

    except Exception as e:
        log.error("watchlist_criteria_update_failed", error=str(e))
        return f"❌ Error: {e}"


def _update_performance_criteria(min_profit_percent: float) -> str:
    """Update performance analysis criteria (Story 3.2 Task 4b UI).

    Args:
        min_profit_percent: Minimum profit percentage for win rate calculation (5-50%).

    Returns:
        Status message indicating success or failure.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            await repo.set_value("min_profit_percent", str(min_profit_percent))

            log.info(
                "performance_criteria_updated",
                min_profit_percent=min_profit_percent,
            )

        run_async_with_client(_async)

        return (
            f"✅ Performance criteria updated:\n"
            f"  • Min Profit for Win: {min_profit_percent:.0f}%\n\n"
            f"Changes will apply on next performance analysis."
        )

    except Exception as e:
        log.error("performance_criteria_update_failed", error=str(e))
        return f"❌ Error: {e}"


def _get_behavioral_criteria() -> tuple[float, float, float, float, float, float, float, float]:
    """Get behavioral profiling criteria from config (Story 3.3 Task 4b UI).

    Returns:
        Tuple of (
            position_size_small_max,
            position_size_medium_max,
            hold_duration_scalper_max,
            hold_duration_day_trader_max,
            hold_duration_swing_trader_max,
            confidence_high_min,
            confidence_medium_min,
            confidence_low_min,
        ).
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)
            criteria = await repo.get_behavioral_criteria()
            return (
                criteria.get("position_size_small_max", 0.5),
                criteria.get("position_size_medium_max", 2.0),
                criteria.get("hold_duration_scalper_max", 3600.0),
                criteria.get("hold_duration_day_trader_max", 86400.0),
                criteria.get("hold_duration_swing_trader_max", 604800.0),
                criteria.get("confidence_high_min", 20.0),
                criteria.get("confidence_medium_min", 10.0),
                criteria.get("confidence_low_min", 5.0),
            )

        return run_async_with_client(_async)
    except Exception as e:
        log.debug("config_get_behavioral_criteria_failed", error=str(e))
        return (0.5, 2.0, 3600.0, 86400.0, 604800.0, 20.0, 10.0, 5.0)  # Defaults


def _update_behavioral_criteria(
    position_size_small_max: float,
    position_size_medium_max: float,
    hold_duration_scalper_max: float,
    hold_duration_day_trader_max: float,
    hold_duration_swing_trader_max: float,
    confidence_high_min: float,
    confidence_medium_min: float,
    confidence_low_min: float,
) -> str:
    """Update behavioral profiling criteria in config (Story 3.3 Task 4b UI).

    Args:
        position_size_small_max: Max SOL for small positions (0.1-2.0).
        position_size_medium_max: Max SOL for medium positions (1.0-10.0).
        hold_duration_scalper_max: Max seconds for scalper (1800-7200).
        hold_duration_day_trader_max: Max seconds for day trader (3600-172800).
        hold_duration_swing_trader_max: Max seconds for swing trader (86400-1209600).
        confidence_high_min: Min trades for high confidence.
        confidence_medium_min: Min trades for medium confidence.
        confidence_low_min: Min trades for low confidence.

    Returns:
        Status message indicating success or failure.
    """
    try:
        from walltrack.data.supabase.repositories.config_repo import (  # noqa: PLC0415
            ConfigRepository,
        )

        async def _async(client):
            repo = ConfigRepository(client)

            # Set each behavioral parameter individually
            await repo.set_value("position_size_small_max", str(position_size_small_max))
            await repo.set_value("position_size_medium_max", str(position_size_medium_max))
            await repo.set_value("hold_duration_scalper_max", str(hold_duration_scalper_max))
            await repo.set_value("hold_duration_day_trader_max", str(hold_duration_day_trader_max))
            await repo.set_value("hold_duration_swing_trader_max", str(hold_duration_swing_trader_max))
            await repo.set_value("confidence_high_min", str(confidence_high_min))
            await repo.set_value("confidence_medium_min", str(confidence_medium_min))
            await repo.set_value("confidence_low_min", str(confidence_low_min))

            # Clear cache to force reload on next profiling run
            repo.clear_cache()

            log.info(
                "behavioral_criteria_updated",
                position_size_small_max=position_size_small_max,
                position_size_medium_max=position_size_medium_max,
                confidence_high_min=int(confidence_high_min),
            )

        run_async_with_client(_async)

        return (
            f"✅ Behavioral criteria updated:\n"
            f"  • Position Size Small: ≤{position_size_small_max} SOL\n"
            f"  • Position Size Large: >{position_size_medium_max} SOL\n"
            f"  • Scalper Hold: ≤{int(hold_duration_scalper_max/3600)}h\n"
            f"  • Day Trader Hold: ≤{int(hold_duration_day_trader_max/3600)}h\n"
            f"  • Swing Trader Hold: ≤{int(hold_duration_swing_trader_max/86400)}d\n"
            f"  • High Confidence: ≥{int(confidence_high_min)} trades"
        )

    except Exception as e:
        log.error("behavioral_criteria_update_failed", error=str(e))
        return f"❌ Error: {e}"


def _get_rpc_config_value(key: str, default: str) -> str:
    """Get RPC config value from database.

    Args:
        key: Config key to fetch.
        default: Default value if not found.

    Returns:
        Config value as string.
    """
    try:
        repo = asyncio.run(_get_config_repo())
        value = asyncio.run(repo.get_value(key))
        return value if value else default
    except Exception:
        return default


def _update_rpc_config(
    signatures_limit: int,
    transactions_limit: int,
    rpc_delay_ms: int,
    wallet_delay_seconds: int,
    batch_size: int,
) -> str:
    """Update RPC rate limiting configuration.

    Args:
        signatures_limit: Max signatures per wallet.
        transactions_limit: Max transactions per wallet.
        rpc_delay_ms: Delay between RPC calls in milliseconds.
        wallet_delay_seconds: Delay between wallets in seconds.
        batch_size: Max wallets per batch.

    Returns:
        Status message for UI display.
    """
    try:
        repo = asyncio.run(_get_config_repo())

        # Update all RPC config values
        asyncio.run(repo.set_value("profiling_signatures_limit", str(signatures_limit)))
        asyncio.run(repo.set_value("profiling_transactions_limit", str(transactions_limit)))
        asyncio.run(repo.set_value("profiling_rpc_delay_ms", str(rpc_delay_ms)))
        asyncio.run(
            repo.set_value("profiling_wallet_delay_seconds", str(wallet_delay_seconds))
        )
        asyncio.run(repo.set_value("profiling_batch_size", str(batch_size)))

        log.info(
            "rpc_config_updated",
            signatures_limit=signatures_limit,
            transactions_limit=transactions_limit,
            rpc_delay_ms=rpc_delay_ms,
            wallet_delay_seconds=wallet_delay_seconds,
            batch_size=batch_size,
        )

        # Reconfigure GlobalRateLimiter with new delay
        from walltrack.services.solana.rate_limiter import GlobalRateLimiter  # noqa: PLC0415

        GlobalRateLimiter.configure(rpc_delay_ms)

        return (
            "✅ RPC Configuration Updated Successfully!\n\n"
            f"  • Signatures per wallet: {signatures_limit}\n"
            f"  • Transactions per wallet: {transactions_limit}\n"
            f"  • RPC delay: {rpc_delay_ms}ms ({1000.0 / rpc_delay_ms:.1f} req/sec)\n"
            f"  • Wallet delay: {wallet_delay_seconds}s\n"
            f"  • Batch size: {batch_size} wallets\n\n"
            f"**Estimated time for 52 wallets:** ~{(signatures_limit + transactions_limit) * 52 * rpc_delay_ms / 1000 / 60:.1f} minutes"
        )

    except Exception as e:
        log.error("rpc_config_update_failed", error=str(e))
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

        # Analysis Criteria Section (Story 3.1-3.5)
        # NOTE: Discovery, profiling, and decay detection now run automatically
        # via background workers (WalletDiscoveryWorker, WalletProfilingWorker, DecayCheckScheduler)
        # This section configures criteria/thresholds for those autonomous processes.
        with gr.Accordion("Analysis Criteria", open=False):
            gr.Markdown(
                """
                ### Wallet Discovery Criteria Configuration

                Configure smart money wallet discovery filters.
                Wallets must meet BOTH criteria (early entry + profitable exit).
                """
            )

            # Load current values from config
            initial_early_entry, initial_min_profit = _get_discovery_criteria_values()

            # Story 3.1: Discovery criteria inputs
            early_entry_slider = gr.Slider(
                minimum=5,
                maximum=120,
                value=initial_early_entry,
                step=5,
                label="Early Entry Window (minutes)",
                info="Maximum minutes after token launch to qualify as 'early entry'",
            )

            min_profit_slider = gr.Slider(
                minimum=10,
                maximum=200,
                value=initial_min_profit,
                step=10,
                label="Minimum Profit %",
                info="Minimum profit percentage to qualify as 'profitable exit'",
            )

            save_discovery_btn = gr.Button("Update Discovery Criteria", variant="primary")
            discovery_criteria_status = gr.Textbox(
                label="Status",
                placeholder="Criteria not yet configured",
                interactive=False,
            )

            # Event handler
            save_discovery_btn.click(
                fn=_update_discovery_criteria,
                inputs=[early_entry_slider, min_profit_slider],
                outputs=[discovery_criteria_status],
            )

            gr.Markdown("---")
            gr.Markdown(
                """
                ### Watchlist Criteria Configuration

                Configure automatic watchlist evaluation thresholds.
                Wallets must meet ALL criteria to be watchlisted.
                """
            )

            # Story 3.5: Watchlist criteria inputs
            min_winrate_slider = gr.Slider(
                minimum=0.0,
                maximum=1.0,
                value=0.70,
                step=0.05,
                label="Minimum Win Rate (0.70 = 70%)",
                info="Minimum win rate required for watchlist inclusion",
            )

            min_pnl_input = gr.Number(
                value=5.0,
                label="Minimum PnL (SOL)",
                info="Minimum total PnL in SOL required",
            )

            min_trades_input = gr.Number(
                value=10,
                label="Minimum Trades",
                precision=0,
                info="Minimum number of completed trades required",
            )

            max_decay_slider = gr.Slider(
                minimum=0.0,
                maximum=1.0,
                value=0.3,
                step=0.05,
                label="Maximum Decay Score (0.30 = 30%)",
                info="Maximum decay score allowed (higher = worse)",
            )

            save_criteria_btn = gr.Button("Update Watchlist Criteria", variant="primary")
            criteria_status = gr.Textbox(
                label="Status",
                placeholder="Criteria not yet configured",
                interactive=False,
            )

            # Event handler
            save_criteria_btn.click(
                fn=_update_watchlist_criteria,
                inputs=[min_winrate_slider, min_pnl_input, min_trades_input, max_decay_slider],
                outputs=[criteria_status],
            )

            gr.Markdown("---")
            gr.Markdown(
                """
                ### Performance Analysis Configuration

                Configure how wallet performance metrics are calculated.
                These settings affect win rate calculation and watchlist evaluation.
                """
            )

            # Minimum profit percentage slider (AC2 & AC7)
            min_profit_slider = gr.Slider(
                minimum=5,
                maximum=50,
                value=10,
                step=5,
                label="Min Profit % for Win Rate",
                info="Trade must exceed this profit to count as win (default: 10%)",
            )

            save_performance_btn = gr.Button("Update Performance Criteria", variant="primary")
            performance_status = gr.Textbox(
                label="Status",
                placeholder="Performance criteria not yet configured",
                interactive=False,
            )

            # Event handler
            save_performance_btn.click(
                fn=_update_performance_criteria,
                inputs=[min_profit_slider],
                outputs=[performance_status],
            )

            gr.Markdown("---")
            gr.Markdown(
                """
                ### Behavioral Profiling Configuration

                Configure thresholds for classifying wallet trading behavior patterns.
                These settings determine how position sizes, hold durations, and confidence levels are categorized.
                """
            )

            # Load current values from config
            (
                current_pos_small,
                current_pos_medium,
                current_hold_scalper,
                current_hold_day,
                current_hold_swing,
                current_conf_high,
                current_conf_medium,
                current_conf_low,
            ) = _get_behavioral_criteria()

            # Position Size Thresholds
            gr.Markdown("#### Position Size Thresholds")

            pos_size_small_slider = gr.Slider(
                minimum=0.1,
                maximum=2.0,
                value=current_pos_small,
                step=0.1,
                label="Small Position Max (SOL)",
                info="Maximum SOL for 'small' classification (default: 0.5)",
            )

            pos_size_medium_slider = gr.Slider(
                minimum=1.0,
                maximum=10.0,
                value=current_pos_medium,
                step=0.5,
                label="Medium Position Max (SOL)",
                info="Maximum SOL for 'medium' classification (default: 2.0)",
            )

            # Hold Duration Thresholds
            gr.Markdown("#### Hold Duration Thresholds")

            hold_scalper_slider = gr.Slider(
                minimum=1800,
                maximum=7200,
                value=current_hold_scalper,
                step=600,
                label="Scalper Max (seconds)",
                info="Maximum hold time for 'scalper' classification (default: 3600 = 1h)",
            )

            hold_day_trader_slider = gr.Slider(
                minimum=3600,
                maximum=172800,
                value=current_hold_day,
                step=3600,
                label="Day Trader Max (seconds)",
                info="Maximum hold time for 'day trader' classification (default: 86400 = 24h)",
            )

            hold_swing_trader_slider = gr.Slider(
                minimum=86400,
                maximum=1209600,
                value=current_hold_swing,
                step=86400,
                label="Swing Trader Max (seconds)",
                info="Maximum hold time for 'swing trader' classification (default: 604800 = 7d)",
            )

            # Confidence Thresholds
            gr.Markdown("#### Confidence Thresholds")

            conf_high_input = gr.Number(
                value=current_conf_high,
                label="High Confidence Min Trades",
                precision=0,
                info="Minimum trades for 'high' confidence (default: 20)",
            )

            conf_medium_input = gr.Number(
                value=current_conf_medium,
                label="Medium Confidence Min Trades",
                precision=0,
                info="Minimum trades for 'medium' confidence (default: 10)",
            )

            conf_low_input = gr.Number(
                value=current_conf_low,
                label="Low Confidence Min Trades",
                precision=0,
                info="Minimum trades for 'low' confidence (default: 5)",
            )

            save_behavioral_btn = gr.Button("Update Behavioral Criteria", variant="primary")
            behavioral_status = gr.Textbox(
                label="Status",
                placeholder="Behavioral criteria not yet configured",
                interactive=False,
            )

            # Event handler
            save_behavioral_btn.click(
                fn=_update_behavioral_criteria,
                inputs=[
                    pos_size_small_slider,
                    pos_size_medium_slider,
                    hold_scalper_slider,
                    hold_day_trader_slider,
                    hold_swing_trader_slider,
                    conf_high_input,
                    conf_medium_input,
                    conf_low_input,
                ],
                outputs=[behavioral_status],
            )

            gr.Markdown("---")
            gr.Markdown(
                """
                ### RPC Rate Limiting Configuration

                Configure Solana RPC request parameters to avoid 429 rate limit errors.
                These settings control how many requests are made and how fast.

                **Official Solana Limits:** 40 requests / 10 seconds = 4 req/sec
                **Recommended:** Use 1 req/sec (1000ms delay) for safety
                """
            )

            # Load current values from config
            current_sigs = _get_rpc_config_value("profiling_signatures_limit", "20")
            current_txs = _get_rpc_config_value("profiling_transactions_limit", "20")
            current_delay = _get_rpc_config_value("profiling_rpc_delay_ms", "1000")
            current_wallet_delay = _get_rpc_config_value("profiling_wallet_delay_seconds", "10")
            current_batch = _get_rpc_config_value("profiling_batch_size", "10")

            signatures_limit_slider = gr.Slider(
                minimum=10,
                maximum=100,
                value=int(current_sigs),
                step=10,
                label="Signatures per Wallet",
                info="Max signatures to fetch per wallet (Light: 20, Conservative: 100)",
            )

            transactions_limit_slider = gr.Slider(
                minimum=10,
                maximum=100,
                value=int(current_txs),
                step=10,
                label="Transactions per Wallet",
                info="Max transactions to parse per wallet (Light: 20, Conservative: 100)",
            )

            rpc_delay_slider = gr.Slider(
                minimum=500,
                maximum=2000,
                value=int(current_delay),
                step=100,
                label="RPC Delay (ms)",
                info="Delay between RPC calls (1000ms = 1 req/sec recommended)",
            )

            wallet_delay_slider = gr.Slider(
                minimum=5,
                maximum=30,
                value=int(current_wallet_delay),
                step=5,
                label="Wallet Delay (seconds)",
                info="Delay between processing wallets (10s recommended)",
            )

            batch_size_slider = gr.Slider(
                minimum=5,
                maximum=20,
                value=int(current_batch),
                step=5,
                label="Batch Size",
                info="Max wallets to process per batch (10 recommended)",
            )

            save_rpc_btn = gr.Button("Update RPC Configuration", variant="primary")
            rpc_status = gr.Textbox(
                label="Status",
                placeholder="RPC configuration not yet updated",
                interactive=False,
            )

            # Event handler
            save_rpc_btn.click(
                fn=_update_rpc_config,
                inputs=[
                    signatures_limit_slider,
                    transactions_limit_slider,
                    rpc_delay_slider,
                    wallet_delay_slider,
                    batch_size_slider,
                ],
                outputs=[rpc_status],
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
