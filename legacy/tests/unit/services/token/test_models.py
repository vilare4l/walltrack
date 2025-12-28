"""Unit tests for token domain models."""

from datetime import UTC, datetime, timedelta

import pytest

from walltrack.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenPriceChange,
    TokenSource,
    TokenTransactions,
    TokenVolume,
)


class TestTokenSource:
    """Tests for TokenSource enum."""

    def test_source_values(self):
        """Test TokenSource has expected values."""
        assert TokenSource.DEXSCREENER.value == "dexscreener"
        assert TokenSource.BIRDEYE.value == "birdeye"
        assert TokenSource.CACHE.value == "cache"
        assert TokenSource.FALLBACK_NEUTRAL.value == "fallback_neutral"


class TestTokenLiquidity:
    """Tests for TokenLiquidity model."""

    def test_default_values(self):
        """Test default liquidity values."""
        liq = TokenLiquidity()
        assert liq.usd == 0.0
        assert liq.base == 0.0
        assert liq.quote == 0.0

    def test_custom_values(self):
        """Test custom liquidity values."""
        liq = TokenLiquidity(usd=50000.0, base=1000000.0, quote=500.0)
        assert liq.usd == 50000.0
        assert liq.base == 1000000.0
        assert liq.quote == 500.0


class TestTokenPriceChange:
    """Tests for TokenPriceChange model."""

    def test_default_values(self):
        """Test default price change values."""
        pc = TokenPriceChange()
        assert pc.m5 is None
        assert pc.h1 is None
        assert pc.h6 is None
        assert pc.h24 is None

    def test_custom_values(self):
        """Test custom price change values."""
        pc = TokenPriceChange(m5=5.5, h1=-2.3, h6=10.0, h24=25.0)
        assert pc.m5 == 5.5
        assert pc.h1 == -2.3
        assert pc.h6 == 10.0
        assert pc.h24 == 25.0


class TestTokenVolume:
    """Tests for TokenVolume model."""

    def test_default_values(self):
        """Test default volume values."""
        vol = TokenVolume()
        assert vol.m5 == 0.0
        assert vol.h1 == 0.0
        assert vol.h6 == 0.0
        assert vol.h24 == 0.0


class TestTokenTransactions:
    """Tests for TokenTransactions model."""

    def test_default_values(self):
        """Test default transaction values."""
        txns = TokenTransactions()
        assert txns.buys == 0
        assert txns.sells == 0
        assert txns.total == 0

    def test_buy_sell_ratio_normal(self):
        """Test buy/sell ratio calculation."""
        txns = TokenTransactions(buys=100, sells=50, total=150)
        assert txns.buy_sell_ratio == 2.0

    def test_buy_sell_ratio_zero_sells(self):
        """Test buy/sell ratio with zero sells."""
        txns = TokenTransactions(buys=100, sells=0, total=100)
        assert txns.buy_sell_ratio == float("inf")

    def test_buy_sell_ratio_zero_both(self):
        """Test buy/sell ratio with zero both."""
        txns = TokenTransactions(buys=0, sells=0, total=0)
        assert txns.buy_sell_ratio == 1.0


class TestTokenCharacteristics:
    """Tests for TokenCharacteristics model."""

    def test_minimum_required_fields(self):
        """Test token with minimum required fields."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012"
        )

        assert token.token_address == "TokenMint12345678901234567890123456789012"
        assert token.name is None
        assert token.symbol is None
        assert token.price_usd == 0.0
        assert token.is_new_token is False
        assert token.source == TokenSource.DEXSCREENER

    def test_full_token_data(self):
        """Test token with full data."""
        now = datetime.now(UTC)
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            name="Test Token",
            symbol="TEST",
            price_usd=0.001,
            price_sol=0.0001,
            market_cap_usd=100000,
            fdv_usd=150000,
            liquidity=TokenLiquidity(usd=50000),
            volume=TokenVolume(h24=25000),
            age_minutes=30,
            is_new_token=False,
            holder_count=1000,
            source=TokenSource.DEXSCREENER,
            fetched_at=now,
        )

        assert token.name == "Test Token"
        assert token.symbol == "TEST"
        assert token.market_cap_usd == 100000
        assert token.liquidity.usd == 50000
        assert token.holder_count == 1000

    def test_address_validation_too_short(self):
        """Test address validation rejects short addresses."""
        with pytest.raises(ValueError):
            TokenCharacteristics(token_address="short")

    def test_address_validation_too_long(self):
        """Test address validation rejects long addresses."""
        with pytest.raises(ValueError):
            TokenCharacteristics(token_address="x" * 50)

    def test_is_cache_valid_not_expired(self):
        """Test cache validity for fresh entry."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            fetched_at=datetime.now(UTC),
            cache_ttl_seconds=300,
        )

        assert token.is_cache_valid() is True

    def test_is_cache_valid_expired(self):
        """Test cache validity for expired entry."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            fetched_at=datetime.now(UTC) - timedelta(seconds=400),
            cache_ttl_seconds=300,
        )

        assert token.is_cache_valid() is False


class TestTokenFetchResult:
    """Tests for TokenFetchResult model."""

    def test_success_result(self):
        """Test successful fetch result."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
        )
        result = TokenFetchResult(
            success=True,
            token=token,
            source=TokenSource.DEXSCREENER,
            fetch_time_ms=50.0,
        )

        assert result.success is True
        assert result.token is not None
        assert result.source == TokenSource.DEXSCREENER
        assert result.fetch_time_ms == 50.0
        assert result.used_fallback is False

    def test_failure_result(self):
        """Test failed fetch result."""
        result = TokenFetchResult(
            success=False,
            token=None,
            source=TokenSource.DEXSCREENER,
            error_message="Timeout",
        )

        assert result.success is False
        assert result.token is None
        assert result.error_message == "Timeout"

    def test_fallback_result(self):
        """Test fallback fetch result."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            source=TokenSource.BIRDEYE,
        )
        result = TokenFetchResult(
            success=True,
            token=token,
            source=TokenSource.BIRDEYE,
            used_fallback=True,
        )

        assert result.success is True
        assert result.used_fallback is True
        assert result.source == TokenSource.BIRDEYE


class TestNewTokenHandling:
    """Tests for new token flag handling (AC4)."""

    def test_new_token_under_10_minutes(self):
        """Test token < 10 minutes old is marked as new."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            created_at=datetime.now(UTC) - timedelta(minutes=5),
            age_minutes=5,
            is_new_token=True,
        )

        assert token.is_new_token is True
        assert token.age_minutes == 5

    def test_established_token_over_10_minutes(self):
        """Test token > 10 minutes old is not marked as new."""
        token = TokenCharacteristics(
            token_address="TokenMint12345678901234567890123456789012",
            created_at=datetime.now(UTC) - timedelta(hours=1),
            age_minutes=60,
            is_new_token=False,
        )

        assert token.is_new_token is False
        assert token.age_minutes == 60
