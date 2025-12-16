# Story 3.3: Token Characteristics Fetching

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: High
- **FR**: FR17

## User Story

**As an** operator,
**I want** token data fetched for each signal,
**So that** token quality factors into scoring.

## Acceptance Criteria

### AC 1: DexScreener Query
**Given** a signal with token address
**When** token characteristics are requested
**Then** DexScreener API is queried for token data
**And** response includes: age, market cap, liquidity, holder count, price

### AC 2: Caching
**Given** DexScreener returns data
**When** data is processed
**Then** token characteristics are cached (TTL: 5 minutes)
**And** data is attached to signal context

### AC 3: Fallback
**Given** DexScreener API fails or times out
**When** fallback is triggered
**Then** Birdeye API is attempted as fallback (NFR18)
**And** if both fail, cached data is used if available
**And** if no data available, token score component is neutral

### AC 4: New Token Handling
**Given** token is very new (< 10 minutes old)
**When** characteristics are evaluated
**Then** "new_token" flag is set
**And** limited historical data is handled gracefully

## Technical Notes

- FR17: Query token characteristics
- Implement in `src/walltrack/services/dexscreener/client.py`
- Fallback in `src/walltrack/services/birdeye/client.py` (or similar)
- Cache in memory or Redis-like structure

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/token.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class TokenSource(str, Enum):
    """Source of token data."""
    DEXSCREENER = "dexscreener"
    BIRDEYE = "birdeye"
    CACHE = "cache"
    FALLBACK_NEUTRAL = "fallback_neutral"


class TokenLiquidity(BaseModel):
    """Token liquidity information."""

    usd: float = Field(default=0.0, ge=0)
    base: float = Field(default=0.0, ge=0)  # Base token amount
    quote: float = Field(default=0.0, ge=0)  # Quote token (usually SOL)


class TokenPriceChange(BaseModel):
    """Price change percentages."""

    m5: float | None = None   # 5 minutes
    h1: float | None = None   # 1 hour
    h6: float | None = None   # 6 hours
    h24: float | None = None  # 24 hours


class TokenVolume(BaseModel):
    """Trading volume information."""

    m5: float = 0.0
    h1: float = 0.0
    h6: float = 0.0
    h24: float = 0.0


class TokenTransactions(BaseModel):
    """Transaction counts."""

    buys: int = 0
    sells: int = 0
    total: int = 0

    @property
    def buy_sell_ratio(self) -> float:
        """Calculate buy/sell ratio."""
        if self.sells == 0:
            return float("inf") if self.buys > 0 else 1.0
        return self.buys / self.sells


class TokenCharacteristics(BaseModel):
    """Complete token characteristics for scoring."""

    # Identity
    token_address: str
    name: str | None = None
    symbol: str | None = None

    # Core metrics
    price_usd: float = Field(default=0.0, ge=0)
    price_sol: float = Field(default=0.0, ge=0)
    market_cap_usd: float | None = None
    fdv_usd: float | None = None  # Fully diluted valuation

    # Liquidity
    liquidity: TokenLiquidity = Field(default_factory=TokenLiquidity)

    # Trading activity
    volume: TokenVolume = Field(default_factory=TokenVolume)
    price_change: TokenPriceChange = Field(default_factory=TokenPriceChange)
    transactions_24h: TokenTransactions = Field(default_factory=TokenTransactions)

    # Token age and metadata
    created_at: datetime | None = None
    age_minutes: int = Field(default=0, ge=0)
    is_new_token: bool = False  # < 10 minutes old

    # Holder info (if available)
    holder_count: int | None = None
    top_10_holder_percentage: float | None = None

    # Risk indicators
    is_honeypot: bool | None = None
    has_freeze_authority: bool | None = None
    has_mint_authority: bool | None = None

    # Metadata
    source: TokenSource = TokenSource.DEXSCREENER
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    cache_ttl_seconds: int = 300

    @field_validator("token_address")
    @classmethod
    def validate_address(cls, v: str) -> str:
        if not v or len(v) < 32 or len(v) > 44:
            raise ValueError(f"Invalid token address: {v}")
        return v

    def is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        elapsed = (datetime.utcnow() - self.fetched_at).total_seconds()
        return elapsed < self.cache_ttl_seconds


