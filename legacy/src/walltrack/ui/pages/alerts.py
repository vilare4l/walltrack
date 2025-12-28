"""Alerts page with list and actions.

Story 10.5-14: Alert list, filtering, acknowledge, and resolve.
"""

from __future__ import annotations

from typing import Any

import gradio as gr
import structlog

from walltrack.models.alert import AlertSeverity, AlertStatus
from walltrack.ui.components.alerts import (
    ALERTS_TABLE_HEADERS,
    format_alert_counts,
    format_alert_for_table,
)

logger = structlog.get_logger(__name__)


def create_alerts_page() -> gr.Column:  # noqa: PLR0915
    """Create the alerts management page.

    Returns:
        Gradio Column containing the alerts page.
    """
    with gr.Column() as alerts_page:
        gr.Markdown("## System Alerts")

        # Summary row
        alert_summary = gr.Markdown("Loading alerts...")

        # Filters row
        with gr.Row():
            severity_filter = gr.Dropdown(
                choices=["All"] + [s.value for s in AlertSeverity],
                value="All",
                label="Severity",
                scale=1,
            )
            status_filter = gr.Dropdown(
                choices=["Active", "All"] + [s.value for s in AlertStatus],
                value="Active",
                label="Status",
                scale=1,
            )
            refresh_btn = gr.Button("Refresh", size="sm", scale=1)

        # Alerts table
        alerts_table = gr.Dataframe(
            headers=ALERTS_TABLE_HEADERS,
            datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
            row_count=10,
            col_count=(8, "fixed"),
            interactive=False,
            label="Alerts",
        )

        # Selected alert state
        selected_alert_id = gr.State(None)

        # Action buttons row
        with gr.Row():
            acknowledge_btn = gr.Button(
                "Acknowledge Selected",
                variant="secondary",
                interactive=False,
            )
            resolve_btn = gr.Button(
                "Resolve Selected",
                variant="primary",
                interactive=False,
            )

        # Resolution input (hidden by default)
        with gr.Row(visible=False) as resolution_row:
            resolution_input = gr.Textbox(
                label="Resolution",
                placeholder="Enter resolution details...",
                scale=3,
            )
            confirm_resolve_btn = gr.Button("Confirm Resolve", variant="primary")
            cancel_resolve_btn = gr.Button("Cancel")

        # Alert detail section
        with gr.Accordion("Alert Details", open=False):
            alert_detail = gr.JSON(label="Selected Alert")

        # Event handlers

        def load_alerts(
            severity: str,
            status: str,
        ) -> tuple[list[list[Any]], str]:
            """Load alerts from database."""
            import asyncio  # noqa: PLC0415

            async def _load() -> tuple[list[list[Any]], str]:
                try:
                    from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                        get_alert_service,
                    )

                    service = await get_alert_service()

                    # Get counts
                    counts = await service.get_active_count()
                    summary = format_alert_counts(counts)

                    # Determine severity filter
                    sev_filter = None if severity == "All" else severity

                    # Get alerts based on status filter
                    if status == "Active":
                        alerts = await service.get_active_alerts(
                            severity=sev_filter,
                            limit=50,
                        )
                    else:
                        # For specific status or All, query directly
                        from walltrack.data.supabase.client import (  # noqa: PLC0415
                            get_supabase_client,
                        )

                        client = await get_supabase_client()
                        query = client.client.table("alerts").select("*")

                        if status != "All":
                            query = query.eq("status", status)
                        if sev_filter:
                            query = query.eq("severity", sev_filter)

                        result = (
                            await query.order("created_at", desc=True).limit(50).execute()
                        )
                        alerts = result.data

                    # Format for table
                    rows = [format_alert_for_table(a) for a in alerts]
                    return rows, summary

                except Exception as e:
                    logger.exception("load_alerts_failed")
                    return [], f"Error loading alerts: {e!s}"

            return asyncio.get_event_loop().run_until_complete(_load())

        def on_row_select(
            evt: gr.SelectData,
            table_data: list[list[Any]],
        ) -> tuple[str | None, dict[str, Any] | None, bool, bool]:
            """Handle row selection."""
            if evt.index is None or not table_data:
                return None, None, False, False

            row_idx = evt.index[0] if isinstance(evt.index, tuple) else evt.index
            if row_idx >= len(table_data):
                return None, None, False, False

            row = table_data[row_idx]
            alert_id = row[0]  # First column is ID (truncated)
            status = row[2]  # Third column is status

            # Enable buttons based on status
            can_acknowledge = status == AlertStatus.ACTIVE.value
            can_resolve = status in [AlertStatus.ACTIVE.value, AlertStatus.ACKNOWLEDGED.value]

            # Load full alert detail
            import asyncio  # noqa: PLC0415

            async def _get_detail() -> dict[str, Any] | None:
                try:
                    from walltrack.data.supabase.client import get_supabase_client  # noqa: PLC0415

                    client = await get_supabase_client()
                    result = (
                        await client.client.table("alerts")
                        .select("*")
                        .ilike("id", f"{alert_id}%")
                        .maybe_single()
                        .execute()
                    )
                    return result.data
                except Exception:
                    return None

            detail = asyncio.get_event_loop().run_until_complete(_get_detail())

            # Return full ID from detail if available
            full_id = detail.get("id") if detail else alert_id

            return full_id, detail, can_acknowledge, can_resolve

        def acknowledge_alert(alert_id: str | None) -> tuple[str, bool, bool]:
            """Acknowledge selected alert."""
            if not alert_id:
                return "No alert selected", False, False

            import asyncio  # noqa: PLC0415

            async def _acknowledge() -> str:
                try:
                    from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                        get_alert_service,
                    )

                    service = await get_alert_service()
                    success = await service.acknowledge_alert(alert_id)

                    if success:
                        return f"Alert {alert_id[:8]} acknowledged"
                    return f"Failed to acknowledge alert {alert_id[:8]}"
                except Exception as e:
                    return f"Error: {e!s}"

            result = asyncio.get_event_loop().run_until_complete(_acknowledge())
            return result, False, True  # Disable acknowledge, keep resolve enabled

        def show_resolve_input() -> gr.update:
            """Show the resolution input row."""
            return gr.update(visible=True)

        def hide_resolve_input() -> gr.update:
            """Hide the resolution input row."""
            return gr.update(visible=False)

        def resolve_alert(
            alert_id: str | None,
            resolution: str,
        ) -> tuple[str, bool, bool, gr.update, str]:
            """Resolve selected alert."""
            if not alert_id:
                return "No alert selected", False, False, gr.update(visible=False), ""

            if not resolution.strip():
                return "Resolution required", False, True, gr.update(visible=True), resolution

            import asyncio  # noqa: PLC0415

            async def _resolve() -> str:
                try:
                    from walltrack.services.alerts.alert_service import (  # noqa: PLC0415
                        get_alert_service,
                    )

                    service = await get_alert_service()
                    success = await service.resolve_alert(alert_id, resolution)

                    if success:
                        return f"Alert {alert_id[:8]} resolved"
                    return f"Failed to resolve alert {alert_id[:8]}"
                except Exception as e:
                    return f"Error: {e!s}"

            result = asyncio.get_event_loop().run_until_complete(_resolve())
            return result, False, False, gr.update(visible=False), ""

        # Wire up events
        refresh_btn.click(
            fn=load_alerts,
            inputs=[severity_filter, status_filter],
            outputs=[alerts_table, alert_summary],
        )

        severity_filter.change(
            fn=load_alerts,
            inputs=[severity_filter, status_filter],
            outputs=[alerts_table, alert_summary],
        )

        status_filter.change(
            fn=load_alerts,
            inputs=[severity_filter, status_filter],
            outputs=[alerts_table, alert_summary],
        )

        alerts_table.select(
            fn=on_row_select,
            inputs=[alerts_table],
            outputs=[selected_alert_id, alert_detail, acknowledge_btn, resolve_btn],
        )

        acknowledge_btn.click(
            fn=acknowledge_alert,
            inputs=[selected_alert_id],
            outputs=[alert_summary, acknowledge_btn, resolve_btn],
        ).then(
            fn=load_alerts,
            inputs=[severity_filter, status_filter],
            outputs=[alerts_table, alert_summary],
        )

        resolve_btn.click(
            fn=show_resolve_input,
            outputs=[resolution_row],
        )

        cancel_resolve_btn.click(
            fn=hide_resolve_input,
            outputs=[resolution_row],
        )

        confirm_resolve_btn.click(
            fn=resolve_alert,
            inputs=[selected_alert_id, resolution_input],
            outputs=[
                alert_summary,
                acknowledge_btn,
                resolve_btn,
                resolution_row,
                resolution_input,
            ],
        ).then(
            fn=load_alerts,
            inputs=[severity_filter, status_filter],
            outputs=[alerts_table, alert_summary],
        )

        # Initial load on page render
        alerts_page.render()

    return alerts_page
