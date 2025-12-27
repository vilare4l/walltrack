"""Worker for processing order retries.

Story 10.5-12: Background worker for automated order retry processing.

Features:
- Polls every 5 seconds for orders needing retry
- Prioritizes EXIT orders over ENTRY orders
- Uses optimistic locking to prevent double execution
- Tracks retry metrics for monitoring
- Creates alerts on max attempts reached
"""

from __future__ import annotations

import asyncio
import contextlib
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from walltrack.data.supabase.repositories.order_repo import (
    OrderRepository,
    get_order_repository,
)
from walltrack.models.order import Order, OrderStatus, OrderType

if TYPE_CHECKING:
    from walltrack.services.order.executor import OrderExecutor

logger = structlog.get_logger(__name__)

# Worker constants
DEFAULT_POLL_INTERVAL = 5.0  # seconds
DEFAULT_BATCH_SIZE = 10
DEFAULT_LOCK_TIMEOUT = 60  # seconds


class RetryMetrics:
    """Metrics for retry worker monitoring."""

    def __init__(self) -> None:
        self.retries_attempted: int = 0
        self.retries_succeeded: int = 0
        self.retries_failed: int = 0
        self.last_run_at: datetime | None = None
        self.orders_processed_last_run: int = 0

    def record_attempt(self, success: bool) -> None:
        """Record a retry attempt."""
        self.retries_attempted += 1
        if success:
            self.retries_succeeded += 1
        else:
            self.retries_failed += 1

    def record_run(self, orders_processed: int) -> None:
        """Record a worker run."""
        self.last_run_at = datetime.utcnow()
        self.orders_processed_last_run = orders_processed

    @property
    def success_rate_pct(self) -> float:
        """Calculate success rate percentage."""
        if self.retries_attempted == 0:
            return 0.0
        return round(self.retries_succeeded / self.retries_attempted * 100, 1)

    def to_dict(self) -> dict[str, int | float | str | None]:
        """Convert metrics to dictionary."""
        return {
            "retries_attempted": self.retries_attempted,
            "retries_succeeded": self.retries_succeeded,
            "retries_failed": self.retries_failed,
            "success_rate_pct": self.success_rate_pct,
            "last_run_at": self.last_run_at.isoformat() if self.last_run_at else None,
            "orders_processed_last_run": self.orders_processed_last_run,
        }


