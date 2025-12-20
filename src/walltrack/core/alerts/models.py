"""Alert system Pydantic models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Type of alert."""

    CIRCUIT_BREAKER_DRAWDOWN = "circuit_breaker_drawdown"
    CIRCUIT_BREAKER_WIN_RATE = "circuit_breaker_win_rate"
    CIRCUIT_BREAKER_CONSECUTIVE_LOSS = "circuit_breaker_consecutive_loss"
    CIRCUIT_BREAKER_MANUAL = "circuit_breaker_manual"
    SYSTEM_ERROR = "system_error"
    DB_CONNECTION = "db_connection"
    API_FAILURE = "api_failure"
    NO_SIGNALS = "no_signals"
    HEALTH_CHECK = "health_check"


class AlertStatus(str, Enum):
    """Alert status."""

    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


class Alert(BaseModel):
    """System alert record."""

    id: str | None = None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: AlertStatus = Field(default=AlertStatus.NEW)
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    resolved_at: datetime | None = None
    related_trigger_id: str | None = None

    @computed_field
    @property
    def is_active(self) -> bool:
        """Whether alert requires attention."""
        return self.status in [AlertStatus.NEW, AlertStatus.ACKNOWLEDGED]

    @computed_field
    @property
    def age_seconds(self) -> int:
        """Seconds since alert was created."""
        return int((datetime.utcnow() - self.created_at).total_seconds())


class AlertAction(BaseModel):
    """Recommended action for an alert."""

    action_id: str
    label: str
    description: str
    action_type: str  # "reset", "investigate", "configure", "manual"
    api_endpoint: str | None = None


class AlertWithActions(BaseModel):
    """Alert with recommended actions."""

    alert: Alert
    recommended_actions: list[AlertAction]


class AlertsFilter(BaseModel):
    """Filter criteria for alerts."""

    alert_types: list[AlertType] | None = None
    severities: list[AlertSeverity] | None = None
    statuses: list[AlertStatus] | None = None
    from_date: datetime | None = None
    to_date: datetime | None = None
    limit: int = Field(default=50, ge=1, le=200)


class AlertsSummary(BaseModel):
    """Summary of alert counts."""

    total: int
    by_status: dict[str, int]
    by_severity: dict[str, int]
    by_type: dict[str, int]
    unacknowledged_count: int
    critical_count: int
