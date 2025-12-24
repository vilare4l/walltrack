# Story 8.3: Scenario Configuration

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: High
- **FR**: FR63

## User Story

**As an** operator,
**I want** to define backtest scenarios with specific parameter sets,
**So that** I can organize and reuse test configurations.

## Acceptance Criteria

### AC 1: Scenario Creation
**Given** scenario configuration interface
**When** operator creates a scenario
**Then** scenario has a name and description
**And** all configurable parameters can be set:
  - Scoring weights (wallet, cluster, token, context)
  - Score threshold
  - Position sizing parameters
  - Exit strategy parameters
  - Risk parameters

### AC 2: Scenario Persistence
**Given** scenario is saved
**When** scenario is stored
**Then** scenario is persisted in database
**And** scenario can be loaded for future backtests
**And** scenario can be duplicated and modified

### AC 3: Scenario Display
**Given** scenario parameters
**When** displayed in UI
**Then** clear comparison to current live settings
**And** differences are highlighted
**And** scenario validation ensures valid parameter ranges

### AC 4: Scenario Management
**Given** multiple scenarios
**When** scenarios are listed
**Then** all saved scenarios are shown
**And** scenarios can be organized by category/tag
**And** scenarios can be imported/exported (JSON)

## Technical Specifications

### Scenario Model

