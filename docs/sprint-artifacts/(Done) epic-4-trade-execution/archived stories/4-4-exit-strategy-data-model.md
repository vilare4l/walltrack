# Story 4.4: Exit Strategy Data Model and Presets

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR23

## User Story

**As an** operator,
**I want** configurable exit strategies with presets,
**So that** I can choose how positions are managed based on my risk preference.

## Acceptance Criteria

### AC 1: Exit Strategy Model
**Given** exit strategy model
**When** strategy is defined
**Then** it includes:
- name: strategy identifier
- take_profit_levels: list of {trigger_multiplier, sell_percentage}
- stop_loss: loss threshold (e.g., 0.5 = -50%)
- trailing_stop: {enabled, activation_multiplier, distance_percentage}
- time_rules: {max_hold_hours, stagnation_exit, stagnation_threshold, stagnation_hours}
- moonbag_pct: percentage kept regardless
- moonbag_stop: stop level for moonbag (or null for ride to zero)

### AC 2: Default Presets
**Given** system initialization
**When** presets are loaded
**Then** five default strategies are available:
- Conservative: 50%@x2, 50%@x3, no trailing, no moonbag
- Balanced: 33%@x2, 33%@x3, trailing (x2, 30%), 34% moonbag
- Moonbag Aggressive: 25%@x2, 25%@x3, no trailing, 50% moonbag ride to zero
- Quick Flip: 100%@x1.5, no trailing, no moonbag
- Diamond Hands: 25%@x5, 25%@x10, trailing (x3, 40%), 50% moonbag

### AC 3: Custom Strategy
**Given** exit_strategies table in Supabase
**When** custom strategy is created
**Then** strategy is validated and stored
**And** strategy becomes available for assignment

## Technical Notes

- FR23: Configurable exit strategies with multiple take-profit levels
- AR19-AR21: Exit strategy system from Architecture
- Implement in `src/walltrack/data/models/exit_strategy.py`
- Store in Supabase exit_strategies table

---

## Technical Specification

### 1. Data Models

