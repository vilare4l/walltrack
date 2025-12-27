# Story 11.11: Assignment - Stratégie par Conviction Tier

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: done
- **Priority**: P1 - High
- **Story Points**: 3
- **Depends on**: Story 11-7 (Exit Strategy CRUD), Story 11-2 (ConfigService)

## User Story

**As a** trader,
**I want** exit strategies automatically assigned based on conviction tier,
**So that** high conviction trades get appropriate exit rules.

## Acceptance Criteria

### AC 1: Default Strategy Assignment
**Given** a position is created with standard conviction
**When** no explicit strategy is assigned
**Then** the default standard strategy is used
**And** it comes from `exit_config.default_strategy_standard_id`

### AC 2: High Conviction Strategy
**Given** a position is created with high conviction
**When** signal score >= high conviction threshold
**Then** the high conviction strategy is assigned
**And** it comes from `exit_config.default_strategy_high_conviction_id`

### AC 3: Manual Override
**Given** a position with auto-assigned strategy
**When** I manually select a different strategy
**Then** the override is used instead
**And** the change is logged

### AC 4: Fallback on Missing Strategy
**Given** the configured default strategy doesn't exist
**When** a position is created
**Then** a built-in fallback strategy is used
**And** a warning is logged

### AC 5: Strategy Change on Position
**Given** an open position with an assigned strategy
**When** I change the strategy
**Then** the new strategy takes effect immediately
**And** exit monitoring uses new rules

## Technical Specifications

### Exit Strategy Assigner

