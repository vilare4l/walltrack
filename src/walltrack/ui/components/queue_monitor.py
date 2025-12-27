"""Queue monitor UI component.

Story 10.5-15: Real-time queue monitoring panel.
"""

from __future__ import annotations

from typing import Any


def format_queue_stats(stats: dict[str, Any]) -> str:
    """Format queue statistics for display.

    Args:
        stats: Statistics from QueuedOrderExecutor.get_stats()

    Returns:
        Formatted markdown string
    """
    running_status = "Running" if stats.get("running", False) else "Stopped"

    lines = [
        f"**Status:** {running_status}",
        "",
        "### Queue Metrics",
        f"- **Queue Size:** {stats.get('queue_size', 0)}",
        f"- **Processing:** {stats.get('processing', 0)} / {stats.get('max_concurrent', 3)}",
        f"- **Available Slots:** {stats.get('available_slots', 0)}",
        "",
        "### Execution Metrics",
        f"- **Orders Executed:** {stats.get('orders_executed', 0)}",
        f"- **Orders Failed:** {stats.get('orders_failed', 0)}",
        f"- **Success Rate:** {stats.get('success_rate', 0)}%",
        f"- **Avg Execution:** {stats.get('avg_execution_seconds', 0):.2f}s",
        f"- **Avg Wait Time:** {stats.get('avg_wait_seconds', 0):.1f}s",
    ]

    # Priority breakdown
    by_priority = stats.get("by_priority", {})
    if by_priority:
        lines.append("")
        lines.append("### By Priority")
        for priority, count in sorted(by_priority.items()):
            lines.append(f"- {priority}: {count}")

    return "\n".join(lines)


def format_queue_summary(stats: dict[str, Any]) -> str:
    """Format compact queue summary.

    Args:
        stats: Statistics from QueuedOrderExecutor.get_stats()

    Returns:
        One-line summary
    """
    queue_size = stats.get("queue_size", 0)
    processing = stats.get("processing", 0)
    max_concurrent = stats.get("max_concurrent", 3)
    success_rate = stats.get("success_rate", 0)

    if queue_size == 0 and processing == 0:
        return "Queue empty, idle"

    return (
        f"Queue: {queue_size} | Processing: {processing}/{max_concurrent} | "
        f"Success: {success_rate}%"
    )


def get_queue_status_color(stats: dict[str, Any]) -> str:
    """Get status color based on queue state.

    Args:
        stats: Statistics from QueuedOrderExecutor.get_stats()

    Returns:
        CSS color name
    """
    if not stats.get("running", False):
        return "gray"

    queue_size = stats.get("queue_size", 0)
    success_rate = stats.get("success_rate", 100)

    if success_rate < 50:
        return "red"
    if queue_size > 10:
        return "orange"
    if queue_size > 0:
        return "blue"
    return "green"


def format_queued_orders(orders: list[dict[str, Any]]) -> list[list[Any]]:
    """Format queued orders for table display.

    Args:
        orders: List of order data dicts

    Returns:
        List of table rows
    """
    rows = []
    for order in orders:
        rows.append([
            str(order.get("order_id", ""))[:8],
            order.get("priority_name", "UNKNOWN"),
            order.get("order_type", ""),
            order.get("symbol", ""),
            order.get("side", ""),
            f"{order.get('quantity', 0):.4f}",
            order.get("wait_time", "?"),
        ])
    return rows


QUEUE_TABLE_HEADERS = [
    "Order ID",
    "Priority",
    "Type",
    "Symbol",
    "Side",
    "Quantity",
    "Wait Time",
]