```python
# src/walltrack/models/exit_strategy.py
from __future__ import annotations
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional
import uuid


class StrategyPreset(str, Enum):
    """Built-in strategy presets."""
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    MOONBAG_AGGRESSIVE = "moonbag_aggressive"
    QUICK_FLIP = "quick_flip"
    DIAMOND_HANDS = "diamond_hands"
    CUSTOM = "custom"


class TakeProfitLevel(BaseModel):
    """Single take-profit level configuration.

    Example: trigger_multiplier=2.0, sell_percentage=50
    means sell 50% of position when price doubles.
    """

    trigger_multiplier: float = Field(
        ...,
        gt=1.0,
        le=100.0,
        description="Price multiplier to trigger (e.g., 2.0 = 2x)"
    )
    sell_percentage: float = Field(
        ...,
        gt=0,
        le=100,
        description="Percentage of remaining position to sell"
    )

    @field_validator("trigger_multiplier")
    @classmethod
    def validate_multiplier(cls, v: float) -> float:
        if v <= 1.0:
            raise ValueError("Trigger multiplier must be > 1.0 (profit)")
        return round(v, 2)


class TrailingStopConfig(BaseModel):
    """Trailing stop configuration.

    Activates when price reaches activation_multiplier,
    then trails at distance_percentage below peak.
    """

    enabled: bool = Field(default=False)
    activation_multiplier: float = Field(
        default=2.0,
        gt=1.0,
        le=50.0,
        description="Multiplier to activate trailing stop"
    )
    distance_percentage: float = Field(
        default=30.0,
        gt=5.0,
        le=50.0,
        description="Distance from peak as percentage (e.g., 30% below)"
    )

    @model_validator(mode="after")
    def validate_trailing_config(self) -> "TrailingStopConfig":
        if self.enabled and self.distance_percentage < 10:
            # Very tight trailing stop is risky
            pass  # Allow but could warn
        return self


class TimeRulesConfig(BaseModel):
    """Time-based exit rules.

    Handles max hold duration and stagnation exits.
    """

    max_hold_hours: int | None = Field(
        default=None,
        ge=1,
        le=720,  # Max 30 days
        description="Maximum hold time before forced exit"
    )
    stagnation_exit_enabled: bool = Field(
        default=False,
        description="Exit if price stagnates"
    )
    stagnation_threshold_pct: float = Field(
        default=5.0,
        ge=1.0,
        le=20.0,
        description="Price movement threshold to be considered stagnant"
    )
    stagnation_hours: int = Field(
        default=24,
        ge=1,
        le=168,  # Max 1 week
        description="Hours of stagnation before exit"
    )


class MoonbagConfig(BaseModel):
    """Moonbag (keep forever) configuration.

    A moonbag is a small portion kept regardless of other rules.
    """

    percentage: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Percentage to keep as moonbag"
    )
    stop_loss: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Stop loss for moonbag (null = ride to zero)"
    )

    @property
    def has_moonbag(self) -> bool:
        return self.percentage > 0

    @property
    def ride_to_zero(self) -> bool:
        return self.has_moonbag and self.stop_loss is None


class ExitStrategy(BaseModel):
    """Complete exit strategy configuration.

    Defines how and when to exit a position.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)
    preset: StrategyPreset = Field(default=StrategyPreset.CUSTOM)
    is_default: bool = Field(default=False, description="Is this a built-in preset")

    # Take profit levels (executed in order of trigger)
    take_profit_levels: list[TakeProfitLevel] = Field(
        default_factory=list,
        max_length=10,
        description="Take profit levels in order"
    )

    # Stop loss
    stop_loss: float = Field(
        default=0.5,
        ge=0.1,
        le=1.0,
        description="Stop loss threshold (0.5 = -50%)"
    )

    # Trailing stop
    trailing_stop: TrailingStopConfig = Field(
        default_factory=TrailingStopConfig
    )

    # Time rules
    time_rules: TimeRulesConfig = Field(
        default_factory=TimeRulesConfig
    )

    # Moonbag
    moonbag: MoonbagConfig = Field(
        default_factory=MoonbagConfig
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str | None = Field(None)

    @model_validator(mode="after")
    def validate_total_sell_percentage(self) -> "ExitStrategy":
        """Ensure take profit + moonbag doesn't exceed 100%."""
        if not self.take_profit_levels:
            return self

        # Calculate effective sell total
        # Each level sells a percentage of REMAINING, so we simulate
        remaining = 100.0 - self.moonbag.percentage
        total_sold = 0.0

        for level in sorted(self.take_profit_levels, key=lambda x: x.trigger_multiplier):
            sell_amount = remaining * (level.sell_percentage / 100)
            total_sold += sell_amount
            remaining -= sell_amount

        # This is informational - the math works out naturally
        return self

    @model_validator(mode="after")
    def validate_take_profit_order(self) -> "ExitStrategy":
        """Ensure take profit levels are in ascending order."""
        if len(self.take_profit_levels) <= 1:
            return self

        multipliers = [tp.trigger_multiplier for tp in self.take_profit_levels]
        if multipliers != sorted(multipliers):
            # Auto-sort them
            self.take_profit_levels = sorted(
                self.take_profit_levels,
                key=lambda x: x.trigger_multiplier
            )

        return self

    @property
    def has_take_profits(self) -> bool:
        return len(self.take_profit_levels) > 0

    @property
    def has_trailing_stop(self) -> bool:
        return self.trailing_stop.enabled

    @property
    def has_time_limits(self) -> bool:
        return (
            self.time_rules.max_hold_hours is not None
            or self.time_rules.stagnation_exit_enabled
        )


class ExitStrategyAssignment(BaseModel):
    """Assignment of exit strategy to a conviction tier or specific position."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    strategy_id: str = Field(..., description="Exit strategy ID")
    conviction_tier: str | None = Field(
        None,
        description="Conviction tier this applies to (high, standard)"
    )
    position_id: str | None = Field(
        None,
        description="Specific position ID (overrides tier)"
    )
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @model_validator(mode="after")
    def validate_assignment(self) -> "ExitStrategyAssignment":
        """Either tier or position_id must be set."""
        if self.conviction_tier is None and self.position_id is None:
            raise ValueError("Either conviction_tier or position_id must be set")
        return self
```

### 2. Default Presets

