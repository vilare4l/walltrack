# Story 4.8: Score-Based Strategy Assignment

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: Medium
- **FR**: FR27

## User Story

**As an** operator,
**I want** exit strategies automatically assigned based on signal score,
**So that** high-conviction trades get more aggressive strategies.

## Acceptance Criteria

### AC 1: Score-Based Rules
**Given** a new position from a scored signal
**When** exit strategy is assigned
**Then** score-based rules are applied:
- Score >= 0.90: Diamond Hands
- Score 0.80-0.89: Moonbag Aggressive
- Score 0.70-0.79: Balanced (default)

### AC 2: Custom Mapping
**Given** score-based assignment rules
**When** operator configures custom mapping
**Then** custom score-to-strategy mapping is used
**And** mapping is stored in Supabase config

### AC 3: Manual Override
**Given** operator override
**When** operator manually assigns strategy to position
**Then** manual assignment overrides score-based default
**And** override is logged

### AC 4: Default Fallback
**Given** default strategy setting
**When** no score-based rule matches
**Then** configured default strategy is used

## Technical Notes

- FR27: Assign exit strategy based on signal score or operator override
- Implement in `src/walltrack/core/execution/position_manager.py`
- Config stored in Supabase

## Implementation Tasks

- [ ] Implement score-to-strategy mapping
- [ ] Store mapping in Supabase config
- [ ] Apply mapping on position creation
- [ ] Allow custom mapping configuration
- [ ] Implement manual override
- [ ] Log overrides

## Definition of Done

- [ ] Strategies assigned by score tier
- [ ] Custom mapping configurable
- [ ] Manual overrides work
- [ ] Default fallback applies

---

## Technical Specifications

### Data Models

```python
# src/walltrack/core/execution/models/strategy_assignment.py
"""Score-based strategy assignment models."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from pydantic import BaseModel, Field, field_validator


class AssignmentSource(StrEnum):
    """Source of strategy assignment."""

    SCORE_BASED = "score_based"
    MANUAL_OVERRIDE = "manual_override"
    DEFAULT_FALLBACK = "default_fallback"


class ScoreRange(BaseModel):
    """A score range for strategy mapping."""

    min_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    max_score: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    strategy_id: str

    @field_validator("min_score", "max_score", mode="before")
    @classmethod
    def coerce_decimal(cls, v):
        return Decimal(str(v)) if v is not None else v

    def contains(self, score: Decimal) -> bool:
        """Check if score falls within this range."""
        return self.min_score <= score <= self.max_score


class StrategyMappingConfig(BaseModel):
    """Configuration for score-to-strategy mapping.

    Default mapping:
    - Score >= 0.90: Diamond Hands (high conviction)
    - Score 0.80-0.89: Moonbag Aggressive
    - Score 0.70-0.79: Balanced
    - Score < 0.70: Default fallback
    """

    mappings: list[ScoreRange] = Field(
        default_factory=lambda: [
            ScoreRange(min_score=Decimal("0.90"), max_score=Decimal("1.00"), strategy_id="preset-diamond-hands"),
            ScoreRange(min_score=Decimal("0.80"), max_score=Decimal("0.89"), strategy_id="preset-moonbag-aggressive"),
            ScoreRange(min_score=Decimal("0.70"), max_score=Decimal("0.79"), strategy_id="preset-balanced"),
        ]
    )

    default_strategy_id: str = Field(
        default="preset-balanced",
        description="Strategy to use when no score range matches"
    )

    enabled: bool = Field(
        default=True,
        description="Enable score-based assignment (vs always use default)"
    )

    def get_strategy_for_score(self, score: Decimal) -> tuple[str, bool]:
        """Get strategy ID for a given score.

        Returns (strategy_id, is_default).
        """
        if not self.enabled:
            return self.default_strategy_id, True

        for mapping in self.mappings:
            if mapping.contains(score):
                return mapping.strategy_id, False

        return self.default_strategy_id, True


class StrategyAssignment(BaseModel):
    """Result of strategy assignment for a position."""

    position_id: str
    signal_id: str
    signal_score: Decimal

    assigned_strategy_id: str
    assignment_source: AssignmentSource

    # For score-based
    matched_range: ScoreRange | None = None

    # For manual override
    override_by: str | None = Field(None, description="Operator who made override")
    override_reason: str | None = None

    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class ManualOverride(BaseModel):
    """Manual strategy override request."""

    position_id: str
    new_strategy_id: str
    override_by: str = Field(description="Operator identifier")
    reason: str | None = Field(None, description="Reason for override")


class OverrideLog(BaseModel):
    """Log entry for strategy overrides."""

    id: str
    position_id: str
    previous_strategy_id: str
    new_strategy_id: str
    override_by: str
    reason: str | None
    overridden_at: datetime = Field(default_factory=datetime.utcnow)
```

