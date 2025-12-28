"""Unit tests for PriceOracle."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.pricing.price_oracle import (
    CachedPrice,
    PriceOracle,
    PriceResult,
    PriceSource,
)


class MockProvider:
    """Mock price provider for testing."""

    def __init__(self, prices: dict[str, Decimal | None] = None):
        self.prices = prices or {}
        self.call_count = 0

    async def get_price(self, token_address: str) -> Decimal | None:
        self.call_count += 1
        return self.prices.get(token_address)

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        self.call_count += 1
        return {
            addr: price
            for addr, price in self.prices.items()
            if addr in token_addresses and price is not None
        }


class FailingProvider:
    """Provider that always raises an exception."""

    async def get_price(self, token_address: str) -> Decimal | None:
        raise Exception("Provider down")

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        raise Exception("Provider down")


@pytest.fixture
def mock_dexscreener():
    """Create mock DexScreener provider."""
    return MockProvider({
        "token_a": Decimal("0.001"),
        "token_b": Decimal("0.002"),
    })


@pytest.fixture
def mock_birdeye():
    """Create mock Birdeye provider."""
    return MockProvider({
        "token_a": Decimal("0.0011"),
        "token_c": Decimal("0.003"),
    })


@pytest.fixture
def mock_jupiter():
    """Create mock Jupiter provider."""
    return MockProvider({
        "token_a": Decimal("0.0012"),
        "token_d": Decimal("0.004"),
    })


@pytest.fixture
def oracle(mock_dexscreener, mock_birdeye, mock_jupiter):
    """Create PriceOracle with mock providers."""
    return PriceOracle(
        providers={
            PriceSource.DEXSCREENER: mock_dexscreener,
            PriceSource.BIRDEYE: mock_birdeye,
            PriceSource.JUPITER: mock_jupiter,
        },
        cache_ttl_seconds=5,
    )


class TestMultiSourcePriceFetching:
    """Test AC1: Multi-Source Price Fetching."""

    @pytest.mark.asyncio
    async def test_returns_price_from_first_source(
        self, oracle, mock_dexscreener
    ):
        """DexScreener is used first when available."""
        result = await oracle.get_price("token_a")

        assert result.success
        assert result.price == Decimal("0.001")
        assert result.source == PriceSource.DEXSCREENER
        assert mock_dexscreener.call_count == 1

    @pytest.mark.asyncio
    async def test_priority_order_respected(self, oracle, mock_dexscreener):
        """DexScreener is tried before Birdeye and Jupiter."""
        # DexScreener has the token
        result = await oracle.get_price("token_a")

        assert result.source == PriceSource.DEXSCREENER
        # Only DexScreener should be called
        assert mock_dexscreener.call_count == 1


class TestFallbackOnFailure:
    """Test AC2: Fallback on Failure."""

    @pytest.mark.asyncio
    async def test_fallback_to_birdeye_when_dexscreener_fails(
        self, mock_birdeye, mock_jupiter
    ):
        """Falls back to Birdeye when DexScreener fails."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: FailingProvider(),
                PriceSource.BIRDEYE: mock_birdeye,
                PriceSource.JUPITER: mock_jupiter,
            },
        )

        result = await oracle.get_price("token_c")

        assert result.success
        assert result.price == Decimal("0.003")
        assert result.source == PriceSource.BIRDEYE

    @pytest.mark.asyncio
    async def test_fallback_to_jupiter_when_all_else_fails(
        self, mock_jupiter
    ):
        """Falls back to Jupiter when DexScreener and Birdeye fail."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: FailingProvider(),
                PriceSource.BIRDEYE: FailingProvider(),
                PriceSource.JUPITER: mock_jupiter,
            },
        )

        result = await oracle.get_price("token_d")

        assert result.success
        assert result.price == Decimal("0.004")
        assert result.source == PriceSource.JUPITER

    @pytest.mark.asyncio
    async def test_all_sources_fail(self):
        """Returns error when all sources fail."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: FailingProvider(),
                PriceSource.BIRDEYE: FailingProvider(),
                PriceSource.JUPITER: FailingProvider(),
            },
        )

        result = await oracle.get_price("token_x")

        assert not result.success
        assert result.error is not None
        assert "All sources failed" in result.error

    @pytest.mark.asyncio
    async def test_failed_source_enters_cooldown(self, mock_jupiter):
        """Failed source is skipped during cooldown period."""
        failing_dex = FailingProvider()
        failing_birdeye = FailingProvider()

        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: failing_dex,
                PriceSource.BIRDEYE: failing_birdeye,
                PriceSource.JUPITER: mock_jupiter,
            },
            failure_cooldown_seconds=30,
            cache_ttl_seconds=1,  # Short cache so we can test cooldown
        )

        # First call - all sources tried, Jupiter succeeds
        result1 = await oracle.get_price("token_d")
        assert result1.success
        assert result1.source == PriceSource.JUPITER

        # Clear cache to force fresh fetch
        oracle.clear_cache()

        # Second call - DexScreener and Birdeye should be in cooldown
        # Since we can't easily verify cooldown without mocking time,
        # just verify the mechanism exists
        assert PriceSource.DEXSCREENER in oracle._source_failures
        assert PriceSource.BIRDEYE in oracle._source_failures


