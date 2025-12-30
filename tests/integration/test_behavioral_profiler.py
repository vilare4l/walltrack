"""Integration tests for behavioral profiler orchestration.

Tests the full behavioral profiling pipeline with mocked external dependencies.
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from walltrack.core.behavioral.profiler import BehavioralProfile, BehavioralProfiler
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.services.helius.client import HeliusClient


@pytest.fixture
def mock_helius_client():
    """Create mocked HeliusClient for testing."""
    return AsyncMock(spec=HeliusClient)


@pytest.fixture
def mock_config():
    """Create mocked ConfigRepository with default thresholds."""
    config = AsyncMock(spec=ConfigRepository)

    # Position sizing thresholds
    config.get_position_size_small_max.return_value = 1.0
    config.get_position_size_medium_max.return_value = 5.0

    # Hold duration thresholds (in seconds)
    config.get_hold_duration_scalper_max.return_value = 3600  # 1 hour
    config.get_hold_duration_day_trader_max.return_value = 86400  # 24 hours
    config.get_hold_duration_swing_trader_max.return_value = 604800  # 7 days

    # Confidence thresholds
    config.get_behavioral_min_trades.return_value = 10
    config.get_behavioral_confidence_medium.return_value = 10
    config.get_behavioral_confidence_high.return_value = 50

    return config


@pytest.fixture
def sample_transactions_scalper():
    """Create sample transactions for a scalper profile (short holds, small positions)."""
    return [
        # BUY at t=1000, 0.5 SOL
        SwapTransaction(
            signature="sig1",
            timestamp=1000,
            tx_type=TransactionType.BUY,
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            sol_amount=0.5,
            token_amount=1000000,
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ),
        # SELL at t=2000 (1000s hold = 16 minutes)
        SwapTransaction(
            signature="sig2",
            timestamp=2000,
            tx_type=TransactionType.SELL,
            token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            sol_amount=0.6,
            token_amount=1000000,
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ),
        # BUY at t=3000, 0.8 SOL
        SwapTransaction(
            signature="sig3",
            timestamp=3000,
            tx_type=TransactionType.BUY,
            token_mint="DifferentTokenMintAddress32Characters",
            sol_amount=0.8,
            token_amount=2000000,
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ),
        # SELL at t=4500 (1500s hold = 25 minutes)
        SwapTransaction(
            signature="sig4",
            timestamp=4500,
            tx_type=TransactionType.SELL,
            token_mint="DifferentTokenMintAddress32Characters",
            sol_amount=0.9,
            token_amount=2000000,
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        ),
    ]


@pytest.fixture
def sample_transactions_day_trader():
    """Create sample transactions for a day trader profile (medium holds, medium positions)."""
    transactions = []

    # Valid base58 token mints (32-44 characters, no 0, O, I, l)
    token_mints = [
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
        "So11111111111111111111111111111111111111112",
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
        "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",
        "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",
        "AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3",
        "2FPyTwcZLUg1MDrwsyoP4D6s1tM7hAkHYRjkNb5w6Pxk",
        "BLZEEuZUBVqFhj8adcCFPJvPVCiCyVmh3hkJMrU8KuJA",
        "CKaKtYvz6dKPyMvYq9Rh3UBrnNqYZAyd7iF4hJtjUvks",
        "orcaEKTdK7LKz57vaAYr9QeNsVEPfiu6QeMU1kektZE",
        "JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN",
        "hntyVP6YFm1Hg25TN9WGLqM12b8TQmcknKrdu1oxWux",
    ]

    # Create 15 BUY/SELL pairs (medium confidence)
    for i in range(15):
        base_time = i * 20000  # Spaced out
        token_mint = token_mints[i % len(token_mints)]

        # BUY with ~3 SOL average
        transactions.append(
            SwapTransaction(
                signature=f"buy{i:064d}",  # 64 chars for valid signature
                timestamp=base_time,
                tx_type=TransactionType.BUY,
                token_mint=token_mint,
                sol_amount=2.5 + (i % 3) * 0.5,  # Varies between 2.5 and 3.5 SOL
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        )

        # SELL after ~6 hours
        transactions.append(
            SwapTransaction(
                signature=f"sell{i:063d}",  # 64 chars for valid signature
                timestamp=base_time + 21600,  # 6 hours later
                tx_type=TransactionType.SELL,
                token_mint=token_mint,
                sol_amount=3.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        )

    return transactions


@pytest.fixture
def sample_transactions_swing_trader():
    """Create sample transactions for a swing trader profile (long holds, large positions)."""
    transactions = []

    # Valid base58 token mints (32-44 characters, no 0, O, I, l)
    token_mints = [
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",
        "7vfCXTUXx5WJV5JADk17DUJ4ksgau7utNKj4b963voxs",
        "So11111111111111111111111111111111111111112",
        "mSoLzYCxHdYgdzU16g5QSh3i5K3z3KZK7ytfqcJm7So",
        "7dHbWXmci3dT8UFYWYZweBLXgycu7Y3iL6trKn1Y7ARj",
        "9n4nbM75f5Ui33ZbPYXn59EwSgE8CGsHtAeTH5YFeJ9E",
        "AGFEad2et2ZJif9jaGpdMixQqvW5i81aBdvKe7PHNfz3",
        "2FPyTwcZLUg1MDrwsyoP4D6s1tM7hAkHYRjkNb5w6Pxk",
    ]

    # Create 60 BUY/SELL pairs (high confidence)
    for i in range(60):
        base_time = i * 1000000  # Spaced out
        token_mint = token_mints[i % len(token_mints)]

        # BUY with ~8 SOL average (large positions)
        transactions.append(
            SwapTransaction(
                signature=f"buy{i:064d}",  # 64 chars for valid signature
                timestamp=base_time,
                tx_type=TransactionType.BUY,
                token_mint=token_mint,
                sol_amount=7.0 + (i % 4),  # Varies between 7 and 10 SOL
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        )

        # SELL after ~3 days
        transactions.append(
            SwapTransaction(
                signature=f"sell{i:063d}",  # 64 chars for valid signature
                timestamp=base_time + 259200,  # 3 days later
                tx_type=TransactionType.SELL,
                token_mint=token_mint,
                sol_amount=8.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        )

    return transactions


class TestBehavioralProfiler:
    """Integration tests for BehavioralProfiler class."""

    @pytest.mark.asyncio
    async def test_analyze_scalper_profile(
        self, mock_helius_client, mock_config, sample_transactions_scalper
    ):
        """Test profiling a scalper wallet with insufficient data.

        AC4: Wallets with < 10 trades return None (insufficient data).
        This test has only 2 trades, so should return None.
        """
        # Setup: Mock Helius to return scalper transactions (2 trades)
        mock_helius_client.get_wallet_transactions.return_value = (
            sample_transactions_scalper
        )

        profiler = BehavioralProfiler(mock_helius_client, mock_config)

        # Act: Analyze wallet
        profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Assert: AC4 compliance - insufficient data (2 trades < 10 min)
        assert profile is None  # Returns None instead of unreliable profile

        # Verify Helius was called
        mock_helius_client.get_wallet_transactions.assert_called_once_with(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"
        )

    @pytest.mark.asyncio
    async def test_analyze_day_trader_profile(
        self, mock_helius_client, mock_config, sample_transactions_day_trader
    ):
        """Test profiling a day trader wallet (medium holds, medium positions)."""
        # Setup: Mock Helius to return day trader transactions
        mock_helius_client.get_wallet_transactions.return_value = (
            sample_transactions_day_trader
        )

        profiler = BehavioralProfiler(mock_helius_client, mock_config)

        # Act: Analyze wallet
        profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Assert: Profile characteristics
        assert profile.position_size_style == "medium"  # Avg ~3 SOL
        assert profile.hold_duration_style == "day_trader"  # Avg 6 hours
        assert profile.confidence == "medium"  # 15 trades (>= 10, < 50)
        assert profile.total_trades == 15

    @pytest.mark.asyncio
    async def test_analyze_swing_trader_profile(
        self, mock_helius_client, mock_config, sample_transactions_swing_trader
    ):
        """Test profiling a swing trader wallet (long holds, large positions)."""
        # Setup: Mock Helius to return swing trader transactions
        mock_helius_client.get_wallet_transactions.return_value = (
            sample_transactions_swing_trader
        )

        profiler = BehavioralProfiler(mock_helius_client, mock_config)

        # Act: Analyze wallet
        profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Assert: Profile characteristics
        assert profile.position_size_style == "large"  # Avg ~8 SOL
        assert profile.hold_duration_style == "swing_trader"  # Avg 3 days
        assert profile.confidence == "high"  # 60 trades (>= 50)
        assert profile.total_trades == 60

    @pytest.mark.asyncio
    async def test_analyze_empty_transactions(self, mock_helius_client, mock_config):
        """Test profiling a wallet with no transactions.

        AC4: Wallets with < 10 trades return None (insufficient data).
        This test has 0 trades, so should return None.
        """
        # Setup: Mock Helius to return empty list
        mock_helius_client.get_wallet_transactions.return_value = []

        profiler = BehavioralProfiler(mock_helius_client, mock_config)

        # Act: Analyze wallet
        profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Assert: AC4 compliance - no transactions (0 trades < 10 min)
        assert profile is None  # Returns None instead of unreliable profile

    @pytest.mark.asyncio
    async def test_analyze_with_custom_thresholds(
        self, mock_helius_client, sample_transactions_day_trader
    ):
        """Test profiling with custom configuration thresholds."""
        # Setup: Custom config with different thresholds
        custom_config = AsyncMock(spec=ConfigRepository)
        custom_config.get_position_size_small_max.return_value = 2.0  # Higher small max
        custom_config.get_position_size_medium_max.return_value = 10.0
        custom_config.get_hold_duration_scalper_max.return_value = 7200  # 2 hours
        custom_config.get_hold_duration_day_trader_max.return_value = 172800  # 2 days
        custom_config.get_hold_duration_swing_trader_max.return_value = 604800
        custom_config.get_behavioral_min_trades.return_value = 5  # Lower minimum
        custom_config.get_behavioral_confidence_medium.return_value = 20
        custom_config.get_behavioral_confidence_high.return_value = 100

        mock_helius_client.get_wallet_transactions.return_value = (
            sample_transactions_day_trader
        )

        profiler = BehavioralProfiler(mock_helius_client, custom_config)

        # Act: Analyze wallet
        profile = await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

        # Assert: Classifications based on custom thresholds
        # Position: avg ~3 SOL, now "medium" (between 2 and 10)
        assert profile.position_size_style == "medium"

        # Hold: avg 6h (21600s), scalper_max=7200s (2h), day_trader_max=172800s (2 days)
        # 21600s > 7200s but <= 172800s → "day_trader"
        assert profile.hold_duration_style == "day_trader"

        # Confidence: 15 trades, min=5, medium=20, high=100 → "low" (>=5 but <20)
        assert profile.confidence == "low"

    @pytest.mark.asyncio
    async def test_analyze_transaction_fetch_failure(
        self, mock_helius_client, mock_config
    ):
        """Test error handling when transaction fetch fails."""
        # Setup: Mock Helius to raise exception
        mock_helius_client.get_wallet_transactions.side_effect = Exception(
            "API connection failed"
        )

        profiler = BehavioralProfiler(mock_helius_client, mock_config)

        # Act & Assert: Should propagate exception
        with pytest.raises(Exception, match="API connection failed"):
            await profiler.analyze("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
