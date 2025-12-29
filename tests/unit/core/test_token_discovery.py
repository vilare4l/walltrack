"""Unit tests for Token Discovery Service.

Tests cover:
- Full discovery workflow with boosted + profiles
- Deduplication of token addresses
- Token enrichment with pair data
- Error handling and graceful degradation
- Empty results handling
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.core.discovery.token_discovery import TokenDiscoveryService
from walltrack.data.models.token import Token, TokenDiscoveryResult
from walltrack.services.dexscreener.models import (
    BaseTokenInfo,
    BoostedToken,
    LiquidityInfo,
    TokenPair,
    TokenProfile,
    VolumeInfo,
)


class TestTokenDiscoveryServiceRunDiscovery:
    """Tests for run_discovery method."""

    @pytest.mark.asyncio
    async def test_discovery_combines_boosted_and_profiles(self):
        """Should combine tokens from both boosted and profiles endpoints."""
        # Arrange
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="addr1"),
            BoostedToken(chainId="solana", tokenAddress="addr2"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = [
            TokenProfile(chainId="solana", tokenAddress="addr3"),
        ]
        mock_dex_client.fetch_token_by_address.return_value = None

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(3, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            # Assert - 3 unique addresses discovered
            assert result.tokens_found == 3
            assert result.new_tokens == 3
            assert result.status == "complete"
            mock_repo.upsert_tokens.assert_called_once()

    @pytest.mark.asyncio
    async def test_discovery_deduplicates_addresses(self):
        """Should deduplicate addresses appearing in both endpoints."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        # Same address in both boosted and profiles
        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="duplicate_addr"),
            BoostedToken(chainId="solana", tokenAddress="unique_boosted"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = [
            TokenProfile(chainId="solana", tokenAddress="duplicate_addr"),
            TokenProfile(chainId="solana", tokenAddress="unique_profile"),
        ]
        mock_dex_client.fetch_token_by_address.return_value = None

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(3, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            # Assert - only 3 unique addresses, not 4
            assert result.tokens_found == 3
            upsert_call_args = mock_repo.upsert_tokens.call_args[0][0]
            addresses = [t.mint for t in upsert_call_args]
            assert len(addresses) == 3
            assert "duplicate_addr" in addresses
            assert "unique_boosted" in addresses
            assert "unique_profile" in addresses

    @pytest.mark.asyncio
    async def test_discovery_returns_no_results_when_empty(self):
        """Should return no_results status when no tokens found."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = []
        mock_dex_client.fetch_token_profiles.return_value = []

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            assert result.tokens_found == 0
            assert result.status == "no_results"
            mock_repo.upsert_tokens.assert_not_called()

    @pytest.mark.asyncio
    async def test_discovery_handles_api_error_gracefully(self):
        """Should return error status on API failure."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.side_effect = Exception("API down")

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            assert result.status == "error"
            assert result.tokens_found == 0
            assert "API down" in result.error_message

    @pytest.mark.asyncio
    async def test_discovery_returns_updated_count(self):
        """Should report updated tokens count from repository."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="existing_token"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []
        mock_dex_client.fetch_token_by_address.return_value = None

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            # 0 new, 1 updated
            mock_repo.upsert_tokens = AsyncMock(return_value=(0, 1))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            assert result.tokens_found == 1
            assert result.new_tokens == 0
            assert result.updated_tokens == 1

    @pytest.mark.asyncio
    async def test_discovery_handles_database_error_gracefully(self):
        """Should return error status on database failure."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="token1"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []
        mock_dex_client.fetch_token_by_address.return_value = None

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(
                side_effect=Exception("Database connection failed")
            )
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            assert result.status == "error"
            assert result.tokens_found == 0
            assert "Database connection failed" in result.error_message


class TestTokenDiscoveryServiceEnrichment:
    """Tests for token enrichment with pair data."""

    @pytest.mark.asyncio
    async def test_enrichment_adds_market_data(self):
        """Should enrich tokens with price, volume, and liquidity."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="rich_token"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []

        # Return rich pair data for enrichment
        mock_pair = TokenPair(
            chainId="solana",
            dexId="raydium",
            pairAddress="pair123",
            baseToken=BaseTokenInfo(
                address="rich_token",
                name="Rich Token",
                symbol="RICH",
            ),
            priceUsd="1.50",
            marketCap=1000000,
            volume=VolumeInfo(h24=50000),
            liquidity=LiquidityInfo(usd=25000),
            pairCreatedAt=1700000000000,  # Timestamp in ms
        )
        mock_dex_client.fetch_token_by_address.return_value = [mock_pair]

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(1, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            await service.run_discovery()

            # Check the token passed to upsert
            upsert_call = mock_repo.upsert_tokens.call_args[0][0]
            enriched_token = upsert_call[0]

            assert enriched_token.mint == "rich_token"
            assert enriched_token.symbol == "RICH"
            assert enriched_token.name == "Rich Token"
            assert enriched_token.price_usd == 1.50
            assert enriched_token.market_cap == 1000000
            assert enriched_token.volume_24h == 50000
            assert enriched_token.liquidity_usd == 25000
            assert enriched_token.age_minutes is not None

    @pytest.mark.asyncio
    async def test_enrichment_handles_no_pairs(self):
        """Should create basic token when no pairs found."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="no_pairs_token"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []
        mock_dex_client.fetch_token_by_address.return_value = None

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(1, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            await service.run_discovery()

            upsert_call = mock_repo.upsert_tokens.call_args[0][0]
            basic_token = upsert_call[0]

            assert basic_token.mint == "no_pairs_token"
            assert basic_token.symbol is None
            assert basic_token.price_usd is None

    @pytest.mark.asyncio
    async def test_enrichment_handles_empty_pairs_list(self):
        """Should create basic token when pairs list is empty."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="empty_pairs_token"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []
        mock_dex_client.fetch_token_by_address.return_value = []  # Empty list

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(1, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            await service.run_discovery()

            upsert_call = mock_repo.upsert_tokens.call_args[0][0]
            basic_token = upsert_call[0]

            assert basic_token.mint == "empty_pairs_token"
            assert basic_token.symbol is None

    @pytest.mark.asyncio
    async def test_enrichment_continues_on_single_token_error(self):
        """Should continue discovery if one token enrichment fails."""
        mock_supabase = MagicMock()
        mock_dex_client = AsyncMock()

        mock_dex_client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="good_token"),
            BoostedToken(chainId="solana", tokenAddress="bad_token"),
        ]
        mock_dex_client.fetch_token_profiles.return_value = []

        # First call succeeds, second raises
        def mock_fetch_by_address(address):
            if address == "bad_token":
                raise Exception("Enrichment failed")
            return None

        mock_dex_client.fetch_token_by_address.side_effect = mock_fetch_by_address

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(2, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase, mock_dex_client)
            result = await service.run_discovery()

            # Both tokens should be saved (one with just address)
            assert result.tokens_found == 2
            assert result.status == "complete"


class TestTokenDiscoveryServiceInitialization:
    """Tests for service initialization."""

    def test_init_creates_repository(self):
        """Should create TokenRepository with supabase client."""
        mock_supabase = MagicMock()
        mock_dex_client = MagicMock()

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            service = TokenDiscoveryService(mock_supabase, mock_dex_client)

            MockRepo.assert_called_once_with(mock_supabase)
            assert service._dex_client == mock_dex_client
