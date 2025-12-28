"""Tests for alert service (Story 5-5)."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.alerts.models import (
    Alert,
    AlertSeverity,
    AlertsFilter,
    AlertStatus,
    AlertType,
)
from walltrack.core.alerts.service import (
    AlertService,
    get_alert_service,
    reset_alert_service,
)
from walltrack.models.risk import CircuitBreakerTrigger, CircuitBreakerType


@pytest.fixture
def service() -> AlertService:
    """Create test service instance."""
    return AlertService()


@pytest.fixture
def drawdown_trigger() -> CircuitBreakerTrigger:
    """Create test drawdown trigger."""
    return CircuitBreakerTrigger(
        id="trigger-1",
        breaker_type=CircuitBreakerType.DRAWDOWN,
        threshold_value=Decimal("20.0"),
        actual_value=Decimal("25.0"),
        capital_at_trigger=Decimal("750.0"),
        peak_capital_at_trigger=Decimal("1000.0"),
    )


@pytest.fixture
def win_rate_trigger() -> CircuitBreakerTrigger:
    """Create test win rate trigger."""
    return CircuitBreakerTrigger(
        id="trigger-2",
        breaker_type=CircuitBreakerType.WIN_RATE,
        threshold_value=Decimal("40.0"),
        actual_value=Decimal("35.0"),
        capital_at_trigger=Decimal("900.0"),
        peak_capital_at_trigger=Decimal("1000.0"),
    )


@pytest.fixture
def consecutive_loss_trigger() -> CircuitBreakerTrigger:
    """Create test consecutive loss trigger."""
    return CircuitBreakerTrigger(
        id="trigger-3",
        breaker_type=CircuitBreakerType.CONSECUTIVE_LOSS,
        threshold_value=Decimal("5"),
        actual_value=Decimal("6"),
        capital_at_trigger=Decimal("800.0"),
        peak_capital_at_trigger=Decimal("1000.0"),
    )


class TestCircuitBreakerAlertCreation:
    """Test alert creation for circuit breakers (AC 1)."""

    @pytest.mark.asyncio
    async def test_create_drawdown_alert(
        self, service: AlertService, drawdown_trigger: CircuitBreakerTrigger
    ) -> None:
        """Creates alert for drawdown circuit breaker."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-123"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_circuit_breaker_alert(drawdown_trigger)

            assert alert.id == "alert-123"
            assert alert.alert_type == AlertType.CIRCUIT_BREAKER_DRAWDOWN
            assert alert.severity == AlertSeverity.CRITICAL
            assert "25.0" in alert.message
            assert "20.0" in alert.message
            assert alert.related_trigger_id == "trigger-1"

    @pytest.mark.asyncio
    async def test_create_win_rate_alert(
        self, service: AlertService, win_rate_trigger: CircuitBreakerTrigger
    ) -> None:
        """Creates alert for win rate circuit breaker."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-456"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_circuit_breaker_alert(win_rate_trigger)

            assert alert.alert_type == AlertType.CIRCUIT_BREAKER_WIN_RATE
            assert "35.0" in alert.message

    @pytest.mark.asyncio
    async def test_create_consecutive_loss_alert(
        self, service: AlertService, consecutive_loss_trigger: CircuitBreakerTrigger
    ) -> None:
        """Creates alert for consecutive loss circuit breaker."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-789"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_circuit_breaker_alert(consecutive_loss_trigger)

            assert alert.alert_type == AlertType.CIRCUIT_BREAKER_CONSECUTIVE_LOSS
            assert "6" in alert.message

    @pytest.mark.asyncio
    async def test_alert_includes_details(
        self, service: AlertService, drawdown_trigger: CircuitBreakerTrigger
    ) -> None:
        """Alert includes threshold and actual values in details."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-123"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_circuit_breaker_alert(drawdown_trigger)

            assert "threshold" in alert.details
            assert "actual" in alert.details
            assert "breaker_type" in alert.details


class TestSystemErrorAlerts:
    """Test system error alert creation (AC 4)."""

    @pytest.mark.asyncio
    async def test_create_db_connection_alert(self, service: AlertService) -> None:
        """Creates alert for database connection error."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-db"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_system_error_alert(
                "db_connection",
                "Failed to connect to database",
                {"error_code": "CONN_REFUSED"},
            )

            assert alert.alert_type == AlertType.DB_CONNECTION
            assert alert.severity == AlertSeverity.ERROR
            assert "Failed to connect" in alert.message

    @pytest.mark.asyncio
    async def test_create_api_failure_alert(self, service: AlertService) -> None:
        """Creates alert for API failure."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-api"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_system_error_alert(
                "api_failure",
                "Jupiter API returned 500",
            )

            assert alert.alert_type == AlertType.API_FAILURE

    @pytest.mark.asyncio
    async def test_create_generic_system_error_alert(
        self, service: AlertService
    ) -> None:
        """Creates generic system error alert for unknown types."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-sys"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_system_error_alert(
                "unknown_error",
                "Something went wrong",
            )

            assert alert.alert_type == AlertType.SYSTEM_ERROR