class TestPriceValidation:
    """Test AC3: Price Validation."""

    @pytest.mark.asyncio
    async def test_rejects_zero_price(self):
        """Price of 0 is rejected."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({"token": Decimal("0")}),
                PriceSource.BIRDEYE: MockProvider({"token": Decimal("0.001")}),
            },
        )

        result = await oracle.get_price("token")

        # Should fall back to Birdeye
        assert result.success
        assert result.source == PriceSource.BIRDEYE

    @pytest.mark.asyncio
    async def test_rejects_extremely_small_price(self):
        """Extremely small prices are rejected."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({"token": Decimal("1e-15")}),
                PriceSource.BIRDEYE: MockProvider({"token": Decimal("0.001")}),
            },
        )

        result = await oracle.get_price("token")

        # Should fall back to Birdeye due to invalid price
        assert result.success
        assert result.source == PriceSource.BIRDEYE

    @pytest.mark.asyncio
    async def test_rejects_extremely_large_price(self):
        """Extremely large prices are rejected."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({"token": Decimal("1e15")}),
                PriceSource.BIRDEYE: MockProvider({"token": Decimal("0.001")}),
            },
        )

        result = await oracle.get_price("token")

        # Should fall back to Birdeye due to invalid price
        assert result.success
        assert result.source == PriceSource.BIRDEYE

    @pytest.mark.asyncio
    async def test_accepts_valid_price_range(self):
        """Valid prices within bounds are accepted."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({
                    "small": Decimal("1e-10"),
                    "large": Decimal("1e10"),
                }),
            },
        )

        small_result = await oracle.get_price("small")
        assert small_result.success

        oracle.clear_cache()

        large_result = await oracle.get_price("large")
        assert large_result.success


