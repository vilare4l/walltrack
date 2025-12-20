"""Alert service for system notifications."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import Any

import structlog

from walltrack.core.alerts.models import (
    Alert,
    AlertAction,
    AlertSeverity,
    AlertsFilter,
    AlertsSummary,
    AlertStatus,
    AlertType,
    AlertWithActions,
)
from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import CircuitBreakerTrigger, CircuitBreakerType

logger = structlog.get_logger(__name__)


# Mapping from circuit breaker type to alert type
CB_TO_ALERT_TYPE: dict[CircuitBreakerType, AlertType] = {
    CircuitBreakerType.DRAWDOWN: AlertType.CIRCUIT_BREAKER_DRAWDOWN,
    CircuitBreakerType.WIN_RATE: AlertType.CIRCUIT_BREAKER_WIN_RATE,
    CircuitBreakerType.CONSECUTIVE_LOSS: AlertType.CIRCUIT_BREAKER_CONSECUTIVE_LOSS,
    CircuitBreakerType.MANUAL: AlertType.CIRCUIT_BREAKER_MANUAL,
}


# Recommended actions for each alert type
ALERT_ACTIONS: dict[AlertType, list[AlertAction]] = {
    AlertType.CIRCUIT_BREAKER_DRAWDOWN: [
        AlertAction(
            action_id="review_positions",
            label="Review Open Positions",
            description="Check current open positions and their PnL",
            action_type="investigate",
            api_endpoint="/positions/",
        ),
        AlertAction(
            action_id="reset_drawdown",
            label="Reset Circuit Breaker",
            description="Reset drawdown circuit breaker to resume trading",
            action_type="reset",
            api_endpoint="/risk/drawdown/reset",
        ),
        AlertAction(
            action_id="adjust_threshold",
            label="Adjust Threshold",
            description="Consider adjusting drawdown threshold",
            action_type="configure",
            api_endpoint="/risk/drawdown/config",
        ),
    ],
    AlertType.CIRCUIT_BREAKER_WIN_RATE: [
        AlertAction(
            action_id="analyze_trades",
            label="Analyze Recent Trades",
            description="Review trade patterns to identify issues",
            action_type="investigate",
            api_endpoint="/risk/win-rate/analysis",
        ),
        AlertAction(
            action_id="reset_win_rate",
            label="Reset Circuit Breaker",
            description="Reset win rate circuit breaker to resume trading",
            action_type="reset",
            api_endpoint="/risk/win-rate/reset",
        ),
    ],
    AlertType.CIRCUIT_BREAKER_CONSECUTIVE_LOSS: [
        AlertAction(
            action_id="review_strategy",
            label="Review Strategy Performance",
            description="Check if signal strategy needs adjustment",
            action_type="investigate",
        ),
        AlertAction(
            action_id="reset_loss_counter",
            label="Reset Loss Counter",
            description="Reset consecutive loss counter to resume trading",
            action_type="reset",
            api_endpoint="/risk/consecutive-loss/reset",
        ),
    ],
    AlertType.SYSTEM_ERROR: [
        AlertAction(
            action_id="check_logs",
            label="Check System Logs",
            description="Review detailed error logs",
            action_type="investigate",
        ),
        AlertAction(
            action_id="health_check",
            label="Run Health Check",
            description="Run system health check",
            action_type="manual",
            api_endpoint="/health",
        ),
    ],
    AlertType.NO_SIGNALS: [
        AlertAction(
            action_id="check_webhook",
            label="Verify Webhook Status",
            description="Ensure webhook endpoint is receiving signals",
            action_type="investigate",
            api_endpoint="/webhook/status",
        ),
        AlertAction(
            action_id="test_signal",
            label="Send Test Signal",
            description="Send a test signal to verify pipeline",
            action_type="manual",
        ),
    ],
}


class AlertService:
    """
    Manages system alerts and notifications.

    Creates alerts for circuit breakers, system errors, and health issues.
    """

    def __init__(self) -> None:
        """Initialize alert service."""
        self._supabase: SupabaseClient | None = None
        self._callbacks: list[Callable[[Alert], Awaitable[None]]] = []

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    def register_callback(
        self, callback: Callable[[Alert], Awaitable[None]]
    ) -> None:
        """Register callback for new alerts (e.g., push notifications)."""
        self._callbacks.append(callback)

    async def create_circuit_breaker_alert(
        self,
        trigger: CircuitBreakerTrigger,
        additional_details: dict[str, Any] | None = None,
    ) -> Alert:
        """Create alert for circuit breaker trigger."""
        alert_type = CB_TO_ALERT_TYPE.get(
            trigger.breaker_type,
            AlertType.CIRCUIT_BREAKER_MANUAL,
        )

        # Build message based on type
        if trigger.breaker_type == CircuitBreakerType.DRAWDOWN:
            title = "Drawdown Circuit Breaker Triggered"
            message = (
                f"Drawdown of {trigger.actual_value:.1f}% exceeded "
                f"threshold of {trigger.threshold_value:.1f}%"
            )
        elif trigger.breaker_type == CircuitBreakerType.WIN_RATE:
            title = "Win Rate Circuit Breaker Triggered"
            message = (
                f"Win rate of {trigger.actual_value:.1f}% fell below "
                f"threshold of {trigger.threshold_value:.1f}%"
            )
        elif trigger.breaker_type == CircuitBreakerType.CONSECUTIVE_LOSS:
            title = "Consecutive Loss Circuit Breaker Triggered"
            message = (
                f"{int(trigger.actual_value)} consecutive losses exceeded "
                f"threshold of {int(trigger.threshold_value)}"
            )
        else:
            title = "Circuit Breaker Triggered"
            message = "Manual circuit breaker activated"

        details: dict[str, Any] = {
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
            related_trigger_id=trigger.id,
        )

        return await self._save_alert(alert)

    async def create_system_error_alert(
        self,
        error_type: str,
        error_message: str,
        details: dict[str, Any] | None = None,
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
            details=details or {},
        )

        return await self._save_alert(alert)

    async def create_no_signals_alert(
        self,
        last_signal_time: datetime,
        threshold_hours: int = 48,
    ) -> Alert:
        """Create alert for no signals received."""
        hours_since = int(
            (datetime.utcnow() - last_signal_time).total_seconds() / 3600
        )

        alert = Alert(
            alert_type=AlertType.NO_SIGNALS,
            severity=AlertSeverity.WARNING,
            title="No Trading Signals Received",
            message=(
                f"No signals received for {hours_since} hours "
                f"(threshold: {threshold_hours}h)"
            ),
            details={
                "last_signal_time": last_signal_time.isoformat(),
                "hours_since": hours_since,
                "threshold_hours": threshold_hours,
            },
        )

        return await self._save_alert(alert)

    async def _save_alert(self, alert: Alert) -> Alert:
        """Save alert to database and notify callbacks."""
        db = await self._get_db()

        result = (
            await db.table("alerts")
            .insert(
                alert.model_dump(
                    exclude={"id", "is_active", "age_seconds"}, mode="json"
                )
            )
            .execute()
        )

        alert.id = result.data[0]["id"]

        logger.warning(
            "alert_created",
            alert_id=alert.id,
            type=alert.alert_type.value,
            severity=alert.severity.value,
            title=alert.title,
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
        operator_id: str,
    ) -> Alert:
        """Acknowledge an alert."""
        db = await self._get_db()

        await (
            db.table("alerts")
            .update(
                {
                    "status": AlertStatus.ACKNOWLEDGED.value,
                    "acknowledged_at": datetime.utcnow().isoformat(),
                    "acknowledged_by": operator_id,
                }
            )
            .eq("id", alert_id)
            .execute()
        )

        result = (
            await db.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .single()
            .execute()
        )

        logger.info(
            "alert_acknowledged",
            alert_id=alert_id,
            operator_id=operator_id,
        )

        return Alert(**result.data)

    async def resolve_alert(self, alert_id: str) -> Alert:
        """Mark alert as resolved."""
        db = await self._get_db()

        await (
            db.table("alerts")
            .update(
                {
                    "status": AlertStatus.RESOLVED.value,
                    "resolved_at": datetime.utcnow().isoformat(),
                }
            )
            .eq("id", alert_id)
            .execute()
        )

        result = (
            await db.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .single()
            .execute()
        )

        logger.info("alert_resolved", alert_id=alert_id)

        return Alert(**result.data)

    async def dismiss_alert(self, alert_id: str) -> Alert:
        """Dismiss an alert (user chose to ignore)."""
        db = await self._get_db()

        await (
            db.table("alerts")
            .update({"status": AlertStatus.DISMISSED.value})
            .eq("id", alert_id)
            .execute()
        )

        result = (
            await db.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .single()
            .execute()
        )

        return Alert(**result.data)

    async def get_alerts(
        self,
        filter_obj: AlertsFilter | None = None,
    ) -> list[Alert]:
        """Get alerts with optional filtering."""
        db = await self._get_db()

        query = db.table("alerts").select("*")

        if filter_obj:
            if filter_obj.alert_types:
                query = query.in_(
                    "alert_type", [t.value for t in filter_obj.alert_types]
                )
            if filter_obj.severities:
                query = query.in_(
                    "severity", [s.value for s in filter_obj.severities]
                )
            if filter_obj.statuses:
                query = query.in_(
                    "status", [s.value for s in filter_obj.statuses]
                )
            if filter_obj.from_date:
                query = query.gte("created_at", filter_obj.from_date.isoformat())
            if filter_obj.to_date:
                query = query.lte("created_at", filter_obj.to_date.isoformat())

        query = query.order("created_at", desc=True).limit(
            filter_obj.limit if filter_obj else 50
        )

        result = await query.execute()

        return [Alert(**row) for row in result.data]

    async def get_alert_with_actions(self, alert_id: str) -> AlertWithActions:
        """Get alert with recommended actions."""
        db = await self._get_db()

        result = (
            await db.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .single()
            .execute()
        )
        alert = Alert(**result.data)

        actions = ALERT_ACTIONS.get(alert.alert_type, [])

        return AlertWithActions(alert=alert, recommended_actions=actions)

    async def get_alerts_summary(self) -> AlertsSummary:
        """Get summary of alerts."""
        db = await self._get_db()

        result = await db.table("alerts").select("*").execute()
        alerts = [Alert(**row) for row in result.data]

        by_status: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for alert in alerts:
            by_status[alert.status.value] = by_status.get(alert.status.value, 0) + 1
            by_severity[alert.severity.value] = (
                by_severity.get(alert.severity.value, 0) + 1
            )
            by_type[alert.alert_type.value] = (
                by_type.get(alert.alert_type.value, 0) + 1
            )

        unacknowledged = sum(1 for a in alerts if a.status == AlertStatus.NEW)
        critical = sum(
            1
            for a in alerts
            if a.severity == AlertSeverity.CRITICAL and a.is_active
        )

        return AlertsSummary(
            total=len(alerts),
            by_status=by_status,
            by_severity=by_severity,
            by_type=by_type,
            unacknowledged_count=unacknowledged,
            critical_count=critical,
        )


# Singleton instance
_alert_service: AlertService | None = None


async def get_alert_service() -> AlertService:
    """Get or create alert service singleton."""
    global _alert_service

    if _alert_service is None:
        _alert_service = AlertService()

    return _alert_service


def reset_alert_service() -> None:
    """Reset the singleton for testing."""
    global _alert_service
    _alert_service = None