### Strategy Assigner Service

```python
# src/walltrack/core/execution/strategy_assigner.py
"""Score-based strategy assignment service."""

import structlog
from datetime import datetime
from decimal import Decimal
from uuid import uuid4

from walltrack.core.execution.models.strategy_assignment import (
    AssignmentSource,
    StrategyMappingConfig,
    StrategyAssignment,
    ManualOverride,
    OverrideLog,
)
from walltrack.core.execution.models.position import Position
from walltrack.core.execution.models.exit_strategy import ExitStrategy
from walltrack.data.supabase.repositories.strategy_repo import StrategyRepository
from walltrack.data.supabase.repositories.config_repo import ConfigRepository

logger = structlog.get_logger(__name__)


class StrategyAssigner:
    """Assigns exit strategies based on signal score or manual override.

    Assignment priority:
    1. Manual override (if exists)
    2. Score-based mapping
    3. Default fallback
    """

    def __init__(
        self,
        strategy_repo: StrategyRepository,
        config_repo: ConfigRepository,
    ) -> None:
        self._strategy_repo = strategy_repo
        self._config_repo = config_repo
        self._override_cache: dict[str, ManualOverride] = {}

    async def load_mapping_config(self) -> StrategyMappingConfig:
        """Load strategy mapping config from Supabase."""
        config_data = await self._config_repo.get_config("strategy_mapping")

        if config_data:
            return StrategyMappingConfig.model_validate(config_data)

        return StrategyMappingConfig()  # Default

    async def save_mapping_config(self, config: StrategyMappingConfig) -> None:
        """Save strategy mapping config to Supabase."""
        await self._config_repo.set_config(
            "strategy_mapping",
            config.model_dump(mode="json"),
        )

        logger.info(
            "strategy_mapping_config_updated",
            mappings_count=len(config.mappings),
            default_strategy=config.default_strategy_id,
            enabled=config.enabled,
        )

    async def assign_strategy(
        self,
        position_id: str,
        signal_id: str,
        signal_score: Decimal,
    ) -> StrategyAssignment:
        """Assign exit strategy to a new position.

        Returns assignment details including source.
        """
        # 1. Check for manual override
        override = self._override_cache.get(position_id)
        if override:
            logger.info(
                "strategy_assigned_manual_override",
                position_id=position_id,
                strategy_id=override.new_strategy_id,
                override_by=override.override_by,
            )

            return StrategyAssignment(
                position_id=position_id,
                signal_id=signal_id,
                signal_score=signal_score,
                assigned_strategy_id=override.new_strategy_id,
                assignment_source=AssignmentSource.MANUAL_OVERRIDE,
                override_by=override.override_by,
                override_reason=override.reason,
            )

        # 2. Load mapping config
        config = await self.load_mapping_config()

        # 3. Get strategy based on score
        strategy_id, is_default = config.get_strategy_for_score(signal_score)

        source = (
            AssignmentSource.DEFAULT_FALLBACK
            if is_default
            else AssignmentSource.SCORE_BASED
        )

        # Find matched range for logging
        matched_range = None
        if not is_default:
            for mapping in config.mappings:
                if mapping.contains(signal_score):
                    matched_range = mapping
                    break

        logger.info(
            "strategy_assigned",
            position_id=position_id,
            signal_score=float(signal_score),
            strategy_id=strategy_id,
            source=source.value,
            matched_range=(
                f"{float(matched_range.min_score)}-{float(matched_range.max_score)}"
                if matched_range else None
            ),
        )

        return StrategyAssignment(
            position_id=position_id,
            signal_id=signal_id,
            signal_score=signal_score,
            assigned_strategy_id=strategy_id,
            assignment_source=source,
            matched_range=matched_range,
        )

    async def get_strategy(self, strategy_id: str) -> ExitStrategy:
        """Get exit strategy by ID."""
        return await self._strategy_repo.get_by_id(strategy_id)

    async def manual_override(
        self,
        override: ManualOverride,
        current_strategy_id: str,
    ) -> OverrideLog:
        """Apply manual strategy override to a position.

        Returns log entry for the override.
        """
        # Store override
        self._override_cache[override.position_id] = override

        # Create log entry
        log = OverrideLog(
            id=str(uuid4()),
            position_id=override.position_id,
            previous_strategy_id=current_strategy_id,
            new_strategy_id=override.new_strategy_id,
            override_by=override.override_by,
            reason=override.reason,
        )

        # Persist override log
        await self._config_repo.log_override(log.model_dump(mode="json"))

        logger.info(
            "strategy_override_applied",
            position_id=override.position_id,
            previous_strategy=current_strategy_id,
            new_strategy=override.new_strategy_id,
            override_by=override.override_by,
            reason=override.reason,
        )

        return log

    def clear_override(self, position_id: str) -> None:
        """Clear manual override for a position (e.g., on close)."""
        self._override_cache.pop(position_id, None)


# Dependency injection
_strategy_assigner: StrategyAssigner | None = None


async def get_strategy_assigner() -> StrategyAssigner:
    """Get strategy assigner singleton."""
    global _strategy_assigner
    if _strategy_assigner is None:
        from walltrack.data.supabase.repositories.strategy_repo import get_strategy_repo
        from walltrack.data.supabase.repositories.config_repo import get_config_repo

        _strategy_assigner = StrategyAssigner(
            strategy_repo=await get_strategy_repo(),
            config_repo=await get_config_repo(),
        )
    return _strategy_assigner
```

