# Story 8.1: Historical Data Collector

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: High
- **FR**: FR61

## User Story

**As an** operator,
**I want** to collect and store historical signal and price data,
**So that** I can run backtests on past market conditions.

## Acceptance Criteria

### AC 1: Signal Data Storage
**Given** the system is running
**When** signals are processed
**Then** all signal data is stored with timestamp
**And** token prices at signal time are recorded
**And** subsequent price movements are tracked

### AC 2: Historical Price Fetching
**Given** historical data collection is enabled
**When** a new token is encountered
**Then** historical price data is fetched (if available)
**And** data is stored in historical_prices table
**And** gaps in data are noted

### AC 3: Price Tracking
**Given** price tracking for active signals
**When** price update runs (every 5 minutes for 24h)
**Then** token prices are fetched and stored
**And** data enables P&L calculation at any point
**And** storage is optimized (aggregate after 24h)

### AC 4: Data Retrieval
**Given** historical data query
**When** backtest requests data for date range
**Then** signals for that range are returned
**And** price data for signal tokens is returned
**And** wallet/cluster state at that time is reconstructable

## Technical Specifications

### Historical Signal Model

**src/walltrack/core/backtest/models.py:**
```python
"""Historical data models for backtesting."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class HistoricalSignal(BaseModel):
    """Stored signal for backtesting."""

    id: UUID
    timestamp: datetime
    wallet_address: str
    token_address: str

    # Signal context snapshot
    wallet_score: Decimal
    cluster_id: Optional[str] = None
    cluster_amplification: Decimal = Decimal("1.0")

    # Token data at signal time
    token_price_usd: Decimal
    token_market_cap: Optional[Decimal] = None
    token_liquidity: Optional[Decimal] = None
    token_age_minutes: Optional[int] = None

    # Scoring context
    computed_score: Decimal
    score_breakdown: dict = Field(default_factory=dict)

    # Decision
    trade_eligible: bool
    actual_traded: bool = False

    class Config:
        json_encoders = {Decimal: str}


class HistoricalPrice(BaseModel):
    """Price point for backtesting."""

    id: UUID
    token_address: str
    timestamp: datetime
    price_usd: Decimal
    source: str = "dexscreener"

    # Optional OHLCV data
    open: Optional[Decimal] = None
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    close: Optional[Decimal] = None
    volume: Optional[Decimal] = None


class PriceTimeline(BaseModel):
    """Price history for a token."""

    token_address: str
    prices: list[HistoricalPrice]
    start_time: datetime
    end_time: datetime

    def price_at(self, timestamp: datetime) -> Optional[Decimal]:
        """Get price closest to timestamp."""
        closest = min(
            self.prices,
            key=lambda p: abs((p.timestamp - timestamp).total_seconds()),
            default=None,
        )
        return closest.price_usd if closest else None
```

### Historical Data Collector

