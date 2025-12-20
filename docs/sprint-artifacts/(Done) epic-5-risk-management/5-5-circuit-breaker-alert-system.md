# Story 5.5: Circuit Breaker Alert System

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: Done
- **Priority**: High
- **FR**: FR31, FR44

## User Story

**As an** operator,
**I want** to be alerted immediately when circuit breakers trigger,
**So that** I can take action promptly.

## Acceptance Criteria

### AC 1: Alert Creation
**Given** any circuit breaker triggers
**When** trigger is detected
**Then** alert is created with:
- Timestamp
- Circuit breaker type (drawdown, win_rate, manual)
- Current values vs thresholds
- Recommended actions

### AC 2: Notification
**Given** alert is created
**When** notification is sent
**Then** alert appears in dashboard Alerts panel immediately
**And** (optional) push notification sent if configured
**And** alert is logged to alerts table

### AC 3: Alerts Panel
**Given** alerts panel in dashboard
**When** operator views alerts
**Then** all recent alerts are listed (newest first)
**And** unacknowledged alerts are highlighted
**And** operator can acknowledge/dismiss alerts

### AC 4: System Alerts
**Given** system issue (not circuit breaker)
**When** critical error occurs (DB connection, API failure)
**Then** system alert is raised
**And** alert type indicates "system_error"
**And** error details are included

## Technical Notes

- FR31: Alert operator when circuit breaker triggers
- FR44: Receive alerts for circuit breakers and system issues
- Implement alerts table in Supabase
- Implement in `src/walltrack/ui/components/alerts.py`

## Implementation Tasks

- [x] Create alerts table in Supabase
- [x] Create `src/walltrack/core/alerts/alert_service.py`
- [x] Implement alert creation on circuit breaker trigger
- [x] Create dashboard alerts panel
- [x] Add alert acknowledgement functionality
- [x] Implement system error alerts
- [ ] (Optional) Add push notification support

## Definition of Done

- [x] Alerts created on circuit breaker triggers
- [x] Dashboard alerts panel shows all alerts
- [x] Alerts can be acknowledged
- [x] System errors create alerts

## Implementation Summary

**Completed:** 2024-12-20

**Files Created/Modified:**
- `src/walltrack/core/alerts/alert_service.py` - AlertService class
- `src/walltrack/models/alert.py` - Models (AlertType, AlertSeverity, AlertStatus, Alert, AlertWithActions, AlertsSummary)
- `src/walltrack/data/supabase/migrations/010_risk_management.sql` - alerts table
- `tests/unit/alerts/test_alert_service.py` - 20 unit tests

**Test Coverage:** 20 tests passing

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/alerts/models.py
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Dict, Any


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
    id: Optional[str] = None
    alert_type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    status: AlertStatus = Field(default=AlertStatus.NEW)
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    resolved_at: Optional[datetime] = None
    related_trigger_id: Optional[str] = None

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
    api_endpoint: Optional[str] = None


class AlertWithActions(BaseModel):
    """Alert with recommended actions."""
    alert: Alert
    recommended_actions: List[AlertAction]


class AlertsFilter(BaseModel):
    """Filter criteria for alerts."""
    alert_types: Optional[List[AlertType]] = None
    severities: Optional[List[AlertSeverity]] = None
    statuses: Optional[List[AlertStatus]] = None
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    limit: int = Field(default=50, ge=1, le=200)


class AlertsSummary(BaseModel):
    """Summary of alert counts."""
    total: int
    by_status: Dict[str, int]
    by_severity: Dict[str, int]
    by_type: Dict[str, int]
    unacknowledged_count: int
    critical_count: int
```

### AlertService

```python
# src/walltrack/core/alerts/service.py
import structlog
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from supabase import AsyncClient

from walltrack.core.alerts.models import (
    AlertSeverity,
    AlertType,
    AlertStatus,
    Alert,
    AlertAction,
    AlertWithActions,
    AlertsFilter,
    AlertsSummary
)
from walltrack.core.risk.models import CircuitBreakerType, CircuitBreakerTrigger
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


