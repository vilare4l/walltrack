"""Price monitor for continuous position monitoring.

Runs a polling loop to check prices against exit levels.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING

import structlog

from walltrack.models.position import Position, PositionStatus

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.position_repo import PositionRepository
    from walltrack.services.execution.exit_manager import ExitManager
    from walltrack.services.token.fetcher import TokenFetcher

logger = structlog.get_logger()


class PriceMonitor:
    """Monitors prices for open positions and triggers exits.

    Runs a continuous loop checking prices against exit levels.
    """

    def __init__(
        self,
        exit_manager: ExitManager | None = None,
        token_fetcher: TokenFetcher | None = None,
        position_repo: PositionRepository | None = None,
        poll_interval_seconds: float = 5.0,
    ) -> None:
        self._exit_manager = exit_manager
        self._token_fetcher = token_fetcher
        self._position_repo = position_repo
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._exit_manager is None:
            from walltrack.services.execution.exit_manager import (  # noqa: PLC0415
                get_exit_manager,
            )

            self._exit_manager = await get_exit_manager()
        if self._token_fetcher is None:
            from walltrack.services.token.fetcher import (  # noqa: PLC0415
                get_token_fetcher,
            )

            self._token_fetcher = await get_token_fetcher()
        if self._position_repo is None:
            from walltrack.data.supabase.repositories.position_repo import (  # noqa: PLC0415
                get_position_repository,
            )

            self._position_repo = await get_position_repository()

        logger.info("price_monitor_initialized", poll_interval=self._poll_interval)

    async def start(self) -> None:
        """Start the price monitoring loop."""
        if self._running:
            logger.warning("price_monitor_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("price_monitor_started")

    async def stop(self) -> None:
        """Stop the price monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
        logger.info("price_monitor_stopped")

    @property
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_positions()
            except Exception as e:
                logger.error("price_monitor_error", error=str(e))

            await asyncio.sleep(self._poll_interval)

    async def _check_all_positions(self) -> None:
        """Check all open positions for exit conditions."""
        # Get all open positions
        open_positions = await self._position_repo.list_open()

        if not open_positions:
            return

        logger.debug("checking_positions", count=len(open_positions))

        # Group positions by token for efficient price fetching
        tokens_to_check: dict[str, list[Position]] = {}
        for position in open_positions:
            if position.token_address not in tokens_to_check:
                tokens_to_check[position.token_address] = []
            tokens_to_check[position.token_address].append(position)

        # Fetch prices and process positions
        for token_address, positions in tokens_to_check.items():
            try:
                # Fetch current price
                token_data = await self._token_fetcher.fetch(token_address)
                if not token_data.success or token_data.token is None:
                    logger.warning(
                        "price_fetch_failed",
                        token=token_address[:8],
                    )
                    continue

                current_price = token_data.token.price_usd

                # Process each position for this token
                for position in positions:
                    await self._exit_manager.process_position(position, current_price)

            except Exception as e:
                logger.error(
                    "position_check_error",
                    token=token_address[:8],
                    error=str(e),
                )

    async def check_single_position(self, position_id: str) -> bool:
        """Check a single position immediately.

        Args:
            position_id: Position ID to check

        Returns:
            True if exit was triggered
        """
        position = await self._position_repo.get_by_id(position_id)
        if not position or position.status not in [
            PositionStatus.OPEN,
            PositionStatus.PARTIAL_EXIT,
            PositionStatus.MOONBAG,
        ]:
            return False

        # Fetch price
        token_data = await self._token_fetcher.fetch(position.token_address)
        if not token_data.success or token_data.token is None:
            return False

        current_price = token_data.token.price_usd

        # Process
        execution = await self._exit_manager.process_position(position, current_price)
        return execution is not None


# Singleton
_price_monitor: PriceMonitor | None = None


async def get_price_monitor() -> PriceMonitor:
    """Get or create price monitor singleton."""
    global _price_monitor
    if _price_monitor is None:
        _price_monitor = PriceMonitor()
        await _price_monitor.initialize()
    return _price_monitor
