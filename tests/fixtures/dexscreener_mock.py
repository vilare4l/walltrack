"""Mock responses for DexScreener API.

Provides pytest fixtures to intercept DexScreener API calls during E2E tests.
Uses respx library for httpx mocking.

Story 2.4 - AC4: Mock DexScreener for CI
- Tests are deterministic (same data every run)
- Real API is NOT called during CI runs
- Mock intercepts at httpx client level

Usage:
    @pytest.fixture
    def test_something(page, mock_dexscreener):
        # DexScreener API calls are now mocked
        page.goto(...)
"""

from collections.abc import Generator
from typing import Any

import pytest
import respx
from httpx import Response

# =============================================================================
# Mock Response Data
# =============================================================================

# Boosted tokens endpoint: /token-boosts/top/v1
MOCK_BOOSTED_TOKENS: list[dict[str, Any]] = [
    {
        "chainId": "solana",
        "tokenAddress": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "icon": "https://example.com/usdc.png",
        "description": "USD Coin - Stablecoin",
        "amount": 5000,
    },
    {
        "chainId": "solana",
        "tokenAddress": "So11111111111111111111111111111111111111112",
        "icon": "https://example.com/wsol.png",
        "description": "Wrapped SOL",
        "amount": 3000,
    },
    {
        "chainId": "solana",
        "tokenAddress": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "icon": "https://example.com/bonk.png",
        "description": "BONK - Community Dog Coin",
        "amount": 2500,
    },
]

# Token profiles endpoint: /token-profiles/latest/v1
MOCK_TOKEN_PROFILES: list[dict[str, Any]] = [
    {
        "chainId": "solana",
        "tokenAddress": "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
        "icon": "https://example.com/wen.png",
        "description": "WEN - Meme Token",
    },
    {
        "chainId": "solana",
        "tokenAddress": "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "icon": "https://example.com/jup.png",
        "description": "Jupiter Aggregator",
    },
]

# Token pairs endpoint: /latest/dex/tokens/{address}
# This is a factory that returns pairs data for any token address
MOCK_TOKEN_PAIRS_BASE: dict[str, Any] = {
    "schemaVersion": "1.0.0",
    "pairs": [
        {
            "chainId": "solana",
            "dexId": "raydium",
            "pairAddress": "58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2",
            "baseToken": {
                "address": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "name": "USD Coin",
                "symbol": "USDC",
            },
            "quoteToken": {
                "address": "So11111111111111111111111111111111111111112",
                "name": "Wrapped SOL",
                "symbol": "SOL",
            },
            "priceUsd": "1.00",
            "priceNative": "0.005",
            "volume": {"h24": 150_000_000.0, "h6": 35_000_000.0, "h1": 8_000_000.0},
            "liquidity": {"usd": 50_000_000.0, "base": 50_000_000, "quote": 250_000},
            "marketCap": 25_000_000_000.0,
            "fdv": 25_000_000_000.0,
            "pairCreatedAt": 1640000000000,  # Unix timestamp in ms
        }
    ],
}


def _create_mock_pairs_for_token(address: str) -> dict[str, Any]:
    """Create mock pairs response for a specific token address.

    Args:
        address: Token mint address.

    Returns:
        Mock pairs response with the token address substituted.
    """
    # Create a copy and substitute the address
    response = MOCK_TOKEN_PAIRS_BASE.copy()
    pairs = [pair.copy() for pair in response["pairs"]]

    # Map known addresses to their metadata
    token_metadata = {
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": {
            "name": "USD Coin",
            "symbol": "USDC",
            "priceUsd": "1.00",
            "marketCap": 25_000_000_000.0,
        },
        "So11111111111111111111111111111111111111112": {
            "name": "Wrapped SOL",
            "symbol": "WSOL",
            "priceUsd": "180.50",
            "marketCap": 80_000_000_000.0,
        },
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": {
            "name": "Bonk",
            "symbol": "BONK",
            "priceUsd": "0.00002345",
            "marketCap": 1_500_000_000.0,
        },
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs": {
            "name": "Wen",
            "symbol": "WEN",
            "priceUsd": "0.000089",
            "marketCap": 50_000_000.0,
        },
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN": {
            "name": "Jupiter",
            "symbol": "JUP",
            "priceUsd": "0.85",
            "marketCap": 1_200_000_000.0,
        },
    }

    # Default metadata for unknown tokens
    metadata = token_metadata.get(
        address,
        {
            "name": "Unknown Token",
            "symbol": "???",
            "priceUsd": "0.001",
            "marketCap": 1_000_000.0,
        },
    )

    # Update the pairs with the correct token info
    for pair in pairs:
        pair["baseToken"] = {
            "address": address,
            "name": metadata["name"],
            "symbol": metadata["symbol"],
        }
        pair["priceUsd"] = metadata["priceUsd"]
        pair["marketCap"] = metadata["marketCap"]

    response["pairs"] = pairs
    return response


