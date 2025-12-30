"""Integration tests for wallet performance analysis.

Tests the full orchestration flow:
- HeliusClient → TransactionParser → PerformanceCalculator → WalletRepository
- Database updates (Supabase + Neo4j)
- Error handling and recovery
"""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.analysis import analyze_wallet_performance
from walltrack.data.models.wallet import PerformanceMetrics
from walltrack.services.helius.client import HeliusClient


@pytest.fixture
def sample_helius_response():
    """Sample Helius API response with SWAP transactions."""
    return [
        {
            "signature": "5j7s8k2dL3FqYx9Kw1nM4pR6tV8uZ2cH5aB7eG9jL3mN",
            "timestamp": 1703001234,
            "type": "SWAP",
            "nativeTransfers": [
                {
                    "fromUserAccount": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                    "toUserAccount": "TokenProgramAddress",
                    "amount": 1000000000,  # 1 SOL in lamports
                }
            ],
            "tokenTransfers": [
                {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "fromUserAccount": "TokenProgramAddress",
                    "toUserAccount": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                    "tokenAmount": 1000000,
                }
            ],
        },
        {
            "signature": "8m2p5n9rK4GtZx2Lw8qN7sR9vT3uY6dJ4bC5eH8kM2oP",
            "timestamp": 1703005678,
            "type": "SWAP",
            "nativeTransfers": [
                {
                    "fromUserAccount": "TokenProgramAddress",
                    "toUserAccount": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                    "amount": 1500000000,  # 1.5 SOL in lamports
                }
            ],
            "tokenTransfers": [
                {
                    "mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                    "fromUserAccount": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                    "toUserAccount": "TokenProgramAddress",
                    "tokenAmount": 1000000,
                }
            ],
        },
    ]


@pytest.fixture
def wallet_address():
    """Sample wallet address for tests."""
    return "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"


@pytest.fixture
def helius_api_key():
    """Get Helius API key from environment (skip if not set)."""
    api_key = os.getenv("HELIUS_API_KEY")
    if not api_key:
        pytest.skip("HELIUS_API_KEY not set")
    return api_key


class TestWalletPerformanceAnalysisIntegration:
    """Integration tests for wallet performance analysis orchestration."""

    @pytest.mark.asyncio
    async def test_analyze_wallet_performance_with_mocked_helius(
        self, wallet_address, sample_helius_response
    ):
        """Test full analysis flow with mocked Helius API."""
        # Arrange - Mock Helius client
        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(
            return_value=sample_helius_response
        )

        # Mock wallet repository
        mock_wallet_repo = MagicMock()
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        # Mock Neo4j update
        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.return_value = AsyncMock()

            # Act
            metrics = await analyze_wallet_performance(
                wallet_address=wallet_address,
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
            )

            # Assert - Verify metrics calculated correctly
            assert isinstance(metrics, PerformanceMetrics)
            assert metrics.win_rate == 100.0  # 1 profitable trade
            assert metrics.pnl_total == 0.5  # 1.5 - 1.0 SOL
            assert metrics.total_trades == 1
            assert metrics.confidence == "low"
            assert metrics.entry_delay_seconds == 0  # No launch times provided

            # Verify Helius client was called
            mock_helius_client.get_wallet_transactions.assert_called_once_with(
                wallet_address=wallet_address, limit=1000, tx_type="SWAP"
            )

            # Verify repository update was called
            mock_wallet_repo.update_performance_metrics.assert_called_once_with(
                wallet_address=wallet_address, metrics=metrics
            )

    @pytest.mark.asyncio
    async def test_analyze_wallet_performance_with_no_transactions(
        self, wallet_address
    ):
        """Test analysis with wallet that has no transactions."""
        # Arrange
        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(return_value=[])

        mock_wallet_repo = MagicMock()
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.return_value = AsyncMock()

            # Act
            metrics = await analyze_wallet_performance(
                wallet_address=wallet_address,
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
            )

            # Assert
            assert metrics.win_rate == 0.0
            assert metrics.pnl_total == 0.0
            assert metrics.total_trades == 0
            assert metrics.confidence == "unknown"

            # Repository should still be updated (with zero metrics)
            mock_wallet_repo.update_performance_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_analyze_wallet_performance_with_token_launch_times(
        self, wallet_address, sample_helius_response
    ):
        """Test analysis with token launch times for entry delay calculation."""
        # Arrange
        token_mint = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        launch_time = datetime.fromtimestamp(1703001234 - 3600)  # 1 hour before first buy

        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(
            return_value=sample_helius_response
        )

        mock_wallet_repo = MagicMock()
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.return_value = AsyncMock()

            # Act
            metrics = await analyze_wallet_performance(
                wallet_address=wallet_address,
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
                token_launch_times={token_mint: launch_time},
            )

            # Assert
            assert metrics.entry_delay_seconds == 3600  # 1 hour delay

    @pytest.mark.asyncio
    async def test_analyze_wallet_performance_helius_error_propagates(
        self, wallet_address
    ):
        """Test that Helius API errors propagate correctly."""
        # Arrange
        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(
            side_effect=Exception("Helius API error")
        )

        mock_wallet_repo = MagicMock()

        # Act & Assert
        with pytest.raises(Exception, match="Helius API error"):
            await analyze_wallet_performance(
                wallet_address=wallet_address,
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
            )

    @pytest.mark.asyncio
    async def test_analyze_wallet_performance_neo4j_error_continues(
        self, wallet_address, sample_helius_response
    ):
        """Test that Neo4j sync errors don't stop Supabase update."""
        # Arrange
        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(
            return_value=sample_helius_response
        )

        mock_wallet_repo = MagicMock()
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        # Mock Neo4j to raise error
        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.side_effect = Exception("Neo4j connection failed")

            # Act - Should NOT raise exception (Neo4j error is logged but not fatal)
            metrics = await analyze_wallet_performance(
                wallet_address=wallet_address,
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
            )

            # Assert - Metrics still calculated and Supabase updated
            assert isinstance(metrics, PerformanceMetrics)
            mock_wallet_repo.update_performance_metrics.assert_called_once()


