"""Tests for Supabase client."""

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from supabase.lib.client_options import AsyncClientOptions

if TYPE_CHECKING:
    from walltrack.data.supabase.client import SupabaseClient


class TestSupabaseClient:
    """Tests for SupabaseClient class."""

    @pytest.fixture
    def mock_settings(self) -> MagicMock:
        """Create mock settings."""
        settings = MagicMock()
        settings.supabase_url = "https://test.supabase.co"
        settings.supabase_key.get_secret_value.return_value = "test-api-key"
        settings.postgres_schema = "walltrack"
        return settings

    @pytest.fixture
    def supabase_client(self, mock_settings: MagicMock) -> "SupabaseClient":
        """Create SupabaseClient with mocked settings."""
        with patch(
            "walltrack.data.supabase.client.get_settings", return_value=mock_settings
        ):
            from walltrack.data.supabase.client import SupabaseClient

            return SupabaseClient()

    def test_init_sets_client_to_none(self, supabase_client) -> None:
        """
        Given: New SupabaseClient
        When: Initialized
        Then: Internal client is None
        """
        assert supabase_client._client is None

    @pytest.mark.asyncio
    async def test_connect_creates_client(
        self, supabase_client, mock_settings: MagicMock
    ) -> None:
        """
        Given: SupabaseClient not connected
        When: connect() is called
        Then: Async client is created with correct credentials and AsyncClientOptions
        """
        mock_async_client = AsyncMock()

        with patch(
            "walltrack.data.supabase.client.create_async_client",
            new_callable=AsyncMock,
            return_value=mock_async_client,
        ) as mock_create:
            await supabase_client.connect()

            # Verify called with correct arguments
            mock_create.assert_called_once()
            call_args = mock_create.call_args
            assert call_args[0][0] == mock_settings.supabase_url
            assert call_args[0][1] == mock_settings.supabase_key.get_secret_value()
            # Verify options is AsyncClientOptions with correct schema
            options = call_args[1]["options"]
            assert isinstance(options, AsyncClientOptions)
            assert options.schema == mock_settings.postgres_schema
            assert supabase_client._client is mock_async_client

    @pytest.mark.asyncio
    async def test_connect_idempotent(self, supabase_client) -> None:
        """
        Given: SupabaseClient already connected
        When: connect() is called again
        Then: Connection is not re-established
        """
        supabase_client._client = MagicMock()

        with patch(
            "walltrack.data.supabase.client.create_async_client",
            new_callable=AsyncMock,
        ) as mock_create:
            await supabase_client.connect()

            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_raises_database_connection_error_on_failure(
        self, supabase_client
    ) -> None:
        """
        Given: Supabase connection fails
        When: connect() is called
        Then: DatabaseConnectionError is raised
        """
        from walltrack.core.exceptions import DatabaseConnectionError

        with patch(
            "walltrack.data.supabase.client.create_async_client",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ), pytest.raises(DatabaseConnectionError, match="Supabase"):
            await supabase_client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_clears_client(self, supabase_client) -> None:
        """
        Given: SupabaseClient connected
        When: disconnect() is called
        Then: Client is set to None
        """
        supabase_client._client = MagicMock()

        await supabase_client.disconnect()

        assert supabase_client._client is None

    @pytest.mark.asyncio
    async def test_health_check_returns_disconnected_when_not_connected(
        self, supabase_client
    ) -> None:
        """
        Given: SupabaseClient not connected
        When: health_check() is called
        Then: Returns disconnected status
        """
        result = await supabase_client.health_check()

        assert result["status"] == "disconnected"
        assert result["healthy"] is False

    @pytest.mark.asyncio
    async def test_health_check_returns_connected_when_connected(
        self, supabase_client
    ) -> None:
        """
        Given: SupabaseClient connected
        When: health_check() is called
        Then: Returns connected status
        """
        mock_client = MagicMock()
        mock_client.auth.get_session = AsyncMock(return_value=None)
        supabase_client._client = mock_client

        result = await supabase_client.health_check()

        assert result["status"] == "connected"
        assert result["healthy"] is True
        mock_client.auth.get_session.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_health_check_returns_error_on_failure(
        self, supabase_client
    ) -> None:
        """
        Given: SupabaseClient connected but auth fails
        When: health_check() is called
        Then: Returns error status
        """
        mock_client = MagicMock()
        mock_client.auth.get_session = AsyncMock(
            side_effect=Exception("Auth service unavailable")
        )
        supabase_client._client = mock_client

        result = await supabase_client.health_check()

        assert result["status"] == "error"
        assert result["healthy"] is False
        assert "Auth service unavailable" in result["error"]


class TestSupabaseSingleton:
    """Tests for Supabase singleton pattern."""

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton before each test."""
        import walltrack.data.supabase.client as client_module

        client_module._supabase_client = None

    @pytest.mark.asyncio
    async def test_get_supabase_client_creates_singleton(self) -> None:
        """
        Given: No existing client
        When: get_supabase_client() is called
        Then: Creates and connects new client
        """
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key.get_secret_value.return_value = "key"
        mock_settings.postgres_schema = "walltrack"

        with (
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.create_async_client",
                new_callable=AsyncMock,
            ),
        ):
            from walltrack.data.supabase.client import get_supabase_client

            client = await get_supabase_client()

            assert client is not None
            assert client._client is not None

    @pytest.mark.asyncio
    async def test_get_supabase_client_returns_same_instance(self) -> None:
        """
        Given: Client already created
        When: get_supabase_client() is called again
        Then: Returns same instance
        """
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key.get_secret_value.return_value = "key"
        mock_settings.postgres_schema = "walltrack"

        with (
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.create_async_client",
                new_callable=AsyncMock,
            ),
        ):
            from walltrack.data.supabase.client import get_supabase_client

            client1 = await get_supabase_client()
            client2 = await get_supabase_client()

            assert client1 is client2

    @pytest.mark.asyncio
    async def test_close_supabase_client_clears_singleton(self) -> None:
        """
        Given: Client exists
        When: close_supabase_client() is called
        Then: Singleton is cleared
        """
        mock_settings = MagicMock()
        mock_settings.supabase_url = "https://test.supabase.co"
        mock_settings.supabase_key.get_secret_value.return_value = "key"
        mock_settings.postgres_schema = "walltrack"

        with (
            patch(
                "walltrack.data.supabase.client.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "walltrack.data.supabase.client.create_async_client",
                new_callable=AsyncMock,
            ),
        ):
            from walltrack.data.supabase.client import (
                close_supabase_client,
                get_supabase_client,
            )

            await get_supabase_client()
            await close_supabase_client()

            import walltrack.data.supabase.client as client_module

            assert client_module._supabase_client is None
