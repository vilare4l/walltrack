"""Unit tests for behavioral profiling functions.

Tests position sizing and hold duration analysis logic.
"""

from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from walltrack.core.behavioral.hold_duration import (
    calculate_hold_duration_avg,
    classify_hold_duration,
    format_duration_human,
)
from walltrack.core.behavioral.position_sizing import (
    calculate_position_size_avg,
    classify_position_size,
)
from walltrack.data.models.transaction import SwapTransaction, TransactionType


class TestCalculatePositionSizeAvg:
    """Tests for calculate_position_size_avg function."""

    def test_empty_list(self):
        """Test with empty transaction list returns 0."""
        result = calculate_position_size_avg([])
        assert result == Decimal("0")

    def test_single_buy_transaction(self):
        """Test with single BUY transaction returns exact amount."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        ]
        result = calculate_position_size_avg(txs)
        assert result == Decimal("2.50000000")

    def test_multiple_buy_transactions(self):
        """Test average calculation with multiple BUY transactions."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703001235,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=3.0,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig3",
                timestamp=1703001236,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.0,
                token_amount=1500000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # Average: (1.0 + 3.0 + 2.0) / 3 = 2.0
        result = calculate_position_size_avg(txs)
        assert result == Decimal("2.00000000")

    def test_filters_sell_transactions(self):
        """Test that SELL transactions are excluded from average."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=1703001235,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=3.0,  # Should be ignored
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig3",
                timestamp=1703001236,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=4.0,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # Average: (2.0 + 4.0) / 2 = 3.0 (SELL excluded)
        result = calculate_position_size_avg(txs)
        assert result == Decimal("3.00000000")

    def test_only_sell_transactions(self):
        """Test with only SELL transactions returns 0."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=5.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        ]
        result = calculate_position_size_avg(txs)
        assert result == Decimal("0")

    def test_decimal_precision(self):
        """Test that result has exactly 8 decimal places."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1703001234,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.23456789,  # More than 8 decimals
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        ]
        result = calculate_position_size_avg(txs)
        # Should be quantized to 8 decimals
        assert result == Decimal("1.23456789")
        assert result.as_tuple().exponent == -8


class TestClassifyPositionSize:
    """Tests for classify_position_size function."""

    @pytest.mark.asyncio
    async def test_small_position(self):
        """Test classification as 'small' when below small threshold."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("0.5"), mock_config)
        assert result == "small"

    @pytest.mark.asyncio
    async def test_small_position_at_threshold(self):
        """Test classification as 'small' when exactly at small threshold."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("1.0"), mock_config)
        assert result == "small"

    @pytest.mark.asyncio
    async def test_medium_position(self):
        """Test classification as 'medium' when between thresholds."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("3.0"), mock_config)
        assert result == "medium"

    @pytest.mark.asyncio
    async def test_medium_position_at_threshold(self):
        """Test classification as 'medium' when exactly at medium threshold."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("5.0"), mock_config)
        assert result == "medium"

    @pytest.mark.asyncio
    async def test_large_position(self):
        """Test classification as 'large' when above medium threshold."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("10.0"), mock_config)
        assert result == "large"

    @pytest.mark.asyncio
    async def test_large_position_just_above_threshold(self):
        """Test classification as 'large' when just above medium threshold."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("5.00000001"), mock_config)
        assert result == "large"

    @pytest.mark.asyncio
    async def test_zero_position(self):
        """Test classification with zero position size."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 1.0
        mock_config.get_position_size_medium_max.return_value = 5.0

        result = await classify_position_size(Decimal("0"), mock_config)
        assert result == "small"

    @pytest.mark.asyncio
    async def test_custom_thresholds(self):
        """Test classification with custom threshold values."""
        mock_config = AsyncMock()
        mock_config.get_position_size_small_max.return_value = 2.0  # Custom
        mock_config.get_position_size_medium_max.return_value = 10.0  # Custom

        # Should be small (1.5 <= 2.0)
        result = await classify_position_size(Decimal("1.5"), mock_config)
        assert result == "small"

        # Should be medium (7.0 > 2.0 and <= 10.0)
        result = await classify_position_size(Decimal("7.0"), mock_config)
        assert result == "medium"

        # Should be large (15.0 > 10.0)
        result = await classify_position_size(Decimal("15.0"), mock_config)
        assert result == "large"