class TestBulkWalletAnalysis:
    """Integration tests for bulk wallet analysis."""

    @pytest.mark.asyncio
    async def test_analyze_all_wallets_with_multiple_wallets(self):
        """Test analyzing multiple wallets concurrently."""
        # Arrange
        from walltrack.core.analysis import analyze_all_wallets
        from walltrack.data.models.wallet import Wallet

        wallets = [
            Wallet(
                wallet_address=f"Wallet{i}111111111111111111111111111111",
                score=0.8,
                discovery_date=datetime.now(),
                token_source="TokenMintXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            )
            for i in range(3)
        ]

        mock_helius_client = MagicMock(spec=HeliusClient)
        mock_helius_client.get_wallet_transactions = AsyncMock(return_value=[])

        mock_wallet_repo = MagicMock()
        mock_wallet_repo.get_all = AsyncMock(return_value=wallets)
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.return_value = AsyncMock()

            # Act
            results = await analyze_all_wallets(
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
                max_concurrent=2,
            )

            # Assert
            assert len(results) == 3  # All wallets analyzed
            assert mock_wallet_repo.update_performance_metrics.call_count == 3

    @pytest.mark.asyncio
    async def test_analyze_all_wallets_continues_on_individual_failures(self):
        """Test that bulk analysis continues even if some wallets fail."""
        # Arrange
        from walltrack.core.analysis import analyze_all_wallets
        from walltrack.data.models.wallet import Wallet

        wallets = [
            Wallet(
                wallet_address=f"Wallet{i}111111111111111111111111111111",
                score=0.8,
                discovery_date=datetime.now(),
                token_source="TokenMintXXXXXXXXXXXXXXXXXXXXXXXXXXXX",
            )
            for i in range(3)
        ]

        mock_helius_client = MagicMock(spec=HeliusClient)
        # First wallet succeeds, second fails, third succeeds
        mock_helius_client.get_wallet_transactions = AsyncMock(
            side_effect=[[], Exception("API error"), []]
        )

        mock_wallet_repo = MagicMock()
        mock_wallet_repo.get_all = AsyncMock(return_value=wallets)
        mock_wallet_repo.update_performance_metrics = AsyncMock()

        with patch(
            "walltrack.core.analysis.performance_orchestrator.update_neo4j_metrics"
        ) as mock_neo4j:
            mock_neo4j.return_value = AsyncMock()

            # Act
            results = await analyze_all_wallets(
                helius_client=mock_helius_client,
                wallet_repo=mock_wallet_repo,
                max_concurrent=1,  # Sequential to control order
            )

            # Assert - Only 2 succeeded (1st and 3rd)
            assert len(results) == 2
