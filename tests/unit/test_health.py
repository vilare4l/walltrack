"""Tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """Create test client for the FastAPI app."""
    from walltrack.main import app

    return TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_endpoint_returns_ok(self, client: TestClient) -> None:
        """
        Given: The application is running
        When: GET /api/health is called
        Then: Returns 200 with status and database info
        """
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        # Health endpoint now returns database status
        assert "status" in data
        assert data["status"] in ["ok", "degraded"]  # Either is valid
        assert "version" in data
        assert "databases" in data
        assert "supabase" in data["databases"]
        assert "neo4j" in data["databases"]

    def test_health_endpoint_includes_scheduler_status(self, client: TestClient) -> None:
        """
        Given: The application is running with scheduler module
        When: GET /api/health is called
        Then: Returns scheduler status with enabled, running, and next_run fields

        Story 2.4 - AC1: Health endpoint reports scheduler status
        """
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()

        # Scheduler info should be present
        assert "scheduler" in data
        scheduler = data["scheduler"]
        assert "enabled" in scheduler
        assert "running" in scheduler
        assert "next_run" in scheduler

        # enabled should be a boolean
        assert isinstance(scheduler["enabled"], bool)
        # running should be a boolean
        assert isinstance(scheduler["running"], bool)
        # next_run should be None or ISO datetime string
        assert scheduler["next_run"] is None or isinstance(scheduler["next_run"], str)

    def test_health_endpoint_method_not_allowed(self, client: TestClient) -> None:
        """
        Given: The application is running
        When: POST /api/health is called
        Then: Returns 405 Method Not Allowed
        """
        response = client.post("/api/health")

        assert response.status_code == 405
