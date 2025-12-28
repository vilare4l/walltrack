"""Real-time P&L calculator for simulated positions."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import structlog

from walltrack.services.dexscreener.client import DexScreenerClient
from walltrack.services.position_service import get_position_service

log = structlog.get_logger()


@dataclass
class PriceCache:
    """Cached price with timestamp."""

    price: Decimal
    fetched_at: datetime
    is_stale: bool = False

    @property
    def age_seconds(self) -> float:
        """Get age of cached price in seconds."""
        return (datetime.now(UTC) - self.fetched_at).total_seconds()


@dataclass
class PortfolioPnL:
    """Portfolio-level P&L summary."""

    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal
    total_pnl: Decimal
    position_count: int
    positions_with_stale_prices: int
    calculated_at: datetime


class SimulationPnLCalculator:
    """Calculate real-time P&L for simulated positions."""

    def __init__(self, cache_ttl_seconds: int = 30) -> None:
        """Initialize P&L calculator.

        Args:
            cache_ttl_seconds: Time-to-live for price cache in seconds
        """
        self._price_cache: dict[str, PriceCache] = {}
        self._cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self._dex_client: DexScreenerClient | None = None

    async def _get_dex_client(self) -> DexScreenerClient:
        """Get or create DexScreener client."""
        if self._dex_client is None:
            self._dex_client = DexScreenerClient()
        return self._dex_client

    async def _get_current_price(self, token_address: str) -> PriceCache:
        """Get current price with caching.

        Args:
            token_address: Token mint address

        Returns:
            PriceCache with current or stale price

        Raises:
            ValueError: If no price available (fresh or cached)
        """
        # Check cache
        if token_address in self._price_cache:
            cached = self._price_cache[token_address]
            if cached.age_seconds < self._cache_ttl.total_seconds():
                return cached

        # Fetch fresh price
        try:
            dex_client = await self._get_dex_client()
            result = await dex_client.fetch_token(token_address)

            if result.success and result.token and result.token.price_usd:
                price_cache = PriceCache(
                    price=Decimal(str(result.token.price_usd)),
                    fetched_at=datetime.now(UTC),
                    is_stale=False,
                )
                self._price_cache[token_address] = price_cache
                return price_cache

        except Exception as e:
            log.warning(
                "price_fetch_failed",
                token=token_address[:8],
                error=str(e),
            )

        # Return stale price if available
        if token_address in self._price_cache:
            cached = self._price_cache[token_address]
            cached.is_stale = True
            return cached

        raise ValueError(f"No price available for {token_address}")

    async def calculate_portfolio_pnl(
        self,
        simulated: bool = True,
    ) -> PortfolioPnL:
        """Calculate total portfolio P&L.

        Args:
            simulated: Filter by simulation status

        Returns:
            PortfolioPnL with aggregated P&L data
        """
        position_service = await get_position_service()

        # Get open positions
        open_positions = await position_service.get_active_positions(
            simulated=simulated,
        )

        # Get all simulated positions for realized P&L
        all_positions = await position_service.get_all_simulated_positions()
        closed_positions = [
            p for p in all_positions if p.realized_pnl_sol is not None
        ]

        # Calculate unrealized P&L
        total_unrealized = Decimal(0)
        stale_count = 0

        for position in open_positions:
            try:
                price_cache = await self._get_current_price(position.token_address)
                current_value = price_cache.price * Decimal(
                    str(position.current_amount_tokens)
                )
                entry_value = Decimal(str(position.entry_price)) * Decimal(
                    str(position.current_amount_tokens)
                )
                total_unrealized += current_value - entry_value

                if price_cache.is_stale:
                    stale_count += 1
            except Exception as e:
                log.warning(
                    "pnl_calculation_failed",
                    token=position.token_address[:8],
                    error=str(e),
                )
                stale_count += 1

        # Calculate realized P&L
        total_realized = Decimal(0)
        for p in closed_positions:
            if p.realized_pnl_sol:
                total_realized += Decimal(str(p.realized_pnl_sol))

        return PortfolioPnL(
            total_unrealized_pnl=total_unrealized,
            total_realized_pnl=total_realized,
            total_pnl=total_unrealized + total_realized,
            position_count=len(open_positions),
            positions_with_stale_prices=stale_count,
            calculated_at=datetime.now(UTC),
        )

    def clear_cache(self) -> None:
        """Clear price cache."""
        self._price_cache.clear()


# Singleton
_pnl_calculator: SimulationPnLCalculator | None = None


async def get_pnl_calculator() -> SimulationPnLCalculator:
    """Get P&L calculator singleton."""
    global _pnl_calculator
    if _pnl_calculator is None:
        _pnl_calculator = SimulationPnLCalculator()
    return _pnl_calculator