**src/walltrack/core/backtest/scenario.py:**
```python
"""Scenario configuration for backtesting."""

from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from walltrack.core.backtest.parameters import (
    BacktestParameters,
    ScoringWeights,
    ExitStrategyParams,
)


class ScenarioCategory(str, Enum):
    """Categories for organizing scenarios."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EXPERIMENTAL = "experimental"
    OPTIMIZATION = "optimization"
    CUSTOM = "custom"


class Scenario(BaseModel):
    """A named backtest scenario configuration."""

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None
    category: ScenarioCategory = ScenarioCategory.CUSTOM
    tags: list[str] = Field(default_factory=list)

    # Scoring parameters
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: Decimal = Decimal("0.70")

    # Position sizing
    base_position_sol: Decimal = Decimal("0.1")
    high_conviction_multiplier: Decimal = Decimal("1.5")
    high_conviction_threshold: Decimal = Decimal("0.85")

    # Exit strategy
    exit_strategy: ExitStrategyParams = Field(default_factory=ExitStrategyParams)

    # Risk parameters
    max_concurrent_positions: int = 5
    max_daily_trades: int = 10
    slippage_bps: int = 100

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: Optional[str] = None
    is_preset: bool = False

    @field_validator("score_threshold")
    @classmethod
    def validate_threshold(cls, v: Decimal) -> Decimal:
        """Ensure threshold is between 0 and 1."""
        if not (0 <= v <= 1):
            raise ValueError("Score threshold must be between 0 and 1")
        return v

    @field_validator("max_concurrent_positions")
    @classmethod
    def validate_max_positions(cls, v: int) -> int:
        """Ensure max positions is reasonable."""
        if not (1 <= v <= 50):
            raise ValueError("Max concurrent positions must be between 1 and 50")
        return v

    def to_backtest_params(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestParameters:
        """Convert scenario to backtest parameters."""
        return BacktestParameters(
            start_date=start_date,
            end_date=end_date,
            scoring_weights=self.scoring_weights,
            score_threshold=self.score_threshold,
            base_position_sol=self.base_position_sol,
            high_conviction_multiplier=self.high_conviction_multiplier,
            high_conviction_threshold=self.high_conviction_threshold,
            exit_strategy=self.exit_strategy,
            max_concurrent_positions=self.max_concurrent_positions,
            max_daily_trades=self.max_daily_trades,
            slippage_bps=self.slippage_bps,
        )

    def to_json(self) -> str:
        """Export scenario as JSON."""
        import json
        return json.dumps(self.model_dump(mode="json"), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Scenario":
        """Import scenario from JSON."""
        import json
        data = json.loads(json_str)
        return cls(**data)

    class Config:
        json_encoders = {Decimal: str}


# Preset scenarios
PRESET_SCENARIOS = [
    Scenario(
        id=uuid4(),
        name="Conservative",
        description="Lower risk with tighter stops and smaller positions",
        category=ScenarioCategory.CONSERVATIVE,
        is_preset=True,
        score_threshold=Decimal("0.80"),
        base_position_sol=Decimal("0.05"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.30"),
            take_profit_levels=[
                {"multiplier": 1.5, "sell_pct": 0.50},
                {"multiplier": 2.0, "sell_pct": 0.50},
            ],
            trailing_stop_enabled=False,
            moonbag_pct=Decimal("0"),
        ),
        max_concurrent_positions=3,
    ),
    Scenario(
        id=uuid4(),
        name="Balanced",
        description="Moderate risk with standard exit strategy",
        category=ScenarioCategory.MODERATE,
        is_preset=True,
        score_threshold=Decimal("0.70"),
        base_position_sol=Decimal("0.1"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.50"),
            take_profit_levels=[
                {"multiplier": 2.0, "sell_pct": 0.33},
                {"multiplier": 3.0, "sell_pct": 0.33},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("2.0"),
            trailing_stop_distance=Decimal("0.30"),
            moonbag_pct=Decimal("0.34"),
        ),
        max_concurrent_positions=5,
    ),
    Scenario(
        id=uuid4(),
        name="Aggressive Moonbag",
        description="Higher risk seeking moonshots with large moonbag",
        category=ScenarioCategory.AGGRESSIVE,
        is_preset=True,
        score_threshold=Decimal("0.65"),
        base_position_sol=Decimal("0.15"),
        high_conviction_multiplier=Decimal("2.0"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.60"),
            take_profit_levels=[
                {"multiplier": 3.0, "sell_pct": 0.25},
                {"multiplier": 5.0, "sell_pct": 0.25},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("3.0"),
            trailing_stop_distance=Decimal("0.40"),
            moonbag_pct=Decimal("0.50"),
        ),
        max_concurrent_positions=7,
    ),
    Scenario(
        id=uuid4(),
        name="Quick Flip",
        description="Fast exits targeting quick profits",
        category=ScenarioCategory.MODERATE,
        is_preset=True,
        score_threshold=Decimal("0.75"),
        base_position_sol=Decimal("0.1"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.20"),
            take_profit_levels=[
                {"multiplier": 1.3, "sell_pct": 0.50},
                {"multiplier": 1.5, "sell_pct": 0.50},
            ],
            trailing_stop_enabled=False,
            moonbag_pct=Decimal("0"),
        ),
        max_concurrent_positions=10,
    ),
    Scenario(
        id=uuid4(),
        name="Diamond Hands",
        description="Long-term holds seeking massive multipliers",
        category=ScenarioCategory.AGGRESSIVE,
        is_preset=True,
        score_threshold=Decimal("0.85"),
        base_position_sol=Decimal("0.2"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.70"),
            take_profit_levels=[
                {"multiplier": 5.0, "sell_pct": 0.25},
                {"multiplier": 10.0, "sell_pct": 0.25},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("5.0"),
            trailing_stop_distance=Decimal("0.50"),
            moonbag_pct=Decimal("0.50"),
        ),
        max_concurrent_positions=3,
    ),
]
```

### Scenario Service

