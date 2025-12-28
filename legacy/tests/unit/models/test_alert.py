"""Tests for Alert model.

Story 10.5-14: Tests for alert model and its behavior.
"""

from datetime import UTC, datetime, timedelta

import pytest

from walltrack.models.alert import Alert, AlertSeverity, AlertStatus


class TestAlertSeverity:
    """Tests for AlertSeverity enum."""

    def test_severity_values(self) -> None:
        """Test severity enum values."""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.HIGH.value == "high"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_severity_from_string(self) -> None:
        """Test creating severity from string."""
        assert AlertSeverity("critical") == AlertSeverity.CRITICAL
        assert AlertSeverity("high") == AlertSeverity.HIGH


class TestAlertStatus:
    """Tests for AlertStatus enum."""

    def test_status_values(self) -> None:
        """Test status enum values."""
        assert AlertStatus.ACTIVE.value == "active"
        assert AlertStatus.ACKNOWLEDGED.value == "acknowledged"
        assert AlertStatus.RESOLVED.value == "resolved"


class TestAlert:
    """Tests for Alert model."""

    def test_create_basic_alert(self) -> None:
        """Test creating a basic alert."""
        alert = Alert(
            alert_type="order_failed",
            severity=AlertSeverity.HIGH,
            title="Order Failed",
            message="Test order failed after 3 attempts",
        )

        assert alert.id is not None
        assert alert.alert_type == "order_failed"
        assert alert.severity == AlertSeverity.HIGH
        assert alert.status == AlertStatus.ACTIVE
        assert alert.title == "Order Failed"
        assert alert.message == "Test order failed after 3 attempts"
        assert alert.data == {}
        assert alert.requires_action is False
        assert alert.dedupe_key is None
        assert alert.created_at is not None

    def test_create_alert_with_data(self) -> None:
        """Test creating alert with additional data."""
        data = {
            "order_id": "abc123",
            "token_address": "TokenAddr123",
            "error": "Slippage too high",
        }
        alert = Alert(
            alert_type="order_failed",
            severity=AlertSeverity.CRITICAL,
            title="Exit Order Failed",
            message="Exit order failed",
            data=data,
            requires_action=True,
            dedupe_key="order_failed_abc123",
        )

        assert alert.data == data
        assert alert.requires_action is True
        assert alert.dedupe_key == "order_failed_abc123"
        assert alert.severity == AlertSeverity.CRITICAL

    def test_is_active_property(self) -> None:
        """Test is_active property."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
        )

        assert alert.is_active is True

        alert.status = AlertStatus.ACKNOWLEDGED
        assert alert.is_active is False

        alert.status = AlertStatus.RESOLVED
        assert alert.is_active is False

    def test_is_resolved_property(self) -> None:
        """Test is_resolved property."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
        )

        assert alert.is_resolved is False

        alert.status = AlertStatus.ACKNOWLEDGED
        assert alert.is_resolved is False

        alert.status = AlertStatus.RESOLVED
        assert alert.is_resolved is True

    def test_age_hours_property(self) -> None:
        """Test age_hours property calculation."""
        # Create alert 2 hours ago
        old_time = datetime.now(UTC) - timedelta(hours=2)
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
            created_at=old_time,
        )

        # Should be approximately 2 hours
        assert 1.9 <= alert.age_hours <= 2.1

    def test_acknowledge_method(self) -> None:
        """Test acknowledge method updates state."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.WARNING,
            title="Test",
            message="Test",
        )

        alert.acknowledge(acknowledged_by="test_user")

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.acknowledged_at is not None
        assert alert.acknowledged_by == "test_user"
        assert alert.updated_at is not None

    def test_acknowledge_default_user(self) -> None:
        """Test acknowledge with default user."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.INFO,
            title="Test",
            message="Test",
        )

        alert.acknowledge()

        assert alert.acknowledged_by == "user"

    def test_resolve_method(self) -> None:
        """Test resolve method updates state."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.HIGH,
            title="Test",
            message="Test",
        )

        alert.resolve(resolution="Fixed by manual intervention")

        assert alert.status == AlertStatus.RESOLVED
        assert alert.resolved_at is not None
        assert alert.resolution == "Fixed by manual intervention"
        assert alert.updated_at is not None

    def test_mark_notified_method(self) -> None:
        """Test mark_notified updates notification timestamp."""
        alert = Alert(
            alert_type="test",
            severity=AlertSeverity.CRITICAL,
            title="Test",
            message="Test",
        )

        assert alert.notified_at is None

        alert.mark_notified()

        assert alert.notified_at is not None
        assert alert.updated_at is not None

    def test_alert_workflow(self) -> None:
        """Test complete alert lifecycle: create -> acknowledge -> resolve."""
        # Create
        alert = Alert(
            alert_type="order_failed_permanently",
            severity=AlertSeverity.CRITICAL,
            title="EXIT Order Failed",
            message="Exit order for TOKEN failed after 3 attempts",
            data={"order_id": "123"},
            requires_action=True,
        )

        assert alert.is_active is True
        assert alert.is_resolved is False

        # Acknowledge
        alert.acknowledge(acknowledged_by="admin")

        assert alert.status == AlertStatus.ACKNOWLEDGED
        assert alert.is_active is False
        assert alert.is_resolved is False

        # Resolve
        alert.resolve(resolution="Manually sold position")

        assert alert.is_resolved is True
        assert alert.resolution == "Manually sold position"
