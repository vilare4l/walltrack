# Story 4.11: Dashboard - Exit Strategy Management

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: Medium
- **FR**: FR49, FR50, FR51

## User Story

**As an** operator,
**I want** to manage exit strategies in the dashboard,
**So that** I can create, modify, and assign strategies.

## Acceptance Criteria

### AC 1: Strategy List
**Given** Exit Strategies panel in dashboard
**When** operator views strategies
**Then** all available strategies are listed (presets + custom)
**And** each shows: name, TP levels, stop-loss, trailing config, moonbag

### AC 2: Create Custom Strategy
**Given** operator creates custom strategy
**When** form is submitted
**Then** strategy is validated (all required fields, valid ranges)
**And** strategy is saved to Supabase
**And** strategy becomes available for assignment

### AC 3: Edit Strategy
**Given** operator edits existing custom strategy
**When** changes are saved
**Then** existing positions with this strategy are NOT affected
**And** new positions will use updated strategy
**And** operator is warned about this behavior

### AC 4: Position Strategy Change
**Given** an open position
**When** operator changes its exit strategy
**Then** new strategy is applied
**And** stop-loss and TP levels are recalculated
**And** change is logged

### AC 5: Default Assignment Config
**Given** default strategy assignment panel
**When** operator configures score-to-strategy mapping
**Then** mapping is saved
**And** future positions use new mapping

## Technical Notes

- FR49: Define custom exit strategies
- FR50: Assign default exit strategy and score-based overrides
- FR51: View and modify exit strategy for active positions
- Implement in `src/walltrack/ui/components/exit_strategies.py`

## Implementation Tasks

- [ ] Create `src/walltrack/ui/components/exit_strategies.py`
- [ ] Implement strategy list view
- [ ] Create strategy creation form with validation
- [ ] Implement strategy editing
- [ ] Add position strategy change functionality
- [ ] Create score-to-strategy mapping config panel

## Definition of Done

- [ ] Strategy list displays all strategies
- [ ] Custom strategies can be created
- [ ] Strategies can be edited safely
- [ ] Position strategies can be changed
- [ ] Score mapping configurable

---

## Technical Specifications

### Gradio Dashboard Component