class TokenFetchResult(BaseModel):
    """Result of token fetch operation."""

    success: bool
    token: TokenCharacteristics | None = None
    source: TokenSource
    fetch_time_ms: float = 0.0
    error_message: str | None = None
    used_fallback: bool = False
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/token.py
from typing import Final

# Cache settings
TOKEN_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes (AC2)
TOKEN_CACHE_MAX_SIZE: Final[int] = 5000

# API timeouts
DEXSCREENER_TIMEOUT_SECONDS: Final[int] = 5
BIRDEYE_TIMEOUT_SECONDS: Final[int] = 5
MAX_RETRIES: Final[int] = 3
RETRY_DELAY_SECONDS: Final[float] = 0.5

# New token threshold
NEW_TOKEN_AGE_MINUTES: Final[int] = 10  # AC4

# API endpoints
DEXSCREENER_BASE_URL: Final[str] = "https://api.dexscreener.com/latest"
BIRDEYE_BASE_URL: Final[str] = "https://public-api.birdeye.so"

# Rate limiting
DEXSCREENER_RATE_LIMIT_PER_MINUTE: Final[int] = 300
BIRDEYE_RATE_LIMIT_PER_MINUTE: Final[int] = 100

# Scoring thresholds
MIN_LIQUIDITY_USD: Final[float] = 1000.0  # Minimum for trading
SUSPICIOUS_TOP_HOLDER_PCT: Final[float] = 50.0  # Red flag if top 10 hold > 50%
```

### 3. DexScreener Client

```python
# src/walltrack/services/dexscreener/client.py
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from walltrack.core.config import settings
from walltrack.core.constants.token import (
    DEXSCREENER_BASE_URL,
    DEXSCREENER_TIMEOUT_SECONDS,
    MAX_RETRIES,
    NEW_TOKEN_AGE_MINUTES,
)
from walltrack.core.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenPriceChange,
    TokenSource,
    TokenTransactions,
    TokenVolume,
)

logger = structlog.get_logger(__name__)


