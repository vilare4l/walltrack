# Story 9.8: Token Characteristics Service

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: High
- **Depends on**: None (new service)
- **Required by**: Story 9.7 (Signal Pipeline Integration)

## User Story

**As a** signal scoring system,
**I want** to fetch token characteristics (liquidity, market cap, age, risk),
**So that** I can properly score signals based on token quality.

## Problem Statement

The `SignalScorer` (Story 3.4) needs `TokenCharacteristics` to calculate the token score component (25% of final score). Currently:
- The model `TokenCharacteristics` exists but has no fetcher
- Scorer uses placeholder/default values
- No honeypot detection implemented
- No liquidity/market cap data available

## Acceptance Criteria

### AC 1: Token Data Fetching
**Given** a token mint address
**When** characteristics are requested
**Then** liquidity in USD is fetched
**And** market cap is calculated
**And** holder count is retrieved
**And** token age is determined

### AC 2: Data Source Integration
**Given** token data is needed
**When** fetching from external APIs
**Then** DexScreener is used as primary source
**And** BirdEye is used as fallback (if configured)
**And** rate limiting is respected
**And** errors are handled gracefully

### AC 3: Honeypot Detection
**Given** a token needs risk assessment
**When** honeypot check is performed
**Then** sell tax is evaluated
**And** liquidity lock status is checked
**And** contract risk flags are assessed
**And** high-risk tokens are flagged

### AC 4: Caching Layer
**Given** token data changes slowly
**When** the same token is queried multiple times
**Then** cached data is returned (TTL: 5 minutes)
**And** cache invalidation works correctly
**And** memory usage is bounded

### AC 5: Safe Defaults
**Given** token data fetch fails
**When** scorer needs characteristics
**Then** conservative defaults are returned
**And** token is flagged as high-risk
**And** error is logged for monitoring

## Technical Specifications

### Token Characteristics Model

```python
# src/walltrack/services/token/models.py

from dataclasses import dataclass
from datetime import datetime

@dataclass
class TokenCharacteristics:
    """Token characteristics for signal scoring."""
    mint: str

    # Liquidity & Market
    liquidity_usd: float = 0.0
    market_cap_usd: float = 0.0
    volume_24h_usd: float = 0.0
    price_usd: float = 0.0

    # Token Info
    holder_count: int = 0
    age_minutes: int = 0
    created_at: datetime | None = None

    # Risk Flags
    is_honeypot: bool = False
    honeypot_reason: str | None = None
    sell_tax_pct: float = 0.0
    buy_tax_pct: float = 0.0
    is_liquidity_locked: bool = False

    # Metadata
    symbol: str = ""
    name: str = ""
    fetched_at: datetime = None
    data_source: str = "unknown"

    def is_safe_to_trade(self) -> bool:
        """Check if token passes basic safety checks."""
        return (
            not self.is_honeypot
            and self.liquidity_usd >= 1000
            and self.sell_tax_pct <= 10
            and self.age_minutes >= 5
        )
```

### Token Characteristics Service

