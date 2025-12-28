"""Exit strategy CRUD service with versioning."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import uuid4

import structlog
from pydantic import BaseModel, Field

from walltrack.data.supabase.client import get_supabase_client

logger = structlog.get_logger(__name__)


class ExitStrategyRule(BaseModel):
    """Single exit rule configuration."""

    rule_type: str  # "take_profit", "stop_loss", "trailing_stop", "time_based"
    trigger_pct: Decimal | None = None
    exit_pct: Decimal = Decimal("100")  # Percentage of position to exit
    priority: int = 0  # Lower = higher priority
    enabled: bool = True
    params: dict[str, Any] = Field(default_factory=dict)


class ExitStrategyCreate(BaseModel):
    """Parameters for creating an exit strategy."""

    name: str
    description: str | None = None
    rules: list[ExitStrategyRule]
    max_hold_hours: int = 24
    stagnation_hours: int = 6
    stagnation_threshold_pct: Decimal = Decimal("2.0")


class ExitStrategyUpdate(BaseModel):
    """Parameters for updating an exit strategy."""

    name: str | None = None
    description: str | None = None
    rules: list[ExitStrategyRule] | None = None
    max_hold_hours: int | None = None
    stagnation_hours: int | None = None
    stagnation_threshold_pct: Decimal | None = None


class ExitStrategy(BaseModel):
    """Full exit strategy model."""

    id: str
    name: str
    description: str | None
    version: int
    status: str  # draft, active, archived
    rules: list[ExitStrategyRule]
    max_hold_hours: int
    stagnation_hours: int
    stagnation_threshold_pct: Decimal
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None = None
    archived_at: datetime | None = None


class ExitStrategyService:
    """Service for exit strategy CRUD operations with versioning."""

    def __init__(self) -> None:
        self._client: Any = None

    async def _get_client(self) -> Any:
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
            "rules": [r.model_dump(mode="json") for r in data.rules],
            "max_hold_hours": data.max_hold_hours,
            "stagnation_hours": data.stagnation_hours,
            "stagnation_threshold_pct": str(data.stagnation_threshold_pct),
        }

        result = (
            await client.table("exit_strategies").insert(strategy_data).execute()
        )

        if not result.data:
            raise ValueError("Failed to create exit strategy")

        logger.info("exit_strategy_created", id=strategy_data["id"], name=data.name)

        return self._parse_strategy(result.data[0])

    async def get(self, strategy_id: str) -> ExitStrategy | None:
        """Get exit strategy by ID."""
        client = await self._get_client()

        result = (
            await client.table("exit_strategies")
            .select("*")
            .eq("id", strategy_id)
            .maybe_single()
            .execute()
        )

        if not result.data:
            return None

        return self._parse_strategy(result.data)

    async def get_active_by_name(self, name: str) -> ExitStrategy | None:
        """Get the active version of a strategy by name."""
        client = await self._get_client()

        result = (
            await client.table("exit_strategies")
            .select("*")
            .eq("name", name)
            .eq("status", "active")
            .maybe_single()
            .execute()
        )

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

        result = (
            await client.table("exit_strategies")
            .select("*")
            .eq("name", name)
            .order("version", desc=True)
            .execute()
        )

        return [self._parse_strategy(s) for s in (result.data or [])]

    async def update(
        self,
        strategy_id: str,
        data: ExitStrategyUpdate,
    ) -> ExitStrategy:
        """Update an exit strategy.

        If strategy is draft: update in place.
        If strategy is active: create new draft version.
        """
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

        update_data: dict[str, Any] = {}
        if data.name is not None:
            update_data["name"] = data.name
        if data.description is not None:
            update_data["description"] = data.description
        if data.rules is not None:
            update_data["rules"] = [r.model_dump(mode="json") for r in data.rules]
        if data.max_hold_hours is not None:
            update_data["max_hold_hours"] = data.max_hold_hours
        if data.stagnation_hours is not None:
            update_data["stagnation_hours"] = data.stagnation_hours
        if data.stagnation_threshold_pct is not None:
            update_data["stagnation_threshold_pct"] = str(data.stagnation_threshold_pct)

        update_data["updated_at"] = datetime.now(UTC).isoformat()

        result = (
            await client.table("exit_strategies")
            .update(update_data)
            .eq("id", strategy_id)
            .execute()
        )

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
        new_rules = (
            [r.model_dump(mode="json") for r in data.rules]
            if data.rules
            else [r.model_dump(mode="json") for r in current.rules]
        )

        new_data = {
            "id": str(uuid4()),
            "name": data.name or current.name,
            "description": (
                data.description if data.description is not None else current.description
            ),
            "version": max_version + 1,
            "status": "draft",
            "rules": new_rules,
            "max_hold_hours": data.max_hold_hours or current.max_hold_hours,
            "stagnation_hours": data.stagnation_hours or current.stagnation_hours,
            "stagnation_threshold_pct": str(
                data.stagnation_threshold_pct or current.stagnation_threshold_pct
            ),
        }

        result = await client.table("exit_strategies").insert(new_data).execute()

        if not result.data:
            raise ValueError("Failed to create new version")

        logger.info(
            "exit_strategy_version_created",
            id=new_data["id"],
            name=current.name,
            version=new_data["version"],
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
            raise ValueError(
                f"Can only activate draft strategies, current status: {strategy.status}"
            )

        # Archive current active strategy with same name
        await (
            client.table("exit_strategies")
            .update(
                {
                    "status": "archived",
                    "archived_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("name", strategy.name)
            .eq("status", "active")
            .execute()
        )

        # Activate the new one
        result = (
            await client.table("exit_strategies")
            .update(
                {
                    "status": "active",
                    "activated_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", strategy_id)
            .execute()
        )

        if not result.data:
            raise ValueError("Failed to activate strategy")

        logger.info("exit_strategy_activated", id=strategy_id, name=strategy.name)

        return self._parse_strategy(result.data[0])

    async def archive(self, strategy_id: str) -> ExitStrategy:
        """Archive an exit strategy."""
        client = await self._get_client()

        result = (
            await client.table("exit_strategies")
            .update(
                {
                    "status": "archived",
                    "archived_at": datetime.now(UTC).isoformat(),
                }
            )
            .eq("id", strategy_id)
            .execute()
        )

        if not result.data:
            raise ValueError("Failed to archive strategy")

        logger.info("exit_strategy_archived", id=strategy_id)

        return self._parse_strategy(result.data[0])

    async def clone(
        self, strategy_id: str, new_name: str | None = None
    ) -> ExitStrategy:
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

        await client.table("exit_strategies").delete().eq("id", strategy_id).execute()

        logger.info("exit_strategy_deleted", id=strategy_id)

        return True

    def _parse_strategy(self, data: dict[str, Any]) -> ExitStrategy:
        """Parse database row to ExitStrategy model."""
        rules = [ExitStrategyRule(**r) for r in (data.get("rules") or [])]

        created_at = data["created_at"]
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        updated_at = data["updated_at"]
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))

        activated_at = data.get("activated_at")
        if activated_at and isinstance(activated_at, str):
            activated_at = datetime.fromisoformat(activated_at.replace("Z", "+00:00"))

        archived_at = data.get("archived_at")
        if archived_at and isinstance(archived_at, str):
            archived_at = datetime.fromisoformat(archived_at.replace("Z", "+00:00"))

        return ExitStrategy(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            version=data.get("version", 1),
            status=data.get("status", "draft"),
            rules=rules,
            max_hold_hours=data.get("max_hold_hours", 24),
            stagnation_hours=data.get("stagnation_hours", 6),
            stagnation_threshold_pct=Decimal(str(data.get("stagnation_threshold_pct", "2.0"))),
            created_at=created_at,
            updated_at=updated_at,
            activated_at=activated_at,
            archived_at=archived_at,
        )


# Singleton
_exit_strategy_service: ExitStrategyService | None = None


async def get_exit_strategy_service() -> ExitStrategyService:
    """Get or create exit strategy service singleton."""
    global _exit_strategy_service

    if _exit_strategy_service is None:
        _exit_strategy_service = ExitStrategyService()

    return _exit_strategy_service


def reset_exit_strategy_service() -> None:
    """Reset the singleton (for testing)."""
    global _exit_strategy_service
    _exit_strategy_service = None
