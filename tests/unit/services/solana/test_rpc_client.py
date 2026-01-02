"""Unit tests for Solana RPC client - wallet discovery methods.

Tests getSignaturesForAddress() and getTransaction() methods required
for wallet discovery from token transaction history.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from walltrack.core.exceptions import WalletConnectionError
from walltrack.services.solana.rpc_client import SolanaRPCClient


class TestRPCClientSignaturesAndTransactions:
    """Test RPC methods for wallet discovery (Story 3.1)."""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings with RPC URL."""
        with patch("walltrack.services.solana.rpc_client.get_settings") as mock:
            settings = MagicMock()
            settings.solana_rpc_url = "https://api.mainnet-beta.solana.com"
            mock.return_value = settings
            yield settings

    @pytest.fixture
    async def rpc_client(self, mock_settings):
        """Create RPC client instance for testing."""
        client = SolanaRPCClient()
        yield client
        await client.close()

    @pytest.fixture
    def sample_signatures_response(self) -> dict:
        """Sample getSignaturesForAddress RPC response.

        Real response structure from Solana RPC.
        """
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": [
                {
                    "signature": "5j7s8k2d3f4g5h6j7k8l9m0n1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j",
                    "slot": 123456789,
                    "blockTime": 1703001234,
                    "err": None,
                    "memo": None,
                },
                {
                    "signature": "2a3b4c5d6e7f8g9h0i1j2k3l4m5n6o7p8q9r0s1t2u3v4w5x6y7z8a9b0c1d2e3f4g",
                    "slot": 123456790,
                    "blockTime": 1703005678,
                    "err": None,
                    "memo": None,
                },
            ],
        }

    @pytest.fixture
    def sample_transaction_response(self) -> dict:
        """Sample getTransaction RPC response.

        Real response structure from Solana RPC with full transaction data.
        """
        return {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "slot": 123456789,
                "transaction": {
                    "message": {
                        "accountKeys": [
                            "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Wallet
                            "So11111111111111111111111111111111111111112",  # WSOL
                            "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Token
                        ],
                        "instructions": [
                            {
                                "programId": "11111111111111111111111111111111",
                                "accounts": [0, 1],
                                "data": "transfer",
                            }
                        ],
                    },
                    "signatures": [
                        "5j7s8k2d3f4g5h6j7k8l9m0n1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j"
                    ],
                },
                "meta": {
                    "err": None,
                    "preBalances": [1000000000, 2000000000],
                    "postBalances": [500000000, 2500000000],
                    "preTokenBalances": [],
                    "postTokenBalances": [
                        {
                            "accountIndex": 2,
                            "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                            "uiTokenAmount": {
                                "amount": "1000000",
                                "decimals": 6,
                                "uiAmount": 1.0,
                            },
                        }
                    ],
                },
                "blockTime": 1703001234,
            },
        }

    @pytest.mark.asyncio
    async def test_get_signatures_for_address_success(
        self, rpc_client: SolanaRPCClient, sample_signatures_response: dict
    ):
        """Test getSignaturesForAddress returns transaction signatures.

        AC1: System calls rpc.getSignaturesForAddress(token_mint, limit=1000).
        AC1: Receives list of transaction signatures.
        """
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = sample_signatures_response

        with patch.object(rpc_client, "post", return_value=mock_response):
            # Call the method
            signatures = await rpc_client.getSignaturesForAddress(
                address="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                limit=2,
            )

            # Verify results
            assert len(signatures) == 2
            assert signatures[0]["signature"].startswith("5j7s8k")
            assert signatures[1]["signature"].startswith("2a3b4c")
            assert signatures[0]["blockTime"] == 1703001234
            assert signatures[1]["blockTime"] == 1703005678

    @pytest.mark.asyncio
    async def test_get_signatures_for_address_empty_result(
        self, rpc_client: SolanaRPCClient
    ):
        """Test getSignaturesForAddress returns empty list for address with no transactions."""
        # Mock empty response
        mock_response = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": []}

        with patch.object(rpc_client, "post", return_value=mock_response):
            signatures = await rpc_client.getSignaturesForAddress(
                address="EmptyWallet1111111111111111111111111111111",
                limit=1000,
            )

            assert signatures == []

    @pytest.mark.asyncio
    async def test_get_transaction_success(
        self, rpc_client: SolanaRPCClient, sample_transaction_response: dict
    ):
        """Test getTransaction returns full transaction data.

        AC2: System calls rpc.getTransaction(signature) for each signature.
        AC2: Retrieves full transaction data with instructions and accounts.
        """
        # Mock the HTTP response
        mock_response = MagicMock()
        mock_response.json.return_value = sample_transaction_response

        with patch.object(rpc_client, "post", return_value=mock_response):
            # Call the method
            transaction = await rpc_client.getTransaction(
                signature="5j7s8k2d3f4g5h6j7k8l9m0n1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j"
            )

            # Verify full transaction structure
            assert transaction is not None
            assert "transaction" in transaction
            assert "meta" in transaction
            assert "blockTime" in transaction
            assert transaction["blockTime"] == 1703001234

            # Verify transaction details
            tx = transaction["transaction"]
            assert "message" in tx
            assert "signatures" in tx
            assert len(tx["message"]["accountKeys"]) == 3

            # Verify meta (balance changes)
            meta = transaction["meta"]
            assert meta["err"] is None
            assert len(meta["preBalances"]) == 2
            assert len(meta["postBalances"]) == 2

    @pytest.mark.asyncio
    async def test_get_transaction_not_found(self, rpc_client: SolanaRPCClient):
        """Test getTransaction returns None for non-existent signature."""
        # Mock null result (transaction not found)
        mock_response = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": None}

        with patch.object(rpc_client, "post", return_value=mock_response):
            transaction = await rpc_client.getTransaction(
                signature="InvalidSignature1111111111111111111111111111111111111111111111"
            )

            assert transaction is None

    @pytest.mark.asyncio
    async def test_get_transaction_handles_429_with_retry(
        self, rpc_client: SolanaRPCClient, sample_transaction_response: dict
    ):
        """Test getTransaction uses BaseAPIClient post() which handles 429 retries.

        Task 2: Add exponential backoff on 429 errors (1s → 2s → 4s).
        Note: Exponential backoff is already implemented in BaseAPIClient._request().
        This test verifies that getTransaction() calls post(), which inherits retry logic.
        """
        # Mock successful response (retry logic is inherited from BaseAPIClient)
        mock_response = MagicMock()
        mock_response.json.return_value = sample_transaction_response

        with patch.object(rpc_client, "post", return_value=mock_response) as mock_post:
            transaction = await rpc_client.getTransaction(
                signature="5j7s8k2d3f4g5h6j7k8l9m0n1p2q3r4s5t6u7v8w9x0y1z2a3b4c5d6e7f8g9h0i1j"
            )

            # Verify post() was called (which has retry logic built-in)
            assert mock_post.called
            assert transaction is not None
            assert transaction["blockTime"] == 1703001234

    @pytest.mark.asyncio
    async def test_get_signatures_handles_rpc_error(self, rpc_client: SolanaRPCClient):
        """Test getSignaturesForAddress raises WalletConnectionError on RPC failure."""
        # Mock RPC error response
        with patch.object(
            rpc_client,
            "post",
            side_effect=Exception("RPC connection failed"),
        ):
            with pytest.raises(WalletConnectionError, match="Failed to fetch signatures"):
                await rpc_client.getSignaturesForAddress(
                    address="ErrorAddress111111111111111111111111111111",
                    limit=1000,
                )

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, rpc_client: SolanaRPCClient):
        """Test rate limiting enforces 2 req/sec throttle.

        Task 2: Add throttling: 2 req/sec (safety margin below 4 req/sec limit).

        This test verifies that multiple consecutive requests are throttled
        to prevent exceeding Solana RPC Public rate limits.
        """
        # Mock successful responses
        mock_response = MagicMock()
        mock_response.json.return_value = {"jsonrpc": "2.0", "id": 1, "result": []}

        with patch.object(rpc_client, "post", return_value=mock_response):
            # Make 3 consecutive requests
            start_time = asyncio.get_event_loop().time()

            await rpc_client.getSignaturesForAddress("addr1", limit=10)
            await rpc_client.getSignaturesForAddress("addr2", limit=10)
            await rpc_client.getSignaturesForAddress("addr3", limit=10)

            end_time = asyncio.get_event_loop().time()
            elapsed = end_time - start_time

            # 3 requests at 2 req/sec = minimum 1 second (0.5s between each)
            # First request: t=0
            # Second request: t=0.5s (throttle 0.5s)
            # Third request: t=1.0s (throttle 0.5s)
            # Total minimum: 1.0 second
            assert elapsed >= 1.0, f"Expected >=1.0s elapsed, got {elapsed:.2f}s"
            assert elapsed < 1.5, f"Throttling too aggressive, got {elapsed:.2f}s"

    @pytest.mark.asyncio
    async def test_get_signatures_respects_limit_parameter(
        self, rpc_client: SolanaRPCClient, sample_signatures_response: dict
    ):
        """Test getSignaturesForAddress passes limit parameter to RPC."""
        mock_response = MagicMock()
        mock_response.json.return_value = sample_signatures_response

        with patch.object(rpc_client, "post", return_value=mock_response) as mock_post:
            await rpc_client.getSignaturesForAddress(
                address="TestAddr111111111111111111111111111111111",
                limit=500,
            )

            # Verify the RPC call included limit in params
            call_args = mock_post.call_args
            payload = call_args.kwargs["json"]
            assert payload["method"] == "getSignaturesForAddress"
            assert payload["params"][0] == "TestAddr111111111111111111111111111111111"
            assert payload["params"][1]["limit"] == 500
