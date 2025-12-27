# Story 12.10: Position Timeline - Exit Events Log

## Story Info
- **Epic**: Epic 12 - Positions Management & Exit Strategy Simulator
- **Status**: ready
- **Priority**: P2 - Medium
- **Story Points**: 3
- **Depends on**: Story 12-3 (Change Strategy)

## User Story

**As a** the operator,
**I want** une timeline complète des événements d'une position,
**So that** je comprends exactement ce qui s'est passé et pourquoi.

## Acceptance Criteria

### AC 1: Display Event Timeline
**Given** une position avec des événements
**When** je consulte la timeline
**Then** je vois chronologiquement:
- Création de la position
- Changements de stratégie
- Déclenchements de TP/SL
- Sorties partielles
- Fermeture finale

### AC 2: Event Details
**Given** un événement dans la timeline
**When** je l'examine
**Then** je vois:
- Timestamp exact
- Type d'événement
- Données avant/après (pour les changements)
- Prix au moment de l'événement
- Commentaire/raison si applicable

### AC 3: Filter Events
**Given** une timeline longue
**When** je filtre par type
**Then** je peux voir seulement certains types d'événements

### AC 4: Export Timeline
**Given** une timeline
**When** je clique export
**Then** je peux télécharger en JSON ou CSV

## Technical Specifications

### Position Event Types

```python
"""Position event type definitions."""

from enum import Enum


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
```

### Position Timeline Service

**src/walltrack/services/positions/timeline_service.py:**
```python
"""Position timeline service for event tracking."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional
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
    price_at_event: Optional[Decimal]
    data_before: Optional[dict]
    data_after: Optional[dict]
    metadata: dict
    comment: Optional[str]


@dataclass
class PositionTimeline:
    """Complete timeline for a position."""
    position_id: str
    token_symbol: str
    entry_time: datetime
    exit_time: Optional[datetime]
    events: list[PositionEvent]
    total_events: int

    @property
    def duration_hours(self) -> float:
        """Get position duration in hours."""
        end = self.exit_time or datetime.utcnow()
        return (end - self.entry_time).total_seconds() / 3600


class PositionTimelineService:
    """
    Service for managing position event timelines.

    Tracks all events that occur during a position's lifecycle.
    """

    def __init__(self):
        self._client = None

    async def _get_client(self):
        """Get Supabase client."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

    async def log_event(
        self,
        position_id: str,
        event_type: PositionEventType,
        price_at_event: Optional[Decimal] = None,
        data_before: Optional[dict] = None,
        data_after: Optional[dict] = None,
        metadata: Optional[dict] = None,
        comment: Optional[str] = None,
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
            "timestamp": datetime.utcnow().isoformat(),
            "price_at_event": str(price_at_event) if price_at_event else None,
            "data_before": data_before,
            "data_after": data_after,
            "metadata": metadata or {},
            "comment": comment,
        }

        result = await client.table("position_events") \
            .insert(event_data) \
            .execute()

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
        event_types: Optional[list[PositionEventType]] = None,
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
        """
        client = await self._get_client()

        # Get position info
        pos_result = await client.table("positions") \
            .select("id, token_symbol, entry_time, exit_time") \
            .eq("id", position_id) \
            .single() \
            .execute()

        if not pos_result.data:
            raise ValueError(f"Position not found: {position_id}")

        position = pos_result.data

        # Build events query
        query = client.table("position_events") \
            .select("*") \
            .eq("position_id", position_id) \
            .order("timestamp", desc=False)

        if event_types:
            type_values = [t.value for t in event_types]
            query = query.in_("event_type", type_values)

        # Get total count
        count_result = await client.table("position_events") \
            .select("id", count="exact") \
            .eq("position_id", position_id) \
            .execute()

        total = count_result.count or 0

        # Get events with pagination
        result = await query \
            .range(offset, offset + limit - 1) \
            .execute()

        events = [self._row_to_event(row) for row in result.data]

        return PositionTimeline(
            position_id=position_id,
            token_symbol=position.get("token_symbol", ""),
            entry_time=datetime.fromisoformat(
                position["entry_time"].replace("Z", "+00:00")
            ),
            exit_time=datetime.fromisoformat(
                position["exit_time"].replace("Z", "+00:00")
            ) if position.get("exit_time") else None,
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

        result = await client.table("position_events") \
            .select("*") \
            .eq("position_id", position_id) \
            .eq("event_type", event_type.value) \
            .order("timestamp") \
            .execute()

        return [self._row_to_event(row) for row in result.data]

    async def get_latest_event(
        self,
        position_id: str,
        event_type: Optional[PositionEventType] = None,
    ) -> Optional[PositionEvent]:
        """Get the most recent event."""
        client = await self._get_client()

        query = client.table("position_events") \
            .select("*") \
            .eq("position_id", position_id) \
            .order("timestamp", desc=True) \
            .limit(1)

        if event_type:
            query = query.eq("event_type", event_type.value)

        result = await query.execute()

        if result.data:
            return self._row_to_event(result.data[0])
        return None

    async def export_timeline(
        self,
        position_id: str,
        format: str = "json",
    ) -> str:
        """
        Export timeline to JSON or CSV.

        Args:
            position_id: Position ID
            format: "json" or "csv"

        Returns:
            Formatted string
        """
        timeline = await self.get_timeline(position_id, limit=1000)

        if format == "json":
            import json
            data = {
                "position_id": timeline.position_id,
                "token_symbol": timeline.token_symbol,
                "entry_time": timeline.entry_time.isoformat(),
                "exit_time": timeline.exit_time.isoformat() if timeline.exit_time else None,
                "duration_hours": timeline.duration_hours,
                "total_events": timeline.total_events,
                "events": [
                    {
                        "id": e.id,
                        "event_type": e.event_type.value,
                        "timestamp": e.timestamp.isoformat(),
                        "price_at_event": str(e.price_at_event) if e.price_at_event else None,
                        "data_before": e.data_before,
                        "data_after": e.data_after,
                        "metadata": e.metadata,
                        "comment": e.comment,
                    }
                    for e in timeline.events
                ],
            }
            return json.dumps(data, indent=2)

        elif format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)

            # Header
            writer.writerow([
                "timestamp", "event_type", "price_at_event",
                "comment", "metadata"
            ])

            # Data
            for e in timeline.events:
                writer.writerow([
                    e.timestamp.isoformat(),
                    e.event_type.value,
                    str(e.price_at_event) if e.price_at_event else "",
                    e.comment or "",
                    str(e.metadata) if e.metadata else "",
                ])

            return output.getvalue()

        else:
            raise ValueError(f"Unknown format: {format}")

    def _row_to_event(self, row: dict) -> PositionEvent:
        """Convert database row to PositionEvent."""
        return PositionEvent(
            id=row["id"],
            position_id=row["position_id"],
            event_type=PositionEventType(row["event_type"]),
            timestamp=datetime.fromisoformat(
                row["timestamp"].replace("Z", "+00:00")
            ),
            price_at_event=Decimal(str(row["price_at_event"]))
                if row.get("price_at_event") else None,
            data_before=row.get("data_before"),
            data_after=row.get("data_after"),
            metadata=row.get("metadata", {}),
            comment=row.get("comment"),
        )


# Singleton
_timeline_service: Optional[PositionTimelineService] = None


async def get_timeline_service() -> PositionTimelineService:
    """Get timeline service instance."""
    global _timeline_service
    if _timeline_service is None:
        _timeline_service = PositionTimelineService()
    return _timeline_service
```

