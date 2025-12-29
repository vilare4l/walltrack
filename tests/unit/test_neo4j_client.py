"""Tests for Neo4j client."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

if TYPE_CHECKING:
    from walltrack.data.neo4j.client import Neo4jClient


class TestNeo4jClient:
    """Tests for Neo4jClient class."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.neo4j_uri = "bolt://localhost:7687"
        settings.neo4j_user = "neo4j"
        settings.neo4j_password.get_secret_value.return_value = "test-password"
        return settings

    @pytest.fixture
    def neo4j_client(self, mock_settings: MagicMock) -> "Neo4jClient":
        """Create Neo4jClient with mocked settings."""
        with patch(
            "walltrack.data.neo4j.client.get_settings", return_value=mock_settings
        ):
            from walltrack.data.neo4j.client import Neo4jClient

            return Neo4jClient()

    def test_init_sets_driver_to_none(self, neo4j_client) -> None:
        """
        Given: New Neo4jClient
        When: Initialized
        Then: Internal driver is None
        """
        assert neo4j_client._driver is None

    @pytest.mark.asyncio
    async def test_connect_creates_driver(
        self, neo4j_client, mock_settings: MagicMock
    ) -> None:
        """
        Given: Neo4jClient not connected
        When: connect() is called
        Then: Async driver is created with correct credentials
        """
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()

        with patch(
            "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
            return_value=mock_driver,
        ) as mock_create:
            await neo4j_client.connect()

            mock_create.assert_called_once_with(
                mock_settings.neo4j_uri,
                auth=(
                    mock_settings.neo4j_user,
                    mock_settings.neo4j_password.get_secret_value(),
                ),
            )
            assert neo4j_client._driver is mock_driver
            mock_driver.verify_connectivity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, neo4j_client) -> None:
        """
        Given: Neo4jClient already connected
        When: connect() is called again
        Then: Connection is not re-established
        """
        neo4j_client._driver = MagicMock()

        with patch(
            "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
        ) as mock_create:
            await neo4j_client.connect()

            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_raises_database_connection_error_on_failure(
        self, neo4j_client
    ) -> None:
        """
        Given: Neo4j connection fails
        When: connect() is called
        Then: DatabaseConnectionError is raised
        """
        from walltrack.core.exceptions import DatabaseConnectionError

        with patch(
            "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
            side_effect=Exception("Connection refused"),
        ):
            with pytest.raises(DatabaseConnectionError, match="Neo4j"):
                await neo4j_client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_closes_driver(self, neo4j_client) -> None:
        """
        Given: Neo4jClient connected
        When: disconnect() is called
        Then: Driver is closed and set to None
        """
        mock_driver = AsyncMock()
        neo4j_client._driver = mock_driver

        await neo4j_client.disconnect()

        mock_driver.close.assert_awaited_once()
        assert neo4j_client._driver is None

    @pytest.mark.asyncio
    async def test_health_check_returns_disconnected_when_not_connected(
        self, neo4j_client
    ) -> None:
        """
        Given: Neo4jClient not connected
        When: health_check() is called
        Then: Returns disconnected status
        """
        result = await neo4j_client.health_check()

        assert result["status"] == "disconnected"
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_health_check_returns_connected_when_connected(
        self, neo4j_client
    ) -> None:
        """
        Given: Neo4jClient connected
        When: health_check() is called
        Then: Returns connected status with ping
        """
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()
        neo4j_client._driver = mock_driver

        result = await neo4j_client.health_check()

        assert result["status"] == "connected"
        assert result["healthy"] is True
        mock_driver.verify_connectivity.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_returns_error_on_failure(self, neo4j_client) -> None:
        """
        Given: Neo4jClient connected but verify fails
        When: health_check() is called
        Then: Returns error status
        """
        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock(
            side_effect=Exception("Network error")
        )
        neo4j_client._driver = mock_driver

        result = await neo4j_client.health_check()

        assert result["status"] == "error"
        assert result["healthy"] is False
        assert "Network error" in result["error"]

    @pytest.mark.asyncio
    async def test_session_context_manager(self, neo4j_client) -> None:
        """
        Given: Neo4jClient connected
        When: session() context manager is used
        Then: Session is properly created and closed
        """
        mock_session = AsyncMock()
        mock_driver = MagicMock()
        mock_driver.session.return_value = mock_session
        neo4j_client._driver = mock_driver

        async with neo4j_client.session() as session:
            assert session is mock_session

        mock_session.close.assert_awaited_once()


class TestNeo4jSingleton:
    """Tests for Neo4j singleton pattern."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        import walltrack.data.neo4j.client as client_module

        client_module._neo4j_client = None

    @pytest.mark.asyncio
    async def test_get_neo4j_client_creates_singleton(self) -> None:
        """
        Given: No existing client
        When: get_neo4j_client() is called
        Then: Creates and connects new client
        """
        mock_settings = MagicMock()
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password.get_secret_value.return_value = "pass"

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()

        with (
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
        ):
            from walltrack.data.neo4j.client import get_neo4j_client

            client = await get_neo4j_client()

            assert client is not None
            assert client._driver is mock_driver

    @pytest.mark.asyncio
    async def test_get_neo4j_client_returns_same_instance(self) -> None:
        """
        Given: Client already created
        When: get_neo4j_client() is called again
        Then: Returns same instance
        """
        mock_settings = MagicMock()
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password.get_secret_value.return_value = "pass"

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()

        with (
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
        ):
            from walltrack.data.neo4j.client import get_neo4j_client

            client1 = await get_neo4j_client()
            client2 = await get_neo4j_client()

            assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_neo4j_client_clears_singleton(self) -> None:
        """
        Given: Client exists
        When: close_neo4j_client() is called
        Then: Singleton is cleared
        """
        mock_settings = MagicMock()
        mock_settings.neo4j_uri = "bolt://localhost:7687"
        mock_settings.neo4j_user = "neo4j"
        mock_settings.neo4j_password.get_secret_value.return_value = "pass"

        mock_driver = AsyncMock()
        mock_driver.verify_connectivity = AsyncMock()

        with (
            patch(
                "walltrack.data.neo4j.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.neo4j.client.AsyncGraphDatabase.driver",
                return_value=mock_driver,
            ),
        ):
            from walltrack.data.neo4j.client import close_neo4j_client, get_neo4j_client

            await get_neo4j_client()
            await close_neo4j_client()

            import walltrack.data.neo4j.client as client_module

            assert client_module._neo4j_client is None
