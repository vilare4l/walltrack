# Story 12.1: Positions List - Refonte avec Actions

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 5
- **Depends on**: Epic 10 (Basic positions), Epic 11-7 (Exit Strategy CRUD)

## User Story

**As a** the operator,
**I want** une liste de positions enrichie avec actions contextuelles,
**So that** je peux voir l'essentiel et agir rapidement.

## Acceptance Criteria

### AC 1: Grouped Position Display
**Given** je suis sur Home ou Explorer
**When** je vois la section Positions
**Then** je vois deux groupes:
- **Actives**: positions en cours
- **Clôturées récentes**: 10 dernières

### AC 2: Active Position Display
**Given** une position active
**When** je la vois dans la liste
**Then** je vois: Token, Entry, Current, P&L%, Stratégie, Actions
**And** les actions sont: [👁️ Détails] [⚙️ Stratégie]

### AC 3: Closed Position Display
**Given** une position clôturée
**When** je la vois dans la liste
**Then** je vois: Token, Entry, Exit, P&L%, Stratégie, Exit Type, Actions
**And** les actions sont: [👁️ Détails] [📊 What-If]

### AC 4: P&L Color Coding
**Given** le P&L est positif
**Then** il est affiché en vert
**Given** le P&L est négatif
**Then** il est affiché en rouge

### AC 5: Real-time Updates
**Given** une position active est affichée
**When** le prix change
**Then** Current et P&L% se mettent à jour automatiquement

## Technical Specifications

### Positions List Component

**src/walltrack/ui/components/positions_list.py:**
```python
"""Enhanced positions list with actions."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Callable

import gradio as gr
import structlog

logger = structlog.get_logger(__name__)


class PositionsListComponent:
    """Enhanced positions list with contextual actions."""

    def __init__(
        self,
        on_view_details: Optional[Callable[[str], None]] = None,
        on_change_strategy: Optional[Callable[[str], None]] = None,
        on_whatif: Optional[Callable[[str], None]] = None,
    ):
        self.on_view_details = on_view_details
        self.on_change_strategy = on_change_strategy
        self.on_whatif = on_whatif
        self._client = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def get_active_positions(self) -> list[dict]:
        """Get all active positions."""
        client = await self._get_client()

        result = await client.table("positions") \
            .select("""
                id, token_address, token_symbol, entry_price, current_price,
                size_sol, pnl_pct, pnl_sol, entry_time, status,
                exit_strategy_id,
                exit_strategies(id, name)
            """) \
            .eq("status", "open") \
            .order("entry_time", desc=True) \
            .execute()

        return result.data or []

    async def get_closed_positions(self, limit: int = 10) -> list[dict]:
        """Get recently closed positions."""
        client = await self._get_client()

        result = await client.table("positions") \
            .select("""
                id, token_address, token_symbol, entry_price, exit_price,
                size_sol, pnl_pct, pnl_sol, entry_time, exit_time, status,
                exit_type, exit_strategy_id,
                exit_strategies(id, name)
            """) \
            .eq("status", "closed") \
            .order("exit_time", desc=True) \
            .limit(limit) \
            .execute()

        return result.data or []

    def format_pnl(self, pnl_pct: float) -> str:
        """Format P&L with color indicator."""
        if pnl_pct > 0:
            return f"🟢 +{pnl_pct:.2f}%"
        elif pnl_pct < 0:
            return f"🔴 {pnl_pct:.2f}%"
        else:
            return f"⚪ {pnl_pct:.2f}%"

    def format_active_table(self, positions: list[dict]) -> list[list]:
        """Format active positions for display."""
        rows = []
        for p in positions:
            strategy_name = p.get("exit_strategies", {}).get("name", "None") if p.get("exit_strategies") else "None"

            rows.append([
                p["id"][:8] + "...",  # ID (truncated)
                p.get("token_symbol") or p["token_address"][:8] + "...",  # Token
                f"${p['entry_price']:.8f}",  # Entry
                f"${p.get('current_price', p['entry_price']):.8f}",  # Current
                self.format_pnl(float(p.get("pnl_pct", 0))),  # P&L
                f"{p['size_sol']:.4f} SOL",  # Size
                strategy_name,  # Strategy
                self._format_duration(p.get("entry_time")),  # Duration
            ])

        return rows

    def format_closed_table(self, positions: list[dict]) -> list[list]:
        """Format closed positions for display."""
        rows = []
        for p in positions:
            strategy_name = p.get("exit_strategies", {}).get("name", "None") if p.get("exit_strategies") else "None"
            exit_type = p.get("exit_type", "unknown")

            # Format exit type with emoji
            exit_emoji = {
                "take_profit": "🎯",
                "stop_loss": "🛑",
                "trailing_stop": "📉",
                "time_based": "⏰",
                "manual": "✋",
                "stagnation": "😴",
            }.get(exit_type, "❓")

            rows.append([
                p["id"][:8] + "...",  # ID
                p.get("token_symbol") or p["token_address"][:8] + "...",  # Token
                f"${p['entry_price']:.8f}",  # Entry
                f"${p.get('exit_price', 0):.8f}",  # Exit
                self.format_pnl(float(p.get("pnl_pct", 0))),  # P&L
                f"{exit_emoji} {exit_type}",  # Exit Type
                strategy_name,  # Strategy
                p.get("exit_time", "")[:10] if p.get("exit_time") else "",  # Date
            ])

        return rows

    def _format_duration(self, entry_time: Optional[str]) -> str:
        """Format duration since entry."""
        if not entry_time:
            return "-"

        entry = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
        now = datetime.now(entry.tzinfo) if entry.tzinfo else datetime.utcnow()
        delta = now - entry

        hours = delta.total_seconds() / 3600

        if hours < 1:
            return f"{int(delta.total_seconds() / 60)}m"
        elif hours < 24:
            return f"{hours:.1f}h"
        else:
            return f"{hours / 24:.1f}d"


async def build_positions_list_component(
    on_view_details: Optional[Callable] = None,
    on_change_strategy: Optional[Callable] = None,
    on_whatif: Optional[Callable] = None,
) -> gr.Blocks:
    """Build the positions list UI component."""
    component = PositionsListComponent(
        on_view_details=on_view_details,
        on_change_strategy=on_change_strategy,
        on_whatif=on_whatif,
    )

    with gr.Blocks() as positions_list:
        gr.Markdown("## Positions")

        with gr.Tabs():
            # Active Positions Tab
            with gr.Tab("Active"):
                active_table = gr.Dataframe(
                    headers=["ID", "Token", "Entry", "Current", "P&L", "Size", "Strategy", "Duration"],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                    label="Active Positions",
                    interactive=False,
                )

                with gr.Row():
                    view_details_btn = gr.Button("👁️ Details", size="sm")
                    change_strategy_btn = gr.Button("⚙️ Strategy", size="sm")
                    refresh_active_btn = gr.Button("🔄 Refresh", size="sm")

                selected_active_id = gr.State(None)

            # Closed Positions Tab
            with gr.Tab("Closed (Recent)"):
                closed_table = gr.Dataframe(
                    headers=["ID", "Token", "Entry", "Exit", "P&L", "Exit Type", "Strategy", "Date"],
                    datatype=["str", "str", "str", "str", "str", "str", "str", "str"],
                    label="Closed Positions",
                    interactive=False,
                )

                with gr.Row():
                    view_closed_details_btn = gr.Button("👁️ Details", size="sm")
                    whatif_btn = gr.Button("📊 What-If", size="sm")
                    refresh_closed_btn = gr.Button("🔄 Refresh", size="sm")

                selected_closed_id = gr.State(None)

        # Status message
        status_msg = gr.Textbox(label="Status", interactive=False, visible=False)

        # Event handlers
        async def load_active():
            positions = await component.get_active_positions()
            return component.format_active_table(positions)

        async def load_closed():
            positions = await component.get_closed_positions()
            return component.format_closed_table(positions)

        def on_active_select(evt: gr.SelectData, table_data):
            if evt.index[0] < len(table_data):
                return table_data[evt.index[0]][0]  # Return ID
            return None

        def on_closed_select(evt: gr.SelectData, table_data):
            if evt.index[0] < len(table_data):
                return table_data[evt.index[0]][0]  # Return ID
            return None

        async def handle_view_details(position_id, is_active: bool = True):
            if not position_id:
                return "Select a position first"
            if on_view_details:
                await on_view_details(position_id.replace("...", ""))
            return f"Viewing details for {position_id}"

        async def handle_change_strategy(position_id):
            if not position_id:
                return "Select a position first"
            if on_change_strategy:
                await on_change_strategy(position_id.replace("...", ""))
            return f"Opening strategy selector for {position_id}"

        async def handle_whatif(position_id):
            if not position_id:
                return "Select a position first"
            if on_whatif:
                await on_whatif(position_id.replace("...", ""))
            return f"Opening What-If simulator for {position_id}"

        # Wire up events
        active_table.select(on_active_select, [active_table], [selected_active_id])
        closed_table.select(on_closed_select, [closed_table], [selected_closed_id])

        refresh_active_btn.click(load_active, [], [active_table])
        refresh_closed_btn.click(load_closed, [], [closed_table])

        view_details_btn.click(
            lambda pid: handle_view_details(pid, True),
            [selected_active_id],
            [status_msg]
        )
        view_closed_details_btn.click(
            lambda pid: handle_view_details(pid, False),
            [selected_closed_id],
            [status_msg]
        )
        change_strategy_btn.click(handle_change_strategy, [selected_active_id], [status_msg])
        whatif_btn.click(handle_whatif, [selected_closed_id], [status_msg])

        # Initial load
        positions_list.load(load_active, [], [active_table])
        positions_list.load(load_closed, [], [closed_table])

    return positions_list
```

