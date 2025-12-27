"""Multi-source price oracle with fallback and caching.

Implements Story 10.5-6: Price Oracle - Multi-Source Aggregator.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import TYPE_CHECKING, Optional, Protocol

import structlog
from cachetools import TTLCache

if TYPE_CHECKING:
    from walltrack.services.birdeye.client import BirdeyeClient
    from walltrack.services.dexscreener.client import DexScreenerClient
    from walltrack.services.jupiter.client import JupiterClient

logger = structlog.get_logger(__name__)


class PriceSource(str, Enum):
    """Available price sources in priority order."""

    DEXSCREENER = "dexscreener"
    BIRDEYE = "birdeye"
    JUPITER = "jupiter"


@dataclass
class PriceResult:
    """Result of a price fetch operation."""

    success: bool
    price: Decimal | None = None
    source: PriceSource | str | None = None
    timestamp: datetime | None = None
    error: str | None = None

    @property
    def age_seconds(self) -> float:
        """Age of price in seconds."""
        if self.timestamp is None:
            return float("inf")
        return (datetime.now(UTC) - self.timestamp).total_seconds()


class PriceProvider(Protocol):
    """Protocol for price providers."""

    async def get_price(self, token_address: str) -> Decimal | None:
        """Get price for a single token."""
        ...

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        """Get prices for multiple tokens."""
        ...


@dataclass
class DexScreenerProvider:
    """DexScreener price provider."""

    client: DexScreenerClient

    async def get_price(self, token_address: str) -> Decimal | None:
        """Get price from DexScreener."""
        try:
            result = await self.client.fetch_token(token_address)
            if result.success and result.token:
                price = result.token.price_usd
                if price and price > 0:
                    return Decimal(str(price))
        except Exception as e:
            logger.debug("dexscreener_price_error", token=token_address[:8], error=str(e))
        return None

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        """Batch fetch from DexScreener (one by one for now)."""
        results: dict[str, Decimal] = {}
        for address in token_addresses:
            price = await self.get_price(address)
            if price is not None:
                results[address] = price
        return results


@dataclass
class BirdeyeProvider:
    """Birdeye price provider."""

    client: BirdeyeClient

    async def get_price(self, token_address: str) -> Decimal | None:
        """Get price from Birdeye."""
        try:
            result = await self.client.fetch_token(token_address)
            if result.success and result.token:
                price = result.token.price_usd
                if price and price > 0:
                    return Decimal(str(price))
        except Exception as e:
            logger.debug("birdeye_price_error", token=token_address[:8], error=str(e))
        return None

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        """Batch fetch from Birdeye (one by one for now)."""
        results: dict[str, Decimal] = {}
        for address in token_addresses:
            price = await self.get_price(address)
            if price is not None:
                results[address] = price
        return results


@dataclass
class JupiterPriceProvider:
    """Jupiter price provider using quotes."""

    client: JupiterClient
    sol_mint: str = field(default="So11111111111111111111111111111111111111112")

    async def get_price(self, token_address: str) -> Decimal | None:
        """Get price via Jupiter quote."""
        try:
            # Get quote for 1 SOL worth
            quote = await self.client.get_quote(
                input_mint=self.sol_mint,
                output_mint=token_address,
                amount=1_000_000_000,  # 1 SOL in lamports
                slippage_bps=100,
            )

            if quote and quote.output_amount > 0:
                # Price in SOL = 1 / tokens_per_sol
                tokens = Decimal(str(quote.output_amount)) / Decimal("1e9")
                if tokens > 0:
                    return Decimal("1") / tokens
        except Exception as e:
            logger.debug("jupiter_price_error", token=token_address[:8], error=str(e))
        return None

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, Decimal]:
        """Jupiter doesn't support batch, fall back to parallel individual calls."""
        results: dict[str, Decimal] = {}
        tasks = [self.get_price(addr) for addr in token_addresses]
        prices = await asyncio.gather(*tasks, return_exceptions=True)

        for addr, price in zip(token_addresses, prices):
            if isinstance(price, Decimal):
                results[addr] = price

        return results


