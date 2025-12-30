"""Unit tests for Neo4j wallet queries (Story 3.1 - Task 4.4).

Tests cover:
- Wallet node creation (MERGE idempotent)
- Wallet node retrieval
- Wallet node deletion
- Duplicate prevention (MERGE behavior)

Note: Uses mocks to avoid Neo4j container dependency in unit tests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestWalletQueries:
    """Tests for Neo4j wallet query functions."""

    @pytest.fixture
    def valid_wallet_address(self) -> str:
        """Sample valid Solana wallet address."""
        return "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    @pytest.mark.asyncio
    async def test_create_wallet_node_success(self, valid_wallet_address):
        """Should create a new wallet node in Neo4j."""
        from walltrack.data.neo4j.queries.wallet import create_wallet_node

        # Mock Neo4j client
        mock_client = AsyncMock()
        mock_client.execute_query.return_value = [
            {
                "wallet_address": valid_wallet_address,
                "created_at": "2025-12-30T12:00:00Z",
                "was_created": True,
            }
        ]

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await create_wallet_node(valid_wallet_address)

            assert result["wallet_address"] == valid_wallet_address
            assert result["was_created"] is True
            assert "created_at" in result

            # Verify MERGE query was called
            mock_client.execute_query.assert_called_once()
            call_args = mock_client.execute_query.call_args
            assert "MERGE (w:Wallet" in call_args[0][0]
            assert call_args[1]["parameters"]["wallet_address"] == valid_wallet_address

    @pytest.mark.asyncio
    async def test_create_wallet_node_idempotent(self, valid_wallet_address):
        """Should return existing node without creating duplicate (MERGE idempotent)."""
        from walltrack.data.neo4j.queries.wallet import create_wallet_node

        # Mock existing node (was_created=False indicates MERGE found existing)
        mock_client = AsyncMock()
        mock_client.execute_query.return_value = [
            {
                "wallet_address": valid_wallet_address,
                "created_at": "2025-12-30T10:00:00Z",
                "was_created": False,  # Already existed
            }
        ]

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await create_wallet_node(valid_wallet_address)

            assert result["wallet_address"] == valid_wallet_address
            assert result["was_created"] is False  # Node already existed

    @pytest.mark.asyncio
    async def test_get_wallet_node_success(self, valid_wallet_address):
        """Should retrieve wallet node by address."""
        from walltrack.data.neo4j.queries.wallet import get_wallet_node

        mock_client = AsyncMock()
        mock_client.execute_query.return_value = [
            {
                "wallet_address": valid_wallet_address,
                "created_at": "2025-12-30T12:00:00Z",
            }
        ]

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await get_wallet_node(valid_wallet_address)

            assert result is not None
            assert result["wallet_address"] == valid_wallet_address
            assert "created_at" in result

            # Verify MATCH query was called
            mock_client.execute_query.assert_called_once()
            call_args = mock_client.execute_query.call_args
            assert "MATCH (w:Wallet" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_get_wallet_node_not_found(self):
        """Should return None when wallet node does not exist."""
        from walltrack.data.neo4j.queries.wallet import get_wallet_node

        mock_client = AsyncMock()
        mock_client.execute_query.return_value = []  # No results

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await get_wallet_node("NonExistentAddress123")

            assert result is None

    @pytest.mark.asyncio
    async def test_delete_wallet_node_success(self, valid_wallet_address):
        """Should delete wallet node and return True."""
        from walltrack.data.neo4j.queries.wallet import delete_wallet_node

        mock_client = AsyncMock()
        mock_client.execute_query.return_value = [
            {"deleted_count": 1}  # Node was deleted
        ]

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await delete_wallet_node(valid_wallet_address)

            assert result is True

            # Verify DETACH DELETE query was called
            mock_client.execute_query.assert_called_once()
            call_args = mock_client.execute_query.call_args
            assert "DETACH DELETE" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_delete_wallet_node_not_found(self):
        """Should return False when wallet node does not exist."""
        from walltrack.data.neo4j.queries.wallet import delete_wallet_node

        mock_client = AsyncMock()
        mock_client.execute_query.return_value = [
            {"deleted_count": 0}  # No node deleted
        ]

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            result = await delete_wallet_node("NonExistentAddress123")

            assert result is False

    @pytest.mark.asyncio
    async def test_create_wallet_node_error_handling(self, valid_wallet_address):
        """Should raise exception when Neo4j query fails."""
        from walltrack.data.neo4j.queries.wallet import create_wallet_node

        mock_client = AsyncMock()
        mock_client.execute_query.side_effect = Exception("Neo4j connection lost")

        with patch(
            "walltrack.data.neo4j.queries.wallet.get_neo4j_client",
            return_value=mock_client,
        ):
            with pytest.raises(Exception) as exc_info:
                await create_wallet_node(valid_wallet_address)

            assert "Neo4j connection lost" in str(exc_info.value)