class TestNoSignalsAlert:
    """Test no signals alert creation."""

    @pytest.mark.asyncio
    async def test_create_no_signals_alert(self, service: AlertService) -> None:
        """Creates alert when no signals received."""
        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-nosig"}])
        )

        last_signal = datetime.utcnow() - timedelta(hours=72)

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_no_signals_alert(
                last_signal, threshold_hours=48
            )

            assert alert.alert_type == AlertType.NO_SIGNALS
            assert alert.severity == AlertSeverity.WARNING
            assert "72" in alert.message


class TestAlertAcknowledge:
    """Test alert acknowledgement (AC 3)."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service: AlertService) -> None:
        """Acknowledge changes status and records operator."""
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "id": "alert-1",
                    "alert_type": "circuit_breaker_drawdown",
                    "severity": "critical",
                    "title": "Test",
                    "message": "Test message",
                    "details": {},
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "acknowledged",
                    "acknowledged_at": datetime.utcnow().isoformat(),
                    "acknowledged_by": "operator-1",
                    "resolved_at": None,
                    "related_trigger_id": None,
                }
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.acknowledge_alert("alert-1", "operator-1")

            assert alert.status == AlertStatus.ACKNOWLEDGED
            assert alert.acknowledged_by == "operator-1"


class TestAlertResolve:
    """Test alert resolution."""

    @pytest.mark.asyncio
    async def test_resolve_alert(self, service: AlertService) -> None:
        """Resolve changes status and records time."""
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "id": "alert-1",
                    "alert_type": "circuit_breaker_drawdown",
                    "severity": "critical",
                    "title": "Test",
                    "message": "Test message",
                    "details": {},
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "resolved",
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": datetime.utcnow().isoformat(),
                    "related_trigger_id": None,
                }
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.resolve_alert("alert-1")

            assert alert.status == AlertStatus.RESOLVED
            assert alert.resolved_at is not None


class TestAlertDismiss:
    """Test alert dismissal."""

    @pytest.mark.asyncio
    async def test_dismiss_alert(self, service: AlertService) -> None:
        """Dismiss changes status."""
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = (
            AsyncMock()
        )
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "id": "alert-1",
                    "alert_type": "circuit_breaker_drawdown",
                    "severity": "critical",
                    "title": "Test",
                    "message": "Test message",
                    "details": {},
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "dismissed",
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": None,
                    "related_trigger_id": None,
                }
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.dismiss_alert("alert-1")

            assert alert.status == AlertStatus.DISMISSED


class TestAlertFiltering:
    """Test alert filtering (AC 3)."""

    @pytest.mark.asyncio
    async def test_get_alerts_no_filter(self, service: AlertService) -> None:
        """Gets all alerts without filter."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alerts = await service.get_alerts()

            assert alerts == []

    @pytest.mark.asyncio
    async def test_get_alerts_with_status_filter(self, service: AlertService) -> None:
        """Gets alerts filtered by status."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.table.return_value.select.return_value = mock_query
        mock_query.in_.return_value = mock_query
        mock_query.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            filter_obj = AlertsFilter(statuses=[AlertStatus.NEW])
            await service.get_alerts(filter_obj)

            mock_query.in_.assert_called()

    @pytest.mark.asyncio
    async def test_get_alerts_returns_alert_objects(
        self, service: AlertService
    ) -> None:
        """Gets alerts returns Alert objects."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "id": "alert-1",
                        "alert_type": "circuit_breaker_drawdown",
                        "severity": "critical",
                        "title": "Test",
                        "message": "Test message",
                        "details": {},
                        "created_at": datetime.utcnow().isoformat(),
                        "status": "new",
                        "acknowledged_at": None,
                        "acknowledged_by": None,
                        "resolved_at": None,
                        "related_trigger_id": None,
                    }
                ]
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alerts = await service.get_alerts()

            assert len(alerts) == 1
            assert isinstance(alerts[0], Alert)


