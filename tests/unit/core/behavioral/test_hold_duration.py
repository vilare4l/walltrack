"""Unit tests for hold duration analysis.

Tests for calculating and classifying wallet hold duration patterns from transaction history.
Story 3.3 - Task 6.
"""

import pytest

from walltrack.data.models.transaction import TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.core.behavioral.hold_duration import (
    calculate_hold_duration_avg,
    classify_hold_duration,
    format_duration_human,
)
from tests.unit.core.behavioral.conftest import (
    VALID_TOKEN_MINT_ABC,
    VALID_TOKEN_MINT_DEF,
)


class TestCalculateHoldDurationAvg:
    """Tests for calculate_hold_duration_avg function."""

    def test_calculates_average_from_buy_sell_pairs(self, swap_transaction_factory):
        """Should match BUY with SELL for same token and calculate average duration."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
            ),
            swap_transaction_factory(
                signature="sig2",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.2,
            ),
        ]

        result = calculate_hold_duration_avg(transactions)

        # Duration: 5000 - 1000 = 4000 seconds
        assert result == 4000

    def test_fifo_matching_multiple_positions(self, swap_transaction_factory):
        """Should match BUY/SELL pairs using FIFO (first in, first out)."""
        transactions = [
            # First BUY
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            # Second BUY
            swap_transaction_factory(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            # First SELL (matches first BUY)
            swap_transaction_factory(
                signature="sig3",
                timestamp=3000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            # Second SELL (matches second BUY)
            swap_transaction_factory(
                signature="sig4",
                timestamp=6000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
        ]

        result = calculate_hold_duration_avg(transactions)

        # First pair: 3000 - 1000 = 2000
        # Second pair: 6000 - 2000 = 4000
        # Average: (2000 + 4000) / 2 = 3000
        assert result == 3000

    def test_multiple_tokens_separate_matching(self, swap_transaction_factory):
        """Should match BUY/SELL pairs separately for each token."""
        transactions = [
            # Token ABC
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            # Token DEF
            swap_transaction_factory(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_DEF,
                sol_amount=1.0,
                token_amount=200.0,
            ),
            # Sell ABC
            swap_transaction_factory(
                signature="sig3",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.2,
                token_amount=100.0,
            ),
            # Sell DEF
            swap_transaction_factory(
                signature="sig4",
                timestamp=10000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_DEF,
                sol_amount=1.5,
                token_amount=200.0,
            ),
        ]

        result = calculate_hold_duration_avg(transactions)

        # ABC: 5000 - 1000 = 4000
        # DEF: 10000 - 2000 = 8000
        # Average: (4000 + 8000) / 2 = 6000
        assert result == 6000

    def test_returns_zero_for_no_valid_pairs(self, swap_transaction_factory):
        """Should return 0 when no complete BUY/SELL pairs exist."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            # No matching SELL
        ]

        result = calculate_hold_duration_avg(transactions)

        assert result == 0

    def test_returns_zero_for_empty_list(self):
        """Should return 0 for empty transaction list."""
        result = calculate_hold_duration_avg([])
        assert result == 0

    def test_ignores_open_positions(self, swap_transaction_factory):
        """Should only calculate duration for closed positions (BUY + SELL pairs)."""
        transactions = [
            # Closed position
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.0,
                token_amount=100.0,
            ),
            swap_transaction_factory(
                signature="sig2",
                timestamp=5000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.2,
                token_amount=100.0,
            ),
            # Open position (no SELL)
            swap_transaction_factory(
                signature="sig3",
                timestamp=6000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_DEF,
                sol_amount=1.0,
                token_amount=200.0,
            ),
        ]

        result = calculate_hold_duration_avg(transactions)

        # Only closed position ABC: 5000 - 1000 = 4000
        assert result == 4000


