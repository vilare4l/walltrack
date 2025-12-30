"""Integration tests for WalletRepository.

Tests wallet repository operations against real Supabase database.
Requires database connection and valid Supabase credentials.
"""

from datetime import UTC, datetime

import pytest

from walltrack.data.models.wallet import PerformanceMetrics, Wallet
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


@pytest.fixture
async def supabase_client():
    """Create connected Supabase client."""
    client = await get_supabase_client()
    yield client
    await client.close()


@pytest.fixture
async def wallet_repo(supabase_client):
    """Create WalletRepository instance."""
    return WalletRepository(supabase_client)


@pytest.fixture
def sample_wallet():
    """Create sample wallet for testing."""
    return Wallet(
        wallet_address="TestWallet1111111111111111111111111",
        discovery_count=1,
        discovery_tokens=["TokenMint1111111111111111111111111111"],
        discovered_at=datetime.now(UTC),
        score=None,
        win_rate=None,
        pnl_total=None,
        entry_delay_seconds=None,
        total_trades=0,
        metrics_last_updated=None,
        metrics_confidence="unknown",
        status="pending",
    )


@pytest.fixture
def sample_metrics():
    """Create sample performance metrics for testing."""
    return PerformanceMetrics(
        win_rate=75.0,
        pnl_total=2.5,
        entry_delay_seconds=3600,
        total_trades=10,
        confidence="medium",
    )


@pytest.mark.asyncio
class TestWalletRepositoryUpsert:
    """Tests for wallet upsert operations."""

    async def test_upsert_new_wallet(self, wallet_repo, sample_wallet):
        """Test upserting a new wallet creates it in database."""
        # Clean up test wallet if exists
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)

        # Act
        result = await wallet_repo.upsert_wallet(sample_wallet)

        # Assert
        assert result.wallet_address == sample_wallet.wallet_address
        assert result.discovery_count == 1
        assert result.discovery_tokens == sample_wallet.discovery_tokens
        assert result.status == "pending"

        # Clean up
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)

    async def test_upsert_existing_wallet_updates_fields(
        self, wallet_repo, sample_wallet
    ):
        """Test upserting existing wallet updates its fields."""
        # Arrange - Create wallet first
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)
        await wallet_repo.upsert_wallet(sample_wallet)

        # Modify wallet data
        sample_wallet.discovery_count = 2
        sample_wallet.discovery_tokens.append("TokenMint2222222222222222222222222222")
        sample_wallet.score = 0.85

        # Act - Upsert again
        result = await wallet_repo.upsert_wallet(sample_wallet)

        # Assert
        assert result.wallet_address == sample_wallet.wallet_address
        assert result.discovery_count == 2
        assert len(result.discovery_tokens) == 2
        assert result.score == 0.85

        # Clean up
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)


@pytest.mark.asyncio
class TestWalletRepositoryGet:
    """Tests for wallet retrieval operations."""

    async def test_get_by_address_existing_wallet(
        self, wallet_repo, sample_wallet
    ):
        """Test getting wallet by address returns wallet."""
        # Arrange
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)
        await wallet_repo.upsert_wallet(sample_wallet)

        # Act
        result = await wallet_repo.get_by_address(sample_wallet.wallet_address)

        # Assert
        assert result is not None
        assert result.wallet_address == sample_wallet.wallet_address
        assert result.discovery_count == sample_wallet.discovery_count

        # Clean up
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)

    async def test_get_by_address_nonexistent_wallet(self, wallet_repo):
        """Test getting nonexistent wallet returns None."""
        # Act
        result = await wallet_repo.get_by_address("NonexistentWallet111111111111111111")

        # Assert
        assert result is None

    async def test_get_all_returns_wallets_ordered_by_score(
        self, wallet_repo
    ):
        """Test get_all returns wallets ordered by score descending."""
        # Arrange - Create test wallets with different scores
        wallet1 = Wallet(
            wallet_address="TestWallet1111111111111111111111111",
            discovery_count=1,
            discovery_tokens=["TokenMint1111111111111111111111111111"],
            discovered_at=datetime.now(UTC),
            score=0.5,
            status="pending",
        )
        wallet2 = Wallet(
            wallet_address="TestWallet2222222222222222222222222",
            discovery_count=1,
            discovery_tokens=["TokenMint2222222222222222222222222222"],
            discovered_at=datetime.now(UTC),
            score=0.8,
            status="pending",
        )

        # Clean up and create
        await wallet_repo.delete_by_address(wallet1.wallet_address)
        await wallet_repo.delete_by_address(wallet2.wallet_address)
        await wallet_repo.upsert_wallet(wallet1)
        await wallet_repo.upsert_wallet(wallet2)

        # Act
        results = await wallet_repo.get_all(limit=10)

        # Assert - Find our test wallets
        test_wallets = [
            w
            for w in results
            if w.wallet_address
            in [wallet1.wallet_address, wallet2.wallet_address]
        ]
        assert len(test_wallets) >= 2
        # Wallet2 (score 0.8) should come before Wallet1 (score 0.5)
        wallet2_idx = next(
            i for i, w in enumerate(test_wallets) if w.wallet_address == wallet2.wallet_address
        )
        wallet1_idx = next(
            i for i, w in enumerate(test_wallets) if w.wallet_address == wallet1.wallet_address
        )
        assert wallet2_idx < wallet1_idx

        # Clean up
        await wallet_repo.delete_by_address(wallet1.wallet_address)
        await wallet_repo.delete_by_address(wallet2.wallet_address)


