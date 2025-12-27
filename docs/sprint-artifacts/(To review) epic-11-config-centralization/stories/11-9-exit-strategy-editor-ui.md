# Story 11.9: UI - Exit Strategy Editor

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: done
- **Priority**: P1 - High
- **Story Points**: 5
- **Depends on**: Story 11-7 (Exit Strategy CRUD)

## User Story

**As a** trader,
**I want** a visual editor to create and modify exit strategies,
**So that** I can easily configure rules without writing code.

## Acceptance Criteria

### AC 1: List All Strategies
**Given** I navigate to Exit Strategies page
**When** the page loads
**Then** I see all strategies with name, version, status
**And** active strategies are highlighted

### AC 2: Create New Strategy
**Given** I click "New Strategy"
**When** I fill in name and add rules
**Then** I can add multiple rules with visual controls
**And** save creates a draft

### AC 3: Edit Strategy
**Given** I select a strategy
**When** I click "Edit"
**Then** I see the rule editor
**And** I can modify or reorder rules

### AC 4: Visual Rule Builder
**Given** I am adding a rule
**When** I select rule type
**Then** I see type-specific inputs (e.g., trigger %, exit %)
**And** validation prevents invalid values

### AC 5: Preview Rules
**Given** I have configured rules
**When** I click "Preview"
**Then** I see a visualization of exit points
**And** chart shows entry, TPs, SL levels

### AC 6: Clone Strategy
**Given** I select an existing strategy
**When** I click "Clone"
**Then** a copy is created with "(copy)" suffix
**And** I can immediately edit the clone

## Technical Specifications

### Exit Strategy Editor Component

