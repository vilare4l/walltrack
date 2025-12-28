# Story 11.6: UI - Historique et Audit des Configs

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 3
- **Depends on**: Story 11-5 (Config UI Page)

## User Story

**As a** system administrator,
**I want** to view configuration change history and audit logs,
**So that** I can track who changed what and when, and restore previous versions if needed.

## Acceptance Criteria

### AC 1: View Config Version History
**Given** I am on the Config page
**When** I click "History" for a config domain
**Then** I see a list of all versions with dates, status, and changes
**And** versions are sorted by created_at DESC

### AC 2: Version Comparison
**Given** I select two versions from the history
**When** I click "Compare"
**Then** I see a diff view highlighting changed fields
**And** old values are shown in red, new in green

### AC 3: Restore Previous Version
**Given** I am viewing a historical version
**When** I click "Restore this version"
**Then** a new draft is created with those values
**And** I can review before activating

### AC 4: Audit Log View
**Given** I navigate to the Audit tab
**When** the page loads
**Then** I see all config changes across all domains
**And** each entry shows timestamp, user, action, table, changes

### AC 5: Filter Audit Logs
**Given** I am viewing the audit log
**When** I filter by date range, action type, or table
**Then** only matching entries are displayed
**And** filters can be combined

## Technical Specifications

### Config History Component

**src/walltrack/ui/components/config_history.py:**
```python
"""Configuration history and audit UI component."""

from datetime import datetime, timedelta
from typing import Optional

import gradio as gr
import structlog

from walltrack.services.config.config_api import ConfigAPI

logger = structlog.get_logger(__name__)


class ConfigHistoryComponent:
    """UI component for config history and version management."""

    def __init__(self, config_api: ConfigAPI):
        self.api = config_api
        self.selected_versions: list[int] = []

    async def get_version_history(
        self,
        table: str,
        limit: int = 20,
    ) -> list[dict]:
        """Get version history for a config table."""
        try:
            versions = await self.api.get_all_versions(table)
            return versions[:limit]
        except Exception as e:
            logger.error("history_fetch_error", table=table, error=str(e))
            return []

    def format_history_table(self, versions: list[dict]) -> list[list]:
        """Format versions for display in a table."""
        rows = []
        for v in versions:
            rows.append([
                v.get("version", "?"),
                v.get("status", "?"),
                v.get("created_at", "?")[:19] if v.get("created_at") else "?",
                v.get("activated_at", "-")[:19] if v.get("activated_at") else "-",
                v.get("notes", "-") or "-",
            ])
        return rows

    async def compare_versions(
        self,
        table: str,
        version_a: int,
        version_b: int,
    ) -> dict:
        """Compare two config versions."""
        try:
            versions = await self.api.get_all_versions(table)

            config_a = None
            config_b = None

            for v in versions:
                if v.get("version") == version_a:
                    config_a = v
                if v.get("version") == version_b:
                    config_b = v

            if not config_a or not config_b:
                return {"error": "Version not found"}

            # Find differences
            diff = self._compute_diff(config_a, config_b)
            return diff

        except Exception as e:
            logger.error("compare_error", error=str(e))
            return {"error": str(e)}

    def _compute_diff(self, old: dict, new: dict) -> dict:
        """Compute difference between two configs."""
        # Fields to exclude from comparison
        exclude = {"id", "created_at", "updated_at", "activated_at", "archived_at", "version", "status"}

        changes = []
        all_keys = set(old.keys()) | set(new.keys())

        for key in sorted(all_keys):
            if key in exclude:
                continue

            old_val = old.get(key)
            new_val = new.get(key)

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

    def format_diff_display(self, diff: dict) -> str:
        """Format diff for display."""
        if "error" in diff:
            return f"Error: {diff['error']}"

        if not diff.get("changes"):
            return "No differences found."

        lines = [
            f"## Comparing v{diff['old_version']} → v{diff['new_version']}",
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
        version_id: int,
    ) -> tuple[bool, str]:
        """Restore a specific version as new draft."""
        try:
            result = await self.api.restore_version(table, version_id)
            if result:
                return True, f"Version restored as new draft. Review and activate when ready."
            return False, "Failed to restore version"
        except Exception as e:
            logger.error("restore_error", error=str(e))
            return False, str(e)


class AuditLogComponent:
    """UI component for audit log viewing."""

    def __init__(self, config_api: ConfigAPI):
        self.api = config_api

    async def get_audit_logs(
        self,
        table: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Get filtered audit logs."""
        try:
            logs = await self.api.get_audit_logs(
                table=table,
                action=action,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            return logs
        except Exception as e:
            logger.error("audit_fetch_error", error=str(e))
            return []

    def format_audit_table(self, logs: list[dict]) -> list[list]:
        """Format audit logs for display."""
        rows = []
        for log in logs:
            # Format changes preview
            changes = log.get("changes", {})
            if isinstance(changes, dict):
                preview = ", ".join(f"{k}" for k in list(changes.keys())[:3])
                if len(changes) > 3:
                    preview += f" (+{len(changes)-3} more)"
            else:
                preview = str(changes)[:50]

            rows.append([
                log.get("timestamp", "?")[:19] if log.get("timestamp") else "?",
                log.get("action", "?"),
                log.get("config_table", "?"),
                log.get("user_id", "system")[:8] + "..." if log.get("user_id") else "system",
                preview or "-",
            ])
        return rows

    def format_log_detail(self, log: dict) -> str:
        """Format single log entry for detailed view."""
        lines = [
            f"## Audit Log Entry",
            f"**Timestamp:** {log.get('timestamp', '?')}",
            f"**Action:** {log.get('action', '?')}",
            f"**Table:** {log.get('config_table', '?')}",
            f"**User:** {log.get('user_id', 'system')}",
            f"**Config ID:** {log.get('config_id', '?')}",
            "",
            "### Changes:",
            "```json",
        ]

        import json
        changes = log.get("changes", {})
        lines.append(json.dumps(changes, indent=2, default=str))
        lines.append("```")

        return "\n".join(lines)