```python
# src/walltrack/constants/exit_presets.py
from walltrack.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    TimeRulesConfig,
    MoonbagConfig,
    StrategyPreset,
)


# ============================================================================
# CONSERVATIVE: Safe, early exits, no trailing, no moonbag
# Best for: Risk-averse operators, volatile markets
# ============================================================================
CONSERVATIVE_STRATEGY = ExitStrategy(
    id="preset-conservative",
    name="Conservative",
    description="Safe strategy: sell 50% at 2x, remaining 50% at 3x. No trailing or moonbag.",
    preset=StrategyPreset.CONSERVATIVE,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),  # 100% of remaining
    ],
    stop_loss=0.5,  # -50%
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(max_hold_hours=72),  # 3 days max
    moonbag=MoonbagConfig(percentage=0),
)


# ============================================================================
# BALANCED: Middle ground with trailing stop and small moonbag
# Best for: Most operators, default recommendation
# ============================================================================
BALANCED_STRATEGY = ExitStrategy(
    id="preset-balanced",
    name="Balanced",
    description="Balanced approach: 33% at 2x, 33% at 3x, trailing stop at 2x (30%), 34% moonbag.",
    preset=StrategyPreset.BALANCED,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=33),
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),  # 50% of remaining ~33%
    ],
    stop_loss=0.5,
    trailing_stop=TrailingStopConfig(
        enabled=True,
        activation_multiplier=2.0,
        distance_percentage=30,
    ),
    time_rules=TimeRulesConfig(max_hold_hours=168),  # 1 week
    moonbag=MoonbagConfig(percentage=34, stop_loss=0.3),  # Moonbag with -70% stop
)


# ============================================================================
# MOONBAG AGGRESSIVE: High moonbag, ride to zero strategy
# Best for: High conviction plays, meme coins with moonshot potential
# ============================================================================
MOONBAG_AGGRESSIVE_STRATEGY = ExitStrategy(
    id="preset-moonbag-aggressive",
    name="Moonbag Aggressive",
    description="High moonbag: 25% at 2x, 25% at 3x, 50% moonbag rides to zero.",
    preset=StrategyPreset.MOONBAG_AGGRESSIVE,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),  # 50% of 50% = 25%
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),  # Remaining 25%
    ],
    stop_loss=0.5,
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(),  # No time limit
    moonbag=MoonbagConfig(percentage=50, stop_loss=None),  # Ride to zero
)


# ============================================================================
# QUICK FLIP: Fast exit, take profit early
# Best for: Scalping, quick trades, high volume tokens
# ============================================================================
QUICK_FLIP_STRATEGY = ExitStrategy(
    id="preset-quick-flip",
    name="Quick Flip",
    description="Fast exit: sell 100% at 1.5x. Tight stop loss, no moonbag.",
    preset=StrategyPreset.QUICK_FLIP,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=1.5, sell_percentage=100),
    ],
    stop_loss=0.3,  # -30% tight stop
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(
        max_hold_hours=24,
        stagnation_exit_enabled=True,
        stagnation_threshold_pct=5,
        stagnation_hours=6,
    ),
    moonbag=MoonbagConfig(percentage=0),
)


# ============================================================================
# DIAMOND HANDS: Long hold, high targets
# Best for: Strong conviction, low volume positions
# ============================================================================
DIAMOND_HANDS_STRATEGY = ExitStrategy(
    id="preset-diamond-hands",
    name="Diamond Hands",
    description="Long hold: 25% at 5x, 25% at 10x, trailing at 3x (40%), 50% moonbag.",
    preset=StrategyPreset.DIAMOND_HANDS,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=5.0, sell_percentage=50),   # 50% of 50% = 25%
        TakeProfitLevel(trigger_multiplier=10.0, sell_percentage=100),  # Remaining 25%
    ],
    stop_loss=0.6,  # -40% wider stop
    trailing_stop=TrailingStopConfig(
        enabled=True,
        activation_multiplier=3.0,
        distance_percentage=40,
    ),
    time_rules=TimeRulesConfig(),  # No time limit
    moonbag=MoonbagConfig(percentage=50, stop_loss=0.2),  # -80% stop for moonbag
)


# All default presets
DEFAULT_PRESETS = [
    CONSERVATIVE_STRATEGY,
    BALANCED_STRATEGY,
    MOONBAG_AGGRESSIVE_STRATEGY,
    QUICK_FLIP_STRATEGY,
    DIAMOND_HANDS_STRATEGY,
]


def get_preset_by_name(name: str) -> ExitStrategy | None:
    """Get preset strategy by name."""
    for preset in DEFAULT_PRESETS:
        if preset.name.lower() == name.lower():
            return preset
    return None


def get_preset_by_type(preset_type: StrategyPreset) -> ExitStrategy | None:
    """Get preset strategy by type."""
    for preset in DEFAULT_PRESETS:
        if preset.preset == preset_type:
            return preset
    return None
```

