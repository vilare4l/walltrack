"""Alert service for creating and managing alerts.

Story 10.5-14: Alerts on order failures.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

from walltrack.models.alert import Alert, AlertSeverity, AlertStatus

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

logger = structlog.get_logger(__name__)


class AlertService:
    """Service for managing system alerts.

    Handles creation, deduplication, and resolution of alerts.
    """

    async def create_alert(
        self,
        alert_type: str,
        severity: str,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
        requires_action: bool = False,
        dedupe_key: str | None = None,
    ) -> Alert:
        """Create a new alert or update existing if dedupe_key matches.

        Args:
            alert_type: Type of alert (e.g., "order_failed")
            severity: Alert severity level
            title: Alert title
            message: Detailed message
            data: Additional context data
            requires_action: Whether user action is required
            dedupe_key: Key for deduplication

        Returns:
            Created or updated alert
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()
        log = logger.bind(alert_type=alert_type, severity=severity)

        # Check for existing alert with same dedupe_key
        if dedupe_key:
            existing = await self._find_by_dedupe_key(client, dedupe_key)

            if existing:
                log.debug("updating_existing_alert", alert_id=existing["id"])
                return await self._update_alert(
                    client, existing["id"], message, data or {}
                )

        # Create new alert
        alert = Alert(
            alert_type=alert_type,
            severity=AlertSeverity(severity),
            title=title,
            message=message,
            data=data or {},
            requires_action=requires_action,
            dedupe_key=dedupe_key,
        )

        await client.client.table("alerts").insert({
            "id": str(alert.id),
            "alert_type": alert.alert_type,
            "severity": alert.severity.value,
            "status": alert.status.value,
            "title": alert.title,
            "message": alert.message,
            "data": alert.data,
            "requires_action": alert.requires_action,
            "dedupe_key": alert.dedupe_key,
            "created_at": alert.created_at.isoformat(),
        }).execute()

        log.info("alert_created", alert_id=str(alert.id), title=title)

        # Emit notification event
        await self._emit_notification_event(alert)

        return alert

    async def acknowledge_alert(
        self,
        alert_id: str,
        acknowledged_by: str = "user",
    ) -> bool:
        """Mark an alert as acknowledged.

        Args:
            alert_id: Alert ID to acknowledge
            acknowledged_by: Who acknowledged the alert

        Returns:
            True if alert was acknowledged
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()
        now = datetime.now(UTC)

        result = (
            await client.client.table("alerts")
            .update({
                "status": AlertStatus.ACKNOWLEDGED.value,
                "acknowledged_at": now.isoformat(),
                "acknowledged_by": acknowledged_by,
                "updated_at": now.isoformat(),
            })
            .eq("id", alert_id)
            .execute()
        )

        success = len(result.data) > 0
        if success:
            logger.info("alert_acknowledged", alert_id=alert_id[:8])

        return success

    async def resolve_alert(
        self,
        alert_id: str,
        resolution: str,
    ) -> bool:
        """Mark an alert as resolved.

        Args:
            alert_id: Alert ID to resolve
            resolution: Resolution description

        Returns:
            True if alert was resolved
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()
        now = datetime.now(UTC)

        result = (
            await client.client.table("alerts")
            .update({
                "status": AlertStatus.RESOLVED.value,
                "resolved_at": now.isoformat(),
                "resolution": resolution,
                "updated_at": now.isoformat(),
            })
            .eq("id", alert_id)
            .execute()
        )

        success = len(result.data) > 0
        if success:
            logger.info("alert_resolved", alert_id=alert_id[:8], resolution=resolution)

        return success

    async def resolve_by_dedupe_key(
        self,
        dedupe_key: str,
        resolution: str,
    ) -> bool:
        """Resolve alert by dedupe key.

        Args:
            dedupe_key: Deduplication key
            resolution: Resolution description

        Returns:
            True if alert was resolved
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()
        now = datetime.now(UTC)

        result = (
            await client.client.table("alerts")
            .update({
                "status": AlertStatus.RESOLVED.value,
                "resolved_at": now.isoformat(),
                "resolution": resolution,
                "updated_at": now.isoformat(),
            })
            .eq("dedupe_key", dedupe_key)
            .eq("status", AlertStatus.ACTIVE.value)
            .execute()
        )

        success = len(result.data) > 0
        if success:
            logger.info(
                "alert_resolved_by_dedupe",
                dedupe_key=dedupe_key[:20],
                resolution=resolution,
            )

        return success

    async def get_active_alerts(
        self,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[Alert]:
        """Get active alerts.

        Args:
            severity: Filter by severity level
            limit: Maximum number of alerts to return

        Returns:
            List of active alerts
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()

        query = (
            client.client.table("alerts")
            .select("*")
            .in_(
                "status",
                [AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value],
            )
        )

        if severity:
            query = query.eq("severity", severity)

        result = await query.order("created_at", desc=True).limit(limit).execute()

        return [self._row_to_alert(row) for row in result.data]

    async def get_alert_by_id(self, alert_id: str) -> Alert | None:
        """Get alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert if found, None otherwise
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()

        result = (
            await client.client.table("alerts")
            .select("*")
            .eq("id", alert_id)
            .maybe_single()
            .execute()
        )

        if result.data:
            return self._row_to_alert(result.data)
        return None

    async def get_active_count(self) -> dict[str, int]:
        """Get count of active alerts by severity.

        Returns:
            Dict with counts per severity and total
        """
        from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

        client = await get_supabase_client()

        result = (
            await client.client.table("alerts")
            .select("severity")
            .eq("status", AlertStatus.ACTIVE.value)
            .execute()
        )

        counts: dict[str, int] = {s.value: 0 for s in AlertSeverity}
        for row in result.data:
            sev = row["severity"]
            counts[sev] = counts.get(sev, 0) + 1

        counts["total"] = len(result.data)
        return counts

    async def _find_by_dedupe_key(
        self,
        client: SupabaseClient,
        dedupe_key: str,
    ) -> dict[str, Any] | None:
        """Find active alert by dedupe key."""
        result = (
            await client.client.table("alerts")
            .select("*")
            .eq("dedupe_key", dedupe_key)
            .eq("status", AlertStatus.ACTIVE.value)
            .maybe_single()
            .execute()
        )

        return result.data

    async def _update_alert(
        self,
        client: SupabaseClient,
        alert_id: str,
        message: str,
        data: dict[str, Any],
    ) -> Alert:
        """Update existing alert."""
        now = datetime.now(UTC)

        result = (
            await client.client.table("alerts")
            .update({
                "message": message,
                "data": data,
                "updated_at": now.isoformat(),
            })
            .eq("id", alert_id)
            .execute()
        )

        return self._row_to_alert(result.data[0])

    async def _emit_notification_event(self, alert: Alert) -> None:
        """Emit notification event for external systems."""
        # For now, just log. Future: webhook, email, etc.
        if alert.severity in [AlertSeverity.CRITICAL, AlertSeverity.HIGH]:
            logger.warning(
                "notification_event",
                alert_id=str(alert.id)[:8],
                severity=alert.severity.value,
                title=alert.title,
            )

    def _row_to_alert(self, row: dict[str, Any]) -> Alert:
        """Convert database row to Alert model."""
        return Alert(
            id=row["id"],
            alert_type=row["alert_type"],
            severity=AlertSeverity(row["severity"]),
            status=AlertStatus(row["status"]),
            title=row["title"],
            message=row["message"],
            data=row.get("data") or {},
            requires_action=row.get("requires_action", False),
            dedupe_key=row.get("dedupe_key"),
            created_at=_parse_datetime(row.get("created_at")),
            updated_at=_parse_datetime(row.get("updated_at")),
            acknowledged_at=_parse_datetime(row.get("acknowledged_at")),
            acknowledged_by=row.get("acknowledged_by"),
            resolved_at=_parse_datetime(row.get("resolved_at")),
            resolution=row.get("resolution"),
            notified_at=_parse_datetime(row.get("notified_at")),
        )


def _parse_datetime(value: str | None) -> datetime | None:
    """Parse datetime from ISO string."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


# Singleton
_alert_service: AlertService | None = None


async def get_alert_service() -> AlertService:
    """Get or create alert service singleton."""
    global _alert_service
    if _alert_service is None:
        _alert_service = AlertService()
    return _alert_service
