"""Configuration history and audit UI components."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from typing import Any

import gradio as gr
import httpx
import structlog

from walltrack.config.settings import get_settings

logger = structlog.get_logger(__name__)


def get_api_base_url() -> str:
    """Get API base URL from settings."""
    settings = get_settings()
    return f"http://localhost:{settings.port}"


class ConfigHistoryComponent:
    """UI component for config history and version management."""

    def __init__(self) -> None:
        self.selected_versions: list[int] = []

    async def get_version_history(
        self,
        table: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get version history for a config table."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{get_api_base_url()}/api/config/{table}/all"
                )
                if response.status_code == 200:
                    data = response.json()
                    configs = data.get("configs", [])
                    return configs[:limit]
        except Exception as e:
            logger.error("history_fetch_error", table=table, error=str(e))
        return []

    def format_history_table(
        self, versions: list[dict[str, Any]]
    ) -> list[list[Any]]:
        """Format versions for display in a table."""
        rows = []
        for v in versions:
            created = v.get("created_at", "?")
            if created and len(created) > 19:
                created = created[:19]

            activated = v.get("activated_at")
            activated = activated[:19] if activated and len(activated) > 19 else "-"

            rows.append([
                v.get("version", "?"),
                v.get("status", "?"),
                created,
                activated,
                v.get("notes", "-") or "-",
            ])
        return rows

    async def compare_versions(
        self,
        table: str,
        version_a: int,
        version_b: int,
    ) -> dict[str, Any]:
        """Compare two config versions."""
        try:
            versions = await self.get_version_history(table, limit=100)

            config_a = None
            config_b = None

            for v in versions:
                if v.get("version") == version_a:
                    config_a = v
                if v.get("version") == version_b:
                    config_b = v

            if not config_a or not config_b:
                return {"error": "Version not found"}

            diff = self._compute_diff(config_a, config_b)
            return diff

        except Exception as e:
            logger.error("compare_error", error=str(e))
            return {"error": str(e)}

    def _compute_diff(
        self,
        old: dict[str, Any],
        new: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute difference between two configs."""
        exclude = {
            "id", "created_at", "updated_at", "activated_at",
            "archived_at", "version", "status"
        }

        changes = []

        # Get data fields (configs store values in 'data' key)
        old_data = old.get("data", old)
        new_data = new.get("data", new)

        all_keys = set(old_data.keys()) | set(new_data.keys())

        for key in sorted(all_keys):
            if key in exclude:
                continue

            old_val = old_data.get(key)
            new_val = new_data.get(key)

            if old_val != new_val:
                changes.append({
                    "field": key,
                    "old_value": old_val,
                    "new_value": new_val,
                })

        return {
            "old_version": old.get("version"),
            "new_version": new.get("version"),
            "changes": changes,
            "total_changes": len(changes),
        }

    def format_diff_display(self, diff: dict[str, Any]) -> str:
        """Format diff for display."""
        if "error" in diff:
            return f"Error: {diff['error']}"

        if not diff.get("changes"):
            return "No differences found."

        lines = [
            f"## Comparing v{diff['old_version']} -> v{diff['new_version']}",
            f"**{diff['total_changes']} change(s)**\n",
        ]

        for change in diff["changes"]:
            field = change["field"]
            old = change["old_value"]
            new = change["new_value"]

            lines.append(f"### {field}")
            lines.append(f"- **Before:** `{old}`")
            lines.append(f"- **After:** `{new}`")
            lines.append("")

        return "\n".join(lines)

    async def restore_version(
        self,
        table: str,
        version: int,
    ) -> tuple[bool, str]:
        """Restore a specific version as new draft."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    f"{get_api_base_url()}/api/config/{table}/restore/{version}"
                )
                if response.status_code == 200:
                    return True, "Version restored as new draft. Review and activate when ready."
                return False, f"Failed to restore: {response.text}"
        except Exception as e:
            logger.error("restore_error", error=str(e))
            return False, str(e)


class AuditLogComponent:
    """UI component for audit log viewing."""

    async def get_audit_logs(
        self,
        table: str | None = None,
        action: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get filtered audit logs."""
        try:
            params: dict[str, Any] = {"limit": limit}

            if table and table != "All":
                params["table"] = table
            if action and action != "All":
                params["action"] = action
            if start_date:
                params["start_date"] = start_date.isoformat()
            if end_date:
                params["end_date"] = end_date.isoformat()

            # Use the generic audit endpoint or per-table endpoint
            url = f"{get_api_base_url()}/api/config/audit"
            if table and table != "All":
                url = f"{get_api_base_url()}/api/config/{table}/audit"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    return data.get("entries", [])
        except Exception as e:
            logger.error("audit_fetch_error", error=str(e))
        return []

    def format_audit_table(
        self, logs: list[dict[str, Any]]
    ) -> list[list[Any]]:
        """Format audit logs for display."""
        rows = []
        for log in logs:
            # Format timestamp
            timestamp = log.get("timestamp", "?")
            if timestamp and len(timestamp) > 19:
                timestamp = timestamp[:19]

            # Format changes preview
            changes = log.get("changes", {})
            if isinstance(changes, dict):
                preview = ", ".join(f"{k}" for k in list(changes.keys())[:3])
                if len(changes) > 3:
                    preview += f" (+{len(changes)-3} more)"
            else:
                preview = str(changes)[:50]

            # Format user ID
            user_id = log.get("user_id", "system")
            if user_id and len(user_id) > 8:
                user_id = user_id[:8] + "..."

            rows.append([
                timestamp,
                log.get("action", "?"),
                log.get("config_table", "?"),
                user_id or "system",
                preview or "-",
            ])
        return rows

    def format_log_detail(self, log: dict[str, Any]) -> str:
        """Format single log entry for detailed view."""
        lines = [
            "## Audit Log Entry",
            f"**Timestamp:** {log.get('timestamp', '?')}",
            f"**Action:** {log.get('action', '?')}",
            f"**Table:** {log.get('config_table', '?')}",
            f"**User:** {log.get('user_id', 'system')}",
            f"**Config ID:** {log.get('config_id', '?')}",
            "",
            "### Changes:",
            "```json",
        ]

        changes = log.get("changes", {})
        lines.append(json.dumps(changes, indent=2, default=str))
        lines.append("```")

        return "\n".join(lines)


