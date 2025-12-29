"""Unit tests for DexScreener API client.

Tests cover:
- Fetching boosted tokens with Solana filtering
- Fetching token profiles with Solana filtering
- Fetching token pairs by address
- Error handling for API failures
- Response parsing and validation
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.exceptions import ExternalServiceError


class TestDexScreenerClientBoostedTokens:
    """Tests for fetch_boosted_tokens method."""

    @pytest.mark.asyncio
    async def test_fetch_boosted_tokens_filters_solana(self):
        """Should filter tokens to Solana chain only."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"chainId": "solana", "tokenAddress": "abc123", "icon": None},
            {"chainId": "ethereum", "tokenAddress": "xyz789"},
            {"chainId": "solana", "tokenAddress": "def456", "icon": "http://icon.png"},
        ]

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                tokens = await client.fetch_boosted_tokens()

                assert len(tokens) == 2
                assert tokens[0].token_address == "abc123"
                assert tokens[1].token_address == "def456"
                mock_get.assert_called_once_with("/token-boosts/top/v1")
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_boosted_tokens_handles_empty_response(self):
        """Should return empty list for empty API response."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                tokens = await client.fetch_boosted_tokens()

                assert tokens == []
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_boosted_tokens_handles_non_list_response(self):
        """Should return empty list for unexpected response format."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = {"error": "unexpected"}

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                tokens = await client.fetch_boosted_tokens()

                assert tokens == []
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_boosted_tokens_raises_on_api_error(self):
        """Should raise ExternalServiceError on API failure."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ExternalServiceError(
                service="dexscreener", message="API error"
            )

            client = DexScreenerClient()
            try:
                with pytest.raises(ExternalServiceError):
                    await client.fetch_boosted_tokens()
            finally:
                await client.close()


class TestDexScreenerClientTokenProfiles:
    """Tests for fetch_token_profiles method."""

    @pytest.mark.asyncio
    async def test_fetch_token_profiles_filters_solana(self):
        """Should filter profiles to Solana chain only."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"chainId": "solana", "tokenAddress": "profile1", "url": "http://dex.com/1"},
            {"chainId": "base", "tokenAddress": "profile2"},
            {"chainId": "solana", "tokenAddress": "profile3", "description": "Test token"},
        ]

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                profiles = await client.fetch_token_profiles()

                assert len(profiles) == 2
                assert profiles[0].token_address == "profile1"
                assert profiles[1].token_address == "profile3"
                mock_get.assert_called_once_with("/token-profiles/latest/v1")
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_token_profiles_handles_empty_response(self):
        """Should return empty list for empty API response."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = []

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                profiles = await client.fetch_token_profiles()

                assert profiles == []
            finally:
                await client.close()


class TestDexScreenerClientTokenByAddress:
    """Tests for fetch_token_by_address method."""

    @pytest.mark.asyncio
    async def test_fetch_token_by_address_returns_pairs(self):
        """Should return token pairs for valid address."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "pairs": [
                {
                    "chainId": "solana",
                    "dexId": "raydium",
                    "pairAddress": "pair1",
                    "baseToken": {
                        "address": "token1",
                        "name": "Token One",
                        "symbol": "TK1",
                    },
                    "priceUsd": "1.50",
                    "volume": {"h24": 100000},
                    "liquidity": {"usd": 50000},
                    "marketCap": 1000000,
                    "pairCreatedAt": 1640000000000,
                },
                {
                    "chainId": "ethereum",
                    "dexId": "uniswap",
                    "pairAddress": "pair2",
                    "baseToken": {
                        "address": "token1",
                        "name": "Token One",
                        "symbol": "TK1",
                    },
                },
            ]
        }

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                pairs = await client.fetch_token_by_address("token1")

                assert pairs is not None
                assert len(pairs) == 1  # Only Solana pair
                assert pairs[0].pair_address == "pair1"
                assert pairs[0].base_token.symbol == "TK1"
                mock_get.assert_called_once_with("/latest/dex/tokens/token1")
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_token_by_address_returns_none_when_no_pairs(self):
        """Should return None when token has no pairs."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.return_value = {"pairs": None}

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                pairs = await client.fetch_token_by_address("unknown")

                assert pairs is None
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_token_by_address_returns_none_on_error(self):
        """Should return None (not raise) on API error."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.side_effect = ExternalServiceError(
                service="dexscreener", message="Not found"
            )

            client = DexScreenerClient()
            try:
                pairs = await client.fetch_token_by_address("invalid")

                assert pairs is None  # Graceful handling, no exception
            finally:
                await client.close()

    @pytest.mark.asyncio
    async def test_fetch_token_by_address_returns_none_on_parse_error(self):
        """Should return None on response parsing error."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(DexScreenerClient, "get", new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response

            client = DexScreenerClient()
            try:
                pairs = await client.fetch_token_by_address("token1")

                assert pairs is None
            finally:
                await client.close()


class TestDexScreenerClientInitialization:
    """Tests for client initialization."""

    def test_client_has_correct_base_url(self):
        """Should initialize with correct DexScreener base URL."""
        from walltrack.services.dexscreener.client import DexScreenerClient

        client = DexScreenerClient()
        assert client.base_url == "https://api.dexscreener.com"

    def test_client_inherits_from_base_api_client(self):
        """Should inherit from BaseAPIClient."""
        from walltrack.services.base import BaseAPIClient
        from walltrack.services.dexscreener.client import DexScreenerClient

        client = DexScreenerClient()
        assert isinstance(client, BaseAPIClient)
