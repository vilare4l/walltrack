"""Tests for alert service.

Story 10.5-14: Tests for alert creation, deduplication, and management.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.models.alert import Alert, AlertSeverity, AlertStatus
from walltrack.services.alerts.alert_service import AlertService, _parse_datetime


class TestAlertService:
    """Tests for AlertService."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.fixture
    def service(self) -> AlertService:
        """Create alert service instance."""
        return AlertService()

    @pytest.mark.asyncio
    async def test_create_alert_new(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test creating a new alert."""
        # Setup mock
        mock_client.client.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": str(uuid4())}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alert = await service.create_alert(
                alert_type="order_failed",
                severity="high",
                title="Order Failed",
                message="Test order failed",
                data={"order_id": "123"},
                requires_action=True,
            )

        assert alert.alert_type == "order_failed"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.ACTIVE
        assert alert.title == "Order Failed"
        assert alert.requires_action is True

    @pytest.mark.asyncio
    async def test_create_alert_with_dedupe_key_new(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test creating alert with dedupe key when no existing alert."""
        # Setup mock - no existing alert
        mock_client.client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )
        mock_client.client.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": str(uuid4())}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alert = await service.create_alert(
                alert_type="order_failed",
                severity="critical",
                title="Exit Order Failed",
                message="Test message",
                dedupe_key="order_failed_123",
            )

        assert alert.dedupe_key == "order_failed_123"
        assert alert.severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_create_alert_updates_existing_with_dedupe_key(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test that existing alert is updated when dedupe key matches."""
        existing_id = str(uuid4())
        existing_alert = {
            "id": existing_id,
            "alert_type": "order_failed",
            "severity": "high",
            "status": "active",
            "title": "Old Title",
            "message": "Old message",
            "data": {},
            "requires_action": True,
            "dedupe_key": "order_failed_123",
            "created_at": datetime.now(UTC).isoformat(),
        }

        # Setup mock - existing alert found
        mock_client.client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=existing_alert)
        )
        mock_client.client.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{**existing_alert, "message": "New message"}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alert = await service.create_alert(
                alert_type="order_failed",
                severity="high",
                title="Exit Order Failed",
                message="New message",
                dedupe_key="order_failed_123",
            )

        # Verify update was called
        mock_client.client.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_acknowledge_alert(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test acknowledging an alert."""
        alert_id = str(uuid4())

        mock_client.client.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": alert_id}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            success = await service.acknowledge_alert(alert_id, acknowledged_by="user")

        assert success is True
        mock_client.client.table.return_value.update.assert_called()

    @pytest.mark.asyncio
    async def test_acknowledge_alert_not_found(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test acknowledging non-existent alert returns False."""
        alert_id = str(uuid4())

        mock_client.client.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            success = await service.acknowledge_alert(alert_id)

        assert success is False

    @pytest.mark.asyncio
    async def test_resolve_alert(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test resolving an alert."""
        alert_id = str(uuid4())

        mock_client.client.table.return_value.update.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": alert_id}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            success = await service.resolve_alert(
                alert_id,
                resolution="Issue fixed manually",
            )

        assert success is True

    @pytest.mark.asyncio
    async def test_resolve_by_dedupe_key(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test resolving alert by dedupe key."""
        mock_client.client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": str(uuid4())}])
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            success = await service.resolve_by_dedupe_key(
                dedupe_key="order_failed_123",
                resolution="Order completed successfully",
            )

        assert success is True

    @pytest.mark.asyncio
    async def test_get_active_alerts(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting active alerts."""
        alerts_data = [
            {
                "id": str(uuid4()),
                "alert_type": "order_failed",
                "severity": "high",
                "status": "active",
                "title": "Alert 1",
                "message": "Message 1",
                "data": {},
                "requires_action": True,
                "created_at": datetime.now(UTC).isoformat(),
            },
            {
                "id": str(uuid4()),
                "alert_type": "order_failed",
                "severity": "critical",
                "status": "acknowledged",
                "title": "Alert 2",
                "message": "Message 2",
                "data": {},
                "requires_action": True,
                "created_at": datetime.now(UTC).isoformat(),
            },
        ]

        mock_client.client.table.return_value.select.return_value.in_.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=alerts_data)
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alerts = await service.get_active_alerts(limit=10)

        assert len(alerts) == 2
        assert all(isinstance(a, Alert) for a in alerts)

    @pytest.mark.asyncio
    async def test_get_active_alerts_with_severity_filter(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting active alerts filtered by severity."""
        alerts_data = [
            {
                "id": str(uuid4()),
                "alert_type": "order_failed",
                "severity": "critical",
                "status": "active",
                "title": "Critical Alert",
                "message": "Message",
                "data": {},
                "requires_action": True,
                "created_at": datetime.now(UTC).isoformat(),
            },
        ]

        mock_client.client.table.return_value.select.return_value.in_.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=alerts_data)
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alerts = await service.get_active_alerts(severity="critical", limit=10)

        assert len(alerts) == 1
        assert alerts[0].severity == AlertSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_get_alert_by_id(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting alert by ID."""
        alert_id = str(uuid4())
        alert_data = {
            "id": alert_id,
            "alert_type": "order_failed",
            "severity": "high",
            "status": "active",
            "title": "Test Alert",
            "message": "Test message",
            "data": {"key": "value"},
            "requires_action": False,
            "created_at": datetime.now(UTC).isoformat(),
        }

        mock_client.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=alert_data)
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alert = await service.get_alert_by_id(alert_id)

        assert alert is not None
        assert str(alert.id) == alert_id
        assert alert.data == {"key": "value"}

    @pytest.mark.asyncio
    async def test_get_alert_by_id_not_found(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting non-existent alert returns None."""
        mock_client.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            alert = await service.get_alert_by_id(str(uuid4()))

        assert alert is None

    @pytest.mark.asyncio
    async def test_get_active_count(
        self,
        service: AlertService,
        mock_client: MagicMock,
    ) -> None:
        """Test getting active alert counts by severity."""
        alerts_data = [
            {"severity": "critical"},
            {"severity": "critical"},
            {"severity": "high"},
            {"severity": "warning"},
        ]

        mock_client.client.table.return_value.select.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=alerts_data)
        )

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new=AsyncMock(return_value=mock_client),
        ):
            counts = await service.get_active_count()

        assert counts["total"] == 4
        assert counts["critical"] == 2
        assert counts["high"] == 1
        assert counts["warning"] == 1
        assert counts["info"] == 0


class TestParseDatetime:
    """Tests for datetime parsing utility."""

    def test_parse_valid_iso_datetime(self) -> None:
        """Test parsing valid ISO datetime string."""
        dt_str = "2024-01-15T10:30:00+00:00"
        result = _parse_datetime(dt_str)

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_datetime_with_z_suffix(self) -> None:
        """Test parsing datetime with Z suffix."""
        dt_str = "2024-01-15T10:30:00Z"
        result = _parse_datetime(dt_str)

        assert result is not None
        assert result.tzinfo is not None

    def test_parse_none_returns_none(self) -> None:
        """Test parsing None returns None."""
        result = _parse_datetime(None)
        assert result is None

    def test_parse_empty_string_returns_none(self) -> None:
        """Test parsing empty string returns None."""
        result = _parse_datetime("")
        assert result is None

    def test_parse_invalid_format_returns_none(self) -> None:
        """Test parsing invalid format returns None."""
        result = _parse_datetime("not-a-date")
        assert result is None
