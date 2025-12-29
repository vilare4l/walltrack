"""Tests for DexScreener mock fixtures.

Validates that the mock fixtures correctly intercept API calls
and return deterministic data.

Story 2.4 - AC4: Mock DexScreener for CI
"""

import httpx
import pytest


class TestDexScreenerMockFixture:
    """Tests for DexScreener mock fixture."""

    def test_mock_intercepts_boosted_tokens(self, mock_dexscreener) -> None:
        """
        Given: The mock_dexscreener fixture is active
        When: We call the boosted tokens endpoint
        Then: We get mocked data instead of real API response
        """
        with httpx.Client() as client:
            response = client.get("https://api.dexscreener.com/token-boosts/top/v1")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 3  # We defined 3 mock tokens

        # Verify specific mock data
        addresses = [t["tokenAddress"] for t in data]
        assert "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v" in addresses  # USDC
        assert "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263" in addresses  # BONK

    def test_mock_intercepts_token_profiles(self, mock_dexscreener) -> None:
        """
        Given: The mock_dexscreener fixture is active
        When: We call the token profiles endpoint
        Then: We get mocked data
        """
        with httpx.Client() as client:
            response = client.get("https://api.dexscreener.com/token-profiles/latest/v1")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2  # We defined 2 mock profiles

    def test_mock_intercepts_token_pairs(self, mock_dexscreener) -> None:
        """
        Given: The mock_dexscreener fixture is active
        When: We call the token pairs endpoint for a specific address
        Then: We get mocked pairs data with correct token info
        """
        # Test with USDC address
        address = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        with httpx.Client() as client:
            response = client.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}")

        assert response.status_code == 200
        data = response.json()
        assert "pairs" in data
        assert len(data["pairs"]) > 0

        # Verify the token info was substituted correctly
        pair = data["pairs"][0]
        assert pair["baseToken"]["address"] == address
        assert pair["baseToken"]["symbol"] == "USDC"
        assert pair["priceUsd"] == "1.00"

    def test_mock_handles_unknown_token(self, mock_dexscreener) -> None:
        """
        Given: The mock_dexscreener fixture is active
        When: We call token pairs for an unknown address
        Then: We get default mock data
        """
        address = "UnknownToken12345678901234567890123456789012"
        with httpx.Client() as client:
            response = client.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}")

        assert response.status_code == 200
        data = response.json()
        pair = data["pairs"][0]
        assert pair["baseToken"]["symbol"] == "???"
        assert pair["baseToken"]["name"] == "Unknown Token"

    def test_mock_is_deterministic(self, mock_dexscreener) -> None:
        """
        Given: The mock_dexscreener fixture is active
        When: We call the same endpoint multiple times
        Then: We get the same response every time
        """
        responses = []
        for _ in range(3):
            with httpx.Client() as client:
                response = client.get("https://api.dexscreener.com/token-boosts/top/v1")
            responses.append(response.json())

        # All responses should be identical
        assert responses[0] == responses[1] == responses[2]


class TestDexScreenerEmptyMock:
    """Tests for empty DexScreener mock fixture."""

    def test_empty_mock_returns_no_tokens(self, mock_dexscreener_empty) -> None:
        """
        Given: The mock_dexscreener_empty fixture is active
        When: We call boosted tokens endpoint
        Then: We get an empty list
        """
        with httpx.Client() as client:
            response = client.get("https://api.dexscreener.com/token-boosts/top/v1")

        assert response.status_code == 200
        data = response.json()
        assert data == []


class TestDexScreenerErrorMock:
    """Tests for error DexScreener mock fixture."""

    def test_error_mock_returns_500(self, mock_dexscreener_error) -> None:
        """
        Given: The mock_dexscreener_error fixture is active
        When: We call any endpoint
        Then: We get a 500 error
        """
        with httpx.Client() as client:
            response = client.get("https://api.dexscreener.com/token-boosts/top/v1")

        assert response.status_code == 500
        assert "error" in response.json()