def build_history_tab(config_api: ConfigAPI) -> gr.Blocks:
    """Build the history tab UI."""
    history_component = ConfigHistoryComponent(config_api)

    with gr.Blocks() as history_tab:
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

        diff_display = gr.Markdown(label="Comparison Result")

        gr.Markdown("### Restore Version")
        with gr.Row():
            restore_version_input = gr.Number(label="Version to Restore", precision=0)
            restore_btn = gr.Button("Restore as Draft", variant="secondary")

        restore_status = gr.Textbox(label="Status", interactive=False)

        # Event handlers
        async def load_history(table):
            versions = await history_component.get_version_history(table)
            return history_component.format_history_table(versions)

        async def do_compare(table, v_a, v_b):
            if not v_a or not v_b:
                return "Please select two versions to compare."
            diff = await history_component.compare_versions(table, int(v_a), int(v_b))
            return history_component.format_diff_display(diff)

        async def do_restore(table, version):
            if not version:
                return "Please enter a version number."
            success, msg = await history_component.restore_version(table, int(version))
            return msg

        # Wire up events
        table_select.change(load_history, [table_select], [history_table])
        refresh_btn.click(load_history, [table_select], [history_table])
        compare_btn.click(do_compare, [table_select, version_a, version_b], [diff_display])
        restore_btn.click(do_restore, [table_select, restore_version_input], [restore_status])

        # Initial load
        history_tab.load(load_history, [table_select], [history_table])

    return history_tab


