"""Alerts API routes."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from walltrack.core.alerts.models import (
    Alert,
    AlertSeverity,
    AlertsFilter,
    AlertsSummary,
    AlertStatus,
    AlertWithActions,
)
from walltrack.core.alerts.service import AlertService, get_alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AcknowledgeRequest(BaseModel):
    """Request to acknowledge an alert."""

    operator_id: str


@router.get("/", response_model=list[Alert])
async def get_alerts(
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    service: AlertService = Depends(get_alert_service),
) -> list[Alert]:
    """Get alerts with optional filtering."""
    filter_obj = AlertsFilter(limit=limit)
    if status:
        filter_obj.statuses = [AlertStatus(status)]
    if severity:
        filter_obj.severities = [AlertSeverity(severity)]

    return await service.get_alerts(filter_obj)


@router.get("/summary", response_model=AlertsSummary)
async def get_alerts_summary(
    service: AlertService = Depends(get_alert_service),
) -> AlertsSummary:
    """Get alerts summary."""
    return await service.get_alerts_summary()


@router.get("/{alert_id}", response_model=AlertWithActions)
async def get_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> AlertWithActions:
    """Get alert with recommended actions."""
    return await service.get_alert_with_actions(alert_id)


@router.post("/{alert_id}/acknowledge", response_model=Alert)
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest,
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    """Acknowledge an alert."""
    return await service.acknowledge_alert(alert_id, request.operator_id)


@router.post("/{alert_id}/resolve", response_model=Alert)
async def resolve_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    """Resolve an alert."""
    return await service.resolve_alert(alert_id)


@router.post("/{alert_id}/dismiss", response_model=Alert)
async def dismiss_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service),
) -> Alert:
    """Dismiss an alert."""
    return await service.dismiss_alert(alert_id)