**src/walltrack/core/backtest/collector.py:**
```python
"""Historical data collector for backtesting."""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog

from walltrack.core.backtest.models import HistoricalSignal, HistoricalPrice
from walltrack.data.supabase.client import get_supabase_client
from walltrack.integrations.dexscreener.client import get_dexscreener_client

log = structlog.get_logger()


class HistoricalDataCollector:
    """Collects and stores historical data for backtesting."""

    def __init__(self, price_track_hours: int = 24) -> None:
        self._price_track_hours = price_track_hours
        self._tracked_tokens: set[str] = set()

    async def store_signal(
        self,
        wallet_address: str,
        token_address: str,
        token_price: float,
        wallet_score: float,
        computed_score: float,
        score_breakdown: dict,
        trade_eligible: bool,
        cluster_id: Optional[str] = None,
        cluster_amplification: float = 1.0,
        token_market_cap: Optional[float] = None,
        token_liquidity: Optional[float] = None,
        token_age_minutes: Optional[int] = None,
    ) -> HistoricalSignal:
        """Store a signal snapshot for backtesting."""
        signal = HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address=wallet_address,
            token_address=token_address,
            wallet_score=Decimal(str(wallet_score)),
            cluster_id=cluster_id,
            cluster_amplification=Decimal(str(cluster_amplification)),
            token_price_usd=Decimal(str(token_price)),
            token_market_cap=Decimal(str(token_market_cap)) if token_market_cap else None,
            token_liquidity=Decimal(str(token_liquidity)) if token_liquidity else None,
            token_age_minutes=token_age_minutes,
            computed_score=Decimal(str(computed_score)),
            score_breakdown=score_breakdown,
            trade_eligible=trade_eligible,
        )

        supabase = await get_supabase_client()
        await supabase.insert("historical_signals", signal.model_dump(mode="json"))

        # Start tracking price for this token
        self._tracked_tokens.add(token_address)

        log.info(
            "historical_signal_stored",
            signal_id=str(signal.id),
            token=token_address,
            score=float(computed_score),
        )

        return signal

    async def record_price(
        self,
        token_address: str,
        price_usd: float,
        source: str = "dexscreener",
    ) -> HistoricalPrice:
        """Record a price point for a token."""
        price = HistoricalPrice(
            id=uuid4(),
            token_address=token_address,
            timestamp=datetime.now(UTC),
            price_usd=Decimal(str(price_usd)),
            source=source,
        )

        supabase = await get_supabase_client()
        await supabase.insert("historical_prices", price.model_dump(mode="json"))

        return price

    async def update_tracked_prices(self) -> int:
        """Update prices for all tracked tokens."""
        dex_client = await get_dexscreener_client()
        updated_count = 0

        for token_address in list(self._tracked_tokens):
            try:
                token_data = await dex_client.get_token_info(token_address)
                if token_data and token_data.price_usd:
                    await self.record_price(
                        token_address=token_address,
                        price_usd=token_data.price_usd,
                    )
                    updated_count += 1
            except Exception as e:
                log.warning(
                    "price_update_failed",
                    token=token_address,
                    error=str(e),
                )

        log.info("tracked_prices_updated", count=updated_count)
        return updated_count

    async def cleanup_old_tracking(self) -> int:
        """Remove tokens from tracking after 24h."""
        supabase = await get_supabase_client()
        cutoff = datetime.now(UTC) - timedelta(hours=self._price_track_hours)

        # Get signals older than cutoff
        old_signals = await supabase.select(
            "historical_signals",
            filters={"timestamp_lt": cutoff.isoformat()},
        )

        # Get tokens that only have old signals
        old_tokens = {s["token_address"] for s in old_signals}

        removed = 0
        for token in old_tokens:
            if token in self._tracked_tokens:
                self._tracked_tokens.remove(token)
                removed += 1

        return removed

    async def get_signals_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[HistoricalSignal]:
        """Get historical signals for a date range."""
        supabase = await get_supabase_client()

        records = await supabase.select(
            "historical_signals",
            filters={
                "timestamp_gte": start_date.isoformat(),
                "timestamp_lte": end_date.isoformat(),
            },
            order_by="timestamp",
        )

        return [HistoricalSignal(**r) for r in records]

    async def get_price_timeline(
        self,
        token_address: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[HistoricalPrice]:
        """Get price history for a token."""
        supabase = await get_supabase_client()

        records = await supabase.select(
            "historical_prices",
            filters={
                "token_address": token_address,
                "timestamp_gte": start_time.isoformat(),
                "timestamp_lte": end_time.isoformat(),
            },
            order_by="timestamp",
        )

        return [HistoricalPrice(**r) for r in records]


# Singleton
_collector: Optional[HistoricalDataCollector] = None


async def get_historical_collector() -> HistoricalDataCollector:
    """Get historical data collector singleton."""
    global _collector
    if _collector is None:
        _collector = HistoricalDataCollector()
    return _collector
```

## Database Schema

```sql
-- Historical signals table
CREATE TABLE IF NOT EXISTS historical_signals (
    id UUID PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL,
    wallet_address VARCHAR(44) NOT NULL,
    token_address VARCHAR(44) NOT NULL,

    -- Context snapshot
    wallet_score DECIMAL(5, 4) NOT NULL,
    cluster_id VARCHAR(36),
    cluster_amplification DECIMAL(5, 4) DEFAULT 1.0,

    -- Token data
    token_price_usd DECIMAL(20, 10) NOT NULL,
    token_market_cap DECIMAL(20, 2),
    token_liquidity DECIMAL(20, 2),
    token_age_minutes INTEGER,

    -- Scoring
    computed_score DECIMAL(5, 4) NOT NULL,
    score_breakdown JSONB DEFAULT '{}',

    -- Decision
    trade_eligible BOOLEAN DEFAULT FALSE,
    actual_traded BOOLEAN DEFAULT FALSE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hist_signals_timestamp ON historical_signals(timestamp);
CREATE INDEX idx_hist_signals_token ON historical_signals(token_address);
CREATE INDEX idx_hist_signals_wallet ON historical_signals(wallet_address);

-- Historical prices table
CREATE TABLE IF NOT EXISTS historical_prices (
    id UUID PRIMARY KEY,
    token_address VARCHAR(44) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price_usd DECIMAL(20, 10) NOT NULL,
    source VARCHAR(50) DEFAULT 'dexscreener',

    -- OHLCV (optional)
    open DECIMAL(20, 10),
    high DECIMAL(20, 10),
    low DECIMAL(20, 10),
    close DECIMAL(20, 10),
    volume DECIMAL(30, 2),

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_hist_prices_token_time ON historical_prices(token_address, timestamp);
CREATE INDEX idx_hist_prices_timestamp ON historical_prices(timestamp);

-- Data retention policy (optional)
-- Consider partitioning by month for large datasets
```

## Implementation Tasks

- [ ] Create historical data models
- [ ] Create historical_signals table
- [ ] Create historical_prices table
- [ ] Implement HistoricalDataCollector
- [ ] Add signal storage to signal processing pipeline
- [ ] Add scheduled price tracking job
- [ ] Implement data cleanup job
- [ ] Write unit tests

## Definition of Done

- [ ] All signals are stored with full context
- [ ] Price tracking runs every 5 minutes
- [ ] Historical data is queryable by date range
- [ ] Data cleanup removes old tracking
- [ ] Tests cover data collection and retrieval
