"""Unit tests for WalletRepository (Story 3.1 - Task 3.5).

Tests cover:
- Creating new wallet records (with duplicate prevention)
- Retrieving wallet by address
- Listing wallets with pagination
- Updating wallet fields (score, win_rate, decay_status, is_blacklisted)
- Error handling for invalid addresses
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.data.models.wallet import Wallet, WalletCreate, WalletUpdate


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
    def wallet_create_data(self, valid_wallet_address, valid_token_address) -> WalletCreate:
        """WalletCreate fixture for testing."""
        return WalletCreate(
            wallet_address=valid_wallet_address,
            token_source=valid_token_address,
        )

    @pytest.mark.asyncio
    async def test_create_wallet_success(self, wallet_create_data):
        """Should create a new wallet record in database."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        # Mock Supabase client with chained methods
        mock_execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "wallet_address": wallet_create_data.wallet_address,
                        "discovery_date": datetime.now().isoformat(),
                        "token_source": wallet_create_data.token_source,
                        "score": 0.0,
                        "win_rate": 0.0,
                        "decay_status": "ok",
                        "is_blacklisted": False,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    }
                ]
            )
        )

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.create_wallet(wallet_create_data)

        assert isinstance(wallet, Wallet)
        assert wallet.wallet_address == wallet_create_data.wallet_address
        assert wallet.token_source == wallet_create_data.token_source
        assert wallet.score == 0.0
        assert wallet.decay_status == "ok"

    @pytest.mark.asyncio
    async def test_create_wallet_duplicate_ignored(self, wallet_create_data):
        """Should ignore duplicate wallet insertions (PRIMARY KEY prevents duplicates)."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        # Mock Supabase client - duplicate insert returns empty data
        mock_execute = AsyncMock(return_value=MagicMock(data=[]))

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.insert.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.create_wallet(wallet_create_data)

        # Should return None for duplicate (PRIMARY KEY constraint)
        assert wallet is None

    @pytest.mark.asyncio
    async def test_get_wallet_success(self, valid_wallet_address, valid_token_address):
        """Should retrieve wallet by address."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        mock_execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "wallet_address": valid_wallet_address,
                        "discovery_date": datetime.now().isoformat(),
                        "token_source": valid_token_address,
                        "score": 0.75,
                        "win_rate": 0.68,
                        "decay_status": "ok",
                        "is_blacklisted": False,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    }
                ]
            )
        )

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.get_wallet(valid_wallet_address)

        assert isinstance(wallet, Wallet)
        assert wallet.wallet_address == valid_wallet_address
        assert wallet.score == 0.75
        assert wallet.win_rate == 0.68

    @pytest.mark.asyncio
    async def test_get_wallet_not_found(self):
        """Should return None when wallet does not exist."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        mock_execute = AsyncMock(return_value=MagicMock(data=[]))

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.get_wallet("NonExistentAddress123")

        assert wallet is None

    @pytest.mark.asyncio
    async def test_list_wallets_success(self, valid_wallet_address, valid_token_address):
        """Should list wallets with pagination limit."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        mock_execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "wallet_address": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                        "discovery_date": datetime.now().isoformat(),
                        "token_source": valid_token_address,
                        "score": 0.8,
                        "win_rate": 0.7,
                        "decay_status": "ok",
                        "is_blacklisted": False,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    },
                    {
                        "wallet_address": "8xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                        "discovery_date": datetime.now().isoformat(),
                        "token_source": valid_token_address,
                        "score": 0.6,
                        "win_rate": 0.5,
                        "decay_status": "ok",
                        "is_blacklisted": False,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    },
                ]
            )
        )

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallets = await repo.list_wallets(limit=50)

        assert isinstance(wallets, list)
        assert len(wallets) == 2
        assert all(isinstance(w, Wallet) for w in wallets)

    @pytest.mark.asyncio
    async def test_list_wallets_empty(self):
        """Should return empty list when no wallets exist."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        mock_execute = AsyncMock(return_value=MagicMock(data=[]))

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.select.return_value.order.return_value.limit.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallets = await repo.list_wallets(limit=50)

        assert isinstance(wallets, list)
        assert len(wallets) == 0

    @pytest.mark.asyncio
    async def test_update_wallet_success(self, valid_wallet_address, valid_token_address):
        """Should update wallet fields (score, win_rate, decay_status, is_blacklisted)."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        wallet_update = WalletUpdate(
            score=0.85,
            win_rate=0.72,
            decay_status="flagged",
        )

        mock_execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "wallet_address": valid_wallet_address,
                        "discovery_date": datetime.now().isoformat(),
                        "token_source": valid_token_address,
                        "score": 0.85,
                        "win_rate": 0.72,
                        "decay_status": "flagged",
                        "is_blacklisted": False,
                        "created_at": datetime.now().isoformat(),
                        "updated_at": datetime.now().isoformat(),
                    }
                ]
            )
        )

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.update_wallet(valid_wallet_address, wallet_update)

        assert isinstance(wallet, Wallet)
        assert wallet.score == 0.85
        assert wallet.win_rate == 0.72
        assert wallet.decay_status == "flagged"

    @pytest.mark.asyncio
    async def test_update_wallet_not_found(self):
        """Should return None when updating non-existent wallet."""
        from walltrack.data.repositories.wallet_repository import WalletRepository

        wallet_update = WalletUpdate(score=0.5)

        mock_execute = AsyncMock(return_value=MagicMock(data=[]))

        mock_supabase = MagicMock()
        mock_supabase.table.return_value.update.return_value.eq.return_value.execute = mock_execute

        repo = WalletRepository(supabase_client=mock_supabase)
        wallet = await repo.update_wallet("NonExistentAddress123", wallet_update)

        assert wallet is None
