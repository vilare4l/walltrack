"""Position timeline service for event tracking."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum

import structlog

logger = structlog.get_logger(__name__)


class PositionEventType(str, Enum):
    """Types of position events."""

    CREATED = "created"
    STRATEGY_ASSIGNED = "strategy_assigned"
    STRATEGY_CHANGED = "strategy_changed"
    PRICE_UPDATE = "price_update"
    TP_TRIGGERED = "tp_triggered"
    SL_TRIGGERED = "sl_triggered"
    TRAILING_ACTIVATED = "trailing_activated"
    TRAILING_TRIGGERED = "trailing_triggered"
    PARTIAL_EXIT = "partial_exit"
    STAGNATION_EXIT = "stagnation_exit"
    TIME_EXIT = "time_exit"
    MANUAL_EXIT = "manual_exit"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class PositionEvent:
    """A single position event."""

    id: str
    position_id: str
    event_type: PositionEventType
    timestamp: datetime
    price_at_event: Decimal | None
    data_before: dict | None
    data_after: dict | None
    metadata: dict = field(default_factory=dict)
    comment: str | None = None


@dataclass
class PositionTimeline:
    """Complete timeline for a position."""

    position_id: str
    token_symbol: str
    entry_time: datetime
    exit_time: datetime | None
    events: list[PositionEvent]
    total_events: int

    @property
    def duration_hours(self) -> float:
        """Get position duration in hours."""
        end = self.exit_time or datetime.now(UTC)
        return (end - self.entry_time).total_seconds() / 3600


class PositionTimelineService:
    """
    Service for managing position event timelines.

    Tracks all events that occur during a position's lifecycle.
    """

    def __init__(self) -> None:
        self._client = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import (  # noqa: PLC0415
                get_supabase_client,
            )

            self._client = await get_supabase_client()
        return self._client

    async def log_event(
        self,
        position_id: str,
        event_type: PositionEventType,
        price_at_event: Decimal | None = None,
        data_before: dict | None = None,
        data_after: dict | None = None,
        metadata: dict | None = None,
        comment: str | None = None,
    ) -> PositionEvent:
        """
        Log a new event for a position.

        Args:
            position_id: Position ID
            event_type: Type of event
            price_at_event: Price when event occurred
            data_before: State before event (for changes)
            data_after: State after event (for changes)
            metadata: Additional event data
            comment: Optional comment/reason

        Returns:
            Created PositionEvent
        """
        client = await self._get_client()

        event_data = {
            "position_id": position_id,
            "event_type": event_type.value,
            "timestamp": datetime.now(UTC).isoformat(),
            "price_at_event": str(price_at_event) if price_at_event else None,
            "data_before": data_before,
            "data_after": data_after,
            "metadata": metadata or {},
            "comment": comment,
        }

        result = await client.table("position_events").insert(event_data).execute()

        row = result.data[0]

        logger.info(
            "position_event_logged",
            position_id=position_id,
            event_type=event_type.value,
            event_id=row["id"],
        )

        return self._row_to_event(row)

    async def get_timeline(
        self,
        position_id: str,
        event_types: list[PositionEventType] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PositionTimeline:
        """
        Get timeline for a position.

        Args:
            position_id: Position ID
            event_types: Optional filter by event types
            limit: Max events to return
            offset: Pagination offset

        Returns:
            PositionTimeline with events

        Raises:
            ValueError: If position not found
        """
        client = await self._get_client()

        # Get position info
        pos_result = await (
            client.table("positions")
            .select("id, token_symbol, entry_time, exit_time")
            .eq("id", position_id)
            .single()
            .execute()
        )

        if not pos_result.data:
            raise ValueError(f"Position not found: {position_id}")

        position = pos_result.data

        # Build events query
        query = (
            client.table("position_events")
            .select("*")
            .eq("position_id", position_id)
            .order("timestamp", desc=False)
        )

        if event_types:
            type_values = [t.value for t in event_types]
            query = query.in_("event_type", type_values)

        # Get total count
        count_query = (
            client.table("position_events")
            .select("id", count="exact")
            .eq("position_id", position_id)
        )

        if event_types:
            type_values = [t.value for t in event_types]
            count_query = count_query.in_("event_type", type_values)

        count_result = await count_query.execute()
        total = count_result.count or 0

        # Get events with pagination
        result = await query.range(offset, offset + limit - 1).execute()

        events = [self._row_to_event(row) for row in result.data]

        return PositionTimeline(
            position_id=position_id,
            token_symbol=position.get("token_symbol") or "",
            entry_time=datetime.fromisoformat(
                position["entry_time"].replace("Z", "+00:00")
            ),
            exit_time=(
                datetime.fromisoformat(position["exit_time"].replace("Z", "+00:00"))
                if position.get("exit_time")
                else None
            ),
            events=events,
            total_events=total,
        )

    async def get_events_by_type(
        self,
        position_id: str,
        event_type: PositionEventType,
    ) -> list[PositionEvent]:
        """Get all events of a specific type."""
        client = await self._get_client()

        result = await (
            client.table("position_events")
            .select("*")
            .eq("position_id", position_id)
            .eq("event_type", event_type.value)
            .order("timestamp")
            .execute()
        )

        return [self._row_to_event(row) for row in result.data]

    async def get_latest_event(
        self,
        position_id: str,
        event_type: PositionEventType | None = None,
    ) -> PositionEvent | None:
        """Get the most recent event."""
        client = await self._get_client()

        query = (
            client.table("position_events")
            .select("*")
            .eq("position_id", position_id)
            .order("timestamp", desc=True)
            .limit(1)
        )

        if event_type:
            query = query.eq("event_type", event_type.value)

        result = await query.execute()

        if result.data:
            return self._row_to_event(result.data[0])
        return None

    async def export_timeline(
        self,
        position_id: str,
        format_type: str = "json",
    ) -> str:
        """
        Export timeline to JSON or CSV.

        Args:
            position_id: Position ID
            format_type: "json" or "csv"

        Returns:
            Formatted string

        Raises:
            ValueError: If format is not supported
        """
        timeline = await self.get_timeline(position_id, limit=1000)

        if format_type == "json":
            data = {
                "position_id": timeline.position_id,
                "token_symbol": timeline.token_symbol,
                "entry_time": timeline.entry_time.isoformat(),
                "exit_time": (
                    timeline.exit_time.isoformat() if timeline.exit_time else None
                ),
                "duration_hours": timeline.duration_hours,
                "total_events": timeline.total_events,
                "events": [
                    {
                        "id": e.id,
                        "event_type": e.event_type.value,
                        "timestamp": e.timestamp.isoformat(),
                        "price_at_event": (
                            str(e.price_at_event) if e.price_at_event else None
                        ),
                        "data_before": e.data_before,
                        "data_after": e.data_after,
                        "metadata": e.metadata,
                        "comment": e.comment,
                    }
                    for e in timeline.events
                ],
            }
            return json.dumps(data, indent=2)

        elif format_type == "csv":
            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow(
                ["timestamp", "event_type", "price_at_event", "comment", "metadata"]
            )

            # Data
            for e in timeline.events:
                writer.writerow(
                    [
                        e.timestamp.isoformat(),
                        e.event_type.value,
                        str(e.price_at_event) if e.price_at_event else "",
                        e.comment or "",
                        str(e.metadata) if e.metadata else "",
                    ]
                )

            return output.getvalue()

        else:
            raise ValueError(f"Unknown format: {format_type}")

    def _row_to_event(self, row: dict) -> PositionEvent:
        """Convert database row to PositionEvent."""
        return PositionEvent(
            id=row["id"],
            position_id=row["position_id"],
            event_type=PositionEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
            price_at_event=(
                Decimal(str(row["price_at_event"]))
                if row.get("price_at_event")
                else None
            ),
            data_before=row.get("data_before"),
            data_after=row.get("data_after"),
            metadata=row.get("metadata") or {},
            comment=row.get("comment"),
        )


# Singleton
_timeline_service: PositionTimelineService | None = None


async def get_timeline_service() -> PositionTimelineService:
    """Get timeline service instance."""
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = PositionTimelineService()
    return _timeline_service


def reset_timeline_service() -> None:
    """Reset the singleton (for testing)."""
    global _timeline_service
    _timeline_service = None
