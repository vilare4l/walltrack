"""Unit tests for WalletClient - Trading wallet functionality.

Tests cover:
- Wallet initialization and keypair loading
- Transaction signing validation
- Balance retrieval (SOL + tokens)
- Safe mode functionality
- Connection failure handling
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import base58

from pydantic import SecretStr
from solders.keypair import Keypair

# Generate a VALID test keypair (DO NOT USE IN PRODUCTION)
# This creates a real keypair that can actually sign messages
_test_keypair = Keypair()
TEST_PRIVATE_KEY = base58.b58encode(bytes(_test_keypair)).decode()


@pytest.fixture
def mock_wallet_settings():
    """Create mock wallet settings for testing."""
    from walltrack.config.wallet_settings import WalletSettings

    return WalletSettings(
        trading_wallet_private_key=SecretStr(TEST_PRIVATE_KEY),
        solana_rpc_url="https://api.devnet.solana.com",
        min_sol_balance=0.01,
        auto_safe_mode_on_error=True,
    )


@pytest.fixture
def wallet_client(mock_wallet_settings):
    """Create WalletClient with mock settings."""
    from walltrack.services.solana.wallet_client import WalletClient

    return WalletClient(settings=mock_wallet_settings)


class TestTradingWalletModels:
    """Tests for trading wallet data models."""

    def test_wallet_connection_status_enum(self):
        """Test WalletConnectionStatus enum values."""
        from walltrack.models.trading_wallet import WalletConnectionStatus

        assert WalletConnectionStatus.CONNECTED == "connected"
        assert WalletConnectionStatus.DISCONNECTED == "disconnected"
        assert WalletConnectionStatus.ERROR == "error"
        assert WalletConnectionStatus.VALIDATING == "validating"

    def test_safe_mode_reason_enum(self):
        """Test SafeModeReason enum values."""
        from walltrack.models.trading_wallet import SafeModeReason

        assert SafeModeReason.CONNECTION_FAILED == "connection_failed"
        assert SafeModeReason.SIGNING_FAILED == "signing_failed"
        assert SafeModeReason.RPC_UNAVAILABLE == "rpc_unavailable"
        assert SafeModeReason.INSUFFICIENT_BALANCE == "insufficient_balance"
        assert SafeModeReason.MANUAL == "manual"

    def test_token_balance_valid(self):
        """Test valid TokenBalance creation."""
        from walltrack.models.trading_wallet import TokenBalance

        token = TokenBalance(
            mint_address="So11111111111111111111111111111111111111112",
            symbol="SOL",
            amount=1000000000.0,
            decimals=9,
            ui_amount=1.0,
            estimated_value_sol=1.0,
        )

        assert token.mint_address == "So11111111111111111111111111111111111111112"
        assert token.ui_amount == 1.0

    def test_token_balance_invalid_mint_rejected(self):
        """Test that invalid mint address is rejected."""
        from walltrack.models.trading_wallet import TokenBalance

        with pytest.raises(ValueError, match="Invalid"):
            TokenBalance(
                mint_address="invalid",
                amount=100.0,
                decimals=9,
                ui_amount=0.0001,
            )

    def test_wallet_balance_sufficient_sol(self):
        """Test has_sufficient_sol property."""
        from walltrack.models.trading_wallet import WalletBalance

        balance = WalletBalance(
            sol_balance=1_000_000_000,
            sol_balance_ui=1.0,
            token_balances=[],
            total_value_sol=1.0,
        )

        assert balance.has_sufficient_sol is True

    def test_wallet_balance_insufficient_sol(self):
        """Test has_sufficient_sol with low balance."""
        from walltrack.models.trading_wallet import WalletBalance

        balance = WalletBalance(
            sol_balance=1000,  # 0.000001 SOL
            sol_balance_ui=0.000001,
            token_balances=[],
            total_value_sol=0.000001,
        )

        assert balance.has_sufficient_sol is False

    def test_wallet_state_creation(self):
        """Test WalletState creation."""
        from walltrack.models.trading_wallet import WalletState, WalletConnectionStatus

        state = WalletState(
            public_key="7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
            status=WalletConnectionStatus.CONNECTED,
        )

        assert state.public_key == "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU"
        assert state.status == WalletConnectionStatus.CONNECTED
        assert state.safe_mode is False

    def test_wallet_state_invalid_pubkey_rejected(self):
        """Test that invalid public key is rejected."""
        from walltrack.models.trading_wallet import WalletState

        with pytest.raises(ValueError, match="Invalid"):
            WalletState(
                public_key="invalid",
            )

    def test_signing_result_success(self):
        """Test SigningResult for successful signing."""
        from walltrack.models.trading_wallet import SigningResult

        result = SigningResult(
            success=True,
            message_hash="abc123",
            signature="sig123",
            latency_ms=10.5,
        )

        assert result.success is True
        assert result.latency_ms >= 0

    def test_signing_result_failure(self):
        """Test SigningResult for failed signing."""
        from walltrack.models.trading_wallet import SigningResult

        result = SigningResult(
            success=False,
            error="Keypair not initialized",
            latency_ms=0,
        )

        assert result.success is False
        assert result.error is not None


class TestWalletSettings:
    """Tests for WalletSettings configuration."""

    def test_wallet_settings_loads_private_key(self, mock_wallet_settings):
        """Test that private key is loaded as SecretStr."""
        assert isinstance(mock_wallet_settings.trading_wallet_private_key, SecretStr)
        # SecretStr masks the value in repr (shows ***)
        assert "**" in repr(mock_wallet_settings.trading_wallet_private_key)
        # The actual value should NOT be in the repr
        assert TEST_PRIVATE_KEY not in repr(mock_wallet_settings.trading_wallet_private_key)

    def test_wallet_settings_default_values(self, mock_wallet_settings):
        """Test default configuration values."""
        assert mock_wallet_settings.rpc_commitment == "confirmed"
        assert mock_wallet_settings.rpc_timeout_seconds == 30
        assert mock_wallet_settings.auto_safe_mode_on_error is True

    def test_wallet_settings_validates_short_key(self):
        """Test that too-short private key is rejected."""
        from walltrack.config.wallet_settings import WalletSettings

        with pytest.raises(ValueError, match="too short"):
            WalletSettings(
                trading_wallet_private_key=SecretStr("short"),
                solana_rpc_url="https://api.devnet.solana.com",
            )


class TestWalletClientInitialization:
    """Tests for wallet initialization."""

    @pytest.mark.asyncio
    async def test_initialize_success(self, wallet_client):
        """Test successful wallet initialization."""
        from walltrack.models.trading_wallet import (
            WalletConnectionStatus,
            WalletBalance,
        )

        with patch.object(
            wallet_client, "_validate_connectivity", new_callable=AsyncMock
        ):
            with patch.object(
                wallet_client, "refresh_balance", new_callable=AsyncMock
            ) as mock_balance:
                mock_balance.return_value = WalletBalance(
                    sol_balance=1_000_000_000,
                    sol_balance_ui=1.0,
                    token_balances=[],
                    total_value_sol=1.0,
                )

                state = await wallet_client.initialize()

                assert state.status == WalletConnectionStatus.CONNECTED
                assert state.public_key is not None
                assert len(state.public_key) == 44  # Base58 pubkey length

    @pytest.mark.asyncio
    async def test_initialize_connection_failure_enters_safe_mode(self, wallet_client):
        """Test that connection failure enters safe mode."""
        from walltrack.services.solana.wallet_client import WalletConnectionError
        from walltrack.models.trading_wallet import SafeModeReason

        with patch.object(
            wallet_client,
            "_validate_connectivity",
            new_callable=AsyncMock,
            side_effect=Exception("RPC unavailable"),
        ):
            with pytest.raises(WalletConnectionError):
                await wallet_client.initialize()

            assert wallet_client.state.safe_mode is True
            assert wallet_client.state.safe_mode_reason == SafeModeReason.CONNECTION_FAILED


class TestWalletSigning:
    """Tests for transaction signing validation."""

    @pytest.mark.asyncio
    async def test_validate_signing_success(self, wallet_client):
        """Test successful signing validation."""
        from walltrack.models.trading_wallet import WalletBalance

        # Initialize first
        with patch.object(
            wallet_client, "_validate_connectivity", new_callable=AsyncMock
        ):
            with patch.object(
                wallet_client, "refresh_balance", new_callable=AsyncMock
            ) as mock_balance:
                mock_balance.return_value = WalletBalance(
                    sol_balance=1_000_000_000,
                    sol_balance_ui=1.0,
                    token_balances=[],
                    total_value_sol=1.0,
                )
                await wallet_client.initialize()

        result = await wallet_client.validate_signing()

        assert result.success is True
        assert result.signature is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_validate_signing_without_init_fails(self, wallet_client):
        """Test signing fails without initialization."""
        result = await wallet_client.validate_signing()

        assert result.success is False
        assert "not initialized" in result.error.lower()


class TestSafeMode:
    """Tests for safe mode functionality."""

    @pytest.mark.asyncio
    async def test_manual_safe_mode_enable(self, wallet_client):
        """Test manual safe mode activation."""
        from walltrack.models.trading_wallet import SafeModeReason

        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.state.safe_mode is True
        assert wallet_client.state.safe_mode_reason == SafeModeReason.MANUAL
        assert wallet_client.state.safe_mode_since is not None

    @pytest.mark.asyncio
    async def test_manual_safe_mode_disable(self, wallet_client):
        """Test manual safe mode deactivation."""
        wallet_client.set_manual_safe_mode(True)
        wallet_client.set_manual_safe_mode(False)

        assert wallet_client.state.safe_mode is False
        assert wallet_client.state.safe_mode_reason is None

    @pytest.mark.asyncio
    async def test_is_ready_for_trading_blocked_in_safe_mode(self, wallet_client):
        """Test trading blocked in safe mode."""
        from walltrack.models.trading_wallet import WalletBalance

        # Create a balance with sufficient SOL
        test_balance = WalletBalance(
            sol_balance=1_000_000_000,
            sol_balance_ui=1.0,
            token_balances=[],
            total_value_sol=1.0,
        )

        # Mock refresh_balance to set state.balance
        async def mock_refresh():
            wallet_client._state.balance = test_balance
            return test_balance

        # Initialize
        with patch.object(
            wallet_client, "_validate_connectivity", new_callable=AsyncMock
        ):
            with patch.object(
                wallet_client, "refresh_balance", side_effect=mock_refresh
            ):
                await wallet_client.initialize()

        assert wallet_client.is_ready_for_trading is True

        # Enable safe mode
        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.is_ready_for_trading is False

    @pytest.mark.asyncio
    async def test_keypair_access_blocked_in_safe_mode(self, wallet_client):
        """Test keypair access blocked in safe mode."""
        wallet_client.set_manual_safe_mode(True)

        assert wallet_client.keypair is None


class TestBalanceRetrieval:
    """Tests for balance retrieval."""

    @pytest.mark.asyncio
    async def test_insufficient_sol_warning(self, wallet_client):
        """Test warning when SOL balance is low."""
        from walltrack.models.trading_wallet import WalletBalance

        # Low balance - less than MIN_SOL_REQUIRED (0.01)
        low_balance = WalletBalance(
            sol_balance=1_000,  # 0.000001 SOL
            sol_balance_ui=0.000001,
            token_balances=[],
            total_value_sol=0.000001,
        )

        # Mock refresh_balance to set state.balance
        async def mock_refresh():
            wallet_client._state.balance = low_balance
            return low_balance

        with patch.object(
            wallet_client, "_validate_connectivity", new_callable=AsyncMock
        ):
            with patch.object(
                wallet_client, "refresh_balance", side_effect=mock_refresh
            ):
                await wallet_client.initialize()

        assert wallet_client.state.balance.has_sufficient_sol is False
