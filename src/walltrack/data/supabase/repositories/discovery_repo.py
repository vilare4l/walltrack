"""Repository for discovery run data."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import structlog

from walltrack.data.supabase.client import SupabaseClient
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunParams,
    DiscoveryRunWallet,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)

log = structlog.get_logger()


class DiscoveryRepository:
    """Repository for discovery runs."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.runs_table = "discovery_runs"
        self.wallets_table = "discovery_run_wallets"

    async def create_run(
        self,
        trigger_type: TriggerType,
        params: dict[str, Any],
        triggered_by: str | None = None,
    ) -> DiscoveryRun:
        """Create a new discovery run record."""
        run_id = uuid4()
        now = datetime.now(UTC)

        data = {
            "id": str(run_id),
            "started_at": now.isoformat(),
            "status": RunStatus.RUNNING.value,
            "trigger_type": trigger_type.value,
            "triggered_by": triggered_by,
            **params,
        }

        await self.client.insert(self.runs_table, data)
        log.info("discovery_run_created", run_id=str(run_id), trigger=trigger_type.value)

        return DiscoveryRun(
            id=run_id,
            started_at=now,
            trigger_type=trigger_type,
            triggered_by=triggered_by,
            params=DiscoveryRunParams(**params) if params else DiscoveryRunParams(),
        )

    async def complete_run(
        self,
        run_id: UUID,
        tokens_analyzed: int,
        new_wallets: int,
        updated_wallets: int,
        profiled_wallets: int,
        duration_seconds: float,
        errors: list[str],
    ) -> None:
        """Mark run as completed with results."""
        await self.client.update(
            self.runs_table,
            {"id": str(run_id)},
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "status": RunStatus.COMPLETED.value,
                "tokens_analyzed": tokens_analyzed,
                "new_wallets": new_wallets,
                "updated_wallets": updated_wallets,
                "profiled_wallets": profiled_wallets,
                "duration_seconds": duration_seconds,
                "errors": errors,
            },
        )
        log.info(
            "discovery_run_completed",
            run_id=str(run_id),
            new_wallets=new_wallets,
            duration=duration_seconds,
        )

    async def fail_run(self, run_id: UUID, error: str) -> None:
        """Mark run as failed."""
        await self.client.update(
            self.runs_table,
            {"id": str(run_id)},
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "status": RunStatus.FAILED.value,
                "errors": [error],
            },
        )
        log.error("discovery_run_failed", run_id=str(run_id), error=error)

    async def cancel_run(self, run_id: UUID) -> None:
        """Mark run as cancelled."""
        await self.client.update(
            self.runs_table,
            {"id": str(run_id)},
            {
                "completed_at": datetime.now(UTC).isoformat(),
                "status": RunStatus.CANCELLED.value,
            },
        )
        log.info("discovery_run_cancelled", run_id=str(run_id))

    async def get_run(self, run_id: UUID) -> DiscoveryRun | None:
        """Get a discovery run by ID."""
        results = await self.client.select(
            self.runs_table,
            filters={"id": str(run_id)},
        )
        if not results:
            return None
        return self._row_to_run(results[0])

    async def get_runs(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        status: RunStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[DiscoveryRun]:
        """Get discovery runs with optional filters.

        Note: For now, this uses basic filtering. Date range filtering
        requires custom query support in the client.
        """
        filters: dict[str, Any] = {}
        if status:
            filters["status"] = status.value

        results = await self.client.select(
            self.runs_table,
            filters=filters if filters else None,
        )

        # Apply date filtering in Python (not ideal but works for now)
        if start_date or end_date:
            filtered = []
            for row in results:
                started = datetime.fromisoformat(row["started_at"].replace("Z", "+00:00"))
                if start_date and started < start_date:
                    continue
                if end_date and started > end_date:
                    continue
                filtered.append(row)
            results = filtered

        # Sort by started_at descending and apply pagination
        results.sort(key=lambda x: x["started_at"], reverse=True)
        results = results[offset : offset + limit]

        return [self._row_to_run(row) for row in results]

    async def get_stats(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> DiscoveryStats:
        """Get aggregated statistics."""
        runs = await self.get_runs(start_date=start_date, end_date=end_date, limit=1000)

        if not runs:
            return DiscoveryStats()

        total = len(runs)
        successful = sum(1 for r in runs if r.status == RunStatus.COMPLETED)
        failed = sum(1 for r in runs if r.status == RunStatus.FAILED)
        total_discovered = sum(r.new_wallets for r in runs)
        total_updated = sum(r.updated_wallets for r in runs)
        total_duration = sum(r.duration_seconds for r in runs if r.duration_seconds)

        # Find last completed run
        completed_runs = [r for r in runs if r.status == RunStatus.COMPLETED]
        last_run_at = completed_runs[0].started_at if completed_runs else None

        return DiscoveryStats(
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            total_wallets_discovered=total_discovered,
            total_wallets_updated=total_updated,
            avg_wallets_per_run=total_discovered / total if total > 0 else 0.0,
            avg_duration_seconds=total_duration / total if total > 0 else 0.0,
            last_run_at=last_run_at,
        )

    async def add_wallet_to_run(
        self,
        run_id: UUID,
        wallet_address: str,
        source_token: str,
        is_new: bool,
        initial_score: float | None = None,
    ) -> None:
        """Record a wallet discovered in a run."""
        await self.client.insert(
            self.wallets_table,
            {
                "id": str(uuid4()),
                "run_id": str(run_id),
                "wallet_address": wallet_address,
                "source_token": source_token,
                "is_new": is_new,
                "initial_score": initial_score,
            },
        )

    async def get_run_wallets(self, run_id: UUID) -> list[DiscoveryRunWallet]:
        """Get wallets discovered in a specific run."""
        results = await self.client.select(
            self.wallets_table,
            filters={"run_id": str(run_id)},
        )
        return [self._row_to_wallet(row) for row in results]

    def _row_to_run(self, row: dict[str, Any]) -> DiscoveryRun:
        """Convert database row to DiscoveryRun model."""
        # Parse started_at
        started_at = row["started_at"]
        if isinstance(started_at, str):
            started_at = datetime.fromisoformat(started_at.replace("Z", "+00:00"))

        # Parse completed_at
        completed_at = row.get("completed_at")
        if completed_at and isinstance(completed_at, str):
            completed_at = datetime.fromisoformat(completed_at.replace("Z", "+00:00"))

        # Build params from individual fields
        params = DiscoveryRunParams(
            min_price_change_pct=row.get("min_price_change_pct") or 100.0,
            min_volume_usd=row.get("min_volume_usd") or 50000.0,
            max_token_age_hours=row.get("max_token_age_hours") or 72,
            early_window_minutes=row.get("early_window_minutes") or 30,
            min_profit_pct=row.get("min_profit_pct") or 50.0,
            max_tokens=row.get("max_tokens") or 20,
        )

        return DiscoveryRun(
            id=UUID(row["id"]),
            started_at=started_at,
            completed_at=completed_at,
            status=RunStatus(row["status"]),
            trigger_type=TriggerType(row["trigger_type"]),
            triggered_by=row.get("triggered_by"),
            params=params,
            tokens_analyzed=row.get("tokens_analyzed") or 0,
            new_wallets=row.get("new_wallets") or 0,
            updated_wallets=row.get("updated_wallets") or 0,
            profiled_wallets=row.get("profiled_wallets") or 0,
            duration_seconds=float(row.get("duration_seconds") or 0.0),
            errors=row.get("errors") or [],
        )

    def _row_to_wallet(self, row: dict[str, Any]) -> DiscoveryRunWallet:
        """Convert database row to DiscoveryRunWallet model."""
        created_at = row.get("created_at")
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return DiscoveryRunWallet(
            id=UUID(row["id"]),
            run_id=UUID(row["run_id"]),
            wallet_address=row["wallet_address"],
            source_token=row["source_token"],
            is_new=row.get("is_new", True),
            initial_score=float(row["initial_score"]) if row.get("initial_score") else None,
            created_at=created_at,
        )
