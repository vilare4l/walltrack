"""Tests for position limit manager (Story 5-4)."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from walltrack.models.risk import (
    PositionLimitConfig,
    QueuedSignal,
)
from walltrack.core.risk.position_limits import (
    PositionLimitManager,
    get_position_limit_manager,
    reset_position_limit_manager,
)


@pytest.fixture
def limit_config() -> PositionLimitConfig:
    """Create test configuration."""
    return PositionLimitConfig(
        max_positions=5,
        enable_queue=True,
        max_queue_size=10,
        queue_expiry_minutes=60,
    )


@pytest.fixture
def manager(limit_config: PositionLimitConfig) -> PositionLimitManager:
    """Create test manager instance."""
    return PositionLimitManager(limit_config)


class TestPositionLimitCheck:
    """Test position limit check logic (AC 1, AC 2)."""

    @pytest.mark.asyncio
    async def test_can_open_when_below_limit(
        self, manager: PositionLimitManager
    ) -> None:
        """Can open when below position limit."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=3))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.check_can_open()

            assert result.can_open is True
            assert result.current_positions == 3
            assert result.slots_available == 2

    @pytest.mark.asyncio
    async def test_cannot_open_at_limit(
        self, manager: PositionLimitManager
    ) -> None:
        """Cannot open when at position limit."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=5))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.check_can_open()

            assert result.can_open is False
            assert result.slots_available == 0

    @pytest.mark.asyncio
    async def test_cannot_open_above_limit(
        self, manager: PositionLimitManager
    ) -> None:
        """Cannot open when above position limit."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=7))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.check_can_open()

            assert result.can_open is False
            assert result.slots_available == 0

    @pytest.mark.asyncio
    async def test_get_open_position_count(
        self, manager: PositionLimitManager
    ) -> None:
        """Get current open position count from database."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=3))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            count = await manager.get_open_position_count()

            assert count == 3


class TestPositionRequest:
    """Test position request handling (AC 2, AC 3)."""

    @pytest.mark.asyncio
    async def test_request_allowed_below_limit(
        self, manager: PositionLimitManager
    ) -> None:
        """Request allowed when below limit."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=3))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result is True

    @pytest.mark.asyncio
    async def test_request_queued_at_limit(
        self, manager: PositionLimitManager
    ) -> None:
        """Request queued when at limit."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=5))
        )
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "queue-1"}])
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result.blocked is True
            assert result.queued is True
            assert result.queue_position == 1
            assert result.reason == "max_positions_reached"

    @pytest.mark.asyncio
    async def test_request_blocked_no_queue(
        self, limit_config: PositionLimitConfig
    ) -> None:
        """Request blocked without queue when disabled."""
        config = limit_config.model_copy(update={"enable_queue": False})
        manager = PositionLimitManager(config)

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=5))
        )
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await manager.request_position("sig-1", {"token": "PUMP"})

            assert result.blocked is True
            assert result.queued is False


class TestSignalQueue:
    """Test signal queue management (AC 4)."""

    @pytest.mark.asyncio
    async def test_queue_fifo_order(
        self, manager: PositionLimitManager
    ) -> None:
        """Queue maintains FIFO order."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=5))
        )
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "queue-1"}])
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.request_position("sig-1", {})

            mock_db.table.return_value.insert.return_value.execute = AsyncMock(
                return_value=MagicMock(data=[{"id": "queue-2"}])
            )
            await manager.request_position("sig-2", {})

            queue = await manager.get_queue_status()

            assert len(queue) == 2
            assert queue[0].signal_id == "sig-1"
            assert queue[1].signal_id == "sig-2"

    @pytest.mark.asyncio
    async def test_queue_max_size_removes_oldest(
        self, limit_config: PositionLimitConfig
    ) -> None:
        """Queue removes oldest when max size reached."""
        config = limit_config.model_copy(update={"max_queue_size": 2})
        manager = PositionLimitManager(config)

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=5))
        )
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "queue-x"}])
        )
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.request_position("sig-1", {})
            await manager.request_position("sig-2", {})
            await manager.request_position("sig-3", {})

            queue = await manager.get_queue_status()

            assert len(queue) == 2
            # sig-1 should have been removed
            assert queue[0].signal_id == "sig-2"

    @pytest.mark.asyncio
    async def test_queue_get_status(
        self, manager: PositionLimitManager
    ) -> None:
        """Get queue status returns queued signals."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={},
        )
        manager._signal_queue.append(signal)

        queue = await manager.get_queue_status()

        assert len(queue) == 1
        assert queue[0].signal_id == "sig-1"


class TestPositionClosed:
    """Test position closed handling (AC 4)."""

    @pytest.mark.asyncio
    async def test_execute_next_on_close(
        self, manager: PositionLimitManager
    ) -> None:
        """Next queued signal executes when position closes."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={"token": "PUMP"},
        )
        manager._signal_queue.append(signal)

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            executed = await manager.on_position_closed("pos-1")

            assert executed is not None
            assert executed.signal_id == "sig-1"
            assert len(manager._signal_queue) == 0

    @pytest.mark.asyncio
    async def test_no_execute_empty_queue(
        self, manager: PositionLimitManager
    ) -> None:
        """Nothing executes when queue is empty."""
        mock_db = MagicMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            executed = await manager.on_position_closed("pos-1")

            assert executed is None

    @pytest.mark.asyncio
    async def test_execute_callback_called(
        self, manager: PositionLimitManager
    ) -> None:
        """Execute callback is called when signal executes."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={"token": "PUMP"},
        )
        manager._signal_queue.append(signal)

        callback = AsyncMock(return_value=True)
        manager.set_execute_callback(callback)

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.on_position_closed("pos-1")

            callback.assert_called_once_with({"token": "PUMP"})

    @pytest.mark.asyncio
    async def test_records_slot_event(
        self, manager: PositionLimitManager
    ) -> None:
        """Records position slot event when executing queued signal."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={},
        )
        manager._signal_queue.append(signal)

        mock_db = MagicMock()
        insert_mock = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = insert_mock
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.on_position_closed("pos-1")

            # Verify position_slot_events was inserted
            calls = mock_db.table.call_args_list
            slot_events_called = any(
                call[0][0] == "position_slot_events" for call in calls
            )
            assert slot_events_called


