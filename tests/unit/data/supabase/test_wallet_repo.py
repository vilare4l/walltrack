"""Unit tests for WalletRepository (Story 3.2 - Task 4).

Tests cover:
- Upserting wallet records
- Retrieving wallet by address
- Listing all wallets
- Getting wallet count
- Updating performance metrics (NEW in Story 3.2)
- Deleting wallet by address
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.wallet import PerformanceMetrics, Wallet
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


class TestWalletRepository:
    """Tests for WalletRepository class."""

    @pytest.fixture
    def valid_wallet_address(self) -> str:
        """Sample valid Solana wallet address."""
        return "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    @pytest.fixture
    def valid_token_address(self) -> str:
        """Sample valid token mint address."""
        return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create a mock SupabaseClient."""
        mock_client = MagicMock()
        mock_client.client = MagicMock()  # The actual Supabase client
        return mock_client

    @pytest.fixture
    def sample_wallet_data(self, valid_wallet_address, valid_token_address) -> dict:
        """Sample wallet data as returned by Supabase."""
        now = datetime.now(UTC).isoformat()
        return {
            "wallet_address": valid_wallet_address,
            "discovery_date": now,
            "token_source": valid_token_address,
            "score": 0.0,
            "win_rate": 0.0,
            "pnl_total": 0.0,
            "entry_delay_seconds": 0,
            "total_trades": 0,
            "metrics_last_updated": None,
            "metrics_confidence": "unknown",
            "decay_status": "ok",
            "is_blacklisted": False,
            "created_at": now,
            "updated_at": now,
        }

    @pytest.mark.asyncio
    async def test_upsert_wallet_success(
        self, mock_supabase_client, valid_wallet_address, valid_token_address, sample_wallet_data
    ):
        """Should upsert a wallet record successfully."""
        # Arrange
        wallet = Wallet(
            wallet_address=valid_wallet_address,
            discovery_date=datetime.now(UTC),
            token_source=valid_token_address,
            score=0.0,
            win_rate=0.0,
            pnl_total=0.0,
            entry_delay_seconds=0,
            total_trades=0,
            metrics_last_updated=None,
            metrics_confidence="unknown",
            decay_status="ok",
            is_blacklisted=False,
        )

        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_wallet_data]))
        mock_supabase_client.client.table.return_value.upsert.return_value.execute = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.upsert_wallet(wallet)

        # Assert
        assert isinstance(result, Wallet)
        assert result.wallet_address == valid_wallet_address
        assert result.token_source == valid_token_address
        assert result.decay_status == "ok"

    @pytest.mark.asyncio
    async def test_get_by_address_success(
        self, mock_supabase_client, valid_wallet_address, sample_wallet_data
    ):
        """Should retrieve wallet by address."""
        # Arrange
        mock_execute = AsyncMock(return_value=MagicMock(data=sample_wallet_data))
        (
            mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.get_by_address(valid_wallet_address)

        # Assert
        assert isinstance(result, Wallet)
        assert result.wallet_address == valid_wallet_address

    @pytest.mark.asyncio
    async def test_get_by_address_not_found(self, mock_supabase_client):
        """Should return None when wallet does not exist."""
        # Arrange
        mock_execute = AsyncMock(return_value=MagicMock(data=None))
        (
            mock_supabase_client.client.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.get_by_address("NonExistentAddress")

        # Assert
        assert result is None

    @pytest.mark.asyncio
    async def test_get_all_success(self, mock_supabase_client, sample_wallet_data):
        """Should list all wallets ordered by score."""
        # Arrange
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_wallet_data]))
        (
            mock_supabase_client.client.table.return_value.select.return_value.order.return_value.limit.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.get_all(limit=100)

        # Assert
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], Wallet)

    @pytest.mark.asyncio
    async def test_get_count_success(self, mock_supabase_client):
        """Should return total count of wallets."""
        # Arrange
        mock_execute = AsyncMock(return_value=MagicMock(count=42))
        (
            mock_supabase_client.client.table.return_value.select.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.get_count()

        # Assert
        assert result == 42

    @pytest.mark.asyncio
    async def test_update_performance_metrics_success(
        self, mock_supabase_client, valid_wallet_address
    ):
        """Should update wallet performance metrics successfully."""
        # Arrange
        metrics = PerformanceMetrics(
            win_rate=75.5,
            pnl_total=2.5,
            entry_delay_seconds=3600,
            total_trades=10,
            confidence="medium",
        )

        mock_execute = AsyncMock(return_value=MagicMock(data=[{"wallet_address": valid_wallet_address}]))
        (
            mock_supabase_client.client.table.return_value.update.return_value.eq.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.update_performance_metrics(valid_wallet_address, metrics)

        # Assert
        assert result is True

        # Verify update was called with correct data
        update_call = mock_supabase_client.client.table.return_value.update.call_args
        update_data = update_call[0][0]

        assert update_data["win_rate"] == 75.5
        assert update_data["pnl_total"] == 2.5
        assert update_data["entry_delay_seconds"] == 3600
        assert update_data["total_trades"] == 10
        assert update_data["metrics_confidence"] == "medium"
        assert "metrics_last_updated" in update_data
        assert "updated_at" in update_data

    @pytest.mark.asyncio
    async def test_update_performance_metrics_failure(
        self, mock_supabase_client, valid_wallet_address
    ):
        """Should return False when performance metrics update fails."""
        # Arrange
        metrics = PerformanceMetrics(
            win_rate=75.5,
            pnl_total=2.5,
            entry_delay_seconds=3600,
            total_trades=10,
            confidence="medium",
        )

        # Mock an exception during update
        mock_supabase_client.client.table.return_value.update.side_effect = Exception(
            "Database error"
        )

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.update_performance_metrics(valid_wallet_address, metrics)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_by_address_success(self, mock_supabase_client, valid_wallet_address):
        """Should delete wallet by address."""
        # Arrange
        mock_execute = AsyncMock(return_value=MagicMock(data=[]))
        (
            mock_supabase_client.client.table.return_value.delete.return_value.eq.return_value.execute
        ) = mock_execute

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.delete_by_address(valid_wallet_address)

        # Assert
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_by_address_failure(self, mock_supabase_client):
        """Should return False when delete fails."""
        # Arrange
        mock_supabase_client.client.table.return_value.delete.side_effect = Exception(
            "Delete failed"
        )

        repo = WalletRepository(mock_supabase_client)

        # Act
        result = await repo.delete_by_address("SomeAddress")

        # Assert
        assert result is False