**src/walltrack/services/exit/strategy_assigner.py:**
```python
"""Exit strategy assignment based on conviction tier."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from walltrack.services.config.config_service import ConfigService, get_config_service
from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyService,
    get_exit_strategy_service,
)

logger = structlog.get_logger(__name__)


class ConvictionTier:
    """Conviction tier definitions."""
    STANDARD = "standard"
    HIGH = "high"
    LOW = "low"


class ExitStrategyAssigner:
    """
    Assigns exit strategies based on conviction tier.

    Uses ConfigService for default strategy IDs.
    Supports manual override.
    """

    def __init__(
        self,
        config_service: ConfigService,
        strategy_service: ExitStrategyService,
    ):
        self.config = config_service
        self.strategy_service = strategy_service

    async def determine_conviction_tier(
        self,
        signal_score: Decimal,
    ) -> str:
        """
        Determine conviction tier from signal score.

        Returns:
            ConvictionTier value
        """
        high_threshold = await self.config.get(
            "trading.high_conviction_threshold",
            Decimal("0.85")
        )

        if signal_score >= high_threshold:
            return ConvictionTier.HIGH

        return ConvictionTier.STANDARD

    async def get_default_strategy_id(
        self,
        conviction_tier: str,
    ) -> Optional[str]:
        """
        Get default strategy ID for a conviction tier.

        Returns:
            Strategy ID or None if not configured
        """
        if conviction_tier == ConvictionTier.HIGH:
            return await self.config.get(
                "exit.default_strategy_high_conviction_id",
                None
            )
        else:
            return await self.config.get(
                "exit.default_strategy_standard_id",
                None
            )

    async def get_strategy_for_position(
        self,
        signal_score: Decimal,
        override_strategy_id: Optional[str] = None,
    ) -> Optional[ExitStrategy]:
        """
        Get the appropriate exit strategy for a position.

        Args:
            signal_score: The signal score
            override_strategy_id: Optional manual override

        Returns:
            ExitStrategy or None
        """
        # Check for manual override
        if override_strategy_id:
            strategy = await self.strategy_service.get(override_strategy_id)
            if strategy:
                logger.info(
                    "strategy_override_used",
                    strategy_id=override_strategy_id,
                    strategy_name=strategy.name,
                )
                return strategy
            logger.warning(
                "override_strategy_not_found",
                strategy_id=override_strategy_id,
            )

        # Determine tier and get default
        tier = await self.determine_conviction_tier(signal_score)
        default_id = await self.get_default_strategy_id(tier)

        if default_id:
            strategy = await self.strategy_service.get(default_id)
            if strategy:
                logger.debug(
                    "default_strategy_assigned",
                    tier=tier,
                    strategy_id=default_id,
                    strategy_name=strategy.name,
                )
                return strategy
            logger.warning(
                "default_strategy_not_found",
                tier=tier,
                strategy_id=default_id,
            )

        # Fallback to active strategy by name
        fallback_name = "High Conviction" if tier == ConvictionTier.HIGH else "Standard"
        strategy = await self.strategy_service.get_active_by_name(fallback_name)

        if strategy:
            logger.info(
                "fallback_strategy_used",
                tier=tier,
                strategy_name=strategy.name,
            )
            return strategy

        logger.error(
            "no_strategy_available",
            tier=tier,
        )
        return None

    async def assign_strategy_to_position(
        self,
        position_id: str,
        signal_score: Decimal,
        override_strategy_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Assign strategy to a position and update database.

        Returns:
            Assigned strategy ID or None
        """
        strategy = await self.get_strategy_for_position(
            signal_score=signal_score,
            override_strategy_id=override_strategy_id,
        )

        if not strategy:
            return None

        # Update position in database
        from walltrack.data.supabase.client import get_supabase_client
        client = await get_supabase_client()

        await client.table("positions") \
            .update({"exit_strategy_id": strategy.id}) \
            .eq("id", position_id) \
            .execute()

        logger.info(
            "strategy_assigned_to_position",
            position_id=position_id,
            strategy_id=strategy.id,
            strategy_name=strategy.name,
        )

        return strategy.id

    async def change_position_strategy(
        self,
        position_id: str,
        new_strategy_id: str,
    ) -> bool:
        """
        Change the exit strategy for an existing position.

        Returns:
            True if successful
        """
        strategy = await self.strategy_service.get(new_strategy_id)
        if not strategy:
            logger.error("strategy_not_found", strategy_id=new_strategy_id)
            return False

        from walltrack.data.supabase.client import get_supabase_client
        client = await get_supabase_client()

        result = await client.table("positions") \
            .update({
                "exit_strategy_id": new_strategy_id,
                "exit_strategy_changed_at": "now()",
            }) \
            .eq("id", position_id) \
            .execute()

        if result.data:
            logger.info(
                "position_strategy_changed",
                position_id=position_id,
                new_strategy_id=new_strategy_id,
                strategy_name=strategy.name,
            )
            return True

        return False


# Singleton
_assigner: Optional[ExitStrategyAssigner] = None


async def get_exit_strategy_assigner() -> ExitStrategyAssigner:
    """Get or create exit strategy assigner singleton."""
    global _assigner

    if _assigner is None:
        config = await get_config_service()
        strategy_service = await get_exit_strategy_service()
        _assigner = ExitStrategyAssigner(config, strategy_service)

    return _assigner
```

### Position Integration

**src/walltrack/services/position/position_service.py (additions):**
```python
# Add to existing PositionService class

async def create_position_with_strategy(
    self,
    signal: "Signal",
    size_sol: Decimal,
    entry_price: Decimal,
    override_strategy_id: Optional[str] = None,
) -> "Position":
    """
    Create position with automatic exit strategy assignment.

    Args:
        signal: The signal that triggered the position
        size_sol: Position size in SOL
        entry_price: Entry price
        override_strategy_id: Optional manual strategy override

    Returns:
        Created position with strategy assigned
    """
    from walltrack.services.exit.strategy_assigner import get_exit_strategy_assigner

    # Create the position first
    position = await self.create_position(
        signal=signal,
        size_sol=size_sol,
        entry_price=entry_price,
    )

    # Assign exit strategy
    assigner = await get_exit_strategy_assigner()
    strategy_id = await assigner.assign_strategy_to_position(
        position_id=position.id,
        signal_score=signal.score,
        override_strategy_id=override_strategy_id,
    )

    if strategy_id:
        position.exit_strategy_id = strategy_id

    return position
```

### Position Model Addition