### Integration with Main Dashboard

**src/walltrack/ui/pages/home_page.py (update):**
```python
"""Home page with positions section."""

import gradio as gr

from walltrack.ui.components.positions_list import build_positions_list_component


async def build_home_page() -> gr.Blocks:
    """Build home page with positions."""

    with gr.Blocks() as home:
        gr.Markdown("# WallTrack Dashboard")

        with gr.Row():
            # Stats cards
            with gr.Column(scale=1):
                gr.Markdown("### Quick Stats")
                # ... existing stats

            with gr.Column(scale=3):
                # Positions section
                positions = await build_positions_list_component(
                    on_view_details=open_details_sidebar,
                    on_change_strategy=open_strategy_modal,
                    on_whatif=open_whatif_modal,
                )

    return home
```

## Implementation Tasks

- [ ] Create PositionsListComponent class
- [ ] Implement get_active_positions() with strategy join
- [ ] Implement get_closed_positions() with exit details
- [ ] Format tables with P&L coloring
- [ ] Add action buttons (Details, Strategy, What-If)
- [ ] Implement row selection handling
- [ ] Add refresh functionality
- [ ] Connect to sidebar/modal callbacks
- [ ] Write tests

## Definition of Done

- [ ] Active positions display with all fields
- [ ] Closed positions display with exit type
- [ ] P&L colored correctly
- [ ] Actions trigger correct callbacks
- [ ] Selection state maintained
- [ ] Refresh works

## File List

### New Files
- `src/walltrack/ui/components/positions_list.py` - Main component

### Modified Files
- `src/walltrack/ui/pages/home_page.py` - Integrate positions list