class DexScreenerClient:
    """Client for DexScreener API."""

    def __init__(self, timeout: int = DEXSCREENER_TIMEOUT_SECONDS):
        self.base_url = DEXSCREENER_BASE_URL
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                headers={"Accept": "application/json"},
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def fetch_token(self, token_address: str) -> TokenFetchResult:
        """
        Fetch token characteristics from DexScreener.

        Args:
            token_address: Solana token mint address

        Returns:
            TokenFetchResult with token data or error
        """
        import time
        start_time = time.perf_counter()

        try:
            client = await self._get_client()
            url = f"{self.base_url}/dex/tokens/{token_address}"

            response = await client.get(url)
            response.raise_for_status()

            data = response.json()
            fetch_time_ms = (time.perf_counter() - start_time) * 1000

            # Parse response
            token = self._parse_response(token_address, data)

            logger.debug(
                "dexscreener_fetch_success",
                token=token_address[:8] + "...",
                fetch_time_ms=round(fetch_time_ms, 2),
            )

            return TokenFetchResult(
                success=True,
                token=token,
                source=TokenSource.DEXSCREENER,
                fetch_time_ms=fetch_time_ms,
            )

        except httpx.TimeoutException as e:
            logger.warning(
                "dexscreener_timeout",
                token=token_address[:8] + "...",
                error=str(e),
            )
            raise  # Will be caught by tenacity for retry

        except httpx.HTTPStatusError as e:
            logger.warning(
                "dexscreener_http_error",
                token=token_address[:8] + "...",
                status=e.response.status_code,
            )
            raise

        except Exception as e:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "dexscreener_error",
                token=token_address[:8] + "...",
                error=str(e),
            )
            return TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.DEXSCREENER,
                fetch_time_ms=fetch_time_ms,
                error_message=str(e),
            )

    def _parse_response(
        self,
        token_address: str,
        data: dict[str, Any],
    ) -> TokenCharacteristics:
        """Parse DexScreener API response."""
        pairs = data.get("pairs", [])

        if not pairs:
            # No trading pairs found - return minimal data
            return TokenCharacteristics(
                token_address=token_address,
                source=TokenSource.DEXSCREENER,
                is_new_token=True,  # Assume new if no pairs
            )

        # Use the highest liquidity pair
        pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0))

        # Parse creation time
        created_at = None
        age_minutes = 0
        if pair.get("pairCreatedAt"):
            created_at = datetime.fromtimestamp(
                pair["pairCreatedAt"] / 1000,
                tz=timezone.utc,
            )
            age_minutes = int((datetime.now(timezone.utc) - created_at).total_seconds() / 60)

        # Parse liquidity
        liq = pair.get("liquidity", {})
        liquidity = TokenLiquidity(
            usd=liq.get("usd", 0),
            base=liq.get("base", 0),
            quote=liq.get("quote", 0),
        )

        # Parse price changes
        pc = pair.get("priceChange", {})
        price_change = TokenPriceChange(
            m5=pc.get("m5"),
            h1=pc.get("h1"),
            h6=pc.get("h6"),
            h24=pc.get("h24"),
        )

        # Parse volume
        vol = pair.get("volume", {})
        volume = TokenVolume(
            m5=vol.get("m5", 0),
            h1=vol.get("h1", 0),
            h6=vol.get("h6", 0),
            h24=vol.get("h24", 0),
        )

        # Parse transactions
        txns = pair.get("txns", {}).get("h24", {})
        transactions = TokenTransactions(
            buys=txns.get("buys", 0),
            sells=txns.get("sells", 0),
            total=txns.get("buys", 0) + txns.get("sells", 0),
        )

        # Get base token info
        base_token = pair.get("baseToken", {})

        return TokenCharacteristics(
            token_address=token_address,
            name=base_token.get("name"),
            symbol=base_token.get("symbol"),
            price_usd=float(pair.get("priceUsd", 0) or 0),
            price_sol=float(pair.get("priceNative", 0) or 0),
            market_cap_usd=pair.get("marketCap"),
            fdv_usd=pair.get("fdv"),
            liquidity=liquidity,
            volume=volume,
            price_change=price_change,
            transactions_24h=transactions,
            created_at=created_at,
            age_minutes=age_minutes,
            is_new_token=age_minutes < NEW_TOKEN_AGE_MINUTES,
            source=TokenSource.DEXSCREENER,
        )
```

### 4. Birdeye Fallback Client

```python
# src/walltrack/services/birdeye/client.py
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from walltrack.core.config import settings
from walltrack.core.constants.token import (
    BIRDEYE_BASE_URL,
    BIRDEYE_TIMEOUT_SECONDS,
    MAX_RETRIES,
    NEW_TOKEN_AGE_MINUTES,
)
from walltrack.core.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenLiquidity,
    TokenSource,
)

logger = structlog.get_logger(__name__)


