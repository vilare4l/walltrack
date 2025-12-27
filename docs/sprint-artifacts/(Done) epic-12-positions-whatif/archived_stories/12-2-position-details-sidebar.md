# Story 12.2: Position Details - Sidebar

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 5
- **Depends on**: Story 12-1 (Positions List)

## User Story

**As a** the operator,
**I want** voir les détails complets d'une position dans le sidebar,
**So that** je comprends le contexte sans quitter la page.

## Acceptance Criteria

### AC 1: Sidebar Opens on Click
**Given** je clique sur [👁️] d'une position
**When** le sidebar s'ouvre
**Then** je vois les détails complets de la position

### AC 2: Active Position Content
**Given** une position ACTIVE
**When** le sidebar s'affiche
**Then** je vois les sections:
- 📊 Performance: Entry price, Current price, P&L, Duration
- 🎯 Stratégie Active: Nom, niveaux TP avec prix, SL, Trailing, "Prochain TP dans: +X%"
- 📈 Source: Wallet source (lien), Signal ID, Score

### AC 3: Closed Position Content
**Given** une position CLÔTURÉE
**When** le sidebar s'affiche
**Then** je vois:
- 📊 Résultat Final: Entry, Exit, P&L, Duration, Exit Type
- 🎯 Stratégie Utilisée: Détails avec ✅/❌ pour niveaux atteints
- 📈 Source: Wallet, Signal ID, Score
- 📊 What-If: Bouton "Ouvrir le Simulateur"

### AC 4: Close Sidebar
**Given** le sidebar est ouvert
**When** je clique ailleurs ou sur X
**Then** le sidebar se ferme

## Technical Specifications

### Position Details Sidebar