### 3. Repository

```python
# src/walltrack/repositories/exit_strategy_repository.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

import structlog
from supabase import AsyncClient

from walltrack.models.exit_strategy import (
    ExitStrategy,
    ExitStrategyAssignment,
    StrategyPreset,
)
from walltrack.constants.exit_presets import DEFAULT_PRESETS
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger()


class ExitStrategyRepository:
    """Repository for exit strategy storage and retrieval."""

    def __init__(self, client: AsyncClient):
        self._client = client

    async def initialize_presets(self) -> int:
        """Seed default preset strategies if not present.

        Returns number of presets inserted.
        """
        inserted = 0

        for preset in DEFAULT_PRESETS:
            # Check if already exists
            existing = await (
                self._client.table("exit_strategies")
                .select("id")
                .eq("id", preset.id)
                .execute()
            )

            if not existing.data:
                await self.create(preset)
                inserted += 1
                logger.info(
                    "exit_preset_seeded",
                    name=preset.name,
                    id=preset.id,
                )

        return inserted

    async def create(self, strategy: ExitStrategy) -> ExitStrategy:
        """Create new exit strategy."""
        data = self._serialize_strategy(strategy)

        result = await (
            self._client.table("exit_strategies")
            .insert(data)
            .execute()
        )

        logger.info("exit_strategy_created", id=strategy.id, name=strategy.name)
        return self._deserialize_strategy(result.data[0])

    async def update(self, strategy: ExitStrategy) -> ExitStrategy:
        """Update existing exit strategy."""
        strategy.updated_at = datetime.utcnow()
        data = self._serialize_strategy(strategy)

        result = await (
            self._client.table("exit_strategies")
            .update(data)
            .eq("id", strategy.id)
            .execute()
        )

        logger.info("exit_strategy_updated", id=strategy.id)
        return self._deserialize_strategy(result.data[0])

    async def get_by_id(self, strategy_id: str) -> ExitStrategy | None:
        """Get strategy by ID."""
        result = await (
            self._client.table("exit_strategies")
            .select("*")
            .eq("id", strategy_id)
            .single()
            .execute()
        )

        if result.data:
            return self._deserialize_strategy(result.data)
        return None

    async def get_by_name(self, name: str) -> ExitStrategy | None:
        """Get strategy by name."""
        result = await (
            self._client.table("exit_strategies")
            .select("*")
            .eq("name", name)
            .single()
            .execute()
        )

        if result.data:
            return self._deserialize_strategy(result.data)
        return None

    async def list_all(self, include_defaults: bool = True) -> list[ExitStrategy]:
        """List all exit strategies."""
        query = self._client.table("exit_strategies").select("*")

        if not include_defaults:
            query = query.eq("is_default", False)

        result = await query.order("created_at").execute()
        return [self._deserialize_strategy(row) for row in result.data]

    async def list_presets(self) -> list[ExitStrategy]:
        """List only preset strategies."""
        result = await (
            self._client.table("exit_strategies")
            .select("*")
            .eq("is_default", True)
            .execute()
        )
        return [self._deserialize_strategy(row) for row in result.data]

    async def delete(self, strategy_id: str) -> bool:
        """Delete strategy (cannot delete defaults)."""
        # Check if default
        strategy = await self.get_by_id(strategy_id)
        if strategy and strategy.is_default:
            logger.warning("cannot_delete_default_strategy", id=strategy_id)
            return False

        await (
            self._client.table("exit_strategies")
            .delete()
            .eq("id", strategy_id)
            .execute()
        )

        logger.info("exit_strategy_deleted", id=strategy_id)
        return True

    # === Assignments ===

    async def get_assignment_for_tier(self, tier: str) -> ExitStrategy | None:
        """Get exit strategy assigned to conviction tier."""
        result = await (
            self._client.table("exit_strategy_assignments")
            .select("strategy_id")
            .eq("conviction_tier", tier)
            .eq("is_active", True)
            .single()
            .execute()
        )

        if result.data:
            return await self.get_by_id(result.data["strategy_id"])
        return None

    async def assign_to_tier(
        self,
        strategy_id: str,
        tier: str,
    ) -> ExitStrategyAssignment:
        """Assign strategy to conviction tier."""
        # Deactivate existing assignment
        await (
            self._client.table("exit_strategy_assignments")
            .update({"is_active": False})
            .eq("conviction_tier", tier)
            .execute()
        )

        # Create new assignment
        assignment = ExitStrategyAssignment(
            strategy_id=strategy_id,
            conviction_tier=tier,
        )

        result = await (
            self._client.table("exit_strategy_assignments")
            .insert({
                "id": assignment.id,
                "strategy_id": assignment.strategy_id,
                "conviction_tier": assignment.conviction_tier,
                "is_active": True,
                "created_at": assignment.created_at.isoformat(),
            })
            .execute()
        )

        logger.info(
            "exit_strategy_assigned_to_tier",
            strategy_id=strategy_id,
            tier=tier,
        )

        return assignment

    # === Serialization ===

    def _serialize_strategy(self, strategy: ExitStrategy) -> dict:
        """Serialize strategy for database storage."""
        return {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "preset": strategy.preset.value,
            "is_default": strategy.is_default,
            "take_profit_levels": [
                {"trigger_multiplier": tp.trigger_multiplier, "sell_percentage": tp.sell_percentage}
                for tp in strategy.take_profit_levels
            ],
            "stop_loss": strategy.stop_loss,
            "trailing_stop": {
                "enabled": strategy.trailing_stop.enabled,
                "activation_multiplier": strategy.trailing_stop.activation_multiplier,
                "distance_percentage": strategy.trailing_stop.distance_percentage,
            },
            "time_rules": {
                "max_hold_hours": strategy.time_rules.max_hold_hours,
                "stagnation_exit_enabled": strategy.time_rules.stagnation_exit_enabled,
                "stagnation_threshold_pct": strategy.time_rules.stagnation_threshold_pct,
                "stagnation_hours": strategy.time_rules.stagnation_hours,
            },
            "moonbag": {
                "percentage": strategy.moonbag.percentage,
                "stop_loss": strategy.moonbag.stop_loss,
            },
            "created_at": strategy.created_at.isoformat(),
            "updated_at": strategy.updated_at.isoformat(),
            "created_by": strategy.created_by,
        }

    def _deserialize_strategy(self, data: dict) -> ExitStrategy:
        """Deserialize strategy from database."""
        from walltrack.models.exit_strategy import (
            TakeProfitLevel,
            TrailingStopConfig,
            TimeRulesConfig,
            MoonbagConfig,
        )

        tp_levels = [
            TakeProfitLevel(**tp)
            for tp in data.get("take_profit_levels", [])
        ]

        trailing = data.get("trailing_stop", {})
        time_rules = data.get("time_rules", {})
        moonbag = data.get("moonbag", {})

        return ExitStrategy(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            preset=StrategyPreset(data.get("preset", "custom")),
            is_default=data.get("is_default", False),
            take_profit_levels=tp_levels,
            stop_loss=data.get("stop_loss", 0.5),
            trailing_stop=TrailingStopConfig(**trailing) if trailing else TrailingStopConfig(),
            time_rules=TimeRulesConfig(**time_rules) if time_rules else TimeRulesConfig(),
            moonbag=MoonbagConfig(**moonbag) if moonbag else MoonbagConfig(),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            created_by=data.get("created_by"),
        )


# Singleton
_repo: ExitStrategyRepository | None = None


async def get_exit_strategy_repository() -> ExitStrategyRepository:
    """Get or create exit strategy repository singleton."""
    global _repo
    if _repo is None:
        client = await get_supabase_client()
        _repo = ExitStrategyRepository(client)
        # Initialize presets on first access
        await _repo.initialize_presets()
    return _repo
```

