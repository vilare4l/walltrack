"""Tests for position timeline service."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.services.positions.timeline_service import (
    PositionEvent,
    PositionEventType,
    PositionTimeline,
    PositionTimelineService,
    reset_timeline_service,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock Supabase client."""
    client = MagicMock()
    client.table = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.insert = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.in_ = MagicMock(return_value=client)
    client.order = MagicMock(return_value=client)
    client.range = MagicMock(return_value=client)
    client.limit = MagicMock(return_value=client)
    client.single = MagicMock(return_value=client)
    client.execute = AsyncMock()
    return client


@pytest.fixture
def sample_event_row() -> dict:
    """Create sample event row from database."""
    return {
        "id": "event-123",
        "position_id": "position-123",
        "event_type": "tp_triggered",
        "timestamp": "2024-01-01T12:00:00+00:00",
        "price_at_event": "1.5",
        "data_before": None,
        "data_after": None,
        "metadata": {"exit_pct": 50, "pnl_pct": 50.0},
        "comment": "First take profit",
    }


@pytest.fixture
def sample_position_data() -> dict:
    """Create sample position data."""
    return {
        "id": "position-123",
        "token_symbol": "TEST",
        "entry_time": "2024-01-01T10:00:00+00:00",
        "exit_time": "2024-01-01T14:00:00+00:00",
    }


@pytest.fixture
def service() -> PositionTimelineService:
    """Create service instance."""
    reset_timeline_service()
    return PositionTimelineService()


class TestPositionEventType:
    """Tests for PositionEventType enum."""

    def test_event_types_exist(self) -> None:
        """All expected event types exist."""
        assert PositionEventType.CREATED.value == "created"
        assert PositionEventType.TP_TRIGGERED.value == "tp_triggered"
        assert PositionEventType.SL_TRIGGERED.value == "sl_triggered"
        assert PositionEventType.STRATEGY_CHANGED.value == "strategy_changed"
        assert PositionEventType.CLOSED.value == "closed"

    def test_event_type_is_string(self) -> None:
        """Event type values are strings."""
        for event_type in PositionEventType:
            assert isinstance(event_type.value, str)


class TestPositionEvent:
    """Tests for PositionEvent dataclass."""

    def test_creates_event(self) -> None:
        """PositionEvent initializes correctly."""
        now = datetime.now(UTC)
        event = PositionEvent(
            id="event-1",
            position_id="pos-1",
            event_type=PositionEventType.TP_TRIGGERED,
            timestamp=now,
            price_at_event=Decimal("1.5"),
            data_before=None,
            data_after={"exit_pct": 50},
            metadata={"pnl_pct": 50.0},
            comment="Test",
        )

        assert event.id == "event-1"
        assert event.event_type == PositionEventType.TP_TRIGGERED
        assert event.price_at_event == Decimal("1.5")

    def test_default_metadata(self) -> None:
        """PositionEvent has default empty metadata."""
        now = datetime.now(UTC)
        event = PositionEvent(
            id="event-1",
            position_id="pos-1",
            event_type=PositionEventType.CREATED,
            timestamp=now,
            price_at_event=None,
            data_before=None,
            data_after=None,
        )

        assert event.metadata == {}
        assert event.comment is None


class TestPositionTimeline:
    """Tests for PositionTimeline dataclass."""

    def test_creates_timeline(self) -> None:
        """PositionTimeline initializes correctly."""
        entry = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        exit_time = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)

        timeline = PositionTimeline(
            position_id="pos-1",
            token_symbol="TEST",
            entry_time=entry,
            exit_time=exit_time,
            events=[],
            total_events=0,
        )

        assert timeline.position_id == "pos-1"
        assert timeline.token_symbol == "TEST"

    def test_duration_hours(self) -> None:
        """duration_hours calculates correctly."""
        entry = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        exit_time = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)

        timeline = PositionTimeline(
            position_id="pos-1",
            token_symbol="TEST",
            entry_time=entry,
            exit_time=exit_time,
            events=[],
            total_events=0,
        )

        assert timeline.duration_hours == 4.0

    def test_duration_hours_active_position(self) -> None:
        """duration_hours works for active positions."""
        entry = datetime.now(UTC)

        timeline = PositionTimeline(
            position_id="pos-1",
            token_symbol="TEST",
            entry_time=entry,
            exit_time=None,  # Still active
            events=[],
            total_events=0,
        )

        # Should be close to 0 since just created
        assert timeline.duration_hours >= 0
        assert timeline.duration_hours < 1