class TestClassifyHoldDuration:
    """Tests for classify_hold_duration function."""

    @pytest.mark.asyncio
    async def test_classifies_scalper_below_threshold(self, mock_config_repo):
        """Should classify as scalper when duration <= scalper_max."""
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600  # 1 hour
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400  # 24 hours
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800  # 7 days

        result = await classify_hold_duration(1800, mock_config_repo)  # 30 minutes

        assert result == "scalper"

    @pytest.mark.asyncio
    async def test_classifies_scalper_at_threshold(self, mock_config_repo):
        """Should classify as scalper when duration exactly at scalper_max."""
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(3600, mock_config_repo)

        assert result == "scalper"

    @pytest.mark.asyncio
    async def test_classifies_day_trader(self, mock_config_repo):
        """Should classify as day_trader when duration between scalper_max and day_trader_max."""
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(7200, mock_config_repo)  # 2 hours

        assert result == "day_trader"

    @pytest.mark.asyncio
    async def test_classifies_swing_trader(self, mock_config_repo):
        """Should classify as swing_trader when duration between day_trader_max and swing_trader_max."""
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(172800, mock_config_repo)  # 2 days

        assert result == "swing_trader"

    @pytest.mark.asyncio
    async def test_classifies_position_trader(self, mock_config_repo):
        """Should classify as position_trader when duration > swing_trader_max."""
        mock_config_repo.get_hold_duration_scalper_max.return_value = 3600
        mock_config_repo.get_hold_duration_day_trader_max.return_value = 86400
        mock_config_repo.get_hold_duration_swing_trader_max.return_value = 604800

        result = await classify_hold_duration(1209600, mock_config_repo)  # 14 days

        assert result == "position_trader"

    @pytest.mark.asyncio
    async def test_uses_fallback_defaults_on_config_error(self, failing_config_repo):
        """Should use hardcoded defaults when config fetch fails."""
        result = await classify_hold_duration(7200, failing_config_repo)  # 2 hours

        # With fallback defaults (scalper_max=3600, day_trader_max=86400), 7200 is day_trader
        assert result == "day_trader"


class TestFormatDurationHuman:
    """Tests for format_duration_human function."""

    def test_formats_zero_seconds(self):
        """Should format 0 seconds as '0s'."""
        assert format_duration_human(0) == "0s"

    def test_formats_seconds_only(self):
        """Should format duration with only seconds."""
        assert format_duration_human(45) == "45s"

    def test_formats_minutes(self):
        """Should format duration with minutes."""
        assert format_duration_human(120) == "2m"

    def test_formats_hours(self):
        """Should format duration with hours."""
        assert format_duration_human(3600) == "1h"

    def test_formats_hours_and_minutes(self):
        """Should format duration with hours and minutes."""
        assert format_duration_human(7320) == "2h 2m"

    def test_formats_days_hours_minutes(self):
        """Should format duration with days, hours, and minutes."""
        assert format_duration_human(90061) == "1d 1h 1m"

    def test_omits_zero_units(self):
        """Should omit units that are zero."""
        assert format_duration_human(86400) == "1d"  # Exactly 1 day, no hours/minutes

    def test_does_not_show_seconds_with_larger_units(self):
        """Should not show seconds if days/hours/minutes are present."""
        assert format_duration_human(3661) == "1h 1m"  # 1 hour, 1 minute, 1 second -> omit seconds


@pytest.fixture
def mock_config_repo(mocker):
    """Mock ConfigRepository for testing."""
    mock = mocker.AsyncMock(spec=ConfigRepository)
    return mock


@pytest.fixture
def failing_config_repo(mocker):
    """Mock ConfigRepository that raises exception."""
    mock = mocker.AsyncMock(spec=ConfigRepository)
    mock.get_hold_duration_scalper_max.side_effect = Exception("DB error")
    mock.get_hold_duration_day_trader_max.side_effect = Exception("DB error")
    mock.get_hold_duration_swing_trader_max.side_effect = Exception("DB error")
    return mock
