"""Tests for explorer tokens display functionality.

Tests for Story 2.3: Token Explorer View.
Covers formatting functions and data fetching layer.
"""

from unittest.mock import AsyncMock, MagicMock, patch


class TestFormatPrice:
    """Tests for _format_price() utility function."""

    def test_format_price_very_small(self) -> None:
        """
        Given: A very small price value (< 0.0001)
        When: _format_price() is called
        Then: Returns price with 8 decimal places
        """
        from walltrack.ui.pages.explorer import _format_price

        result = _format_price(0.00001234)
        assert result == "$0.00001234"

    def test_format_price_small(self) -> None:
        """
        Given: A small price value (0.0001 to 0.01)
        When: _format_price() is called
        Then: Returns price with 6 decimal places
        """
        from walltrack.ui.pages.explorer import _format_price

        result = _format_price(0.005678)
        assert result == "$0.005678"

    def test_format_price_medium(self) -> None:
        """
        Given: A medium price value (0.01 to 1)
        When: _format_price() is called
        Then: Returns price with 4 decimal places
        """
        from walltrack.ui.pages.explorer import _format_price

        result = _format_price(0.1234)
        assert result == "$0.1234"

    def test_format_price_large(self) -> None:
        """
        Given: A normal price value (>= 1)
        When: _format_price() is called
        Then: Returns price with 2 decimal places
        """
        from walltrack.ui.pages.explorer import _format_price

        result = _format_price(123.456)
        assert result == "$123.46"

    def test_format_price_none(self) -> None:
        """
        Given: None value
        When: _format_price() is called
        Then: Returns 'N/A'
        """
        from walltrack.ui.pages.explorer import _format_price

        result = _format_price(None)
        assert result == "N/A"


class TestFormatMarketCap:
    """Tests for _format_market_cap() utility function."""

    def test_format_market_cap_billions(self) -> None:
        """
        Given: A value in billions
        When: _format_market_cap() is called
        Then: Returns value with B suffix
        """
        from walltrack.ui.pages.explorer import _format_market_cap

        result = _format_market_cap(1_500_000_000)
        assert result == "$1.5B"

    def test_format_market_cap_millions(self) -> None:
        """
        Given: A value in millions
        When: _format_market_cap() is called
        Then: Returns value with M suffix
        """
        from walltrack.ui.pages.explorer import _format_market_cap

        result = _format_market_cap(2_500_000)
        assert result == "$2.5M"

    def test_format_market_cap_thousands(self) -> None:
        """
        Given: A value in thousands
        When: _format_market_cap() is called
        Then: Returns value with K suffix
        """
        from walltrack.ui.pages.explorer import _format_market_cap

        result = _format_market_cap(45_000)
        assert result == "$45.0K"

    def test_format_market_cap_small(self) -> None:
        """
        Given: A value under 1000
        When: _format_market_cap() is called
        Then: Returns value without suffix
        """
        from walltrack.ui.pages.explorer import _format_market_cap

        result = _format_market_cap(500)
        assert result == "$500"

    def test_format_market_cap_none(self) -> None:
        """
        Given: None value
        When: _format_market_cap() is called
        Then: Returns 'N/A'
        """
        from walltrack.ui.pages.explorer import _format_market_cap

        result = _format_market_cap(None)
        assert result == "N/A"


