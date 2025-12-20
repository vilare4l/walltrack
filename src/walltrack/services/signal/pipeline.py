"""Signal processing pipeline."""

import structlog

from walltrack.models.signal_filter import FilterStatus, SignalContext
from walltrack.services.helius.models import ParsedSwapEvent
from walltrack.services.signal.filter import SignalFilter

logger = structlog.get_logger(__name__)


class SignalPipeline:
    """
    Main signal processing pipeline.

    Orchestrates filtering, scoring, and trade eligibility.
    """

    def __init__(
        self,
        signal_filter: SignalFilter,
    ) -> None:
        """Initialize signal pipeline.

        Args:
            signal_filter: Signal filter service

        Note:
            Future Stories will add: signal_scorer (3.4), threshold_checker (3.5)
        """
        self.signal_filter = signal_filter

    async def process_swap_event(self, event: ParsedSwapEvent) -> SignalContext | None:
        """
        Process swap event through the full pipeline.

        Args:
            event: Parsed swap event

        Returns:
            SignalContext if signal passes filtering, None otherwise
        """
        # Step 1: Filter signal (Story 3.2)
        filter_result = await self.signal_filter.filter_signal(event)

        if filter_result.status != FilterStatus.PASSED:
            logger.debug(
                "signal_filtered_out",
                status=filter_result.status.value,
                wallet=event.wallet_address[:8] + "...",
            )
            return None

        # Create enriched signal context
        signal_context = self.signal_filter.create_signal_context(event, filter_result)

        logger.info(
            "signal_passed_filter",
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
            cluster_id=signal_context.cluster_id,
            is_leader=signal_context.is_cluster_leader,
        )

        # TODO(Story 3.4): Score signal with signal_scorer
        # TODO(Story 3.5): Apply threshold with threshold_checker

        return signal_context


# Singleton pipeline instance
_pipeline: SignalPipeline | None = None


async def get_pipeline() -> SignalPipeline:
    """Get or create signal pipeline singleton."""
    global _pipeline

    if _pipeline is None:
        # Lazy imports to avoid circular dependencies
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415
        from walltrack.data.supabase.repositories.wallet_repo import (  # noqa: PLC0415
            WalletRepository,
        )
        from walltrack.services.signal.wallet_cache import WalletCache  # noqa: PLC0415

        client = await get_supabase_client()
        wallet_repo = WalletRepository(client)
        wallet_cache = WalletCache(wallet_repo)
        await wallet_cache.initialize()

        signal_filter = SignalFilter(wallet_cache)
        _pipeline = SignalPipeline(signal_filter)

    return _pipeline


async def reset_pipeline() -> None:
    """Reset pipeline singleton (for testing)."""
    global _pipeline
    _pipeline = None
