"""Unit tests for wallet address validation.

Tests cover:
- Base58 format validation for Solana addresses
- Address length validation
- On-chain wallet existence validation
- WalletValidationResult model
"""

from unittest.mock import AsyncMock, patch

import pytest


class TestIsValidSolanaAddress:
    """Tests for is_valid_solana_address function."""

    def test_valid_address_returns_true(self):
        """Valid Solana addresses should return True."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        # Real Solana addresses (44 chars, base58)
        valid_addresses = [
            "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            "So11111111111111111111111111111111111111112",  # Wrapped SOL
            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        ]

        for addr in valid_addresses:
            assert is_valid_solana_address(addr) is True, f"Expected {addr} to be valid"

    def test_invalid_characters_returns_false(self):
        """Addresses with invalid base58 characters should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        # Contains 0, O, I, l which are not in base58 alphabet
        invalid_addresses = [
            "0WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # 0 not in base58
            "OWzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # O not in base58
            "IWzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # I not in base58
            "lWzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",  # l not in base58
        ]

        for addr in invalid_addresses:
            assert is_valid_solana_address(addr) is False, f"Expected {addr} to be invalid"

    def test_too_short_returns_false(self):
        """Addresses shorter than 32 chars should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        assert is_valid_solana_address("abc") is False
        assert is_valid_solana_address("1234567890123456789012345678901") is False  # 31 chars

    def test_too_long_returns_false(self):
        """Addresses longer than 44 chars should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        assert is_valid_solana_address("a" * 45) is False
        assert is_valid_solana_address("a" * 100) is False

    def test_empty_string_returns_false(self):
        """Empty string should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        assert is_valid_solana_address("") is False

    def test_none_returns_false(self):
        """None should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        assert is_valid_solana_address(None) is False  # type: ignore[arg-type]

    def test_whitespace_only_returns_false(self):
        """Whitespace-only string should return False."""
        from walltrack.core.wallet.validator import is_valid_solana_address

        assert is_valid_solana_address("   ") is False
        assert is_valid_solana_address("\t\n") is False


class TestWalletValidationResult:
    """Tests for WalletValidationResult Pydantic model."""

    def test_model_creation(self):
        """Should create model with all fields."""
        from walltrack.data.models.wallet import WalletValidationResult

        result = WalletValidationResult(
            is_valid=True,
            address="9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
            exists_on_chain=True,
        )

        assert result.is_valid is True
        assert result.address == "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        assert result.exists_on_chain is True
        assert result.error_message is None

    def test_model_with_error(self):
        """Should create model with error message."""
        from walltrack.data.models.wallet import WalletValidationResult

        result = WalletValidationResult(
            is_valid=False,
            address="invalid",
            error_message="Invalid Solana address format",
        )

        assert result.is_valid is False
        assert result.error_message == "Invalid Solana address format"
        assert result.exists_on_chain is False

    def test_model_is_pydantic_basemodel(self):
        """WalletValidationResult should be a Pydantic BaseModel."""
        from pydantic import BaseModel

        from walltrack.data.models.wallet import WalletValidationResult

        assert issubclass(WalletValidationResult, BaseModel)


class TestValidateWalletOnChain:
    """Tests for validate_wallet_on_chain function."""

    @pytest.mark.asyncio
    async def test_invalid_format_returns_error(self):
        """Invalid address format should return error without RPC call."""
        from walltrack.core.wallet.validator import validate_wallet_on_chain

        result = await validate_wallet_on_chain("invalid_address")

        assert result.is_valid is False
        assert result.error_message == "Invalid Solana address format"
        assert result.exists_on_chain is False

    @pytest.mark.asyncio
    async def test_valid_address_exists_on_chain(self):
        """Valid address existing on-chain should return success."""
        from walltrack.core.wallet.validator import validate_wallet_on_chain

        with patch(
            "walltrack.core.wallet.validator.SolanaRPCClient"
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.validate_wallet_exists = AsyncMock(return_value=True)
            mock_instance.close = AsyncMock()

            result = await validate_wallet_on_chain(
                "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
            )

            assert result.is_valid is True
            assert result.exists_on_chain is True
            assert result.error_message is None

    @pytest.mark.asyncio
    async def test_valid_address_not_found_on_chain(self):
        """Valid address not found on-chain should return error."""
        from walltrack.core.wallet.validator import validate_wallet_on_chain

        with patch(
            "walltrack.core.wallet.validator.SolanaRPCClient"
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.validate_wallet_exists = AsyncMock(return_value=False)
            mock_instance.close = AsyncMock()

            result = await validate_wallet_on_chain(
                "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
            )

            assert result.is_valid is False
            assert result.exists_on_chain is False
            assert result.error_message == "Wallet not found on Solana network"

    @pytest.mark.asyncio
    async def test_rpc_error_returns_error(self):
        """RPC connection error should return error message."""
        from walltrack.core.exceptions import WalletConnectionError
        from walltrack.core.wallet.validator import validate_wallet_on_chain

        with patch(
            "walltrack.core.wallet.validator.SolanaRPCClient"
        ) as MockClient:
            mock_instance = MockClient.return_value
            mock_instance.validate_wallet_exists = AsyncMock(
                side_effect=WalletConnectionError("Connection timeout")
            )
            mock_instance.close = AsyncMock()

            result = await validate_wallet_on_chain(
                "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
            )

            assert result.is_valid is False
            assert "Connection timeout" in result.error_message