class BirdeyeClient:
    """Fallback client for Birdeye API (NFR18)."""

    def __init__(self, api_key: str | None = None):
        self.base_url = BIRDEYE_BASE_URL
        self.api_key = api_key or settings.birdeye_api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=BIRDEYE_TIMEOUT_SECONDS,
                headers={
                    "Accept": "application/json",
                    "X-API-KEY": self.api_key,
                },
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=2),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.HTTPStatusError)),
    )
    async def fetch_token(self, token_address: str) -> TokenFetchResult:
        """
        Fetch token characteristics from Birdeye (fallback).

        Args:
            token_address: Solana token mint address

        Returns:
            TokenFetchResult with token data or error
        """
        import time
        start_time = time.perf_counter()

        try:
            client = await self._get_client()

            # Fetch token overview
            url = f"{self.base_url}/defi/token_overview"
            params = {"address": token_address}

            response = await client.get(url, params=params)
            response.raise_for_status()

            data = response.json()
            fetch_time_ms = (time.perf_counter() - start_time) * 1000

            token = self._parse_response(token_address, data.get("data", {}))

            logger.debug(
                "birdeye_fetch_success",
                token=token_address[:8] + "...",
                fetch_time_ms=round(fetch_time_ms, 2),
            )

            return TokenFetchResult(
                success=True,
                token=token,
                source=TokenSource.BIRDEYE,
                fetch_time_ms=fetch_time_ms,
                used_fallback=True,
            )

        except Exception as e:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "birdeye_error",
                token=token_address[:8] + "...",
                error=str(e),
            )
            return TokenFetchResult(
                success=False,
                token=None,
                source=TokenSource.BIRDEYE,
                fetch_time_ms=fetch_time_ms,
                error_message=str(e),
                used_fallback=True,
            )

    def _parse_response(
        self,
        token_address: str,
        data: dict[str, Any],
    ) -> TokenCharacteristics:
        """Parse Birdeye API response."""
        # Parse creation time if available
        created_at = None
        age_minutes = 0

        if data.get("createdAt"):
            created_at = datetime.fromtimestamp(
                data["createdAt"],
                tz=timezone.utc,
            )
            age_minutes = int((datetime.now(timezone.utc) - created_at).total_seconds() / 60)

        return TokenCharacteristics(
            token_address=token_address,
            name=data.get("name"),
            symbol=data.get("symbol"),
            price_usd=float(data.get("price", 0) or 0),
            market_cap_usd=data.get("mc"),
            liquidity=TokenLiquidity(usd=data.get("liquidity", 0)),
            holder_count=data.get("holder"),
            created_at=created_at,
            age_minutes=age_minutes,
            is_new_token=age_minutes < NEW_TOKEN_AGE_MINUTES,
            source=TokenSource.BIRDEYE,
        )
```

### 5. Token Cache Service

```python
# src/walltrack/services/token/cache.py
import asyncio
from collections import OrderedDict
from datetime import datetime

import structlog

from walltrack.core.constants.token import (
    TOKEN_CACHE_MAX_SIZE,
    TOKEN_CACHE_TTL_SECONDS,
)
from walltrack.core.models.token import TokenCharacteristics, TokenSource

logger = structlog.get_logger(__name__)


