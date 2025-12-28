"""Service for creating and managing exit orders."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import structlog

from walltrack.models.order import Order, OrderStatus, OrderType
from walltrack.models.position import (
    ExitExecution,
    ExitReason,
    Position,
    PositionStatus,
)

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.order_repo import OrderRepository
    from walltrack.data.supabase.repositories.position_repo import PositionRepository
    from walltrack.services.order.executor import OrderExecutor
    from walltrack.services.order.order_factory import OrderFactory
    from walltrack.services.pricing.price_oracle import PriceOracle

logger = structlog.get_logger(__name__)


class ExitOrderService:
    """
    Service for handling exit order flow.

    Creates exit orders and updates positions on fill.
    Replaces direct exit execution with order-based flow.
    """

    def __init__(
        self,
        order_repo: OrderRepository,
        position_repo: PositionRepository,
        executor: OrderExecutor,
        price_oracle: PriceOracle,
        order_factory: OrderFactory,
    ) -> None:
        """
        Initialize ExitOrderService.

        Args:
            order_repo: Repository for order persistence
            position_repo: Repository for position updates
            executor: Order executor for trade execution
            price_oracle: Price oracle for current prices
            order_factory: Factory for creating orders
        """
        self.order_repo = order_repo
        self.position_repo = position_repo
        self.executor = executor
        self.price_oracle = price_oracle
        self.order_factory = order_factory

    async def create_exit_order(
        self,
        position: Position,
        exit_reason: ExitReason,
        sell_percent: Decimal = Decimal("100"),
        max_slippage_bps: int = 150,
    ) -> Order | None:
        """
        Create an exit order for a position.

        Args:
            position: The position to exit
            exit_reason: Why we're exiting (stop_loss, take_profit, etc.)
            sell_percent: Percentage of remaining tokens to sell (1-100)
            max_slippage_bps: Maximum slippage allowed (higher for exits)

        Returns:
            Created order or None if position can't be exited
        """
        log = logger.bind(
            position_id=position.id[:8],
            reason=exit_reason.value,
            sell_pct=str(sell_percent),
        )

        # Validate position can be exited
        if position.status not in [
            PositionStatus.OPEN,
            PositionStatus.PARTIAL_EXIT,
            PositionStatus.MOONBAG,
        ]:
            log.warning("position_not_exitable", status=position.status.value)
            return None

        # Check remaining tokens
        remaining_tokens = Decimal(str(position.current_amount_tokens))
        if remaining_tokens <= Decimal("0.001"):
            log.warning("no_tokens_to_exit", remaining=str(remaining_tokens))
            return None

        # Check for pending exit orders
        pending_exits = await self.order_repo.get_by_position(
            position.id,
            order_type=OrderType.EXIT,
        )
        active_exits = [o for o in pending_exits if not o.is_terminal]

        if active_exits:
            log.warning("exit_already_pending", count=len(active_exits))
            return None

        # Get current price
        price_result = await self.price_oracle.get_price(position.token_address)

        if not price_result.success:
            log.warning("price_fetch_failed", error=price_result.error)
            # For SL exits, use last known price as fallback
            if exit_reason == ExitReason.STOP_LOSS:
                fallback_price = position.peak_price or position.entry_price * 0.5
                expected_price = Decimal(str(fallback_price))
                log.info("using_fallback_price", price=str(expected_price))
            else:
                return None
        else:
            expected_price = price_result.price

        # Calculate amount to sell
        amount_tokens = remaining_tokens * sell_percent / Decimal("100")

        # Create exit order
        order = self.order_factory.create_exit_order(
            position=position,
            amount_tokens=amount_tokens,
            expected_price=expected_price,
            exit_reason=exit_reason.value,
            max_slippage_bps=max_slippage_bps,
        )

        await self.order_repo.create(order)
        log.info("exit_order_created", order_id=str(order.id)[:8], amount=str(amount_tokens))

        # Mark position as closing
        position.status = PositionStatus.CLOSING
        position.exit_reason = exit_reason
        await self.position_repo.update(position)

        return order

    async def execute_exit_order(self, order: Order) -> bool:
        """
        Execute an exit order and update position.

        Args:
            order: Exit order to execute

        Returns:
            True if exit was successful
        """
        log = logger.bind(order_id=str(order.id)[:8], position_id=order.position_id)

        result = await self.executor.execute(order)
        executed_order = result.order

        if result.success:
            await self._process_successful_exit(executed_order)
            log.info("exit_executed", actual_price=str(result.actual_price))
            return True
        else:
            if executed_order.can_retry:
                log.warning(
                    "exit_failed_will_retry",
                    attempt=executed_order.attempt_count,
                    next_retry=executed_order.next_retry_at,
                )
                # Update order in repo (already updated by executor)
            else:
                log.error("exit_failed_permanently", error=result.error)
                await self._handle_failed_exit(executed_order)
            return False

    async def _process_successful_exit(self, order: Order) -> None:
        """
        Update position after successful exit.

        Args:
            order: Successfully filled exit order
        """
        if not order.position_id:
            logger.error("order_missing_position_id", order_id=str(order.id))
            return

        position = await self.position_repo.get_by_id(order.position_id)

        if not position:
            logger.error("position_not_found", position_id=order.position_id)
            return

        # Calculate PnL for this exit
        tokens_sold = float(order.amount_tokens or Decimal("0"))
        actual_price = float(order.actual_price or order.expected_price)
        exit_value_sol = tokens_sold * actual_price

        # Calculate proportional entry cost
        entry_cost_ratio = tokens_sold / position.entry_amount_tokens
        entry_cost_sol = position.entry_amount_sol * entry_cost_ratio

        pnl_sol = exit_value_sol - entry_cost_sol

        # Update position
        position.current_amount_tokens -= tokens_sold
        position.realized_pnl_sol += pnl_sol

        # Add tx signature to exit list
        if order.tx_signature:
            position.exit_tx_signatures.append(order.tx_signature)

        # Update exit price (average or last)
        position.exit_price = actual_price

        # Check if fully exited
        remaining = position.current_amount_tokens

        if remaining <= 0.001:  # Small threshold for rounding
            position.status = PositionStatus.CLOSED
            position.exit_time = datetime.now(UTC)
        else:
            position.status = PositionStatus.PARTIAL_EXIT

        await self.position_repo.update(position)

        # Record exit execution
        await self._record_exit_execution(order, position, pnl_sol)

        logger.info(
            "position_updated_after_exit",
            position_id=position.id[:8],
            status=position.status.value,
            remaining_tokens=position.current_amount_tokens,
            realized_pnl=position.realized_pnl_sol,
        )

    async def _record_exit_execution(
        self,
        order: Order,
        position: Position,
        pnl_sol: float,
    ) -> None:
        """
        Record exit execution for tracking.

        Args:
            order: Filled exit order
            position: Position that was exited
            pnl_sol: Realized PnL for this exit
        """
        # Determine sell percentage
        tokens_sold = float(order.amount_tokens or Decimal("0"))
        sell_pct = (tokens_sold / position.entry_amount_tokens) * 100

        execution = ExitExecution(
            position_id=position.id,
            exit_reason=position.exit_reason or ExitReason.MANUAL,
            trigger_level=position.exit_reason.value if position.exit_reason else "manual",
            sell_percentage=sell_pct,
            amount_tokens_sold=tokens_sold,
            amount_sol_received=float(order.amount_sol),
            exit_price=float(order.actual_price or order.expected_price),
            tx_signature=order.tx_signature or "",
            realized_pnl_sol=pnl_sol,
        )

        try:
            await self.position_repo.save_exit_execution(execution)
        except Exception as e:
            logger.warning("exit_execution_save_failed", error=str(e))

    async def _handle_failed_exit(self, order: Order) -> None:
        """
        Handle permanently failed exit order.

        Restores position status and creates alert.

        Args:
            order: Failed exit order
        """
        if order.position_id:
            position = await self.position_repo.get_by_id(order.position_id)
            if position:
                # Restore to previous status
                if position.current_amount_tokens < position.entry_amount_tokens:
                    position.status = PositionStatus.PARTIAL_EXIT
                else:
                    position.status = PositionStatus.OPEN
                await self.position_repo.update(position)

        # Create critical alert
        await self._create_critical_alert(order)

    async def _create_critical_alert(self, order: Order) -> None:
        """
        Create critical alert for failed exit.

        Args:
            order: Failed order requiring attention
        """
        # TODO: Implement alert service (Story 10.5-14)
        logger.error(
            "exit_order_failed_critical",
            order_id=str(order.id),
            position_id=order.position_id,
            token=order.token_address[:8] if order.token_address else "unknown",
            error=order.last_error,
            attempts=order.attempt_count,
        )

    async def retry_failed_exit(self, order_id: str) -> Order | None:
        """
        Manually retry a failed exit order.

        Args:
            order_id: ID of the failed order to retry

        Returns:
            New order if retry was initiated, None otherwise
        """
        from uuid import UUID

        order = await self.order_repo.get_by_id(UUID(order_id))

        if not order:
            logger.warning("order_not_found", order_id=order_id)
            return None

        if order.status != OrderStatus.CANCELLED:
            logger.warning(
                "order_not_cancelled",
                order_id=order_id,
                status=order.status.value,
            )
            return None

        if not order.position_id:
            logger.warning("order_missing_position", order_id=order_id)
            return None

        position = await self.position_repo.get_by_id(order.position_id)

        if not position:
            logger.warning("position_not_found", position_id=order.position_id)
            return None

        # Determine exit reason from original order or position
        exit_reason = position.exit_reason or ExitReason.MANUAL

        # Create new exit order with same parameters
        new_order = await self.create_exit_order(
            position=position,
            exit_reason=exit_reason,
            sell_percent=Decimal("100"),  # Full remaining on retry
            max_slippage_bps=200,  # Higher slippage for retry
        )

        if new_order:
            # Execute immediately
            success = await self.execute_exit_order(new_order)
            if success:
                logger.info(
                    "exit_retry_successful",
                    original_order=order_id,
                    new_order=str(new_order.id)[:8],
                )
            return new_order

        return None


# Singleton
_exit_service: ExitOrderService | None = None


async def get_exit_order_service() -> ExitOrderService:
    """Get or create exit order service."""
    global _exit_service

    if _exit_service is None:
        from walltrack.core.simulation.context import is_simulation_mode
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.order_repo import OrderRepository
        from walltrack.data.supabase.repositories.position_repo import PositionRepository
        from walltrack.services.order.executor import get_order_executor
        from walltrack.services.order.order_factory import OrderFactory
        from walltrack.services.pricing.price_oracle import get_price_oracle

        client = await get_supabase_client()

        _exit_service = ExitOrderService(
            order_repo=OrderRepository(client),
            position_repo=PositionRepository(client),
            executor=await get_order_executor(),
            price_oracle=await get_price_oracle(),
            order_factory=OrderFactory(is_simulation_mode=is_simulation_mode()),
        )

    return _exit_service
