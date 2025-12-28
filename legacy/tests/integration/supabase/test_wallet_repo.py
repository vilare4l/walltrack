"""Integration tests for wallet repository.

These tests mock the Supabase client to test repository logic without
requiring a real database connection.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


def create_chainable_mock() -> MagicMock:
    """Create a chainable mock for Supabase query builder."""
    mock = MagicMock()
    # All builder methods return self for chaining
    mock.select.return_value = mock
    mock.insert.return_value = mock
    mock.update.return_value = mock
    mock.delete.return_value = mock
    mock.eq.return_value = mock
    mock.gte.return_value = mock
    mock.order.return_value = mock
    mock.range.return_value = mock
    mock.limit.return_value = mock
    mock.maybe_single.return_value = mock
    # execute() is async
    mock.execute = AsyncMock()
    return mock


@pytest.fixture
def mock_supabase_client() -> MagicMock:
    """Create mock Supabase client."""
    client = MagicMock()

    # table() returns a chainable query builder
    query_builder = create_chainable_mock()
    client.table.return_value = query_builder

    # Default execute response
    response = MagicMock()
    response.data = []
    response.count = 0
    query_builder.execute.return_value = response

    # Mock rpc for increment_wallet_discovery
    rpc_mock = MagicMock()
    rpc_mock.execute = AsyncMock(return_value=MagicMock())
    client.client = MagicMock()
    client.client.rpc.return_value = rpc_mock

    return client


@pytest.fixture
def wallet_repo(mock_supabase_client: MagicMock) -> WalletRepository:
    """Create wallet repository with mock client."""
    return WalletRepository(mock_supabase_client)


@pytest.fixture
def sample_wallet() -> Wallet:
    """Create a sample wallet for testing."""
    return Wallet(
        address="A" * 44,  # Valid Solana address length
        status=WalletStatus.ACTIVE,
        score=0.75,
        profile=WalletProfile(
            win_rate=0.65,
            total_pnl=500.0,
            total_trades=10,
        ),
        discovery_tokens=["B" * 44, "C" * 44],
    )


@pytest.fixture
def sample_db_row() -> dict:
    """Create a sample database row."""
    return {
        "address": "A" * 44,
        "status": "active",
        "score": 0.75,
        "win_rate": 0.65,
        "total_pnl": 500.0,
        "avg_pnl_per_trade": 50.0,
        "total_trades": 10,
        "timing_percentile": 0.5,
        "avg_hold_time_hours": 4.0,
        "preferred_hours": [9, 10, 11],
        "avg_position_size_sol": 0.5,
        "discovered_at": datetime.utcnow().isoformat(),
        "discovery_count": 2,
        "discovery_tokens": ["B" * 44, "C" * 44],
        "decay_detected_at": None,
        "consecutive_losses": 0,
        "rolling_win_rate": None,
        "blacklisted_at": None,
        "blacklist_reason": None,
        "last_profiled_at": None,
        "last_signal_at": None,
        "updated_at": datetime.utcnow().isoformat(),
    }


class TestWalletRepository:
    """Tests for WalletRepository."""

    @pytest.mark.asyncio
    async def test_get_by_address_found(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test getting wallet by address when found."""
        # Setup mock response
        response = MagicMock()
        response.data = sample_db_row
        mock_supabase_client.table.return_value.execute.return_value = response

        wallet = await wallet_repo.get_by_address("A" * 44)

        assert wallet is not None
        assert wallet.address == "A" * 44
        assert wallet.status == WalletStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_get_by_address_not_found(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test getting wallet by address when not found."""
        response = MagicMock()
        response.data = None
        mock_supabase_client.table.return_value.execute.return_value = response

        wallet = await wallet_repo.get_by_address("nonexistent")

        assert wallet is None

    @pytest.mark.asyncio
    async def test_exists_true(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test exists returns True when wallet found."""
        response = MagicMock()
        response.data = [{"address": "A" * 44}]
        mock_supabase_client.table.return_value.execute.return_value = response

        exists = await wallet_repo.exists("A" * 44)

        assert exists is True

    @pytest.mark.asyncio
    async def test_exists_false(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test exists returns False when wallet not found."""
        response = MagicMock()
        response.data = []
        mock_supabase_client.table.return_value.execute.return_value = response

        exists = await wallet_repo.exists("nonexistent")

        assert exists is False

    @pytest.mark.asyncio
    async def test_create_wallet(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_wallet: Wallet,
        sample_db_row: dict,
    ) -> None:
        """Test creating a new wallet."""
        response = MagicMock()
        response.data = [sample_db_row]
        mock_supabase_client.table.return_value.execute.return_value = response

        created = await wallet_repo.create(sample_wallet)

        assert created.address == sample_wallet.address
        mock_supabase_client.table.return_value.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_wallet(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_wallet: Wallet,
        sample_db_row: dict,
    ) -> None:
        """Test updating an existing wallet."""
        response = MagicMock()
        response.data = [sample_db_row]
        mock_supabase_client.table.return_value.execute.return_value = response

        updated = await wallet_repo.update(sample_wallet)

        assert updated.address == sample_wallet.address
        mock_supabase_client.table.return_value.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_upsert_new_wallet(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_wallet: Wallet,
        sample_db_row: dict,
    ) -> None:
        """Test upserting a new wallet."""
        # First call: exists check returns False
        exists_response = MagicMock()
        exists_response.data = []

        # Second call: create returns wallet
        create_response = MagicMock()
        create_response.data = [sample_db_row]

        mock_supabase_client.table.return_value.execute.side_effect = [
            exists_response,
            create_response,
        ]

        wallet, is_new = await wallet_repo.upsert(sample_wallet)

        assert is_new is True
        assert wallet.address == sample_wallet.address

    @pytest.mark.asyncio
    async def test_upsert_existing_wallet(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_wallet: Wallet,
        sample_db_row: dict,
    ) -> None:
        """Test upserting an existing wallet."""
        # First call: exists check returns True
        exists_response = MagicMock()
        exists_response.data = [{"address": "A" * 44}]

        # Second call: get returns wallet after increment
        get_response = MagicMock()
        get_response.data = sample_db_row

        mock_supabase_client.table.return_value.execute.side_effect = [
            exists_response,
            get_response,
        ]

        _, is_new = await wallet_repo.upsert(sample_wallet)

        assert is_new is False

    @pytest.mark.asyncio
    async def test_get_active_wallets(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test getting active wallets with minimum score."""
        response = MagicMock()
        response.data = [sample_db_row, sample_db_row]
        mock_supabase_client.table.return_value.execute.return_value = response

        wallets = await wallet_repo.get_active_wallets(min_score=0.5, limit=10)

        assert len(wallets) == 2
        mock_supabase_client.table.return_value.eq.assert_called()

    @pytest.mark.asyncio
    async def test_get_by_status(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
        sample_db_row: dict,
    ) -> None:
        """Test getting wallets by status."""
        response = MagicMock()
        response.data = [sample_db_row]
        mock_supabase_client.table.return_value.execute.return_value = response

        wallets = await wallet_repo.get_by_status(WalletStatus.ACTIVE, limit=50)

        assert len(wallets) == 1
        assert wallets[0].status == WalletStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_set_status_blacklisted(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test setting wallet status to blacklisted."""
        response = MagicMock()
        response.data = [{"address": "A" * 44}]
        mock_supabase_client.table.return_value.execute.return_value = response

        await wallet_repo.set_status(
            "A" * 44,
            WalletStatus.BLACKLISTED,
            reason="Detected as bot",
        )

        mock_supabase_client.table.return_value.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_wallet(
        self,
        wallet_repo: WalletRepository,
        mock_supabase_client: MagicMock,
    ) -> None:
        """Test deleting a wallet."""
        response = MagicMock()
        response.data = [{"address": "A" * 44}]
        mock_supabase_client.table.return_value.execute.return_value = response

        deleted = await wallet_repo.delete("A" * 44)

        assert deleted is True
        mock_supabase_client.table.return_value.delete.assert_called_once()

    def test_wallet_to_row_conversion(
        self,
        wallet_repo: WalletRepository,
        sample_wallet: Wallet,
    ) -> None:
        """Test converting Wallet model to database row."""
        row = wallet_repo._wallet_to_row(sample_wallet)

        assert row["address"] == sample_wallet.address
        assert row["status"] == "active"
        assert row["score"] == sample_wallet.score
        assert row["win_rate"] == sample_wallet.profile.win_rate

    def test_row_to_wallet_conversion(
        self,
        wallet_repo: WalletRepository,
        sample_db_row: dict,
    ) -> None:
        """Test converting database row to Wallet model."""
        wallet = wallet_repo._row_to_wallet(sample_db_row)

        assert wallet.address == sample_db_row["address"]
        assert wallet.status == WalletStatus.ACTIVE
        assert wallet.profile.win_rate == sample_db_row["win_rate"]