### Integration with Position Manager

```python
# src/walltrack/core/execution/position_manager.py (strategy assignment additions)
"""Position manager with strategy assignment."""

from walltrack.core.execution.strategy_assigner import get_strategy_assigner


class PositionManager:
    """Enhanced position manager with automatic strategy assignment."""

    async def create_position(
        self,
        signal: Signal,
        trade_result: SwapResult,
    ) -> Position:
        """Create position with automatic strategy assignment."""

        # 1. Get strategy assigner
        assigner = await get_strategy_assigner()

        # 2. Assign strategy based on signal score
        assignment = await assigner.assign_strategy(
            position_id=str(uuid4()),
            signal_id=signal.id,
            signal_score=signal.score,
        )

        # 3. Get full strategy details
        strategy = await assigner.get_strategy(assignment.assigned_strategy_id)

        # 4. Create position with assigned strategy
        position = Position(
            id=assignment.position_id,
            wallet_id=self._wallet_id,
            token_mint=signal.token_mint,
            entry_price=trade_result.output_amount / trade_result.input_amount,
            amount=trade_result.output_amount,
            entry_time=datetime.utcnow(),
            signal_id=signal.id,
            exit_strategy_id=strategy.id,
            exit_strategy=strategy,
            strategy_assignment=assignment,
        )

        # 5. Save position
        await self._position_repo.create(position)

        # 6. Initialize monitoring
        await self._exit_manager.initialize_position(position)

        return position

    async def change_position_strategy(
        self,
        position_id: str,
        new_strategy_id: str,
        operator: str,
        reason: str | None = None,
    ) -> Position:
        """Change exit strategy for an existing position."""

        # Get current position
        position = await self._position_repo.get_by_id(position_id)

        if not position:
            raise ValueError(f"Position not found: {position_id}")

        # Apply override
        assigner = await get_strategy_assigner()
        override = ManualOverride(
            position_id=position_id,
            new_strategy_id=new_strategy_id,
            override_by=operator,
            reason=reason,
        )

        log = await assigner.manual_override(override, position.exit_strategy_id)

        # Get new strategy
        new_strategy = await assigner.get_strategy(new_strategy_id)

        # Update position
        position.exit_strategy_id = new_strategy_id
        position.exit_strategy = new_strategy

        await self._position_repo.update(position)

        # Recalculate levels with new strategy
        await self._exit_manager.recalculate_levels(position)

        return position
```

### API Routes

