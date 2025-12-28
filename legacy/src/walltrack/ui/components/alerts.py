"""Alerts UI component.

Story 10.5-14: Alerts panel for order failure notifications.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from walltrack.models.alert import Alert, AlertSeverity, AlertStatus


def get_severity_color(severity: AlertSeverity | str) -> str:
    """Get color for severity display.

    Args:
        severity: Alert severity

    Returns:
        CSS color name
    """
    if isinstance(severity, str):
        try:
            severity = AlertSeverity(severity)
        except ValueError:
            return "gray"

    colors = {
        AlertSeverity.INFO: "blue",
        AlertSeverity.WARNING: "orange",
        AlertSeverity.HIGH: "red",
        AlertSeverity.CRITICAL: "darkred",
    }
    return colors.get(severity, "gray")


def get_severity_emoji(severity: AlertSeverity | str) -> str:
    """Get emoji for severity display.

    Args:
        severity: Alert severity

    Returns:
        Severity emoji
    """
    if isinstance(severity, str):
        try:
            severity = AlertSeverity(severity)
        except ValueError:
            return ""

    emojis = {
        AlertSeverity.INFO: "",
        AlertSeverity.WARNING: "",
        AlertSeverity.HIGH: "",
        AlertSeverity.CRITICAL: "",
    }
    return emojis.get(severity, "")


def get_status_color(status: AlertStatus | str) -> str:
    """Get color for status display.

    Args:
        status: Alert status

    Returns:
        CSS color name
    """
    if isinstance(status, str):
        try:
            status = AlertStatus(status)
        except ValueError:
            return "gray"

    colors = {
        AlertStatus.ACTIVE: "red",
        AlertStatus.ACKNOWLEDGED: "orange",
        AlertStatus.RESOLVED: "green",
    }
    return colors.get(status, "gray")


def format_alert_summary(alert: dict[str, Any] | Alert) -> str:
    """Format alert for summary display.

    Args:
        alert: Alert dict or Alert model

    Returns:
        Formatted summary string
    """
    if isinstance(alert, Alert):
        severity = alert.severity.value.upper()
        status = alert.status.value.upper()
        title = alert.title
    else:
        severity = str(alert.get("severity", "")).upper()
        status = str(alert.get("status", "")).upper()
        title = alert.get("title", "")

    return f"[{severity}] [{status}] {title}"


def format_alert_for_table(alert: dict[str, Any] | Alert) -> list[Any]:
    """Format alert for table row display.

    Args:
        alert: Alert dict or Alert model

    Returns:
        List of values for table row
    """
    if isinstance(alert, Alert):
        created = alert.created_at.strftime("%Y-%m-%d %H:%M:%S")
        return [
            str(alert.id)[:8],
            alert.severity.value,
            alert.status.value,
            alert.title,
            alert.message[:50] + "..." if len(alert.message) > 50 else alert.message,
            "Yes" if alert.requires_action else "No",
            created,
            f"{alert.age_hours:.1f}h",
        ]
    else:
        created = alert.get("created_at", "")
        if isinstance(created, str):
            with contextlib.suppress(Exception):
                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                created = dt.strftime("%Y-%m-%d %H:%M:%S")

        message = alert.get("message", "")
        if len(message) > 50:
            message = message[:50] + "..."

        return [
            str(alert.get("id", ""))[:8],
            alert.get("severity", ""),
            alert.get("status", ""),
            alert.get("title", ""),
            message,
            "Yes" if alert.get("requires_action") else "No",
            created,
            _calculate_age_hours(alert.get("created_at")),
        ]


def get_alert_actions(alert: dict[str, Any] | Alert) -> dict[str, bool]:
    """Get available actions for an alert.

    Args:
        alert: Alert dict or Alert model

    Returns:
        Dict with can_acknowledge and can_resolve flags
    """
    if isinstance(alert, Alert):
        status = alert.status
    else:
        try:
            status = AlertStatus(alert.get("status", ""))
        except ValueError:
            status = None

    can_acknowledge = status == AlertStatus.ACTIVE
    can_resolve = status in [AlertStatus.ACTIVE, AlertStatus.ACKNOWLEDGED]

    return {
        "can_acknowledge": can_acknowledge,
        "can_resolve": can_resolve,
    }


def format_alert_counts(counts: dict[str, int]) -> str:
    """Format alert counts for display.

    Args:
        counts: Dict with counts per severity

    Returns:
        Formatted summary
    """
    total = counts.get("total", 0)
    if total == 0:
        return "No active alerts"

    parts = []
    for sev in ["critical", "high", "warning", "info"]:
        count = counts.get(sev, 0)
        if count > 0:
            emoji = get_severity_emoji(sev)
            parts.append(f"{emoji} {count} {sev}")

    return f"**{total} Active Alerts:** " + ", ".join(parts)


def _calculate_age_hours(created_at: str | None) -> str:
    """Calculate age of alert in hours."""
    if not created_at:
        return "?"

    try:
        from datetime import UTC  # noqa: PLC0415

        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        now = datetime.now(UTC)
        hours = (now - dt).total_seconds() / 3600
        return f"{hours:.1f}h"
    except Exception:
        return "?"


# Table headers for alerts display
ALERTS_TABLE_HEADERS = [
    "ID",
    "Severity",
    "Status",
    "Title",
    "Message",
    "Action Req.",
    "Created",
    "Age",
]