```python
# src/walltrack/services/token/characteristics.py

import asyncio
from datetime import datetime, UTC
from typing import Any

import httpx
import structlog

from walltrack.config.settings import get_settings

log = structlog.get_logger()


class TokenCharacteristicsService:
    """Fetches and caches token characteristics for scoring."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[TokenCharacteristics, datetime]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes

    async def connect(self) -> None:
        """Initialize HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=10.0)

    async def disconnect(self) -> None:
        """Close HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def get_characteristics(
        self, mint: str, force_refresh: bool = False
    ) -> TokenCharacteristics:
        """
        Get token characteristics with caching.

        Args:
            mint: Token mint address
            force_refresh: Bypass cache

        Returns:
            TokenCharacteristics with all available data
        """
        # Check cache
        if not force_refresh and mint in self._cache:
            cached, cached_at = self._cache[mint]
            age = (datetime.now(UTC) - cached_at).total_seconds()
            if age < self._cache_ttl_seconds:
                return cached

        # Fetch fresh data
        try:
            characteristics = await self._fetch_from_dexscreener(mint)

            # Add honeypot check
            characteristics = await self._check_honeypot(characteristics)

            # Cache result
            self._cache[mint] = (characteristics, datetime.now(UTC))

            # Cleanup old cache entries
            self._cleanup_cache()

            return characteristics

        except Exception as e:
            log.error("token_fetch_failed", mint=mint, error=str(e))
            return self._get_safe_defaults(mint)

    async def _fetch_from_dexscreener(self, mint: str) -> TokenCharacteristics:
        """Fetch token data from DexScreener API."""
        url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"

        response = await self._client.get(url)
        response.raise_for_status()
        data = response.json()

        pairs = data.get("pairs", [])
        if not pairs:
            return self._get_safe_defaults(mint)

        # Use the highest liquidity pair
        pair = max(pairs, key=lambda p: float(p.get("liquidity", {}).get("usd", 0)))

        # Calculate token age
        created_at = None
        age_minutes = 0
        if pair.get("pairCreatedAt"):
            created_at = datetime.fromtimestamp(
                pair["pairCreatedAt"] / 1000, tz=UTC
            )
            age_minutes = int(
                (datetime.now(UTC) - created_at).total_seconds() / 60
            )

        return TokenCharacteristics(
            mint=mint,
            liquidity_usd=float(pair.get("liquidity", {}).get("usd", 0)),
            market_cap_usd=float(pair.get("marketCap", 0) or 0),
            volume_24h_usd=float(pair.get("volume", {}).get("h24", 0)),
            price_usd=float(pair.get("priceUsd", 0) or 0),
            holder_count=0,  # Not available from DexScreener
            age_minutes=age_minutes,
            created_at=created_at,
            symbol=pair.get("baseToken", {}).get("symbol", ""),
            name=pair.get("baseToken", {}).get("name", ""),
            fetched_at=datetime.now(UTC),
            data_source="dexscreener",
        )

    async def _check_honeypot(
        self, token: TokenCharacteristics
    ) -> TokenCharacteristics:
        """Check if token is a honeypot using RugCheck or similar."""
        try:
            # Try RugCheck API
            url = f"https://api.rugcheck.xyz/v1/tokens/{token.mint}/report"
            response = await self._client.get(url, timeout=5.0)

            if response.status_code == 200:
                data = response.json()

                # Check risk score
                risk_score = data.get("score", 0)
                risks = data.get("risks", [])

                # High risk = potential honeypot
                if risk_score < 500:  # RugCheck uses 0-1000 scale
                    token.is_honeypot = True
                    token.honeypot_reason = "; ".join(
                        r.get("name", "") for r in risks[:3]
                    )

                # Check for specific risks
                for risk in risks:
                    if "honeypot" in risk.get("name", "").lower():
                        token.is_honeypot = True
                        token.honeypot_reason = risk.get("description", "")
                        break

        except Exception as e:
            log.debug("honeypot_check_failed", mint=token.mint, error=str(e))
            # Don't fail - just can't verify

        return token

    def _get_safe_defaults(self, mint: str) -> TokenCharacteristics:
        """Return conservative defaults when data unavailable."""
        return TokenCharacteristics(
            mint=mint,
            liquidity_usd=0,
            market_cap_usd=0,
            volume_24h_usd=0,
            holder_count=0,
            age_minutes=0,
            is_honeypot=True,  # Assume worst case
            honeypot_reason="data_unavailable",
            fetched_at=datetime.now(UTC),
            data_source="defaults",
        )

    def _cleanup_cache(self) -> None:
        """Remove expired cache entries."""
        now = datetime.now(UTC)
        expired = [
            mint for mint, (_, cached_at) in self._cache.items()
            if (now - cached_at).total_seconds() > self._cache_ttl_seconds * 2
        ]
        for mint in expired:
            del self._cache[mint]

        # Limit cache size
        if len(self._cache) > 1000:
            # Remove oldest entries
            sorted_items = sorted(
                self._cache.items(),
                key=lambda x: x[1][1]
            )
            for mint, _ in sorted_items[:100]:
                del self._cache[mint]


# Singleton
_token_service: TokenCharacteristicsService | None = None

async def get_token_service() -> TokenCharacteristicsService:
    """Get or create token service singleton."""
    global _token_service
    if _token_service is None:
        _token_service = TokenCharacteristicsService()
        await _token_service.connect()
    return _token_service
```