```python
# src/walltrack/api/routes/strategy_routes.py
"""Strategy assignment API routes."""

from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from walltrack.core.execution.strategy_assigner import (
    get_strategy_assigner,
    StrategyAssigner,
)
from walltrack.core.execution.models.strategy_assignment import (
    StrategyMappingConfig,
    ScoreRange,
    ManualOverride,
)

router = APIRouter(prefix="/strategies", tags=["strategies"])


class UpdateMappingRequest(BaseModel):
    """Request to update strategy mapping."""

    mappings: list[ScoreRange]
    default_strategy_id: str
    enabled: bool = True


class OverrideRequest(BaseModel):
    """Request to override position strategy."""

    new_strategy_id: str
    reason: str | None = None


class AssignmentPreviewRequest(BaseModel):
    """Request to preview strategy assignment."""

    score: float


@router.get("/mapping")
async def get_mapping_config(
    assigner: StrategyAssigner = Depends(get_strategy_assigner),
) -> StrategyMappingConfig:
    """Get current strategy mapping configuration."""
    return await assigner.load_mapping_config()


@router.put("/mapping")
async def update_mapping_config(
    request: UpdateMappingRequest,
    assigner: StrategyAssigner = Depends(get_strategy_assigner),
) -> dict:
    """Update strategy mapping configuration."""

    config = StrategyMappingConfig(
        mappings=request.mappings,
        default_strategy_id=request.default_strategy_id,
        enabled=request.enabled,
    )

    await assigner.save_mapping_config(config)

    return {"status": "updated", "mappings_count": len(config.mappings)}


@router.post("/preview-assignment")
async def preview_assignment(
    request: AssignmentPreviewRequest,
    assigner: StrategyAssigner = Depends(get_strategy_assigner),
) -> dict:
    """Preview which strategy would be assigned for a given score."""

    config = await assigner.load_mapping_config()
    score = Decimal(str(request.score))

    strategy_id, is_default = config.get_strategy_for_score(score)

    return {
        "score": float(score),
        "strategy_id": strategy_id,
        "is_default": is_default,
    }


@router.post("/positions/{position_id}/override")
async def override_position_strategy(
    position_id: str,
    request: OverrideRequest,
    operator: str = "system",  # Would come from auth in real app
    assigner: StrategyAssigner = Depends(get_strategy_assigner),
) -> dict:
    """Manually override strategy for a position."""

    # Would get current strategy from position
    # For now, just create the override
    override = ManualOverride(
        position_id=position_id,
        new_strategy_id=request.new_strategy_id,
        override_by=operator,
        reason=request.reason,
    )

    log = await assigner.manual_override(override, "previous-strategy-id")

    return {
        "status": "overridden",
        "log_id": log.id,
        "new_strategy_id": log.new_strategy_id,
    }
```

### Database Schema

```sql
-- Strategy mapping configuration
CREATE TABLE IF NOT EXISTS system_config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Default strategy mapping config
INSERT INTO system_config (key, value) VALUES (
    'strategy_mapping',
    '{
        "enabled": true,
        "default_strategy_id": "preset-balanced",
        "mappings": [
            {"min_score": 0.90, "max_score": 1.00, "strategy_id": "preset-diamond-hands"},
            {"min_score": 0.80, "max_score": 0.89, "strategy_id": "preset-moonbag-aggressive"},
            {"min_score": 0.70, "max_score": 0.79, "strategy_id": "preset-balanced"}
        ]
    }'
) ON CONFLICT (key) DO NOTHING;

-- Strategy override log
CREATE TABLE IF NOT EXISTS strategy_override_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    position_id UUID NOT NULL REFERENCES positions(id),
    previous_strategy_id VARCHAR(100) NOT NULL,
    new_strategy_id VARCHAR(100) NOT NULL,
    override_by VARCHAR(100) NOT NULL,
    reason TEXT,
    overridden_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_override_log_position ON strategy_override_log(position_id);
CREATE INDEX idx_override_log_date ON strategy_override_log(overridden_at);

-- Add strategy assignment info to positions
ALTER TABLE positions ADD COLUMN IF NOT EXISTS strategy_assignment JSONB DEFAULT NULL;
```

### Gradio Dashboard Component