# Mapping from circuit breaker type to alert type
CB_TO_ALERT_TYPE = {
    CircuitBreakerType.DRAWDOWN: AlertType.CIRCUIT_BREAKER_DRAWDOWN,
    CircuitBreakerType.WIN_RATE: AlertType.CIRCUIT_BREAKER_WIN_RATE,
    CircuitBreakerType.CONSECUTIVE_LOSS: AlertType.CIRCUIT_BREAKER_CONSECUTIVE_LOSS,
    CircuitBreakerType.MANUAL: AlertType.CIRCUIT_BREAKER_MANUAL,
}


# Recommended actions for each alert type
ALERT_ACTIONS: Dict[AlertType, List[AlertAction]] = {
    AlertType.CIRCUIT_BREAKER_DRAWDOWN: [
        AlertAction(
            action_id="review_positions",
            label="Review Open Positions",
            description="Check current open positions and their PnL",
            action_type="investigate",
            api_endpoint="/positions/"
        ),
        AlertAction(
            action_id="reset_drawdown",
            label="Reset Circuit Breaker",
            description="Reset drawdown circuit breaker to resume trading",
            action_type="reset",
            api_endpoint="/risk/drawdown/reset"
        ),
        AlertAction(
            action_id="adjust_threshold",
            label="Adjust Threshold",
            description="Consider adjusting drawdown threshold",
            action_type="configure",
            api_endpoint="/risk/drawdown/config"
        ),
    ],
    AlertType.CIRCUIT_BREAKER_WIN_RATE: [
        AlertAction(
            action_id="analyze_trades",
            label="Analyze Recent Trades",
            description="Review trade patterns to identify issues",
            action_type="investigate",
            api_endpoint="/risk/win-rate/analysis"
        ),
        AlertAction(
            action_id="reset_win_rate",
            label="Reset Circuit Breaker",
            description="Reset win rate circuit breaker to resume trading",
            action_type="reset",
            api_endpoint="/risk/win-rate/reset"
        ),
    ],
    AlertType.CIRCUIT_BREAKER_CONSECUTIVE_LOSS: [
        AlertAction(
            action_id="review_strategy",
            label="Review Strategy Performance",
            description="Check if signal strategy needs adjustment",
            action_type="investigate"
        ),
        AlertAction(
            action_id="reset_loss_counter",
            label="Reset Loss Counter",
            description="Reset consecutive loss counter to resume trading",
            action_type="reset",
            api_endpoint="/risk/consecutive-loss/reset"
        ),
    ],
    AlertType.SYSTEM_ERROR: [
        AlertAction(
            action_id="check_logs",
            label="Check System Logs",
            description="Review detailed error logs",
            action_type="investigate"
        ),
        AlertAction(
            action_id="health_check",
            label="Run Health Check",
            description="Run system health check",
            action_type="manual",
            api_endpoint="/health"
        ),
    ],
    AlertType.NO_SIGNALS: [
        AlertAction(
            action_id="check_webhook",
            label="Verify Webhook Status",
            description="Ensure webhook endpoint is receiving signals",
            action_type="investigate",
            api_endpoint="/webhook/status"
        ),
        AlertAction(
            action_id="test_signal",
            label="Send Test Signal",
            description="Send a test signal to verify pipeline",
            action_type="manual"
        ),
    ],
}


