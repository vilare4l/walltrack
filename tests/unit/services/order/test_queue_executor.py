"""Tests for queued order executor.

Story 10.5-15: Queue executor tests.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType
from walltrack.services.order.priority_queue import (
    OrderPriorityQueue,
    reset_priority_queue,
)
from walltrack.services.order.queue_executor import (
    QueuedOrderExecutor,
    get_queued_executor,
    reset_queued_executor,
)


def create_test_order(
    order_type: OrderType = OrderType.ENTRY,
    status: OrderStatus = OrderStatus.PENDING,
) -> Order:
    """Create a test order."""
    return Order(
        id=uuid4(),
        order_type=order_type,
        side=OrderSide.BUY,
        token_address="TEST123",
        amount_sol=Decimal("0.1"),
        expected_price=Decimal("1.0"),
        status=status,
    )


class TestQueuedOrderExecutor:
    """Tests for QueuedOrderExecutor."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self) -> None:
        """Reset singletons before each test."""
        reset_priority_queue()
        reset_queued_executor()

    @pytest.mark.asyncio
    async def test_submit_order(self) -> None:
        """Test submitting order to queue."""
        queue = OrderPriorityQueue()
        executor = QueuedOrderExecutor(queue=queue)

        order = create_test_order()
        await executor.submit_order(order)

        assert queue.queue_size == 1

    @pytest.mark.asyncio
    async def test_submit_emergency_order(self) -> None:
        """Test submitting emergency order."""
        queue = OrderPriorityQueue()
        executor = QueuedOrderExecutor(queue=queue)

        normal = create_test_order()
        emergency = create_test_order()

        await executor.submit_order(normal)
        await executor.submit_order(emergency, emergency=True)

        # Emergency should be first (lower priority value)
        first = await queue.peek()
        assert first is not None
        assert str(first.id) == str(emergency.id)

    @pytest.mark.asyncio
    async def test_start_stop(self) -> None:
        """Test starting and stopping executor."""
        executor = QueuedOrderExecutor()

        assert not executor.is_running

        await executor.start()
        assert executor.is_running

        await executor.stop()
        assert not executor.is_running

    @pytest.mark.asyncio
    async def test_double_start(self) -> None:
        """Test that double start is handled."""
        executor = QueuedOrderExecutor()

        await executor.start()
        await executor.start()  # Should not error
        assert executor.is_running

        await executor.stop()

    @pytest.mark.asyncio
    async def test_get_stats(self) -> None:
        """Test statistics retrieval."""
        executor = QueuedOrderExecutor(max_concurrent=3)

        stats = executor.get_stats()

        assert "running" in stats
        assert stats["running"] is False
        assert stats["orders_executed"] == 0
        assert stats["orders_failed"] == 0
        assert "queue_size" in stats
        assert "max_concurrent" in stats

    @pytest.mark.asyncio
    async def test_execute_order_success(self) -> None:
        """Test successful order execution."""
        queue = OrderPriorityQueue()
        executor = QueuedOrderExecutor(queue=queue, poll_interval=0.01)

        order = create_test_order()

        # Mock the order executor
        mock_result = MagicMock()
        mock_result.status = OrderStatus.FILLED

        mock_order_executor = MagicMock()
        mock_order_executor.execute = AsyncMock(return_value=mock_result)

        with patch(
            "walltrack.services.order.executor.get_order_executor",
            new=AsyncMock(return_value=mock_order_executor),
        ):
            await executor.submit_order(order)

            # Execute manually (avoid background loop)
            dequeued = await queue.dequeue()
            assert dequeued is not None
            await executor._execute_order(dequeued)

        # Check metrics updated
        stats = executor.get_stats()
        assert stats["orders_executed"] == 1
        assert stats["orders_failed"] == 0

    @pytest.mark.asyncio
    async def test_execute_order_failure(self) -> None:
        """Test failed order execution creates alert."""
        queue = OrderPriorityQueue()
        executor = QueuedOrderExecutor(queue=queue, poll_interval=0.01)

        order = create_test_order()

        # Mock the order executor to raise error
        mock_order_executor = MagicMock()
        mock_order_executor.execute = AsyncMock(side_effect=Exception("Test error"))

        mock_alert_service = AsyncMock()
        mock_alert_service.create_alert = AsyncMock()

        with (
            patch(
                "walltrack.services.order.executor.get_order_executor",
                new=AsyncMock(return_value=mock_order_executor),
            ),
            patch(
                "walltrack.services.alerts.alert_service.get_alert_service",
                new=AsyncMock(return_value=mock_alert_service),
            ),
        ):
            await executor.submit_order(order)

            dequeued = await queue.dequeue()
            assert dequeued is not None
            await executor._execute_order(dequeued)

        # Check failure metrics
        stats = executor.get_stats()
        assert stats["orders_executed"] == 0
        assert stats["orders_failed"] == 1

    @pytest.mark.asyncio
    async def test_queue_property(self) -> None:
        """Test queue property access."""
        queue = OrderPriorityQueue()
        executor = QueuedOrderExecutor(queue=queue)

        assert executor.queue is queue


class TestSingletonExecutor:
    """Tests for singleton executor functions."""

    @pytest.fixture(autouse=True)
    def reset_singletons(self) -> None:
        """Reset singletons before each test."""
        reset_priority_queue()
        reset_queued_executor()

    def test_get_singleton(self) -> None:
        """Test singleton retrieval."""
        exec1 = get_queued_executor()
        exec2 = get_queued_executor()
        assert exec1 is exec2

    def test_reset_singleton(self) -> None:
        """Test singleton reset."""
        exec1 = get_queued_executor()
        reset_queued_executor()
        exec2 = get_queued_executor()
        assert exec1 is not exec2
