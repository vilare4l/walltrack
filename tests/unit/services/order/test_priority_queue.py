"""Tests for order priority queue.

Story 10.5-15: Priority queue tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest

from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType
from walltrack.services.order.priority_queue import (
    OrderPriority,
    OrderPriorityQueue,
    get_order_priority_queue,
    reset_priority_queue,
)

if TYPE_CHECKING:
    pass


def create_test_order(
    order_type: OrderType = OrderType.ENTRY,
    exit_reason: str | None = None,
) -> Order:
    """Create a test order."""
    return Order(
        id=uuid4(),
        order_type=order_type,
        side=OrderSide.BUY,
        token_address="TEST123",
        amount_sol=Decimal("0.1"),
        expected_price=Decimal("1.0"),
        status=OrderStatus.PENDING,
        exit_reason=exit_reason,
    )


class TestOrderPriority:
    """Tests for OrderPriority enum."""

    def test_priority_ordering(self) -> None:
        """Test that priority values are correctly ordered."""
        assert OrderPriority.EMERGENCY < OrderPriority.EXIT_STOP_LOSS
        assert OrderPriority.EXIT_STOP_LOSS < OrderPriority.EXIT_TRAILING
        assert OrderPriority.EXIT_TRAILING < OrderPriority.EXIT_TAKE_PROFIT
        assert OrderPriority.EXIT_TAKE_PROFIT < OrderPriority.EXIT_MANUAL
        assert OrderPriority.EXIT_MANUAL < OrderPriority.EXIT_OTHER
        assert OrderPriority.EXIT_OTHER < OrderPriority.ENTRY

    def test_exit_before_entry(self) -> None:
        """Test that all EXIT priorities are higher than ENTRY."""
        assert OrderPriority.EXIT_STOP_LOSS < OrderPriority.ENTRY
        assert OrderPriority.EXIT_TRAILING < OrderPriority.ENTRY
        assert OrderPriority.EXIT_TAKE_PROFIT < OrderPriority.ENTRY
        assert OrderPriority.EXIT_MANUAL < OrderPriority.ENTRY
        assert OrderPriority.EXIT_OTHER < OrderPriority.ENTRY


class TestOrderPriorityQueue:
    """Tests for OrderPriorityQueue."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_priority_queue()

    @pytest.mark.asyncio
    async def test_enqueue_and_dequeue(self) -> None:
        """Test basic enqueue and dequeue."""
        queue = OrderPriorityQueue()
        order = create_test_order()

        await queue.enqueue(order)
        assert queue.queue_size == 1

        dequeued = await queue.dequeue()
        assert dequeued is not None
        assert str(dequeued.id) == str(order.id)
        assert queue.queue_size == 0

    @pytest.mark.asyncio
    async def test_priority_ordering_exit_before_entry(self) -> None:
        """Test that EXIT orders come before ENTRY orders."""
        queue = OrderPriorityQueue()

        entry_order = create_test_order(OrderType.ENTRY)
        exit_order = create_test_order(OrderType.EXIT)

        # Enqueue entry first, then exit
        await queue.enqueue(entry_order)
        await queue.enqueue(exit_order)

        # Exit should come out first
        first = await queue.dequeue()
        assert first is not None
        assert first.order_type == OrderType.EXIT

        await queue.mark_complete(str(first.id))

        second = await queue.dequeue()
        assert second is not None
        assert second.order_type == OrderType.ENTRY

    @pytest.mark.asyncio
    async def test_exit_priority_by_reason(self) -> None:
        """Test exit orders prioritized by reason."""
        queue = OrderPriorityQueue()

        take_profit = create_test_order(OrderType.EXIT, exit_reason="take_profit hit")
        stop_loss = create_test_order(OrderType.EXIT, exit_reason="stop_loss triggered")
        trailing = create_test_order(OrderType.EXIT, exit_reason="trailing stop")

        # Enqueue in reverse priority order
        await queue.enqueue(take_profit)
        await queue.enqueue(trailing)
        await queue.enqueue(stop_loss)

        # Should come out in priority order
        first = await queue.dequeue()
        assert first is not None
        assert "stop_loss" in (first.exit_reason or "")
        await queue.mark_complete(str(first.id))

        second = await queue.dequeue()
        assert second is not None
        assert "trailing" in (second.exit_reason or "")
        await queue.mark_complete(str(second.id))

        third = await queue.dequeue()
        assert third is not None
        assert "take_profit" in (third.exit_reason or "")

    @pytest.mark.asyncio
    async def test_emergency_priority(self) -> None:
        """Test emergency orders have highest priority."""
        queue = OrderPriorityQueue()

        normal_exit = create_test_order(OrderType.EXIT, exit_reason="stop_loss")
        emergency_entry = create_test_order(OrderType.ENTRY)

        await queue.enqueue(normal_exit)
        await queue.enqueue(emergency_entry, emergency=True)

        # Emergency should come first even though it's an entry
        first = await queue.dequeue()
        assert first is not None
        assert str(first.id) == str(emergency_entry.id)

    @pytest.mark.asyncio
    async def test_concurrency_limit(self) -> None:
        """Test that dequeue respects concurrency limit."""
        queue = OrderPriorityQueue(max_concurrent=2)

        order1 = create_test_order()
        order2 = create_test_order()
        order3 = create_test_order()

        await queue.enqueue(order1)
        await queue.enqueue(order2)
        await queue.enqueue(order3)

        # Dequeue first two
        d1 = await queue.dequeue()
        d2 = await queue.dequeue()
        assert d1 is not None
        assert d2 is not None

        # Third should return None (at limit)
        d3 = await queue.dequeue()
        assert d3 is None

        # Complete one, then third should work
        await queue.mark_complete(str(d1.id))
        d3 = await queue.dequeue()
        assert d3 is not None

    @pytest.mark.asyncio
    async def test_remove_from_queue(self) -> None:
        """Test removing order from queue."""
        queue = OrderPriorityQueue()

        order1 = create_test_order()
        order2 = create_test_order()

        await queue.enqueue(order1)
        await queue.enqueue(order2)

        removed = await queue.remove(str(order1.id))
        assert removed is True
        assert queue.queue_size == 1

        # Can't remove again
        removed2 = await queue.remove(str(order1.id))
        assert removed2 is False

    @pytest.mark.asyncio
    async def test_peek(self) -> None:
        """Test peek without removing."""
        queue = OrderPriorityQueue()

        order = create_test_order()
        await queue.enqueue(order)

        peeked = await queue.peek()
        assert peeked is not None
        assert str(peeked.id) == str(order.id)
        assert queue.queue_size == 1  # Still in queue

    @pytest.mark.asyncio
    async def test_contains(self) -> None:
        """Test checking if order is in queue or processing."""
        queue = OrderPriorityQueue()

        order = create_test_order()
        assert await queue.contains(str(order.id)) is False

        await queue.enqueue(order)
        assert await queue.contains(str(order.id)) is True

        # Dequeue (now processing)
        await queue.dequeue()
        assert await queue.contains(str(order.id)) is True

        # Mark complete
        await queue.mark_complete(str(order.id))
        assert await queue.contains(str(order.id)) is False

    @pytest.mark.asyncio
    async def test_clear(self) -> None:
        """Test clearing the queue."""
        queue = OrderPriorityQueue()

        for _ in range(5):
            await queue.enqueue(create_test_order())

        assert queue.queue_size == 5

        cleared = await queue.clear()
        assert cleared == 5
        assert queue.queue_size == 0

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        queue = OrderPriorityQueue(max_concurrent=3)

        entry = create_test_order(OrderType.ENTRY)
        exit_order = create_test_order(OrderType.EXIT)

        await queue.enqueue(entry)
        await queue.enqueue(exit_order)

        stats = queue.get_stats()

        assert stats["queue_size"] == 2
        assert stats["processing"] == 0
        assert stats["max_concurrent"] == 3
        assert stats["available_slots"] == 3
        assert "ENTRY" in stats["by_priority"]

    @pytest.mark.asyncio
    async def test_fifo_within_same_priority(self) -> None:
        """Test that orders with same priority maintain FIFO order."""
        queue = OrderPriorityQueue()

        orders = [create_test_order() for _ in range(3)]

        for order in orders:
            await queue.enqueue(order)

        # Should come out in order they were added
        for expected in orders:
            dequeued = await queue.dequeue()
            assert dequeued is not None
            assert str(dequeued.id) == str(expected.id)
            await queue.mark_complete(str(dequeued.id))


class TestSingletonQueue:
    """Tests for singleton queue functions."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        reset_priority_queue()

    def test_get_singleton(self) -> None:
        """Test singleton retrieval."""
        queue1 = get_order_priority_queue()
        queue2 = get_order_priority_queue()
        assert queue1 is queue2

    def test_reset_singleton(self) -> None:
        """Test singleton reset."""
        queue1 = get_order_priority_queue()
        reset_priority_queue()
        queue2 = get_order_priority_queue()
        assert queue1 is not queue2
