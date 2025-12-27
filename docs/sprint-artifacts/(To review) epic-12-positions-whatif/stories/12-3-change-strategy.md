# Story 12.3: Change Strategy - Position Active

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P1 - High
- **Story Points**: 5
- **Depends on**: Story 12-2 (Position Details), Story 11-7 (Exit Strategy CRUD)

## User Story

**As a** the operator,
**I want** changer la stratégie d'une position active,
**So that** je peux adapter ma sortie selon l'évolution du marché.

## Acceptance Criteria

### AC 1: Open Strategy Panel
**Given** je clique sur [⚙️] d'une position active
**When** le panneau s'ouvre
**Then** je vois:
- Stratégie actuelle
- Dropdown avec toutes les stratégies disponibles
- Preview des nouveaux niveaux TP/SL
- Bouton "Appliquer"

### AC 2: Preview New Levels
**Given** je sélectionne une nouvelle stratégie
**When** le dropdown change
**Then** je vois un preview des niveaux recalculés par rapport au prix d'entrée
**And** les prix absolus sont affichés

### AC 3: Apply Strategy Change
**Given** je sélectionne une nouvelle stratégie
**When** je clique "Appliquer"
**Then** une confirmation est demandée
**And** après confirmation, la stratégie est changée immédiatement
**And** un log est créé dans l'audit

### AC 4: Preserve Reached TPs
**Given** la position a déjà atteint un TP (partiellement vendu)
**When** je change de stratégie
**Then** les TP déjà exécutés restent marqués
**And** seuls les TP restants sont recalculés

### AC 5: Log Strategy Change
**Given** une stratégie est changée
**When** le changement est appliqué
**Then** un event est enregistré dans position_events
**And** l'ancien et nouveau strategy_id sont loggés

## Technical Specifications

### Strategy Change Modal

