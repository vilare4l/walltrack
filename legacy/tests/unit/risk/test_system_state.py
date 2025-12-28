"""Tests for system state management."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.risk.system_state import (
    SystemStateManager,
    reset_system_state_manager,
)
from walltrack.models.risk import (
    CircuitBreakerType,
    PauseReason,
    PauseRequest,
    ResumeRequest,
    SystemStatus,
)


@pytest.fixture
def manager() -> SystemStateManager:
    """Create a fresh system state manager."""
    reset_system_state_manager()
    return SystemStateManager()


class TestSystemStateInitial:
    """Test initial system state."""

    def test_initial_state_running(self, manager: SystemStateManager) -> None:
        """Initial state is running."""
        assert manager.state.status == SystemStatus.RUNNING
        assert manager.state.is_paused is False
        assert manager.can_trade() is True

    def test_exits_always_allowed(self, manager: SystemStateManager) -> None:
        """Exits are always allowed."""
        assert manager.can_exit() is True

    def test_initial_state_no_pause_info(self, manager: SystemStateManager) -> None:
        """Initial state has no pause info."""
        assert manager.state.paused_at is None
        assert manager.state.paused_by is None
        assert manager.state.pause_reason is None

    def test_computed_fields_initial(self, manager: SystemStateManager) -> None:
        """Computed fields work for initial state."""
        assert manager.state.is_paused is False
        assert manager.state.is_circuit_breaker_pause is False
        assert manager.state.pause_duration_seconds is None


class TestManualPause:
    """Test manual pause functionality."""

    @pytest.mark.asyncio
    async def test_pause_changes_state(self, manager: SystemStateManager) -> None:
        """Pause changes system state."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = PauseRequest(
            operator_id="operator-1",
            reason=PauseReason.MAINTENANCE,
            note="Scheduled maintenance",
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.pause(request)

            assert state.status == SystemStatus.PAUSED_MANUAL
            assert state.paused_by == "operator-1"
            assert state.pause_reason == PauseReason.MAINTENANCE
            assert state.pause_note == "Scheduled maintenance"
            assert manager.can_trade() is False

    @pytest.mark.asyncio
    async def test_pause_records_timestamp(self, manager: SystemStateManager) -> None:
        """Pause records timestamp."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = PauseRequest(
            operator_id="operator-1",
            reason=PauseReason.INVESTIGATION,
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.pause(request)

            assert state.paused_at is not None
            assert isinstance(state.paused_at, datetime)

    @pytest.mark.asyncio
    async def test_pause_when_already_paused(
        self, manager: SystemStateManager
    ) -> None:
        """Pause when already paused returns current state unchanged."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        manager._state.paused_by = "original-operator"

        request = PauseRequest(
            operator_id="operator-2",
            reason=PauseReason.INVESTIGATION,
        )

        # No database call should happen
        state = await manager.pause(request)

        # State unchanged
        assert state.paused_by == "original-operator"

    @pytest.mark.asyncio
    async def test_pause_clears_resumed_fields(
        self, manager: SystemStateManager
    ) -> None:
        """Pause clears any previous resumed fields."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        # Simulate previous resume
        manager._state.resumed_at = datetime.utcnow()
        manager._state.resumed_by = "previous-operator"

        request = PauseRequest(
            operator_id="operator-1",
            reason=PauseReason.SYSTEM_ISSUE,
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.pause(request)

            assert state.resumed_at is None
            assert state.resumed_by is None


class TestResume:
    """Test resume functionality."""

    @pytest.mark.asyncio
    async def test_resume_from_manual_pause(
        self, manager: SystemStateManager
    ) -> None:
        """Resume from manual pause."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        manager._state.paused_at = datetime.utcnow()
        manager._state.paused_by = "operator-1"

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = ResumeRequest(operator_id="operator-1")

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.resume(request)

            assert state.status == SystemStatus.RUNNING
            assert state.resumed_by == "operator-1"
            assert state.resumed_at is not None
            assert manager.can_trade() is True

    @pytest.mark.asyncio
    async def test_resume_from_circuit_breaker_requires_ack(
        self, manager: SystemStateManager
    ) -> None:
        """Resume from circuit breaker requires acknowledgement."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN

        request = ResumeRequest(
            operator_id="operator-1",
            acknowledge_warning=False,
        )

        with pytest.raises(ValueError) as exc:
            await manager.resume(request)

        assert "acknowledge" in str(exc.value).lower()

    @pytest.mark.asyncio
    async def test_resume_from_circuit_breaker_with_ack(
        self, manager: SystemStateManager
    ) -> None:
        """Resume from circuit breaker with acknowledgement."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN
        manager._state.paused_at = datetime.utcnow()

        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value.is_.return_value.execute = (
            AsyncMock()
        )

        request = ResumeRequest(
            operator_id="operator-1",
            acknowledge_warning=True,
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.resume(request)

            assert state.status == SystemStatus.RUNNING

    @pytest.mark.asyncio
    async def test_resume_when_not_paused(
        self, manager: SystemStateManager
    ) -> None:
        """Resume when not paused returns current state."""
        assert manager._state.status == SystemStatus.RUNNING

        request = ResumeRequest(operator_id="operator-1")

        state = await manager.resume(request)

        assert state.status == SystemStatus.RUNNING

    @pytest.mark.asyncio
    async def test_resume_clears_circuit_breaker_triggers(
        self, manager: SystemStateManager
    ) -> None:
        """Resume from CB clears active triggers."""
        manager._state.status = SystemStatus.PAUSED_WIN_RATE
        manager._state.paused_at = datetime.utcnow()

        mock_db = MagicMock()
        mock_update = MagicMock()
        mock_update.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.update.return_value = mock_update
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        request = ResumeRequest(
            operator_id="operator-1",
            acknowledge_warning=True,
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await manager.resume(request)

            # Verify update was called for circuit_breaker_triggers
            mock_db.table.assert_any_call("circuit_breaker_triggers")


class TestCircuitBreakerPause:
    """Test circuit breaker pause."""

    @pytest.mark.asyncio
    async def test_set_drawdown_pause(self, manager: SystemStateManager) -> None:
        """Circuit breaker sets drawdown pause status."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.set_circuit_breaker_pause(
                CircuitBreakerType.DRAWDOWN
            )

            assert state.status == SystemStatus.PAUSED_DRAWDOWN
            assert state.paused_by == "system"
            assert state.is_circuit_breaker_pause is True

    @pytest.mark.asyncio
    async def test_set_win_rate_pause(self, manager: SystemStateManager) -> None:
        """Circuit breaker sets win rate pause status."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.set_circuit_breaker_pause(
                CircuitBreakerType.WIN_RATE
            )

            assert state.status == SystemStatus.PAUSED_WIN_RATE

    @pytest.mark.asyncio
    async def test_set_consecutive_loss_pause(
        self, manager: SystemStateManager
    ) -> None:
        """Circuit breaker sets consecutive loss pause status."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            state = await manager.set_circuit_breaker_pause(
                CircuitBreakerType.CONSECUTIVE_LOSS
            )

            assert state.status == SystemStatus.PAUSED_CONSECUTIVE_LOSS


class TestExitsDuringPause:
    """Test that exits work during pause."""

    def test_can_exit_when_manual_pause(self, manager: SystemStateManager) -> None:
        """Exits allowed during manual pause."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        assert manager.can_exit() is True

    def test_can_exit_when_drawdown_pause(
        self, manager: SystemStateManager
    ) -> None:
        """Exits allowed during drawdown pause."""
        manager._state.status = SystemStatus.PAUSED_DRAWDOWN
        assert manager.can_exit() is True

    def test_can_exit_when_win_rate_pause(
        self, manager: SystemStateManager
    ) -> None:
        """Exits allowed during win rate pause."""
        manager._state.status = SystemStatus.PAUSED_WIN_RATE
        assert manager.can_exit() is True

    def test_cannot_trade_when_paused(self, manager: SystemStateManager) -> None:
        """Cannot trade when paused."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        assert manager.can_trade() is False


class TestGetState:
    """Test getting system state."""

    @pytest.mark.asyncio
    async def test_get_state_returns_response(
        self, manager: SystemStateManager
    ) -> None:
        """Get state returns SystemStateResponse."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.is_.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            response = await manager.get_state()

            assert response.state == manager.state
            assert response.can_exit is True
            assert isinstance(response.active_circuit_breakers, list)
            assert isinstance(response.recent_events, list)

    @pytest.mark.asyncio
    async def test_get_state_can_trade_when_running(
        self, manager: SystemStateManager
    ) -> None:
        """Can trade is True when running."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.is_.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            response = await manager.get_state()

            assert response.can_trade is True

    @pytest.mark.asyncio
    async def test_get_state_cannot_trade_when_paused(
        self, manager: SystemStateManager
    ) -> None:
        """Can trade is False when paused."""
        manager._state.status = SystemStatus.PAUSED_MANUAL

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.is_.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = (
            AsyncMock(return_value=MagicMock(data=[]))
        )

        with patch.object(
            manager, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            response = await manager.get_state()

            assert response.can_trade is False


class TestPauseDurationComputed:
    """Test pause duration computed field."""

    def test_pause_duration_when_paused(self, manager: SystemStateManager) -> None:
        """Pause duration calculated when paused."""
        manager._state.status = SystemStatus.PAUSED_MANUAL
        manager._state.paused_at = datetime.utcnow()

        # Duration should be close to 0 since we just set it
        assert manager.state.pause_duration_seconds is not None
        assert manager.state.pause_duration_seconds >= 0

    def test_pause_duration_none_when_running(
        self, manager: SystemStateManager
    ) -> None:
        """Pause duration is None when running."""
        assert manager.state.pause_duration_seconds is None
