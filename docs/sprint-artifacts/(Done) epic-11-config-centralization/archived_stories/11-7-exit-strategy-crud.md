# Story 11.7: Exit Strategy - CRUD et Versioning

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 5
- **Depends on**: Story 11-1 (Schema Migration)

## ⚠️ Important Context

**La table `exit_strategies` existe déjà** (créée dans `src/walltrack/data/supabase/migrations/008_exit_strategies.sql`) avec une structure différente:

| Actuel (008) | Cible (V14) |
|--------------|-------------|
| id TEXT | id TEXT (inchangé) |
| is_default BOOLEAN | status ENUM (draft/active/archived) |
| Pas de version | version INTEGER |
| take_profit_levels JSONB | rules JSONB (structure unifiée) |
| stop_loss DECIMAL | Intégré dans rules |
| trailing_stop JSONB | Intégré dans rules |
| time_rules JSONB | max_hold_hours, stagnation_* colonnes |

Cette story **AJOUTE le lifecycle** via ALTER TABLE et **MIGRE les données existantes**.

## User Story

**As a** trader,
**I want** to create, edit, and version exit strategies,
**So that** I can manage multiple strategies and track their evolution.

## Acceptance Criteria

### AC 1: Create Exit Strategy
**Given** I have the required parameters
**When** I call `create_strategy()`
**Then** a new strategy is created with version 1
**And** status is set to "draft"

### AC 2: Edit Draft Strategy
**Given** a strategy in "draft" status
**When** I modify parameters
**Then** the draft is updated in place
**And** no new version is created

### AC 3: Activate Strategy
**Given** a draft strategy
**When** I activate it
**Then** status changes to "active"
**And** activated_at is set
**And** previous active strategy (if any) is archived

### AC 4: Version on Edit Active
**Given** an active strategy
**When** I edit it
**Then** a new version is created as draft
**And** the active version remains unchanged
**And** I can continue editing the draft

### AC 5: List Strategies
**Given** multiple strategies exist
**When** I list strategies
**Then** I see all versions grouped by base name
**And** active version is highlighted

### AC 6: Clone Strategy
**Given** an existing strategy
**When** I clone it
**Then** a new strategy is created with version 1
**And** name has "(copy)" suffix
**And** status is "draft"

## Technical Specifications

### Exit Strategy Service

