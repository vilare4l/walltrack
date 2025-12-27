"""Alerts service package."""

from walltrack.services.alerts.alert_service import (
    AlertService,
    get_alert_service,
)

__all__ = [
    "AlertService",
    "get_alert_service",
]
