"""Repository for position sizing configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient

from walltrack.models.position_sizing import (
    PositionSizeAudit,
    PositionSizingConfig,
)

logger = structlog.get_logger(__name__)

# Fixed ID for singleton config row
CONFIG_ID = "00000000-0000-0000-0000-000000000001"


class PositionConfigRepository:
    """Repository for position sizing configuration."""

    def __init__(self, client: SupabaseClient):
        """Initialize repository with Supabase client.

        Args:
            client: Supabase client wrapper
        """
        self._client = client

    async def get_config(self) -> PositionSizingConfig:
        """Get current position sizing configuration.

        Returns:
            Current config or defaults if not found
        """
        try:
            result = (
                await self._client.table("position_sizing_config")
                .select("*")
                .eq("id", CONFIG_ID)
                .single()
                .execute()
            )

            if result.data:
                return self._row_to_config(result.data)
        except Exception as e:
            logger.warning("position_config_fetch_failed", error=str(e))

        # Return defaults if no config exists or fetch failed
        return PositionSizingConfig()

    async def save_config(self, config: PositionSizingConfig) -> PositionSizingConfig:
        """Save position sizing configuration.

        Args:
            config: Configuration to save

        Returns:
            Saved configuration
        """
        data = {
            "id": CONFIG_ID,
            "base_position_pct": config.base_position_pct,
            "min_position_sol": config.min_position_sol,
            "max_position_sol": config.max_position_sol,
            "high_conviction_multiplier": config.high_conviction_multiplier,
            "standard_conviction_multiplier": config.standard_conviction_multiplier,
            "high_conviction_threshold": config.high_conviction_threshold,
            "min_conviction_threshold": config.min_conviction_threshold,
            "max_concurrent_positions": config.max_concurrent_positions,
            "max_capital_allocation_pct": config.max_capital_allocation_pct,
            "reserve_sol": config.reserve_sol,
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": config.updated_by,
        }

        result = await self._client.table("position_sizing_config").upsert(data).execute()

        logger.info("position_config_saved", config_id=CONFIG_ID)

        if result.data:
            return self._row_to_config(result.data[0])
        return config

    async def save_audit(self, audit: PositionSizeAudit) -> str:
        """Save position sizing audit entry.

        Args:
            audit: Audit entry to save

        Returns:
            Generated audit ID
        """
        data = {
            "signal_id": audit.signal_id,
            "token_address": audit.token_address,
            "signal_score": audit.signal_score,
            "available_balance_sol": audit.available_balance_sol,
            "current_position_count": audit.current_position_count,
            "current_allocated_sol": audit.current_allocated_sol,
            "config_snapshot": audit.config_snapshot,
            "decision": audit.result.decision.value,
            "conviction_tier": audit.result.conviction_tier.value,
            "base_size_sol": audit.result.base_size_sol,
            "multiplier": audit.result.multiplier,
            "calculated_size_sol": audit.result.calculated_size_sol,
            "final_size_sol": audit.result.final_size_sol,
            "reason": audit.result.reason,
            "reduction_applied": audit.result.reduction_applied,
            "reduction_reason": audit.result.reduction_reason,
            "created_at": audit.created_at.isoformat(),
        }

        result = await self._client.table("position_sizing_audit").insert(data).execute()

        if result.data:
            audit_id = result.data[0]["id"]
            logger.debug(
                "position_audit_saved",
                audit_id=audit_id,
                decision=audit.result.decision.value,
            )
            return audit_id

        raise Exception("Failed to save position sizing audit")

    async def get_recent_audits(
        self,
        limit: int = 50,
        signal_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get recent position sizing audit entries.

        Args:
            limit: Maximum number of entries to return
            signal_id: Optional filter by signal ID

        Returns:
            List of audit entries as dicts
        """
        query = (
            self._client.table("position_sizing_audit")
            .select("*")
            .order("created_at", desc=True)
            .limit(limit)
        )

        if signal_id:
            query = query.eq("signal_id", signal_id)

        result = await query.execute()
        return result.data or []

    def _row_to_config(self, row: dict[str, Any]) -> PositionSizingConfig:
        """Convert database row to PositionSizingConfig.

        Args:
            row: Database row as dictionary

        Returns:
            PositionSizingConfig model
        """
        # Parse updated_at
        updated_at = row.get("updated_at")
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at.replace("Z", "+00:00"))
        else:
            updated_at = datetime.now(UTC)

        return PositionSizingConfig(
            base_position_pct=row.get("base_position_pct", 2.0),
            min_position_sol=row.get("min_position_sol", 0.01),
            max_position_sol=row.get("max_position_sol", 1.0),
            high_conviction_multiplier=row.get("high_conviction_multiplier", 1.5),
            standard_conviction_multiplier=row.get("standard_conviction_multiplier", 1.0),
            high_conviction_threshold=row.get("high_conviction_threshold", 0.85),
            min_conviction_threshold=row.get("min_conviction_threshold", 0.70),
            max_concurrent_positions=row.get("max_concurrent_positions", 5),
            max_capital_allocation_pct=row.get("max_capital_allocation_pct", 50.0),
            reserve_sol=row.get("reserve_sol", 0.05),
            updated_at=updated_at,
            updated_by=row.get("updated_by"),
        )