class TestExpiredSignals:
    """Test expired signal handling."""

    @pytest.mark.asyncio
    async def test_clean_expired_signals(
        self, manager: PositionLimitManager
    ) -> None:
        """Expired signals are removed from queue."""
        expired_signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() - timedelta(hours=1),  # Already expired
            signal_data={},
        )
        valid_signal = QueuedSignal(
            id="q-2",
            signal_id="sig-2",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={},
        )
        manager._signal_queue.append(expired_signal)
        manager._signal_queue.append(valid_signal)

        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            queue = await manager.get_queue_status()

            assert len(queue) == 1
            assert queue[0].signal_id == "sig-2"


class TestCancelQueued:
    """Test signal cancellation."""

    @pytest.mark.asyncio
    async def test_cancel_queued_signal(
        self, manager: PositionLimitManager
    ) -> None:
        """Can cancel queued signal."""
        signal = QueuedSignal(
            id="q-1",
            signal_id="sig-1",
            expires_at=datetime.utcnow() + timedelta(hours=1),
            signal_data={},
        )
        manager._signal_queue.append(signal)

        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            success = await manager.cancel_queued_signal("sig-1")

            assert success is True
            assert len(manager._signal_queue) == 0

    @pytest.mark.asyncio
    async def test_cancel_not_found(
        self, manager: PositionLimitManager
    ) -> None:
        """Cancel returns False for non-existent signal."""
        mock_db = MagicMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            success = await manager.cancel_queued_signal("not-exist")

            assert success is False


class TestConfigUpdate:
    """Test configuration update (AC 5)."""

    @pytest.mark.asyncio
    async def test_update_config(
        self, manager: PositionLimitManager
    ) -> None:
        """Config update persists to database."""
        new_config = PositionLimitConfig(max_positions=10)

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.update_config(new_config)

            assert manager.config.max_positions == 10


class TestSingletonManagement:
    """Test singleton instance management."""

    def test_reset_singleton(self) -> None:
        """Reset clears singleton instance."""
        reset_position_limit_manager()
        # Just verify it doesn't error

    @pytest.mark.asyncio
    async def test_get_singleton_creates_instance(self) -> None:
        """get_position_limit_manager creates instance."""
        reset_position_limit_manager()

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "value": {
                        "max_positions": 5,
                        "enable_queue": True,
                        "max_queue_size": 10,
                        "queue_expiry_minutes": 60,
                    }
                }
            )
        )
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch(
            "walltrack.core.risk.position_limits.get_supabase_client",
            new_callable=AsyncMock,
            return_value=mock_db,
        ):
            manager = await get_position_limit_manager()
            assert manager is not None

        reset_position_limit_manager()