### Position Timeline UI Component

**src/walltrack/ui/components/position_timeline.py:**
```python
"""Position timeline UI component."""

from datetime import datetime
from typing import Optional

import gradio as gr

from walltrack.services.positions.timeline_service import (
    get_timeline_service,
    PositionEventType,
    PositionTimeline,
)


# Event type display config
EVENT_DISPLAY = {
    PositionEventType.CREATED: ("🆕", "Position Created", "blue"),
    PositionEventType.STRATEGY_ASSIGNED: ("📋", "Strategy Assigned", "purple"),
    PositionEventType.STRATEGY_CHANGED: ("🔄", "Strategy Changed", "orange"),
    PositionEventType.PRICE_UPDATE: ("📊", "Price Update", "gray"),
    PositionEventType.TP_TRIGGERED: ("🎯", "Take Profit Triggered", "green"),
    PositionEventType.SL_TRIGGERED: ("🛑", "Stop Loss Triggered", "red"),
    PositionEventType.TRAILING_ACTIVATED: ("📈", "Trailing Stop Activated", "teal"),
    PositionEventType.TRAILING_TRIGGERED: ("📉", "Trailing Stop Hit", "orange"),
    PositionEventType.PARTIAL_EXIT: ("➖", "Partial Exit", "yellow"),
    PositionEventType.STAGNATION_EXIT: ("⏸️", "Stagnation Exit", "gray"),
    PositionEventType.TIME_EXIT: ("⏰", "Time-Based Exit", "purple"),
    PositionEventType.MANUAL_EXIT: ("👆", "Manual Exit", "blue"),
    PositionEventType.CLOSED: ("✅", "Position Closed", "green"),
    PositionEventType.ERROR: ("❌", "Error", "red"),
}


def format_timeline_markdown(timeline: PositionTimeline) -> str:
    """Format timeline as markdown."""
    md = f"""
## Position Timeline: {timeline.token_symbol}

**Position ID:** {timeline.position_id[:12]}...
**Entry:** {timeline.entry_time.strftime('%Y-%m-%d %H:%M:%S')}
**Exit:** {timeline.exit_time.strftime('%Y-%m-%d %H:%M:%S') if timeline.exit_time else 'Active'}
**Duration:** {timeline.duration_hours:.1f} hours
**Total Events:** {timeline.total_events}

---

"""

    for event in timeline.events:
        icon, label, _ = EVENT_DISPLAY.get(
            event.event_type,
            ("❓", event.event_type.value, "gray")
        )

        time_str = event.timestamp.strftime('%H:%M:%S')
        date_str = event.timestamp.strftime('%Y-%m-%d')

        # Event header
        md += f"### {icon} {label}\n"
        md += f"**{date_str}** at **{time_str}**\n\n"

        # Price if available
        if event.price_at_event:
            md += f"- **Price:** ${event.price_at_event:.8f}\n"

        # Show changes for strategy events
        if event.event_type == PositionEventType.STRATEGY_CHANGED:
            if event.data_before:
                md += f"- **From:** {event.data_before.get('strategy_name', 'Unknown')}\n"
            if event.data_after:
                md += f"- **To:** {event.data_after.get('strategy_name', 'Unknown')}\n"

        # Show exit details
        if event.event_type in [
            PositionEventType.TP_TRIGGERED,
            PositionEventType.SL_TRIGGERED,
            PositionEventType.PARTIAL_EXIT,
        ]:
            if event.metadata:
                exit_pct = event.metadata.get("exit_pct", 0)
                pnl = event.metadata.get("pnl_pct", 0)
                md += f"- **Exit:** {exit_pct}% of position\n"
                md += f"- **P&L:** {pnl:+.2f}%\n"

        # Comment
        if event.comment:
            md += f"- **Note:** {event.comment}\n"

        md += "\n---\n\n"

    return md


def format_timeline_dataframe(timeline: PositionTimeline) -> list[list]:
    """Format timeline as dataframe rows."""
    rows = []

    for event in timeline.events:
        icon, label, _ = EVENT_DISPLAY.get(
            event.event_type,
            ("❓", event.event_type.value, "gray")
        )

        price_str = f"${event.price_at_event:.8f}" if event.price_at_event else "-"

        # Build details string
        details = []
        if event.comment:
            details.append(event.comment)

        if event.event_type == PositionEventType.STRATEGY_CHANGED:
            if event.data_before and event.data_after:
                details.append(
                    f"{event.data_before.get('strategy_name', '?')} → "
                    f"{event.data_after.get('strategy_name', '?')}"
                )

        if event.metadata:
            if "exit_pct" in event.metadata:
                details.append(f"Exit: {event.metadata['exit_pct']}%")
            if "pnl_pct" in event.metadata:
                details.append(f"P&L: {event.metadata['pnl_pct']:+.2f}%")

        rows.append([
            event.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            f"{icon} {label}",
            price_str,
            " | ".join(details) if details else "-",
        ])

    return rows


class PositionTimelineComponent:
    """Position timeline UI component."""

    def __init__(self):
        self._service = None

    async def _get_service(self):
        """Get timeline service."""
        if self._service is None:
            self._service = await get_timeline_service()
        return self._service

    async def load_timeline(
        self,
        position_id: str,
        event_filter: list[str] = None,
        view_mode: str = "table",
    ) -> tuple:
        """
        Load timeline for display.

        Returns:
            (dataframe_rows, markdown_text, export_json, export_csv)
        """
        if not position_id:
            return [], "", "", ""

        service = await self._get_service()

        # Convert filter strings to event types
        event_types = None
        if event_filter:
            event_types = [
                PositionEventType(f) for f in event_filter
                if f in [e.value for e in PositionEventType]
            ]

        timeline = await service.get_timeline(
            position_id=position_id,
            event_types=event_types,
            limit=500,
        )

        # Format outputs
        df_rows = format_timeline_dataframe(timeline)
        md_text = format_timeline_markdown(timeline)

        # Export formats
        json_export = await service.export_timeline(position_id, "json")
        csv_export = await service.export_timeline(position_id, "csv")

        return df_rows, md_text, json_export, csv_export

    def build(self) -> gr.Blocks:
        """Build timeline component."""
        with gr.Blocks() as timeline_block:
            position_id_input = gr.Textbox(
                label="Position ID",
                placeholder="Enter position ID...",
                visible=False,
            )

            with gr.Row():
                event_filter = gr.CheckboxGroup(
                    label="Filter Events",
                    choices=[
                        ("Created", "created"),
                        ("Strategy Changed", "strategy_changed"),
                        ("Take Profit", "tp_triggered"),
                        ("Stop Loss", "sl_triggered"),
                        ("Trailing Stop", "trailing_triggered"),
                        ("Partial Exit", "partial_exit"),
                        ("Closed", "closed"),
                    ],
                    value=[],
                )

                view_mode = gr.Radio(
                    label="View Mode",
                    choices=["Table", "Timeline"],
                    value="Table",
                )

            refresh_btn = gr.Button("🔄 Refresh", size="sm")

            # Table view
            timeline_table = gr.Dataframe(
                headers=["Time", "Event", "Price", "Details"],
                datatype=["str", "str", "str", "str"],
                interactive=False,
                wrap=True,
            )

            # Timeline view (markdown)
            timeline_md = gr.Markdown(visible=False)

            # Export section
            with gr.Accordion("Export", open=False):
                with gr.Row():
                    export_json_btn = gr.Button("📥 Export JSON", size="sm")
                    export_csv_btn = gr.Button("📥 Export CSV", size="sm")

                export_output = gr.Textbox(
                    label="Export Data",
                    lines=10,
                    interactive=False,
                    visible=False,
                )

            # State for exports
            json_state = gr.State("")
            csv_state = gr.State("")

            # Event handlers
            async def load_data(pos_id, filters, mode):
                if not pos_id:
                    return [], "", "", "", gr.update(visible=mode=="Table"), gr.update(visible=mode=="Timeline")

                df_rows, md_text, json_data, csv_data = await self.load_timeline(
                    pos_id, filters, mode
                )

                return (
                    df_rows,
                    md_text,
                    json_data,
                    csv_data,
                    gr.update(visible=mode=="Table"),
                    gr.update(visible=mode=="Timeline"),
                )

            def show_json(json_data):
                return gr.update(value=json_data, visible=True)

            def show_csv(csv_data):
                return gr.update(value=csv_data, visible=True)

            # Wire events
            refresh_btn.click(
                load_data,
                [position_id_input, event_filter, view_mode],
                [timeline_table, timeline_md, json_state, csv_state,
                 timeline_table, timeline_md],
            )

            event_filter.change(
                load_data,
                [position_id_input, event_filter, view_mode],
                [timeline_table, timeline_md, json_state, csv_state,
                 timeline_table, timeline_md],
            )

            view_mode.change(
                load_data,
                [position_id_input, event_filter, view_mode],
                [timeline_table, timeline_md, json_state, csv_state,
                 timeline_table, timeline_md],
            )

            export_json_btn.click(show_json, [json_state], [export_output])
            export_csv_btn.click(show_csv, [csv_state], [export_output])

            # Expose for external control
            timeline_block.position_id_input = position_id_input
            timeline_block.refresh = refresh_btn.click

        return timeline_block


async def build_timeline_component() -> gr.Blocks:
    """Build and return timeline component."""
    component = PositionTimelineComponent()
    return component.build()
```