```python
# src/walltrack/ui/components/exit_strategies.py
"""Exit strategy management dashboard component."""

import gradio as gr
import pandas as pd
from decimal import Decimal
from uuid import uuid4

from walltrack.core.execution.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    TimeRulesConfig,
    MoonbagConfig,
    PRESET_STRATEGIES,
)
from walltrack.data.supabase.repositories.strategy_repo import get_strategy_repo
from walltrack.core.execution.strategy_assigner import get_strategy_assigner


async def load_all_strategies() -> pd.DataFrame:
    """Load all strategies (presets + custom)."""
    repo = await get_strategy_repo()
    custom_strategies = await repo.get_all()

    # Combine presets and custom
    all_strategies = list(PRESET_STRATEGIES.values()) + custom_strategies

    data = []
    for s in all_strategies:
        tp_summary = ", ".join([
            f"{int(tp.trigger_multiplier)}x→{tp.sell_percentage}%"
            for tp in s.take_profit_levels
        ])

        trailing_str = (
            f"Active@{s.trailing_stop.activation_multiplier}x ({s.trailing_stop.distance_percentage}%)"
            if s.trailing_stop.enabled else "Off"
        )

        moonbag_str = (
            f"{s.moonbag.percentage}% (SL:{s.moonbag.stop_loss*100:.0f}%)"
            if s.moonbag and s.moonbag.percentage > 0 else "None"
        )

        is_preset = s.id.startswith("preset-")

        data.append({
            "id": s.id,
            "Name": s.name,
            "Stop Loss": f"{s.stop_loss_percentage}%",
            "Take Profits": tp_summary,
            "Trailing": trailing_str,
            "Moonbag": moonbag_str,
            "Type": "Preset" if is_preset else "Custom",
        })

    return pd.DataFrame(data)


async def load_strategy_detail(strategy_id: str) -> dict | None:
    """Load strategy detail for editing."""
    if not strategy_id:
        return None

    # Check presets first
    if strategy_id in PRESET_STRATEGIES:
        return PRESET_STRATEGIES[strategy_id].model_dump()

    # Then custom
    repo = await get_strategy_repo()
    strategy = await repo.get_by_id(strategy_id)

    if strategy:
        return strategy.model_dump()

    return None


async def save_strategy(
    strategy_id: str | None,
    name: str,
    stop_loss_pct: float,
    # TP Level 1
    tp1_mult: float,
    tp1_pct: int,
    # TP Level 2
    tp2_mult: float,
    tp2_pct: int,
    # TP Level 3 (optional)
    tp3_mult: float,
    tp3_pct: int,
    # Trailing stop
    trailing_enabled: bool,
    trailing_activation: float,
    trailing_distance: float,
    # Time rules
    max_hold_hours: int,
    stagnation_enabled: bool,
    stagnation_hours: int,
    stagnation_threshold: float,
    # Moonbag
    moonbag_pct: int,
    moonbag_sl: float,
) -> str:
    """Save a custom strategy."""
    repo = await get_strategy_repo()

    # Build take profit levels
    tp_levels = []
    if tp1_mult > 0 and tp1_pct > 0:
        tp_levels.append(TakeProfitLevel(
            trigger_multiplier=Decimal(str(tp1_mult)),
            sell_percentage=tp1_pct,
        ))
    if tp2_mult > 0 and tp2_pct > 0:
        tp_levels.append(TakeProfitLevel(
            trigger_multiplier=Decimal(str(tp2_mult)),
            sell_percentage=tp2_pct,
        ))
    if tp3_mult > 0 and tp3_pct > 0:
        tp_levels.append(TakeProfitLevel(
            trigger_multiplier=Decimal(str(tp3_mult)),
            sell_percentage=tp3_pct,
        ))

    strategy = ExitStrategy(
        id=strategy_id or f"custom-{uuid4().hex[:8]}",
        name=name,
        stop_loss_percentage=Decimal(str(stop_loss_pct)),
        take_profit_levels=tp_levels,
        trailing_stop=TrailingStopConfig(
            enabled=trailing_enabled,
            activation_multiplier=Decimal(str(trailing_activation)),
            distance_percentage=Decimal(str(trailing_distance)),
        ),
        time_rules=TimeRulesConfig(
            max_hold_hours=max_hold_hours if max_hold_hours > 0 else None,
            stagnation_exit_enabled=stagnation_enabled,
            stagnation_hours=stagnation_hours,
            stagnation_threshold_percentage=Decimal(str(stagnation_threshold)),
        ) if max_hold_hours > 0 or stagnation_enabled else None,
        moonbag=MoonbagConfig(
            percentage=moonbag_pct,
            stop_loss=Decimal(str(moonbag_sl)),
        ) if moonbag_pct > 0 else None,
    )

    if strategy_id:
        await repo.update(strategy)
        return f"✓ Strategy '{name}' updated"
    else:
        await repo.create(strategy)
        return f"✓ Strategy '{name}' created"


async def delete_strategy(strategy_id: str) -> str:
    """Delete a custom strategy."""
    if strategy_id.startswith("preset-"):
        return "⚠ Cannot delete preset strategies"

    repo = await get_strategy_repo()
    await repo.delete(strategy_id)

    return f"✓ Strategy deleted"


async def change_position_strategy(
    position_id: str,
    new_strategy_id: str,
    reason: str,
) -> str:
    """Change strategy for an open position."""
    from walltrack.core.execution.position_manager import get_position_manager

    if not position_id or not new_strategy_id:
        return "⚠ Select a position and strategy"

    manager = await get_position_manager()

    try:
        await manager.change_position_strategy(
            position_id=position_id,
            new_strategy_id=new_strategy_id,
            operator="dashboard",
            reason=reason or "Manual change from dashboard",
        )
        return f"✓ Strategy changed to {new_strategy_id}"
    except ValueError as e:
        return f"⚠ Error: {e}"


def format_strategy_detail(detail: dict | None) -> str:
    """Format strategy detail for display."""
    if not detail:
        return "Select a strategy to view details"

    lines = [
        f"## {detail['name']}",
        f"**ID:** `{detail['id']}`",
        "",
        "### Stop Loss",
        f"- **Percentage:** {detail['stop_loss_percentage']}%",
        "",
        "### Take Profit Levels",
    ]

    for i, tp in enumerate(detail.get('take_profit_levels', [])):
        lines.append(f"{i+1}. **{tp['trigger_multiplier']}x** → Sell {tp['sell_percentage']}%")

    lines.extend(["", "### Trailing Stop"])
    ts = detail.get('trailing_stop', {})
    if ts.get('enabled'):
        lines.append(f"- **Activation:** {ts['activation_multiplier']}x")
        lines.append(f"- **Distance:** {ts['distance_percentage']}%")
    else:
        lines.append("- Disabled")

    if detail.get('time_rules'):
        tr = detail['time_rules']
        lines.extend(["", "### Time Rules"])
        if tr.get('max_hold_hours'):
            lines.append(f"- **Max Hold:** {tr['max_hold_hours']} hours")
        if tr.get('stagnation_exit_enabled'):
            lines.append(f"- **Stagnation:** {tr['stagnation_hours']}h window, {tr['stagnation_threshold_percentage']}% threshold")

    if detail.get('moonbag'):
        mb = detail['moonbag']
        lines.extend(["", "### Moonbag"])
        lines.append(f"- **Percentage:** {mb['percentage']}%")
        lines.append(f"- **Stop Loss:** {float(mb['stop_loss'])*100:.0f}%")

    return "\n".join(lines)


def create_exit_strategies_panel() -> gr.Blocks:
    """Create the exit strategy management panel."""

    with gr.Blocks() as panel:
        gr.Markdown("# Exit Strategy Management")

        with gr.Tabs():
            # Strategy List Tab
            with gr.Tab("All Strategies"):
                refresh_btn = gr.Button("🔄 Refresh", size="sm")

                strategies_table = gr.Dataframe(
                    label="Available Strategies",
                    headers=["Name", "Stop Loss", "Take Profits", "Trailing", "Moonbag", "Type"],
                    interactive=False,
                )

                gr.Markdown("---")

                with gr.Row():
                    strategy_id_input = gr.Textbox(
                        label="Strategy ID",
                        placeholder="Select from table",
                    )
                    load_btn = gr.Button("Load Detail")

                strategy_detail = gr.Markdown("Select a strategy to view details")

                refresh_btn.click(
                    fn=load_all_strategies,
                    outputs=strategies_table,
                )

                load_btn.click(
                    fn=lambda sid: format_strategy_detail(load_strategy_detail(sid)),
                    inputs=strategy_id_input,
                    outputs=strategy_detail,
                )

            # Create/Edit Strategy Tab
            with gr.Tab("Create/Edit Strategy"):
                gr.Markdown("### Strategy Details")

                with gr.Row():
                    edit_strategy_id = gr.Textbox(
                        label="Strategy ID (leave empty for new)",
                        placeholder="custom-xxx or empty",
                    )
                    strategy_name = gr.Textbox(
                        label="Name",
                        placeholder="My Custom Strategy",
                    )

                with gr.Row():
                    stop_loss_pct = gr.Number(
                        label="Stop Loss %",
                        value=30,
                        minimum=5,
                        maximum=90,
                    )

                gr.Markdown("### Take Profit Levels")

                with gr.Row():
                    gr.Markdown("**Level 1**")
                    tp1_mult = gr.Number(label="Multiplier", value=2.0, minimum=1.1)
                    tp1_pct = gr.Number(label="Sell %", value=33, minimum=0, maximum=100)

                with gr.Row():
                    gr.Markdown("**Level 2**")
                    tp2_mult = gr.Number(label="Multiplier", value=3.0, minimum=1.1)
                    tp2_pct = gr.Number(label="Sell %", value=50, minimum=0, maximum=100)

                with gr.Row():
                    gr.Markdown("**Level 3 (optional)**")
                    tp3_mult = gr.Number(label="Multiplier", value=0, minimum=0)
                    tp3_pct = gr.Number(label="Sell %", value=0, minimum=0, maximum=100)

                gr.Markdown("### Trailing Stop")

                with gr.Row():
                    trailing_enabled = gr.Checkbox(label="Enable", value=True)
                    trailing_activation = gr.Number(
                        label="Activation Multiplier",
                        value=2.0,
                        minimum=1.1,
                    )
                    trailing_distance = gr.Number(
                        label="Distance %",
                        value=30,
                        minimum=5,
                        maximum=50,
                    )

                gr.Markdown("### Time Rules")

                with gr.Row():
                    max_hold_hours = gr.Number(
                        label="Max Hold Hours (0=disabled)",
                        value=0,
                        minimum=0,
                    )
                    stagnation_enabled = gr.Checkbox(label="Stagnation Exit", value=False)
                    stagnation_hours = gr.Number(
                        label="Stagnation Window (hours)",
                        value=6,
                        minimum=1,
                    )
                    stagnation_threshold = gr.Number(
                        label="Movement Threshold %",
                        value=5,
                        minimum=1,
                    )

                gr.Markdown("### Moonbag")

                with gr.Row():
                    moonbag_pct = gr.Number(
                        label="Keep % (0=disabled)",
                        value=0,
                        minimum=0,
                        maximum=50,
                    )
                    moonbag_sl = gr.Number(
                        label="Moonbag Stop Loss (0-1)",
                        value=0.3,
                        minimum=0,
                        maximum=1,
                    )

                with gr.Row():
                    save_btn = gr.Button("Save Strategy", variant="primary")
                    delete_btn = gr.Button("Delete Strategy", variant="stop")

                save_status = gr.Textbox(label="Status", interactive=False)

                save_btn.click(
                    fn=save_strategy,
                    inputs=[
                        edit_strategy_id, strategy_name, stop_loss_pct,
                        tp1_mult, tp1_pct, tp2_mult, tp2_pct, tp3_mult, tp3_pct,
                        trailing_enabled, trailing_activation, trailing_distance,
                        max_hold_hours, stagnation_enabled, stagnation_hours, stagnation_threshold,
                        moonbag_pct, moonbag_sl,
                    ],
                    outputs=save_status,
                )

                delete_btn.click(
                    fn=delete_strategy,
                    inputs=edit_strategy_id,
                    outputs=save_status,
                )

            # Change Position Strategy Tab
            with gr.Tab("Change Position Strategy"):
                gr.Markdown("""
                ### Change Exit Strategy for Active Position

                **Warning:** Changing strategy will recalculate all stop-loss and take-profit levels.
                Existing positions using this strategy are NOT affected when you edit a strategy.
                """)

                with gr.Row():
                    pos_id_input = gr.Textbox(
                        label="Position ID",
                        placeholder="Enter position ID",
                    )
                    new_strategy_dropdown = gr.Dropdown(
                        label="New Strategy",
                        choices=[
                            "preset-conservative",
                            "preset-balanced",
                            "preset-moonbag-aggressive",
                            "preset-quick-flip",
                            "preset-diamond-hands",
                        ],
                    )

                change_reason = gr.Textbox(
                    label="Reason (optional)",
                    placeholder="Why are you changing the strategy?",
                )

                change_btn = gr.Button("Change Strategy", variant="primary")
                change_status = gr.Textbox(label="Status", interactive=False)

                change_btn.click(
                    fn=change_position_strategy,
                    inputs=[pos_id_input, new_strategy_dropdown, change_reason],
                    outputs=change_status,
                )

            # Score Mapping Tab (references 4-8)
            with gr.Tab("Score-Based Assignment"):
                gr.Markdown("""
                ### Automatic Strategy Assignment

                Configure which strategy is automatically assigned based on signal conviction score.
                """)

                from walltrack.ui.components.strategy_mapping import create_strategy_mapping_panel
                mapping_panel = create_strategy_mapping_panel()

        # Auto-load strategies on display
        panel.load(fn=load_all_strategies, outputs=strategies_table)

    return panel
```