**src/walltrack/ui/pages/exit_strategies_page.py:**
```python
"""Exit strategies editor page."""

import gradio as gr
import structlog
from decimal import Decimal

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategyService,
    ExitStrategyCreate,
    ExitStrategyUpdate,
    ExitStrategyRule,
    get_exit_strategy_service,
)
from walltrack.services.exit.strategy_templates import TEMPLATES, get_template

logger = structlog.get_logger(__name__)


class ExitStrategiesPage:
    """Exit strategies management page."""

    def __init__(self):
        self.service: ExitStrategyService = None

    async def initialize(self):
        """Initialize service."""
        self.service = await get_exit_strategy_service()

    async def get_strategies_list(self, include_archived: bool = False) -> list[list]:
        """Get formatted strategies list for table."""
        if not self.service:
            await self.initialize()

        strategies = await self.service.list_all(include_archived=include_archived)

        rows = []
        for s in strategies:
            status_emoji = {
                "active": "✅",
                "draft": "📝",
                "archived": "📦"
            }.get(s.status, "❓")

            rows.append([
                s.id[:8] + "...",
                s.name,
                s.version,
                f"{status_emoji} {s.status}",
                len(s.rules),
                s.created_at.strftime("%Y-%m-%d %H:%M"),
            ])

        return rows

    async def get_strategy_details(self, strategy_id: str) -> dict:
        """Get strategy details for editing."""
        if not self.service:
            await self.initialize()

        # Handle truncated ID from table
        strategies = await self.service.list_all(include_archived=True)
        strategy = None
        for s in strategies:
            if s.id.startswith(strategy_id.replace("...", "")):
                strategy = s
                break

        if not strategy:
            return {"error": "Strategy not found"}

        return {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description or "",
            "version": strategy.version,
            "status": strategy.status,
            "rules": [
                {
                    "rule_type": r.rule_type,
                    "trigger_pct": float(r.trigger_pct) if r.trigger_pct else None,
                    "exit_pct": float(r.exit_pct),
                    "priority": r.priority,
                    "enabled": r.enabled,
                    "params": r.params,
                }
                for r in strategy.rules
            ],
            "max_hold_hours": strategy.max_hold_hours,
            "stagnation_hours": strategy.stagnation_hours,
            "stagnation_threshold_pct": float(strategy.stagnation_threshold_pct),
        }

    async def create_strategy(
        self,
        name: str,
        description: str,
        rules_json: str,
        max_hold_hours: int,
        stagnation_hours: int,
        stagnation_threshold: float,
    ) -> tuple[bool, str]:
        """Create a new strategy from form data."""
        if not self.service:
            await self.initialize()

        try:
            import json
            rules_data = json.loads(rules_json)
            rules = [
                ExitStrategyRule(
                    rule_type=r["rule_type"],
                    trigger_pct=Decimal(str(r["trigger_pct"])) if r.get("trigger_pct") is not None else None,
                    exit_pct=Decimal(str(r.get("exit_pct", 100))),
                    priority=r.get("priority", 0),
                    enabled=r.get("enabled", True),
                    params=r.get("params", {}),
                )
                for r in rules_data
            ]

            create_data = ExitStrategyCreate(
                name=name,
                description=description or None,
                rules=rules,
                max_hold_hours=max_hold_hours,
                stagnation_hours=stagnation_hours,
                stagnation_threshold_pct=Decimal(str(stagnation_threshold)),
            )

            strategy = await self.service.create(create_data)
            return True, f"Strategy '{strategy.name}' created (draft)"

        except Exception as e:
            logger.error("create_strategy_error", error=str(e))
            return False, str(e)

    async def update_strategy(
        self,
        strategy_id: str,
        name: str,
        description: str,
        rules_json: str,
        max_hold_hours: int,
        stagnation_hours: int,
        stagnation_threshold: float,
    ) -> tuple[bool, str]:
        """Update an existing strategy."""
        if not self.service:
            await self.initialize()

        try:
            import json
            rules_data = json.loads(rules_json)
            rules = [
                ExitStrategyRule(
                    rule_type=r["rule_type"],
                    trigger_pct=Decimal(str(r["trigger_pct"])) if r.get("trigger_pct") is not None else None,
                    exit_pct=Decimal(str(r.get("exit_pct", 100))),
                    priority=r.get("priority", 0),
                    enabled=r.get("enabled", True),
                    params=r.get("params", {}),
                )
                for r in rules_data
            ]

            update_data = ExitStrategyUpdate(
                name=name,
                description=description or None,
                rules=rules,
                max_hold_hours=max_hold_hours,
                stagnation_hours=stagnation_hours,
                stagnation_threshold_pct=Decimal(str(stagnation_threshold)),
            )

            strategy = await self.service.update(strategy_id, update_data)
            return True, f"Strategy '{strategy.name}' updated"

        except Exception as e:
            logger.error("update_strategy_error", error=str(e))
            return False, str(e)

    async def activate_strategy(self, strategy_id: str) -> tuple[bool, str]:
        """Activate a draft strategy."""
        if not self.service:
            await self.initialize()

        try:
            strategy = await self.service.activate(strategy_id)
            return True, f"Strategy '{strategy.name}' is now active"
        except Exception as e:
            logger.error("activate_error", error=str(e))
            return False, str(e)

    async def clone_strategy(self, strategy_id: str) -> tuple[bool, str]:
        """Clone a strategy."""
        if not self.service:
            await self.initialize()

        try:
            cloned = await self.service.clone(strategy_id)
            return True, f"Cloned as '{cloned.name}' (draft)"
        except Exception as e:
            logger.error("clone_error", error=str(e))
            return False, str(e)

    async def delete_draft(self, strategy_id: str) -> tuple[bool, str]:
        """Delete a draft strategy."""
        if not self.service:
            await self.initialize()

        try:
            await self.service.delete_draft(strategy_id)
            return True, "Draft deleted"
        except Exception as e:
            logger.error("delete_error", error=str(e))
            return False, str(e)

    async def create_from_template(self, template_name: str) -> tuple[bool, str]:
        """Create strategy from template."""
        if not self.service:
            await self.initialize()

        try:
            template = get_template(template_name)
            strategy = await self.service.create(template)
            return True, f"Created '{strategy.name}' from {template_name} template"
        except Exception as e:
            logger.error("template_error", error=str(e))
            return False, str(e)


def build_rule_editor_component() -> tuple:
    """Build rule editor UI components."""
    with gr.Column():
        gr.Markdown("### Exit Rules")

        rules_json = gr.Code(
            language="json",
            label="Rules (JSON)",
            value='[\n  {\n    "rule_type": "stop_loss",\n    "trigger_pct": -10,\n    "exit_pct": 100,\n    "priority": 0,\n    "enabled": true\n  },\n  {\n    "rule_type": "take_profit",\n    "trigger_pct": 15,\n    "exit_pct": 50,\n    "priority": 1,\n    "enabled": true\n  }\n]',
            lines=15,
        )

        gr.Markdown("""
        **Rule Types:**
        - `stop_loss`: Exit when loss reaches trigger_pct (negative)
        - `take_profit`: Exit when gain reaches trigger_pct (positive)
        - `trailing_stop`: Exit on drop from high, params: {"activation_pct": N}
        - `time_based`: Exit after N hours, params: {"max_hours": N}

        **Fields:**
        - `trigger_pct`: Trigger percentage (negative for stop loss)
        - `exit_pct`: Percentage of position to exit (1-100)
        - `priority`: Lower = higher priority (0 = highest)
        - `enabled`: true/false
        - `params`: Additional parameters for rule type
        """)

    return rules_json


async def build_exit_strategies_page() -> gr.Blocks:
    """Build the exit strategies management page."""
    page = ExitStrategiesPage()
    await page.initialize()

    with gr.Blocks() as strategies_page:
        gr.Markdown("# Exit Strategies")

        # State
        selected_strategy_id = gr.State(None)
        edit_mode = gr.State(False)

        with gr.Row():
            # Left panel - Strategy list
            with gr.Column(scale=1):
                gr.Markdown("### Strategies")

                include_archived = gr.Checkbox(label="Show Archived", value=False)

                strategies_table = gr.Dataframe(
                    headers=["ID", "Name", "Version", "Status", "Rules", "Created"],
                    datatype=["str", "str", "number", "str", "number", "str"],
                    label="Exit Strategies",
                    interactive=False,
                )

                with gr.Row():
                    refresh_btn = gr.Button("Refresh", size="sm")
                    new_btn = gr.Button("+ New", variant="primary", size="sm")

                gr.Markdown("### Quick Actions")
                with gr.Row():
                    template_select = gr.Dropdown(
                        choices=["standard", "aggressive", "conservative"],
                        label="Template",
                    )
                    create_from_template_btn = gr.Button("Create from Template", size="sm")

            # Right panel - Editor
            with gr.Column(scale=2):
                gr.Markdown("### Strategy Editor")

                with gr.Group():
                    with gr.Row():
                        strategy_name = gr.Textbox(label="Name", placeholder="My Strategy")
                        strategy_version = gr.Number(label="Version", precision=0, interactive=False)
                        strategy_status = gr.Textbox(label="Status", interactive=False)

                    strategy_description = gr.Textbox(
                        label="Description",
                        placeholder="Strategy description...",
                        lines=2,
                    )

                    with gr.Row():
                        max_hold_hours = gr.Number(
                            label="Max Hold (hours)",
                            value=24,
                            precision=0,
                        )
                        stagnation_hours = gr.Number(
                            label="Stagnation (hours)",
                            value=6,
                            precision=0,
                        )
                        stagnation_threshold = gr.Number(
                            label="Stagnation Threshold (%)",
                            value=2.0,
                        )

                    rules_json = build_rule_editor_component()

                # Actions
                with gr.Row():
                    save_btn = gr.Button("Save Draft", variant="primary")
                    activate_btn = gr.Button("Activate", variant="secondary")
                    clone_btn = gr.Button("Clone")
                    delete_btn = gr.Button("Delete Draft", variant="stop")

                status_msg = gr.Textbox(label="Status", interactive=False)

        # Strategy visualization
        with gr.Accordion("Strategy Preview", open=False):
            preview_chart = gr.Plot(label="Exit Levels Visualization")

            def generate_preview_chart(rules_str: str, entry_price: float = 100):
                """Generate preview chart of exit levels."""
                import matplotlib.pyplot as plt
                import json

                try:
                    rules = json.loads(rules_str)
                except:
                    return None

                fig, ax = plt.subplots(figsize=(10, 6))

                # Entry line
                ax.axhline(y=entry_price, color='blue', linestyle='-', label='Entry', linewidth=2)

                colors = {
                    "stop_loss": "red",
                    "take_profit": "green",
                    "trailing_stop": "orange",
                }

                for rule in rules:
                    if not rule.get("enabled", True):
                        continue

                    rule_type = rule.get("rule_type")
                    trigger_pct = rule.get("trigger_pct")

                    if trigger_pct is None:
                        continue

                    level = entry_price * (1 + trigger_pct / 100)
                    color = colors.get(rule_type, "gray")
                    exit_pct = rule.get("exit_pct", 100)

                    ax.axhline(
                        y=level,
                        color=color,
                        linestyle='--',
                        label=f'{rule_type} ({trigger_pct:+}%) - Exit {exit_pct}%',
                        alpha=0.7,
                    )

                ax.set_ylabel('Price')
                ax.set_title('Exit Strategy Levels')
                ax.legend(loc='best')
                ax.grid(True, alpha=0.3)

                # Set y-axis range
                ax.set_ylim([entry_price * 0.7, entry_price * 1.5])

                plt.tight_layout()
                return fig

            preview_btn = gr.Button("Generate Preview")
            preview_btn.click(generate_preview_chart, [rules_json], [preview_chart])

        # Event handlers
        async def load_strategies(show_archived):
            return await page.get_strategies_list(include_archived=show_archived)

        async def on_strategy_select(evt: gr.SelectData, table_data):
            if evt.index[0] < len(table_data):
                strategy_id = table_data[evt.index[0]][0]
                details = await page.get_strategy_details(strategy_id)

                if "error" in details:
                    return [None, "", "", 0, "", "", "[]", 24, 6, 2.0, details["error"]]

                import json
                rules_str = json.dumps(details["rules"], indent=2)

                return [
                    details["id"],
                    details["name"],
                    details["description"],
                    details["version"],
                    details["status"],
                    rules_str,
                    details["max_hold_hours"],
                    details["stagnation_hours"],
                    details["stagnation_threshold_pct"],
                    f"Loaded: {details['name']}"
                ]

            return [None, "", "", 0, "", "[]", 24, 6, 2.0, ""]

        async def on_save(
            strategy_id,
            name,
            description,
            rules_str,
            max_hold,
            stagnation_h,
            stagnation_t,
        ):
            if strategy_id:
                success, msg = await page.update_strategy(
                    strategy_id, name, description, rules_str,
                    int(max_hold), int(stagnation_h), float(stagnation_t)
                )
            else:
                success, msg = await page.create_strategy(
                    name, description, rules_str,
                    int(max_hold), int(stagnation_h), float(stagnation_t)
                )

            # Reload list
            strategies = await page.get_strategies_list()
            return strategies, msg

        async def on_activate(strategy_id):
            if not strategy_id:
                return "No strategy selected"
            success, msg = await page.activate_strategy(strategy_id)
            return msg

        async def on_clone(strategy_id):
            if not strategy_id:
                return "No strategy selected", await page.get_strategies_list()
            success, msg = await page.clone_strategy(strategy_id)
            strategies = await page.get_strategies_list()
            return msg, strategies

        async def on_delete(strategy_id):
            if not strategy_id:
                return "No strategy selected", await page.get_strategies_list()
            success, msg = await page.delete_draft(strategy_id)
            strategies = await page.get_strategies_list()
            return msg, strategies

        async def on_new():
            return [
                None, "", "", 0, "draft",
                '[\n  {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "priority": 0, "enabled": true}\n]',
                24, 6, 2.0, "New strategy - fill in details"
            ]

        async def on_create_from_template(template):
            if not template:
                return "Select a template", await page.get_strategies_list()
            success, msg = await page.create_from_template(template)
            strategies = await page.get_strategies_list()
            return msg, strategies

        # Wire up events
        refresh_btn.click(load_strategies, [include_archived], [strategies_table])
        include_archived.change(load_strategies, [include_archived], [strategies_table])

        strategies_table.select(
            on_strategy_select,
            [strategies_table],
            [selected_strategy_id, strategy_name, strategy_description,
             strategy_version, strategy_status, rules_json,
             max_hold_hours, stagnation_hours, stagnation_threshold, status_msg]
        )

        save_btn.click(
            on_save,
            [selected_strategy_id, strategy_name, strategy_description,
             rules_json, max_hold_hours, stagnation_hours, stagnation_threshold],
            [strategies_table, status_msg]
        )

        activate_btn.click(on_activate, [selected_strategy_id], [status_msg])
        clone_btn.click(on_clone, [selected_strategy_id], [status_msg, strategies_table])
        delete_btn.click(on_delete, [selected_strategy_id], [status_msg, strategies_table])
        new_btn.click(
            on_new,
            [],
            [selected_strategy_id, strategy_name, strategy_description,
             strategy_version, strategy_status, rules_json,
             max_hold_hours, stagnation_hours, stagnation_threshold, status_msg]
        )
        create_from_template_btn.click(
            on_create_from_template,
            [template_select],
            [status_msg, strategies_table]
        )

        # Initial load
        strategies_page.load(load_strategies, [include_archived], [strategies_table])

    return strategies_page
```

## Implementation Tasks

- [x] Create ExitStrategiesPage class
- [x] Implement strategies list view
- [x] Implement strategy selection and loading
- [x] Build rule editor with JSON input
- [x] Add form validation
- [x] Implement create/update handlers
- [x] Implement activate/clone/delete handlers
- [x] Add strategy preview chart
- [x] Create from template functionality
- [x] Add to main navigation

## Definition of Done

- [x] All strategies display in list
- [x] Create new strategy works
- [x] Edit existing strategy works
- [x] Rule editor validates JSON
- [x] Preview shows exit levels
- [x] Clone creates copy
- [x] Delete removes drafts only

## File List

### New Files
- `src/walltrack/ui/pages/exit_strategies_page.py` - Main page

### Modified Files
- `src/walltrack/ui/app.py` - Add exit strategies to navigation
