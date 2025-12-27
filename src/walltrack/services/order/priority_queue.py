"""Priority queue for order processing.

Story 10.5-15: Order Priority Queue - EXIT before ENTRY prioritization.
"""

from __future__ import annotations

import asyncio
import heapq
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import IntEnum
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from walltrack.models.order import Order

logger = structlog.get_logger(__name__)


class OrderPriority(IntEnum):
    """Order priority levels (lower = higher priority)."""

    EMERGENCY = 0
    EXIT_STOP_LOSS = 10
    EXIT_TRAILING = 20
    EXIT_TAKE_PROFIT = 30
    EXIT_MANUAL = 40
    EXIT_OTHER = 50
    ENTRY = 100


@dataclass(order=True)
class PrioritizedOrder:
    """Order wrapper with priority for heap queue."""

    priority: int
    created_at: float = field(compare=True)
    order_id: str = field(compare=False)
    order: Order = field(compare=False)


class OrderPriorityQueue:
    """Priority queue for order execution.

    Ensures EXIT orders are processed before ENTRY,
    with sub-priorities within each type.
    """

    def __init__(
        self,
        max_concurrent: int = 3,
    ) -> None:
        """Initialize priority queue.

        Args:
            max_concurrent: Maximum concurrent orders to process
        """
        self._queue: list[PrioritizedOrder] = []
        self._processing: set[str] = set()
        self._max_concurrent = max_concurrent
        self._lock = asyncio.Lock()

        # Metrics
        self._processed_count = 0
        self._total_wait_time = 0.0

    async def enqueue(self, order: Order, emergency: bool = False) -> None:
        """Add order to priority queue.

        Args:
            order: Order to enqueue
            emergency: Whether this is an emergency order
        """
        async with self._lock:
            priority = self._calculate_priority(order, emergency)

            item = PrioritizedOrder(
                priority=priority,
                created_at=order.created_at.timestamp(),
                order_id=str(order.id),
                order=order,
            )

            heapq.heappush(self._queue, item)

            logger.debug(
                "order_enqueued",
                order_id=str(order.id)[:8],
                priority=priority,
                queue_size=len(self._queue),
            )

    async def dequeue(self) -> Order | None:
        """Get next order to process (respecting concurrency limit).

        Returns:
            Next order to process, or None if no slots available
        """
        async with self._lock:
            if len(self._processing) >= self._max_concurrent:
                return None

            if not self._queue:
                return None

            item = heapq.heappop(self._queue)

            # Track processing
            self._processing.add(item.order_id)

            # Update metrics
            wait_time = datetime.now(UTC).timestamp() - item.created_at
            self._total_wait_time += wait_time
            self._processed_count += 1

            logger.debug(
                "order_dequeued",
                order_id=item.order_id[:8],
                priority=item.priority,
                wait_time=f"{wait_time:.1f}s",
            )

            return item.order

    async def mark_complete(self, order_id: str) -> None:
        """Mark order as completed (release slot).

        Args:
            order_id: ID of completed order
        """
        async with self._lock:
            self._processing.discard(order_id)
            logger.debug("order_processing_complete", order_id=order_id[:8])

    async def remove(self, order_id: str) -> bool:
        """Remove order from queue (if not yet processing).

        Args:
            order_id: ID of order to remove

        Returns:
            True if order was removed
        """
        async with self._lock:
            for i, item in enumerate(self._queue):
                if item.order_id == order_id:
                    del self._queue[i]
                    heapq.heapify(self._queue)
                    logger.debug("order_removed", order_id=order_id[:8])
                    return True
            return False

    async def peek(self) -> Order | None:
        """Peek at next order without removing.

        Returns:
            Next order in queue, or None if empty
        """
        async with self._lock:
            if not self._queue:
                return None
            return self._queue[0].order

    async def contains(self, order_id: str) -> bool:
        """Check if order is in queue or processing.

        Args:
            order_id: Order ID to check

        Returns:
            True if order is queued or processing
        """
        async with self._lock:
            if order_id in self._processing:
                return True
            return any(item.order_id == order_id for item in self._queue)

    def _calculate_priority(self, order: Order, emergency: bool) -> int:
        """Calculate priority value for order.

        Args:
            order: Order to calculate priority for
            emergency: Whether this is an emergency order

        Returns:
            Priority value (lower = higher priority)
        """
        from walltrack.models.order import OrderType  # noqa: PLC0415

        if emergency:
            return OrderPriority.EMERGENCY

        if order.order_type != OrderType.EXIT:
            return OrderPriority.ENTRY

        # Map exit reasons to priorities
        exit_reason = (order.exit_reason or "").lower()
        reason_map = [
            ("stop_loss", OrderPriority.EXIT_STOP_LOSS),
            ("trailing", OrderPriority.EXIT_TRAILING),
            ("take_profit", OrderPriority.EXIT_TAKE_PROFIT),
            ("manual", OrderPriority.EXIT_MANUAL),
            ("emergency", OrderPriority.EXIT_MANUAL),
        ]

        return next(
            (priority for keyword, priority in reason_map if keyword in exit_reason),
            OrderPriority.EXIT_OTHER,
        )

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return len(self._queue)

    @property
    def processing_count(self) -> int:
        """Number of orders currently processing."""
        return len(self._processing)

    @property
    def available_slots(self) -> int:
        """Available processing slots."""
        return max(0, self._max_concurrent - len(self._processing))

    @property
    def max_concurrent(self) -> int:
        """Maximum concurrent orders."""
        return self._max_concurrent

    def get_stats(self) -> dict[str, int | float | dict[str, int]]:
        """Get queue statistics.

        Returns:
            Dict with queue statistics
        """
        avg_wait = (
            self._total_wait_time / self._processed_count
            if self._processed_count > 0
            else 0
        )

        # Count by priority
        priority_counts: dict[str, int] = {}
        for item in self._queue:
            try:
                prio_name = OrderPriority(item.priority).name
            except ValueError:
                prio_name = f"UNKNOWN_{item.priority}"
            priority_counts[prio_name] = priority_counts.get(prio_name, 0) + 1

        return {
            "queue_size": len(self._queue),
            "processing": len(self._processing),
            "available_slots": self.available_slots,
            "max_concurrent": self._max_concurrent,
            "total_processed": self._processed_count,
            "avg_wait_seconds": round(avg_wait, 1),
            "by_priority": priority_counts,
        }

    async def clear(self) -> int:
        """Clear all orders from queue.

        Returns:
            Number of orders cleared
        """
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            logger.info("queue_cleared", count=count)
            return count


# Singleton
_priority_queue: OrderPriorityQueue | None = None


def get_order_priority_queue(max_concurrent: int = 3) -> OrderPriorityQueue:
    """Get or create priority queue.

    Args:
        max_concurrent: Maximum concurrent orders (only used on first call)

    Returns:
        The singleton priority queue instance
    """
    global _priority_queue
    if _priority_queue is None:
        _priority_queue = OrderPriorityQueue(max_concurrent=max_concurrent)
    return _priority_queue


def reset_priority_queue() -> None:
    """Reset the priority queue singleton (for testing)."""
    global _priority_queue
    _priority_queue = None