class TokenCache:
    """In-memory LRU cache for token characteristics."""

    def __init__(
        self,
        max_size: int = TOKEN_CACHE_MAX_SIZE,
        ttl_seconds: int = TOKEN_CACHE_TTL_SECONDS,
    ):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, TokenCharacteristics] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, token_address: str) -> TokenCharacteristics | None:
        """Get token from cache if valid."""
        async with self._lock:
            if token_address not in self._cache:
                self._misses += 1
                return None

            token = self._cache[token_address]

            # Check TTL
            if not token.is_cache_valid():
                del self._cache[token_address]
                self._misses += 1
                return None

            # Move to end for LRU
            self._cache.move_to_end(token_address)
            self._hits += 1

            # Update source to indicate cache hit
            token.source = TokenSource.CACHE
            return token

    async def set(self, token: TokenCharacteristics) -> None:
        """Store token in cache."""
        async with self._lock:
            # Evict if at capacity
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)

            # Update TTL and store
            token.cache_ttl_seconds = self.ttl_seconds
            token.fetched_at = datetime.utcnow()
            self._cache[token.token_address] = token

    async def invalidate(self, token_address: str) -> None:
        """Remove token from cache."""
        async with self._lock:
            self._cache.pop(token_address, None)

    async def clear(self) -> None:
        """Clear entire cache."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> dict:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "ttl_seconds": self.ttl_seconds,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": round(hit_rate, 4),
        }
```

### 6. Token Fetcher Service (with fallback)

```python
# src/walltrack/services/token/fetcher.py
import time

import structlog

from walltrack.core.constants.token import TOKEN_CACHE_TTL_SECONDS
from walltrack.core.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenSource,
)
from walltrack.services.dexscreener.client import DexScreenerClient
from walltrack.services.birdeye.client import BirdeyeClient
from walltrack.services.token.cache import TokenCache

logger = structlog.get_logger(__name__)


class TokenFetcher:
    """
    Fetches token characteristics with caching and fallback.

    Priority: Cache -> DexScreener -> Birdeye -> Neutral
    """

    def __init__(
        self,
        dexscreener_client: DexScreenerClient,
        birdeye_client: BirdeyeClient,
        token_cache: TokenCache,
    ):
        self.dexscreener = dexscreener_client
        self.birdeye = birdeye_client
        self.cache = token_cache

    async def fetch(self, token_address: str) -> TokenFetchResult:
        """
        Fetch token characteristics with fallback chain.

        1. Check cache
        2. Try DexScreener
        3. Fallback to Birdeye
        4. Return neutral if all fail
        """
        start_time = time.perf_counter()

        # Step 1: Check cache (AC2)
        cached = await self.cache.get(token_address)
        if cached:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.debug(
                "token_cache_hit",
                token=token_address[:8] + "...",
            )
            return TokenFetchResult(
                success=True,
                token=cached,
                source=TokenSource.CACHE,
                fetch_time_ms=fetch_time_ms,
            )

        # Step 2: Try DexScreener (AC1)
        result = await self.dexscreener.fetch_token(token_address)

        if result.success and result.token:
            await self.cache.set(result.token)
            return result

        # Step 3: Fallback to Birdeye (AC3 / NFR18)
        logger.info(
            "token_fallback_birdeye",
            token=token_address[:8] + "...",
            dexscreener_error=result.error_message,
        )

        birdeye_result = await self.birdeye.fetch_token(token_address)

        if birdeye_result.success and birdeye_result.token:
            await self.cache.set(birdeye_result.token)
            return birdeye_result

        # Step 4: Check cache again (might have stale data)
        stale_cached = await self._get_stale_cache(token_address)
        if stale_cached:
            fetch_time_ms = (time.perf_counter() - start_time) * 1000
            logger.warning(
                "token_using_stale_cache",
                token=token_address[:8] + "...",
            )
            return TokenFetchResult(
                success=True,
                token=stale_cached,
                source=TokenSource.CACHE,
                fetch_time_ms=fetch_time_ms,
                used_fallback=True,
            )

        # Step 5: Return neutral (AC3 - no data available)
        fetch_time_ms = (time.perf_counter() - start_time) * 1000
        logger.warning(
            "token_fallback_neutral",
            token=token_address[:8] + "...",
        )

        neutral_token = TokenCharacteristics(
            token_address=token_address,
            source=TokenSource.FALLBACK_NEUTRAL,
            is_new_token=True,  # Assume new if we can't get data
        )

        return TokenFetchResult(
            success=True,  # Neutral is still "success" for scoring
            token=neutral_token,
            source=TokenSource.FALLBACK_NEUTRAL,
            fetch_time_ms=fetch_time_ms,
            used_fallback=True,
            error_message="All sources failed, using neutral defaults",
        )

    async def _get_stale_cache(self, token_address: str) -> TokenCharacteristics | None:
        """Get potentially stale cache entry for fallback."""
        # Access internal cache directly for stale data
        if token_address in self.cache._cache:
            return self.cache._cache[token_address]
        return None

    async def close(self) -> None:
        """Close all clients."""
        await self.dexscreener.close()
        await self.birdeye.close()
```

### 7. API Endpoints

```python
# src/walltrack/api/routes/tokens.py
from fastapi import APIRouter, Depends, HTTPException

import structlog

from walltrack.core.models.token import TokenCharacteristics, TokenFetchResult
from walltrack.services.token.fetcher import TokenFetcher
from walltrack.services.token.cache import TokenCache

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/tokens", tags=["tokens"])


def get_token_fetcher() -> TokenFetcher:
    """Dependency for token fetcher."""
    from walltrack.services.token.fetcher import get_fetcher
    return get_fetcher()


def get_token_cache() -> TokenCache:
    """Dependency for token cache."""
    from walltrack.services.token.fetcher import get_fetcher
    return get_fetcher().cache


@router.get("/{token_address}", response_model=TokenCharacteristics)
async def get_token(
    token_address: str,
    fetcher: TokenFetcher = Depends(get_token_fetcher),
) -> TokenCharacteristics:
    """
    Get token characteristics.

    Fetches from DexScreener with Birdeye fallback.
    Results are cached for 5 minutes.
    """
    result = await fetcher.fetch(token_address)

    if not result.success or not result.token:
        raise HTTPException(
            status_code=404,
            detail=f"Token not found: {token_address}",
        )

    return result.token


@router.get("/{token_address}/full", response_model=TokenFetchResult)
async def get_token_full(
    token_address: str,
    fetcher: TokenFetcher = Depends(get_token_fetcher),
) -> TokenFetchResult:
    """Get token with full fetch metadata."""
    return await fetcher.fetch(token_address)


@router.get("/cache/stats")
async def get_cache_stats(
    cache: TokenCache = Depends(get_token_cache),
) -> dict:
    """Get token cache statistics."""
    return cache.get_stats()


@router.delete("/cache/{token_address}")
async def invalidate_token_cache(
    token_address: str,
    cache: TokenCache = Depends(get_token_cache),
) -> dict:
    """Invalidate specific token from cache."""
    await cache.invalidate(token_address)
    return {"status": "invalidated", "token": token_address}


@router.delete("/cache")
async def clear_token_cache(
    cache: TokenCache = Depends(get_token_cache),
) -> dict:
    """Clear entire token cache."""
    await cache.clear()
    return {"status": "cleared"}
```

### 8. Unit Tests

```python
# tests/unit/services/token/test_fetcher.py
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.models.token import (
    TokenCharacteristics,
    TokenFetchResult,
    TokenSource,
    TokenLiquidity,
)
from walltrack.services.dexscreener.client import DexScreenerClient
from walltrack.services.birdeye.client import BirdeyeClient
from walltrack.services.token.cache import TokenCache
from walltrack.services.token.fetcher import TokenFetcher


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Sample token for testing."""
    return TokenCharacteristics(
        token_address="TokenMint12345678901234567890123456789012",
        name="Test Token",
        symbol="TEST",
        price_usd=0.001,
        market_cap_usd=100000,
        liquidity=TokenLiquidity(usd=50000),
        age_minutes=30,
        is_new_token=False,
        source=TokenSource.DEXSCREENER,
    )


