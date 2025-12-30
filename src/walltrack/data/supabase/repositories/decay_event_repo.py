"""Decay event repository for Supabase.

This module provides a repository pattern for accessing the decay_events table
in Supabase, storing wallet decay status transitions and score adjustments.

Story 3.4 - Wallet Decay Detection (AC4: Event Logging)
"""

import structlog

from walltrack.data.models.decay_event import DecayEvent, DecayEventCreate
from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger(__name__)


class DecayEventRepository:
    """Repository for accessing decay_events table in Supabase.

    Provides CRUD operations for decay events, tracking wallet performance
    degradation and recovery transitions.

    Attributes:
        _client: SupabaseClient instance for database operations.

    Example:
        client = await get_supabase_client()
        repo = DecayEventRepository(client)
        event = await repo.create(event_data)
    """

    TABLE_NAME = "decay_events"

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize repository with Supabase client.

        Args:
            client: Connected SupabaseClient instance.
        """
        self._client = client

    async def create(self, event: DecayEventCreate) -> DecayEvent:
        """Insert decay event to database.

        Args:
            event: DecayEventCreate instance with event data.

        Returns:
            DecayEvent with generated ID and created_at timestamp.

        Raises:
            Exception: If insert operation fails.

        Example:
            event_data = DecayEventCreate(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                event_type=DecayEventType.DECAY_DETECTED,
                rolling_win_rate=Decimal("0.35"),
                lifetime_win_rate=Decimal("0.62"),
                consecutive_losses=0,
                score_before=Decimal("0.8500"),
                score_after=Decimal("0.6800"),
            )
            created_event = await repo.create(event_data)
        """
        try:
            # Prepare insert data (exclude auto-generated fields)
            insert_data = {
                "wallet_address": event.wallet_address,
                "event_type": event.event_type.value,
                "rolling_win_rate": (
                    float(event.rolling_win_rate) if event.rolling_win_rate else None
                ),
                "lifetime_win_rate": (
                    float(event.lifetime_win_rate) if event.lifetime_win_rate else None
                ),
                "consecutive_losses": event.consecutive_losses,
                "score_before": (
                    float(event.score_before) if event.score_before else None
                ),
                "score_after": float(event.score_after) if event.score_after else None,
            }

            # Execute insert
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .insert(insert_data)
                .execute()
            )

            if not result.data or len(result.data) == 0:
                raise ValueError("Insert operation returned no data")

            # Convert response to DecayEvent model
            created_event = DecayEvent(**result.data[0])

            log.info(
                "decay_event_created",
                wallet_address=event.wallet_address[:8] + "...",
                event_type=event.event_type.value,
                event_id=str(created_event.id),
            )

            return created_event

        except Exception as e:
            log.error(
                "decay_event_creation_failed",
                wallet_address=event.wallet_address[:8] + "...",
                event_type=event.event_type.value,
                error=str(e),
            )
            raise

    async def get_wallet_events(
        self, wallet_address: str, limit: int = 50
    ) -> list[DecayEvent]:
        """Fetch decay events for a specific wallet.

        Args:
            wallet_address: Solana wallet address.
            limit: Maximum number of events to return (default: 50).

        Returns:
            List of DecayEvent objects ordered by created_at DESC.

        Example:
            events = await repo.get_wallet_events(
                "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                limit=10
            )
            for event in events:
                print(f"{event.event_type}: {event.created_at}")
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .eq("wallet_address", wallet_address)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            events = [DecayEvent(**row) for row in result.data]

            log.debug(
                "wallet_decay_events_fetched",
                wallet_address=wallet_address[:8] + "...",
                count=len(events),
            )

            return events

        except Exception as e:
            log.error(
                "wallet_decay_events_fetch_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return []

    async def get_recent_events(
        self, event_type: str | None = None, limit: int = 100
    ) -> list[DecayEvent]:
        """Fetch recent decay events across all wallets.

        Args:
            event_type: Optional filter by event type (decay_detected, recovery, etc.).
            limit: Maximum number of events to return (default: 100).

        Returns:
            List of DecayEvent objects ordered by created_at DESC.

        Example:
            # Get all recent events
            events = await repo.get_recent_events(limit=50)

            # Get only recovery events
            recoveries = await repo.get_recent_events(
                event_type="recovery",
                limit=20
            )
        """
        try:
            query = (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .order("created_at", desc=True)
                .limit(limit)
            )

            # Apply event_type filter if provided
            if event_type:
                query = query.eq("event_type", event_type)

            result = await query.execute()

            events = [DecayEvent(**row) for row in result.data]

            log.debug(
                "recent_decay_events_fetched",
                event_type=event_type or "all",
                count=len(events),
            )

            return events

        except Exception as e:
            log.error(
                "recent_decay_events_fetch_failed",
                event_type=event_type or "all",
                error=str(e),
            )
            return []

    async def count_by_type(self, event_type: str) -> int:
        """Count decay events by type.

        Args:
            event_type: Event type to count (decay_detected, recovery, consecutive_losses, dormancy).

        Returns:
            Count of events of the specified type.

        Example:
            decay_count = await repo.count_by_type("decay_detected")
            recovery_count = await repo.count_by_type("recovery")
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .eq("event_type", event_type)
                .execute()
            )

            count = result.count or 0

            log.debug(
                "decay_events_counted",
                event_type=event_type,
                count=count,
            )

            return count

        except Exception as e:
            log.error(
                "decay_events_count_failed",
                event_type=event_type,
                error=str(e),
            )
            return 0