class TestPositionTimelineService:
    """Tests for PositionTimelineService."""

    @pytest.mark.asyncio
    async def test_log_event(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_event_row: dict,
    ) -> None:
        """log_event creates event in database."""
        mock_client.execute.return_value = MagicMock(data=[sample_event_row])

        with patch.object(service, "_get_client", return_value=mock_client):
            event = await service.log_event(
                position_id="position-123",
                event_type=PositionEventType.TP_TRIGGERED,
                price_at_event=Decimal("1.5"),
                metadata={"exit_pct": 50},
                comment="First take profit",
            )

        assert event.id == "event-123"
        assert event.event_type == PositionEventType.TP_TRIGGERED
        mock_client.table.assert_called_with("position_events")
        mock_client.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_timeline(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_position_data: dict,
        sample_event_row: dict,
    ) -> None:
        """get_timeline returns timeline with events."""
        # First call returns position, second returns count, third returns events
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(count=1),
            MagicMock(data=[sample_event_row]),
        ]

        with patch.object(service, "_get_client", return_value=mock_client):
            timeline = await service.get_timeline("position-123")

        assert timeline.position_id == "position-123"
        assert timeline.token_symbol == "TEST"
        assert len(timeline.events) == 1
        assert timeline.total_events == 1

    @pytest.mark.asyncio
    async def test_get_timeline_position_not_found(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
    ) -> None:
        """get_timeline raises error when position not found."""
        mock_client.execute.return_value = MagicMock(data=None)

        with (
            patch.object(service, "_get_client", return_value=mock_client),
            pytest.raises(ValueError, match="Position not found"),
        ):
            await service.get_timeline("invalid-id")

    @pytest.mark.asyncio
    async def test_get_timeline_with_filter(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_position_data: dict,
        sample_event_row: dict,
    ) -> None:
        """get_timeline filters by event types."""
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(count=1),
            MagicMock(data=[sample_event_row]),
        ]

        with patch.object(service, "_get_client", return_value=mock_client):
            timeline = await service.get_timeline(
                "position-123",
                event_types=[PositionEventType.TP_TRIGGERED],
            )

        assert len(timeline.events) == 1
        mock_client.in_.assert_called()

    @pytest.mark.asyncio
    async def test_get_events_by_type(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_event_row: dict,
    ) -> None:
        """get_events_by_type returns filtered events."""
        mock_client.execute.return_value = MagicMock(data=[sample_event_row])

        with patch.object(service, "_get_client", return_value=mock_client):
            events = await service.get_events_by_type(
                "position-123",
                PositionEventType.TP_TRIGGERED,
            )

        assert len(events) == 1
        assert events[0].event_type == PositionEventType.TP_TRIGGERED

    @pytest.mark.asyncio
    async def test_get_latest_event(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_event_row: dict,
    ) -> None:
        """get_latest_event returns most recent event."""
        mock_client.execute.return_value = MagicMock(data=[sample_event_row])

        with patch.object(service, "_get_client", return_value=mock_client):
            event = await service.get_latest_event("position-123")

        assert event is not None
        assert event.id == "event-123"
        mock_client.order.assert_called_with("timestamp", desc=True)
        mock_client.limit.assert_called_with(1)

    @pytest.mark.asyncio
    async def test_get_latest_event_none(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
    ) -> None:
        """get_latest_event returns None when no events."""
        mock_client.execute.return_value = MagicMock(data=[])

        with patch.object(service, "_get_client", return_value=mock_client):
            event = await service.get_latest_event("position-123")

        assert event is None


class TestExportTimeline:
    """Tests for export_timeline."""

    @pytest.mark.asyncio
    async def test_export_json(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_position_data: dict,
        sample_event_row: dict,
    ) -> None:
        """export_timeline exports as JSON."""
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(count=1),
            MagicMock(data=[sample_event_row]),
        ]

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.export_timeline("position-123", "json")

        import json

        data = json.loads(result)
        assert data["position_id"] == "position-123"
        assert data["token_symbol"] == "TEST"
        assert len(data["events"]) == 1

    @pytest.mark.asyncio
    async def test_export_csv(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_position_data: dict,
        sample_event_row: dict,
    ) -> None:
        """export_timeline exports as CSV."""
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(count=1),
            MagicMock(data=[sample_event_row]),
        ]

        with patch.object(service, "_get_client", return_value=mock_client):
            result = await service.export_timeline("position-123", "csv")

        assert "timestamp" in result  # Header
        assert "tp_triggered" in result  # Event type
        assert "First take profit" in result  # Comment

    @pytest.mark.asyncio
    async def test_export_invalid_format(
        self,
        service: PositionTimelineService,
        mock_client: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """export_timeline raises error for invalid format."""
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(count=0),
            MagicMock(data=[]),
        ]

        with (
            patch.object(service, "_get_client", return_value=mock_client),
            pytest.raises(ValueError, match="Unknown format"),
        ):
            await service.export_timeline("position-123", "xml")


class TestRowToEvent:
    """Tests for _row_to_event helper."""

    def test_converts_row(self, service: PositionTimelineService) -> None:
        """_row_to_event converts database row to PositionEvent."""
        row = {
            "id": "event-1",
            "position_id": "pos-1",
            "event_type": "created",
            "timestamp": "2024-01-01T10:00:00+00:00",
            "price_at_event": "1.0",
            "data_before": None,
            "data_after": {"status": "active"},
            "metadata": {"source": "signal"},
            "comment": None,
        }

        event = service._row_to_event(row)

        assert event.id == "event-1"
        assert event.event_type == PositionEventType.CREATED
        assert event.price_at_event == Decimal("1.0")
        assert event.data_after == {"status": "active"}

    def test_handles_null_values(self, service: PositionTimelineService) -> None:
        """_row_to_event handles null values."""
        row = {
            "id": "event-1",
            "position_id": "pos-1",
            "event_type": "created",
            "timestamp": "2024-01-01T10:00:00Z",
            "price_at_event": None,
            "data_before": None,
            "data_after": None,
            "metadata": None,
            "comment": None,
        }

        event = service._row_to_event(row)

        assert event.price_at_event is None
        assert event.metadata == {}
