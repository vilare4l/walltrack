"""Unit tests for position sizing analysis.

Tests for calculating and classifying wallet position sizes from transaction history.
Story 3.3 - Task 6.
"""

from decimal import Decimal

import pytest

from walltrack.data.models.transaction import TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository
from walltrack.core.behavioral.position_sizing import (
    calculate_position_size_avg,
    classify_position_size,
)
from tests.unit.core.behavioral.conftest import (
    VALID_TOKEN_MINT_ABC,
    VALID_TOKEN_MINT_DEF,
)


class TestCalculatePositionSizeAvg:
    """Tests for calculate_position_size_avg function."""

    def test_calculates_average_from_buy_transactions(self, swap_transaction_factory):
        """Should calculate average SOL amount from BUY transactions only."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=1.5,
                token_amount=100.0,
            ),
            swap_transaction_factory(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                token_mint=VALID_TOKEN_MINT_DEF,
                sol_amount=2.5,
                token_amount=200.0,
            ),
            swap_transaction_factory(
                signature="sig3",
                timestamp=3000,
                tx_type=TransactionType.SELL,
                token_mint=VALID_TOKEN_MINT_ABC,
                sol_amount=3.0,
                token_amount=100.0,
            ),
        ]

        result = calculate_position_size_avg(transactions)

        # Average of 1.5 and 2.5 = 2.0
        assert result == Decimal("2.00000000")

    def test_returns_zero_for_no_buy_transactions(self, swap_transaction_factory):
        """Should return 0 when no BUY transactions exist."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.SELL,
                sol_amount=3.0,
            ),
        ]

        result = calculate_position_size_avg(transactions)

        assert result == Decimal("0")

    def test_returns_zero_for_empty_list(self):
        """Should return 0 for empty transaction list."""
        result = calculate_position_size_avg([])
        assert result == Decimal("0")

    def test_very_small_position_sizes(self, swap_transaction_factory):
        """Should handle very small position sizes correctly."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                sol_amount=0.05,
            ),
            swap_transaction_factory(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                sol_amount=0.15,
            ),
        ]

        result = calculate_position_size_avg(transactions)

        # Average of 0.05 and 0.15 = 0.1
        assert result == Decimal("0.10000000")

    def test_very_large_position_sizes(self, swap_transaction_factory):
        """Should handle very large position sizes correctly."""
        transactions = [
            swap_transaction_factory(
                signature="sig1",
                timestamp=1000,
                tx_type=TransactionType.BUY,
                sol_amount=50.0,
            ),
            swap_transaction_factory(
                signature="sig2",
                timestamp=2000,
                tx_type=TransactionType.BUY,
                sol_amount=100.0,
            ),
        ]

        result = calculate_position_size_avg(transactions)

        # Average of 50.0 and 100.0 = 75.0
        assert result == Decimal("75.00000000")


class TestClassifyPositionSize:
    """Tests for classify_position_size function."""

    @pytest.mark.asyncio
    async def test_classifies_small_position_below_threshold(self, mock_config_repo):
        """Should classify position as small when <= small_max threshold."""
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0

        result = await classify_position_size(Decimal("0.3"), mock_config_repo)

        assert result == "small"

    @pytest.mark.asyncio
    async def test_classifies_small_position_at_threshold(self, mock_config_repo):
        """Should classify position as small when exactly at small_max threshold."""
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0

        result = await classify_position_size(Decimal("0.5"), mock_config_repo)

        assert result == "small"

    @pytest.mark.asyncio
    async def test_classifies_medium_position(self, mock_config_repo):
        """Should classify position as medium when between small_max and medium_max."""
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0

        result = await classify_position_size(Decimal("1.0"), mock_config_repo)

        assert result == "medium"

    @pytest.mark.asyncio
    async def test_classifies_medium_position_at_upper_threshold(self, mock_config_repo):
        """Should classify position as medium when exactly at medium_max threshold."""
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0

        result = await classify_position_size(Decimal("2.0"), mock_config_repo)

        assert result == "medium"

    @pytest.mark.asyncio
    async def test_classifies_large_position(self, mock_config_repo):
        """Should classify position as large when > medium_max threshold."""
        mock_config_repo.get_position_size_small_max.return_value = 0.5
        mock_config_repo.get_position_size_medium_max.return_value = 2.0

        result = await classify_position_size(Decimal("5.0"), mock_config_repo)

        assert result == "large"

    @pytest.mark.asyncio
    async def test_uses_fallback_defaults_on_config_error(self, failing_config_repo):
        """Should use hardcoded defaults when config fetch fails."""
        result = await classify_position_size(Decimal("0.8"), failing_config_repo)

        # With fallback defaults (small_max=1.0, medium_max=5.0), 0.8 is small
        assert result == "small"


@pytest.fixture
def mock_config_repo(mocker):
    """Mock ConfigRepository for testing."""
    mock = mocker.AsyncMock(spec=ConfigRepository)
    return mock


@pytest.fixture
def failing_config_repo(mocker):
    """Mock ConfigRepository that raises exception."""
    mock = mocker.AsyncMock(spec=ConfigRepository)
    mock.get_position_size_small_max.side_effect = Exception("DB error")
    mock.get_position_size_medium_max.side_effect = Exception("DB error")
    return mock