**src/walltrack/ui/components/change_strategy_modal.py:**
```python
"""Strategy change modal for active positions."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

import gradio as gr
import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyService,
    get_exit_strategy_service,
)
from walltrack.services.exit.strategy_assigner import get_exit_strategy_assigner

logger = structlog.get_logger(__name__)


class ChangeStrategyModal:
    """Modal for changing position exit strategy."""

    def __init__(self):
        self.strategy_service: Optional[ExitStrategyService] = None
        self._client = None

    async def initialize(self):
        """Initialize services."""
        self.strategy_service = await get_exit_strategy_service()
        from walltrack.data.supabase.client import get_supabase_client
        self._client = await get_supabase_client()

    async def get_available_strategies(self) -> list[tuple[str, str]]:
        """Get all active strategies for dropdown."""
        if not self.strategy_service:
            await self.initialize()

        strategies = await self.strategy_service.list_all()
        active_strategies = [s for s in strategies if s.status == "active"]

        return [(f"{s.name} (v{s.version})", s.id) for s in active_strategies]

    async def get_position(self, position_id: str) -> Optional[dict]:
        """Get position details."""
        if not self._client:
            await self.initialize()

        result = await self._client.table("positions") \
            .select("""
                id, token_address, entry_price, current_price, size_sol,
                exit_strategy_id, status,
                exit_strategies(id, name, version),
                position_exits(id, exit_type, trigger_pct, executed_at)
            """) \
            .eq("id", position_id) \
            .eq("status", "open") \
            .single() \
            .execute()

        return result.data

    async def get_strategy(self, strategy_id: str) -> Optional[ExitStrategy]:
        """Get strategy by ID."""
        if not self.strategy_service:
            await self.initialize()

        return await self.strategy_service.get(strategy_id)

    def calculate_preview(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        executed_exits: list[dict],
    ) -> dict:
        """
        Calculate preview of strategy levels.

        Returns dict with levels and their absolute prices.
        """
        # Get already executed exit types
        executed_types = set()
        for ex in executed_exits:
            key = f"{ex['exit_type']}_{ex['trigger_pct']}"
            executed_types.add(key)

        preview = {
            "strategy_name": strategy.name,
            "levels": [],
        }

        for rule in strategy.rules:
            if not rule.enabled:
                continue

            rule_type = rule.rule_type
            trigger_pct = rule.trigger_pct

            # Calculate absolute price
            if trigger_pct is not None:
                abs_price = entry_price * (1 + trigger_pct / 100)
            else:
                abs_price = None

            # Check if already executed
            key = f"{rule_type}_{trigger_pct}"
            already_executed = key in executed_types

            preview["levels"].append({
                "type": rule_type,
                "trigger_pct": trigger_pct,
                "exit_pct": rule.exit_pct,
                "absolute_price": abs_price,
                "already_executed": already_executed,
            })

        return preview

    async def apply_strategy_change(
        self,
        position_id: str,
        new_strategy_id: str,
        user_id: str = "operator",
    ) -> tuple[bool, str]:
        """
        Apply strategy change to position.

        Returns (success, message).
        """
        if not self._client:
            await self.initialize()

        # Get current position
        position = await self.get_position(position_id)
        if not position:
            return False, "Position not found or not open"

        old_strategy_id = position.get("exit_strategy_id")
        old_strategy = position.get("exit_strategies") or {}

        # Get new strategy
        new_strategy = await self.get_strategy(new_strategy_id)
        if not new_strategy:
            return False, "New strategy not found"

        # Update position
        result = await self._client.table("positions") \
            .update({
                "exit_strategy_id": new_strategy_id,
                "exit_strategy_changed_at": datetime.utcnow().isoformat(),
            }) \
            .eq("id", position_id) \
            .execute()

        if not result.data:
            return False, "Failed to update position"

        # Log the event
        await self._log_strategy_change(
            position_id=position_id,
            old_strategy_id=old_strategy_id,
            old_strategy_name=old_strategy.get("name", "None"),
            new_strategy_id=new_strategy_id,
            new_strategy_name=new_strategy.name,
            user_id=user_id,
        )

        logger.info(
            "position_strategy_changed",
            position_id=position_id,
            old_strategy=old_strategy.get("name"),
            new_strategy=new_strategy.name,
        )

        return True, f"Strategy changed to {new_strategy.name}"

    async def _log_strategy_change(
        self,
        position_id: str,
        old_strategy_id: Optional[str],
        old_strategy_name: str,
        new_strategy_id: str,
        new_strategy_name: str,
        user_id: str,
    ):
        """Log strategy change event."""
        event_data = {
            "position_id": position_id,
            "event_type": "strategy_change",
            "timestamp": datetime.utcnow().isoformat(),
            "details": {
                "old_strategy_id": old_strategy_id,
                "old_strategy_name": old_strategy_name,
                "new_strategy_id": new_strategy_id,
                "new_strategy_name": new_strategy_name,
                "changed_by": user_id,
            }
        }

        await self._client.table("position_events") \
            .insert(event_data) \
            .execute()


def format_preview_markdown(preview: dict, entry_price: Decimal) -> str:
    """Format preview as markdown table."""
    md = f"""
### Preview: {preview['strategy_name']}

Entry Price: ${entry_price:.8f}

| Type | Trigger | Exit % | Price | Status |
|------|---------|--------|-------|--------|
"""
    for level in preview["levels"]:
        status = "✅ Executed" if level["already_executed"] else "⏳ Pending"
        trigger = f"{level['trigger_pct']:+}%" if level["trigger_pct"] is not None else "-"
        price = f"${level['absolute_price']:.8f}" if level["absolute_price"] else "-"

        md += f"| {level['type']} | {trigger} | {level['exit_pct']}% | {price} | {status} |\n"

    return md


async def build_change_strategy_modal() -> gr.Blocks:
    """Build the change strategy modal."""
    modal = ChangeStrategyModal()
    await modal.initialize()

    with gr.Blocks() as change_modal:
        position_id_state = gr.State(None)

        with gr.Column(visible=False) as modal_container:
            gr.Markdown("## Change Exit Strategy")

            current_strategy_text = gr.Markdown()

            strategy_dropdown = gr.Dropdown(
                label="Select New Strategy",
                choices=[],
            )

            preview_content = gr.Markdown()

            with gr.Row():
                cancel_btn = gr.Button("Cancel", variant="secondary")
                confirm_btn = gr.Button("Confirm Change", variant="primary")

            status_msg = gr.Textbox(label="Status", interactive=False)

        # Event handlers
        async def open_modal(position_id: str):
            if not position_id:
                return [gr.update(visible=False), None, "", [], "", ""]

            position = await modal.get_position(position_id)
            if not position:
                return [gr.update(visible=False), None, "Position not found", [], "", ""]

            current_strategy = position.get("exit_strategies") or {}
            current_text = f"**Current Strategy:** {current_strategy.get('name', 'None')}"

            strategies = await modal.get_available_strategies()

            return [
                gr.update(visible=True),
                position_id,
                current_text,
                gr.update(choices=strategies),
                "",
                ""
            ]

        async def on_strategy_select(strategy_id, position_id):
            if not strategy_id or not position_id:
                return ""

            position = await modal.get_position(position_id)
            if not position:
                return "Position not found"

            strategy = await modal.get_strategy(strategy_id)
            if not strategy:
                return "Strategy not found"

            entry_price = Decimal(str(position["entry_price"]))
            executed_exits = position.get("position_exits") or []

            preview = modal.calculate_preview(strategy, entry_price, executed_exits)
            return format_preview_markdown(preview, entry_price)

        async def on_confirm(strategy_id, position_id):
            if not strategy_id or not position_id:
                return "Select a strategy first"

            success, msg = await modal.apply_strategy_change(position_id, strategy_id)
            return msg

        def on_cancel():
            return [gr.update(visible=False), None, "", [], "", ""]

        # Wire up events
        strategy_dropdown.change(
            on_strategy_select,
            [strategy_dropdown, position_id_state],
            [preview_content]
        )

        confirm_btn.click(
            on_confirm,
            [strategy_dropdown, position_id_state],
            [status_msg]
        )

        cancel_btn.click(
            on_cancel,
            [],
            [modal_container, position_id_state, current_strategy_text, strategy_dropdown, preview_content, status_msg]
        )

        # Expose open function
        change_modal.open_modal = open_modal
        change_modal.modal_container = modal_container
        change_modal.position_id_state = position_id_state
        change_modal.current_strategy_text = current_strategy_text
        change_modal.strategy_dropdown = strategy_dropdown
        change_modal.preview_content = preview_content
        change_modal.status_msg = status_msg

    return change_modal
```

