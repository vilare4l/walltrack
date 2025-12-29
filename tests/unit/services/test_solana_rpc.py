"""Unit tests for Solana RPC client.

Tests cover:
- Client initialization with proper configuration
- Wallet validation via getAccountInfo RPC call
- Error handling for network failures
- Circuit breaker behavior
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from walltrack.core.exceptions import WalletConnectionError


class TestSolanaRPCClient:
    """Tests for SolanaRPCClient class."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with Solana RPC URL."""
        settings = MagicMock()
        settings.solana_rpc_url = "https://api.mainnet-beta.solana.com"
        return settings

    @pytest.fixture
    def valid_address(self) -> str:
        """Valid Solana wallet address for testing."""
        return "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"

    @pytest.fixture
    def invalid_address(self) -> str:
        """Invalid address with wrong characters."""
        return "invalid_wallet_address_0OIl"

    def test_wallet_connection_error_exists(self):
        """WalletConnectionError should exist in exceptions module."""
        from walltrack.core.exceptions import WalletConnectionError

        error = WalletConnectionError("Test error", wallet_address="test123")
        assert str(error) == "Test error"
        assert error.wallet_address == "test123"

    @pytest.mark.asyncio
    async def test_client_initialization(self, mock_settings):
        """Client should initialize with settings."""
        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()
            assert client.base_url == mock_settings.solana_rpc_url
            assert client.timeout == 5.0

    @pytest.mark.asyncio
    async def test_get_account_info_success(self, mock_settings, valid_address):
        """Should return account info for valid wallet."""
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "context": {"slot": 123456},
                "value": {
                    "data": ["", "base58"],
                    "executable": False,
                    "lamports": 1000000000,
                    "owner": "11111111111111111111111111111111",
                    "rentEpoch": 0,
                },
            },
        }

        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()

            # Mock the post method
            with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
                mock_http_response = MagicMock()
                mock_http_response.json.return_value = mock_response
                mock_post.return_value = mock_http_response

                result = await client.get_account_info(valid_address)

                assert result is not None
                assert result["lamports"] == 1000000000

    @pytest.mark.asyncio
    async def test_get_account_info_not_found(self, mock_settings, valid_address):
        """Should return None for wallet not found on-chain."""
        mock_response = {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {"context": {"slot": 123456}, "value": None},
        }

        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()

            with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
                mock_http_response = MagicMock()
                mock_http_response.json.return_value = mock_response
                mock_post.return_value = mock_http_response

                result = await client.get_account_info(valid_address)
                assert result is None

    @pytest.mark.asyncio
    async def test_validate_wallet_exists_true(self, mock_settings, valid_address):
        """Should return True if wallet exists on-chain."""
        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()

            with patch.object(
                client, "get_account_info", new_callable=AsyncMock
            ) as mock_get_account:
                mock_get_account.return_value = {"lamports": 1000000}

                result = await client.validate_wallet_exists(valid_address)
                assert result is True

    @pytest.mark.asyncio
    async def test_validate_wallet_exists_false(self, mock_settings, valid_address):
        """Should return False if wallet does not exist on-chain."""
        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()

            with patch.object(
                client, "get_account_info", new_callable=AsyncMock
            ) as mock_get_account:
                mock_get_account.return_value = None

                result = await client.validate_wallet_exists(valid_address)
                assert result is False

    @pytest.mark.asyncio
    async def test_get_account_info_raises_on_error(self, mock_settings, valid_address):
        """Should raise WalletConnectionError on RPC failure."""
        with patch("walltrack.services.solana.rpc_client.get_settings", return_value=mock_settings):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()

            with patch.object(client, "post", new_callable=AsyncMock) as mock_post:
                mock_post.side_effect = httpx.TimeoutException("Connection timeout")

                with pytest.raises(WalletConnectionError) as exc_info:
                    await client.get_account_info(valid_address)

                assert "Connection timeout" in str(exc_info.value)
                assert exc_info.value.wallet_address == valid_address


class TestSolanaRPCClientConfiguration:
    """Tests for SolanaRPCClient configuration and behavior."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with Solana RPC URL."""
        settings = MagicMock()
        settings.solana_rpc_url = "https://api.mainnet-beta.solana.com"
        return settings

    def test_client_has_correct_timeout(self, mock_settings):
        """Client should have 5 second timeout as per AC4."""
        with patch(
            "walltrack.services.solana.rpc_client.get_settings",
            return_value=mock_settings,
        ):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()
            assert client.timeout == 5.0

    def test_client_uses_correct_base_url(self, mock_settings):
        """Client should use base URL from settings."""
        with patch(
            "walltrack.services.solana.rpc_client.get_settings",
            return_value=mock_settings,
        ):
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()
            assert client.base_url == mock_settings.solana_rpc_url

    def test_client_inherits_from_base_api_client(self, mock_settings):
        """Client should inherit retry and circuit breaker from BaseAPIClient."""
        with patch(
            "walltrack.services.solana.rpc_client.get_settings",
            return_value=mock_settings,
        ):
            from walltrack.services.base import BaseAPIClient
            from walltrack.services.solana.rpc_client import SolanaRPCClient

            client = SolanaRPCClient()
            assert isinstance(client, BaseAPIClient)
