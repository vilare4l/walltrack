"""Scheduled task for periodic decay detection."""

import structlog

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.trade_repo import TradeRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.decay_detector import DecayDetector, DecayEvent

log = structlog.get_logger()


async def run_decay_check(
    batch_size: int = 100,
    max_concurrent: int = 20,
) -> dict[str, int]:
    """
    Run periodic decay detection for all wallets.

    Should be scheduled to run every 1-4 hours.

    Args:
        batch_size: Number of wallets to process per batch
        max_concurrent: Maximum concurrent checks

    Returns:
        Summary of decay check results
    """
    log.info("scheduled_decay_check_started")

    # Initialize dependencies
    supabase = await get_supabase_client()
    wallet_repo = WalletRepository(supabase)
    trade_repo = TradeRepository(supabase)
    event_repo = DecayEventRepository(supabase)

    async def store_and_notify(event: DecayEvent) -> None:
        """Store event and trigger notifications."""
        await event_repo.create(event)

    detector = DecayDetector(
        wallet_repo=wallet_repo,
        trade_repo=trade_repo,
        notification_callback=store_and_notify,
    )

    events = await detector.check_all_wallets(
        batch_size=batch_size,
        max_concurrent=max_concurrent,
    )

    # Log summary
    decay_count = sum(1 for e in events if e.event_type == "decay_detected")
    recovery_count = sum(1 for e in events if e.event_type == "recovery")
    loss_count = sum(1 for e in events if e.event_type == "consecutive_losses")

    result = {
        "total_events": len(events),
        "decay_detected": decay_count,
        "recoveries": recovery_count,
        "consecutive_losses": loss_count,
    }

    log.info("scheduled_decay_check_completed", **result)
    return result
