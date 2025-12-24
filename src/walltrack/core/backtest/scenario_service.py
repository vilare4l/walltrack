"""Service for managing backtest scenarios."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from walltrack.core.backtest.scenario import (
    PRESET_SCENARIOS,
    Scenario,
    ScenarioCategory,
)
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


class ScenarioService:
    """Service for CRUD operations on scenarios.

    Handles persistence and retrieval of backtest scenarios,
    including preset scenarios and user-defined ones.
    """

    async def get_all_scenarios(
        self,
        category: ScenarioCategory | None = None,
        include_presets: bool = True,
    ) -> list[Scenario]:
        """Get all scenarios, optionally filtered.

        Args:
            category: Optional category to filter by.
            include_presets: Whether to include preset scenarios.

        Returns:
            List of scenarios sorted by name.
        """
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

    async def get_scenario(self, scenario_id: UUID) -> Scenario | None:
        """Get a scenario by ID.

        Args:
            scenario_id: UUID of the scenario.

        Returns:
            Scenario if found, None otherwise.
        """
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
        """Create a new scenario.

        Args:
            scenario: Scenario to create.

        Returns:
            Created scenario with timestamps set.
        """
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
    ) -> Scenario | None:
        """Update an existing scenario.

        Args:
            scenario_id: UUID of the scenario to update.
            updates: Dictionary of fields to update.

        Returns:
            Updated scenario if found.

        Raises:
            ValueError: If attempting to update a preset scenario.
        """
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
        """Delete a scenario.

        Args:
            scenario_id: UUID of the scenario to delete.

        Returns:
            True if deleted.

        Raises:
            ValueError: If attempting to delete a preset scenario.
        """
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
        """Duplicate a scenario with a new name.

        Args:
            scenario_id: UUID of the scenario to duplicate.
            new_name: Name for the duplicate.

        Returns:
            New scenario with copied configuration.

        Raises:
            ValueError: If original scenario not found.
        """
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
        """Export scenario as JSON string.

        Args:
            scenario_id: UUID of the scenario.

        Returns:
            JSON string representation.

        Raises:
            ValueError: If scenario not found.
        """
        scenario = await self.get_scenario(scenario_id)
        if not scenario:
            raise ValueError(f"Scenario {scenario_id} not found")
        return scenario.to_json()

    async def import_scenario(self, json_str: str) -> Scenario:
        """Import scenario from JSON string.

        Args:
            json_str: JSON string to import.

        Returns:
            Created scenario with new ID.
        """
        scenario = Scenario.from_json(json_str)
        # Generate new ID to avoid conflicts
        scenario.id = uuid4()
        scenario.is_preset = False
        return await self.create_scenario(scenario)

    def compare_to_live(self, scenario: Scenario, live_config: dict) -> dict:
        """Compare scenario to live configuration.

        Args:
            scenario: Scenario to compare.
            live_config: Current live configuration.

        Returns:
            Dictionary of differences.
        """
        differences = {}

        # Compare scoring weights
        weight_fields = [
            "wallet_weight",
            "cluster_weight",
            "token_weight",
            "context_weight",
        ]
        for weight in weight_fields:
            scenario_val = getattr(scenario.scoring_weights, weight)
            live_val = live_config.get("scoring_weights", {}).get(weight)
            if live_val and scenario_val != Decimal(str(live_val)):
                differences[f"scoring_weights.{weight}"] = {
                    "scenario": float(scenario_val),
                    "live": float(live_val),
                }

        # Compare threshold
        live_threshold = live_config.get("score_threshold", 0.7)
        if scenario.score_threshold != Decimal(str(live_threshold)):
            differences["score_threshold"] = {
                "scenario": float(scenario.score_threshold),
                "live": live_threshold,
            }

        # Compare position sizing
        live_position = live_config.get("base_position_sol", 0.1)
        if scenario.base_position_sol != Decimal(str(live_position)):
            differences["base_position_sol"] = {
                "scenario": float(scenario.base_position_sol),
                "live": live_position,
            }

        return differences


# Singleton
_scenario_service: ScenarioService | None = None


async def get_scenario_service() -> ScenarioService:
    """Get scenario service singleton.

    Returns:
        ScenarioService singleton instance.
    """
    global _scenario_service
    if _scenario_service is None:
        _scenario_service = ScenarioService()
    return _scenario_service
