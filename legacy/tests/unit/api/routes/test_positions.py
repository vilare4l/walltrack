"""Tests for positions API endpoints."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from walltrack.api.routes.positions import router


@pytest.fixture
def app() -> FastAPI:
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/api")
    return app


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    """Create test client."""
    return TestClient(app)


def create_supabase_mock(return_data, count: int | None = None):
    """Create a properly chained async Supabase mock."""
    result_mock = MagicMock()
    result_mock.data = return_data
    result_mock.count = count

    chain = MagicMock()
    chain.table.return_value = chain
    chain.select.return_value = chain
    chain.eq.return_value = chain
    chain.in_.return_value = chain
    chain.order.return_value = chain
    chain.range.return_value = chain
    chain.limit.return_value = chain
    chain.single.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.execute = AsyncMock(return_value=result_mock)

    return chain


@pytest.fixture
def sample_position() -> dict:
    """Sample position data."""
    return {
        "id": "pos-123",
        "token_address": "token123",
        "token_symbol": "TEST",
        "entry_price": "1.0",
        "exit_price": "1.5",
        "entry_time": "2024-01-01T10:00:00+00:00",
        "exit_time": "2024-01-01T14:00:00+00:00",
        "status": "closed",
        "pnl_pct": "50.0",
        "pnl_sol": "5.0",
        "size_sol": "10.0",
        "exit_strategies": {"name": "Test Strategy"},
    }


@pytest.fixture
def sample_active_position() -> dict:
    """Sample active position data."""
    return {
        "id": "pos-456",
        "token_address": "token456",
        "token_symbol": "ACTIVE",
        "entry_price": "2.0",
        "exit_price": None,
        "current_price": "2.5",
        "entry_time": "2024-01-15T10:00:00+00:00",
        "exit_time": None,
        "status": "active",
        "pnl_pct": "25.0",
        "pnl_sol": "2.5",
        "size_sol": "10.0",
        "remaining_pct": "100",
        "exit_strategy_id": "strat-1",
        "exit_type": None,
        "conviction_tier": "high",
        "exit_strategies": {
            "id": "strat-1",
            "name": "Aggressive",
            "rules": [
                {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50, "enabled": True},
                {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "enabled": True},
            ],
        },
    }


class TestListPositions:
    """Tests for GET /positions endpoint."""

    def test_list_positions_success(
        self,
        client: TestClient,
        sample_position: dict,
    ) -> None:
        """Test successful listing of positions."""
        mock_supabase = create_supabase_mock([sample_position], count=1)

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/positions")

        assert response.status_code == 200
        data = response.json()
        assert len(data["positions"]) == 1
        assert data["total"] == 1
        assert data["positions"][0]["id"] == "pos-123"

    def test_list_positions_with_status_filter(
        self,
        client: TestClient,
        sample_position: dict,
    ) -> None:
        """Test filtering by status."""
        mock_supabase = create_supabase_mock([sample_position], count=1)

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/positions?status=closed")

        assert response.status_code == 200
        mock_supabase.eq.assert_called()

    def test_list_positions_pagination(
        self,
        client: TestClient,
    ) -> None:
        """Test pagination parameters."""
        mock_supabase = create_supabase_mock([], count=0)

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/positions?limit=10&offset=20")

        assert response.status_code == 200
        data = response.json()
        assert data["limit"] == 10
        assert data["offset"] == 20


class TestGetPosition:
    """Tests for GET /positions/{id} endpoint."""

    def test_get_position_success(
        self,
        client: TestClient,
        sample_active_position: dict,
    ) -> None:
        """Test successful retrieval of position details."""
        # First call returns position, second returns history count
        mock_supabase = MagicMock()
        position_result = MagicMock(data=sample_active_position)
        history_result = MagicMock(data=[], count=5)
        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=[position_result, history_result])

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/positions/pos-456")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "pos-456"
        assert data["status"] == "active"
        assert data["price_history_count"] == 5
        # Strategy levels should be calculated for active position
        assert data["strategy_levels"] is not None

    def test_get_position_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test 404 when position not found."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.get("/api/positions/invalid-id")

        assert response.status_code == 404


class TestChangeStrategy:
    """Tests for PATCH /positions/{id}/strategy endpoint."""

    def test_change_strategy_success(
        self,
        client: TestClient,
        sample_active_position: dict,
    ) -> None:
        """Test successful strategy change."""
        mock_supabase = MagicMock()
        position_result = MagicMock(data=sample_active_position)
        update_result = MagicMock(data=None)
        mock_supabase.table.return_value = mock_supabase
        mock_supabase.select.return_value = mock_supabase
        mock_supabase.eq.return_value = mock_supabase
        mock_supabase.single.return_value = mock_supabase
        mock_supabase.update.return_value = mock_supabase
        mock_supabase.execute = AsyncMock(side_effect=[position_result, update_result])

        mock_strategy = MagicMock()
        mock_strategy.status = "active"
        mock_strategy.name = "New Strategy"
        mock_strategy.rules = [
            MagicMock(enabled=True, trigger_pct=Decimal("30"), exit_pct=Decimal("50"), rule_type="take_profit"),
        ]

        mock_strategy_service = MagicMock()
        mock_strategy_service.get = AsyncMock(return_value=mock_strategy)

        mock_timeline = MagicMock()
        mock_timeline.log_event = AsyncMock()

        with (
            patch(
                "walltrack.api.routes.positions.get_supabase_client",
                new=AsyncMock(return_value=mock_supabase),
            ),
            patch(
                "walltrack.api.routes.positions.get_exit_strategy_service",
                new=AsyncMock(return_value=mock_strategy_service),
            ),
            patch(
                "walltrack.api.routes.positions.get_timeline_service",
                new=AsyncMock(return_value=mock_timeline),
            ),
        ):
            response = client.patch(
                "/api/positions/pos-456/strategy",
                json={"strategy_id": "new-strat", "reason": "Testing"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["new_strategy_id"] == "new-strat"

    def test_change_strategy_position_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test error when position not found."""
        mock_supabase = create_supabase_mock(None)

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.patch(
                "/api/positions/invalid/strategy",
                json={"strategy_id": "new-strat"},
            )

        assert response.status_code == 404

    def test_change_strategy_not_active(
        self,
        client: TestClient,
        sample_position: dict,
    ) -> None:
        """Test error when position is not active."""
        mock_supabase = create_supabase_mock(sample_position)  # status=closed

        with patch(
            "walltrack.api.routes.positions.get_supabase_client",
            new=AsyncMock(return_value=mock_supabase),
        ):
            response = client.patch(
                "/api/positions/pos-123/strategy",
                json={"strategy_id": "new-strat"},
            )

        assert response.status_code == 400
        assert "active" in response.json()["detail"].lower()