**src/walltrack/services/exit/exit_strategy_service.py:**
```python
"""Exit strategy CRUD service with versioning."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from walltrack.data.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


class ExitStrategyRule(BaseModel):
    """Single exit rule configuration."""
    rule_type: str  # "take_profit", "stop_loss", "trailing_stop", "time_based"
    trigger_pct: Optional[Decimal] = None
    exit_pct: Decimal = Decimal("100")  # Percentage of position to exit
    priority: int = 0  # Lower = higher priority
    enabled: bool = True
    params: dict = Field(default_factory=dict)


class ExitStrategyCreate(BaseModel):
    """Parameters for creating an exit strategy."""
    name: str
    description: Optional[str] = None
    rules: list[ExitStrategyRule]
    max_hold_hours: int = 24
    stagnation_hours: int = 6
    stagnation_threshold_pct: Decimal = Decimal("2.0")


class ExitStrategyUpdate(BaseModel):
    """Parameters for updating an exit strategy."""
    name: Optional[str] = None
    description: Optional[str] = None
    rules: Optional[list[ExitStrategyRule]] = None
    max_hold_hours: Optional[int] = None
    stagnation_hours: Optional[int] = None
    stagnation_threshold_pct: Optional[Decimal] = None


class ExitStrategy(BaseModel):
    """Full exit strategy model."""
    id: str
    name: str
    description: Optional[str]
    version: int
    status: str  # draft, active, archived
    rules: list[ExitStrategyRule]
    max_hold_hours: int
    stagnation_hours: int
    stagnation_threshold_pct: Decimal
    created_at: datetime
    updated_at: datetime
    activated_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None


class ExitStrategyService:
    """Service for exit strategy CRUD operations with versioning."""

    def __init__(self):
        self._client = None

    async def _get_client(self):
        """Get or initialize Supabase client."""
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    async def create(self, data: ExitStrategyCreate) -> ExitStrategy:
        """Create a new exit strategy."""
        client = await self._get_client()

        strategy_data = {
            "id": str(uuid4()),
            "name": data.name,
            "description": data.description,
            "version": 1,
            "status": "draft",
            "rules": [r.model_dump() for r in data.rules],
            "max_hold_hours": data.max_hold_hours,
            "stagnation_hours": data.stagnation_hours,
            "stagnation_threshold_pct": str(data.stagnation_threshold_pct),
        }

        result = await client.table("exit_strategies") \
            .insert(strategy_data) \
            .execute()

        if not result.data:
            raise ValueError("Failed to create exit strategy")

        logger.info("exit_strategy_created", id=strategy_data["id"], name=data.name)

        return self._parse_strategy(result.data[0])

    async def get(self, strategy_id: str) -> Optional[ExitStrategy]:
        """Get exit strategy by ID."""
        client = await self._get_client()

        result = await client.table("exit_strategies") \
            .select("*") \
            .eq("id", strategy_id) \
            .single() \
            .execute()

        if not result.data:
            return None

        return self._parse_strategy(result.data)

    async def get_active_by_name(self, name: str) -> Optional[ExitStrategy]:
        """Get the active version of a strategy by name."""
        client = await self._get_client()

        result = await client.table("exit_strategies") \
            .select("*") \
            .eq("name", name) \
            .eq("status", "active") \
            .single() \
            .execute()

        if not result.data:
            return None

        return self._parse_strategy(result.data)

    async def list_all(
        self,
        include_archived: bool = False,
    ) -> list[ExitStrategy]:
        """List all exit strategies."""
        client = await self._get_client()

        query = client.table("exit_strategies").select("*")

        if not include_archived:
            query = query.neq("status", "archived")

        query = query.order("name").order("version", desc=True)

        result = await query.execute()

        return [self._parse_strategy(s) for s in (result.data or [])]

    async def list_by_name(self, name: str) -> list[ExitStrategy]:
        """List all versions of a strategy by name."""
        client = await self._get_client()

        result = await client.table("exit_strategies") \
            .select("*") \
            .eq("name", name) \
            .order("version", desc=True) \
            .execute()

        return [self._parse_strategy(s) for s in (result.data or [])]

    async def update(
        self,
        strategy_id: str,
        data: ExitStrategyUpdate,
    ) -> ExitStrategy:
        """
        Update an exit strategy.

        If strategy is draft: update in place.
        If strategy is active: create new draft version.
        """
        client = await self._get_client()

        # Get current strategy
        current = await self.get(strategy_id)
        if not current:
            raise ValueError(f"Strategy not found: {strategy_id}")

        if current.status == "archived":
            raise ValueError("Cannot update archived strategy")

        if current.status == "draft":
            # Update in place
            return await self._update_draft(strategy_id, data)
        else:
            # Create new version
            return await self._create_new_version(current, data)

    async def _update_draft(
        self,
        strategy_id: str,
        data: ExitStrategyUpdate,
    ) -> ExitStrategy:
        """Update a draft strategy in place."""
        client = await self._get_client()

        update_data = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        if data.rules is not None:
            update_data["rules"] = [r.model_dump() for r in data.rules]
        if data.max_hold_hours is not None:
            update_data["max_hold_hours"] = data.max_hold_hours
        if data.stagnation_hours is not None:
            update_data["stagnation_hours"] = data.stagnation_hours
        if data.stagnation_threshold_pct is not None:
            update_data["stagnation_threshold_pct"] = str(data.stagnation_threshold_pct)

        update_data["updated_at"] = datetime.utcnow().isoformat()

        result = await client.table("exit_strategies") \
            .update(update_data) \
            .eq("id", strategy_id) \
            .execute()

        if not result.data:
            raise ValueError("Failed to update strategy")

        logger.info("exit_strategy_updated", id=strategy_id)

        return self._parse_strategy(result.data[0])

    async def _create_new_version(
        self,
        current: ExitStrategy,
        data: ExitStrategyUpdate,
    ) -> ExitStrategy:
        """Create a new version of an active strategy."""
        client = await self._get_client()

        # Get highest version for this name
        versions = await self.list_by_name(current.name)
        max_version = max(v.version for v in versions) if versions else 0

        # Build new strategy data
        new_data = {
            "id": str(uuid4()),
            "name": data.name or current.name,
            "description": data.description if data.description is not None else current.description,
            "version": max_version + 1,
            "status": "draft",
            "rules": [r.model_dump() for r in data.rules] if data.rules else [r.model_dump() for r in current.rules],
            "max_hold_hours": data.max_hold_hours or current.max_hold_hours,
            "stagnation_hours": data.stagnation_hours or current.stagnation_hours,
            "stagnation_threshold_pct": str(data.stagnation_threshold_pct or current.stagnation_threshold_pct),
        }

        result = await client.table("exit_strategies") \
            .insert(new_data) \
            .execute()

        if not result.data:
            raise ValueError("Failed to create new version")

        logger.info(
            "exit_strategy_version_created",
            id=new_data["id"],
            name=current.name,
            version=new_data["version"]
        )

        return self._parse_strategy(result.data[0])

    async def activate(self, strategy_id: str) -> ExitStrategy:
        """Activate a draft strategy."""
        client = await self._get_client()

        # Get strategy
        strategy = await self.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        if strategy.status != "draft":
            raise ValueError(f"Can only activate draft strategies, current status: {strategy.status}")

        # Archive current active strategy with same name
        await client.table("exit_strategies") \
            .update({
                "status": "archived",
                "archived_at": datetime.utcnow().isoformat()
            }) \
            .eq("name", strategy.name) \
            .eq("status", "active") \
            .execute()

        # Activate the new one
        result = await client.table("exit_strategies") \
            .update({
                "status": "active",
                "activated_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", strategy_id) \
            .execute()

        if not result.data:
            raise ValueError("Failed to activate strategy")

        logger.info("exit_strategy_activated", id=strategy_id, name=strategy.name)

        return self._parse_strategy(result.data[0])

    async def archive(self, strategy_id: str) -> ExitStrategy:
        """Archive an exit strategy."""
        client = await self._get_client()

        result = await client.table("exit_strategies") \
            .update({
                "status": "archived",
                "archived_at": datetime.utcnow().isoformat()
            }) \
            .eq("id", strategy_id) \
            .execute()

        if not result.data:
            raise ValueError("Failed to archive strategy")

        logger.info("exit_strategy_archived", id=strategy_id)

        return self._parse_strategy(result.data[0])

    async def clone(self, strategy_id: str, new_name: Optional[str] = None) -> ExitStrategy:
        """Clone an existing strategy."""
        # Get source strategy
        source = await self.get(strategy_id)
        if not source:
            raise ValueError(f"Strategy not found: {strategy_id}")

        # Create clone
        clone_data = ExitStrategyCreate(
            name=new_name or f"{source.name} (copy)",
            description=source.description,
            rules=source.rules,
            max_hold_hours=source.max_hold_hours,
            stagnation_hours=source.stagnation_hours,
            stagnation_threshold_pct=source.stagnation_threshold_pct,
        )

        cloned = await self.create(clone_data)

        logger.info("exit_strategy_cloned", source_id=strategy_id, new_id=cloned.id)

        return cloned

    async def delete_draft(self, strategy_id: str) -> bool:
        """Delete a draft strategy (cannot delete active/archived)."""
        client = await self._get_client()

        strategy = await self.get(strategy_id)
        if not strategy:
            raise ValueError(f"Strategy not found: {strategy_id}")

        if strategy.status != "draft":
            raise ValueError("Can only delete draft strategies")

        await client.table("exit_strategies") \
            .delete() \
            .eq("id", strategy_id) \
            .execute()

        logger.info("exit_strategy_deleted", id=strategy_id)

        return True

    def _parse_strategy(self, data: dict) -> ExitStrategy:
        """Parse database row to ExitStrategy model."""
        rules = [ExitStrategyRule(**r) for r in (data.get("rules") or [])]

        return ExitStrategy(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            version=data["version"],
            status=data["status"],
            rules=rules,
            max_hold_hours=data["max_hold_hours"],
            stagnation_hours=data["stagnation_hours"],
            stagnation_threshold_pct=Decimal(str(data["stagnation_threshold_pct"])),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            activated_at=datetime.fromisoformat(data["activated_at"].replace("Z", "+00:00")) if data.get("activated_at") else None,
            archived_at=datetime.fromisoformat(data["archived_at"].replace("Z", "+00:00")) if data.get("archived_at") else None,
        )


# Singleton
_exit_strategy_service: Optional[ExitStrategyService] = None


async def get_exit_strategy_service() -> ExitStrategyService:
    """Get or create exit strategy service singleton."""
    global _exit_strategy_service

    if _exit_strategy_service is None:
        _exit_strategy_service = ExitStrategyService()

    return _exit_strategy_service
```

