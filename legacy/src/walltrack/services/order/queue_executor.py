"""Queued order executor with priority processing.

Story 10.5-15: Order Priority Queue - Background worker for queue processing.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import TYPE_CHECKING, Any

import structlog

from walltrack.models.order import OrderStatus, OrderType
from walltrack.services.order.priority_queue import (
    OrderPriorityQueue,
    get_order_priority_queue,
)

if TYPE_CHECKING:
    from walltrack.models.order import Order

logger = structlog.get_logger(__name__)


class QueuedOrderExecutor:
    """Executes orders from priority queue.

    Runs as background worker, processing orders respecting:
    - Priority (EXIT before ENTRY)
    - Concurrency limits
    - Error handling with alerts
    """

    def __init__(
        self,
        queue: OrderPriorityQueue | None = None,
        poll_interval: float = 1.0,
        max_concurrent: int = 3,
    ) -> None:
        """Initialize queued executor.

        Args:
            queue: Priority queue instance (uses singleton if None)
            poll_interval: Seconds between queue polls
            max_concurrent: Maximum concurrent order executions
        """
        self._queue = queue or get_order_priority_queue(max_concurrent)
        self._poll_interval = poll_interval
        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._active_tasks: set[asyncio.Task[None]] = set()

        # Metrics
        self._orders_executed = 0
        self._orders_failed = 0
        self._total_execution_time = 0.0

    async def start(self) -> None:
        """Start the queue processor."""
        if self._running:
            logger.warning("queue_executor_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._process_loop())
        logger.info("queue_executor_started")

    async def stop(self, timeout: float = 10.0) -> None:
        """Stop the queue processor.

        Args:
            timeout: Maximum seconds to wait for graceful shutdown
        """
        if not self._running:
            return

        self._running = False

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except TimeoutError:
                logger.warning("queue_executor_stop_timeout")
                self._task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._task

        logger.info("queue_executor_stopped")

    async def submit_order(
        self,
        order: Order,
        emergency: bool = False,
    ) -> None:
        """Submit order to queue for processing.

        Args:
            order: Order to submit
            emergency: Whether this is an emergency order
        """
        await self._queue.enqueue(order, emergency=emergency)

        logger.info(
            "order_submitted_to_queue",
            order_id=str(order.id)[:8],
            order_type=order.order_type.value,
            emergency=emergency,
            queue_size=self._queue.queue_size,
        )

    async def _process_loop(self) -> None:
        """Main processing loop."""
        while self._running:
            try:
                # Get next order (respects concurrency limit)
                order = await self._queue.dequeue()

                if order:
                    # Process in background task
                    task = asyncio.create_task(self._execute_order(order))
                    self._active_tasks.add(task)
                    task.add_done_callback(self._active_tasks.discard)
                else:
                    # No order available, wait before polling again
                    await asyncio.sleep(self._poll_interval)

            except Exception as e:
                logger.exception("queue_process_loop_error", error=str(e))
                await asyncio.sleep(self._poll_interval)

    async def _execute_order(self, order: Order) -> None:
        """Execute a single order.

        Args:
            order: Order to execute
        """
        import time  # noqa: PLC0415

        start_time = time.monotonic()
        log = logger.bind(order_id=str(order.id)[:8], order_type=order.order_type.value)

        try:
            log.info("executing_order_from_queue")

            # Get executor and execute
            from walltrack.services.order.executor import (  # noqa: PLC0415
                get_order_executor,
            )

            executor = await get_order_executor()
            result = await executor.execute(order)

            # Track metrics
            execution_time = time.monotonic() - start_time
            self._total_execution_time += execution_time

            if result.status == OrderStatus.FILLED:
                self._orders_executed += 1
                log.info(
                    "order_executed_successfully",
                    execution_time=f"{execution_time:.2f}s",
                )
            else:
                self._orders_failed += 1
                log.warning(
                    "order_execution_not_filled",
                    status=result.status.value,
                    execution_time=f"{execution_time:.2f}s",
                )

        except Exception as e:
            self._orders_failed += 1
            log.exception("order_execution_failed", error=str(e))

            # Create alert for failed order
            await self._create_failure_alert(order, str(e))

        finally:
            # Always mark complete to release slot
            await self._queue.mark_complete(str(order.id))

    async def _create_failure_alert(self, order: Order, error: str) -> None:
        """Create alert for failed order execution.

        Args:
            order: Failed order
            error: Error message
        """
        try:
            from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                get_alert_service,
            )

            severity = (
                "critical" if order.order_type == OrderType.EXIT else "high"
            )

            alert_service = await get_alert_service()
            await alert_service.create_alert(
                alert_type="order_queue_failed",
                severity=severity,
                title=f"{order.order_type.value.upper()} Order Queue Failed",
                message=f"Order {str(order.id)[:8]} failed in queue: {error}",
                data={
                    "order_id": str(order.id),
                    "order_type": order.order_type.value,
                    "token_address": order.token_address,
                    "error": error,
                },
                requires_action=True,
                dedupe_key=f"queue_failed_{order.id}",
            )
        except Exception as e:
            logger.warning("alert_creation_failed", error=str(e))

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics.

        Returns:
            Dict with execution statistics
        """
        queue_stats = self._queue.get_stats()

        avg_execution = (
            self._total_execution_time / self._orders_executed
            if self._orders_executed > 0
            else 0
        )

        return {
            "running": self._running,
            "orders_executed": self._orders_executed,
            "orders_failed": self._orders_failed,
            "avg_execution_seconds": round(avg_execution, 2),
            "success_rate": (
                round(
                    self._orders_executed
                    / (self._orders_executed + self._orders_failed)
                    * 100,
                    1,
                )
                if (self._orders_executed + self._orders_failed) > 0
                else 0
            ),
            **queue_stats,
        }

    @property
    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._running

    @property
    def queue(self) -> OrderPriorityQueue:
        """Get the priority queue."""
        return self._queue


# Singleton
_queued_executor: QueuedOrderExecutor | None = None


def get_queued_executor(
    poll_interval: float = 1.0,
    max_concurrent: int = 3,
) -> QueuedOrderExecutor:
    """Get or create queued executor singleton.

    Args:
        poll_interval: Seconds between queue polls
        max_concurrent: Maximum concurrent executions

    Returns:
        The singleton executor instance
    """
    global _queued_executor
    if _queued_executor is None:
        _queued_executor = QueuedOrderExecutor(
            poll_interval=poll_interval,
            max_concurrent=max_concurrent,
        )
    return _queued_executor


def reset_queued_executor() -> None:
    """Reset the queued executor singleton (for testing)."""
    global _queued_executor
    _queued_executor = None
