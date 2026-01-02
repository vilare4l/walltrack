"""Unit tests for behavioral profiler.

Tests for orchestrating behavioral profiling analysis for wallets.
Story 3.3 - Task 6.
"""

from decimal import Decimal

import pytest

from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.core.behavioral.profiler import BehavioralProfile, BehavioralProfiler
from tests.unit.core.behavioral.conftest import (
    VALID_WALLET_ADDRESS,
    VALID_TOKEN_MINT_ABC,
)


class TestBehavioralProfiler:
    """Tests for BehavioralProfiler class."""

    @pytest.mark.asyncio
    async def test_analyze_returns_none_for_insufficient_trades(
        self, mock_rpc_client, mock_config_repo, swap_transaction_factory, mocker
    ):
        """Should return None when wallet has fewer than minimum required trades."""
        # Setup: Wallet with only 4 BUY transactions (below min_trades=5)
        mock_rpc_client.getSignaturesForAddress.return_value = [
            {"signature": "sig1"},
            {"signature": "sig2"},
            {"signature": "sig3"},
            {"signature": "sig4"},
        ]

        transactions = [
            swap_transaction_factory(
                signature=f"sig{i}",
                timestamp=1000 * i,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
                wallet_address=VALID_WALLET_ADDRESS,
            )
            for i in range(1, 5)
        ]

        mock_rpc_client.getTransaction.return_value = {"transaction": {}, "meta": {}}
        mock_config_repo.get_behavioral_min_trades.return_value = 5

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        # Mock the parser.parse() method on the profiler instance
        profiler.parser.parse = mocker.MagicMock(side_effect=transactions)

        result = await profiler.analyze(VALID_WALLET_ADDRESS)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_returns_profile_for_sufficient_trades(
        self, mock_rpc_client, mock_config_repo, swap_transaction_factory, mocker
    ):
        """Should return BehavioralProfile when wallet has sufficient trades."""
        # Setup: Wallet with 10 BUY transactions (meets min_trades)
        mock_rpc_client.getSignaturesForAddress.return_value = [
            {"signature": f"sig{i}"} for i in range(1, 11)
        ]

        transactions = [
            swap_transaction_factory(
                signature=f"sig{i}",
                timestamp=1000 * i,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.5,
                token_amount=100.0,
                wallet_address=VALID_WALLET_ADDRESS,
            )
            for i in range(1, 11)
        ]

        mock_rpc_client.getTransaction.return_value = {"transaction": {}, "meta": {}}

        # Config returns
        mock_config_repo.get_behavioral_min_trades.return_value = 5
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800
        mock_config_repo.get_behavioral_confidence_medium.return_value = 10
        mock_config_repo.get_behavioral_confidence_high.return_value = 20

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        # Mock the parser.parse() method on the profiler instance
        profiler.parser.parse = mocker.MagicMock(side_effect=transactions)

        result = await profiler.analyze(VALID_WALLET_ADDRESS)

        assert result is not None
        assert isinstance(result, BehavioralProfile)
        assert result.wallet_address == VALID_WALLET_ADDRESS
        assert result.total_trades == 10
        assert result.position_size_style == "medium"  # 1.5 SOL is medium

    @pytest.mark.asyncio
    async def test_calculate_confidence_unknown_for_low_trades(
        self, mock_rpc_client, mock_config_repo
    ):
        """Should calculate confidence as 'unknown' when trades < min_trades."""
        mock_config_repo.get_behavioral_min_trades.return_value = 10

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        result = await profiler._calculate_confidence(5)

        assert result == "unknown"

    @pytest.mark.asyncio
    async def test_calculate_confidence_low(self, mock_rpc_client, mock_config_repo):
        """Should calculate confidence as 'low' when trades >= min_trades and < medium."""
        mock_config_repo.get_behavioral_min_trades.return_value = 5
        mock_config_repo.get_behavioral_confidence_medium.return_value = 10
        mock_config_repo.get_behavioral_confidence_high.return_value = 20

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        result = await profiler._calculate_confidence(7)

        assert result == "low"

    @pytest.mark.asyncio
    async def test_calculate_confidence_medium(self, mock_rpc_client, mock_config_repo):
        """Should calculate confidence as 'medium' when trades >= medium and < high."""
        mock_config_repo.get_behavioral_min_trades.return_value = 5
        mock_config_repo.get_behavioral_confidence_medium.return_value = 10
        mock_config_repo.get_behavioral_confidence_high.return_value = 20

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        result = await profiler._calculate_confidence(15)

        assert result == "medium"

    @pytest.mark.asyncio
    async def test_calculate_confidence_high(self, mock_rpc_client, mock_config_repo):
        """Should calculate confidence as 'high' when trades >= high threshold."""
        mock_config_repo.get_behavioral_min_trades.return_value = 5
        mock_config_repo.get_behavioral_confidence_medium.return_value = 10
        mock_config_repo.get_behavioral_confidence_high.return_value = 20

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        result = await profiler._calculate_confidence(50)

        assert result == "high"

    @pytest.mark.asyncio
    async def test_analyze_fetches_rpc_transactions(
        self, mock_rpc_client, mock_config_repo, swap_transaction_factory, mocker
    ):
        """Should fetch transaction signatures and full transactions via RPC."""
        mock_rpc_client.getSignaturesForAddress.return_value = [
            {"signature": "sig1"},
            {"signature": "sig2"},
        ]

        mock_rpc_client.getTransaction.return_value = {"transaction": {}, "meta": {}}

        # Config returns
        mock_config_repo.get_behavioral_min_trades.return_value = 1
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800
        mock_config_repo.get_behavioral_confidence_medium.return_value = 10
        mock_config_repo.get_behavioral_confidence_high.return_value = 20

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        # Mock the parser to return a valid transaction each time
        profiler.parser.parse = mocker.MagicMock(
            return_value=swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
                wallet_address=VALID_WALLET_ADDRESS,
            )
        )

        await profiler.analyze(VALID_WALLET_ADDRESS)

        # Verify RPC calls
        mock_rpc_client.getSignaturesForAddress.assert_called_once_with(
            address=VALID_WALLET_ADDRESS, limit=100
        )
        assert mock_rpc_client.getTransaction.call_count == 2

    @pytest.mark.asyncio
    async def test_analyze_handles_rpc_fetch_error(
        self, mock_rpc_client, mock_config_repo
    ):
        """Should raise exception when RPC fetch fails."""
        mock_rpc_client.getSignaturesForAddress.side_effect = Exception("RPC error")

        profiler = BehavioralProfiler(mock_rpc_client, mock_config_repo)

        with pytest.raises(Exception, match="RPC error"):
            await profiler.analyze("wallet1")


@pytest.fixture
def mock_rpc_client(mocker):
    """Mock SolanaRPCClient for testing."""
    from walltrack.services.solana.rpc_client import SolanaRPCClient

    mock = mocker.AsyncMock(spec=SolanaRPCClient)
    return mock


@pytest.fixture
def mock_config_repo(mocker):
    """Mock ConfigRepository for testing."""
    from walltrack.data.supabase.repositories.config_repo import ConfigRepository

    mock = mocker.AsyncMock(spec=ConfigRepository)
    return mock
