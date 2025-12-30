"""Unit tests for HeliusClient.

Tests the Helius API client for transaction history fetching
with mocked HTTP responses using respx.
"""

import pytest
import respx
from httpx import Response

from walltrack.core.exceptions import ExternalServiceError
from walltrack.services.helius.client import HeliusClient


@pytest.fixture
def helius_client():
    """Create HeliusClient instance for testing."""
    import os
    # Set dummy API key for testing
    os.environ["HELIUS_API_KEY"] = "test-api-key-12345"
    client = HeliusClient()
    yield client
    # Cleanup
    del os.environ["HELIUS_API_KEY"]


@pytest.fixture
def mock_token_transactions_success():
    """Mock successful Helius token transactions response.

    Returns mock data for a token with 2 swap transactions:
    - Transaction 1: Wallet1 buys token (30min after launch)
    - Transaction 2: Wallet1 sells token (60% profit)
    """
    return [
        {
            "signature": "5xJ8...abc",
            "timestamp": 1704067200,  # 30 min after token launch
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "Wallet1abc123...",
                    "toUserAccount": "TokenMintXYZ...",
                    "amount": 500000000  # BUY 0.5 SOL
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "TokenMintXYZ...",
                    "toUserAccount": "Wallet1abc123...",
                    "mint": "TokenMintXYZ",
                    "tokenAmount": 1000000
                }
            ]
        },
        {
            "signature": "7yK9...def",
            "timestamp": 1704070800,  # Later SELL
            "type": "SWAP",
            "source": "RAYDIUM",
            "nativeTransfers": [
                {
                    "fromUserAccount": "TokenMintXYZ...",
                    "toUserAccount": "Wallet1abc123...",
                    "amount": 800000000  # SELL 0.8 SOL (60% profit)
                }
            ],
            "tokenTransfers": [
                {
                    "fromUserAccount": "Wallet1abc123...",
                    "toUserAccount": "TokenMintXYZ...",
                    "mint": "TokenMintXYZ",
                    "tokenAmount": 1000000
                }
            ]
        }
    ]


@pytest.mark.asyncio
@respx.mock
async def test_get_token_transactions_success(helius_client, mock_token_transactions_success):
    """Test successful token transactions fetching."""
    # ARRANGE
    token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Valid Solana address (USDC)

    # Mock the Helius API response
    respx.get(
        url__regex=r"https://api\.helius\.xyz/v0/addresses/.*/transactions.*"
    ).mock(return_value=Response(200, json=mock_token_transactions_success))

    # ACT
    transactions = await helius_client.get_token_transactions(
        token_mint=token_mint,
        limit=100
    )

    # ASSERT
    assert len(transactions) == 2
    assert transactions[0]["signature"] == "5xJ8...abc"
    assert transactions[0]["type"] == "SWAP"
    assert transactions[1]["signature"] == "7yK9...def"

    # Cleanup
    await helius_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_token_transactions_empty(helius_client):
    """Test empty response when no transactions found."""
    # ARRANGE
    token_mint = "So11111111111111111111111111111111111111112"  # Valid Solana address (Wrapped SOL)

    # Mock empty response
    respx.get(
        url__regex=r"https://api\.helius\.xyz/v0/addresses/.*/transactions.*"
    ).mock(return_value=Response(200, json=[]))

    # ACT
    transactions = await helius_client.get_token_transactions(
        token_mint=token_mint,
        limit=100
    )

    # ASSERT
    assert transactions == []

    # Cleanup
    await helius_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_token_transactions_api_error(helius_client):
    """Test error handling when Helius API fails."""
    # ARRANGE
    token_mint = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"  # Valid Solana address (RAY)

    # Mock 500 error from Helius API
    respx.get(
        url__regex=r"https://api\.helius\.xyz/v0/addresses/.*/transactions.*"
    ).mock(return_value=Response(500, text="Internal Server Error"))

    # ACT & ASSERT
    with pytest.raises(ExternalServiceError) as exc_info:
        await helius_client.get_token_transactions(
            token_mint=token_mint,
            limit=100
        )

    # Check error message contains Helius reference (API or URL)
    error_msg = str(exc_info.value)
    assert ("Helius API" in error_msg or "api.helius.xyz" in error_msg)

    # Cleanup
    await helius_client.close()


@pytest.mark.asyncio
@respx.mock
async def test_get_token_transactions_with_filters(helius_client, mock_token_transactions_success):
    """Test token transactions with type filter."""
    # ARRANGE
    token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # Valid Solana address (USDC)

    # Mock response
    respx.get(
        url__regex=r"https://api\.helius\.xyz/v0/addresses/.*/transactions.*"
    ).mock(return_value=Response(200, json=mock_token_transactions_success))

    # ACT
    transactions = await helius_client.get_token_transactions(
        token_mint=token_mint,
        limit=50,
        tx_type="SWAP"
    )

    # ASSERT
    assert len(transactions) == 2
    # Verify all are SWAP transactions
    for tx in transactions:
        assert tx["type"] == "SWAP"

    # Cleanup
    await helius_client.close()
