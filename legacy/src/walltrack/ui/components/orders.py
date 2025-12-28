"""Order components for dashboard display.

Story 10.5-13: Order card and summary components.
"""

from __future__ import annotations

import contextlib
from datetime import datetime
from typing import Any

from walltrack.models.order import Order, OrderStatus


def get_status_color(status: OrderStatus | str) -> str:
    """Get color for status display.

    Args:
        status: Order status

    Returns:
        CSS color name
    """
    if isinstance(status, str):
        try:
            status = OrderStatus(status)
        except ValueError:
            return "gray"

    colors = {
        OrderStatus.PENDING: "orange",
        OrderStatus.SUBMITTED: "blue",
        OrderStatus.CONFIRMING: "purple",
        OrderStatus.FILLED: "green",
        OrderStatus.FAILED: "red",
        OrderStatus.CANCELLED: "gray",
    }
    return colors.get(status, "gray")


def get_status_emoji(status: OrderStatus | str) -> str:
    """Get emoji for status display.

    Args:
        status: Order status

    Returns:
        Status emoji
    """
    if isinstance(status, str):
        try:
            status = OrderStatus(status)
        except ValueError:
            return ""

    emojis = {
        OrderStatus.PENDING: "",
        OrderStatus.SUBMITTED: "",
        OrderStatus.CONFIRMING: "",
        OrderStatus.FILLED: "",
        OrderStatus.FAILED: "",
        OrderStatus.CANCELLED: "",
    }
    return emojis.get(status, "")


def format_order_summary(order: dict[str, Any] | Order) -> str:
    """Format order for summary display.

    Args:
        order: Order dict or Order model

    Returns:
        Formatted summary string
    """
    if isinstance(order, Order):
        status = order.status.value.upper()
        order_type = order.order_type.value.upper()
        token = order.token_symbol or order.token_address[:8]
        amount = float(order.amount_sol)
    else:
        status = str(order.get("status", "")).upper()
        order_type = str(order.get("order_type", "")).upper()
        token = order.get("token_symbol") or str(order.get("token_address", ""))[:8]
        amount = float(order.get("amount_sol", 0))

    return f"[{status}] {order_type} {amount:.4f} SOL -> {token}"


def format_order_for_table(order: dict[str, Any] | Order) -> list[Any]:
    """Format order for table row display.

    Args:
        order: Order dict or Order model

    Returns:
        List of values for table row
    """
    if isinstance(order, Order):
        return [
            str(order.id)[:8],
            order.order_type.value,
            order.token_symbol or order.token_address[:8],
            float(order.amount_sol),
            order.status.value,
            order.attempt_count,
            order.created_at.strftime("%H:%M:%S"),
            order.updated_at.strftime("%H:%M:%S"),
        ]
    else:
        created: str | Any = order.get("created_at", "")
        updated: str | Any = order.get("updated_at", "")

        if isinstance(created, str):
            with contextlib.suppress(Exception):
                created = datetime.fromisoformat(
                    created.replace("Z", "+00:00")
                ).strftime("%H:%M:%S")

        if isinstance(updated, str):
            with contextlib.suppress(Exception):
                updated = datetime.fromisoformat(
                    updated.replace("Z", "+00:00")
                ).strftime("%H:%M:%S")

        return [
            str(order.get("id", ""))[:8],
            order.get("order_type", ""),
            order.get("token_symbol") or str(order.get("token_address", ""))[:8],
            float(order.get("amount_sol", 0)),
            order.get("status", ""),
            order.get("attempt_count", 0),
            created,
            updated,
        ]


def get_order_actions(order: dict[str, Any] | Order) -> dict[str, bool]:
    """Get available actions for an order.

    Args:
        order: Order dict or Order model

    Returns:
        Dict with can_cancel and can_retry flags
    """
    if isinstance(order, Order):
        status = order.status
        attempt_count = order.attempt_count
        max_attempts = order.max_attempts
    else:
        try:
            status = OrderStatus(order.get("status", ""))
        except ValueError:
            status = None
        attempt_count = order.get("attempt_count", 0)
        max_attempts = order.get("max_attempts", 3)

    can_cancel = status in [OrderStatus.PENDING, OrderStatus.FAILED]
    can_retry = (
        status in [OrderStatus.PENDING, OrderStatus.FAILED]
        and attempt_count < max_attempts
    )

    return {
        "can_cancel": can_cancel,
        "can_retry": can_retry,
    }