class TestGetTimeline:
    """Tests for GET /positions/{id}/timeline endpoint."""

    def test_get_timeline_success(
        self,
        client: TestClient,
    ) -> None:
        """Test successful timeline retrieval."""
        mock_timeline = MagicMock()
        mock_timeline.position_id = "pos-123"
        mock_timeline.token_symbol = "TEST"
        mock_timeline.entry_time = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        mock_timeline.exit_time = datetime(2024, 1, 1, 14, 0, 0, tzinfo=UTC)
        mock_timeline.duration_hours = 4.0
        mock_timeline.total_events = 2

        event = MagicMock()
        event.id = "event-1"
        event.event_type = MagicMock(value="created")
        event.timestamp = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC)
        event.price_at_event = Decimal("1.0")
        event.data_before = None
        event.data_after = {"status": "active"}
        event.metadata = {}
        event.comment = None
        mock_timeline.events = [event]

        mock_service = MagicMock()
        mock_service.get_timeline = AsyncMock(return_value=mock_timeline)

        with patch(
            "walltrack.api.routes.positions.get_timeline_service",
            new=AsyncMock(return_value=mock_service),
        ):
            response = client.get("/api/positions/pos-123/timeline")

        assert response.status_code == 200
        data = response.json()
        assert data["position_id"] == "pos-123"
        assert len(data["events"]) == 1

    def test_get_timeline_not_found(
        self,
        client: TestClient,
    ) -> None:
        """Test timeline error when position not found."""
        mock_service = MagicMock()
        mock_service.get_timeline = AsyncMock(side_effect=ValueError("Position not found"))

        with patch(
            "walltrack.api.routes.positions.get_timeline_service",
            new=AsyncMock(return_value=mock_service),
        ):
            response = client.get("/api/positions/invalid/timeline")

        assert response.status_code == 404


class TestExportTimeline:
    """Tests for GET /positions/{id}/timeline/export endpoint."""

    def test_export_json(
        self,
        client: TestClient,
    ) -> None:
        """Test JSON export."""
        mock_service = MagicMock()
        mock_service.export_timeline = AsyncMock(return_value='{"test": true}')

        with patch(
            "walltrack.api.routes.positions.get_timeline_service",
            new=AsyncMock(return_value=mock_service),
        ):
            response = client.get("/api/positions/pos-123/timeline/export?format=json")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "json"

    def test_export_csv(
        self,
        client: TestClient,
    ) -> None:
        """Test CSV export."""
        mock_service = MagicMock()
        mock_service.export_timeline = AsyncMock(return_value="timestamp,event\n...")

        with patch(
            "walltrack.api.routes.positions.get_timeline_service",
            new=AsyncMock(return_value=mock_service),
        ):
            response = client.get("/api/positions/pos-123/timeline/export?format=csv")

        assert response.status_code == 200
        data = response.json()
        assert data["format"] == "csv"