```python
# src/walltrack/ui/components/strategy_mapping.py
"""Strategy mapping configuration UI component."""

import gradio as gr
from decimal import Decimal

from walltrack.core.execution.strategy_assigner import get_strategy_assigner
from walltrack.core.execution.models.strategy_assignment import (
    StrategyMappingConfig,
    ScoreRange,
)


async def load_current_mapping() -> dict:
    """Load current mapping for display."""
    assigner = await get_strategy_assigner()
    config = await assigner.load_mapping_config()

    return {
        "enabled": config.enabled,
        "default": config.default_strategy_id,
        "mappings": [
            {
                "range": f"{float(m.min_score):.2f} - {float(m.max_score):.2f}",
                "strategy": m.strategy_id,
            }
            for m in config.mappings
        ],
    }


async def save_mapping(
    enabled: bool,
    default_strategy: str,
    range_1_min: float,
    range_1_max: float,
    range_1_strategy: str,
    range_2_min: float,
    range_2_max: float,
    range_2_strategy: str,
    range_3_min: float,
    range_3_max: float,
    range_3_strategy: str,
) -> str:
    """Save updated mapping configuration."""
    assigner = await get_strategy_assigner()

    mappings = []

    # Only add ranges with valid strategies
    if range_1_strategy:
        mappings.append(ScoreRange(
            min_score=Decimal(str(range_1_min)),
            max_score=Decimal(str(range_1_max)),
            strategy_id=range_1_strategy,
        ))

    if range_2_strategy:
        mappings.append(ScoreRange(
            min_score=Decimal(str(range_2_min)),
            max_score=Decimal(str(range_2_max)),
            strategy_id=range_2_strategy,
        ))

    if range_3_strategy:
        mappings.append(ScoreRange(
            min_score=Decimal(str(range_3_min)),
            max_score=Decimal(str(range_3_max)),
            strategy_id=range_3_strategy,
        ))

    config = StrategyMappingConfig(
        enabled=enabled,
        default_strategy_id=default_strategy,
        mappings=mappings,
    )

    await assigner.save_mapping_config(config)

    return "✓ Mapping saved successfully"


async def preview_assignment(score: float) -> str:
    """Preview strategy assignment for a score."""
    assigner = await get_strategy_assigner()
    config = await assigner.load_mapping_config()

    strategy_id, is_default = config.get_strategy_for_score(Decimal(str(score)))

    if is_default:
        return f"Score {score:.2f} → **{strategy_id}** (default fallback)"
    else:
        return f"Score {score:.2f} → **{strategy_id}** (score-based)"


def create_strategy_mapping_panel() -> gr.Blocks:
    """Create the strategy mapping configuration panel."""

    with gr.Blocks() as panel:
        gr.Markdown("## Score-Based Strategy Assignment")
        gr.Markdown("""
        Configure automatic exit strategy assignment based on signal conviction score.
        Higher scores get more aggressive strategies (willing to hold longer for bigger gains).
        """)

        with gr.Row():
            enabled = gr.Checkbox(
                label="Enable Score-Based Assignment",
                value=True,
            )
            default_strategy = gr.Dropdown(
                label="Default Strategy (when no range matches)",
                choices=[
                    "preset-conservative",
                    "preset-balanced",
                    "preset-moonbag-aggressive",
                    "preset-quick-flip",
                    "preset-diamond-hands",
                ],
                value="preset-balanced",
            )

        gr.Markdown("### Score Ranges")

        # Range 1: High conviction (0.90-1.00)
        with gr.Row():
            gr.Markdown("**Tier 1 (Highest Conviction)**")
        with gr.Row():
            r1_min = gr.Number(label="Min Score", value=0.90, minimum=0, maximum=1)
            r1_max = gr.Number(label="Max Score", value=1.00, minimum=0, maximum=1)
            r1_strategy = gr.Dropdown(
                label="Strategy",
                choices=[
                    "preset-conservative",
                    "preset-balanced",
                    "preset-moonbag-aggressive",
                    "preset-quick-flip",
                    "preset-diamond-hands",
                ],
                value="preset-diamond-hands",
            )

        # Range 2: Medium-high conviction (0.80-0.89)
        with gr.Row():
            gr.Markdown("**Tier 2 (High Conviction)**")
        with gr.Row():
            r2_min = gr.Number(label="Min Score", value=0.80, minimum=0, maximum=1)
            r2_max = gr.Number(label="Max Score", value=0.89, minimum=0, maximum=1)
            r2_strategy = gr.Dropdown(
                label="Strategy",
                choices=[
                    "preset-conservative",
                    "preset-balanced",
                    "preset-moonbag-aggressive",
                    "preset-quick-flip",
                    "preset-diamond-hands",
                ],
                value="preset-moonbag-aggressive",
            )

        # Range 3: Standard conviction (0.70-0.79)
        with gr.Row():
            gr.Markdown("**Tier 3 (Standard Conviction)**")
        with gr.Row():
            r3_min = gr.Number(label="Min Score", value=0.70, minimum=0, maximum=1)
            r3_max = gr.Number(label="Max Score", value=0.79, minimum=0, maximum=1)
            r3_strategy = gr.Dropdown(
                label="Strategy",
                choices=[
                    "preset-conservative",
                    "preset-balanced",
                    "preset-moonbag-aggressive",
                    "preset-quick-flip",
                    "preset-diamond-hands",
                ],
                value="preset-balanced",
            )

        with gr.Row():
            save_btn = gr.Button("Save Mapping", variant="primary")
            save_status = gr.Textbox(label="Status", interactive=False)

        save_btn.click(
            fn=save_mapping,
            inputs=[
                enabled, default_strategy,
                r1_min, r1_max, r1_strategy,
                r2_min, r2_max, r2_strategy,
                r3_min, r3_max, r3_strategy,
            ],
            outputs=save_status,
        )

        gr.Markdown("---")
        gr.Markdown("### Preview Assignment")

        with gr.Row():
            test_score = gr.Slider(
                label="Test Score",
                minimum=0,
                maximum=1,
                step=0.01,
                value=0.85,
            )
            preview_result = gr.Markdown()

        test_score.change(
            fn=preview_assignment,
            inputs=test_score,
            outputs=preview_result,
        )

    return panel
```