def build_audit_tab(config_api: ConfigAPI) -> gr.Blocks:
    """Build the audit log tab UI."""
    audit_component = AuditLogComponent(config_api)

    with gr.Blocks() as audit_tab:
        gr.Markdown("## Configuration Audit Log")

        # Filters
        with gr.Row():
            filter_table = gr.Dropdown(
                choices=["All", "trading", "scoring", "discovery", "cluster", "risk", "exit", "api"],
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

        log_detail = gr.Markdown(label="Log Detail")

        # State for storing logs
        logs_state = gr.State([])

        # Event handlers
        async def load_audit_logs(table, action, days):
            table_filter = None if table == "All" else table
            action_filter = None if action == "All" else action
            start_date = datetime.utcnow() - timedelta(days=int(days))

            logs = await audit_component.get_audit_logs(
                table=table_filter,
                action=action_filter,
                start_date=start_date,
            )

            table_data = audit_component.format_audit_table(logs)
            return table_data, logs

        def show_detail(logs, index):
            if not logs or index is None:
                return "No log selected."
            idx = int(index)
            if idx < 0 or idx >= len(logs):
                return f"Invalid index. Valid range: 0-{len(logs)-1}"
            return audit_component.format_log_detail(logs[idx])

        # Wire up events
        filter_btn.click(
            load_audit_logs,
            [filter_table, filter_action, filter_days],
            [audit_table, logs_state]
        )
        view_detail_btn.click(show_detail, [logs_state, log_index], [log_detail])

        # Initial load
        audit_tab.load(
            load_audit_logs,
            [filter_table, filter_action, filter_days],
            [audit_table, logs_state]
        )

    return audit_tab
```

### Extended Config API for History

**src/walltrack/services/config/config_api.py (additions):**
```python
# Add to existing ConfigAPI class

async def get_all_versions(self, table: str) -> list[dict]:
    """Get all versions of a config table."""
    db_table = f"{table}_config"

    result = await self.client.table(db_table) \
        .select("*") \
        .order("version", desc=True) \
        .execute()

    return result.data or []

async def restore_version(self, table: str, config_id: int) -> bool:
    """Restore a specific version as new draft."""
    db_table = f"{table}_config"

    # Get the version to restore
    result = await self.client.table(db_table) \
        .select("*") \
        .eq("id", config_id) \
        .single() \
        .execute()

    if not result.data:
        return False

    old_config = result.data

    # Remove system fields
    exclude = {"id", "created_at", "updated_at", "activated_at", "archived_at", "version", "status"}
    new_data = {k: v for k, v in old_config.items() if k not in exclude}
    new_data["status"] = "draft"
    new_data["notes"] = f"Restored from version {old_config.get('version', '?')}"

    # Archive any existing draft
    await self.client.table(db_table) \
        .update({"status": "archived"}) \
        .eq("status", "draft") \
        .execute()

    # Create new draft
    insert_result = await self.client.table(db_table) \
        .insert(new_data) \
        .execute()

    if insert_result.data:
        await self._log_audit(table, insert_result.data[0]["id"], "restore", new_data)
        return True

    return False

async def get_audit_logs(
    self,
    table: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100,
) -> list[dict]:
    """Get filtered audit logs."""
    query = self.client.table("config_audit_log").select("*")

    if table:
        query = query.eq("config_table", table)

    if action:
        query = query.eq("action", action)

    if start_date:
        query = query.gte("timestamp", start_date.isoformat())

    if end_date:
        query = query.lte("timestamp", end_date.isoformat())

    query = query.order("timestamp", desc=True).limit(limit)

    result = await query.execute()
    return result.data or []
```

### Integration with Config Page

**Update src/walltrack/ui/pages/config_page.py:**
```python
"""Config page with history and audit tabs."""

import gradio as gr

from walltrack.services.config.config_api import ConfigAPI
from walltrack.ui.components.config_editor import build_config_editor
from walltrack.ui.components.config_history import build_history_tab, build_audit_tab


async def build_config_page() -> gr.Blocks:
    """Build complete config management page."""
    config_api = await ConfigAPI.create()

    with gr.Blocks() as config_page:
        gr.Markdown("# Configuration Management")

        with gr.Tabs():
            with gr.Tab("Editor"):
                await build_config_editor(config_api)

            with gr.Tab("History"):
                build_history_tab(config_api)

            with gr.Tab("Audit Log"):
                build_audit_tab(config_api)

    return config_page
```

## Implementation Tasks

- [x] Create ConfigHistoryComponent class
- [x] Create AuditLogComponent class
- [x] Implement version comparison logic
- [x] Implement restore_version in ConfigAPI
- [x] Implement get_audit_logs with filters
- [x] Build history tab UI
- [x] Build audit tab UI
- [x] Integrate tabs into config page
- [x] Write tests for history component
- [x] Write tests for audit component

## Definition of Done

- [x] Version history displays correctly
- [x] Version comparison shows diffs
- [x] Restore creates new draft
- [x] Audit logs display with filters
- [x] All date filters work
- [x] Tests passing

## File List

### New Files
- `src/walltrack/ui/components/config_history.py` - History and audit components

### Modified Files
- `src/walltrack/services/config/config_api.py` - Add history/audit methods
- `src/walltrack/ui/pages/config_page.py` - Add tabs