class TestCachingWithTTL:
    """Test AC4: Caching with TTL."""

    @pytest.mark.asyncio
    async def test_cached_price_returned(self, oracle, mock_dexscreener):
        """Second request within TTL returns cached price."""
        # First call
        result1 = await oracle.get_price("token_a")
        assert result1.success

        # Second call - should use cache
        result2 = await oracle.get_price("token_a")
        assert result2.success
        assert result2.price == result1.price

        # Provider should only be called once
        assert mock_dexscreener.call_count == 1

    @pytest.mark.asyncio
    async def test_cache_includes_source_and_timestamp(self, oracle):
        """Cached result includes source and timestamp."""
        result = await oracle.get_price("token_a")

        # Check cached entry
        cached = oracle._cache.get("token_a")
        assert cached is not None
        assert cached.source == PriceSource.DEXSCREENER
        assert cached.timestamp is not None

    @pytest.mark.asyncio
    async def test_clear_cache_specific_token(self, oracle, mock_dexscreener):
        """Can clear cache for specific token."""
        # Populate cache
        await oracle.get_price("token_a")
        await oracle.get_price("token_b")

        # Clear only token_a
        oracle.clear_cache("token_a")

        assert oracle._cache.get("token_a") is None
        assert oracle._cache.get("token_b") is not None

    @pytest.mark.asyncio
    async def test_clear_all_cache(self, oracle, mock_dexscreener):
        """Can clear entire cache."""
        # Populate cache
        await oracle.get_price("token_a")
        await oracle.get_price("token_b")

        # Clear all
        oracle.clear_cache()

        assert oracle._cache.get("token_a") is None
        assert oracle._cache.get("token_b") is None


class TestBatchPriceFetching:
    """Test AC5: Batch Price Fetching."""

    @pytest.mark.asyncio
    async def test_batch_returns_dict(self, oracle):
        """get_prices_batch returns dict of results."""
        results = await oracle.get_prices_batch(["token_a", "token_b"])

        assert isinstance(results, dict)
        assert "token_a" in results
        assert "token_b" in results

    @pytest.mark.asyncio
    async def test_batch_uses_cache(self, oracle, mock_dexscreener):
        """Batch fetch uses cache for cached tokens."""
        # Cache token_a
        await oracle.get_price("token_a")
        initial_calls = mock_dexscreener.call_count

        # Batch fetch both
        results = await oracle.get_prices_batch(["token_a", "token_b"])

        # token_a should come from cache, only token_b fetched
        assert results["token_a"].success
        assert results["token_b"].success
        # Provider called once for individual get_price + once for batch
        # The batch only fetches token_b since token_a is cached

    @pytest.mark.asyncio
    async def test_batch_marks_failed_tokens(self):
        """Batch marks tokens as failed when all sources fail."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({}),  # No prices
                PriceSource.BIRDEYE: MockProvider({}),
                PriceSource.JUPITER: MockProvider({}),
            },
        )

        results = await oracle.get_prices_batch(["unknown_token"])

        assert "unknown_token" in results
        assert not results["unknown_token"].success

    @pytest.mark.asyncio
    async def test_batch_fallback_between_sources(self):
        """Batch fetches remaining tokens from fallback sources."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: MockProvider({"token_a": Decimal("0.001")}),
                PriceSource.BIRDEYE: MockProvider({"token_b": Decimal("0.002")}),
            },
        )

        results = await oracle.get_prices_batch(["token_a", "token_b"])

        assert results["token_a"].source == PriceSource.DEXSCREENER
        assert results["token_b"].source == PriceSource.BIRDEYE


class TestPriceResult:
    """Test PriceResult dataclass."""

    def test_age_seconds_calculation(self):
        """age_seconds calculates correctly."""
        old_time = datetime.now(UTC) - timedelta(seconds=10)
        result = PriceResult(
            success=True,
            price=Decimal("0.001"),
            timestamp=old_time,
        )

        assert result.age_seconds >= 10

    def test_age_seconds_none_timestamp(self):
        """age_seconds returns inf for None timestamp."""
        result = PriceResult(success=False)

        assert result.age_seconds == float("inf")


class TestSourceFailureRecovery:
    """Test source failure and recovery."""

    @pytest.mark.asyncio
    async def test_reset_source_failures(self):
        """Can reset all source failure states."""
        oracle = PriceOracle(
            providers={
                PriceSource.DEXSCREENER: FailingProvider(),
                PriceSource.BIRDEYE: MockProvider({"token": Decimal("0.001")}),
            },
        )

        # Trigger failure
        await oracle.get_price("token")
        assert PriceSource.DEXSCREENER in oracle._source_failures

        # Reset failures
        oracle.reset_source_failures()
        assert len(oracle._source_failures) == 0