### Strategy Repository

```python
# src/walltrack/data/supabase/repositories/strategy_repo.py
"""Exit strategy repository."""

import structlog
from typing import Optional

from walltrack.data.supabase.client import get_supabase_client
from walltrack.core.execution.models.exit_strategy import ExitStrategy

logger = structlog.get_logger(__name__)


class StrategyRepository:
    """Repository for custom exit strategies."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    async def create(self, strategy: ExitStrategy) -> ExitStrategy:
        """Create a new custom strategy."""
        client = await self._get_client()

        data = strategy.model_dump(mode="json")

        await client.table("exit_strategies").insert(data).execute()

        logger.info(
            "strategy_created",
            strategy_id=strategy.id,
            name=strategy.name,
        )

        return strategy

    async def get_by_id(self, strategy_id: str) -> Optional[ExitStrategy]:
        """Get strategy by ID."""
        client = await self._get_client()

        result = await client.table("exit_strategies").select("*").eq("id", strategy_id).execute()

        if not result.data:
            return None

        return ExitStrategy.model_validate(result.data[0])

    async def get_all(self) -> list[ExitStrategy]:
        """Get all custom strategies."""
        client = await self._get_client()

        result = await client.table("exit_strategies").select("*").order("name").execute()

        return [ExitStrategy.model_validate(row) for row in result.data]

    async def update(self, strategy: ExitStrategy) -> ExitStrategy:
        """Update an existing strategy."""
        client = await self._get_client()

        data = strategy.model_dump(mode="json")

        await client.table("exit_strategies").update(data).eq("id", strategy.id).execute()

        logger.info(
            "strategy_updated",
            strategy_id=strategy.id,
            name=strategy.name,
        )

        return strategy

    async def delete(self, strategy_id: str) -> None:
        """Delete a custom strategy."""
        client = await self._get_client()

        await client.table("exit_strategies").delete().eq("id", strategy_id).execute()

        logger.info(
            "strategy_deleted",
            strategy_id=strategy_id,
        )


# Singleton
_strategy_repo: StrategyRepository | None = None


async def get_strategy_repo() -> StrategyRepository:
    """Get strategy repository singleton."""
    global _strategy_repo
    if _strategy_repo is None:
        _strategy_repo = StrategyRepository()
    return _strategy_repo
```