class TestAlertWithActions:
    """Test alert with recommended actions."""

    @pytest.mark.asyncio
    async def test_get_alert_with_actions(self, service: AlertService) -> None:
        """Gets alert with recommended actions."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "id": "alert-1",
                    "alert_type": "circuit_breaker_drawdown",
                    "severity": "critical",
                    "title": "Test",
                    "message": "Test message",
                    "details": {},
                    "created_at": datetime.utcnow().isoformat(),
                    "status": "new",
                    "acknowledged_at": None,
                    "acknowledged_by": None,
                    "resolved_at": None,
                    "related_trigger_id": None,
                }
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await service.get_alert_with_actions("alert-1")

            assert result.alert.id == "alert-1"
            assert len(result.recommended_actions) > 0


class TestAlertsSummary:
    """Test alerts summary."""

    @pytest.mark.asyncio
    async def test_get_alerts_summary(self, service: AlertService) -> None:
        """Gets summary of alerts."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "id": "alert-1",
                        "alert_type": "circuit_breaker_drawdown",
                        "severity": "critical",
                        "title": "Test",
                        "message": "Test message",
                        "details": {},
                        "created_at": datetime.utcnow().isoformat(),
                        "status": "new",
                        "acknowledged_at": None,
                        "acknowledged_by": None,
                        "resolved_at": None,
                        "related_trigger_id": None,
                    },
                    {
                        "id": "alert-2",
                        "alert_type": "system_error",
                        "severity": "error",
                        "title": "Test 2",
                        "message": "Test message 2",
                        "details": {},
                        "created_at": datetime.utcnow().isoformat(),
                        "status": "acknowledged",
                        "acknowledged_at": datetime.utcnow().isoformat(),
                        "acknowledged_by": "op-1",
                        "resolved_at": None,
                        "related_trigger_id": None,
                    },
                ]
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            summary = await service.get_alerts_summary()

            assert summary.total == 2
            assert summary.unacknowledged_count == 1
            assert summary.critical_count == 1


class TestAlertCallbacks:
    """Test alert callbacks (AC 2 - notification)."""

    @pytest.mark.asyncio
    async def test_callback_called_on_create(
        self, service: AlertService, drawdown_trigger: CircuitBreakerTrigger
    ) -> None:
        """Callbacks are called when alert is created."""
        callback = AsyncMock()
        service.register_callback(callback)

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-123"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await service.create_circuit_breaker_alert(drawdown_trigger)

            callback.assert_called_once()

    @pytest.mark.asyncio
    async def test_callback_error_does_not_stop_alert(
        self, service: AlertService, drawdown_trigger: CircuitBreakerTrigger
    ) -> None:
        """Callback errors don't prevent alert creation."""
        callback = AsyncMock(side_effect=Exception("Callback failed"))
        service.register_callback(callback)

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "alert-123"}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            alert = await service.create_circuit_breaker_alert(drawdown_trigger)

            assert alert.id == "alert-123"


class TestSingletonManagement:
    """Test singleton instance management."""

    def test_reset_singleton(self) -> None:
        """Reset clears singleton instance."""
        reset_alert_service()

    @pytest.mark.asyncio
    async def test_get_singleton_creates_instance(self) -> None:
        """get_alert_service creates instance."""
        reset_alert_service()

        service = await get_alert_service()
        assert service is not None

        reset_alert_service()