@dataclass
class CachedPrice:
    """Cached price entry."""

    price: Decimal
    source: PriceSource
    timestamp: datetime


class PriceOracle:
    """
    Multi-source price oracle with caching and fallback.

    Fetches prices from multiple sources in priority order
    with automatic fallback on failure.
    """

    # Source priority order
    SOURCE_PRIORITY = [
        PriceSource.DEXSCREENER,
        PriceSource.BIRDEYE,
        PriceSource.JUPITER,
    ]

    # Price validation bounds
    MIN_VALID_PRICE = Decimal("1e-12")
    MAX_VALID_PRICE = Decimal("1e12")

    def __init__(
        self,
        providers: dict[PriceSource, PriceProvider] | None = None,
        cache_ttl_seconds: int = 5,
        cache_max_size: int = 5000,
        failure_cooldown_seconds: int = 30,
        # Legacy support for stub initialization
        jupiter_client: JupiterClient | None = None,
    ) -> None:
        """
        Initialize PriceOracle.

        Args:
            providers: Dict mapping source to provider implementation
            cache_ttl_seconds: How long to cache prices (default 5s)
            cache_max_size: Max entries in cache
            failure_cooldown_seconds: How long to skip failed sources
            jupiter_client: Legacy Jupiter client (for backwards compatibility)
        """
        self.providers = providers or {}
        self.cache_ttl = cache_ttl_seconds
        self._cache: TTLCache = TTLCache(maxsize=cache_max_size, ttl=cache_ttl_seconds)
        self._source_failures: dict[PriceSource, datetime] = {}
        self._failure_cooldown = timedelta(seconds=failure_cooldown_seconds)

        # Legacy support
        self._jupiter_client = jupiter_client

    async def get_price(self, token_address: str) -> PriceResult:
        """
        Get price for a token with fallback.

        Tries sources in priority order until one succeeds.

        Args:
            token_address: Token mint address

        Returns:
            PriceResult with price or error
        """
        log = logger.bind(token=token_address[:8])

        # Check cache first
        cached = self._cache.get(token_address)
        if cached is not None:
            log.debug("price_from_cache", source=cached.source.value)
            return PriceResult(
                success=True,
                price=cached.price,
                source=cached.source,
                timestamp=cached.timestamp,
            )

        # Ensure providers are initialized
        if not self.providers:
            await self._init_providers()

        # Try each source in order
        errors: list[str] = []
        for source in self.SOURCE_PRIORITY:
            # Skip sources in cooldown
            if self._is_source_in_cooldown(source):
                log.debug("source_in_cooldown", source=source.value)
                continue

            provider = self.providers.get(source)
            if provider is None:
                continue

            try:
                price = await provider.get_price(token_address)

                if price is not None and self._is_valid_price(price):
                    now = datetime.now(UTC)
                    result = PriceResult(
                        success=True,
                        price=price,
                        source=source,
                        timestamp=now,
                    )

                    # Cache the result
                    self._cache[token_address] = CachedPrice(
                        price=price,
                        source=source,
                        timestamp=now,
                    )

                    log.debug(
                        "price_fetched",
                        price=str(price),
                        source=source.value,
                    )

                    return result

                if price is not None:
                    errors.append(f"{source.value}: invalid price {price}")
                else:
                    errors.append(f"{source.value}: no price returned")

            except Exception as e:
                error_msg = f"{source.value}: {e}"
                errors.append(error_msg)
                log.warning(
                    "price_source_failed",
                    source=source.value,
                    error=str(e),
                )
                self._mark_source_failed(source)

        # All sources failed
        log.warning("all_price_sources_failed", errors=errors)
        return PriceResult(
            success=False,
            error=f"All sources failed: {'; '.join(errors)}",
        )

    async def get_prices_batch(
        self,
        token_addresses: list[str],
    ) -> dict[str, PriceResult]:
        """
        Get prices for multiple tokens efficiently.

        Uses batch API calls where supported.

        Args:
            token_addresses: List of token addresses

        Returns:
            Dict mapping token address to PriceResult
        """
        results: dict[str, PriceResult] = {}
        tokens_to_fetch: list[str] = []

        # Check cache first
        for address in token_addresses:
            cached = self._cache.get(address)
            if cached is not None:
                results[address] = PriceResult(
                    success=True,
                    price=cached.price,
                    source=cached.source,
                    timestamp=cached.timestamp,
                )
            else:
                tokens_to_fetch.append(address)

        if not tokens_to_fetch:
            return results

        # Ensure providers are initialized
        if not self.providers:
            await self._init_providers()

        # Try batch fetch from each source
        for source in self.SOURCE_PRIORITY:
            if not tokens_to_fetch:
                break

            if self._is_source_in_cooldown(source):
                continue

            provider = self.providers.get(source)
            if provider is None:
                continue

            try:
                batch_prices = await provider.get_prices_batch(tokens_to_fetch)

                fetched_addresses = []
                for address, price in batch_prices.items():
                    if self._is_valid_price(price):
                        now = datetime.now(UTC)
                        results[address] = PriceResult(
                            success=True,
                            price=price,
                            source=source,
                            timestamp=now,
                        )

                        self._cache[address] = CachedPrice(
                            price=price,
                            source=source,
                            timestamp=now,
                        )

                        fetched_addresses.append(address)

                # Remove fetched addresses from pending list
                for addr in fetched_addresses:
                    if addr in tokens_to_fetch:
                        tokens_to_fetch.remove(addr)

            except Exception as e:
                logger.warning(
                    "batch_price_source_failed",
                    source=source.value,
                    error=str(e),
                )
                self._mark_source_failed(source)

        # Mark remaining tokens as failed
        for address in tokens_to_fetch:
            results[address] = PriceResult(
                success=False,
                error="All sources failed",
            )

        return results

    async def _init_providers(self) -> None:
        """Lazy initialize providers."""
        try:
            from walltrack.services.birdeye.client import BirdeyeClient
            from walltrack.services.dexscreener.client import DexScreenerClient
            from walltrack.services.jupiter.client import get_jupiter_client

            self.providers = {
                PriceSource.DEXSCREENER: DexScreenerProvider(
                    client=DexScreenerClient(),
                ),
                PriceSource.BIRDEYE: BirdeyeProvider(
                    client=BirdeyeClient(),
                ),
                PriceSource.JUPITER: JupiterPriceProvider(
                    client=await get_jupiter_client(),
                ),
            }
        except Exception as e:
            logger.error("provider_init_failed", error=str(e))
            # Fall back to legacy Jupiter-only mode
            if self._jupiter_client:
                self.providers = {
                    PriceSource.JUPITER: JupiterPriceProvider(
                        client=self._jupiter_client,
                    ),
                }

    def _is_valid_price(self, price: Decimal) -> bool:
        """Check if price is within valid bounds."""
        return self.MIN_VALID_PRICE <= price <= self.MAX_VALID_PRICE

    def _is_source_in_cooldown(self, source: PriceSource) -> bool:
        """Check if source is in failure cooldown."""
        failure_time = self._source_failures.get(source)
        if failure_time is None:
            return False
        return datetime.now(UTC) - failure_time < self._failure_cooldown

    def _mark_source_failed(self, source: PriceSource) -> None:
        """Mark source as temporarily failed."""
        self._source_failures[source] = datetime.now(UTC)

    def clear_cache(self, token_address: str | None = None) -> None:
        """Clear cache for a specific token or all tokens."""
        if token_address:
            self._cache.pop(token_address, None)
        else:
            self._cache.clear()

    def reset_source_failures(self) -> None:
        """Reset all source failure states."""
        self._source_failures.clear()


# Singleton
_price_oracle: PriceOracle | None = None


async def get_price_oracle() -> PriceOracle:
    """Get or create price oracle singleton."""
    global _price_oracle

    if _price_oracle is None:
        _price_oracle = PriceOracle()

    return _price_oracle


def reset_price_oracle() -> None:
    """Reset the singleton (for testing)."""
    global _price_oracle
    _price_oracle = None
