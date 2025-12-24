"""Tests for real-time P&L calculator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestPriceCache:
    """Tests for PriceCache dataclass."""

    def test_price_cache_creation(self) -> None:
        """Test PriceCache can be created with required fields."""
        from walltrack.core.simulation.pnl_calculator import PriceCache

        cache = PriceCache(
            price=Decimal("0.001"),
            fetched_at=datetime.now(UTC),
        )
        assert cache.price == Decimal("0.001")
        assert cache.is_stale is False

    def test_price_cache_age_seconds(self) -> None:
        """Test age_seconds property calculates correctly."""
        from walltrack.core.simulation.pnl_calculator import PriceCache

        old_time = datetime.now(UTC) - timedelta(seconds=60)
        cache = PriceCache(
            price=Decimal("0.001"),
            fetched_at=old_time,
        )
        assert cache.age_seconds >= 60
        assert cache.age_seconds < 62  # Some tolerance


class TestPortfolioPnL:
    """Tests for PortfolioPnL dataclass."""

    def test_portfolio_pnl_creation(self) -> None:
        """Test PortfolioPnL can be created."""
        from walltrack.core.simulation.pnl_calculator import PortfolioPnL

        pnl = PortfolioPnL(
            total_unrealized_pnl=Decimal("100"),
            total_realized_pnl=Decimal("50"),
            total_pnl=Decimal("150"),
            position_count=3,
            positions_with_stale_prices=1,
            calculated_at=datetime.now(UTC),
        )
        assert pnl.total_pnl == Decimal("150")
        assert pnl.position_count == 3


class TestSimulationPnLCalculator:
    """Tests for SimulationPnLCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create a P&L calculator instance."""
        from walltrack.core.simulation.pnl_calculator import SimulationPnLCalculator

        return SimulationPnLCalculator(cache_ttl_seconds=30)

    @pytest.fixture
    def mock_dex_client(self) -> MagicMock:
        """Create mock DexScreener client."""
        mock = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.token = MagicMock()
        mock_result.token.price_usd = 0.002
        mock.fetch_token = AsyncMock(return_value=mock_result)
        return mock


class TestGetCurrentPrice(TestSimulationPnLCalculator):
    """Tests for _get_current_price method."""

    async def test_fetches_fresh_price(
        self,
        calculator,
        mock_dex_client: MagicMock,
    ) -> None:
        """Test that fresh price is fetched when cache is empty."""
        with patch(
            "walltrack.core.simulation.pnl_calculator.DexScreenerClient",
            return_value=mock_dex_client,
        ):
            price_cache = await calculator._get_current_price(
                "TestToken1111111111111111111111111111111111"
            )

            assert price_cache.price == Decimal("0.002")
            assert price_cache.is_stale is False

    async def test_returns_cached_price_when_valid(
        self,
        calculator,
        mock_dex_client: MagicMock,
    ) -> None:
        """Test that cached price is returned when still valid."""
        from walltrack.core.simulation.pnl_calculator import PriceCache

        token = "TestToken1111111111111111111111111111111111"
        calculator._price_cache[token] = PriceCache(
            price=Decimal("0.001"),
            fetched_at=datetime.now(UTC),
        )

        price_cache = await calculator._get_current_price(token)

        # Should return cached price without calling API
        mock_dex_client.fetch_token.assert_not_called()
        assert price_cache.price == Decimal("0.001")

    async def test_returns_stale_price_on_api_failure(
        self,
        calculator,
        mock_dex_client: MagicMock,
    ) -> None:
        """Test that stale price is returned when API fails."""
        from walltrack.core.simulation.pnl_calculator import PriceCache

        token = "TestToken1111111111111111111111111111111111"

        # Set old cache entry
        calculator._price_cache[token] = PriceCache(
            price=Decimal("0.001"),
            fetched_at=datetime.now(UTC) - timedelta(seconds=60),
        )

        # Make API fail
        mock_dex_client.fetch_token = AsyncMock(side_effect=Exception("API error"))

        with patch(
            "walltrack.core.simulation.pnl_calculator.DexScreenerClient",
            return_value=mock_dex_client,
        ):
            price_cache = await calculator._get_current_price(token)

            assert price_cache.price == Decimal("0.001")
            assert price_cache.is_stale is True


class TestCalculatePortfolioPnL(TestSimulationPnLCalculator):
    """Tests for calculate_portfolio_pnl method."""

    async def test_calculates_unrealized_pnl(
        self,
        calculator,
        mock_dex_client: MagicMock,
    ) -> None:
        """Test unrealized P&L calculation."""
        from walltrack.core.simulation.pnl_calculator import PriceCache
        from walltrack.models.position import Position, PositionStatus

        # Mock position service
        mock_position = MagicMock(spec=Position)
        mock_position.token_address = "TestToken1111111111111111111111111111111111"
        mock_position.entry_price = 0.001
        mock_position.current_amount_tokens = 100000.0
        mock_position.simulated = True
        mock_position.status = PositionStatus.OPEN

        mock_position_service = MagicMock()
        mock_position_service.get_active_positions = AsyncMock(
            return_value=[mock_position]
        )
        mock_position_service.get_all_simulated_positions = AsyncMock(return_value=[])

        # Set cached price (2x entry)
        calculator._price_cache["TestToken1111111111111111111111111111111111"] = (
            PriceCache(
                price=Decimal("0.002"),
                fetched_at=datetime.now(UTC),
            )
        )

        with patch(
            "walltrack.core.simulation.pnl_calculator.get_position_service",
            return_value=mock_position_service,
        ):
            portfolio = await calculator.calculate_portfolio_pnl()

            # Entry: 0.001 * 100000 = $100
            # Current: 0.002 * 100000 = $200
            # Unrealized P&L = $100
            assert portfolio.total_unrealized_pnl == Decimal("100")
            assert portfolio.position_count == 1

    async def test_calculates_realized_pnl(
        self,
        calculator,
    ) -> None:
        """Test realized P&L from closed positions."""
        mock_closed_position = MagicMock()
        mock_closed_position.realized_pnl_sol = 1.5
        mock_closed_position.simulated = True
        mock_closed_position.status = "closed"

        mock_position_service = MagicMock()
        mock_position_service.get_active_positions = AsyncMock(return_value=[])
        mock_position_service.get_all_simulated_positions = AsyncMock(
            return_value=[mock_closed_position]
        )

        with patch(
            "walltrack.core.simulation.pnl_calculator.get_position_service",
            return_value=mock_position_service,
        ):
            portfolio = await calculator.calculate_portfolio_pnl()

            assert portfolio.position_count == 0


class TestClearCache(TestSimulationPnLCalculator):
    """Tests for clear_cache method."""

    async def test_clears_all_cached_prices(self, calculator) -> None:
        """Test that clear_cache empties the price cache."""
        from walltrack.core.simulation.pnl_calculator import PriceCache

        calculator._price_cache["token1"] = PriceCache(
            price=Decimal("0.001"),
            fetched_at=datetime.now(UTC),
        )
        calculator._price_cache["token2"] = PriceCache(
            price=Decimal("0.002"),
            fetched_at=datetime.now(UTC),
        )

        calculator.clear_cache()

        assert len(calculator._price_cache) == 0


class TestGetPnLCalculator:
    """Tests for get_pnl_calculator singleton."""

    async def test_returns_singleton_instance(self) -> None:
        """Test that get_pnl_calculator returns the same instance."""
        from walltrack.core.simulation.pnl_calculator import (
            SimulationPnLCalculator,
            get_pnl_calculator,
        )

        # Reset singleton
        import walltrack.core.simulation.pnl_calculator as module

        module._pnl_calculator = None

        calc1 = await get_pnl_calculator()
        calc2 = await get_pnl_calculator()

        assert calc1 is calc2
        assert isinstance(calc1, SimulationPnLCalculator)
