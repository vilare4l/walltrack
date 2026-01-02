"""Unit tests for PerformanceCalculator.

Tests cover:
- Win rate calculation with various trade outcomes
- PnL total calculation
- Entry delay calculation
- Confidence level assignment
- Edge cases (no trades, open positions, etc.)
"""

from datetime import datetime

import pytest

from walltrack.core.analysis.performance_calculator import PerformanceCalculator
from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.models.wallet import PerformanceMetrics


@pytest.fixture
def calculator():
    """Create PerformanceCalculator instance."""
    return PerformanceCalculator()


@pytest.fixture
def sample_wallet_address():
    """Sample wallet address for tests."""
    return "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"


@pytest.fixture
def sample_token_mint():
    """Sample token mint address for tests."""
    return "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


class TestCalculateMetrics:
    """Tests for calculate_metrics() method."""

    def test_no_transactions_returns_zero_metrics(self, calculator):
        """Test that empty transaction list returns zero metrics."""
        # Act
        metrics = calculator.calculate_metrics(transactions=[])

        # Assert
        assert metrics.win_rate == 0.0
        assert metrics.pnl_total == 0.0
        assert metrics.entry_delay_seconds == 0
        assert metrics.total_trades == 0
        assert metrics.confidence == "unknown"

    def test_only_open_positions_returns_zero_metrics(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test that only BUYs (no SELLs) returns zero metrics."""
        # Arrange
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703001300,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.win_rate == 0.0
        assert metrics.pnl_total == 0.0
        assert metrics.entry_delay_seconds == 0
        assert metrics.total_trades == 0
        assert metrics.confidence == "unknown"

    def test_single_profitable_trade(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test single profitable trade (100% win rate)."""
        # Arrange
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703005678,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.win_rate == 100.0
        assert metrics.pnl_total == 0.5  # 1.5 - 1.0
        assert metrics.total_trades == 1
        assert metrics.confidence == "low"  # 1 trade = low confidence

    def test_single_losing_trade(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test single losing trade (0% win rate)."""
        # Arrange
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=2.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703005678,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.win_rate == 0.0
        assert metrics.pnl_total == -0.5  # 1.5 - 2.0
        assert metrics.total_trades == 1
        assert metrics.confidence == "low"

    def test_mixed_win_loss_trades(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test multiple trades with mixed outcomes (50% win rate)."""
        # Arrange - Token1: WIN (+0.5), Token2: LOSS (-0.3)
        transactions = [
            # Token1: BUY 1.0 -> SELL 1.5 = +0.5
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703005678,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            # Token2: BUY 2.0 -> SELL 1.7 = -0.3
            SwapTransaction(
                signature="sig3",
                timestamp=1703010000,
                tx_type=TransactionType.BUY,
                token_mint="TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=1703015000,
                tx_type=TransactionType.SELL,
                token_mint="TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                sol_amount=1.7,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.win_rate == 50.0  # 1 win, 1 loss
        assert metrics.pnl_total == pytest.approx(0.2)  # +0.5 - 0.3
        assert metrics.total_trades == 2
        assert metrics.confidence == "low"  # 2 trades = low

    def test_entry_delay_calculation_with_launch_times(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test entry delay calculation when launch times provided."""
        # Arrange - Token launched at 12:00, wallet bought at 13:30 (90 min delay)
        launch_time = datetime.fromtimestamp(1703001800)  # 12:00:00
        first_buy_time = 1703001800 + 5400  # 13:30:00 (90 min later)

        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=first_buy_time,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=first_buy_time + 1000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        token_launch_times = {sample_token_mint: launch_time}

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions, token_launch_times=token_launch_times
        )

        # Assert
        assert metrics.entry_delay_seconds == 5400  # 90 minutes
        assert metrics.total_trades == 1

    def test_entry_delay_without_launch_times(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test entry delay is zero when launch times not provided."""
        # Arrange
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703005678,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions, token_launch_times=None
        )

        # Assert
        assert metrics.entry_delay_seconds == 0


class TestConfidenceLevels:
    """Tests for confidence level assignment."""

    def test_confidence_unknown_no_trades(self, calculator):
        """Test confidence is 'unknown' with no trades."""
        # Act
        metrics = calculator.calculate_metrics(transactions=[])

        # Assert
        assert metrics.confidence == "unknown"

    def test_confidence_low_1_to_4_trades(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test confidence is 'low' with 1-4 trades."""
        # Arrange - Create 3 completed trades
        transactions = []
        # Use valid base58 characters (no X)
        base_mints = [
            "TokenMint1111111111111111111111111111",
            "TokenMint2222222222222222222222222222",
            "TokenMint3333333333333333333333333333",
        ]
        for i, token_mint in enumerate(base_mints):
            transactions.extend(
                [
                    SwapTransaction(
                        signature=f"sig_buy_{i}",
                        timestamp=1703001234 + (i * 10000),
                        tx_type=TransactionType.BUY,
                        token_mint=token_mint,
                        sol_amount=1.0,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                    SwapTransaction(
                        signature=f"sig_sell_{i}",
                        timestamp=1703001234 + (i * 10000) + 1000,
                        tx_type=TransactionType.SELL,
                        token_mint=token_mint,
                        sol_amount=1.2,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                ]
            )

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.total_trades == 3
        assert metrics.confidence == "low"

    def test_confidence_medium_5_to_19_trades(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test confidence is 'medium' with 5-19 trades."""
        # Arrange - Create 10 completed trades
        transactions = []
        # Use valid base58 chars: no 0, O, I, l
        base_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        for i in range(10):
            # Generate unique token mint with valid base58 chars
            token_mint = f"TokenMint{base_chars[i]}" + "1" * 23
            transactions.extend(
                [
                    SwapTransaction(
                        signature=f"sig_buy_{i}",
                        timestamp=1703001234 + (i * 10000),
                        tx_type=TransactionType.BUY,
                        token_mint=token_mint,
                        sol_amount=1.0,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                    SwapTransaction(
                        signature=f"sig_sell_{i}",
                        timestamp=1703001234 + (i * 10000) + 1000,
                        tx_type=TransactionType.SELL,
                        token_mint=token_mint,
                        sol_amount=1.2,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                ]
            )

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.total_trades == 10
        assert metrics.confidence == "medium"

    def test_confidence_high_20_plus_trades(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test confidence is 'high' with 20+ trades."""
        # Arrange - Create 25 completed trades
        transactions = []
        # Use valid base58 chars: no 0, O, I, l
        base_chars = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
        for i in range(25):
            # Generate unique token mint with valid base58 chars
            token_mint = f"TM{base_chars[i % len(base_chars)]}{base_chars[(i+1) % len(base_chars)]}" + "1" * 28
            transactions.extend(
                [
                    SwapTransaction(
                        signature=f"sig_buy_{i}",
                        timestamp=1703001234 + (i * 10000),
                        tx_type=TransactionType.BUY,
                        token_mint=token_mint,
                        sol_amount=1.0,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                    SwapTransaction(
                        signature=f"sig_sell_{i}",
                        timestamp=1703001234 + (i * 10000) + 1000,
                        tx_type=TransactionType.SELL,
                        token_mint=token_mint,
                        sol_amount=1.2,
                        token_amount=1000000,
                        wallet_address=sample_wallet_address,
                    ),
                ]
            )

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.total_trades == 25
        assert metrics.confidence == "high"


class TestFIFOMatching:
    """Tests for FIFO trade matching logic."""

    def test_fifo_matching_multiple_buys_sells(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test FIFO matching: oldest BUY matches oldest SELL."""
        # Arrange - Same token: BUY(1.0), BUY(2.0), SELL(1.5), SELL(2.5)
        # Expected: BUY(1.0)->SELL(1.5)=+0.5, BUY(2.0)->SELL(2.5)=+0.5
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,  # First BUY
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,  # Second BUY
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig3",
                timestamp=1703003000,  # First SELL (matches first BUY)
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=1703004000,  # Second SELL (matches second BUY)
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=2.5,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.total_trades == 2
        assert metrics.win_rate == 100.0  # Both profitable
        assert metrics.pnl_total == pytest.approx(1.0)  # +0.5 + 0.5

    def test_fifo_ignores_unmatched_sells(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test that extra SELLs (without BUYs) are ignored."""
        # Arrange - 1 BUY, 2 SELLs (only first SELL should match)
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig3",
                timestamp=1703003000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=2.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert
        assert metrics.total_trades == 1  # Only 1 matched pair
        assert metrics.pnl_total == 0.5  # 1.5 - 1.0


class TestMinProfitThreshold:
    """Tests for min_profit_percent threshold (AC2 & AC7)."""

    def test_win_rate_with_10_percent_threshold(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test win rate with 10% profit threshold (AC2)."""
        # Arrange - Trade 1: +15% profit (WIN), Trade 2: +5% profit (LOSS - below threshold)
        transactions = [
            # Trade 1: BUY 1.0 -> SELL 1.15 = +15% (WIN)
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.15,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            # Trade 2: BUY 2.0 -> SELL 2.1 = +5% (LOSS - below 10% threshold)
            SwapTransaction(
                signature="sig3",
                timestamp=1703003000,
                tx_type=TransactionType.BUY,
                token_mint="TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=1703004000,
                tx_type=TransactionType.SELL,
                token_mint="TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX",
                sol_amount=2.1,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions,
            min_profit_percent=10.0,  # AC2: 10% threshold
        )

        # Assert
        assert metrics.win_rate == 50.0, "Only trade with >10% profit should count as win"
        assert metrics.total_trades == 2, "Both trades closed"
        # PnL should still reflect actual profit (+0.15 + 0.1 = +0.25)
        assert metrics.pnl_total == pytest.approx(0.25)

    def test_win_rate_exactly_at_threshold(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test trade exactly at 10% threshold (should be WIN)."""
        # Arrange - BUY 1.0 -> SELL 1.1 = exactly 10%
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.1,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions,
            min_profit_percent=10.0,
        )

        # Assert - Exactly 10% should count as WIN
        assert metrics.win_rate == 100.0, "Trade at exactly 10% profit should be WIN"

    def test_custom_profit_threshold(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test with custom min_profit_percent value (AC7)."""
        # Arrange - BUY 1.0 -> SELL 1.2 = 20% profit
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.2,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act - Use 25% threshold
        metrics = calculator.calculate_metrics(
            transactions=transactions,
            min_profit_percent=25.0,
        )

        # Assert - 20% profit < 25% threshold = LOSS
        assert metrics.win_rate == 0.0, "20% profit < 25% threshold should be LOSS"

    def test_default_threshold_backwards_compatible(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test that omitting min_profit_percent uses default (0% - any positive profit)."""
        # Arrange - BUY 1.0 -> SELL 1.01 = 1% profit
        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703002000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.01,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        # Act - No min_profit_percent provided (backwards compat)
        metrics = calculator.calculate_metrics(transactions=transactions)

        # Assert - Any positive profit should be WIN (default behavior)
        assert metrics.win_rate == 100.0, "Without threshold, any positive PnL should be WIN"


class TestEntryDelayEdgeCases:
    """Tests for entry delay calculation edge cases."""

    def test_entry_delay_negative_ignored(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test that negative delays (buy before launch) are ignored."""
        # Arrange - Wallet bought BEFORE token launch (impossible/pre-sale)
        launch_time = datetime.fromtimestamp(1703005000)
        buy_time = 1703001000  # 4000 seconds BEFORE launch

        transactions = [
            SwapTransaction(
                signature="sig1",
                timestamp=buy_time,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=buy_time + 1000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        token_launch_times = {sample_token_mint: launch_time}

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions, token_launch_times=token_launch_times
        )

        # Assert
        assert metrics.entry_delay_seconds == 0  # Negative delay ignored

    def test_entry_delay_average_across_tokens(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test entry delay is averaged across multiple tokens."""
        # Arrange - Token1: 3600s delay (1h), Token2: 7200s delay (2h)
        # Expected average: (3600 + 7200) / 2 = 5400s (1.5h)
        launch1 = datetime.fromtimestamp(1703001000)
        launch2 = datetime.fromtimestamp(1703001000)

        token_mint_2 = "TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX"

        transactions = [
            # Token1: Buy at launch+3600s
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000 + 3600,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703001000 + 5000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            # Token2: Buy at launch+7200s
            SwapTransaction(
                signature="sig3",
                timestamp=1703001000 + 7200,
                tx_type=TransactionType.BUY,
                token_mint=token_mint_2,
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=1703001000 + 9000,
                tx_type=TransactionType.SELL,
                token_mint=token_mint_2,
                sol_amount=2.5,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        token_launch_times = {
            sample_token_mint: launch1,
            token_mint_2: launch2,
        }

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions, token_launch_times=token_launch_times
        )

        # Assert
        assert metrics.entry_delay_seconds == 5400  # (3600 + 7200) / 2

    def test_entry_delay_missing_launch_time_ignored(
        self, calculator, sample_wallet_address, sample_token_mint
    ):
        """Test that tokens without launch time don't affect average."""
        # Arrange - Token1 has launch time (3600s delay), Token2 missing
        # Expected: Only Token1 counted in average
        launch1 = datetime.fromtimestamp(1703001000)
        token_mint_2 = "TokenMint2XXXXXXXXXXXXXXXXXXXXXXXXXXXX"

        transactions = [
            # Token1: Buy at launch+3600s
            SwapTransaction(
                signature="sig1",
                timestamp=1703001000 + 3600,
                tx_type=TransactionType.BUY,
                token_mint=sample_token_mint,
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703001000 + 5000,
                tx_type=TransactionType.SELL,
                token_mint=sample_token_mint,
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address=sample_wallet_address,
            ),
            # Token2: No launch time in dict
            SwapTransaction(
                signature="sig3",
                timestamp=1703010000,
                tx_type=TransactionType.BUY,
                token_mint=token_mint_2,
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=1703015000,
                tx_type=TransactionType.SELL,
                token_mint=token_mint_2,
                sol_amount=2.5,
                token_amount=2000000,
                wallet_address=sample_wallet_address,
            ),
        ]

        token_launch_times = {sample_token_mint: launch1}  # Only Token1

        # Act
        metrics = calculator.calculate_metrics(
            transactions=transactions, token_launch_times=token_launch_times
        )

        # Assert
        assert metrics.entry_delay_seconds == 3600  # Only Token1 counted
        assert metrics.total_trades == 2  # Both tokens have trades
