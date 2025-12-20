"""Signal filter service for filtering to monitored wallets."""

import time

import structlog

from walltrack.constants.signal_filter import (
    LOG_BLACKLISTED_SIGNALS,
    LOG_DISCARDED_SIGNALS,
    MAX_LOOKUP_TIME_MS,
)
from walltrack.models.signal_filter import (
    FilterResult,
    FilterStatus,
    SignalContext,
)
from walltrack.services.helius.models import ParsedSwapEvent
from walltrack.services.signal.wallet_cache import WalletCache

logger = structlog.get_logger(__name__)


class SignalFilter:
    """
    Filters signals to only process monitored wallets.

    Integrates with blacklist and provides wallet metadata enrichment.
    """

    def __init__(self, wallet_cache: WalletCache) -> None:
        """Initialize signal filter.

        Args:
            wallet_cache: Wallet cache for fast lookups
        """
        self.wallet_cache = wallet_cache

    async def filter_signal(self, event: ParsedSwapEvent) -> FilterResult:
        """
        Filter signal based on wallet monitoring status.

        Args:
            event: Parsed swap event to filter

        Returns:
            FilterResult with status and timing
        """
        start_time = time.perf_counter()

        try:
            # Get wallet from cache (O(1) lookup)
            entry, cache_hit = await self.wallet_cache.get(event.wallet_address)

            lookup_time_ms = (time.perf_counter() - start_time) * 1000

            # Warn if lookup exceeds limit
            if lookup_time_ms > MAX_LOOKUP_TIME_MS:
                logger.warning(
                    "filter_lookup_slow",
                    lookup_time_ms=round(lookup_time_ms, 2),
                    limit_ms=MAX_LOOKUP_TIME_MS,
                    wallet=event.wallet_address[:8] + "...",
                )

            # Check blacklist first (AC4)
            if entry and entry.is_blacklisted:
                if LOG_BLACKLISTED_SIGNALS:
                    logger.info(
                        "signal_blocked_blacklisted",
                        wallet=event.wallet_address[:8] + "...",
                        token=event.token_address[:8] + "...",
                    )
                return FilterResult(
                    status=FilterStatus.BLOCKED_BLACKLISTED,
                    wallet_address=event.wallet_address,
                    is_monitored=entry.is_monitored if entry else False,
                    is_blacklisted=True,
                    lookup_time_ms=lookup_time_ms,
                    cache_hit=cache_hit,
                    wallet_metadata=entry,
                )

            # Check if monitored (AC2/AC3)
            is_monitored = entry.is_monitored if entry else False

            if not is_monitored:
                if LOG_DISCARDED_SIGNALS:
                    logger.debug(
                        "signal_discarded_not_monitored",
                        wallet=event.wallet_address[:8] + "...",
                    )
                return FilterResult(
                    status=FilterStatus.DISCARDED_NOT_MONITORED,
                    wallet_address=event.wallet_address,
                    is_monitored=False,
                    is_blacklisted=False,
                    lookup_time_ms=lookup_time_ms,
                    cache_hit=cache_hit,
                    wallet_metadata=entry,
                )

            # Signal passed - monitored and not blacklisted
            return FilterResult(
                status=FilterStatus.PASSED,
                wallet_address=event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
                lookup_time_ms=lookup_time_ms,
                cache_hit=cache_hit,
                wallet_metadata=entry,
            )

        except Exception as e:
            logger.error(
                "filter_error",
                wallet=event.wallet_address[:8] + "...",
                error=str(e),
            )
            return FilterResult(
                status=FilterStatus.ERROR,
                wallet_address=event.wallet_address,
                is_monitored=False,
                is_blacklisted=False,
                lookup_time_ms=(time.perf_counter() - start_time) * 1000,
                cache_hit=False,
            )

    def create_signal_context(
        self,
        event: ParsedSwapEvent,
        filter_result: FilterResult,
    ) -> SignalContext:
        """
        Create enriched signal context with wallet metadata.

        Called only for signals that passed filtering.

        Args:
            event: Original swap event
            filter_result: Result of filtering

        Returns:
            Enriched SignalContext
        """
        metadata = filter_result.wallet_metadata

        return SignalContext(
            wallet_address=event.wallet_address,
            token_address=event.token_address,
            direction=event.direction.value,
            amount_token=event.amount_token,
            amount_sol=event.amount_sol,
            timestamp=event.timestamp,
            tx_signature=event.tx_signature,
            cluster_id=metadata.cluster_id if metadata else None,
            is_cluster_leader=metadata.is_leader if metadata else False,
            wallet_reputation=metadata.reputation_score if metadata else 0.5,
            filter_status=filter_result.status,
            filter_time_ms=filter_result.lookup_time_ms,
        )