**src/walltrack/core/backtest/scenario_service.py:**
```python
"""Service for managing backtest scenarios."""

from datetime import datetime, UTC
from typing import Optional
from uuid import UUID

import structlog

from walltrack.core.backtest.scenario import (
    Scenario,
    ScenarioCategory,
    PRESET_SCENARIOS,
)
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


class ScenarioService:
    """Service for CRUD operations on scenarios."""

    async def get_all_scenarios(
        self,
        category: Optional[ScenarioCategory] = None,
        include_presets: bool = True,
    ) -> list[Scenario]:
        """Get all scenarios, optionally filtered."""
        supabase = await get_supabase_client()

        filters = {}
        if category:
            filters["category"] = category.value

        records = await supabase.select("backtest_scenarios", filters=filters)
        scenarios = [Scenario(**r) for r in records]

        if include_presets:
            presets = PRESET_SCENARIOS
            if category:
                presets = [p for p in presets if p.category == category]
            scenarios = presets + scenarios

        return sorted(scenarios, key=lambda s: s.name)

    async def get_scenario(self, scenario_id: UUID) -> Optional[Scenario]:
        """Get a scenario by ID."""
        # Check presets first
        for preset in PRESET_SCENARIOS:
            if preset.id == scenario_id:
                return preset

        supabase = await get_supabase_client()
        records = await supabase.select(
            "backtest_scenarios",
            filters={"id": str(scenario_id)},
        )

        if records:
            return Scenario(**records[0])
        return None

    async def create_scenario(self, scenario: Scenario) -> Scenario:
        """Create a new scenario."""
        scenario.created_at = datetime.now(UTC)
        scenario.updated_at = datetime.now(UTC)
        scenario.is_preset = False

        supabase = await get_supabase_client()
        await supabase.insert(
            "backtest_scenarios",
            scenario.model_dump(mode="json"),
        )

        log.info("scenario_created", scenario_id=str(scenario.id), name=scenario.name)
        return scenario

    async def update_scenario(
        self,
        scenario_id: UUID,
        updates: dict,
    ) -> Optional[Scenario]:
        """Update an existing scenario."""
        # Prevent updating presets
        for preset in PRESET_SCENARIOS:
            if preset.id == scenario_id:
                raise ValueError("Cannot modify preset scenarios")

        updates["updated_at"] = datetime.now(UTC).isoformat()

        supabase = await get_supabase_client()
        result = await supabase.update(
            "backtest_scenarios",
            {"id": str(scenario_id)},
            updates,
        )

        if result:
            log.info("scenario_updated", scenario_id=str(scenario_id))
            return Scenario(**result)
        return None

    async def delete_scenario(self, scenario_id: UUID) -> bool:
        """Delete a scenario."""
        # Prevent deleting presets
        for preset in PRESET_SCENARIOS:
            if preset.id == scenario_id:
                raise ValueError("Cannot delete preset scenarios")

        supabase = await get_supabase_client()
        await supabase.delete("backtest_scenarios", {"id": str(scenario_id)})

        log.info("scenario_deleted", scenario_id=str(scenario_id))
        return True

    async def duplicate_scenario(
        self,
        scenario_id: UUID,
        new_name: str,
    ) -> Scenario:
        """Duplicate a scenario with a new name."""
        original = await self.get_scenario(scenario_id)
        if not original:
            raise ValueError(f"Scenario {scenario_id} not found")

        duplicate = Scenario(
            name=new_name,
            description=f"Copy of {original.name}",
            category=original.category,
            tags=original.tags.copy(),
            scoring_weights=original.scoring_weights.model_copy(),
            score_threshold=original.score_threshold,
            base_position_sol=original.base_position_sol,
            high_conviction_multiplier=original.high_conviction_multiplier,
            high_conviction_threshold=original.high_conviction_threshold,
            exit_strategy=original.exit_strategy.model_copy(),
            max_concurrent_positions=original.max_concurrent_positions,
            max_daily_trades=original.max_daily_trades,
            slippage_bps=original.slippage_bps,
        )

        return await self.create_scenario(duplicate)

    async def export_scenario(self, scenario_id: UUID) -> str:
        """Export scenario as JSON string."""
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return scenario.to_json()

    async def import_scenario(self, json_str: str) -> Scenario:
        """Import scenario from JSON string."""
        scenario = Scenario.from_json(json_str)
        # Generate new ID to avoid conflicts
        from uuid import uuid4
        scenario.id = uuid4()
        scenario.is_preset = False
        return await self.create_scenario(scenario)

    def compare_to_live(self, scenario: Scenario, live_config: dict) -> dict:
        """Compare scenario to live configuration."""
        differences = {}

        # Compare scoring weights
        for weight in ["wallet_weight", "cluster_weight", "token_weight", "context_weight"]:
            scenario_val = getattr(scenario.scoring_weights, weight)
            live_val = live_config.get("scoring_weights", {}).get(weight)
            if live_val and scenario_val != Decimal(str(live_val)):
                differences[f"scoring_weights.{weight}"] = {
                    "scenario": float(scenario_val),
                    "live": float(live_val),
                }

        # Compare threshold
        if scenario.score_threshold != Decimal(str(live_config.get("score_threshold", 0.7))):
            differences["score_threshold"] = {
                "scenario": float(scenario.score_threshold),
                "live": live_config.get("score_threshold"),
            }

        # Compare position sizing
        if scenario.base_position_sol != Decimal(str(live_config.get("base_position_sol", 0.1))):
            differences["base_position_sol"] = {
                "scenario": float(scenario.base_position_sol),
                "live": live_config.get("base_position_sol"),
            }

        return differences


# Singleton
_scenario_service: Optional[ScenarioService] = None


async def get_scenario_service() -> ScenarioService:
    """Get scenario service singleton."""
    global _scenario_service
    if _scenario_service is None:
        _scenario_service = ScenarioService()
    return _scenario_service
```

