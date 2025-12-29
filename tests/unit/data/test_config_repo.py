"""Unit tests for Config Repository.

Tests cover:
- Getting trading wallet address
- Setting trading wallet address
- Clearing trading wallet address
- Error handling for database operations
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestConfigRepository:
    """Tests for ConfigRepository class."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_trading_wallet_returns_address_when_exists(
        self, mock_supabase_client
    ):
        """Should return wallet address when it exists in config."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        # Setup mock
        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={"key": "trading_wallet_address", "value": "9WzDX..."}
            )
        )

        repo = ConfigRepository(mock_supabase_client)
        result = await repo.get_trading_wallet()

        assert result == "9WzDX..."

    @pytest.mark.asyncio
    async def test_get_trading_wallet_returns_none_when_not_exists(
        self, mock_supabase_client
    ):
        """Should return None when wallet address not in config."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        repo = ConfigRepository(mock_supabase_client)
        result = await repo.get_trading_wallet()

        assert result is None

    @pytest.mark.asyncio
    async def test_set_trading_wallet_creates_or_updates(self, mock_supabase_client):
        """Should upsert wallet address in config."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.upsert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"key": "trading_wallet_address"}])
        )

        repo = ConfigRepository(mock_supabase_client)
        await repo.set_trading_wallet("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")

        mock_supabase_client.client.table.assert_called_with("config")

    @pytest.mark.asyncio
    async def test_clear_trading_wallet_removes_address(self, mock_supabase_client):
        """Should remove wallet address from config."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        repo = ConfigRepository(mock_supabase_client)
        await repo.clear_trading_wallet()

        mock_supabase_client.client.table.assert_called_with("config")


class TestConfigRepositoryGetValue:
    """Tests for generic get_value method."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_value_returns_value_when_exists(self, mock_supabase_client):
        """Should return value for existing key."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={"key": "test_key", "value": "test_value"})
        )

        repo = ConfigRepository(mock_supabase_client)
        result = await repo.get_value("test_key")

        assert result == "test_value"

    @pytest.mark.asyncio
    async def test_set_value_upserts_value(self, mock_supabase_client):
        """Should upsert value for key."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.upsert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"key": "test_key"}])
        )

        repo = ConfigRepository(mock_supabase_client)
        await repo.set_value("test_key", "test_value")

        mock_supabase_client.client.table.assert_called_with("config")

    @pytest.mark.asyncio
    async def test_delete_value_removes_key(self, mock_supabase_client):
        """Should delete key from config."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.delete.return_value.eq.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        repo = ConfigRepository(mock_supabase_client)
        await repo.delete_value("test_key")

        mock_supabase_client.client.table.assert_called_with("config")


class TestConfigRepositoryErrorHandling:
    """Tests for error handling in ConfigRepository."""

    @pytest.fixture
    def mock_supabase_client(self):
        """Create mock Supabase client."""
        client = MagicMock()
        client.client = MagicMock()
        return client

    @pytest.mark.asyncio
    async def test_get_value_returns_none_on_exception(self, mock_supabase_client):
        """Should return None when database query fails."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        repo = ConfigRepository(mock_supabase_client)
        result = await repo.get_value("test_key")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_trading_wallet_handles_exception(self, mock_supabase_client):
        """Should return None when getting wallet fails."""
        from walltrack.data.supabase.repositories.config_repo import ConfigRepository

        mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            side_effect=Exception("Network error")
        )

        repo = ConfigRepository(mock_supabase_client)
        result = await repo.get_trading_wallet()

        assert result is None