### Integration with Signal Scorer

```python
# In signal_scorer.py, update token score calculation:

async def _calculate_token_score(
    self, token: TokenCharacteristics
) -> TokenScoreBreakdown:
    """Calculate token quality score."""

    # Liquidity score (30%)
    if token.liquidity_usd >= 100_000:
        liquidity_score = 1.0
    elif token.liquidity_usd >= 10_000:
        liquidity_score = 0.7 + (token.liquidity_usd - 10_000) / 300_000
    elif token.liquidity_usd >= 1_000:
        liquidity_score = 0.3 + (token.liquidity_usd - 1_000) / 30_000
    else:
        liquidity_score = token.liquidity_usd / 3_333

    # Market cap score (25%)
    if token.market_cap_usd >= 1_000_000:
        mcap_score = 1.0
    elif token.market_cap_usd >= 100_000:
        mcap_score = 0.6 + (token.market_cap_usd - 100_000) / 2_250_000
    else:
        mcap_score = token.market_cap_usd / 166_666

    # Age score (25%) - newer is riskier
    if token.age_minutes >= 1440:  # 24h+
        age_score = 1.0
    elif token.age_minutes >= 60:  # 1h+
        age_score = 0.5 + (token.age_minutes - 60) / 2_760
    elif token.age_minutes >= 5:
        age_score = 0.2 + (token.age_minutes - 5) / 183
    else:
        age_score = 0.0  # Too new

    # Volume score (20%)
    if token.volume_24h_usd >= 100_000:
        volume_score = 1.0
    else:
        volume_score = min(token.volume_24h_usd / 100_000, 1.0)

    # Calculate weighted score
    base_score = (
        liquidity_score * 0.30 +
        mcap_score * 0.25 +
        age_score * 0.25 +
        volume_score * 0.20
    )

    # Apply penalties
    if token.is_honeypot:
        base_score *= 0.0  # Complete rejection
    elif token.age_minutes < 5:
        base_score *= 0.5  # New token penalty

    return TokenScoreBreakdown(
        final=base_score,
        liquidity=liquidity_score,
        market_cap=mcap_score,
        age=age_score,
        volume=volume_score,
        is_honeypot=token.is_honeypot,
    )
```

## API Rate Limits

| Source | Rate Limit | Strategy |
|--------|------------|----------|
| DexScreener | 300/min | Cache 5min, batch requests |
| RugCheck | 60/min | Cache results, fail gracefully |
| BirdEye | Depends on plan | Optional fallback |

## Testing Requirements

### Unit Tests
```python
class TestTokenCharacteristicsService:
    async def test_fetch_valid_token(self):
        """Fetch data for known token."""

    async def test_cache_hit(self):
        """Second call returns cached data."""

    async def test_unknown_token_returns_defaults(self):
        """Unknown token gets safe defaults."""

    async def test_honeypot_detected(self):
        """Honeypot tokens are flagged."""

    async def test_cache_expiry(self):
        """Expired cache entries are refreshed."""
```

### Integration Tests
```python
async def test_real_token_fetch():
    """Test with real Solana token (BONK, known safe)."""
    service = TokenCharacteristicsService()
    await service.connect()

    token = await service.get_characteristics(
        "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"  # BONK
    )

    assert token.liquidity_usd > 0
    assert not token.is_honeypot
```

## Definition of Done

- [ ] TokenCharacteristicsService implemented
- [ ] DexScreener integration working
- [ ] Honeypot detection via RugCheck
- [ ] Caching with 5-minute TTL
- [ ] Safe defaults on fetch failure
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration test with real token works
- [ ] Rate limiting respected

## Estimated Effort

- **Implementation**: 2-3 hours
- **Testing**: 1-2 hours
- **Total**: 3-5 hours

## Notes

This service is required by Story 9.7 (Pipeline Integration). The scorer currently has placeholder token scores - this provides real data.