### Database Schema

```sql
-- Exit strategies table
CREATE TABLE IF NOT EXISTS exit_strategies (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,

    -- Stop loss
    stop_loss_percentage DECIMAL(5, 2) NOT NULL,

    -- Take profit levels (JSONB array)
    take_profit_levels JSONB NOT NULL DEFAULT '[]',

    -- Trailing stop config
    trailing_stop JSONB NOT NULL DEFAULT '{"enabled": false}',

    -- Time rules config
    time_rules JSONB,

    -- Moonbag config
    moonbag JSONB,

    -- Metadata
    is_preset BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert preset strategies
INSERT INTO exit_strategies (id, name, stop_loss_percentage, take_profit_levels, trailing_stop, moonbag, is_preset)
VALUES
    ('preset-conservative', 'Conservative', 20, '[{"trigger_multiplier": 1.5, "sell_percentage": 50}, {"trigger_multiplier": 2.0, "sell_percentage": 50}]', '{"enabled": false}', null, true),
    ('preset-balanced', 'Balanced', 30, '[{"trigger_multiplier": 2.0, "sell_percentage": 33}, {"trigger_multiplier": 3.0, "sell_percentage": 50}]', '{"enabled": true, "activation_multiplier": 2.0, "distance_percentage": 30}', '{"percentage": 34, "stop_loss": 0.3}', true),
    ('preset-moonbag-aggressive', 'Moonbag Aggressive', 35, '[{"trigger_multiplier": 2.0, "sell_percentage": 25}, {"trigger_multiplier": 3.0, "sell_percentage": 25}, {"trigger_multiplier": 5.0, "sell_percentage": 25}]', '{"enabled": true, "activation_multiplier": 2.0, "distance_percentage": 25}', '{"percentage": 25, "stop_loss": 0.5}', true),
    ('preset-quick-flip', 'Quick Flip', 25, '[{"trigger_multiplier": 1.5, "sell_percentage": 100}]', '{"enabled": false}', null, true),
    ('preset-diamond-hands', 'Diamond Hands', 40, '[{"trigger_multiplier": 5.0, "sell_percentage": 50}, {"trigger_multiplier": 10.0, "sell_percentage": 30}]', '{"enabled": true, "activation_multiplier": 3.0, "distance_percentage": 20}', '{"percentage": 20, "stop_loss": 0.7}', true)
ON CONFLICT (id) DO NOTHING;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_strategies_name ON exit_strategies(name);
CREATE INDEX IF NOT EXISTS idx_strategies_preset ON exit_strategies(is_preset);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_strategies_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER strategies_updated_at
    BEFORE UPDATE ON exit_strategies
    FOR EACH ROW
    EXECUTE FUNCTION update_strategies_updated_at();
```

