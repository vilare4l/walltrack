"""Async signal logger that batches writes for performance."""

import asyncio
import contextlib

import structlog

from walltrack.constants.signal_log import (
    LOG_BATCH_SIZE,
    LOG_FLUSH_INTERVAL_SECONDS,
    MAX_LOG_QUEUE_SIZE,
)
from walltrack.data.supabase.repositories.signal_repo import SignalRepository
from walltrack.models.signal_log import SignalLogEntry

logger = structlog.get_logger(__name__)


class AsyncSignalLogger:
    """Async signal logger that batches writes for performance.

    Ensures logging doesn't block the main processing pipeline (AC4).
    Uses a background task to flush batches to the database.
    """

    def __init__(
        self,
        signal_repo: SignalRepository,
        batch_size: int = LOG_BATCH_SIZE,
        flush_interval: int = LOG_FLUSH_INTERVAL_SECONDS,
    ):
        """Initialize async logger.

        Args:
            signal_repo: Repository for signal storage
            batch_size: Number of signals per batch
            flush_interval: Seconds between flushes
        """
        self.signal_repo = signal_repo
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._queue: asyncio.Queue[SignalLogEntry] = asyncio.Queue(
            maxsize=MAX_LOG_QUEUE_SIZE
        )
        self._running = False
        self._flush_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start background flush task."""
        if self._running:
            return

        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info(
            "async_logger_started",
            batch_size=self.batch_size,
            flush_interval=self.flush_interval,
        )

    async def stop(self) -> None:
        """Stop background flush task and flush remaining."""
        self._running = False

        if self._flush_task:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task

        # Flush remaining items
        await self._flush_batch()
        logger.info("async_logger_stopped")

    async def log(self, signal: SignalLogEntry) -> None:
        """Queue signal for async logging.

        Non-blocking to maintain < 500ms processing time (AC4).

        Args:
            signal: Signal entry to log
        """
        try:
            self._queue.put_nowait(signal)
        except asyncio.QueueFull:
            logger.warning(
                "signal_log_queue_full",
                queue_size=MAX_LOG_QUEUE_SIZE,
            )
            # Drop oldest and add new
            try:
                self._queue.get_nowait()
                self._queue.put_nowait(signal)
            except asyncio.QueueEmpty:
                pass

    async def log_immediate(self, signal: SignalLogEntry) -> str:
        """Log signal immediately (bypasses queue).

        Use for critical signals that must be persisted immediately.

        Args:
            signal: Signal entry to log

        Returns:
            Generated UUID
        """
        return await self.signal_repo.save(signal)

    async def _flush_loop(self) -> None:
        """Background loop to flush batches."""
        while self._running:
            try:
                await asyncio.sleep(self.flush_interval)
                await self._flush_batch()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("signal_flush_error", error=str(e))

    async def _flush_batch(self) -> None:
        """Flush current batch to database."""
        batch: list[SignalLogEntry] = []

        # Collect items from queue
        while len(batch) < self.batch_size:
            try:
                item = self._queue.get_nowait()
                batch.append(item)
            except asyncio.QueueEmpty:
                break

        if not batch:
            return

        try:
            await self.signal_repo.save_batch(batch)
            logger.debug(
                "signal_batch_flushed",
                count=len(batch),
            )
        except Exception as e:
            logger.error(
                "signal_batch_save_error",
                count=len(batch),
                error=str(e),
            )
            # Re-queue failed items
            for item in batch:
                try:
                    self._queue.put_nowait(item)
                except asyncio.QueueFull:
                    break

    async def flush_now(self) -> int:
        """Force immediate flush of all queued signals.

        Returns:
            Number of signals flushed
        """
        total_flushed = 0
        while not self._queue.empty():
            batch: list[SignalLogEntry] = []
            while len(batch) < self.batch_size and not self._queue.empty():
                try:
                    item = self._queue.get_nowait()
                    batch.append(item)
                except asyncio.QueueEmpty:
                    break

            if batch:
                try:
                    await self.signal_repo.save_batch(batch)
                    total_flushed += len(batch)
                except Exception as e:
                    logger.error("signal_flush_now_error", error=str(e))
                    break

        return total_flushed

    @property
    def queue_size(self) -> int:
        """Current queue size."""
        return self._queue.qsize()

    @property
    def is_running(self) -> bool:
        """Whether the logger is running."""
        return self._running


# Module-level singleton
_logger: AsyncSignalLogger | None = None


def get_async_logger(signal_repo: SignalRepository | None = None) -> AsyncSignalLogger:
    """Get or create async logger singleton.

    Args:
        signal_repo: Signal repository (required on first call)

    Returns:
        AsyncSignalLogger instance

    Raises:
        ValueError: If signal_repo is None on first call
    """
    global _logger
    if _logger is None:
        if signal_repo is None:
            raise ValueError("signal_repo required for first call")
        _logger = AsyncSignalLogger(signal_repo=signal_repo)
    return _logger


def reset_async_logger() -> None:
    """Reset async logger singleton (for testing)."""
    global _logger
    _logger = None
