"""Integration tests for token discovery workflow.

Tests the complete token discovery flow:
1. DexScreener API fetch (mocked)
2. Token enrichment
3. Database storage
4. Result verification
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.discovery.token_discovery import TokenDiscoveryService
from walltrack.data.models.token import Token
from walltrack.services.dexscreener.models import (
    BaseTokenInfo,
    BoostedToken,
    LiquidityInfo,
    TokenPair,
    TokenProfile,
    VolumeInfo,
)


class TestTokenDiscoveryIntegration:
    """Integration tests for complete token discovery workflow."""

    @pytest.fixture
    def mock_dex_client(self) -> AsyncMock:
        """Create mock DexScreener client with realistic responses."""
        client = AsyncMock()

        # Boosted tokens (Solana only)
        client.fetch_boosted_tokens.return_value = [
            BoostedToken(chainId="solana", tokenAddress="token1_mint_address"),
            BoostedToken(chainId="solana", tokenAddress="token2_mint_address"),
        ]

        # Token profiles (Solana only)
        client.fetch_token_profiles.return_value = [
            TokenProfile(chainId="solana", tokenAddress="token3_mint_address"),
            TokenProfile(
                chainId="solana", tokenAddress="token1_mint_address"
            ),  # Duplicate
        ]

        # Pair data for enrichment
        def mock_fetch_by_address(address: str):
            if address == "token1_mint_address":
                return [
                    TokenPair(
                        chainId="solana",
                        dexId="raydium",
                        pairAddress="pair1",
                        baseToken=BaseTokenInfo(
                            address=address,
                            name="Token One",
                            symbol="TK1",
                        ),
                        priceUsd="1.50",
                        marketCap=1000000,
                        volume=VolumeInfo(h24=50000),
                        liquidity=LiquidityInfo(usd=25000),
                        pairCreatedAt=1700000000000,
                    )
                ]
            elif address == "token2_mint_address":
                return [
                    TokenPair(
                        chainId="solana",
                        dexId="orca",
                        pairAddress="pair2",
                        baseToken=BaseTokenInfo(
                            address=address,
                            name="Token Two",
                            symbol="TK2",
                        ),
                        priceUsd="0.001",
                        marketCap=50000,
                        volume=VolumeInfo(h24=10000),
                        liquidity=LiquidityInfo(usd=5000),
                    )
                ]
            return None  # token3 has no pairs

        client.fetch_token_by_address.side_effect = mock_fetch_by_address
        client.close = AsyncMock()

        return client

    @pytest.fixture
    def mock_supabase_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_discovery_fetches_and_stores_tokens(
        self, mock_dex_client: AsyncMock, mock_supabase_client: MagicMock
    ):
        """
        Given: DexScreener API returns tokens from boosted and profiles endpoints
        When: run_discovery() is called
        Then: Unique tokens are enriched and stored in database
        """
        stored_tokens: list[Token] = []

        async def mock_upsert(tokens: list[Token]) -> tuple[int, int]:
            stored_tokens.extend(tokens)
            return (len(tokens), 0)

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = mock_upsert
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase_client, mock_dex_client)
            result = await service.run_discovery()

            # Verify API calls
            mock_dex_client.fetch_boosted_tokens.assert_called_once()
            mock_dex_client.fetch_token_profiles.assert_called_once()

            # Verify deduplication (4 raw tokens -> 3 unique)
            assert result.tokens_found == 3
            assert result.new_tokens == 3
            assert result.status == "complete"

            # Verify tokens stored
            assert len(stored_tokens) == 3
            mints = [t.mint for t in stored_tokens]
            assert "token1_mint_address" in mints
            assert "token2_mint_address" in mints
            assert "token3_mint_address" in mints

    @pytest.mark.asyncio
    async def test_discovery_enriches_tokens_with_market_data(
        self, mock_dex_client: AsyncMock, mock_supabase_client: MagicMock
    ):
        """
        Given: DexScreener returns pair data for tokens
        When: run_discovery() is called
        Then: Tokens are enriched with price, volume, and liquidity
        """
        stored_tokens: list[Token] = []

        async def mock_upsert(tokens: list[Token]) -> tuple[int, int]:
            stored_tokens.extend(tokens)
            return (len(tokens), 0)

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = mock_upsert
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase_client, mock_dex_client)
            await service.run_discovery()

            # Find enriched token1
            token1 = next(
                (t for t in stored_tokens if t.mint == "token1_mint_address"), None
            )
            assert token1 is not None
            assert token1.symbol == "TK1"
            assert token1.name == "Token One"
            assert token1.price_usd == 1.50
            assert token1.market_cap == 1000000
            assert token1.volume_24h == 50000
            assert token1.liquidity_usd == 25000
            assert token1.age_minutes is not None

            # Find token3 (no pairs - basic data only)
            token3 = next(
                (t for t in stored_tokens if t.mint == "token3_mint_address"), None
            )
            assert token3 is not None
            assert token3.symbol is None
            assert token3.price_usd is None

    @pytest.mark.asyncio
    async def test_discovery_handles_empty_results(
        self, mock_supabase_client: MagicMock
    ):
        """
        Given: DexScreener returns no tokens
        When: run_discovery() is called
        Then: Returns no_results status without errors
        """
        empty_dex_client = AsyncMock()
        empty_dex_client.fetch_boosted_tokens.return_value = []
        empty_dex_client.fetch_token_profiles.return_value = []

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            mock_repo.upsert_tokens = AsyncMock(return_value=(0, 0))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase_client, empty_dex_client)
            result = await service.run_discovery()

            assert result.tokens_found == 0
            assert result.status == "no_results"
            mock_repo.upsert_tokens.assert_not_called()

    @pytest.mark.asyncio
    async def test_discovery_handles_api_errors_gracefully(
        self, mock_supabase_client: MagicMock
    ):
        """
        Given: DexScreener API fails
        When: run_discovery() is called
        Then: Returns error status with message (no exception raised)
        """
        failing_dex_client = AsyncMock()
        failing_dex_client.fetch_boosted_tokens.side_effect = Exception(
            "Connection refused"
        )

        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase_client, failing_dex_client)
            result = await service.run_discovery()

            assert result.status == "error"
            assert "Connection refused" in result.error_message
            assert result.tokens_found == 0

    @pytest.mark.asyncio
    async def test_discovery_reports_updated_tokens(
        self, mock_dex_client: AsyncMock, mock_supabase_client: MagicMock
    ):
        """
        Given: Some tokens already exist in database
        When: run_discovery() is called
        Then: Reports both new and updated token counts
        """
        with patch(
            "walltrack.core.discovery.token_discovery.TokenRepository"
        ) as MockRepo:
            mock_repo = MagicMock()
            # Simulate 1 new, 2 updated
            mock_repo.upsert_tokens = AsyncMock(return_value=(1, 2))
            MockRepo.return_value = mock_repo

            service = TokenDiscoveryService(mock_supabase_client, mock_dex_client)
            result = await service.run_discovery()

            assert result.new_tokens == 1
            assert result.updated_tokens == 2
            assert result.tokens_found == 3
