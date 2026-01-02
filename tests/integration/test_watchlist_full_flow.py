"""Integration tests for watchlist full flow.

Tests Story 3.5 - Auto Watchlist Management:
- Wallet profiling triggers watchlist evaluation
- WatchlistEvaluator scoring logic
- Dual database updates (Supabase + Neo4j)
- Manual override operations
- Blacklist functionality
"""

from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.wallets.watchlist import WatchlistEvaluator
from walltrack.data.models.wallet import Wallet, WalletStatus, WatchlistDecision
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


@pytest.fixture
def sample_wallet_high_performer():
    """Sample wallet with high performance metrics (should be watchlisted)."""
    return Wallet(
        wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Valid Solana address
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Required field
        score=0.85,  # 0.0-1.0 range
        win_rate=75.5,  # 75.5% - above 70% threshold
        pnl_total=12.5,  # 12.5 SOL - above 5 SOL threshold
        entry_delay_seconds=3600,
        total_trades=25,  # 25 trades - above 10 threshold
        metrics_confidence="high",
        discovery_date=datetime.now(UTC),
        position_size_avg=Decimal("2.5"),
        position_size_style="medium",
        hold_duration_avg=7200,
        hold_duration_style="day_trader",
        rolling_win_rate=Decimal("72.0"),  # Win rate over recent 20 trades
        consecutive_losses=2,
        decay_status="ok",  # Must be 'ok', 'flagged', 'downgraded', or 'dormant'
        wallet_status=WalletStatus.PROFILED,
        watchlist_score=None,
        watchlist_reason=None,
        manual_override=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_wallet_low_performer():
    """Sample wallet with low performance metrics (should be ignored)."""
    return Wallet(
        wallet_address="3kVK9DwSDkVvMyuRGPKGqbYMFBTrr1zpXgb3sPXfMnJy",  # Valid Solana address
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # Required field
        score=0.45,  # 0.0-1.0 range
        win_rate=45.0,  # 45% - below 70% threshold
        pnl_total=2.5,  # 2.5 SOL - below 5 SOL threshold
        entry_delay_seconds=3600,
        total_trades=8,  # 8 trades - below 10 threshold
        metrics_confidence="medium",
        discovery_date=datetime.now(UTC),
        position_size_avg=Decimal("1.2"),
        position_size_style="small",
        hold_duration_avg=3600,
        hold_duration_style="scalper",
        rolling_win_rate=Decimal("42.0"),  # Win rate over recent 20 trades
        consecutive_losses=5,
        decay_status="ok",  # Must be 'ok', 'flagged', 'downgraded', or 'dormant'
        wallet_status=WalletStatus.PROFILED,
        watchlist_score=None,
        watchlist_reason=None,
        manual_override=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def mock_config_repo():
    """Mock ConfigRepository with default watchlist criteria and scoring weights."""
    mock_repo = MagicMock(spec=ConfigRepository)

    async def mock_get_watchlist_criteria():
        return {
            "min_winrate": 0.70,
            "min_pnl": 5.0,
            "min_trades": 10,
            "max_decay_score": 0.30,
        }

    async def mock_get_scoring_weights():
        return {
            "weight_win_rate": 0.40,
            "weight_pnl": 0.30,
            "weight_trades": 0.20,
            "weight_decay": 0.10,
        }

    mock_repo.get_watchlist_criteria = mock_get_watchlist_criteria
    mock_repo.get_scoring_weights = mock_get_scoring_weights
    return mock_repo


class TestWatchlistFullFlowIntegration:
    """Integration tests for complete watchlist flow."""

    @pytest.mark.asyncio
    async def test_watchlist_evaluation_high_performer(
        self,
        sample_wallet_high_performer,
        mock_config_repo,
    ):
        """Test watchlist evaluation for high-performing wallet."""
        # Arrange
        evaluator = WatchlistEvaluator(mock_config_repo)

        # Act
        decision = await evaluator.evaluate_wallet(sample_wallet_high_performer)

        # Assert
        assert decision.status == WalletStatus.WATCHLISTED
        assert decision.score > Decimal("0.50")  # Should have high composite score
        assert "criteria" in decision.reason.lower()  # "Meets all criteria"
        assert isinstance(decision.timestamp, datetime)

    @pytest.mark.asyncio
    async def test_watchlist_evaluation_low_performer(
        self,
        sample_wallet_low_performer,
        mock_config_repo,
    ):
        """Test watchlist evaluation for low-performing wallet."""
        # Arrange
        evaluator = WatchlistEvaluator(mock_config_repo)

        # Act
        decision = await evaluator.evaluate_wallet(sample_wallet_low_performer)

        # Assert
        assert decision.status == WalletStatus.IGNORED
        assert decision.score >= Decimal("0.0000")  # Score is calculated even for ignored wallets
        assert "failed" in decision.reason.lower()  # "Failed: win_rate < 0.7, ..."

    @pytest.mark.asyncio
    @patch("walltrack.data.neo4j.queries.wallet.update_wallet_watchlist_status")
    async def test_wallet_repository_update_watchlist_status(
        self,
        mock_neo4j_update,
        sample_wallet_high_performer,
    ):
        """Test WalletRepository.update_watchlist_status with dual database sync."""
        # Arrange - Mock Neo4j update as coroutine
        async def mock_neo4j_coro(*args, **kwargs):
            return {
                "wallet_address": sample_wallet_high_performer.wallet_address,
                "wallet_status": "watchlisted",
                "watchlist_score": 0.8523,
            }

        mock_neo4j_update.side_effect = mock_neo4j_coro

        # Mock Supabase client with proper async chain
        mock_execute_result = MagicMock(data=[])
        mock_eq = MagicMock()
        mock_eq.execute = AsyncMock(return_value=mock_execute_result)

        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=mock_eq)

        mock_table = MagicMock()
        mock_table.update = MagicMock(return_value=mock_update)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        mock_supabase = MagicMock()
        mock_supabase.client = mock_client

        wallet_repo = WalletRepository(mock_supabase)

        decision = WatchlistDecision(
            status=WalletStatus.WATCHLISTED,
            score=Decimal("0.8523"),
            reason="Meets all criteria: win_rate 75.5%, pnl 12.5 SOL, trades 25, decay 15%",
            timestamp=datetime.now(UTC),
        )

        # Act
        await wallet_repo.update_watchlist_status(
            wallet_address=sample_wallet_high_performer.wallet_address,
            decision=decision,
            manual=False,
        )

        # Assert - Verify Supabase update called
        mock_client.table.assert_called_with("wallets")
        update_call_args = mock_table.update.call_args[0][0]
        assert update_call_args["wallet_status"] == "watchlisted"
        assert update_call_args["watchlist_score"] == 0.8523
        assert update_call_args["manual_override"] is False

        # Assert - Verify Neo4j update called
        mock_neo4j_update.assert_called_once_with(
            wallet_address=sample_wallet_high_performer.wallet_address,
            status="watchlisted",
            score=0.8523,
        )

    @pytest.mark.asyncio
    @patch("walltrack.data.neo4j.queries.wallet.update_wallet_watchlist_status")
    async def test_manual_override_add_to_watchlist(
        self,
        mock_neo4j_update,
        sample_wallet_low_performer,
    ):
        """Test manual override: add low performer to watchlist."""
        # Arrange - Mock Neo4j update as coroutine
        async def mock_neo4j_coro(*args, **kwargs):
            return {
                "wallet_address": sample_wallet_low_performer.wallet_address,
                "wallet_status": "watchlisted",
                "watchlist_score": 1.0,
            }

        mock_neo4j_update.side_effect = mock_neo4j_coro

        # Mock Supabase client
        mock_execute_result = MagicMock(data=[])
        mock_eq = MagicMock()
        mock_eq.execute = AsyncMock(return_value=mock_execute_result)

        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=mock_eq)

        mock_table = MagicMock()
        mock_table.update = MagicMock(return_value=mock_update)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        mock_supabase = MagicMock()
        mock_supabase.client = mock_client

        wallet_repo = WalletRepository(mock_supabase)

        decision = WatchlistDecision(
            status=WalletStatus.WATCHLISTED,
            score=Decimal("1.0000"),
            reason="Manually added by operator",
            timestamp=datetime.now(UTC),
        )

        # Act
        await wallet_repo.update_watchlist_status(
            wallet_address=sample_wallet_low_performer.wallet_address,
            decision=decision,
            manual=True,  # Manual override
        )

        # Assert - Verify manual_override flag set
        update_call_args = mock_table.update.call_args[0][0]
        assert update_call_args["manual_override"] is True
        assert update_call_args["wallet_status"] == "watchlisted"

    @pytest.mark.asyncio
    @patch("walltrack.data.neo4j.queries.wallet.update_wallet_watchlist_status")
    async def test_blacklist_wallet(
        self,
        mock_neo4j_update,
        sample_wallet_high_performer,
    ):
        """Test blacklist operation."""
        # Arrange - Mock Neo4j update as coroutine
        async def mock_neo4j_coro(*args, **kwargs):
            return {
                "wallet_address": sample_wallet_high_performer.wallet_address,
                "wallet_status": "blacklisted",
                "watchlist_score": 0.0,
            }

        mock_neo4j_update.side_effect = mock_neo4j_coro

        # Mock Supabase client
        mock_execute_result = MagicMock(data=[])
        mock_eq = MagicMock()
        mock_eq.execute = AsyncMock(return_value=mock_execute_result)

        mock_update = MagicMock()
        mock_update.eq = MagicMock(return_value=mock_eq)

        mock_table = MagicMock()
        mock_table.update = MagicMock(return_value=mock_update)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        mock_supabase = MagicMock()
        mock_supabase.client = mock_client

        wallet_repo = WalletRepository(mock_supabase)

        # Act
        await wallet_repo.blacklist_wallet(
            wallet_address=sample_wallet_high_performer.wallet_address,
            reason="Suspected bot wallet",
        )

        # Assert
        update_call_args = mock_table.update.call_args[0][0]
        assert update_call_args["wallet_status"] == "blacklisted"
        assert update_call_args["manual_override"] is True
        assert "Blacklisted: Suspected bot wallet" in update_call_args["watchlist_reason"]

        # Assert Neo4j sync
        mock_neo4j_update.assert_called_once_with(
            wallet_address=sample_wallet_high_performer.wallet_address,
            status="blacklisted",
            score=0.0,
        )

    @pytest.mark.asyncio
    async def test_get_wallets_by_status(self):
        """Test filtering wallets by status."""
        # Arrange
        mock_result = MagicMock()
        mock_result.data = [
            {
                "wallet_address": "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                "token_source": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "wallet_status": "watchlisted",
                "watchlist_score": "0.8500",
                "score": "0.85",
                "win_rate": "75.0",
                "pnl_total": "10.0",
                "entry_delay_seconds": 3600,
                "total_trades": 20,
                "metrics_confidence": "high",
                "discovery_date": datetime.now(UTC).isoformat(),
                "position_size_avg": "2.0",
                "position_size_style": "medium",
                "hold_duration_avg": 7200,
                "hold_duration_style": "day_trader",
                "rolling_win_rate": "72.0",
                "consecutive_losses": 2,
                "decay_status": "ok",
                "watchlist_reason": "Meets criteria",
                "manual_override": False,
                "created_at": datetime.now(UTC).isoformat(),
                "updated_at": datetime.now(UTC).isoformat(),
            }
        ]

        # Mock Supabase client chain
        mock_order = MagicMock()
        mock_order.execute = AsyncMock(return_value=mock_result)

        mock_eq = MagicMock()
        mock_eq.order = MagicMock(return_value=mock_order)

        mock_select = MagicMock()
        mock_select.eq = MagicMock(return_value=mock_eq)

        mock_table = MagicMock()
        mock_table.select = MagicMock(return_value=mock_select)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        mock_supabase = MagicMock()
        mock_supabase.client = mock_client

        wallet_repo = WalletRepository(mock_supabase)

        # Act
        wallets = await wallet_repo.get_wallets_by_status(WalletStatus.WATCHLISTED)

        # Assert
        assert len(wallets) == 1
        assert wallets[0].wallet_status == WalletStatus.WATCHLISTED
        assert wallets[0].wallet_address == "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    @pytest.mark.asyncio
    async def test_get_watchlist_count(self):
        """Test getting count of watchlisted wallets."""
        # Arrange
        mock_result = MagicMock()
        mock_result.count = 42

        # Mock Supabase client chain
        mock_eq = MagicMock()
        mock_eq.execute = AsyncMock(return_value=mock_result)

        mock_select = MagicMock()
        mock_select.eq = MagicMock(return_value=mock_eq)

        mock_table = MagicMock()
        mock_table.select = MagicMock(return_value=mock_select)

        mock_client = MagicMock()
        mock_client.table = MagicMock(return_value=mock_table)

        mock_supabase = MagicMock()
        mock_supabase.client = mock_client

        wallet_repo = WalletRepository(mock_supabase)

        # Act
        count = await wallet_repo.get_watchlist_count()

        # Assert
        assert count == 42
