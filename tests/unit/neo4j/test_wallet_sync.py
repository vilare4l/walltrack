"""Unit tests for wallet sync service (Story 3.1 - Task 4.3).

Tests cover:
- Single wallet sync to Neo4j
- Batch wallet sync
- Error handling when Neo4j fails
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestWalletSync:
    """Tests for wallet sync service."""

    @pytest.fixture
    def valid_wallet_address(self) -> str:
        """Sample valid Solana wallet address."""
        return "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    @pytest.mark.asyncio
    async def test_sync_wallet_to_neo4j_success(self, valid_wallet_address):
        """Should sync wallet to Neo4j successfully."""
        from walltrack.data.neo4j.services.wallet_sync import sync_wallet_to_neo4j

        # Mock create_wallet_node to return success
        with patch(
            "walltrack.data.neo4j.services.wallet_sync.create_wallet_node",
            return_value={
                "wallet_address": valid_wallet_address,
                "was_created": True,
            },
        ) as mock_create:
            result = await sync_wallet_to_neo4j(valid_wallet_address)

            assert result is True
            mock_create.assert_called_once_with(valid_wallet_address)

    @pytest.mark.asyncio
    async def test_sync_wallet_to_neo4j_idempotent(self, valid_wallet_address):
        """Should handle existing wallet (idempotent)."""
        from walltrack.data.neo4j.services.wallet_sync import sync_wallet_to_neo4j

        # Mock create_wallet_node returning existing node
        with patch(
            "walltrack.data.neo4j.services.wallet_sync.create_wallet_node",
            return_value={
                "wallet_address": valid_wallet_address,
                "was_created": False,  # Already existed
            },
        ):
            result = await sync_wallet_to_neo4j(valid_wallet_address)

            assert result is True  # Still success even if already exists

    @pytest.mark.asyncio
    async def test_sync_wallet_to_neo4j_failure(self, valid_wallet_address):
        """Should return False when sync fails."""
        from walltrack.data.neo4j.services.wallet_sync import sync_wallet_to_neo4j

        # Mock create_wallet_node to raise exception
        with patch(
            "walltrack.data.neo4j.services.wallet_sync.create_wallet_node",
            side_effect=Exception("Neo4j connection lost"),
        ):
            result = await sync_wallet_to_neo4j(valid_wallet_address)

            # Should return False instead of raising (graceful failure)
            assert result is False

    @pytest.mark.asyncio
    async def test_sync_batch_wallets_success(self):
        """Should sync multiple wallets in batch."""
        from walltrack.data.neo4j.services.wallet_sync import sync_batch_wallets_to_neo4j

        wallet_addresses = [
            "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            "8xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            "7xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ]

        # Mock sync_wallet_to_neo4j to return True
        with patch(
            "walltrack.data.neo4j.services.wallet_sync.sync_wallet_to_neo4j",
            return_value=True,
        ) as mock_sync:
            result = await sync_batch_wallets_to_neo4j(wallet_addresses)

            assert result["total"] == 3
            assert result["success"] == 3
            assert result["failed"] == 0
            assert mock_sync.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_batch_wallets_partial_failure(self):
        """Should handle partial failures in batch sync."""
        from walltrack.data.neo4j.services.wallet_sync import sync_batch_wallets_to_neo4j

        wallet_addresses = [
            "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            "8xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            "7xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ]

        # Mock sync_wallet_to_neo4j to alternate success/failure
        async def mock_sync_side_effect(addr):
            # First and third succeed, second fails
            return addr[0] in ["9", "7"]

        with patch(
            "walltrack.data.neo4j.services.wallet_sync.sync_wallet_to_neo4j",
            side_effect=mock_sync_side_effect,
        ):
            result = await sync_batch_wallets_to_neo4j(wallet_addresses)

            assert result["total"] == 3
            assert result["success"] == 2
            assert result["failed"] == 1