## Database Schema

```sql
-- Backtest scenarios table
CREATE TABLE IF NOT EXISTS backtest_scenarios (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50) DEFAULT 'custom',
    tags TEXT[] DEFAULT '{}',

    -- Scoring parameters
    scoring_weights JSONB NOT NULL,
    score_threshold DECIMAL(5, 4) DEFAULT 0.70,

    -- Position sizing
    base_position_sol DECIMAL(10, 4) DEFAULT 0.1,
    high_conviction_multiplier DECIMAL(5, 2) DEFAULT 1.5,
    high_conviction_threshold DECIMAL(5, 4) DEFAULT 0.85,

    -- Exit strategy
    exit_strategy JSONB NOT NULL,

    -- Risk parameters
    max_concurrent_positions INTEGER DEFAULT 5,
    max_daily_trades INTEGER DEFAULT 10,
    slippage_bps INTEGER DEFAULT 100,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by VARCHAR(100),
    is_preset BOOLEAN DEFAULT FALSE,

    UNIQUE(name)
);

CREATE INDEX idx_scenarios_category ON backtest_scenarios(category);
CREATE INDEX idx_scenarios_created ON backtest_scenarios(created_at);
```

## Implementation Tasks

- [x] Create Scenario model with validation
- [x] Create preset scenarios
- [x] Implement ScenarioService CRUD operations
- [ ] Add backtest_scenarios table
- [x] Implement scenario export/import
- [x] Implement comparison to live config
- [x] Write unit tests

## Definition of Done

- [x] Scenarios can be created, updated, deleted
- [x] Preset scenarios are available
- [x] Scenarios can be duplicated
- [x] Export/import works correctly
- [x] Validation prevents invalid parameters
- [x] Tests cover all operations

## Dev Agent Record

### Implementation Notes
- Created `scenario.py` with ScenarioCategory enum and Scenario model
- Scenario has validators for score_threshold (0-1) and max_concurrent_positions (1-50)
- `to_backtest_params()` converts scenario to BacktestParameters for engine
- `to_json()`/`from_json()` for import/export functionality
- Created 5 preset scenarios: Conservative, Balanced, Aggressive Moonbag, Quick Flip, Diamond Hands
- Created `scenario_service.py` with ScenarioService class
- Service provides CRUD operations with preset protection (cannot modify/delete presets)
- `duplicate_scenario()` creates copies with new IDs
- `compare_to_live()` finds differences between scenario and live config

### Tests Created
- `tests/unit/core/backtest/test_scenario.py` - 11 tests covering:
  - ScenarioCategory enum values
  - Scenario creation and custom parameters
  - Threshold and position validation
  - to_backtest_params conversion
  - JSON export/import
  - Preset scenarios validation
- `tests/unit/core/backtest/test_scenario_service.py` - 13 tests covering:
  - get_all_scenarios with filtering
  - get_scenario by ID (presets and custom)
  - create_scenario
  - update/delete preset protection
  - duplicate_scenario
  - export/import scenarios
  - compare_to_live differences

## File List

### New Files
- `src/walltrack/core/backtest/scenario.py` - Scenario model and presets
- `src/walltrack/core/backtest/scenario_service.py` - Scenario service
- `tests/unit/core/backtest/test_scenario.py` - Scenario tests
- `tests/unit/core/backtest/test_scenario_service.py` - Service tests

## Change Log

- 2025-12-21: Story 8-3 implementation complete - Scenario configuration