class AlertService:
    """
    Manages system alerts and notifications.

    Creates alerts for circuit breakers, system errors, and health issues.
    """

    def __init__(self):
        self._supabase: Optional[AsyncClient] = None
        self._callbacks: List[callable] = []

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    def register_callback(self, callback: callable) -> None:
        """Register callback for new alerts (e.g., push notifications)."""
        self._callbacks.append(callback)

    async def create_circuit_breaker_alert(
        self,
        trigger: CircuitBreakerTrigger,
        additional_details: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create alert for circuit breaker trigger."""
        alert_type = CB_TO_ALERT_TYPE.get(
            trigger.breaker_type,
            AlertType.CIRCUIT_BREAKER_MANUAL
        )

        # Build message based on type
        if trigger.breaker_type == CircuitBreakerType.DRAWDOWN:
            title = "Drawdown Circuit Breaker Triggered"
            message = f"Drawdown of {trigger.actual_value:.1f}% exceeded threshold of {trigger.threshold_value:.1f}%"
        elif trigger.breaker_type == CircuitBreakerType.WIN_RATE:
            title = "Win Rate Circuit Breaker Triggered"
            message = f"Win rate of {trigger.actual_value:.1f}% fell below threshold of {trigger.threshold_value:.1f}%"
        elif trigger.breaker_type == CircuitBreakerType.CONSECUTIVE_LOSS:
            title = "Consecutive Loss Circuit Breaker Triggered"
            message = f"{int(trigger.actual_value)} consecutive losses exceeded threshold of {int(trigger.threshold_value)}"
        else:
            title = "Circuit Breaker Triggered"
            message = f"Manual circuit breaker activated"

        details = {
            "threshold": str(trigger.threshold_value),
            "actual": str(trigger.actual_value),
            "capital_at_trigger": str(trigger.capital_at_trigger),
            "breaker_type": trigger.breaker_type.value,
        }
        if additional_details:
            details.update(additional_details)

        alert = Alert(
            alert_type=alert_type,
            severity=AlertSeverity.CRITICAL,
            title=title,
            message=message,
            details=details,
            related_trigger_id=trigger.id
        )

        return await self._save_alert(alert)

    async def create_system_error_alert(
        self,
        error_type: str,
        error_message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> Alert:
        """Create alert for system error."""
        alert_type_map = {
            "db_connection": AlertType.DB_CONNECTION,
            "api_failure": AlertType.API_FAILURE,
            "health_check": AlertType.HEALTH_CHECK,
        }

        alert = Alert(
            alert_type=alert_type_map.get(error_type, AlertType.SYSTEM_ERROR),
            severity=AlertSeverity.ERROR,
            title=f"System Error: {error_type}",
            message=error_message,
            details=details or {}
        )

        return await self._save_alert(alert)

    async def create_no_signals_alert(
        self,
        last_signal_time: datetime,
        threshold_hours: int = 48
    ) -> Alert:
        """Create alert for no signals received."""
        hours_since = int((datetime.utcnow() - last_signal_time).total_seconds() / 3600)

        alert = Alert(
            alert_type=AlertType.NO_SIGNALS,
            severity=AlertSeverity.WARNING,
            title="No Trading Signals Received",
            message=f"No signals received for {hours_since} hours (threshold: {threshold_hours}h)",
            details={
                "last_signal_time": last_signal_time.isoformat(),
                "hours_since": hours_since,
                "threshold_hours": threshold_hours
            }
        )

        return await self._save_alert(alert)

    async def _save_alert(self, alert: Alert) -> Alert:
        """Save alert to database and notify callbacks."""
        db = await self._get_db()

        result = await db.table("alerts").insert(
            alert.model_dump(exclude={"id", "is_active", "age_seconds"}, mode="json")
        ).execute()

        alert.id = result.data[0]["id"]

        logger.warning(
            "alert_created",
            alert_id=alert.id,
            type=alert.alert_type.value,
            severity=alert.severity.value,
            title=alert.title
        )

        # Notify callbacks (e.g., push notifications)
        for callback in self._callbacks:
            try:
                await callback(alert)
            except Exception as e:
                logger.error("alert_callback_failed", error=str(e))

        return alert

    async def acknowledge_alert(
        self,
        alert_id: str,
        operator_id: str
    ) -> Alert:
        """Acknowledge an alert."""
        db = await self._get_db()

        await db.table("alerts").update({
            "status": AlertStatus.ACKNOWLEDGED.value,
            "acknowledged_at": datetime.utcnow().isoformat(),
            "acknowledged_by": operator_id
        }).eq("id", alert_id).execute()

        result = await db.table("alerts").select("*").eq("id", alert_id).single().execute()

        logger.info(
            "alert_acknowledged",
            alert_id=alert_id,
            operator_id=operator_id
        )

        return Alert(**result.data)

    async def resolve_alert(self, alert_id: str) -> Alert:
        """Mark alert as resolved."""
        db = await self._get_db()

        await db.table("alerts").update({
            "status": AlertStatus.RESOLVED.value,
            "resolved_at": datetime.utcnow().isoformat()
        }).eq("id", alert_id).execute()

        result = await db.table("alerts").select("*").eq("id", alert_id).single().execute()

        logger.info("alert_resolved", alert_id=alert_id)

        return Alert(**result.data)

    async def dismiss_alert(self, alert_id: str) -> Alert:
        """Dismiss an alert (user chose to ignore)."""
        db = await self._get_db()

        await db.table("alerts").update({
            "status": AlertStatus.DISMISSED.value
        }).eq("id", alert_id).execute()

        result = await db.table("alerts").select("*").eq("id", alert_id).single().execute()

        return Alert(**result.data)

    async def get_alerts(
        self,
        filter: Optional[AlertsFilter] = None
    ) -> List[Alert]:
        """Get alerts with optional filtering."""
        db = await self._get_db()

        query = db.table("alerts").select("*")

        if filter:
            if filter.alert_types:
                query = query.in_("alert_type", [t.value for t in filter.alert_types])
            if filter.severities:
                query = query.in_("severity", [s.value for s in filter.severities])
            if filter.statuses:
                query = query.in_("status", [s.value for s in filter.statuses])
            if filter.from_date:
                query = query.gte("created_at", filter.from_date.isoformat())
            if filter.to_date:
                query = query.lte("created_at", filter.to_date.isoformat())

        query = query.order("created_at", desc=True).limit(filter.limit if filter else 50)

        result = await query.execute()

        return [Alert(**row) for row in result.data]

    async def get_alert_with_actions(self, alert_id: str) -> AlertWithActions:
        """Get alert with recommended actions."""
        db = await self._get_db()

        result = await db.table("alerts").select("*").eq("id", alert_id).single().execute()
        alert = Alert(**result.data)

        actions = ALERT_ACTIONS.get(alert.alert_type, [])

        return AlertWithActions(alert=alert, recommended_actions=actions)

    async def get_alerts_summary(self) -> AlertsSummary:
        """Get summary of alerts."""
        db = await self._get_db()

        result = await db.table("alerts").select("*").execute()
        alerts = [Alert(**row) for row in result.data]

        by_status = {}
        by_severity = {}
        by_type = {}

        for alert in alerts:
            by_status[alert.status.value] = by_status.get(alert.status.value, 0) + 1
            by_severity[alert.severity.value] = by_severity.get(alert.severity.value, 0) + 1
            by_type[alert.alert_type.value] = by_type.get(alert.alert_type.value, 0) + 1

        unacknowledged = sum(1 for a in alerts if a.status == AlertStatus.NEW)
        critical = sum(1 for a in alerts if a.severity == AlertSeverity.CRITICAL and a.is_active)

        return AlertsSummary(
            total=len(alerts),
            by_status=by_status,
            by_severity=by_severity,
            by_type=by_type,
            unacknowledged_count=unacknowledged,
            critical_count=critical
        )


# Singleton instance
_alert_service: Optional[AlertService] = None


async def get_alert_service() -> AlertService:
    """Get or create alert service singleton."""
    global _alert_service

    if _alert_service is None:
        _alert_service = AlertService()

    return _alert_service
```

### Gradio Alerts Panel

```python
# src/walltrack/ui/components/alerts.py
import gradio as gr
from datetime import datetime
from typing import List, Tuple

from walltrack.core.alerts.service import get_alert_service
from walltrack.core.alerts.models import (
    Alert,
    AlertStatus,
    AlertSeverity,
    AlertsFilter
)


async def load_alerts(status_filter: str = "all") -> List[List]:
    """Load alerts for display."""
    service = await get_alert_service()

    filter = AlertsFilter(limit=100)
    if status_filter != "all":
        filter.statuses = [AlertStatus(status_filter)]

    alerts = await service.get_alerts(filter)

    rows = []
    for alert in alerts:
        severity_emoji = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }.get(alert.severity, "")

        status_emoji = {
            AlertStatus.NEW: "🔴",
            AlertStatus.ACKNOWLEDGED: "🟡",
            AlertStatus.RESOLVED: "🟢",
            AlertStatus.DISMISSED: "⚪"
        }.get(alert.status, "")

        rows.append([
            alert.id,
            f"{severity_emoji} {alert.severity.value.upper()}",
            f"{status_emoji} {alert.status.value}",
            alert.title,
            alert.created_at.strftime("%Y-%m-%d %H:%M"),
            alert.acknowledged_by or "-"
        ])

    return rows


async def get_alert_detail(alert_id: str) -> Tuple[str, str, str]:
    """Get alert details."""
    if not alert_id:
        return "", "", ""

    service = await get_alert_service()
    alert_with_actions = await service.get_alert_with_actions(alert_id)
    alert = alert_with_actions.alert

    # Format details
    detail_text = f"""
**Title:** {alert.title}

**Message:** {alert.message}

**Type:** {alert.alert_type.value}
**Severity:** {alert.severity.value}
**Status:** {alert.status.value}

**Created:** {alert.created_at.strftime("%Y-%m-%d %H:%M:%S")}
**Acknowledged:** {alert.acknowledged_at.strftime("%Y-%m-%d %H:%M:%S") if alert.acknowledged_at else "Not acknowledged"}
**Resolved:** {alert.resolved_at.strftime("%Y-%m-%d %H:%M:%S") if alert.resolved_at else "Not resolved"}

**Details:**
```json
{alert.details}
```
"""

    # Format actions
    actions_text = "\n".join([
        f"- **{a.label}**: {a.description}"
        for a in alert_with_actions.recommended_actions
    ]) or "No recommended actions"

    return alert_id, detail_text, actions_text


async def acknowledge_selected(alert_id: str, operator_id: str) -> str:
    """Acknowledge selected alert."""
    if not alert_id:
        return "No alert selected"

    service = await get_alert_service()
    await service.acknowledge_alert(alert_id, operator_id)

    return f"Alert {alert_id} acknowledged"


async def resolve_selected(alert_id: str) -> str:
    """Resolve selected alert."""
    if not alert_id:
        return "No alert selected"

    service = await get_alert_service()
    await service.resolve_alert(alert_id)

    return f"Alert {alert_id} resolved"


async def dismiss_selected(alert_id: str) -> str:
    """Dismiss selected alert."""
    if not alert_id:
        return "No alert selected"

    service = await get_alert_service()
    await service.dismiss_alert(alert_id)

    return f"Alert {alert_id} dismissed"


async def get_summary() -> str:
    """Get alerts summary."""
    service = await get_alert_service()
    summary = await service.get_alerts_summary()

    return f"""
**Total Alerts:** {summary.total}
**Unacknowledged:** {summary.unacknowledged_count}
**Critical Active:** {summary.critical_count}

**By Status:** {summary.by_status}
**By Severity:** {summary.by_severity}
"""


def create_alerts_panel() -> gr.Blocks:
    """Create the alerts panel for the dashboard."""

    with gr.Blocks() as alerts_panel:
        gr.Markdown("## System Alerts")

        with gr.Row():
            with gr.Column(scale=1):
                summary_display = gr.Markdown("Loading summary...")
                refresh_btn = gr.Button("🔄 Refresh", size="sm")

        with gr.Row():
            status_filter = gr.Dropdown(
                choices=["all", "new", "acknowledged", "resolved", "dismissed"],
                value="all",
                label="Filter by Status"
            )

        alerts_table = gr.Dataframe(
            headers=["ID", "Severity", "Status", "Title", "Created", "Acknowledged By"],
            datatype=["str", "str", "str", "str", "str", "str"],
            interactive=False,
            label="Alerts"
        )

        selected_alert_id = gr.Textbox(visible=False)

        with gr.Row():
            with gr.Column():
                gr.Markdown("### Alert Details")
                alert_detail = gr.Markdown("Select an alert to view details")

            with gr.Column():
                gr.Markdown("### Recommended Actions")
                alert_actions = gr.Markdown("Select an alert to view actions")

        with gr.Row():
            operator_id = gr.Textbox(
                label="Operator ID",
                placeholder="Your operator ID",
                value="operator-1"
            )

        with gr.Row():
            ack_btn = gr.Button("✅ Acknowledge", variant="primary")
            resolve_btn = gr.Button("🟢 Resolve", variant="secondary")
            dismiss_btn = gr.Button("⚪ Dismiss", variant="secondary")

        action_result = gr.Textbox(label="Result", interactive=False)

        # Event handlers
        def on_select(evt: gr.SelectData):
            if evt.index and len(evt.index) > 0:
                return evt.value
            return ""

        alerts_table.select(
            fn=on_select,
            outputs=selected_alert_id
        )

        selected_alert_id.change(
            fn=get_alert_detail,
            inputs=[selected_alert_id],
            outputs=[selected_alert_id, alert_detail, alert_actions]
        )

        refresh_btn.click(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        refresh_btn.click(
            fn=get_summary,
            outputs=[summary_display]
        )

        status_filter.change(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        ack_btn.click(
            fn=acknowledge_selected,
            inputs=[selected_alert_id, operator_id],
            outputs=[action_result]
        ).then(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        resolve_btn.click(
            fn=resolve_selected,
            inputs=[selected_alert_id],
            outputs=[action_result]
        ).then(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        dismiss_btn.click(
            fn=dismiss_selected,
            inputs=[selected_alert_id],
            outputs=[action_result]
        ).then(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        # Initial load
        alerts_panel.load(
            fn=load_alerts,
            inputs=[status_filter],
            outputs=[alerts_table]
        )

        alerts_panel.load(
            fn=get_summary,
            outputs=[summary_display]
        )

    return alerts_panel
```

### Database Schema (Supabase)

```sql
-- System alerts table
CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(100) NOT NULL,
    severity VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    acknowledged_at TIMESTAMPTZ,
    acknowledged_by VARCHAR(100),
    resolved_at TIMESTAMPTZ,
    related_trigger_id VARCHAR(100)
);

CREATE INDEX idx_alerts_status ON alerts(status);
CREATE INDEX idx_alerts_severity ON alerts(severity);
CREATE INDEX idx_alerts_created ON alerts(created_at DESC);
CREATE INDEX idx_alerts_type ON alerts(alert_type);
CREATE INDEX idx_alerts_active ON alerts(status) WHERE status IN ('new', 'acknowledged');
```

### FastAPI Routes

```python
# src/walltrack/api/routes/alerts.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from walltrack.core.alerts.service import get_alert_service, AlertService
from walltrack.core.alerts.models import (
    Alert,
    AlertWithActions,
    AlertsFilter,
    AlertsSummary
)

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AcknowledgeRequest(BaseModel):
    operator_id: str


@router.get("/", response_model=List[Alert])
async def get_alerts(
    status: str | None = None,
    severity: str | None = None,
    limit: int = 50,
    service: AlertService = Depends(get_alert_service)
):
    """Get alerts with optional filtering."""
    filter = AlertsFilter(limit=limit)
    if status:
        filter.statuses = [AlertStatus(status)]
    if severity:
        filter.severities = [AlertSeverity(severity)]

    return await service.get_alerts(filter)


@router.get("/summary", response_model=AlertsSummary)
async def get_alerts_summary(
    service: AlertService = Depends(get_alert_service)
):
    """Get alerts summary."""
    return await service.get_alerts_summary()


@router.get("/{alert_id}", response_model=AlertWithActions)
async def get_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """Get alert with recommended actions."""
    return await service.get_alert_with_actions(alert_id)


@router.post("/{alert_id}/acknowledge", response_model=Alert)
async def acknowledge_alert(
    alert_id: str,
    request: AcknowledgeRequest,
    service: AlertService = Depends(get_alert_service)
):
    """Acknowledge an alert."""
    return await service.acknowledge_alert(alert_id, request.operator_id)


@router.post("/{alert_id}/resolve", response_model=Alert)
async def resolve_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """Resolve an alert."""
    return await service.resolve_alert(alert_id)


@router.post("/{alert_id}/dismiss", response_model=Alert)
async def dismiss_alert(
    alert_id: str,
    service: AlertService = Depends(get_alert_service)
):
    """Dismiss an alert."""
    return await service.dismiss_alert(alert_id)
```

### Unit Tests

```python
# tests/unit/alerts/test_alert_service.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from walltrack.core.alerts.models import (
    AlertSeverity,
    AlertType,
    AlertStatus,
    Alert,
    AlertsFilter
)
from walltrack.core.alerts.service import AlertService
from walltrack.core.risk.models import CircuitBreakerType, CircuitBreakerTrigger


@pytest.fixture
def service():
    return AlertService()


@pytest.fixture
def drawdown_trigger():
    return CircuitBreakerTrigger(
        id="trigger-1",
        breaker_type=CircuitBreakerType.DRAWDOWN,
        threshold_value=Decimal("20.0"),
        actual_value=Decimal("25.0"),
        capital_at_trigger=Decimal("750.0"),
        peak_capital_at_trigger=Decimal("1000.0")
    )


class TestAlertCreation:
    """Test alert creation."""

    @pytest.mark.asyncio
    async def test_create_circuit_breaker_alert(self, service, drawdown_trigger):
        """Creates alert for circuit breaker trigger."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "alert-123"}
        ]

        with patch.object(service, '_get_db', return_value=mock_db):
            alert = await service.create_circuit_breaker_alert(drawdown_trigger)

            assert alert.id == "alert-123"
            assert alert.alert_type == AlertType.CIRCUIT_BREAKER_DRAWDOWN
            assert alert.severity == AlertSeverity.CRITICAL
            assert "25.0%" in alert.message

    @pytest.mark.asyncio
    async def test_create_system_error_alert(self, service):
        """Creates alert for system error."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "alert-456"}
        ]

        with patch.object(service, '_get_db', return_value=mock_db):
            alert = await service.create_system_error_alert(
                "db_connection",
                "Failed to connect to database",
                {"error_code": "CONN_REFUSED"}
            )

            assert alert.alert_type == AlertType.DB_CONNECTION
            assert alert.severity == AlertSeverity.ERROR

    @pytest.mark.asyncio
    async def test_create_no_signals_alert(self, service):
        """Creates alert for no signals."""
        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "alert-789"}
        ]

        last_signal = datetime.utcnow() - timedelta(hours=72)

        with patch.object(service, '_get_db', return_value=mock_db):
            alert = await service.create_no_signals_alert(last_signal, threshold_hours=48)

            assert alert.alert_type == AlertType.NO_SIGNALS
            assert alert.severity == AlertSeverity.WARNING
            assert "72 hours" in alert.message


class TestAlertStatusChanges:
    """Test alert status changes."""

    @pytest.mark.asyncio
    async def test_acknowledge_alert(self, service):
        """Acknowledge changes status and records operator."""
        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
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
            "related_trigger_id": None
        }

        with patch.object(service, '_get_db', return_value=mock_db):
            alert = await service.acknowledge_alert("alert-1", "operator-1")

            assert alert.status == AlertStatus.ACKNOWLEDGED
            assert alert.acknowledged_by == "operator-1"

    @pytest.mark.asyncio
    async def test_resolve_alert(self, service):
        """Resolve changes status and records time."""
        mock_db = AsyncMock()
        mock_db.table.return_value.update.return_value.eq.return_value.execute = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
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
            "related_trigger_id": None
        }

        with patch.object(service, '_get_db', return_value=mock_db):
            alert = await service.resolve_alert("alert-1")

            assert alert.status == AlertStatus.RESOLVED
            assert alert.resolved_at is not None


class TestAlertFiltering:
    """Test alert filtering."""

    @pytest.mark.asyncio
    async def test_filter_by_status(self, service):
        """Filters alerts by status."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.in_.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        with patch.object(service, '_get_db', return_value=mock_db):
            filter = AlertsFilter(statuses=[AlertStatus.NEW])
            await service.get_alerts(filter)

            mock_db.table.return_value.select.return_value.in_.assert_called_once()


class TestAlertCallbacks:
    """Test alert callbacks."""

    @pytest.mark.asyncio
    async def test_callback_called_on_create(self, service, drawdown_trigger):
        """Callbacks are called when alert is created."""
        callback = AsyncMock()
        service.register_callback(callback)

        mock_db = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute.return_value.data = [
            {"id": "alert-123"}
        ]

        with patch.object(service, '_get_db', return_value=mock_db):
            await service.create_circuit_breaker_alert(drawdown_trigger)

            callback.assert_called_once()
```
