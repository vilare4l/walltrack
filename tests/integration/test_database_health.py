"""Integration tests for database health endpoint."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


class TestDatabaseHealthEndpoint:
    """Tests for /api/health with database status."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.app_name = "WallTrack"
        settings.app_version = "2.0.0"
        settings.supabase_url = "https://test.supabase.co"
        settings.supabase_key.get_secret_value.return_value = "key"
        settings.neo4j_uri = "bolt://localhost:7687"
        settings.neo4j_user = "neo4j"
        settings.neo4j_password.get_secret_value.return_value = "pass"
        return settings

    @pytest.fixture(autouse=True)
    def reset_singletons(self) -> None:
        """Reset database singletons before and after each test."""
        import walltrack.data.neo4j.client as neo4j_module
        import walltrack.data.supabase.client as supabase_module

        # Clear before test
        neo4j_module._neo4j_client = None
        supabase_module._supabase_client = None

        yield

        # Clear after test
        neo4j_module._neo4j_client = None
        supabase_module._supabase_client = None

    def test_health_returns_database_status(self, mock_settings: MagicMock) -> None:
        """
        Given: Both databases are connected
        When: GET /api/health is called
        Then: Returns status with database health info
        """
        mock_supabase_async_client = AsyncMock()
        mock_neo4j_driver = AsyncMock()
        mock_neo4j_driver.verify_connectivity = AsyncMock()

        with (
            patch(
                "walltrack.config.settings.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.main.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.create_async_client",
                new_callable=AsyncMock,
                return_value=mock_supabase_async_client,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_neo4j_driver,
            ),
        ):
            from walltrack.main import create_app

            app = create_app()
            client = TestClient(app)

            response = client.get("/api/health")

            assert response.status_code == 200
            data = response.json()
            assert "status" in data
            assert "databases" in data
            assert "supabase" in data["databases"]
            assert "neo4j" in data["databases"]

    def test_health_returns_ok_when_all_healthy(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: Both databases are healthy
        When: GET /api/health is called
        Then: Overall status is "ok"

        This test directly sets up mock clients as singletons to simulate
        healthy database connections, bypassing the lifespan connection logic.
        """
        import walltrack.data.neo4j.client as neo4j_module
        import walltrack.data.supabase.client as supabase_module
        from walltrack.data.neo4j.client import Neo4jClient
        from walltrack.data.supabase.client import SupabaseClient

        # Create mock clients that return healthy status
        mock_supabase = MagicMock(spec=SupabaseClient)
        mock_supabase.health_check = AsyncMock(
            return_value={"status": "connected", "healthy": True}
        )

        mock_neo4j = MagicMock(spec=Neo4jClient)
        mock_neo4j.health_check = AsyncMock(
            return_value={"status": "connected", "healthy": True}
        )

        # Set the singletons directly
        supabase_module._supabase_client = mock_supabase
        neo4j_module._neo4j_client = mock_neo4j

        with (
            patch(
                "walltrack.config.settings.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.api.routes.health.get_settings",
                return_value=mock_settings,
            ),
        ):
            from walltrack.main import create_app

            app = create_app()
            # Skip lifespan by not using TestClient context manager
            # Instead, create routes directly
            from fastapi.testclient import TestClient

            # Use TestClient without lifespan events
            with TestClient(app, raise_server_exceptions=True) as client:
                response = client.get("/api/health")

            data = response.json()
            assert data["status"] == "ok"
            assert data["databases"]["supabase"]["healthy"] is True
            assert data["databases"]["neo4j"]["healthy"] is True

    def test_health_returns_degraded_when_database_down(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: Databases are not connected
        When: GET /api/health is called
        Then: Overall status is "degraded"
        """
        with (
            patch(
                "walltrack.config.settings.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.main.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.main.get_supabase_client",
                new_callable=AsyncMock,
                side_effect=Exception("Supabase down"),
            ),
            patch(
                "walltrack.main.get_neo4j_client",
                new_callable=AsyncMock,
                side_effect=Exception("Neo4j down"),
            ),
        ):
            from walltrack.main import create_app

            app = create_app()
            client = TestClient(app)

            response = client.get("/api/health")

            data = response.json()
            assert data["status"] == "degraded"

    def test_health_includes_version(self, mock_settings: MagicMock) -> None:
        """
        Given: Application is running
        When: GET /api/health is called
        Then: Response includes version
        """
        mock_supabase_async_client = AsyncMock()
        mock_neo4j_driver = AsyncMock()
        mock_neo4j_driver.verify_connectivity = AsyncMock()

        with (
            patch(
                "walltrack.config.settings.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.main.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.create_async_client",
                new_callable=AsyncMock,
                return_value=mock_supabase_async_client,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_neo4j_driver,
            ),
        ):
            from walltrack.main import create_app

            app = create_app()
            client = TestClient(app)

            response = client.get("/api/health")

            data = response.json()
            assert "version" in data
            assert data["version"] == "2.0.0"
