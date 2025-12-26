"""Tests for discovery API endpoints."""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from walltrack.api.routes.discovery import router
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunParams,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)


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


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create mock Supabase client."""
    return MagicMock()


@pytest.fixture
def mock_repo() -> MagicMock:
    """Create mock DiscoveryRepository."""
    repo = MagicMock()
    repo.create_run = AsyncMock()
    repo.get_run = AsyncMock()
    repo.get_runs = AsyncMock()
    repo.get_stats = AsyncMock()
    repo.complete_run = AsyncMock()
    repo.fail_run = AsyncMock()
    return repo


class TestTriggerDiscoveryEndpoint:
    """Tests for POST /api/discovery/run."""

    def test_trigger_discovery_returns_run_id(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that trigger_discovery returns a run_id."""
        run_id = uuid4()
        mock_repo.create_run.return_value = DiscoveryRun(
            id=run_id,
            started_at=datetime.now(UTC),
            trigger_type=TriggerType.API,
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.post(
                "/api/discovery/run",
                json={"min_price_change_pct": 100.0},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == str(run_id)
        assert data["status"] == "started"
        assert "message" in data

    def test_trigger_discovery_uses_default_params(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that trigger_discovery uses default parameters."""
        run_id = uuid4()
        mock_repo.create_run.return_value = DiscoveryRun(
            id=run_id,
            started_at=datetime.now(UTC),
            trigger_type=TriggerType.API,
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.post("/api/discovery/run", json={})

        assert response.status_code == 200

    def test_trigger_discovery_validates_params(
        self,
        client: TestClient,
    ) -> None:
        """Test that trigger_discovery validates parameters."""
        response = client.post(
            "/api/discovery/run",
            json={"min_price_change_pct": -50.0},  # Invalid: must be >= 0
        )

        assert response.status_code == 422  # Validation error


class TestGetRunEndpoint:
    """Tests for GET /api/discovery/runs/{run_id}."""

    def test_get_run_returns_run(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that get_run returns the run."""
        run_id = uuid4()
        mock_repo.get_run.return_value = DiscoveryRun(
            id=run_id,
            started_at=datetime.now(UTC),
            trigger_type=TriggerType.MANUAL,
            status=RunStatus.COMPLETED,
            tokens_analyzed=10,
            new_wallets=25,
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get(f"/api/discovery/runs/{run_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == str(run_id)
        assert data["status"] == "completed"
        assert data["tokens_analyzed"] == 10
        assert data["new_wallets"] == 25

    def test_get_run_returns_404_when_not_found(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that get_run returns 404 for missing run."""
        mock_repo.get_run.return_value = None

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get(f"/api/discovery/runs/{uuid4()}")

        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"


class TestListRunsEndpoint:
    """Tests for GET /api/discovery/runs."""

    def test_list_runs_returns_empty_list(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that list_runs returns empty list when no runs."""
        mock_repo.get_runs.return_value = []

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/runs")

        assert response.status_code == 200
        data = response.json()
        assert data["runs"] == []
        assert data["page"] == 1
        assert data["has_more"] is False

    def test_list_runs_returns_paginated_results(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that list_runs returns paginated results."""
        runs = [
            DiscoveryRun(
                id=uuid4(),
                started_at=datetime.now(UTC),
                trigger_type=TriggerType.SCHEDULED,
            )
            for _ in range(3)
        ]
        mock_repo.get_runs.return_value = runs

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/runs?page=1&page_size=10")

        assert response.status_code == 200
        data = response.json()
        assert len(data["runs"]) == 3
        assert data["page"] == 1
        assert data["page_size"] == 10

    def test_list_runs_filters_by_status(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that list_runs filters by status."""
        mock_repo.get_runs.return_value = []

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/runs?status=completed")

        assert response.status_code == 200
        mock_repo.get_runs.assert_called_once()
        call_kwargs = mock_repo.get_runs.call_args[1]
        assert call_kwargs["status"] == RunStatus.COMPLETED

    def test_list_runs_rejects_invalid_status(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that list_runs rejects invalid status."""
        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/runs?status=invalid")

        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]


class TestStatsEndpoint:
    """Tests for GET /api/discovery/stats."""

    def test_get_stats_returns_statistics(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that get_stats returns statistics."""
        mock_repo.get_stats.return_value = DiscoveryStats(
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            total_wallets_discovered=1000,
            avg_wallets_per_run=10.0,
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_runs"] == 100
        assert data["successful_runs"] == 95
        assert data["failed_runs"] == 5
        assert data["total_wallets_discovered"] == 1000
        assert data["avg_wallets_per_run"] == 10.0

    def test_get_stats_with_date_range(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that get_stats accepts date range."""
        mock_repo.get_stats.return_value = DiscoveryStats()

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get(
                "/api/discovery/stats"
                "?start_date=2024-01-01T00:00:00Z"
                "&end_date=2024-01-31T23:59:59Z"
            )

        assert response.status_code == 200


class TestConfigEndpoints:
    """Tests for GET/PUT /api/discovery/config."""

    def test_get_config_returns_defaults(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that get_config returns default configuration."""
        mock_repo.get_stats.return_value = DiscoveryStats(
            last_run_at=datetime.now(UTC),
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.get("/api/discovery/config")

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is True
        assert data["schedule_hours"] == 6
        assert "params" in data

    def test_update_config_returns_updated(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that update_config returns updated configuration."""
        response = client.put(
            "/api/discovery/config",
            json={
                "enabled": False,
                "schedule_hours": 12,
                "params": {"max_tokens": 50},
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["enabled"] is False
        assert data["schedule_hours"] == 12
        assert data["params"]["max_tokens"] == 50

    def test_update_config_validates_schedule_hours(
        self,
        client: TestClient,
    ) -> None:
        """Test that update_config validates schedule_hours."""
        response = client.put(
            "/api/discovery/config",
            json={"schedule_hours": 0},  # Invalid: must be >= 1
        )

        assert response.status_code == 422


class TestRequestModels:
    """Tests for request/response models."""

    def test_trigger_request_validates_max_constraints(
        self,
        client: TestClient,
    ) -> None:
        """Test that trigger request validates max constraints."""
        response = client.post(
            "/api/discovery/run",
            json={"min_price_change_pct": 2000},  # Invalid: max 1000
        )

        assert response.status_code == 422

    def test_trigger_request_accepts_all_params(
        self,
        client: TestClient,
        mock_repo: MagicMock,
    ) -> None:
        """Test that trigger request accepts all parameters."""
        run_id = uuid4()
        mock_repo.create_run.return_value = DiscoveryRun(
            id=run_id,
            started_at=datetime.now(UTC),
            trigger_type=TriggerType.API,
        )

        with (
            patch(
                "walltrack.api.routes.discovery.get_supabase_client",
                new=AsyncMock(),
            ),
            patch(
                "walltrack.api.routes.discovery.DiscoveryRepository",
                return_value=mock_repo,
            ),
        ):
            response = client.post(
                "/api/discovery/run",
                json={
                    "min_price_change_pct": 150.0,
                    "min_volume_usd": 75000.0,
                    "max_token_age_hours": 48,
                    "early_window_minutes": 20,
                    "min_profit_pct": 60.0,
                    "max_tokens": 30,
                    "profile_immediately": False,
                },
            )

        assert response.status_code == 200