# =============================================================================
# Pytest Fixtures
# =============================================================================


@pytest.fixture
def mock_boosted_tokens() -> list[dict[str, Any]]:
    """Return mock boosted tokens response.

    Returns:
        List of boosted token data.
    """
    return MOCK_BOOSTED_TOKENS


@pytest.fixture
def mock_token_profiles() -> list[dict[str, Any]]:
    """Return mock token profiles response.

    Returns:
        List of token profile data.
    """
    return MOCK_TOKEN_PROFILES


@pytest.fixture
def mock_token_pairs() -> dict[str, Any]:
    """Return mock token pairs response (USDC as example).

    Returns:
        Token pairs response for USDC.
    """
    return MOCK_TOKEN_PAIRS_BASE


@pytest.fixture
def mock_dexscreener() -> Generator[respx.MockRouter, None, None]:
    """Mock all DexScreener API calls.

    Intercepts:
    - GET https://api.dexscreener.com/token-boosts/top/v1
    - GET https://api.dexscreener.com/token-profiles/latest/v1
    - GET https://api.dexscreener.com/latest/dex/tokens/{address}

    Yields:
        respx.MockRouter: The mock router for additional assertions.

    Example:
        def test_discovery(page, mock_dexscreener):
            # All DexScreener calls are now mocked
            page.goto(base_url)
            page.click("text=Run Discovery")
            # ...

            # Optional: verify specific calls were made
            assert mock_dexscreener["boosted"].called
    """
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        # Mock boosted tokens endpoint
        router.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
            return_value=Response(200, json=MOCK_BOOSTED_TOKENS)
        )

        # Mock token profiles endpoint
        router.get("https://api.dexscreener.com/token-profiles/latest/v1").mock(
            return_value=Response(200, json=MOCK_TOKEN_PROFILES)
        )

        # Mock token pairs endpoint (pattern for any token address)
        # This uses a side_effect to generate dynamic responses per token
        def _pairs_handler(request: respx.Route) -> Response:
            # Extract token address from URL path
            # URL format: https://api.dexscreener.com/latest/dex/tokens/{address}
            path_parts = str(request.url.path).split("/")
            address = path_parts[-1] if path_parts else ""
            return Response(200, json=_create_mock_pairs_for_token(address))

        router.get(url__regex=r"https://api\.dexscreener\.com/latest/dex/tokens/.+").mock(
            side_effect=_pairs_handler
        )

        yield router


@pytest.fixture
def mock_dexscreener_empty() -> Generator[respx.MockRouter, None, None]:
    """Mock DexScreener API with empty responses.

    Useful for testing empty state scenarios.

    Yields:
        respx.MockRouter: The mock router.
    """
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        # All endpoints return empty lists/objects
        router.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
            return_value=Response(200, json=[])
        )
        router.get("https://api.dexscreener.com/token-profiles/latest/v1").mock(
            return_value=Response(200, json=[])
        )
        router.get(url__regex=r"https://api\.dexscreener\.com/latest/dex/tokens/.+").mock(
            return_value=Response(200, json={"pairs": []})
        )

        yield router


@pytest.fixture
def mock_dexscreener_error() -> Generator[respx.MockRouter, None, None]:
    """Mock DexScreener API with error responses.

    Useful for testing error handling.

    Yields:
        respx.MockRouter: The mock router.
    """
    with respx.mock(assert_all_called=False, assert_all_mocked=False) as router:
        # All endpoints return 500 errors
        router.get("https://api.dexscreener.com/token-boosts/top/v1").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )
        router.get("https://api.dexscreener.com/token-profiles/latest/v1").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )
        router.get(url__regex=r"https://api\.dexscreener\.com/latest/dex/tokens/.+").mock(
            return_value=Response(500, json={"error": "Internal Server Error"})
        )

        yield router