class TestFormatAge:
    """Tests for _format_age() utility function."""

    def test_format_age_minutes(self) -> None:
        """
        Given: Age less than 60 minutes
        When: _format_age() is called
        Then: Returns value with m suffix
        """
        from walltrack.ui.pages.explorer import _format_age

        result = _format_age(45)
        assert result == "45m"

    def test_format_age_hours(self) -> None:
        """
        Given: Age between 60 minutes and 24 hours
        When: _format_age() is called
        Then: Returns value with h suffix
        """
        from walltrack.ui.pages.explorer import _format_age

        result = _format_age(180)
        assert result == "3h"

    def test_format_age_days(self) -> None:
        """
        Given: Age of exactly 2 days (2880 minutes)
        When: _format_age() is called
        Then: Returns value with d suffix only
        """
        from walltrack.ui.pages.explorer import _format_age

        result = _format_age(2880)
        assert result == "2d"

    def test_format_age_days_hours(self) -> None:
        """
        Given: Age with days and remaining hours
        When: _format_age() is called
        Then: Returns value with d and h suffix
        """
        from walltrack.ui.pages.explorer import _format_age

        result = _format_age(3000)  # 2 days 2 hours
        assert result == "2d 2h"

    def test_format_age_none(self) -> None:
        """
        Given: None value
        When: _format_age() is called
        Then: Returns 'N/A'
        """
        from walltrack.ui.pages.explorer import _format_age

        result = _format_age(None)
        assert result == "N/A"


class TestFetchAndFormatTokens:
    """Tests for _fetch_tokens() and _format_tokens_for_table() functions."""

    def test_fetch_tokens_empty(self) -> None:
        """
        Given: No tokens in database
        When: _fetch_tokens() is called
        Then: Returns empty list
        """
        from walltrack.ui.pages.explorer import _fetch_tokens

        mock_repo = MagicMock()
        mock_repo.get_all = AsyncMock(return_value=[])

        with (
            patch(
                "walltrack.data.supabase.repositories.token_repo.TokenRepository",
                return_value=mock_repo,
            ),
            patch(
                "walltrack.data.supabase.client.get_supabase_client",
                return_value=AsyncMock(),
            ),
        ):
            result = _fetch_tokens()

        assert result == []

    def test_format_tokens_for_table(self) -> None:
        """
        Given: Tokens exist
        When: _format_tokens_for_table() is called
        Then: Returns formatted list for table display
        """
        from walltrack.data.models.token import Token
        from walltrack.ui.pages.explorer import _format_tokens_for_table

        mock_token = Token(
            mint="abc123def456",
            name="Test Token",
            symbol="TEST",
            price_usd=0.001234,
            market_cap=1500000,
            liquidity_usd=50000,
            age_minutes=2880,
        )

        result = _format_tokens_for_table([mock_token])

        assert len(result) == 1
        row = result[0]
        assert row[0] == "Test Token"  # Name
        assert row[1] == "TEST"  # Symbol
        assert "$0.001234" in row[2]  # Price
        assert "$1.5M" in row[3]  # Market Cap
        assert "2d" in row[4]  # Age
        assert row[5] == "N/A"  # Wallets (TODO: Story 3.1)

    def test_format_tokens_handles_unknown_values(self) -> None:
        """
        Given: Token with None values for name/symbol
        When: _format_tokens_for_table() is called
        Then: Returns 'Unknown' and '???' for missing values
        """
        from walltrack.data.models.token import Token
        from walltrack.ui.pages.explorer import _format_tokens_for_table

        mock_token = Token(
            mint="abc123",
            name=None,
            symbol=None,
            price_usd=None,
            market_cap=None,
            liquidity_usd=None,
            age_minutes=None,
        )

        result = _format_tokens_for_table([mock_token])

        assert len(result) == 1
        row = result[0]
        assert row[0] == "Unknown"  # Name
        assert row[1] == "???"  # Symbol
        assert row[2] == "N/A"  # Price
        assert row[3] == "N/A"  # Market Cap
        assert row[4] == "N/A"  # Age
        assert row[5] == "N/A"  # Wallets

    def test_fetch_tokens_handles_error(self) -> None:
        """
        Given: Database error occurs
        When: _fetch_tokens() is called
        Then: Returns empty list (graceful degradation)
        """
        from walltrack.ui.pages.explorer import _fetch_tokens

        with (
            patch(
                "walltrack.data.supabase.client.get_supabase_client",
                side_effect=Exception("Connection failed"),
            ),
        ):
            result = _fetch_tokens()

        assert result == []
