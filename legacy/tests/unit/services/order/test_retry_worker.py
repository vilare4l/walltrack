"""Tests for order retry worker.

Story 10.5-12: Tests for automated order retry processing.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType
from walltrack.services.order.retry_worker import (
    RetryMetrics,
    RetryWorker,
    reset_retry_worker,
)


def create_test_order(
    order_type: OrderType = OrderType.ENTRY,
    status: OrderStatus = OrderStatus.FAILED,
    attempt_count: int = 1,
    next_retry_at: datetime | None = None,
) -> Order:
    """Create a test order."""
    return Order(
        id=uuid4(),
        order_type=order_type,
        side=OrderSide.BUY if order_type == OrderType.ENTRY else OrderSide.SELL,
        token_address="TokenAddr123456789012345678901234567890123",
        token_symbol="TEST",
        amount_sol=Decimal("0.5"),
        expected_price=Decimal("0.001"),
        status=status,
        attempt_count=attempt_count,
        max_attempts=3,
        next_retry_at=next_retry_at or datetime.utcnow() - timedelta(seconds=10),
    )


class TestRetryMetrics:
    """Tests for RetryMetrics."""

    def test_initial_values(self) -> None:
        """Test initial metric values."""
        metrics = RetryMetrics()

        assert metrics.retries_attempted == 0
        assert metrics.retries_succeeded == 0
        assert metrics.retries_failed == 0
        assert metrics.success_rate_pct == 0.0

    def test_record_successful_attempt(self) -> None:
        """Test recording successful attempt."""
        metrics = RetryMetrics()
        metrics.record_attempt(success=True)

        assert metrics.retries_attempted == 1
        assert metrics.retries_succeeded == 1
        assert metrics.retries_failed == 0
        assert metrics.success_rate_pct == 100.0

    def test_record_failed_attempt(self) -> None:
        """Test recording failed attempt."""
        metrics = RetryMetrics()
        metrics.record_attempt(success=False)

        assert metrics.retries_attempted == 1
        assert metrics.retries_succeeded == 0
        assert metrics.retries_failed == 1
        assert metrics.success_rate_pct == 0.0

    def test_success_rate_calculation(self) -> None:
        """Test success rate calculation."""
        metrics = RetryMetrics()
        metrics.record_attempt(success=True)
        metrics.record_attempt(success=True)
        metrics.record_attempt(success=False)

        assert metrics.retries_attempted == 3
        assert metrics.success_rate_pct == 66.7

    def test_to_dict(self) -> None:
        """Test metrics serialization."""
        metrics = RetryMetrics()
        metrics.record_attempt(success=True)
        metrics.record_run(orders_processed=5)

        result = metrics.to_dict()

        assert result["retries_attempted"] == 1
        assert result["retries_succeeded"] == 1
        assert result["orders_processed_last_run"] == 5
        assert result["last_run_at"] is not None


class TestRetryWorker:
    """Tests for RetryWorker."""

    @pytest.fixture
    def mock_order_repo(self) -> MagicMock:
        """Create mock order repository."""
        repo = MagicMock()
        repo.get_pending_retries = AsyncMock(return_value=[])
        repo.acquire_lock = AsyncMock(return_value=True)
        repo.release_lock = AsyncMock()
        repo.update = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock order executor."""
        executor = MagicMock()
        executor.execute = AsyncMock()
        return executor

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_retry_worker()

    async def test_worker_starts_and_stops(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker can be started and stopped."""
        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
            poll_interval=0.1,
        )

        assert not worker.is_running

        await worker.start()
        assert worker.is_running

        await worker.stop()
        assert not worker.is_running

    async def test_worker_processes_no_orders(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker handles no pending orders."""
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[])

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        processed = await worker.process_once()

        assert processed == 0
        mock_order_repo.get_pending_retries.assert_called_once()
        mock_executor.execute.assert_not_called()

    async def test_worker_processes_single_order(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker processes a single order."""
        order = create_test_order()
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_executor.execute = AsyncMock(
            return_value=MagicMock(
                success=True,
                tx_signature="tx123",
            )
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        processed = await worker.process_once()

        assert processed == 1
        mock_order_repo.acquire_lock.assert_called_once()
        mock_executor.execute.assert_called_once()
        mock_order_repo.release_lock.assert_called_once()
        assert worker.metrics.retries_succeeded == 1

    async def test_worker_skips_locked_orders(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker skips orders that cannot be locked."""
        order = create_test_order()
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_order_repo.acquire_lock = AsyncMock(return_value=False)

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        processed = await worker.process_once()

        assert processed == 0
        mock_executor.execute.assert_not_called()

    async def test_worker_tracks_failed_retries(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker tracks failed retry attempts."""
        order = create_test_order(attempt_count=1)
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_order_repo.get_by_id = AsyncMock(return_value=create_test_order(attempt_count=2))
        mock_executor.execute = AsyncMock(
            return_value=MagicMock(
                success=False,
                error="Network error",
            )
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        processed = await worker.process_once()

        assert processed == 1
        assert worker.metrics.retries_failed == 1

    async def test_worker_handles_max_attempts_reached(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker handles order that exhausted all retries."""
        # Order at max attempts (can't retry anymore)
        order = create_test_order(attempt_count=3)
        exhausted_order = create_test_order(attempt_count=3)
        exhausted_order.status = OrderStatus.FAILED

        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_order_repo.get_by_id = AsyncMock(return_value=exhausted_order)
        mock_executor.execute = AsyncMock(
            return_value=MagicMock(
                success=False,
                error="Final failure",
            )
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        processed = await worker.process_once()

        assert processed == 1
        # Order should be cancelled when max attempts reached
        mock_order_repo.update.assert_called()


class TestRetryWorkerPriority:
    """Tests for retry worker priority ordering."""

    @pytest.fixture
    def mock_order_repo(self) -> MagicMock:
        """Create mock order repository."""
        repo = MagicMock()
        repo.acquire_lock = AsyncMock(return_value=True)
        repo.release_lock = AsyncMock()
        repo.update = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock order executor."""
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=MagicMock(success=True, tx_signature="tx")
        )
        return executor

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_retry_worker()

    async def test_exit_orders_processed_first(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test EXIT orders are processed before ENTRY."""
        entry_order = create_test_order(order_type=OrderType.ENTRY)
        exit_order = create_test_order(order_type=OrderType.EXIT)

        # Return orders in the order the worker should process them
        # (already prioritized by repo)
        mock_order_repo.get_pending_retries = AsyncMock(
            return_value=[exit_order, entry_order]
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        await worker.process_once()

        # Verify exit was processed first
        calls = mock_executor.execute.call_args_list
        assert len(calls) == 2
        assert calls[0][0][0].order_type == OrderType.EXIT
        assert calls[1][0][0].order_type == OrderType.ENTRY


class TestRetryWorkerLocking:
    """Tests for retry worker locking behavior."""

    @pytest.fixture
    def mock_order_repo(self) -> MagicMock:
        """Create mock order repository."""
        repo = MagicMock()
        repo.get_pending_retries = AsyncMock(return_value=[])
        repo.acquire_lock = AsyncMock(return_value=True)
        repo.release_lock = AsyncMock()
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock order executor."""
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=MagicMock(success=True, tx_signature="tx")
        )
        return executor

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_retry_worker()

    async def test_lock_released_on_success(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test lock is released after successful processing."""
        order = create_test_order()
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        await worker.process_once()

        mock_order_repo.release_lock.assert_called_once_with(order.id)

    async def test_lock_released_on_failure(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test lock is released even on failure."""
        order = create_test_order()
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_order_repo.get_by_id = AsyncMock(return_value=order)
        mock_executor.execute = AsyncMock(
            return_value=MagicMock(success=False, error="Error")
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        await worker.process_once()

        mock_order_repo.release_lock.assert_called_once_with(order.id)

    async def test_lock_released_on_exception(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test lock is released even when exception occurs."""
        order = create_test_order()
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_executor.execute = AsyncMock(side_effect=Exception("Unexpected error"))

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        # Should not raise
        with pytest.raises(Exception):
            await worker.process_once()

        # Lock should still be released
        mock_order_repo.release_lock.assert_called_once_with(order.id)


class TestRetryWorkerBatchSize:
    """Tests for retry worker batch size."""

    @pytest.fixture
    def mock_order_repo(self) -> MagicMock:
        """Create mock order repository."""
        repo = MagicMock()
        repo.acquire_lock = AsyncMock(return_value=True)
        repo.release_lock = AsyncMock()
        repo.update = AsyncMock()
        return repo

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock order executor."""
        executor = MagicMock()
        executor.execute = AsyncMock(
            return_value=MagicMock(success=True, tx_signature="tx")
        )
        return executor

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_retry_worker()

    async def test_respects_batch_size(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test worker respects batch size limit."""
        orders = [create_test_order() for _ in range(5)]
        mock_order_repo.get_pending_retries = AsyncMock(return_value=orders)

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
            batch_size=5,
        )

        processed = await worker.process_once()

        assert processed == 5
        # Repository should have been called with correct limit
        mock_order_repo.get_pending_retries.assert_called_once_with(limit=5)


class TestRetryWorkerOrderStatusTransitions:
    """Tests for order status transitions during retry."""

    @pytest.fixture
    def mock_order_repo(self) -> MagicMock:
        """Create mock order repository."""
        repo = MagicMock()
        repo.acquire_lock = AsyncMock(return_value=True)
        repo.release_lock = AsyncMock()
        repo.update = AsyncMock()
        repo.get_by_id = AsyncMock()
        return repo

    @pytest.fixture
    def mock_executor(self) -> MagicMock:
        """Create mock order executor."""
        return MagicMock()

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_retry_worker()

    async def test_failed_order_transitions_to_pending(
        self,
        mock_order_repo: MagicMock,
        mock_executor: MagicMock,
    ) -> None:
        """Test failed order transitions to pending for retry."""
        order = create_test_order(status=OrderStatus.FAILED)
        mock_order_repo.get_pending_retries = AsyncMock(return_value=[order])
        mock_executor.execute = AsyncMock(
            return_value=MagicMock(success=True, tx_signature="tx")
        )

        worker = RetryWorker(
            order_repo=mock_order_repo,
            executor=mock_executor,
        )

        await worker.process_once()

        # Order should have been updated (transition to pending)
        mock_order_repo.update.assert_called()
