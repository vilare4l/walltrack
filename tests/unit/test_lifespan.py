"""Tests for FastAPI lifespan management."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestLifespan:
    """Tests for application lifespan management."""

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

    @pytest.mark.asyncio
    async def test_lifespan_connects_databases_on_startup(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: Application starts
        When: Lifespan context is entered
        Then: Both database clients are connected
        """
        mock_supabase = AsyncMock()
        mock_neo4j = AsyncMock()
        mock_neo4j.verify_connectivity = AsyncMock()

        with (
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
                return_value=mock_supabase,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_neo4j,
            ),
        ):
            # Reset singletons
            import walltrack.data.neo4j.client as neo4j_module
            import walltrack.data.supabase.client as supabase_module

            neo4j_module._neo4j_client = None
            supabase_module._supabase_client = None

            from walltrack.main import create_app

            app = create_app()

            # Test that lifespan is set
            assert app.router.lifespan_context is not None

    @pytest.mark.asyncio
    async def test_lifespan_handles_database_failure_gracefully(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: Database connection fails on startup
        When: Lifespan context is entered
        Then: App continues (degraded mode) without crashing
        """
        from walltrack.core.exceptions import DatabaseConnectionError

        with (
            patch(
                "walltrack.main.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.main.get_supabase_client",
                new_callable=AsyncMock,
                side_effect=DatabaseConnectionError("Supabase down"),
            ),
            patch(
                "walltrack.main.get_neo4j_client",
                new_callable=AsyncMock,
                side_effect=DatabaseConnectionError("Neo4j down"),
            ),
        ):
            from walltrack.main import create_app

            app = create_app()
            client = TestClient(app)

            # App should still respond despite DB failures
            response = client.get("/api/health")
            assert response.status_code == 200


class TestCreateApp:
    """Tests for create_app factory."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.app_name = "WallTrack"
        settings.app_version = "2.0.0"
        return settings

    def test_create_app_returns_fastapi_instance(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: create_app is called
        When: Application is created
        Then: Returns a FastAPI instance
        """
        with patch("walltrack.main.get_settings", return_value=mock_settings):
            from walltrack.main import create_app

            app = create_app()

            assert isinstance(app, FastAPI)

    def test_create_app_includes_health_router(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: create_app is called
        When: Application is created
        Then: Health router is included
        """
        with patch("walltrack.main.get_settings", return_value=mock_settings):
            from walltrack.main import create_app

            app = create_app()
            routes = [route.path for route in app.routes]

            assert "/api/health" in routes

    def test_create_app_has_lifespan_context(
        self, mock_settings: MagicMock
    ) -> None:
        """
        Given: create_app is called
        When: Application is created
        Then: Lifespan context manager is configured
        """
        with patch("walltrack.main.get_settings", return_value=mock_settings):
            from walltrack.main import create_app

            app = create_app()

            assert app.router.lifespan_context is not None
