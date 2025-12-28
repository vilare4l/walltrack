"""Wallet profiling scheduled task."""

import structlog

from walltrack.data.models.wallet import WalletStatus
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.profiler import WalletProfiler
from walltrack.services.helius.client import get_helius_client

log = structlog.get_logger()


async def run_profiling_task(
    batch_size: int = 50,
    lookback_days: int = 90,
    stale_hours: int = 24,
) -> dict[str, int]:
    """
    Run scheduled wallet profiling task.

    Profiles wallets that haven't been profiled recently (stale profiles).

    Args:
        batch_size: Number of wallets to profile per run
        lookback_days: Days of trading history to analyze
        stale_hours: Consider profile stale after this many hours

    Returns:
        Summary of profiling results
    """
    log.info(
        "profiling_task_starting",
        batch_size=batch_size,
        lookback_days=lookback_days,
        stale_hours=stale_hours,
    )

    # Initialize dependencies
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    helius = await get_helius_client()
    profiler = WalletProfiler(wallet_repo, helius)

    # Get wallets needing profiling (active wallets with stale profiles)
    active_wallets = await wallet_repo.get_by_status(
        WalletStatus.ACTIVE,
        limit=batch_size,
    )

    # Filter to wallets that need re-profiling
    wallets_to_profile = [
        w for w in active_wallets
        if profiler._needs_profiling(w, stale_hours=stale_hours)
    ]

    if not wallets_to_profile:
        log.info("no_wallets_to_profile")
        return {"processed": 0, "successful": 0, "failed": 0}

    # Run batch profiling
    addresses = [w.address for w in wallets_to_profile]
    profiled = await profiler.profile_batch(
        addresses=addresses,
        lookback_days=lookback_days,
    )

    result = {
        "processed": len(addresses),
        "successful": len(profiled),
        "failed": len(addresses) - len(profiled),
    }

    log.info("profiling_task_completed", **result)
    return result


async def profile_new_wallets(
    lookback_days: int = 90,
    max_concurrent: int = 10,
) -> dict[str, int]:
    """
    Profile wallets that have never been profiled.

    This is typically run after wallet discovery to immediately
    profile newly discovered wallets.

    Args:
        lookback_days: Days of trading history to analyze
        max_concurrent: Maximum concurrent profiling operations

    Returns:
        Summary of profiling results
    """
    log.info("profile_new_wallets_starting")

    # Initialize dependencies
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    helius = await get_helius_client()
    profiler = WalletProfiler(wallet_repo, helius)

    # Get wallets that have never been profiled
    # These are wallets with last_profiled_at = None
    wallets = await wallet_repo.get_unprofiled_wallets(limit=100)

    if not wallets:
        log.info("no_unprofiled_wallets")
        return {"processed": 0, "successful": 0, "failed": 0}

    addresses = [w.address for w in wallets]
    profiled = await profiler.profile_batch(
        addresses=addresses,
        lookback_days=lookback_days,
        max_concurrent=max_concurrent,
    )

    result = {
        "processed": len(addresses),
        "successful": len(profiled),
        "failed": len(addresses) - len(profiled),
    }

    log.info("profile_new_wallets_completed", **result)
    return result