**Add to positions table:**
```sql
-- Add to positions table (migration)
ALTER TABLE positions
ADD COLUMN IF NOT EXISTS exit_strategy_id UUID REFERENCES exit_strategies(id),
ADD COLUMN IF NOT EXISTS exit_strategy_changed_at TIMESTAMPTZ;

-- Index for strategy lookups
CREATE INDEX IF NOT EXISTS idx_positions_exit_strategy
ON positions(exit_strategy_id);
```

### Exit Config Update

**Add to exit_config table:**
```sql
-- Ensure exit_config has strategy reference columns
ALTER TABLE exit_config
ADD COLUMN IF NOT EXISTS default_strategy_standard_id UUID REFERENCES exit_strategies(id),
ADD COLUMN IF NOT EXISTS default_strategy_high_conviction_id UUID REFERENCES exit_strategies(id);

-- Set defaults to active strategies
UPDATE exit_config
SET
    default_strategy_standard_id = (
        SELECT id FROM exit_strategies
        WHERE name = 'Standard' AND status = 'active'
        LIMIT 1
    ),
    default_strategy_high_conviction_id = (
        SELECT id FROM exit_strategies
        WHERE name = 'High Conviction' AND status = 'active'
        LIMIT 1
    )
WHERE status = 'active';
```

### UI Integration

**src/walltrack/ui/components/position_strategy_selector.py:**
```python
"""Position strategy selector component."""

import gradio as gr

from walltrack.services.exit.exit_strategy_service import get_exit_strategy_service
from walltrack.services.exit.strategy_assigner import get_exit_strategy_assigner


async def build_position_strategy_selector(position_id: str) -> gr.Blocks:
    """Build strategy selector for a position."""
    strategy_service = await get_exit_strategy_service()
    assigner = await get_exit_strategy_assigner()

    with gr.Blocks() as selector:
        gr.Markdown("### Exit Strategy")

        strategy_dropdown = gr.Dropdown(
            label="Exit Strategy",
            choices=[],
        )

        change_btn = gr.Button("Change Strategy", size="sm")
        status_text = gr.Textbox(label="Status", interactive=False)

        async def load_strategies():
            strategies = await strategy_service.list_all()
            return gr.update(
                choices=[(f"{s.name} (v{s.version})", s.id) for s in strategies]
            )

        async def change_strategy(strategy_id):
            if not strategy_id:
                return "Select a strategy"

            success = await assigner.change_position_strategy(position_id, strategy_id)
            if success:
                return "Strategy changed successfully"
            return "Failed to change strategy"

        selector.load(load_strategies, [], [strategy_dropdown])
        change_btn.click(change_strategy, [strategy_dropdown], [status_text])

    return selector
```

## Implementation Tasks

- [x] Create ConvictionTier enum/class
- [x] Create ExitStrategyAssigner class
- [x] Implement determine_conviction_tier()
- [x] Implement get_default_strategy_id()
- [x] Implement get_strategy_for_position()
- [x] Implement assign_strategy_to_position()
- [x] Implement change_position_strategy()
- [x] Add exit_strategy_id to positions table
- [x] Add default strategy columns to exit_config
- [x] Integrate with position creation flow
- [x] Create UI selector component
- [x] Write unit tests

## Definition of Done

- [x] Auto-assignment works for standard tier
- [x] Auto-assignment works for high conviction
- [x] Manual override takes precedence
- [x] Fallback works when strategy missing
- [x] Position update changes strategy
- [x] UI selector functional
- [x] All tests passing

## File List

### New Files
- `src/walltrack/services/exit/strategy_assigner.py` - Assignment logic
- `src/walltrack/ui/components/position_strategy_selector.py` - UI component
- `tests/unit/services/exit/test_strategy_assigner.py` - Tests

### Modified Files
- `src/walltrack/services/position/position_service.py` - Add strategy assignment
- `migrations/V8__config_tables.sql` - Add strategy columns to exit_config
- `migrations/V9__orders.sql` - Add exit_strategy_id to positions
