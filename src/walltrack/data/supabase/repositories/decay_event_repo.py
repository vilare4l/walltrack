"""Repository for decay events."""

from typing import Any

import structlog

from walltrack.data.supabase.client import SupabaseClient
from walltrack.discovery.decay_detector import DecayEvent

log = structlog.get_logger()


class DecayEventRepository:
    """Repository for decay event storage."""

    def __init__(self, client: SupabaseClient) -> None:
        self.client = client
        self.table = "decay_events"

    async def create(self, event: DecayEvent) -> str:
        """Store a decay event. Returns event ID."""
        data = {
            "wallet_address": event.wallet_address,
            "event_type": event.event_type,
            "rolling_win_rate": event.rolling_win_rate,
            "lifetime_win_rate": event.lifetime_win_rate,
            "consecutive_losses": event.consecutive_losses,
            "score_before": event.score_before,
            "score_after": event.score_after,
            "created_at": event.timestamp.isoformat(),
        }

        response = await self.client.table(self.table).insert(data).execute()
        event_id: str = response.data[0]["id"]

        log.info(
            "decay_event_stored",
            event_id=event_id,
            wallet=event.wallet_address,
            type=event.event_type,
        )

        return event_id

    async def get_wallet_events(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get decay events for a wallet."""
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

    async def get_recent_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent decay events."""
        query = self.client.table(self.table).select("*")

        if event_type:
            query = query.eq("event_type", event_type)

        response = await (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        result: list[dict[str, Any]] = response.data
        return result

    async def count_by_type(
        self,
        event_type: str | None = None,
    ) -> int:
        """Count decay events by type."""
        query = self.client.table(self.table).select("*", count="exact")

        if event_type:
            query = query.eq("event_type", event_type)

        response = await query.execute()
        return response.count or 0
