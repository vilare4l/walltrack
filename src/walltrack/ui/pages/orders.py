"""Orders page with list and actions.

Story 10.5-13: Order list, filtering, details, and manual actions.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import gradio as gr
import structlog

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.order_repo import get_order_repository
from walltrack.models.order import OrderStatus, OrderType
from walltrack.services.order.executor import get_order_executor

logger = structlog.get_logger(__name__)

# Time range options
TIME_RANGES = {
    "1 hour": timedelta(hours=1),
    "6 hours": timedelta(hours=6),
    "24 hours": timedelta(hours=24),
    "7 days": timedelta(days=7),
}


def create_orders_page(sidebar_state: gr.State | None = None) -> gr.Column:  # noqa: ARG001
    """Create the orders management page.

    Args:
        sidebar_state: Optional shared sidebar state for detail display (unused).

    Returns:
        Gradio Column containing the orders page.
    """
    with gr.Column() as orders_page:
        gr.Markdown("## Orders Management")

        # Filters row
        with gr.Row():
            status_filter = gr.Dropdown(
                choices=["All"] + [s.value for s in OrderStatus],
                value="All",
                label="Status",
                scale=1,
            )
            type_filter = gr.Dropdown(
                choices=["All", "entry", "exit"],
                value="All",
                label="Type",
                scale=1,
            )
            time_range = gr.Dropdown(
                choices=["1 hour", "6 hours", "24 hours", "7 days", "All"],
                value="24 hours",
                label="Time Range",
                scale=1,
            )
            refresh_btn = gr.Button("Refresh", size="sm", scale=1)

        # Status counters
        with gr.Row():
            pending_count = gr.Number(
                label="Pending",
                precision=0,
                interactive=False,
                scale=1,
            )
            submitted_count = gr.Number(
                label="Submitted",
                precision=0,
                interactive=False,
                scale=1,
            )
            filled_count = gr.Number(
                label="Filled",
                precision=0,
                interactive=False,
                scale=1,
            )
            failed_count = gr.Number(
                label="Failed/Cancelled",
                precision=0,
                interactive=False,
                scale=1,
            )

        # Orders table
        orders_table = gr.Dataframe(
            headers=[
                "ID",
                "Type",
                "Token",
                "Amount (SOL)",
                "Status",
                "Attempts",
                "Created",
                "Updated",
            ],
            datatype=["str", "str", "str", "number", "str", "number", "str", "str"],
            label="Orders",
            interactive=False,
            wrap=True,
        )

        # Order detail section
        with gr.Accordion("Order Details", open=False):
            with gr.Row():
                detail_order_id = gr.Textbox(label="Order ID", interactive=False)
                detail_status = gr.Textbox(label="Status", interactive=False)
                detail_type = gr.Textbox(label="Type", interactive=False)

            with gr.Row():
                detail_token = gr.Textbox(label="Token", interactive=False)
                detail_amount_sol = gr.Number(label="Amount (SOL)", interactive=False)
                detail_expected_price = gr.Number(
                    label="Expected Price", interactive=False
                )

            with gr.Row():
                detail_actual_price = gr.Number(label="Actual Price", interactive=False)
                detail_slippage = gr.Textbox(label="Slippage", interactive=False)
                detail_tx = gr.Textbox(label="TX Signature", interactive=False)

            with gr.Row():
                detail_signal_id = gr.Textbox(label="Signal ID", interactive=False)
                detail_position_id = gr.Textbox(label="Position ID", interactive=False)

            # Error display (only visible when there's an error)
            detail_error = gr.Textbox(
                label="Error Message",
                lines=2,
                interactive=False,
                visible=True,
            )

            # Timeline
            gr.Markdown("#### Status Timeline")
            timeline_table = gr.Dataframe(
                headers=["Timestamp", "Transition", "Details"],
                datatype=["str", "str", "str"],
                label="Status Changes",
                interactive=False,
            )

            # Actions row
            with gr.Row():
                cancel_btn = gr.Button(
                    "Cancel Order",
                    variant="stop",
                    visible=True,
                )
                retry_btn = gr.Button(
                    "Retry Now",
                    variant="primary",
                    visible=True,
                )

            action_result = gr.Textbox(
                label="Action Result",
                interactive=False,
            )

        # Hidden state for selected order
        selected_order_id = gr.State(value=None)

    # Set up event handlers
    filter_inputs = [status_filter, type_filter, time_range]
    load_outputs = [
        orders_table,
        pending_count,
        submitted_count,
        filled_count,
        failed_count,
    ]

    detail_outputs = [
        detail_order_id,
        detail_status,
        detail_type,
        detail_token,
        detail_amount_sol,
        detail_expected_price,
        detail_actual_price,
        detail_slippage,
        detail_tx,
        detail_signal_id,
        detail_position_id,
        detail_error,
        timeline_table,
        cancel_btn,
        retry_btn,
    ]

    # Initial load and filter changes
    for filter_input in filter_inputs:
        filter_input.change(
            fn=load_orders,
            inputs=filter_inputs,
            outputs=load_outputs,
        )

    # Refresh button
    refresh_btn.click(
        fn=load_orders,
        inputs=filter_inputs,
        outputs=load_outputs,
    )

    # Table row selection
    orders_table.select(
        fn=_handle_row_select,
        inputs=[orders_table],
        outputs=[selected_order_id],
    ).then(
        fn=load_order_detail,
        inputs=[selected_order_id],
        outputs=detail_outputs,
    )

    # Cancel action
    cancel_btn.click(
        fn=cancel_order,
        inputs=[detail_order_id],
        outputs=[action_result],
    ).then(
        fn=load_orders,
        inputs=filter_inputs,
        outputs=load_outputs,
    )

    # Retry action
    retry_btn.click(
        fn=retry_order_now,
        inputs=[detail_order_id],
        outputs=[action_result],
    ).then(
        fn=load_orders,
        inputs=filter_inputs,
        outputs=load_outputs,
    )

    # Auto-load on page render
    orders_page.render(
        fn=load_orders,
        inputs=filter_inputs,
        outputs=load_outputs,
    )

    result: gr.Column = orders_page
    return result


def _handle_row_select(
    table_data: list[list[Any]],
    evt: gr.SelectData,
) -> str | None:
    """Handle table row selection."""
    if evt is None or evt.index is None:
        return None

    row_idx = evt.index[0] if isinstance(evt.index, (list, tuple)) else evt.index
    if row_idx < len(table_data):
        return str(table_data[row_idx][0])  # Return short ID
    return None


async def load_orders(
    status_filter: str,
    type_filter: str,
    time_range: str,
) -> tuple[list[list[Any]], int, int, int, int]:
    """Load orders based on filters.

    Args:
        status_filter: Filter by status or "All"
        type_filter: Filter by type or "All"
        time_range: Time range filter

    Returns:
        Tuple of (table_rows, pending, submitted, filled, failed_count)
    """
    try:
        repo = await get_order_repository()

        # Determine date range
        start_date = None
        if time_range in TIME_RANGES:
            start_date = datetime.now(UTC) - TIME_RANGES[time_range]

        # Determine status filter
        status = None
        if status_filter != "All":
            status = OrderStatus(status_filter)

        # Determine type filter
        order_type = None
        if type_filter != "All":
            order_type = OrderType(type_filter)

        # Get orders
        orders = await repo.get_history(
            start_date=start_date,
            order_type=order_type,
            status=status,
            limit=100,
        )

        # Format for table
        table_rows: list[list[Any]] = []
        for o in orders:
            table_rows.append([
                str(o.id)[:8],
                o.order_type.value,
                o.token_symbol or o.token_address[:8],
                float(o.amount_sol),
                o.status.value,
                o.attempt_count,
                _format_timestamp(o.created_at),
                _format_timestamp(o.updated_at),
            ])

        # Count by status
        counts = await repo.count_by_status()

        return (
            table_rows,
            counts.get("pending", 0),
            counts.get("submitted", 0) + counts.get("confirming", 0),
            counts.get("filled", 0),
            counts.get("failed", 0) + counts.get("cancelled", 0),
        )

    except Exception as e:
        logger.error("load_orders_failed", error=str(e))
        return ([], 0, 0, 0, 0)


OrderDetailResult = tuple[
    str,  # order_id
    str,  # status
    str,  # order_type
    str,  # token
    float,  # amount_sol
    float,  # expected_price
    float,  # actual_price
    str,  # slippage
    str,  # tx_signature
    str,  # signal_id
    str,  # position_id
    str,  # error
    list[list[str]],  # timeline
    gr.Button,  # cancel_btn
    gr.Button,  # retry_btn
]


async def load_order_detail(
    order_id: str | None,
) -> OrderDetailResult:
    """Load full order details.

    Args:
        order_id: Short order ID (first 8 chars)

    Returns:
        Tuple of order detail values
    """
    empty_result: OrderDetailResult = (
        "",
        "",
        "",
        "",
        0.0,
        0.0,
        0.0,
        "",
        "",
        "",
        "",
        "",
        [],
        gr.Button(visible=False),
        gr.Button(visible=False),
    )

    if not order_id:
        return empty_result

    try:
        client = await get_supabase_client()

        # Get order with partial ID match
        result = (
            await client.client.table("orders")
            .select("*")
            .like("id", f"{order_id}%")
            .maybe_single()
            .execute()
        )

        if result is None or not result.data:
            return empty_result

        order: dict[str, Any] = result.data  # type: ignore[assignment]

        # Get timeline from status log
        timeline = await _get_order_timeline(client, str(order["id"]))

        # Calculate slippage
        slippage_text = "N/A"
        if order.get("actual_price") and order.get("expected_price"):
            actual = float(order["actual_price"])
            expected = float(order["expected_price"])
            if expected > 0:
                slippage_bps = abs(actual - expected) / expected * 10000
                slippage_text = f"{slippage_bps:.0f} bps"

        # Determine available actions
        can_cancel = order["status"] in ["pending", "failed"]
        can_retry = (
            order["status"] in ["pending", "failed"]
            and order["attempt_count"] < order.get("max_attempts", 3)
        )

        return (
            str(order["id"]),
            str(order["status"]),
            str(order["order_type"]),
            str(order.get("token_symbol") or order["token_address"][:8]),
            float(order["amount_sol"]),
            float(order.get("expected_price", 0)),
            float(order.get("actual_price", 0) or 0),
            slippage_text,
            str(order.get("tx_signature", "") or ""),
            str(order.get("signal_id", "") or ""),
            str(order.get("position_id", "") or ""),
            str(order.get("last_error", "") or ""),
            timeline,
            gr.Button(visible=can_cancel),
            gr.Button(visible=can_retry),
        )

    except Exception as e:
        logger.error("load_order_detail_failed", error=str(e), order_id=order_id)
        return empty_result


async def _get_order_timeline(
    client: Any,
    order_id: str,
) -> list[list[str]]:
    """Get timeline events for order.

    Args:
        client: Supabase client
        order_id: Full order ID

    Returns:
        List of [timestamp, transition, details] rows
    """
    try:
        result = (
            await client.client.table("order_status_log")
            .select("*")
            .eq("order_id", order_id)
            .order("changed_at", desc=False)
            .execute()
        )

        timeline: list[list[str]] = []
        for event in result.data:
            old_status = event.get("old_status", "new")
            new_status = event["new_status"]
            changed_at = _format_timestamp(
                datetime.fromisoformat(
                    event["changed_at"].replace("Z", "+00:00")
                )
            )
            details = event.get("details", "") or ""

            timeline.append([
                changed_at,
                f"{old_status} -> {new_status}",
                details[:50] if details else "",
            ])

        return timeline

    except Exception as e:
        logger.warning("get_timeline_failed", error=str(e))
        return []


async def cancel_order(order_id: str) -> str:
    """Cancel an order manually.

    Args:
        order_id: Full order ID

    Returns:
        Result message
    """
    if not order_id:
        return "No order selected"

    try:
        repo = await get_order_repository()
        order = await repo.get_by_id(order_id)

        if not order:
            return "Order not found"

        if order.status not in [OrderStatus.PENDING, OrderStatus.FAILED]:
            return f"Cannot cancel order in status {order.status.value}"

        order.cancel("Manually cancelled by user")
        await repo.update(order)

        logger.info("order_cancelled_manually", order_id=order_id[:8])
        return f"Order {order_id[:8]} cancelled successfully"

    except Exception as e:
        logger.error("cancel_order_failed", error=str(e), order_id=order_id[:8])
        return f"Failed to cancel: {e}"


async def retry_order_now(order_id: str) -> str:
    """Force immediate retry of an order.

    Args:
        order_id: Full order ID

    Returns:
        Result message
    """
    if not order_id:
        return "No order selected"

    try:
        repo = await get_order_repository()
        order = await repo.get_by_id(order_id)

        if not order:
            return "Order not found"

        if not order.can_retry and order.status != OrderStatus.PENDING:
            return (
                f"Order cannot be retried "
                f"(status: {order.status.value}, attempts: {order.attempt_count})"
            )

        # Execute immediately
        executor = await get_order_executor()
        result = await executor.execute(order)

        if result.success:
            logger.info(
                "order_retried_manually",
                order_id=order_id[:8],
                success=True,
            )
            return f"Order {order_id[:8]} executed successfully!"
        else:
            logger.warning(
                "order_retry_failed",
                order_id=order_id[:8],
                error=result.error,
            )
            return f"Retry failed: {result.error}"

    except Exception as e:
        logger.error("retry_order_failed", error=str(e), order_id=order_id[:8])
        return f"Failed to retry: {e}"


def _format_timestamp(dt: datetime | str | None) -> str:
    """Format timestamp for display.

    Args:
        dt: Datetime object or ISO string

    Returns:
        Formatted timestamp string
    """
    if not dt:
        return "N/A"

    try:
        if isinstance(dt, str):
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(dt) if dt else "N/A"