### Position Events Table

**migrations/V13__position_events.sql:**
```sql
-- Position events table for strategy changes and other events
CREATE TABLE IF NOT EXISTS position_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    position_id UUID NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,  -- strategy_change, exit_triggered, etc.
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_position_events_position ON position_events(position_id);
CREATE INDEX idx_position_events_type ON position_events(event_type);
CREATE INDEX idx_position_events_time ON position_events(timestamp DESC);
```

## Implementation Tasks

- [x] Create ChangeStrategyModal class
- [x] Implement get_available_strategies()
- [x] Implement calculate_preview()
- [x] Implement apply_strategy_change()
- [x] Create position_events table migration
- [x] Log strategy changes
- [x] Build modal UI
- [x] Add preview on strategy select
- [x] Handle executed exits preservation
- [x] Write tests

## Definition of Done

- [x] Modal opens with current strategy
- [x] Dropdown shows all active strategies
- [x] Preview shows calculated levels
- [x] Confirm changes strategy
- [x] Event is logged
- [x] Executed exits preserved
- [x] Tests passing

## File List

### New Files
- `src/walltrack/ui/components/change_strategy_modal.py` - Modal component
- `migrations/V13__position_events.sql` - Events table

### Modified Files
- `src/walltrack/ui/components/position_details_sidebar.py` - Connect to modal