### API Routes

```python
# src/walltrack/api/routes/strategy_management_routes.py
"""Exit strategy management API routes."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from walltrack.data.supabase.repositories.strategy_repo import (
    get_strategy_repo,
    StrategyRepository,
)
from walltrack.core.execution.models.exit_strategy import (
    ExitStrategy,
    PRESET_STRATEGIES,
)

router = APIRouter(prefix="/exit-strategies", tags=["exit-strategies"])


class StrategyListResponse(BaseModel):
    """Response for strategy list."""

    presets: list[ExitStrategy]
    custom: list[ExitStrategy]
    total: int


@router.get("/")
async def list_strategies(
    repo: StrategyRepository = Depends(get_strategy_repo),
) -> StrategyListResponse:
    """List all available strategies."""
    custom = await repo.get_all()

    return StrategyListResponse(
        presets=list(PRESET_STRATEGIES.values()),
        custom=custom,
        total=len(PRESET_STRATEGIES) + len(custom),
    )


@router.get("/{strategy_id}")
async def get_strategy(
    strategy_id: str,
    repo: StrategyRepository = Depends(get_strategy_repo),
) -> ExitStrategy:
    """Get strategy by ID."""
    # Check presets first
    if strategy_id in PRESET_STRATEGIES:
        return PRESET_STRATEGIES[strategy_id]

    # Then custom
    strategy = await repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    return strategy


@router.post("/")
async def create_strategy(
    strategy: ExitStrategy,
    repo: StrategyRepository = Depends(get_strategy_repo),
) -> ExitStrategy:
    """Create a new custom strategy."""
    if strategy.id.startswith("preset-"):
        raise HTTPException(status_code=400, detail="Cannot create preset strategies")

    return await repo.create(strategy)


@router.put("/{strategy_id}")
async def update_strategy(
    strategy_id: str,
    strategy: ExitStrategy,
    repo: StrategyRepository = Depends(get_strategy_repo),
) -> ExitStrategy:
    """Update an existing custom strategy."""
    if strategy_id.startswith("preset-"):
        raise HTTPException(status_code=400, detail="Cannot modify preset strategies")

    if strategy.id != strategy_id:
        raise HTTPException(status_code=400, detail="Strategy ID mismatch")

    return await repo.update(strategy)


@router.delete("/{strategy_id}")
async def delete_strategy(
    strategy_id: str,
    repo: StrategyRepository = Depends(get_strategy_repo),
) -> dict:
    """Delete a custom strategy."""
    if strategy_id.startswith("preset-"):
        raise HTTPException(status_code=400, detail="Cannot delete preset strategies")

    await repo.delete(strategy_id)

    return {"status": "deleted", "strategy_id": strategy_id}
```