**src/walltrack/ui/components/position_details_sidebar.py:**
```python
"""Position details sidebar component."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

import gradio as gr
import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    get_exit_strategy_service,
)

logger = structlog.get_logger(__name__)


class PositionDetailsSidebar:
    """Sidebar component for position details."""

    def __init__(self):
        self._client = None
        self._strategy_service = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def _get_strategy_service(self):
        """Get exit strategy service."""
        if self._strategy_service is None:
            self._strategy_service = await get_exit_strategy_service()
        return self._strategy_service

    async def get_position_details(self, position_id: str) -> Optional[dict]:
        """Get full position details."""
        client = await self._get_client()

        # Handle truncated IDs
        if position_id.endswith("..."):
            position_id = position_id.replace("...", "")

        result = await client.table("positions") \
            .select("""
                *,
                exit_strategies(id, name, rules, max_hold_hours),
                signals(id, score, wallet_address, created_at)
            """) \
            .ilike("id", f"{position_id}%") \
            .single() \
            .execute()

        return result.data

    def render_active_position(self, position: dict) -> str:
        """Render markdown for active position."""
        entry_price = Decimal(str(position["entry_price"]))
        current_price = Decimal(str(position.get("current_price", entry_price)))
        pnl_pct = ((current_price - entry_price) / entry_price) * 100
        pnl_sol = Decimal(str(position["size_sol"])) * (pnl_pct / 100)

        # Duration
        entry_time = datetime.fromisoformat(position["entry_time"].replace("Z", "+00:00"))
        duration = datetime.utcnow() - entry_time.replace(tzinfo=None)
        hours = duration.total_seconds() / 3600

        # Strategy details
        strategy = position.get("exit_strategies") or {}
        strategy_name = strategy.get("name", "None")
        rules = strategy.get("rules", [])

        # Calculate next TP
        next_tp_info = self._calculate_next_tp(rules, pnl_pct)

        # Signal info
        signal = position.get("signals") or {}
        wallet = signal.get("wallet_address", "Unknown")[:16]
        signal_score = signal.get("score", 0)

        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

        md = f"""
## 📊 Performance

| Metric | Value |
|--------|-------|
| Entry Price | ${entry_price:.8f} |
| Current Price | ${current_price:.8f} |
| P&L | {pnl_emoji} {pnl_pct:+.2f}% ({pnl_sol:+.4f} SOL) |
| Size | {position['size_sol']:.4f} SOL |
| Duration | {hours:.1f} hours |

---

## 🎯 Stratégie Active: {strategy_name}

"""
        if rules:
            md += "| Type | Trigger | Exit % | Status |\n"
            md += "|------|---------|--------|--------|\n"

            for rule in rules:
                rule_type = rule.get("rule_type", "?")
                trigger = rule.get("trigger_pct")
                exit_pct = rule.get("exit_pct", 100)

                if trigger is not None:
                    status = "✅" if pnl_pct >= float(trigger) else "⏳"
                    md += f"| {rule_type} | {trigger:+}% | {exit_pct}% | {status} |\n"
                else:
                    md += f"| {rule_type} | - | {exit_pct}% | ⏳ |\n"

            if next_tp_info:
                md += f"\n**Prochain TP dans:** {next_tp_info}\n"

        md += f"""
---

## 📈 Source

| | |
|---|---|
| Wallet | `{wallet}...` |
| Signal Score | {signal_score:.2f} |
| Signal Date | {signal.get('created_at', 'N/A')[:16]} |
"""

        return md

    def render_closed_position(self, position: dict) -> str:
        """Render markdown for closed position."""
        entry_price = Decimal(str(position["entry_price"]))
        exit_price = Decimal(str(position.get("exit_price", entry_price)))
        pnl_pct = float(position.get("pnl_pct", 0))
        pnl_sol = float(position.get("pnl_sol", 0))

        # Duration
        entry_time = datetime.fromisoformat(position["entry_time"].replace("Z", "+00:00"))
        exit_time = datetime.fromisoformat(position["exit_time"].replace("Z", "+00:00")) if position.get("exit_time") else entry_time
        duration = exit_time - entry_time
        hours = duration.total_seconds() / 3600

        exit_type = position.get("exit_type", "unknown")
        exit_emoji = {
            "take_profit": "🎯",
            "stop_loss": "🛑",
            "trailing_stop": "📉",
            "time_based": "⏰",
            "manual": "✋",
            "stagnation": "😴",
        }.get(exit_type, "❓")

        # Strategy details
        strategy = position.get("exit_strategies") or {}
        strategy_name = strategy.get("name", "None")
        rules = strategy.get("rules", [])

        # Signal info
        signal = position.get("signals") or {}
        wallet = signal.get("wallet_address", "Unknown")[:16]
        signal_score = signal.get("score", 0)

        pnl_emoji = "🟢" if pnl_pct >= 0 else "🔴"

        md = f"""
## 📊 Résultat Final

| Metric | Value |
|--------|-------|
| Entry Price | ${entry_price:.8f} |
| Exit Price | ${exit_price:.8f} |
| P&L | {pnl_emoji} {pnl_pct:+.2f}% ({pnl_sol:+.4f} SOL) |
| Exit Type | {exit_emoji} {exit_type} |
| Duration | {hours:.1f} hours |

---

## 🎯 Stratégie Utilisée: {strategy_name}

"""
        if rules:
            md += "| Type | Trigger | Exit % | Reached |\n"
            md += "|------|---------|--------|----------|\n"

            # Determine what was reached based on final pnl
            max_reached_pnl = pnl_pct

            for rule in rules:
                rule_type = rule.get("rule_type", "?")
                trigger = rule.get("trigger_pct")
                exit_pct = rule.get("exit_pct", 100)

                if trigger is not None:
                    # Check if this level was reached
                    reached = "✅" if max_reached_pnl >= float(trigger) else "❌"
                    md += f"| {rule_type} | {trigger:+}% | {exit_pct}% | {reached} |\n"
                else:
                    md += f"| {rule_type} | - | {exit_pct}% | - |\n"

        md += f"""
---

## 📈 Source

| | |
|---|---|
| Wallet | `{wallet}...` |
| Signal Score | {signal_score:.2f} |
| Signal Date | {signal.get('created_at', 'N/A')[:16]} |

---

## 📊 What-If Analysis

*Click the button below to simulate alternative strategies*
"""

        return md

    def _calculate_next_tp(self, rules: list, current_pnl_pct: float) -> Optional[str]:
        """Calculate next take profit level."""
        tp_rules = [r for r in rules if r.get("rule_type") == "take_profit"]
        tp_rules.sort(key=lambda r: r.get("trigger_pct", 0))

        for rule in tp_rules:
            trigger = rule.get("trigger_pct", 0)
            if trigger > current_pnl_pct:
                diff = trigger - current_pnl_pct
                return f"+{diff:.1f}% to TP ({trigger}%)"

        return None


async def build_position_details_sidebar() -> gr.Blocks:
    """Build the position details sidebar."""
    sidebar = PositionDetailsSidebar()

    with gr.Blocks() as details_sidebar:
        position_id_state = gr.State(None)

        with gr.Column(visible=False) as sidebar_container:
            gr.Markdown("## Position Details")

            close_btn = gr.Button("✕ Close", size="sm")

            details_content = gr.Markdown()

            with gr.Row(visible=False) as whatif_row:
                whatif_btn = gr.Button("📊 Open What-If Simulator", variant="primary")

            with gr.Row(visible=False) as strategy_row:
                change_strategy_btn = gr.Button("⚙️ Change Strategy", variant="secondary")

        # External trigger to open sidebar
        async def open_sidebar(position_id: str):
            if not position_id:
                return [gr.update(visible=False), "", gr.update(visible=False), gr.update(visible=False), None]

            position = await sidebar.get_position_details(position_id)
            if not position:
                return [gr.update(visible=False), "Position not found", gr.update(visible=False), gr.update(visible=False), None]

            is_active = position.get("status") == "open"

            if is_active:
                content = sidebar.render_active_position(position)
                return [
                    gr.update(visible=True),
                    content,
                    gr.update(visible=False),  # whatif hidden for active
                    gr.update(visible=True),   # strategy visible for active
                    position["id"]
                ]
            else:
                content = sidebar.render_closed_position(position)
                return [
                    gr.update(visible=True),
                    content,
                    gr.update(visible=True),   # whatif visible for closed
                    gr.update(visible=False),  # strategy hidden for closed
                    position["id"]
                ]

        def close_sidebar_handler():
            return [gr.update(visible=False), "", gr.update(visible=False), gr.update(visible=False), None]

        close_btn.click(
            close_sidebar_handler,
            [],
            [sidebar_container, details_content, whatif_row, strategy_row, position_id_state]
        )

        # Expose open function
        details_sidebar.open_sidebar = open_sidebar
        details_sidebar.sidebar_container = sidebar_container
        details_sidebar.details_content = details_content
        details_sidebar.whatif_row = whatif_row
        details_sidebar.strategy_row = strategy_row
        details_sidebar.position_id_state = position_id_state

    return details_sidebar
```

## Implementation Tasks

- [x] Create PositionDetailsSidebar class
- [x] Implement get_position_details() with joins
- [x] Implement render_active_position()
- [x] Implement render_closed_position()
- [x] Calculate next TP level
- [x] Show reached/not reached levels
- [x] Build sidebar UI component
- [x] Add open/close functionality
- [x] Connect What-If and Strategy buttons
- [x] Write tests

## Definition of Done

- [x] Sidebar opens with position details
- [x] Active positions show correct content
- [x] Closed positions show correct content
- [x] Strategy levels show status
- [x] What-If button visible for closed
- [x] Strategy button visible for active
- [x] Close works correctly

## File List

### New Files
- `src/walltrack/ui/components/position_details_sidebar.py` - Sidebar component

### Modified Files
- `src/walltrack/ui/components/positions_list.py` - Connect to sidebar