### 4. API Routes

```python
# src/walltrack/api/routes/exit_strategies.py
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from walltrack.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    TimeRulesConfig,
    MoonbagConfig,
    StrategyPreset,
)
from walltrack.repositories.exit_strategy_repository import (
    ExitStrategyRepository,
    get_exit_strategy_repository,
)

router = APIRouter(prefix="/exit-strategies", tags=["exit-strategies"])


class TakeProfitInput(BaseModel):
    trigger_multiplier: float
    sell_percentage: float


class TrailingStopInput(BaseModel):
    enabled: bool = False
    activation_multiplier: float = 2.0
    distance_percentage: float = 30.0


class TimeRulesInput(BaseModel):
    max_hold_hours: int | None = None
    stagnation_exit_enabled: bool = False
    stagnation_threshold_pct: float = 5.0
    stagnation_hours: int = 24


class MoonbagInput(BaseModel):
    percentage: float = 0.0
    stop_loss: float | None = None


class CreateStrategyRequest(BaseModel):
    name: str
    description: str | None = None
    take_profit_levels: list[TakeProfitInput]
    stop_loss: float = 0.5
    trailing_stop: TrailingStopInput | None = None
    time_rules: TimeRulesInput | None = None
    moonbag: MoonbagInput | None = None


class AssignTierRequest(BaseModel):
    strategy_id: str
    tier: str  # "high" or "standard"


@router.get("/", response_model=list[ExitStrategy])
async def list_strategies(
    include_defaults: bool = True,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> list[ExitStrategy]:
    """List all exit strategies."""
    return await repo.list_all(include_defaults)


@router.get("/presets", response_model=list[ExitStrategy])
async def list_presets(
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> list[ExitStrategy]:
    """List only preset (default) strategies."""
    return await repo.list_presets()


@router.get("/{strategy_id}", response_model=ExitStrategy)
async def get_strategy(
    strategy_id: str,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> ExitStrategy:
    """Get strategy by ID."""
    strategy = await repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )
    return strategy


@router.post("/", response_model=ExitStrategy, status_code=status.HTTP_201_CREATED)
async def create_strategy(
    request: CreateStrategyRequest,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> ExitStrategy:
    """Create custom exit strategy."""
    # Check name uniqueness
    existing = await repo.get_by_name(request.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Strategy with name '{request.name}' already exists",
        )

    strategy = ExitStrategy(
        name=request.name,
        description=request.description,
        preset=StrategyPreset.CUSTOM,
        is_default=False,
        take_profit_levels=[
            TakeProfitLevel(**tp.model_dump())
            for tp in request.take_profit_levels
        ],
        stop_loss=request.stop_loss,
        trailing_stop=TrailingStopConfig(**(request.trailing_stop.model_dump() if request.trailing_stop else {})),
        time_rules=TimeRulesConfig(**(request.time_rules.model_dump() if request.time_rules else {})),
        moonbag=MoonbagConfig(**(request.moonbag.model_dump() if request.moonbag else {})),
    )

    return await repo.create(strategy)


@router.put("/{strategy_id}", response_model=ExitStrategy)
async def update_strategy(
    strategy_id: str,
    request: CreateStrategyRequest,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> ExitStrategy:
    """Update exit strategy (cannot update defaults)."""
    existing = await repo.get_by_id(strategy_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {strategy_id} not found",
        )

    if existing.is_default:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify default preset strategies",
        )

    # Update fields
    existing.name = request.name
    existing.description = request.description
    existing.take_profit_levels = [
        TakeProfitLevel(**tp.model_dump())
        for tp in request.take_profit_levels
    ]
    existing.stop_loss = request.stop_loss
    if request.trailing_stop:
        existing.trailing_stop = TrailingStopConfig(**request.trailing_stop.model_dump())
    if request.time_rules:
        existing.time_rules = TimeRulesConfig(**request.time_rules.model_dump())
    if request.moonbag:
        existing.moonbag = MoonbagConfig(**request.moonbag.model_dump())

    return await repo.update(existing)


@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_strategy(
    strategy_id: str,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> None:
    """Delete custom exit strategy."""
    success = await repo.delete(strategy_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete default preset strategies",
        )


@router.post("/assign-tier")
async def assign_to_tier(
    request: AssignTierRequest,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> dict:
    """Assign exit strategy to conviction tier."""
    if request.tier not in ["high", "standard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be 'high' or 'standard'",
        )

    # Verify strategy exists
    strategy = await repo.get_by_id(request.strategy_id)
    if not strategy:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Strategy {request.strategy_id} not found",
        )

    assignment = await repo.assign_to_tier(request.strategy_id, request.tier)

    return {
        "assignment_id": assignment.id,
        "strategy_id": assignment.strategy_id,
        "strategy_name": strategy.name,
        "tier": request.tier,
    }


@router.get("/tier/{tier}", response_model=ExitStrategy | None)
async def get_tier_strategy(
    tier: str,
    repo: ExitStrategyRepository = Depends(get_exit_strategy_repository),
) -> ExitStrategy | None:
    """Get exit strategy assigned to conviction tier."""
    if tier not in ["high", "standard"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tier must be 'high' or 'standard'",
        )

    return await repo.get_assignment_for_tier(tier)
```