@pytest.mark.asyncio
class TestWalletRepositoryPerformanceMetrics:
    """Tests for performance metrics update operations."""

    async def test_update_performance_metrics_success(
        self, wallet_repo, sample_wallet, sample_metrics
    ):
        """Test updating performance metrics for existing wallet."""
        # Arrange - Create wallet first
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)
        await wallet_repo.upsert_wallet(sample_wallet)

        # Act
        success = await wallet_repo.update_performance_metrics(
            sample_wallet.wallet_address, sample_metrics
        )

        # Assert
        assert success is True

        # Verify metrics were updated
        updated_wallet = await wallet_repo.get_by_address(
            sample_wallet.wallet_address
        )
        assert updated_wallet is not None
        assert updated_wallet.win_rate == 75.0
        assert updated_wallet.pnl_total == 2.5
        assert updated_wallet.entry_delay_seconds == 3600
        assert updated_wallet.total_trades == 10
        assert updated_wallet.metrics_confidence == "medium"
        assert updated_wallet.metrics_last_updated is not None

        # Clean up
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)

    async def test_update_performance_metrics_nonexistent_wallet(
        self, wallet_repo, sample_metrics
    ):
        """Test updating metrics for nonexistent wallet fails gracefully."""
        # Act - Try to update nonexistent wallet (Supabase won't error, just no rows affected)
        success = await wallet_repo.update_performance_metrics(
            "NonexistentWallet111111111111111111", sample_metrics
        )

        # Assert - Should return True (no DB error), but wallet still doesn't exist
        # This is by design - Supabase update on non-existent row doesn't error
        result = await wallet_repo.get_by_address(
            "NonexistentWallet111111111111111111"
        )
        assert result is None

    async def test_update_performance_metrics_with_zero_values(
        self, wallet_repo, sample_wallet
    ):
        """Test updating metrics with zero values (all losses scenario)."""
        # Arrange
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)
        await wallet_repo.upsert_wallet(sample_wallet)

        zero_metrics = PerformanceMetrics(
            win_rate=0.0,
            pnl_total=-1.5,
            entry_delay_seconds=0,
            total_trades=5,
            confidence="low",
        )

        # Act
        success = await wallet_repo.update_performance_metrics(
            sample_wallet.wallet_address, zero_metrics
        )

        # Assert
        assert success is True
        updated_wallet = await wallet_repo.get_by_address(
            sample_wallet.wallet_address
        )
        assert updated_wallet is not None
        assert updated_wallet.win_rate == 0.0
        assert updated_wallet.pnl_total == -1.5
        assert updated_wallet.total_trades == 5
        assert updated_wallet.metrics_confidence == "low"

        # Clean up
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)


@pytest.mark.asyncio
class TestWalletRepositoryDelete:
    """Tests for wallet deletion operations."""

    async def test_delete_by_address_existing_wallet(
        self, wallet_repo, sample_wallet
    ):
        """Test deleting existing wallet."""
        # Arrange
        await wallet_repo.delete_by_address(sample_wallet.wallet_address)
        await wallet_repo.upsert_wallet(sample_wallet)

        # Act
        success = await wallet_repo.delete_by_address(sample_wallet.wallet_address)

        # Assert
        assert success is True
        result = await wallet_repo.get_by_address(sample_wallet.wallet_address)
        assert result is None

    async def test_delete_by_address_nonexistent_wallet(self, wallet_repo):
        """Test deleting nonexistent wallet returns True (no error)."""
        # Act
        success = await wallet_repo.delete_by_address(
            "NonexistentWallet111111111111111111"
        )

        # Assert - Supabase delete on nonexistent row doesn't error
        assert success is True