class TestCalculateHoldDurationAvg:
    """Tests for calculate_hold_duration_avg function."""

    def test_empty_list(self):
        """Test with empty transaction list returns 0."""
        result = calculate_hold_duration_avg([])
        assert result == 0

    def test_single_buy_sell_pair(self):
        """Test with single BUY/SELL pair calculates exact duration."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # Duration: 5000 - 1000 = 4000 seconds
        result = calculate_hold_duration_avg(txs)
        assert result == 4000

    def test_multiple_buy_sell_pairs(self):
        """Test average calculation with multiple BUY/SELL pairs."""
        txs = [
            # First pair: duration = 3000
            SwapTransaction(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=4000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            # Second pair: duration = 5000
            SwapTransaction(
                signature="sig3",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                token_mint="DifferentTokenMintAddress32Characters",
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig4",
                timestamp=7000,
                tx_type=TransactionType.SELL,
                token_mint="DifferentTokenMintAddress32Characters",
                sol_amount=2.5,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # Average: (3000 + 5000) / 2 = 4000
        result = calculate_hold_duration_avg(txs)
        assert result == 4000

    def test_fifo_matching(self):
        """Test FIFO matching logic for multiple BUYs before SELL."""
        txs = [
            # First BUY
            SwapTransaction(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            # Second BUY
            SwapTransaction(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            # First SELL - should match with first BUY (FIFO)
            SwapTransaction(
                signature="sig3",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            # Second SELL - should match with second BUY
            SwapTransaction(
                signature="sig4",
                timestamp=6000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.5,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # First pair: 5000 - 1000 = 4000
        # Second pair: 6000 - 2000 = 4000
        # Average: 4000
        result = calculate_hold_duration_avg(txs)
        assert result == 4000

    def test_unmatched_buys_ignored(self):
        """Test that unmatched BUYs (no corresponding SELL) are ignored."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            SwapTransaction(
                signature="sig2",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
            # This BUY has no matching SELL - should be ignored
            SwapTransaction(
                signature="sig3",
                timestamp=6000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=2.0,
                token_amount=2000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            ),
        ]
        # Only first pair: 5000 - 1000 = 4000
        result = calculate_hold_duration_avg(txs)
        assert result == 4000

    def test_only_buys_returns_zero(self):
        """Test with only BUY transactions returns 0."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.0,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        ]
        result = calculate_hold_duration_avg(txs)
        assert result == 0

    def test_only_sells_returns_zero(self):
        """Test with only SELL transactions returns 0."""
        txs = [
            SwapTransaction(
                signature="sig1",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                sol_amount=1.5,
                token_amount=1000000,
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            )
        ]
        result = calculate_hold_duration_avg(txs)
        assert result == 0


class TestClassifyHoldDuration:
    """Tests for classify_hold_duration function."""

    @pytest.mark.asyncio
    async def test_scalper_classification(self):
        """Test classification as 'scalper' for short holds (< 1 hour)."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600  # 1 hour
        mock_config.get_hold_duration_day_trader_max.return_value = 86400  # 24 hours
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800  # 7 days

        result = await classify_hold_duration(1800, mock_config)  # 30 minutes
        assert result == "scalper"

    @pytest.mark.asyncio
    async def test_scalper_at_threshold(self):
        """Test classification as 'scalper' at exact threshold."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(3600, mock_config)  # Exactly 1 hour
        assert result == "scalper"

    @pytest.mark.asyncio
    async def test_day_trader_classification(self):
        """Test classification as 'day_trader' for holds between 1h and 24h."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(7200, mock_config)  # 2 hours
        assert result == "day_trader"

    @pytest.mark.asyncio
    async def test_day_trader_at_threshold(self):
        """Test classification as 'day_trader' at exact threshold."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(86400, mock_config)  # Exactly 24 hours
        assert result == "day_trader"

    @pytest.mark.asyncio
    async def test_swing_trader_classification(self):
        """Test classification as 'swing_trader' for holds between 1d and 7d."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(172800, mock_config)  # 2 days
        assert result == "swing_trader"

    @pytest.mark.asyncio
    async def test_swing_trader_at_threshold(self):
        """Test classification as 'swing_trader' at exact threshold."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(604800, mock_config)  # Exactly 7 days
        assert result == "swing_trader"

    @pytest.mark.asyncio
    async def test_position_trader_classification(self):
        """Test classification as 'position_trader' for long holds (> 7 days)."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(1209600, mock_config)  # 14 days
        assert result == "position_trader"

    @pytest.mark.asyncio
    async def test_zero_duration(self):
        """Test classification with zero duration (edge case)."""
        mock_config = AsyncMock()
        mock_config.get_hold_duration_scalper_max.return_value = 3600
        mock_config.get_hold_duration_day_trader_max.return_value = 86400
        mock_config.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(0, mock_config)
        assert result == "scalper"


class TestFormatDurationHuman:
    """Tests for format_duration_human function."""

    def test_zero_seconds(self):
        """Test formatting 0 seconds."""
        assert format_duration_human(0) == "0s"

    def test_only_seconds(self):
        """Test formatting small durations (seconds only)."""
        assert format_duration_human(45) == "45s"

    def test_only_minutes(self):
        """Test formatting minutes."""
        assert format_duration_human(120) == "2m"

    def test_only_hours(self):
        """Test formatting hours."""
        assert format_duration_human(3600) == "1h"

    def test_only_days(self):
        """Test formatting days."""
        assert format_duration_human(86400) == "1d"

    def test_hours_and_minutes(self):
        """Test formatting hours and minutes."""
        assert format_duration_human(7320) == "2h 2m"

    def test_days_and_hours(self):
        """Test formatting days and hours."""
        assert format_duration_human(90000) == "1d 1h"

    def test_days_hours_minutes(self):
        """Test formatting days, hours, and minutes."""
        assert format_duration_human(90061) == "1d 1h 1m"

    def test_large_duration(self):
        """Test formatting large duration (multiple days)."""
        # 3 days, 5 hours, 20 minutes, 15 seconds
        seconds = (3 * 86400) + (5 * 3600) + (20 * 60) + 15
        assert format_duration_human(seconds) == "3d 5h 20m"

    def test_no_seconds_shown_when_larger_units_exist(self):
        """Test that seconds are omitted when larger units exist."""
        # 1 hour, 30 minutes, 45 seconds
        seconds = 3600 + 1800 + 45
        assert format_duration_human(seconds) == "1h 30m"  # Seconds omitted