### Database Migration

```sql
-- position_events table (may already exist from 12-3)
-- Ensure all event types are supported

-- Add index for timeline queries
CREATE INDEX IF NOT EXISTS idx_position_events_timeline
ON position_events (position_id, timestamp);

-- Add index for event type filtering
CREATE INDEX IF NOT EXISTS idx_position_events_type
ON position_events (position_id, event_type);
```

## Implementation Tasks

- [x] Create PositionEventType enum
- [x] Create PositionEvent dataclass
- [x] Create PositionTimeline dataclass
- [x] Implement PositionTimelineService
- [x] Implement log_event() method
- [x] Implement get_timeline() with filtering
- [x] Implement export_timeline() for JSON/CSV
- [x] Create timeline UI component
- [x] Add event type display configuration
- [x] Format timeline as markdown
- [x] Format timeline as dataframe
- [x] Add filter controls
- [x] Add export functionality
- [x] Write tests

## Definition of Done

- [x] Events logged correctly
- [x] Timeline displays chronologically
- [x] Filtering works by event type
- [x] Export works in JSON and CSV
- [x] UI shows event details
- [x] Tests pass

## File List

### New Files
- `src/walltrack/services/positions/timeline_service.py` - Timeline service
- `src/walltrack/ui/components/position_timeline.py` - Timeline UI

### Modified Files
- `src/walltrack/ui/components/position_details.py` - Integrate timeline
- `src/walltrack/services/positions/__init__.py` - Export timeline service