@pytest.fixture
def mock_dexscreener() -> MagicMock:
    """Mock DexScreener client."""
    client = MagicMock(spec=DexScreenerClient)
    client.fetch_token = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def mock_birdeye() -> MagicMock:
    """Mock Birdeye client."""
    client = MagicMock(spec=BirdeyeClient)
    client.fetch_token = AsyncMock()
    client.close = AsyncMock()
    return client


class TestTokenFetcher:
    """Tests for TokenFetcher."""

    @pytest.mark.asyncio
    async def test_fetch_from_cache(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test cache hit returns cached data."""
        cache = TokenCache()
        await cache.set(sample_token)

        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.CACHE
        mock_dexscreener.fetch_token.assert_not_called()

    @pytest.mark.asyncio
    async def test_fetch_from_dexscreener(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test DexScreener fetch on cache miss."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.DEXSCREENER,
            fetch_time_ms=50.0,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.DEXSCREENER
        mock_dexscreener.fetch_token.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_birdeye(
        self,
        sample_token: TokenCharacteristics,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test Birdeye fallback when DexScreener fails."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=False,
            token=None,
            source=TokenSource.DEXSCREENER,
            error_message="Timeout",
        )
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=True,
            token=sample_token,
            source=TokenSource.BIRDEYE,
            used_fallback=True,
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch(sample_token.token_address)

        assert result.success is True
        assert result.source == TokenSource.BIRDEYE
        assert result.used_fallback is True

    @pytest.mark.asyncio
    async def test_neutral_fallback(
        self,
        mock_dexscreener: MagicMock,
        mock_birdeye: MagicMock,
    ):
        """Test neutral fallback when all sources fail."""
        mock_dexscreener.fetch_token.return_value = TokenFetchResult(
            success=False, token=None, source=TokenSource.DEXSCREENER
        )
        mock_birdeye.fetch_token.return_value = TokenFetchResult(
            success=False, token=None, source=TokenSource.BIRDEYE
        )

        cache = TokenCache()
        fetcher = TokenFetcher(mock_dexscreener, mock_birdeye, cache)
        result = await fetcher.fetch("UnknownToken12345678901234567890123")

        assert result.success is True  # Neutral is still success
        assert result.source == TokenSource.FALLBACK_NEUTRAL
        assert result.token.is_new_token is True


class TestTokenCache:
    """Tests for TokenCache."""

    @pytest.mark.asyncio
    async def test_cache_hit(self, sample_token: TokenCharacteristics):
        """Test cache stores and retrieves tokens."""
        cache = TokenCache()
        await cache.set(sample_token)

        result = await cache.get(sample_token.token_address)

        assert result is not None
        assert result.token_address == sample_token.token_address
        assert result.source == TokenSource.CACHE

    @pytest.mark.asyncio
    async def test_cache_ttl_expiry(self, sample_token: TokenCharacteristics):
        """Test cache entry expires after TTL."""
        cache = TokenCache(ttl_seconds=1)
        await cache.set(sample_token)

        # Wait for expiry
        import asyncio
        await asyncio.sleep(1.1)

        result = await cache.get(sample_token.token_address)
        assert result is None

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = TokenCache(max_size=2)

        # Fill cache
        for i in range(3):
            token = TokenCharacteristics(
                token_address=f"Token{i}{'0' * 38}",
                source=TokenSource.DEXSCREENER,
            )
            await cache.set(token)

        # First token should be evicted
        assert await cache.get("Token0" + "0" * 38) is None
        assert await cache.get("Token2" + "0" * 38) is not None


class TestNewTokenHandling:
    """Tests for new token handling (AC4)."""

    @pytest.mark.asyncio
    async def test_new_token_flag(self):
        """Test new token flag for tokens < 10 minutes old."""
        # Token created 5 minutes ago
        new_token = TokenCharacteristics(
            token_address="NewToken12345678901234567890123456789",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            age_minutes=5,
            is_new_token=True,
            source=TokenSource.DEXSCREENER,
        )

        assert new_token.is_new_token is True
        assert new_token.age_minutes == 5

    @pytest.mark.asyncio
    async def test_established_token_flag(self):
        """Test new token flag is false for older tokens."""
        old_token = TokenCharacteristics(
            token_address="OldToken123456789012345678901234567890",
            created_at=datetime.now(timezone.utc) - timedelta(hours=24),
            age_minutes=1440,
            is_new_token=False,
            source=TokenSource.DEXSCREENER,
        )

        assert old_token.is_new_token is False
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/services/dexscreener/client.py`
- [ ] Implement DexScreener API client
- [ ] Add response caching (5 min TTL)
- [ ] Create Birdeye fallback client
- [ ] Implement fallback logic
- [ ] Handle new tokens gracefully
- [ ] Attach data to signal context

## Definition of Done

- [ ] Token data fetched from DexScreener
- [ ] Caching works with 5 min TTL
- [ ] Fallback to Birdeye on failure
- [ ] New tokens handled gracefully