### Database Migration

**migrations/V14__exit_strategies_lifecycle.sql:**
```sql
-- ============================================
-- Exit Strategies Lifecycle Migration
-- Adds versioning and status to existing table
-- ============================================

-- Add lifecycle columns
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS status VARCHAR(20) DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS activated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

-- Add rules column (unified structure)
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS rules JSONB DEFAULT '[]';

-- Add stagnation columns (extracted from time_rules)
ALTER TABLE exit_strategies
    ADD COLUMN IF NOT EXISTS max_hold_hours INTEGER DEFAULT 24,
    ADD COLUMN IF NOT EXISTS stagnation_hours INTEGER DEFAULT 6,
    ADD COLUMN IF NOT EXISTS stagnation_threshold_pct DECIMAL(5,2) DEFAULT 2.0;

-- Migrate existing data: convert is_default to status
UPDATE exit_strategies
SET status = CASE WHEN is_default = true THEN 'active' ELSE 'draft' END,
    activated_at = CASE WHEN is_default = true THEN NOW() ELSE NULL END;

-- Migrate time_rules into separate columns
UPDATE exit_strategies
SET max_hold_hours = COALESCE((time_rules->>'max_hold_hours')::INTEGER, 24),
    stagnation_hours = COALESCE((time_rules->>'stagnation_hours')::INTEGER, 6),
    stagnation_threshold_pct = COALESCE((time_rules->>'stagnation_threshold_pct')::DECIMAL, 2.0);

-- Migrate existing fields to unified rules format
UPDATE exit_strategies
SET rules = (
    SELECT jsonb_agg(rule) FROM (
        -- Take profit levels
        SELECT jsonb_build_object(
            'rule_type', 'take_profit',
            'trigger_pct', (tp->>'multiplier')::DECIMAL * 100,
            'exit_pct', (tp->>'sell_percentage')::DECIMAL,
            'priority', tp_idx,
            'enabled', true,
            'params', '{}'::JSONB
        ) as rule
        FROM jsonb_array_elements(take_profit_levels) WITH ORDINALITY AS t(tp, tp_idx)
        UNION ALL
        -- Stop loss
        SELECT jsonb_build_object(
            'rule_type', 'stop_loss',
            'trigger_pct', -stop_loss * 100,
            'exit_pct', 100,
            'priority', 0,
            'enabled', true,
            'params', '{}'::JSONB
        )
        UNION ALL
        -- Trailing stop (if enabled)
        SELECT jsonb_build_object(
            'rule_type', 'trailing_stop',
            'trigger_pct', -(trailing_stop->>'distance_percentage')::DECIMAL,
            'exit_pct', 100,
            'priority', 10,
            'enabled', (trailing_stop->>'enabled')::BOOLEAN,
            'params', jsonb_build_object('activation_pct', (trailing_stop->>'activation_multiplier')::DECIMAL * 100)
        )
    ) subq
);

-- Drop old columns (optional, can keep for compatibility)
-- ALTER TABLE exit_strategies DROP COLUMN IF EXISTS is_default;
-- ALTER TABLE exit_strategies DROP COLUMN IF EXISTS take_profit_levels;
-- ALTER TABLE exit_strategies DROP COLUMN IF EXISTS trailing_stop;
-- ALTER TABLE exit_strategies DROP COLUMN IF EXISTS time_rules;

-- Add status check constraint
ALTER TABLE exit_strategies
    ADD CONSTRAINT chk_exit_strategy_status
    CHECK (status IN ('draft', 'active', 'archived'));

-- Partial unique index: only one active per name
CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_strategies_single_active
    ON exit_strategies(name) WHERE status = 'active';

-- Add indexes
CREATE INDEX IF NOT EXISTS idx_exit_strategies_status ON exit_strategies(status);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_name_status ON exit_strategies(name, status);
```