### Unit Tests

```python
# tests/unit/core/execution/test_strategy_assigner.py
"""Tests for score-based strategy assignment."""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.execution.strategy_assigner import StrategyAssigner
from walltrack.core.execution.models.strategy_assignment import (
    AssignmentSource,
    StrategyMappingConfig,
    ScoreRange,
    ManualOverride,
)


@pytest.fixture
def mock_strategy_repo():
    repo = AsyncMock()
    repo.get_by_id.return_value = MagicMock(id="preset-balanced", name="Balanced")
    return repo


@pytest.fixture
def mock_config_repo():
    repo = AsyncMock()
    repo.get_config.return_value = None  # Use defaults
    return repo


@pytest.fixture
def assigner(mock_strategy_repo, mock_config_repo):
    return StrategyAssigner(mock_strategy_repo, mock_config_repo)


class TestStrategyMappingConfig:
    """Test strategy mapping configuration."""

    def test_default_mappings(self):
        """Test default mapping configuration."""
        config = StrategyMappingConfig()

        assert len(config.mappings) == 3
        assert config.default_strategy_id == "preset-balanced"
        assert config.enabled is True

    def test_get_strategy_high_score(self):
        """Test getting strategy for high conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(Decimal("0.95"))

        assert strategy_id == "preset-diamond-hands"
        assert is_default is False

    def test_get_strategy_medium_score(self):
        """Test getting strategy for medium conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(Decimal("0.85"))

        assert strategy_id == "preset-moonbag-aggressive"
        assert is_default is False

    def test_get_strategy_standard_score(self):
        """Test getting strategy for standard conviction score."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(Decimal("0.75"))

        assert strategy_id == "preset-balanced"
        assert is_default is False

    def test_get_strategy_low_score_fallback(self):
        """Test default fallback for low scores."""
        config = StrategyMappingConfig()

        strategy_id, is_default = config.get_strategy_for_score(Decimal("0.50"))

        assert strategy_id == "preset-balanced"  # Default
        assert is_default is True

    def test_get_strategy_disabled(self):
        """Test always returns default when disabled."""
        config = StrategyMappingConfig(enabled=False)

        strategy_id, is_default = config.get_strategy_for_score(Decimal("0.95"))

        assert strategy_id == "preset-balanced"  # Default
        assert is_default is True

    def test_custom_mappings(self):
        """Test custom mapping configuration."""
        config = StrategyMappingConfig(
            mappings=[
                ScoreRange(
                    min_score=Decimal("0.80"),
                    max_score=Decimal("1.00"),
                    strategy_id="custom-aggressive",
                ),
            ],
            default_strategy_id="custom-conservative",
        )

        # High score gets custom aggressive
        strategy_id, _ = config.get_strategy_for_score(Decimal("0.90"))
        assert strategy_id == "custom-aggressive"

        # Low score gets custom conservative
        strategy_id, _ = config.get_strategy_for_score(Decimal("0.50"))
        assert strategy_id == "custom-conservative"


class TestStrategyAssigner:
    """Test strategy assigner service."""

    @pytest.mark.asyncio
    async def test_assign_score_based(self, assigner):
        """Test score-based strategy assignment."""
        assignment = await assigner.assign_strategy(
            position_id="pos-001",
            signal_id="sig-001",
            signal_score=Decimal("0.92"),
        )

        assert assignment.position_id == "pos-001"
        assert assignment.signal_score == Decimal("0.92")
        assert assignment.assigned_strategy_id == "preset-diamond-hands"
        assert assignment.assignment_source == AssignmentSource.SCORE_BASED

    @pytest.mark.asyncio
    async def test_assign_default_fallback(self, assigner):
        """Test default fallback for unmatched scores."""
        assignment = await assigner.assign_strategy(
            position_id="pos-002",
            signal_id="sig-002",
            signal_score=Decimal("0.50"),
        )

        assert assignment.assigned_strategy_id == "preset-balanced"
        assert assignment.assignment_source == AssignmentSource.DEFAULT_FALLBACK

    @pytest.mark.asyncio
    async def test_manual_override(self, assigner, mock_config_repo):
        """Test manual strategy override."""
        override = ManualOverride(
            position_id="pos-003",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
            reason="Customer requested conservative approach",
        )

        log = await assigner.manual_override(override, "preset-balanced")

        assert log.position_id == "pos-003"
        assert log.previous_strategy_id == "preset-balanced"
        assert log.new_strategy_id == "preset-conservative"
        assert log.override_by == "operator-1"

        mock_config_repo.log_override.assert_called_once()

    @pytest.mark.asyncio
    async def test_override_takes_precedence(self, assigner):
        """Test manual override takes precedence over score-based."""
        # First apply override
        override = ManualOverride(
            position_id="pos-004",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
        )
        await assigner.manual_override(override, "preset-balanced")

        # Now assign - should use override
        assignment = await assigner.assign_strategy(
            position_id="pos-004",
            signal_id="sig-004",
            signal_score=Decimal("0.95"),  # Would be diamond hands without override
        )

        assert assignment.assigned_strategy_id == "preset-conservative"
        assert assignment.assignment_source == AssignmentSource.MANUAL_OVERRIDE

    @pytest.mark.asyncio
    async def test_clear_override(self, assigner):
        """Test clearing override."""
        # Apply override
        override = ManualOverride(
            position_id="pos-005",
            new_strategy_id="preset-conservative",
            override_by="operator-1",
        )
        await assigner.manual_override(override, "preset-balanced")

        # Clear it
        assigner.clear_override("pos-005")

        # Now assign - should use score-based
        assignment = await assigner.assign_strategy(
            position_id="pos-005",
            signal_id="sig-005",
            signal_score=Decimal("0.95"),
        )

        assert assignment.assigned_strategy_id == "preset-diamond-hands"
        assert assignment.assignment_source == AssignmentSource.SCORE_BASED


class TestScoreRangeEdgeCases:
    """Test edge cases for score ranges."""

    def test_boundary_score_min(self):
        """Test score at range minimum boundary."""
        range_ = ScoreRange(
            min_score=Decimal("0.80"),
            max_score=Decimal("0.89"),
            strategy_id="test-strategy",
        )

        assert range_.contains(Decimal("0.80")) is True
        assert range_.contains(Decimal("0.79")) is False

    def test_boundary_score_max(self):
        """Test score at range maximum boundary."""
        range_ = ScoreRange(
            min_score=Decimal("0.80"),
            max_score=Decimal("0.89"),
            strategy_id="test-strategy",
        )

        assert range_.contains(Decimal("0.89")) is True
        assert range_.contains(Decimal("0.90")) is False

    def test_overlapping_ranges(self):
        """Test first matching range wins."""
        config = StrategyMappingConfig(
            mappings=[
                ScoreRange(
                    min_score=Decimal("0.85"),
                    max_score=Decimal("1.00"),
                    strategy_id="strategy-a",
                ),
                ScoreRange(
                    min_score=Decimal("0.80"),
                    max_score=Decimal("0.90"),
                    strategy_id="strategy-b",
                ),
            ]
        )

        # 0.88 matches both - first wins
        strategy_id, _ = config.get_strategy_for_score(Decimal("0.88"))
        assert strategy_id == "strategy-a"
```
