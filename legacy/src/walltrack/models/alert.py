"""Alert model for system notifications.

Story 10.5-14: Alerts on order failures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(str, Enum):
    """Alert status."""

    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class Alert(BaseModel):
    """System alert for notifications.

    Attributes:
        id: Unique alert identifier
        alert_type: Type of alert (e.g., "order_failed")
        severity: Alert severity level
        status: Current alert status
        title: Short alert title
        message: Detailed alert message
        data: Additional context data
        requires_action: Whether user action is required
        dedupe_key: Key for deduplication
    """

    id: UUID = Field(default_factory=uuid4)
    alert_type: str
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.ACTIVE
    title: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)

    # Tracking
    requires_action: bool = False
    dedupe_key: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None

    # Notification tracking
    notified_at: datetime | None = None

    @property
    def is_active(self) -> bool:
        """Check if alert is active."""
        return self.status == AlertStatus.ACTIVE

    @property
    def is_resolved(self) -> bool:
        """Check if alert is resolved."""
        return self.status == AlertStatus.RESOLVED

    @property
    def age_hours(self) -> float:
        """Age of alert in hours."""
        now = datetime.now(UTC)
        created = (
            self.created_at
            if self.created_at.tzinfo
            else self.created_at.replace(tzinfo=UTC)
        )
        return (now - created).total_seconds() / 3600

    def acknowledge(self, acknowledged_by: str = "user") -> None:
        """Mark alert as acknowledged."""
        self.status = AlertStatus.ACKNOWLEDGED
        self.acknowledged_at = datetime.now(UTC)
        self.acknowledged_by = acknowledged_by
        self.updated_at = datetime.now(UTC)

    def resolve(self, resolution: str) -> None:
        """Mark alert as resolved."""
        self.status = AlertStatus.RESOLVED
        self.resolved_at = datetime.now(UTC)
        self.resolution = resolution
        self.updated_at = datetime.now(UTC)

    def mark_notified(self) -> None:
        """Mark that notification was sent."""
        self.notified_at = datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