class RetryWorker:
    """Background worker for processing order retries.

    Runs periodically to check for orders needing retry
    and executes them with proper ordering.
    """

    def __init__(
        self,
        order_repo: OrderRepository,
        executor: OrderExecutor,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        lock_timeout_seconds: int = DEFAULT_LOCK_TIMEOUT,
    ) -> None:
        """Initialize retry worker.

        Args:
            order_repo: Repository for order persistence
            executor: Order executor for trade execution
            poll_interval: Seconds between polling cycles
            batch_size: Max orders to process per cycle
            lock_timeout_seconds: Lock timeout for order processing
        """
        self.order_repo = order_repo
        self.executor = executor
        self.poll_interval = poll_interval
        self.batch_size = batch_size
        self.lock_timeout = lock_timeout_seconds

        self._running = False
        self._task: asyncio.Task[None] | None = None
        self._metrics = RetryMetrics()
        self._worker_id = f"retry_worker_{id(self)}"

    @property
    def is_running(self) -> bool:
        """Check if worker is running."""
        return self._running

    @property
    def metrics(self) -> RetryMetrics:
        """Get worker metrics."""
        return self._metrics

    async def start(self) -> None:
        """Start the retry worker."""
        if self._running:
            logger.warning("retry_worker_already_running", worker_id=self._worker_id)
            return

        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(
            "retry_worker_started",
            worker_id=self._worker_id,
            poll_interval=self.poll_interval,
            batch_size=self.batch_size,
        )

    async def stop(self) -> None:
        """Stop the retry worker."""
        if not self._running:
            return

        self._running = False
        if self._task:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

        logger.info("retry_worker_stopped", worker_id=self._worker_id)

    async def _run_loop(self) -> None:
        """Main worker loop."""
        while self._running:
            try:
                await self._process_pending_retries()
            except Exception as e:
                logger.error(
                    "retry_worker_error",
                    worker_id=self._worker_id,
                    error=str(e),
                )

            await asyncio.sleep(self.poll_interval)

    async def _process_pending_retries(self) -> None:
        """Process all pending retries."""
        # Get orders ready for retry, prioritized
        orders = await self.order_repo.get_pending_retries(limit=self.batch_size)

        if not orders:
            self._metrics.record_run(0)
            return

        logger.debug(
            "processing_retries",
            worker_id=self._worker_id,
            count=len(orders),
        )

        processed = 0
        for order in orders:
            # Acquire lock
            if not await self._acquire_lock(order):
                continue

            try:
                await self._process_single_retry(order)
                processed += 1
            finally:
                await self._release_lock(order)

        self._metrics.record_run(processed)

    async def _acquire_lock(self, order: Order) -> bool:
        """Acquire processing lock for order."""
        acquired = await self.order_repo.acquire_lock(
            order_id=order.id,
            lock_by=self._worker_id,
            lock_timeout_seconds=self.lock_timeout,
        )

        if not acquired:
            logger.debug(
                "order_lock_failed",
                order_id=str(order.id)[:8],
                worker_id=self._worker_id,
            )

        return acquired

    async def _release_lock(self, order: Order) -> None:
        """Release processing lock for order."""
        await self.order_repo.release_lock(order.id)

    async def _process_single_retry(self, order: Order) -> None:
        """Process a single order retry."""
        log = logger.bind(
            order_id=str(order.id)[:8],
            order_type=order.order_type.value,
            attempt=order.attempt_count + 1,
            token=order.token_symbol or order.token_address[:8],
        )

        log.info("processing_retry")

        # Move from FAILED to PENDING for retry (if can retry)
        if order.status == OrderStatus.FAILED and order.can_retry:
            order.schedule_retry()
            await self.order_repo.update(order)

        # Execute via executor
        result = await self.executor.execute(order)

        if result.success:
            log.info(
                "retry_succeeded",
                tx_signature=result.tx_signature[:8] if result.tx_signature else None,
            )
            self._metrics.record_attempt(success=True)

            # Handle position creation/update based on order type
            await self._handle_order_filled(order)

        else:
            log.warning("retry_failed", error=result.error)
            self._metrics.record_attempt(success=False)

            # Reload order to get updated attempt count
            updated_order = await self.order_repo.get_by_id(order.id)
            if updated_order and not updated_order.can_retry:
                await self._handle_max_attempts_reached(updated_order)

    async def _handle_order_filled(self, order: Order) -> None:
        """Handle successful order fill."""
        if order.order_type == OrderType.ENTRY:
            await self._handle_entry_filled(order)
        elif order.order_type == OrderType.EXIT:
            await self._handle_exit_filled(order)

        # Resolve any existing alert for this order
        await self._resolve_order_alert(order)

    async def _handle_entry_filled(self, order: Order) -> None:
        """Handle successful entry order fill."""
        log = logger.bind(order_id=str(order.id)[:8])
        log.info("entry_order_filled_via_retry")

        # Entry service handles position creation during execute
        # No additional action needed here

    async def _handle_exit_filled(self, order: Order) -> None:
        """Handle successful exit order fill."""
        log = logger.bind(
            order_id=str(order.id)[:8],
            position_id=order.position_id[:8] if order.position_id else None,
        )
        log.info("exit_order_filled_via_retry")

    async def _resolve_order_alert(self, order: Order) -> None:
        """Resolve any existing alert for this order."""
        try:
            from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                get_alert_service,
            )

            alert_service = await get_alert_service()
            dedupe_key = f"order_failed_{order.id}"
            resolved = await alert_service.resolve_by_dedupe_key(
                dedupe_key=dedupe_key,
                resolution="Order completed successfully",
            )
            if resolved:
                logger.info(
                    "order_alert_resolved",
                    order_id=str(order.id)[:8],
                )
        except ImportError:
            pass  # Alert service not available
        except Exception as e:
            logger.warning("alert_resolution_failed", error=str(e))

        # Exit service handles position update during execute
        # No additional action needed here

    async def _handle_max_attempts_reached(self, order: Order) -> None:
        """Handle order that has exhausted all retries."""
        log = logger.bind(
            order_id=str(order.id)[:8],
            attempts=order.attempt_count,
            max_attempts=order.max_attempts,
        )

        # Cancel the order permanently
        order.cancel(f"Max retries reached ({order.max_attempts} attempts)")
        await self.order_repo.update(order)

        # Determine severity based on order type
        severity = "critical" if order.order_type == OrderType.EXIT else "high"

        # Create alert (Story 10.5-14 will implement full alert service)
        log.error(
            "order_failed_permanently",
            severity=severity,
            last_error=order.last_error,
        )

        # Try to create alert via alert service if available
        try:
            from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                get_alert_service,
            )

            alert_service = await get_alert_service()
            await alert_service.create_alert(
                alert_type="order_failed_permanently",
                severity=severity,
                title=f"{order.order_type.value.upper()} Order Failed - Manual Action Required",
                message=(
                    f"Order {str(order.id)[:8]} for "
                    f"{order.token_symbol or order.token_address[:8]} "
                    f"failed after {order.attempt_count} attempts. "
                    f"Last error: {order.last_error}"
                ),
                data={
                    "order_id": str(order.id),
                    "order_type": order.order_type.value,
                    "token_address": order.token_address,
                    "position_id": order.position_id,
                    "error": order.last_error,
                },
                requires_action=True,
                dedupe_key=f"order_failed_{order.id}",
            )
        except ImportError:
            # Alert service not yet implemented
            log.warning("alert_service_not_available")
        except Exception as e:
            log.warning("alert_creation_failed", error=str(e))

    async def process_once(self) -> int:
        """Process pending retries once (for testing).

        Returns:
            Number of orders processed
        """
        orders = await self.order_repo.get_pending_retries(limit=self.batch_size)

        processed = 0
        for order in orders:
            if not await self._acquire_lock(order):
                continue

            try:
                await self._process_single_retry(order)
                processed += 1
            finally:
                await self._release_lock(order)

        self._metrics.record_run(processed)
        return processed


# Singleton
_retry_worker: RetryWorker | None = None


async def get_retry_worker() -> RetryWorker:
    """Get or create retry worker singleton."""
    global _retry_worker
    if _retry_worker is None:
        from walltrack.services.order.executor import get_order_executor  # noqa: PLC0415

        order_repo = await get_order_repository()
        executor = await get_order_executor()
        _retry_worker = RetryWorker(
            order_repo=order_repo,
            executor=executor,
        )
    return _retry_worker


async def start_retry_worker() -> None:
    """Start the retry worker."""
    worker = await get_retry_worker()
    await worker.start()


async def stop_retry_worker() -> None:
    """Stop the retry worker."""
    worker = await get_retry_worker()
    await worker.stop()


def reset_retry_worker() -> None:
    """Reset singleton for testing."""
    global _retry_worker
    _retry_worker = None