def create_history_tab() -> None:
    """Create the history tab UI."""
    history_component = ConfigHistoryComponent()

    gr.Markdown("## Configuration Version History")

    with gr.Row():
        table_select = gr.Dropdown(
            choices=["trading", "scoring", "discovery", "cluster", "risk", "exit", "api"],
            value="trading",
            label="Config Domain",
        )
        refresh_btn = gr.Button("Refresh", size="sm")

    # Version history table
    history_table = gr.Dataframe(
        headers=["Version", "Status", "Created", "Activated", "Notes"],
        datatype=["number", "str", "str", "str", "str"],
        label="Version History",
        interactive=False,
    )

    gr.Markdown("### Compare Versions")
    with gr.Row():
        version_a = gr.Number(label="Version A", precision=0)
        version_b = gr.Number(label="Version B", precision=0)
        compare_btn = gr.Button("Compare")

    diff_display = gr.Markdown("")

    gr.Markdown("### Restore Version")
    with gr.Row():
        restore_version_input = gr.Number(label="Version to Restore", precision=0)
        restore_btn = gr.Button("Restore as Draft", variant="secondary")

    restore_status = gr.Textbox(label="Status", interactive=False)

    # Event handlers - synchronous wrappers
    def load_history_sync(table: str) -> list[list[Any]]:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        versions = loop.run_until_complete(
            history_component.get_version_history(table)
        )
        return history_component.format_history_table(versions)

    def do_compare_sync(
        table: str,
        v_a: float | None,
        v_b: float | None
    ) -> str:
        if not v_a or not v_b:
            return "Please select two versions to compare."

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        diff = loop.run_until_complete(
            history_component.compare_versions(table, int(v_a), int(v_b))
        )
        return history_component.format_diff_display(diff)

    def do_restore_sync(table: str, version: float | None) -> str:
        if not version:
            return "Please enter a version number."

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        _success, msg = loop.run_until_complete(
            history_component.restore_version(table, int(version))
        )
        return msg

    # Wire up events
    table_select.change(load_history_sync, [table_select], [history_table])
    refresh_btn.click(load_history_sync, [table_select], [history_table])
    compare_btn.click(
        do_compare_sync,
        [table_select, version_a, version_b],
        [diff_display]
    )
    restore_btn.click(
        do_restore_sync,
        [table_select, restore_version_input],
        [restore_status]
    )


def create_audit_tab() -> None:
    """Create the audit log tab UI."""
    audit_component = AuditLogComponent()

    gr.Markdown("## Configuration Audit Log")

    # Filters
    with gr.Row():
        filter_table = gr.Dropdown(
            choices=[
                "All", "trading", "scoring", "discovery",
                "cluster", "risk", "exit", "api"
            ],
            value="All",
            label="Table",
        )
        filter_action = gr.Dropdown(
            choices=["All", "create", "update", "activate", "archive", "restore"],
            value="All",
            label="Action",
        )
        filter_days = gr.Slider(
            minimum=1,
            maximum=90,
            value=7,
            step=1,
            label="Last N Days",
        )
        filter_btn = gr.Button("Apply Filters")

    # Audit log table
    audit_table = gr.Dataframe(
        headers=["Timestamp", "Action", "Table", "User", "Changes Preview"],
        datatype=["str", "str", "str", "str", "str"],
        label="Audit Logs",
        interactive=False,
    )

    # Detail view
    gr.Markdown("### Log Details")
    with gr.Row():
        log_index = gr.Number(label="Row Index (0-based)", precision=0, value=0)
        view_detail_btn = gr.Button("View Details")

    log_detail = gr.Markdown("")

    # State for storing logs
    logs_state = gr.State([])

    # Event handlers
    def load_audit_logs_sync(
        table: str,
        action: str,
        days: int
    ) -> tuple[list[list[Any]], list[dict[str, Any]]]:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        table_filter = None if table == "All" else table
        action_filter = None if action == "All" else action
        start_date = datetime.now(UTC) - timedelta(days=int(days))

        logs = loop.run_until_complete(
            audit_component.get_audit_logs(
                table=table_filter,
                action=action_filter,
                start_date=start_date,
            )
        )

        table_data = audit_component.format_audit_table(logs)
        return table_data, logs

    def show_detail(logs: list[dict[str, Any]], index: float | None) -> str:
        if not logs or index is None:
            return "No log selected."
        idx = int(index)
        if idx < 0 or idx >= len(logs):
            return f"Invalid index. Valid range: 0-{len(logs)-1}"
        return audit_component.format_log_detail(logs[idx])

    # Wire up events
    filter_btn.click(
        load_audit_logs_sync,
        [filter_table, filter_action, filter_days],
        [audit_table, logs_state]
    )
    view_detail_btn.click(show_detail, [logs_state, log_index], [log_detail])
