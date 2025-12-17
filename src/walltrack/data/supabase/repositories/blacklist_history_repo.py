"""Repository for blacklist history."""

from typing import Any

import structlog

from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger()


class BlacklistHistoryRepository:
    """Repository for blacklist history records."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "blacklist_history"

    async def record_blacklist(
        self,
        wallet_address: str,
        reason: str,
        previous_status: str,
        operator_id: str | None = None,
    ) -> str:
        """Record a blacklist action. Returns record ID."""
        data = {
            "wallet_address": wallet_address,
            "action": "blacklisted",
            "reason": reason,
            "previous_status": previous_status,
            "operator_id": operator_id,
        }

        response = await self.client.table(self.table).insert(data).execute()
        record_id: str = response.data[0]["id"]

        log.info(
            "blacklist_recorded",
            wallet=wallet_address,
            action="blacklisted",
            reason=reason,
        )

        return record_id

    async def record_unblacklist(
        self,
        wallet_address: str,
        operator_id: str | None = None,
    ) -> str:
        """Record an unblacklist action. Returns record ID."""
        data = {
            "wallet_address": wallet_address,
            "action": "unblacklisted",
            "operator_id": operator_id,
        }

        response = await self.client.table(self.table).insert(data).execute()
        record_id: str = response.data[0]["id"]

        log.info(
            "blacklist_recorded",
            wallet=wallet_address,
            action="unblacklisted",
        )

        return record_id

    async def get_wallet_history(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get blacklist history for a wallet."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("wallet_address", wallet_address)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        result: list[dict[str, Any]] = response.data
        return result

    async def get_recent_actions(
        self,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent blacklist actions."""
        query = self.client.table(self.table).select("*")

        if action:
            query = query.eq("action", action)

        response = await (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        result: list[dict[str, Any]] = response.data
        return result
