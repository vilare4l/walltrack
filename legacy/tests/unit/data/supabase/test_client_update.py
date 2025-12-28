"""Tests for SupabaseClient update method."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.data.supabase.client import SupabaseClient


class TestSupabaseClientUpdate:
    """Tests for SupabaseClient update method."""

    @pytest.fixture
    def mock_table_chain(self) -> MagicMock:
        """Create mock for table method chain."""
        mock_response = MagicMock()
        mock_response.data = [{"id": "123", "status": "closed"}]

        # Chain: table().update().eq().execute()
        mock_eq = MagicMock()
        mock_eq.execute = AsyncMock(return_value=mock_response)

        mock_update = MagicMock()
        mock_update.eq.return_value = mock_eq

        mock_table = MagicMock()
        mock_table.update.return_value = mock_update

        return mock_table

    async def test_update_method_exists(self) -> None:
        """Test that SupabaseClient has update method."""
        client = SupabaseClient()
        assert hasattr(client, "update")
        assert callable(client.update)

    async def test_update_calls_table_update(
        self,
        mock_table_chain: MagicMock,
    ) -> None:
        """Test that update method calls table update correctly."""
        client = SupabaseClient()
        client._client = MagicMock()  # Prevent connection error

        with patch.object(client, "table", return_value=mock_table_chain) as mock_table:
            await client.update(
                "positions",
                {"id": "123"},
                {"status": "closed", "exit_price": 0.002},
            )

            mock_table.assert_called_with("positions")

    async def test_update_applies_filters(
        self,
        mock_table_chain: MagicMock,
    ) -> None:
        """Test that update applies filter conditions."""
        client = SupabaseClient()
        client._client = MagicMock()

        with patch.object(client, "table", return_value=mock_table_chain):
            await client.update(
                "positions",
                {"id": "123"},
                {"status": "closed"},
            )

            # Verify eq was called for the filter
            mock_table_chain.update.return_value.eq.assert_called_with("id", "123")

    async def test_update_returns_updated_data(
        self,
        mock_table_chain: MagicMock,
    ) -> None:
        """Test that update returns the updated record."""
        client = SupabaseClient()
        client._client = MagicMock()

        with patch.object(client, "table", return_value=mock_table_chain):
            result = await client.update(
                "positions",
                {"id": "123"},
                {"status": "closed"},
            )

            assert result["id"] == "123"
            assert result["status"] == "closed"