### 5. Unit Tests

```python
# tests/unit/models/test_exit_strategy.py
import pytest
from pydantic import ValidationError

from walltrack.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    TimeRulesConfig,
    MoonbagConfig,
    StrategyPreset,
)
from walltrack.constants.exit_presets import (
    DEFAULT_PRESETS,
    CONSERVATIVE_STRATEGY,
    BALANCED_STRATEGY,
    get_preset_by_name,
)


class TestTakeProfitLevel:
    """Tests for TakeProfitLevel model."""

    def test_valid_take_profit(self):
        """Test valid take profit level."""
        tp = TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50)
        assert tp.trigger_multiplier == 2.0
        assert tp.sell_percentage == 50

    def test_multiplier_must_be_greater_than_one(self):
        """Test multiplier validation."""
        with pytest.raises(ValidationError):
            TakeProfitLevel(trigger_multiplier=0.8, sell_percentage=50)

    def test_sell_percentage_range(self):
        """Test sell percentage must be 0-100."""
        with pytest.raises(ValidationError):
            TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=150)


class TestTrailingStopConfig:
    """Tests for TrailingStopConfig model."""

    def test_default_disabled(self):
        """Test trailing stop disabled by default."""
        config = TrailingStopConfig()
        assert config.enabled is False

    def test_valid_config(self):
        """Test valid trailing stop config."""
        config = TrailingStopConfig(
            enabled=True,
            activation_multiplier=2.0,
            distance_percentage=30,
        )
        assert config.enabled is True
        assert config.activation_multiplier == 2.0


class TestMoonbagConfig:
    """Tests for MoonbagConfig model."""

    def test_no_moonbag_by_default(self):
        """Test no moonbag by default."""
        config = MoonbagConfig()
        assert config.percentage == 0
        assert config.has_moonbag is False

    def test_ride_to_zero(self):
        """Test ride to zero detection."""
        config = MoonbagConfig(percentage=50, stop_loss=None)
        assert config.has_moonbag is True
        assert config.ride_to_zero is True

    def test_moonbag_with_stop(self):
        """Test moonbag with stop loss."""
        config = MoonbagConfig(percentage=50, stop_loss=0.3)
        assert config.has_moonbag is True
        assert config.ride_to_zero is False


class TestExitStrategy:
    """Tests for ExitStrategy model."""

    def test_basic_strategy(self):
        """Test basic strategy creation."""
        strategy = ExitStrategy(
            name="Test Strategy",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            ],
        )
        assert strategy.name == "Test Strategy"
        assert len(strategy.take_profit_levels) == 1

    def test_take_profits_auto_sorted(self):
        """Test take profit levels are auto-sorted."""
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            ],
        )
        # Should be sorted ascending
        assert strategy.take_profit_levels[0].trigger_multiplier == 2.0
        assert strategy.take_profit_levels[1].trigger_multiplier == 3.0

    def test_properties(self):
        """Test strategy property checks."""
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=100),
            ],
            trailing_stop=TrailingStopConfig(enabled=True, activation_multiplier=2.0, distance_percentage=30),
            time_rules=TimeRulesConfig(max_hold_hours=24),
        )

        assert strategy.has_take_profits is True
        assert strategy.has_trailing_stop is True
        assert strategy.has_time_limits is True


class TestDefaultPresets:
    """Tests for default preset strategies."""

    def test_five_presets_defined(self):
        """Test exactly five presets are defined."""
        assert len(DEFAULT_PRESETS) == 5

    def test_all_presets_valid(self):
        """Test all presets pass validation."""
        for preset in DEFAULT_PRESETS:
            assert preset.id.startswith("preset-")
            assert preset.is_default is True
            assert preset.name is not None

    def test_conservative_preset(self):
        """Test conservative preset configuration."""
        strategy = CONSERVATIVE_STRATEGY
        assert strategy.name == "Conservative"
        assert len(strategy.take_profit_levels) == 2
        assert strategy.trailing_stop.enabled is False
        assert strategy.moonbag.percentage == 0

    def test_balanced_preset(self):
        """Test balanced preset configuration."""
        strategy = BALANCED_STRATEGY
        assert strategy.name == "Balanced"
        assert strategy.trailing_stop.enabled is True
        assert strategy.moonbag.percentage == 34

    def test_get_preset_by_name(self):
        """Test preset lookup by name."""
        strategy = get_preset_by_name("Conservative")
        assert strategy is not None
        assert strategy.name == "Conservative"

    def test_get_preset_by_name_case_insensitive(self):
        """Test preset lookup is case insensitive."""
        strategy = get_preset_by_name("BALANCED")
        assert strategy is not None
        assert strategy.name == "Balanced"

    def test_get_preset_by_name_not_found(self):
        """Test preset lookup returns None for unknown."""
        strategy = get_preset_by_name("Unknown")
        assert strategy is None
```

