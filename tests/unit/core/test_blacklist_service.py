"""Tests for blacklist service."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from walltrack.core.blacklist_service import BlacklistService
from walltrack.data.models.wallet import Wallet, WalletStatus

# Valid Solana address for testing
WALLET_1 = "A" * 44


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    repo.update.return_value = None
    return repo


@pytest.fixture
def service(mock_wallet_repo: AsyncMock) -> BlacklistService:
    """Create blacklist service with mocked repo."""
    return BlacklistService(wallet_repo=mock_wallet_repo)


class TestBlacklistService:
    """Tests for BlacklistService."""

    @pytest.mark.asyncio
    async def test_add_to_blacklist(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test adding wallet to blacklist."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address=WALLET_1,
            reason="Suspicious activity",
        )

        assert result.status == WalletStatus.BLACKLISTED
        assert result.blacklist_reason == "Suspicious activity"
        assert result.blacklisted_at is not None
        mock_wallet_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_to_blacklist_already_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test adding already blacklisted wallet."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.BLACKLISTED,
            blacklisted_at=datetime.utcnow(),
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address=WALLET_1,
            reason="New reason",
        )

        # Should return existing blacklisted wallet without update
        assert result.status == WalletStatus.BLACKLISTED
        mock_wallet_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_to_blacklist_wallet_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test blacklisting non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.add_to_blacklist(
                address="nonexistent",
                reason="Test",
            )

    @pytest.mark.asyncio
    async def test_add_to_blacklist_with_operator_id(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test blacklisting with operator ID."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address=WALLET_1,
            reason="Spam wallet",
            operator_id="admin123",
        )

        assert result.status == WalletStatus.BLACKLISTED
        mock_wallet_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_from_blacklist(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test removing wallet from blacklist."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.BLACKLISTED,
            blacklisted_at=datetime.utcnow(),
            blacklist_reason="Test reason",
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.remove_from_blacklist(address=WALLET_1)

        assert result.status == WalletStatus.ACTIVE
        assert result.blacklisted_at is None
        assert result.blacklist_reason is None
        mock_wallet_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_not_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test removing non-blacklisted wallet."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        with pytest.raises(ValueError, match="not blacklisted"):
            await service.remove_from_blacklist(address=WALLET_1)

    @pytest.mark.asyncio
    async def test_remove_from_blacklist_wallet_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test removing from blacklist for non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        with pytest.raises(ValueError, match="not found"):
            await service.remove_from_blacklist(address="nonexistent")

    @pytest.mark.asyncio
    async def test_is_blacklisted_true(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking blacklisted wallet."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.BLACKLISTED)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.is_blacklisted(WALLET_1)

        assert result is True

    @pytest.mark.asyncio
    async def test_is_blacklisted_false(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking non-blacklisted wallet."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.is_blacklisted(WALLET_1)

        assert result is False

    @pytest.mark.asyncio
    async def test_is_blacklisted_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test checking non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        result = await service.is_blacklisted("nonexistent")

        assert result is False

    @pytest.mark.asyncio
    async def test_get_blacklisted_wallets(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test getting blacklisted wallets."""
        wallets = [
            Wallet(address=WALLET_1, status=WalletStatus.BLACKLISTED),
            Wallet(address="B" * 44, status=WalletStatus.BLACKLISTED),
        ]
        mock_wallet_repo.get_by_status.return_value = wallets

        result = await service.get_blacklisted_wallets(limit=50)

        assert len(result) == 2
        mock_wallet_repo.get_by_status.assert_called_once_with(
            WalletStatus.BLACKLISTED, limit=50
        )

    @pytest.mark.asyncio
    async def test_check_and_block_signal_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test signal blocking for blacklisted wallet."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.BLACKLISTED)
        mock_wallet_repo.get_by_address.return_value = wallet

        is_blocked, reason = await service.check_and_block_signal(WALLET_1)

        assert is_blocked is True
        assert reason == "blocked_blacklisted"

    @pytest.mark.asyncio
    async def test_check_and_block_signal_not_blacklisted(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test signal not blocked for active wallet."""
        wallet = Wallet(address=WALLET_1, status=WalletStatus.ACTIVE)
        mock_wallet_repo.get_by_address.return_value = wallet

        is_blocked, reason = await service.check_and_block_signal(WALLET_1)

        assert is_blocked is False
        assert reason is None

    @pytest.mark.asyncio
    async def test_check_and_block_signal_wallet_not_found(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test signal not blocked for non-existent wallet."""
        mock_wallet_repo.get_by_address.return_value = None

        is_blocked, reason = await service.check_and_block_signal("nonexistent")

        assert is_blocked is False
        assert reason is None


class TestBlacklistServiceDecayStatus:
    """Tests for blacklisting wallets with decay status."""

    @pytest.mark.asyncio
    async def test_blacklist_decay_detected_wallet(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test blacklisting a wallet that's in decay detected status."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.DECAY_DETECTED,
            decay_detected_at=datetime.utcnow(),
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address=WALLET_1,
            reason="Manual blacklist",
        )

        assert result.status == WalletStatus.BLACKLISTED
        mock_wallet_repo.update.assert_called_once()

    @pytest.mark.asyncio
    async def test_blacklist_insufficient_data_wallet(
        self,
        service: BlacklistService,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test blacklisting a wallet with insufficient data."""
        wallet = Wallet(
            address=WALLET_1,
            status=WalletStatus.INSUFFICIENT_DATA,
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        result = await service.add_to_blacklist(
            address=WALLET_1,
            reason="Known bad actor",
        )

        assert result.status == WalletStatus.BLACKLISTED
        mock_wallet_repo.update.assert_called_once()
