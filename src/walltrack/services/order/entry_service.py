"""Service for creating and managing entry orders."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from walltrack.models.order import Order, OrderStatus

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.order_repo import OrderRepository
    from walltrack.data.supabase.repositories.signal_repo import SignalRepository
    from walltrack.models.signal_log import SignalLogEntry
    from walltrack.services.order.executor import OrderExecutor
    from walltrack.services.order.order_factory import OrderFactory
    from walltrack.services.position_service import PositionService
    from walltrack.services.pricing.price_oracle import PriceOracle
    from walltrack.services.risk.risk_manager import RiskManager

logger = structlog.get_logger(__name__)


class EntryOrderService:
    """
    Service for handling entry order flow.

    Converts signals to orders and creates positions on fill.
    This replaces the direct position creation in SignalPipeline.
    """

    def __init__(
        self,
        order_repo: OrderRepository,
        signal_repo: SignalRepository,
        position_service: PositionService,
        executor: OrderExecutor,
        risk_manager: RiskManager,
        price_oracle: PriceOracle,
        order_factory: OrderFactory,
    ) -> None:
        """
        Initialize EntryOrderService.

        Args:
            order_repo: Repository for order persistence
            signal_repo: Repository for signal updates
            position_service: Service for position creation
            executor: Order executor for trade execution
            risk_manager: Risk manager for entry checks
            price_oracle: Price oracle for current prices
            order_factory: Factory for creating orders
        """
        self.order_repo = order_repo
        self.signal_repo = signal_repo
        self.position_service = position_service
        self.executor = executor
        self.risk_manager = risk_manager
        self.price_oracle = price_oracle
        self.order_factory = order_factory

    async def process_signal(self, signal: SignalLogEntry) -> Order | None:
        """
        Process a validated signal and create entry order.

        Flow:
        1. Risk management checks
        2. Get current price
        3. Calculate position size
        4. Create order
        5. Execute order
        6. Create position if filled

        Args:
            signal: Validated signal from pipeline

        Returns:
            Created order if successful, None if blocked by risk management
        """
        log = logger.bind(
            signal_id=signal.id,
            token=signal.token_address[:8],
        )

        # Step 1: Risk management checks
        risk_check = await self.risk_manager.check_entry_allowed(
            token_address=signal.token_address,
            cluster_id=None,  # TODO: Add cluster_id to signal
        )

        if not risk_check.allowed:
            log.warning("entry_blocked_by_risk", reason=risk_check.reason)
            await self._update_signal_status(signal, "blocked", risk_check.reason)
            return None

        # Step 2: Get current price
        price_result = await self.price_oracle.get_price(signal.token_address)
        if not price_result.success:
            log.warning("price_fetch_failed", error=price_result.error)
            await self._update_signal_status(signal, "error", "Price fetch failed")
            return None

        expected_price = price_result.price

        # Step 3: Calculate position size
        position_size = await self.risk_manager.calculate_position_size(
            signal=signal,
            current_price=expected_price,
        )

        log.info(
            "position_size_calculated",
            amount_sol=str(position_size.amount_sol),
            sizing_mode=position_size.mode,
        )

        # Step 4: Create entry order
        order = self.order_factory.create_entry_order(
            signal_id=signal.id or "",
            token_address=signal.token_address,
            amount_sol=position_size.amount_sol,
            expected_price=expected_price,
            max_slippage_bps=100,
        )

        await self.order_repo.create(order)
        log.info("entry_order_created", order_id=str(order.id)[:8])

        # Step 5: Execute order
        result = await self.executor.execute(order)
        executed_order = result.order  # Use the order from result (may be updated)

        if result.success:
            # Step 6: Create position from filled order
            position = await self._create_position_from_order(executed_order, signal)
            log.info(
                "position_created_from_order",
                position_id=position.id[:8],
            )

            await self._update_signal_status(signal, "executed", None)
            return executed_order

        else:
            # Check if can retry
            if executed_order.can_retry:
                log.info(
                    "order_scheduled_for_retry",
                    attempt=executed_order.attempt_count,
                    next_retry=executed_order.next_retry_at,
                )
                # Retry will be handled by RetryWorker (Story 10.5-12)
            else:
                log.warning(
                    "order_failed_permanently",
                    error=result.error,
                    attempts=executed_order.attempt_count,
                )
                await self._update_signal_status(signal, "failed", result.error)
                await self._create_failure_alert(signal, executed_order)

            return executed_order

    async def _create_position_from_order(
        self,
        order: Order,
        signal: SignalLogEntry,
    ):
        """
        Create a position from a filled entry order.

        Args:
            order: Filled order
            signal: Source signal

        Returns:
            Created position
        """
        # Determine conviction tier from signal score
        score = signal.final_score or 0.5
        if score >= 0.85:
            conviction_tier = "high"
        else:
            conviction_tier = "standard"

        # Create position via PositionService
        position = await self.position_service.create_position(
            signal_id=signal.id or "",
            token_address=order.token_address,
            entry_price=float(order.actual_price or order.expected_price),
            entry_amount_sol=float(order.amount_sol),
            entry_amount_tokens=float(order.amount_tokens or Decimal("0")),
            exit_strategy_id="default-exit-strategy",  # TODO: Get from signal
            conviction_tier=conviction_tier,
            token_symbol=order.token_symbol,
        )

        # Link position to order
        # The order already has the signal_id
        # Position now has entry_order reference via signal_id chain

        return position

    async def _update_signal_status(
        self,
        signal: SignalLogEntry,
        status: str,
        error: str | None,
    ) -> None:
        """
        Update signal execution status.

        Args:
            signal: Signal to update
            status: New status (executed, failed, blocked, error)
            error: Optional error message
        """
        try:
            # Update signal status via repository
            # The signal_repo.update method expects specific fields
            if signal.id:
                await self.signal_repo.update_execution_status(
                    signal_id=signal.id,
                    status=status,
                    error=error,
                )
        except Exception as e:
            logger.warning(
                "signal_status_update_failed",
                signal_id=signal.id,
                error=str(e),
            )

    async def _create_failure_alert(
        self,
        signal: SignalLogEntry,
        order: Order,
    ) -> None:
        """
        Create alert for failed entry.

        Args:
            signal: Source signal
            order: Failed order
        """
        # TODO: Implement alert service (Story 10.5-14)
        logger.warning(
            "entry_order_failed_alert",
            signal_id=signal.id,
            order_id=str(order.id),
            token=signal.token_address[:8],
            error=order.last_error,
            attempts=order.attempt_count,
        )

    async def retry_failed_order(self, order: Order) -> Order | None:
        """
        Retry a failed order.

        Args:
            order: Failed order to retry

        Returns:
            Updated order if retry was attempted, None otherwise
        """
        if not order.can_retry:
            logger.warning(
                "order_cannot_retry",
                order_id=str(order.id)[:8],
                attempts=order.attempt_count,
                max_attempts=order.max_attempts,
            )
            return None

        # Reset status for retry
        order.status = OrderStatus.PENDING
        await self.order_repo.update(order)

        # Re-execute
        result = await self.executor.execute(order)
        executed_order = result.order

        if result.success:
            # Get signal and create position
            signal = await self.signal_repo.get_by_id(order.signal_id)
            if signal:
                await self._create_position_from_order(executed_order, signal)
                await self._update_signal_status(signal, "executed", None)

        return executed_order


# Singleton
_entry_service: EntryOrderService | None = None


async def get_entry_order_service() -> EntryOrderService:
    """Get or create entry order service."""
    global _entry_service

    if _entry_service is None:
        from walltrack.core.simulation.context import is_simulation_mode
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.order_repo import OrderRepository
        from walltrack.data.supabase.repositories.signal_repo import SignalRepository
        from walltrack.services.order.executor import get_order_executor
        from walltrack.services.order.order_factory import OrderFactory
        from walltrack.services.position_service import get_position_service
        from walltrack.services.pricing.price_oracle import get_price_oracle
        from walltrack.services.risk.risk_manager import get_risk_manager

        client = await get_supabase_client()

        _entry_service = EntryOrderService(
            order_repo=OrderRepository(client),
            signal_repo=SignalRepository(client),
            position_service=await get_position_service(),
            executor=await get_order_executor(),
            risk_manager=await get_risk_manager(),
            price_oracle=await get_price_oracle(),
            order_factory=OrderFactory(is_simulation_mode=is_simulation_mode()),
        )

    return _entry_service
