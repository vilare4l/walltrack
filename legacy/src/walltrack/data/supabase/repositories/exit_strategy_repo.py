"""Repository for exit strategy storage and retrieval."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

from walltrack.constants.exit_presets import DEFAULT_PRESETS
from walltrack.models.exit_strategy import (
    ExitStrategy,
    ExitStrategyAssignment,
    MoonbagConfig,
    StrategyPreset,
    TakeProfitLevel,
    TimeRulesConfig,
    TrailingStopConfig,
)

logger = structlog.get_logger(__name__)


class ExitStrategyRepository:
    """Repository for exit strategy storage and retrieval."""

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize repository with Supabase client."""
        self._client = client

    async def initialize_presets(self) -> int:
        """Seed default preset strategies if not present.

        Returns:
            Number of presets inserted
        """
        inserted = 0

        for preset in DEFAULT_PRESETS:
            try:
                existing = (
                    await self._client.table("exit_strategies")
                    .select("id")
                    .eq("id", preset.id)
                    .execute()
                )

                if not existing.data:
                    await self.create(preset)
                    inserted += 1
                    logger.info("exit_preset_seeded", name=preset.name, id=preset.id)
            except Exception as e:
                logger.warning("exit_preset_seed_failed", name=preset.name, error=str(e))

        return inserted

    async def create(self, strategy: ExitStrategy) -> ExitStrategy:
        """Create new exit strategy."""
        data = self._serialize_strategy(strategy)

        result = await self._client.table("exit_strategies").insert(data).execute()

        logger.info("exit_strategy_created", id=strategy.id, name=strategy.name)
        return self._deserialize_strategy(result.data[0])

    async def update(self, strategy: ExitStrategy) -> ExitStrategy:
        """Update existing exit strategy."""
        strategy.updated_at = datetime.now(UTC)
        data = self._serialize_strategy(strategy)

        result = (
            await self._client.table("exit_strategies")
            .update(data)
            .eq("id", strategy.id)
            .execute()
        )

        logger.info("exit_strategy_updated", id=strategy.id)
        return self._deserialize_strategy(result.data[0])

    async def get_by_id(self, strategy_id: str) -> ExitStrategy | None:
        """Get strategy by ID."""
        try:
            result = (
                await self._client.table("exit_strategies")
                .select("*")
                .eq("id", strategy_id)
                .single()
                .execute()
            )

            if result.data:
                return self._deserialize_strategy(result.data)
        except Exception:
            pass
        return None

    async def get_by_name(self, name: str) -> ExitStrategy | None:
        """Get strategy by name."""
        try:
            result = (
                await self._client.table("exit_strategies")
                .select("*")
                .eq("name", name)
                .single()
                .execute()
            )

            if result.data:
                return self._deserialize_strategy(result.data)
        except Exception:
            pass
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
        result = (
            await self._client.table("exit_strategies")
            .select("*")
            .eq("is_default", True)
            .execute()
        )
        return [self._deserialize_strategy(row) for row in result.data]

    async def delete(self, strategy_id: str) -> bool:
        """Delete strategy (cannot delete defaults)."""
        strategy = await self.get_by_id(strategy_id)
        if strategy and strategy.is_default:
            logger.warning("cannot_delete_default_strategy", id=strategy_id)
            return False

        await self._client.table("exit_strategies").delete().eq("id", strategy_id).execute()

        logger.info("exit_strategy_deleted", id=strategy_id)
        return True

    # === Assignments ===

    async def get_assignment_for_tier(self, tier: str) -> ExitStrategy | None:
        """Get exit strategy assigned to conviction tier."""
        try:
            result = (
                await self._client.table("exit_strategy_assignments")
                .select("strategy_id")
                .eq("conviction_tier", tier)
                .eq("is_active", True)
                .single()
                .execute()
            )

            if result.data:
                return await self.get_by_id(result.data["strategy_id"])
        except Exception:
            pass
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

        await (
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

        logger.info("exit_strategy_assigned", strategy_id=strategy_id, tier=tier)
        return assignment

    # === Serialization ===

    def _serialize_strategy(self, strategy: ExitStrategy) -> dict[str, Any]:
        """Serialize strategy for database storage."""
        return {
            "id": strategy.id,
            "name": strategy.name,
            "description": strategy.description,
            "preset": strategy.preset.value,
            "is_default": strategy.is_default,
            "take_profit_levels": [
                {
                    "trigger_multiplier": tp.trigger_multiplier,
                    "sell_percentage": tp.sell_percentage,
                }
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

    def _deserialize_strategy(self, data: dict[str, Any]) -> ExitStrategy:
        """Deserialize strategy from database."""
        tp_levels = [TakeProfitLevel(**tp) for tp in data.get("take_profit_levels", [])]

        trailing = data.get("trailing_stop", {})
        time_rules = data.get("time_rules", {})
        moonbag = data.get("moonbag", {})

        created_at = data.get("created_at", "")
        updated_at = data.get("updated_at", "")

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

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
            created_at=created_at,
            updated_at=updated_at,
            created_by=data.get("created_by"),
        )


# Singleton
_repo: ExitStrategyRepository | None = None


async def get_exit_strategy_repository() -> ExitStrategyRepository:
    """Get or create exit strategy repository singleton."""
    global _repo
    if _repo is None:
        from walltrack.data.supabase.client import (  # noqa: PLC0415
            get_supabase_client,
        )

        client = await get_supabase_client()
        _repo = ExitStrategyRepository(client)
    return _repo