### Unit Tests

```python
# tests/unit/ui/test_exit_strategies_dashboard.py
"""Tests for exit strategy management dashboard."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from walltrack.ui.components.exit_strategies import (
    load_all_strategies,
    load_strategy_detail,
    save_strategy,
    delete_strategy,
    format_strategy_detail,
)
from walltrack.core.execution.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    PRESET_STRATEGIES,
)


@pytest.fixture
def sample_strategy():
    return ExitStrategy(
        id="custom-test",
        name="Test Strategy",
        stop_loss_percentage=Decimal("25"),
        take_profit_levels=[
            TakeProfitLevel(trigger_multiplier=Decimal("2"), sell_percentage=50),
            TakeProfitLevel(trigger_multiplier=Decimal("3"), sell_percentage=50),
        ],
        trailing_stop=TrailingStopConfig(
            enabled=True,
            activation_multiplier=Decimal("2"),
            distance_percentage=Decimal("25"),
        ),
    )


class TestLoadAllStrategies:
    """Test loading all strategies."""

    @pytest.mark.asyncio
    async def test_includes_presets(self):
        """Test that presets are included."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.get_all = AsyncMock(return_value=[])

            df = await load_all_strategies()

            # Should have preset strategies
            assert len(df) >= len(PRESET_STRATEGIES)
            assert "Balanced" in df["Name"].values

    @pytest.mark.asyncio
    async def test_includes_custom(self, sample_strategy):
        """Test that custom strategies are included."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.get_all = AsyncMock(return_value=[sample_strategy])

            df = await load_all_strategies()

            assert "Test Strategy" in df["Name"].values


class TestLoadStrategyDetail:
    """Test loading strategy details."""

    @pytest.mark.asyncio
    async def test_load_preset(self):
        """Test loading a preset strategy."""
        detail = await load_strategy_detail("preset-balanced")

        assert detail is not None
        assert detail["name"] == "Balanced"

    @pytest.mark.asyncio
    async def test_load_custom(self, sample_strategy):
        """Test loading a custom strategy."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.get_by_id = AsyncMock(return_value=sample_strategy)

            detail = await load_strategy_detail("custom-test")

            assert detail is not None
            assert detail["name"] == "Test Strategy"

    @pytest.mark.asyncio
    async def test_load_nonexistent(self):
        """Test loading nonexistent strategy."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.get_by_id = AsyncMock(return_value=None)

            detail = await load_strategy_detail("nonexistent")

            assert detail is None


class TestSaveStrategy:
    """Test saving strategies."""

    @pytest.mark.asyncio
    async def test_create_new_strategy(self):
        """Test creating a new strategy."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.create = AsyncMock()

            result = await save_strategy(
                strategy_id=None,
                name="New Strategy",
                stop_loss_pct=30,
                tp1_mult=2.0, tp1_pct=50,
                tp2_mult=3.0, tp2_pct=50,
                tp3_mult=0, tp3_pct=0,
                trailing_enabled=True,
                trailing_activation=2.0,
                trailing_distance=30,
                max_hold_hours=0,
                stagnation_enabled=False,
                stagnation_hours=6,
                stagnation_threshold=5,
                moonbag_pct=0,
                moonbag_sl=0.3,
            )

            assert "created" in result
            mock.return_value.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_existing_strategy(self):
        """Test updating an existing strategy."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.update = AsyncMock()

            result = await save_strategy(
                strategy_id="custom-existing",
                name="Updated Strategy",
                stop_loss_pct=25,
                tp1_mult=2.0, tp1_pct=33,
                tp2_mult=3.0, tp2_pct=33,
                tp3_mult=5.0, tp3_pct=34,
                trailing_enabled=True,
                trailing_activation=2.5,
                trailing_distance=25,
                max_hold_hours=24,
                stagnation_enabled=True,
                stagnation_hours=6,
                stagnation_threshold=5,
                moonbag_pct=20,
                moonbag_sl=0.5,
            )

            assert "updated" in result
            mock.return_value.update.assert_called_once()


class TestDeleteStrategy:
    """Test deleting strategies."""

    @pytest.mark.asyncio
    async def test_delete_custom(self):
        """Test deleting a custom strategy."""
        with patch("walltrack.ui.components.exit_strategies.get_strategy_repo") as mock:
            mock.return_value.delete = AsyncMock()

            result = await delete_strategy("custom-test")

            assert "deleted" in result
            mock.return_value.delete.assert_called_once_with("custom-test")

    @pytest.mark.asyncio
    async def test_cannot_delete_preset(self):
        """Test that preset strategies cannot be deleted."""
        result = await delete_strategy("preset-balanced")

        assert "Cannot" in result


class TestFormatStrategyDetail:
    """Test strategy detail formatting."""

    def test_format_basic_strategy(self, sample_strategy):
        """Test formatting a basic strategy."""
        detail = sample_strategy.model_dump()
        result = format_strategy_detail(detail)

        assert "Test Strategy" in result
        assert "25%" in result  # Stop loss
        assert "2x" in result  # TP level

    def test_format_with_moonbag(self):
        """Test formatting strategy with moonbag."""
        detail = {
            "id": "test",
            "name": "Moonbag Test",
            "stop_loss_percentage": 30,
            "take_profit_levels": [
                {"trigger_multiplier": 2, "sell_percentage": 50}
            ],
            "trailing_stop": {"enabled": False},
            "moonbag": {"percentage": 20, "stop_loss": 0.5},
        }

        result = format_strategy_detail(detail)

        assert "Moonbag" in result
        assert "20%" in result

    def test_format_with_time_rules(self):
        """Test formatting strategy with time rules."""
        detail = {
            "id": "test",
            "name": "Time Test",
            "stop_loss_percentage": 30,
            "take_profit_levels": [],
            "trailing_stop": {"enabled": False},
            "time_rules": {
                "max_hold_hours": 24,
                "stagnation_exit_enabled": True,
                "stagnation_hours": 6,
                "stagnation_threshold_percentage": 5,
            },
        }

        result = format_strategy_detail(detail)

        assert "Time Rules" in result
        assert "24 hours" in result
        assert "Stagnation" in result

    def test_format_empty(self):
        """Test formatting empty detail."""
        result = format_strategy_detail(None)
        assert "Select a strategy" in result
```