### 6. Database Schema

```sql
-- migrations/007_exit_strategies.sql

-- Exit strategies table
CREATE TABLE IF NOT EXISTS exit_strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    preset TEXT NOT NULL DEFAULT 'custom',
    is_default BOOLEAN NOT NULL DEFAULT false,

    -- Take profit levels (JSONB array)
    take_profit_levels JSONB NOT NULL DEFAULT '[]',

    -- Stop loss
    stop_loss DECIMAL(5, 4) NOT NULL DEFAULT 0.5,

    -- Trailing stop config (JSONB)
    trailing_stop JSONB NOT NULL DEFAULT '{"enabled": false, "activation_multiplier": 2.0, "distance_percentage": 30.0}',

    -- Time rules (JSONB)
    time_rules JSONB NOT NULL DEFAULT '{"max_hold_hours": null, "stagnation_exit_enabled": false, "stagnation_threshold_pct": 5.0, "stagnation_hours": 24}',

    -- Moonbag config (JSONB)
    moonbag JSONB NOT NULL DEFAULT '{"percentage": 0.0, "stop_loss": null}',

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,

    -- Constraints
    CONSTRAINT valid_preset CHECK (preset IN ('conservative', 'balanced', 'moonbag_aggressive', 'quick_flip', 'diamond_hands', 'custom')),
    CONSTRAINT valid_stop_loss CHECK (stop_loss >= 0.1 AND stop_loss <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_exit_strategies_preset ON exit_strategies(preset);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_default ON exit_strategies(is_default);

-- Exit strategy assignments to tiers
CREATE TABLE IF NOT EXISTS exit_strategy_assignments (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES exit_strategies(id) ON DELETE CASCADE,
    conviction_tier TEXT,
    position_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Either tier or position must be set
    CONSTRAINT assignment_target CHECK (
        (conviction_tier IS NOT NULL AND position_id IS NULL) OR
        (conviction_tier IS NULL AND position_id IS NOT NULL)
    ),
    CONSTRAINT valid_tier CHECK (conviction_tier IS NULL OR conviction_tier IN ('high', 'standard'))
);

CREATE INDEX IF NOT EXISTS idx_assignments_tier ON exit_strategy_assignments(conviction_tier) WHERE conviction_tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_assignments_position ON exit_strategy_assignments(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_assignments_active ON exit_strategy_assignments(is_active);

-- RLS Policies
ALTER TABLE exit_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE exit_strategy_assignments ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on exit_strategies"
ON exit_strategies FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on exit_strategy_assignments"
ON exit_strategy_assignments FOR ALL TO service_role USING (true);

-- Note: Default presets are seeded by application on startup
```

## Implementation Tasks

- [ ] Create `src/walltrack/models/exit_strategy.py` with all models
- [ ] Create `src/walltrack/constants/exit_presets.py` with 5 default presets
- [ ] Create `src/walltrack/repositories/exit_strategy_repository.py`
- [ ] Implement preset initialization on startup
- [ ] Create `src/walltrack/api/routes/exit_strategies.py`
- [ ] Implement custom strategy validation
- [ ] Implement tier assignment functionality
- [ ] Add database migrations
- [ ] Write comprehensive unit tests

## Definition of Done

- [ ] Exit strategy model complete with all components (take profit, trailing, time rules, moonbag)
- [ ] Five default presets seeded on startup
- [ ] Custom strategies can be created/updated/deleted
- [ ] Default presets cannot be modified or deleted
- [ ] Strategies can be assigned to conviction tiers
- [ ] All strategies stored in Supabase
- [ ] Unit tests pass with >90% coverage
