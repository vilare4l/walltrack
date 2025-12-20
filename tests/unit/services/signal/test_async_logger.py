"""Unit tests for async signal logger."""

import asyncio
import time
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.models.signal_log import SignalLogEntry, SignalStatus
from walltrack.services.signal.async_logger import (
    AsyncSignalLogger,
    get_async_logger,
    reset_async_logger,
)


@pytest.fixture
def sample_signal() -> SignalLogEntry:
    """Sample signal for testing."""
    return SignalLogEntry(
        tx_signature="sig123456789012345678901234567890123456789012345",
        wallet_address="Wallet123456789012345678901234567890123456",
        token_address="Token12345678901234567890123456789012345678",
        direction="buy",
        amount_token=1000000,
        amount_sol=1.0,
        final_score=0.75,
        status=SignalStatus.SCORED,
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def mock_repo() -> MagicMock:
    """Mock signal repository."""
    repo = MagicMock()
    repo.save = AsyncMock(return_value="uuid-123")
    repo.save_batch = AsyncMock(return_value=["id1", "id2"])
    return repo


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset async logger singleton before each test."""
    reset_async_logger()
    yield
    reset_async_logger()


class TestAsyncSignalLoggerBasic:
    """Basic tests for AsyncSignalLogger."""

    @pytest.mark.asyncio
    async def test_queue_signal(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test signal is queued for async logging."""
        logger = AsyncSignalLogger(mock_repo, batch_size=10, flush_interval=60)

        await logger.log(sample_signal)

        assert logger.queue_size == 1

    @pytest.mark.asyncio
    async def test_queue_multiple_signals(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test multiple signals are queued."""
        logger = AsyncSignalLogger(mock_repo, batch_size=10, flush_interval=60)

        await logger.log(sample_signal)
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        assert logger.queue_size == 3

    @pytest.mark.asyncio
    async def test_non_blocking_log(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test that logging is non-blocking."""
        logger = AsyncSignalLogger(mock_repo)

        start = time.perf_counter()
        await logger.log(sample_signal)
        elapsed_ms = (time.perf_counter() - start) * 1000

        # Should be < 10ms (non-blocking)
        assert elapsed_ms < 10

    @pytest.mark.asyncio
    async def test_log_immediate(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test immediate logging bypasses queue."""
        logger = AsyncSignalLogger(mock_repo)

        result = await logger.log_immediate(sample_signal)

        assert result == "uuid-123"
        mock_repo.save.assert_called_once_with(sample_signal)
        assert logger.queue_size == 0


class TestAsyncSignalLoggerFlush:
    """Tests for batch flushing."""

    @pytest.mark.asyncio
    async def test_batch_flush_on_interval(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test batch is flushed after interval."""
        logger = AsyncSignalLogger(mock_repo, batch_size=100, flush_interval=1)
        await logger.start()

        # Queue signals
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        assert logger.queue_size == 2

        # Wait for flush
        await asyncio.sleep(1.5)

        await logger.stop()

        mock_repo.save_batch.assert_called()
        assert logger.queue_size == 0

    @pytest.mark.asyncio
    async def test_flush_now(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test force flush all queued signals."""
        logger = AsyncSignalLogger(mock_repo, batch_size=2, flush_interval=60)

        await logger.log(sample_signal)
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        assert logger.queue_size == 3

        flushed = await logger.flush_now()

        assert flushed == 3
        assert logger.queue_size == 0
        assert mock_repo.save_batch.call_count == 2  # 2 + 1 batches

    @pytest.mark.asyncio
    async def test_flush_on_stop(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test remaining signals are flushed on stop."""
        logger = AsyncSignalLogger(mock_repo, batch_size=100, flush_interval=60)
        await logger.start()

        await logger.log(sample_signal)
        await logger.log(sample_signal)

        await logger.stop()

        mock_repo.save_batch.assert_called()


class TestAsyncSignalLoggerQueueFull:
    """Tests for queue full handling."""

    @pytest.mark.asyncio
    async def test_queue_full_drops_oldest(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test handling when queue is full."""
        logger = AsyncSignalLogger(mock_repo, batch_size=100)
        # Replace with small queue
        logger._queue = asyncio.Queue(maxsize=2)

        # Fill queue
        await logger.log(sample_signal)
        await logger.log(sample_signal)

        # Should not raise, should drop oldest
        await logger.log(sample_signal)

        assert logger.queue_size == 2

    @pytest.mark.asyncio
    async def test_queue_full_logs_warning(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test warning is logged when queue is full."""
        logger = AsyncSignalLogger(mock_repo, batch_size=100)
        logger._queue = asyncio.Queue(maxsize=1)

        await logger.log(sample_signal)

        with patch("walltrack.services.signal.async_logger.logger") as mock_log:
            await logger.log(sample_signal)
            mock_log.warning.assert_called_once()


class TestAsyncSignalLoggerStartStop:
    """Tests for start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_creates_flush_task(
        self,
        mock_repo: MagicMock,
    ):
        """Test start creates background task."""
        logger = AsyncSignalLogger(mock_repo)

        assert not logger.is_running
        assert logger._flush_task is None

        await logger.start()

        assert logger.is_running
        assert logger._flush_task is not None

        await logger.stop()

    @pytest.mark.asyncio
    async def test_start_idempotent(
        self,
        mock_repo: MagicMock,
    ):
        """Test start is idempotent."""
        logger = AsyncSignalLogger(mock_repo)

        await logger.start()
        task1 = logger._flush_task

        await logger.start()
        task2 = logger._flush_task

        assert task1 is task2

        await logger.stop()

    @pytest.mark.asyncio
    async def test_stop_cancels_task(
        self,
        mock_repo: MagicMock,
    ):
        """Test stop cancels background task."""
        logger = AsyncSignalLogger(mock_repo, flush_interval=60)

        await logger.start()
        assert logger.is_running

        await logger.stop()

        assert not logger.is_running


class TestAsyncSignalLoggerErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_batch_save_error_requeues(
        self,
        sample_signal: SignalLogEntry,
        mock_repo: MagicMock,
    ):
        """Test failed batch save requeues signals."""
        mock_repo.save_batch = AsyncMock(side_effect=Exception("DB error"))

        logger = AsyncSignalLogger(mock_repo, batch_size=10, flush_interval=1)
        await logger.start()

        await logger.log(sample_signal)
        await logger.log(sample_signal)

        initial_size = logger.queue_size

        # Wait for flush attempt
        await asyncio.sleep(1.5)

        # Signals should be requeued
        assert logger.queue_size == initial_size

        await logger.stop()


class TestAsyncSignalLoggerSingleton:
    """Tests for singleton pattern."""

    def test_get_async_logger_requires_repo_first_call(self):
        """Test first call requires signal_repo."""
        with pytest.raises(ValueError) as exc_info:
            get_async_logger()

        assert "signal_repo required" in str(exc_info.value)

    def test_get_async_logger_creates_singleton(
        self,
        mock_repo: MagicMock,
    ):
        """Test singleton is created on first call."""
        logger1 = get_async_logger(mock_repo)
        logger2 = get_async_logger()

        assert logger1 is logger2

    def test_reset_clears_singleton(
        self,
        mock_repo: MagicMock,
    ):
        """Test reset clears the singleton."""
        _logger = get_async_logger(mock_repo)
        assert _logger is not None

        reset_async_logger()

        # Should require repo again
        with pytest.raises(ValueError):
            get_async_logger()