### Exit Strategy Preset Templates

**src/walltrack/services/exit/strategy_templates.py:**
```python
"""Pre-defined exit strategy templates."""

from decimal import Decimal

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategyCreate,
    ExitStrategyRule,
)


def get_standard_template() -> ExitStrategyCreate:
    """Standard balanced exit strategy."""
    return ExitStrategyCreate(
        name="Standard",
        description="Balanced exit with 15% TP, 10% SL",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-10"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("15"),
                exit_pct=Decimal("50"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("30"),
                exit_pct=Decimal("100"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="trailing_stop",
                trigger_pct=Decimal("-5"),
                exit_pct=Decimal("100"),
                priority=3,
                params={"activation_pct": 10},
            ),
        ],
        max_hold_hours=24,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("2.0"),
    )


def get_aggressive_template() -> ExitStrategyCreate:
    """Aggressive high-conviction template."""
    return ExitStrategyCreate(
        name="High Conviction",
        description="Let winners run with wide stops",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-15"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("25"),
                exit_pct=Decimal("30"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("50"),
                exit_pct=Decimal("50"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("100"),
                exit_pct=Decimal("100"),
                priority=3,
            ),
            ExitStrategyRule(
                rule_type="trailing_stop",
                trigger_pct=Decimal("-8"),
                exit_pct=Decimal("100"),
                priority=4,
                params={"activation_pct": 20},
            ),
        ],
        max_hold_hours=48,
        stagnation_hours=12,
        stagnation_threshold_pct=Decimal("3.0"),
    )


def get_conservative_template() -> ExitStrategyCreate:
    """Conservative quick exit template."""
    return ExitStrategyCreate(
        name="Conservative",
        description="Tight stops, quick profits",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-5"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("10"),
                exit_pct=Decimal("75"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("20"),
                exit_pct=Decimal("100"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="time_based",
                trigger_pct=None,
                exit_pct=Decimal("100"),
                priority=5,
                params={"max_hours": 12},
            ),
        ],
        max_hold_hours=12,
        stagnation_hours=4,
        stagnation_threshold_pct=Decimal("1.5"),
    )


TEMPLATES = {
    "standard": get_standard_template,
    "aggressive": get_aggressive_template,
    "conservative": get_conservative_template,
}


def get_template(name: str) -> ExitStrategyCreate:
    """Get a template by name."""
    factory = TEMPLATES.get(name.lower())
    if not factory:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATES.keys())}")
    return factory()
```

## Implementation Tasks

- [x] Create ExitStrategyRule model
- [x] Create ExitStrategyCreate/Update models
- [x] Create ExitStrategy full model
- [x] Implement ExitStrategyService class
- [x] Implement create() with versioning
- [x] Implement update() with draft/active handling
- [x] Implement activate() with archive of previous
- [x] Implement clone()
- [x] Add database migration for exit_strategies table
- [x] Create strategy templates
- [x] Write unit tests

## Definition of Done

- [x] CRUD operations work correctly
- [x] Versioning creates new versions on active edit
- [x] Only one active version per name
- [x] Clone creates proper copy
- [x] Templates available
- [x] All tests passing

## File List

### New Files
- `src/walltrack/services/exit/__init__.py` - Package init
- `src/walltrack/services/exit/exit_strategy_service.py` - CRUD service
- `src/walltrack/services/exit/strategy_templates.py` - Templates
- `migrations/V14__exit_strategies_lifecycle.sql` - Lifecycle migration
- `tests/unit/services/exit/test_exit_strategy_service.py` - Tests

### Modified Files
- None (existing table altered, not recreated)
