# Story 3.2: Signal Filtering to Monitored Wallets

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: High
- **FR**: FR14

## User Story

**As an** operator,
**I want** only signals from monitored wallets to be processed,
**So that** system resources focus on relevant activity.

## Acceptance Criteria

### AC 1: Wallet Lookup
**Given** a webhook notification arrives
**When** the wallet address is checked
**Then** query confirms if wallet is in monitored watchlist
**And** query response time is < 50ms

### AC 2: Monitored Wallet
**Given** wallet IS in monitored watchlist
**When** filter check passes
**Then** signal proceeds to scoring pipeline
**And** signal is marked with source wallet metadata

### AC 3: Non-Monitored Wallet
**Given** wallet is NOT in monitored watchlist
**When** filter check runs
**Then** signal is discarded
**And** discard is logged at DEBUG level (not stored)
**And** no further processing occurs

### AC 4: Blacklisted Wallet
**Given** wallet is blacklisted
**When** filter check runs
**Then** signal is logged with status "blocked_blacklisted"
**And** signal is NOT scored or processed further

## Technical Notes

- FR14: Filter notifications to only monitored wallet addresses
- Implement efficient lookup (in-memory cache or fast DB query)
- Integrate with blacklist from Story 1.7

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/signal_filter.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class FilterStatus(str, Enum):
    """Status of signal filtering."""
    PASSED = "passed"
    DISCARDED_NOT_MONITORED = "discarded_not_monitored"
    BLOCKED_BLACKLISTED = "blocked_blacklisted"
    ERROR = "error"


class WalletCacheEntry(BaseModel):
    """Entry in the monitored wallets cache."""

    wallet_address: str
    is_monitored: bool = False
    is_blacklisted: bool = False
    cluster_id: str | None = None
    is_leader: bool = False
    reputation_score: float = Field(default=0.5, ge=0, le=1)
    cached_at: datetime = Field(default_factory=datetime.utcnow)
    ttl_seconds: int = Field(default=300)  # 5 minutes

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = (datetime.utcnow() - self.cached_at).total_seconds()
        return elapsed > self.ttl_seconds


class FilterResult(BaseModel):
    """Result of signal filtering."""

    status: FilterStatus
    wallet_address: str
    is_monitored: bool
    is_blacklisted: bool
    lookup_time_ms: float = Field(..., ge=0)
    cache_hit: bool = False
    wallet_metadata: WalletCacheEntry | None = None


class SignalContext(BaseModel):
    """Context attached to signal after filtering."""

    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"
    amount_token: float
    amount_sol: float
    timestamp: datetime
    tx_signature: str

    # Enriched from filter
    cluster_id: str | None = None
    is_cluster_leader: bool = False
    wallet_reputation: float = Field(default=0.5, ge=0, le=1)

    # Processing metadata
    filter_status: FilterStatus = FilterStatus.PASSED
    filter_time_ms: float = 0.0
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/signal_filter.py
from typing import Final

# Performance requirements
MAX_LOOKUP_TIME_MS: Final[int] = 50  # AC1: < 50ms lookup

# Cache settings
WALLET_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes
WALLET_CACHE_MAX_SIZE: Final[int] = 10000  # Maximum cached wallets
CACHE_REFRESH_BATCH_SIZE: Final[int] = 100

# Logging
LOG_DISCARDED_SIGNALS: Final[bool] = True  # DEBUG level logging
LOG_BLACKLISTED_SIGNALS: Final[bool] = True  # INFO level logging
```

### 3. In-Memory Wallet Cache

```python
# src/walltrack/services/signal/wallet_cache.py
import asyncio
from collections import OrderedDict
from datetime import datetime
from typing import Set

import structlog

from walltrack.core.constants.signal_filter import (
    WALLET_CACHE_MAX_SIZE,
    WALLET_CACHE_TTL_SECONDS,
)
from walltrack.core.models.signal_filter import WalletCacheEntry
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

logger = structlog.get_logger(__name__)


class WalletCache:
    """
    In-memory LRU cache for monitored wallet lookups.

    Provides O(1) lookups to meet < 50ms requirement.
    """

    def __init__(
        self,
        wallet_repo: WalletRepository,
        max_size: int = WALLET_CACHE_MAX_SIZE,
        ttl_seconds: int = WALLET_CACHE_TTL_SECONDS,
    ):
        self.wallet_repo = wallet_repo
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._cache: OrderedDict[str, WalletCacheEntry] = OrderedDict()
        self._monitored_set: Set[str] = set()  # Fast O(1) membership check
        self._blacklist_set: Set[str] = set()  # Fast O(1) blacklist check
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Load initial wallet data from database."""
        async with self._lock:
            if self._initialized:
                return

            try:
                # Load monitored wallets
                monitored = await self.wallet_repo.get_monitored_wallets()
                self._monitored_set = {w.wallet_address for w in monitored}

                # Load blacklisted wallets
                blacklisted = await self.wallet_repo.get_blacklisted_wallets()
                self._blacklist_set = {w.wallet_address for w in blacklisted}

                # Pre-populate cache with wallet metadata
                for wallet in monitored[:self.max_size]:
                    entry = WalletCacheEntry(
                        wallet_address=wallet.wallet_address,
                        is_monitored=True,
                        is_blacklisted=wallet.wallet_address in self._blacklist_set,
                        cluster_id=wallet.cluster_id,
                        is_leader=wallet.is_leader,
                        reputation_score=wallet.reputation_score,
                        ttl_seconds=self.ttl_seconds,
                    )
                    self._cache[wallet.wallet_address] = entry

                self._initialized = True
                logger.info(
                    "wallet_cache_initialized",
                    monitored_count=len(self._monitored_set),
                    blacklist_count=len(self._blacklist_set),
                    cache_size=len(self._cache),
                )
            except Exception as e:
                logger.error("wallet_cache_init_failed", error=str(e))
                raise

    async def get(self, wallet_address: str) -> tuple[WalletCacheEntry | None, bool]:
        """
        Get wallet entry from cache.

        Returns (entry, cache_hit) tuple.
        """
        if not self._initialized:
            await self.initialize()

        # Fast path: check sets first (O(1))
        is_monitored = wallet_address in self._monitored_set
        is_blacklisted = wallet_address in self._blacklist_set

        # Check cache for full metadata
        if wallet_address in self._cache:
            entry = self._cache[wallet_address]

            # Check if expired
            if entry.is_expired():
                await self._refresh_entry(wallet_address)
                entry = self._cache.get(wallet_address)

            # Move to end for LRU
            if entry:
                self._cache.move_to_end(wallet_address)
                return entry, True

        # Not in cache but in monitored set - fetch and cache
        if is_monitored:
            entry = await self._fetch_and_cache(wallet_address, is_blacklisted)
            return entry, False

        # Not monitored - create minimal entry for logging
        return WalletCacheEntry(
            wallet_address=wallet_address,
            is_monitored=False,
            is_blacklisted=is_blacklisted,
        ), False

    async def _fetch_and_cache(
        self,
        wallet_address: str,
        is_blacklisted: bool,
    ) -> WalletCacheEntry:
        """Fetch wallet from DB and add to cache."""
        wallet = await self.wallet_repo.get_by_address(wallet_address)

        entry = WalletCacheEntry(
            wallet_address=wallet_address,
            is_monitored=True,
            is_blacklisted=is_blacklisted,
            cluster_id=wallet.cluster_id if wallet else None,
            is_leader=wallet.is_leader if wallet else False,
            reputation_score=wallet.reputation_score if wallet else 0.5,
            ttl_seconds=self.ttl_seconds,
        )

        # Add to cache with LRU eviction
        async with self._lock:
            if len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)  # Remove oldest
            self._cache[wallet_address] = entry

        return entry

    async def _refresh_entry(self, wallet_address: str) -> None:
        """Refresh expired cache entry."""
        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if wallet:
            entry = WalletCacheEntry(
                wallet_address=wallet_address,
                is_monitored=True,
                is_blacklisted=wallet_address in self._blacklist_set,
                cluster_id=wallet.cluster_id,
                is_leader=wallet.is_leader,
                reputation_score=wallet.reputation_score,
                ttl_seconds=self.ttl_seconds,
            )
            self._cache[wallet_address] = entry

    async def invalidate(self, wallet_address: str) -> None:
        """Remove wallet from cache (e.g., after status change)."""
        async with self._lock:
            self._cache.pop(wallet_address, None)

    async def refresh_sets(self) -> None:
        """Refresh monitored and blacklist sets from database."""
        async with self._lock:
            monitored = await self.wallet_repo.get_monitored_wallets()
            self._monitored_set = {w.wallet_address for w in monitored}

            blacklisted = await self.wallet_repo.get_blacklisted_wallets()
            self._blacklist_set = {w.wallet_address for w in blacklisted}

            logger.info(
                "wallet_sets_refreshed",
                monitored_count=len(self._monitored_set),
                blacklist_count=len(self._blacklist_set),
            )
```

### 4. Signal Filter Service

```python
# src/walltrack/services/signal/filter.py
import time
from datetime import datetime

import structlog

from walltrack.core.constants.signal_filter import (
    LOG_BLACKLISTED_SIGNALS,
    LOG_DISCARDED_SIGNALS,
    MAX_LOOKUP_TIME_MS,
)
from walltrack.core.models.signal_filter import (
    FilterResult,
    FilterStatus,
    SignalContext,
)
from walltrack.core.models.webhook import ParsedSwapEvent
from walltrack.services.signal.wallet_cache import WalletCache

logger = structlog.get_logger(__name__)


class SignalFilter:
    """
    Filters signals to only process monitored wallets.

    Integrates with blacklist and provides wallet metadata enrichment.
    """

    def __init__(self, wallet_cache: WalletCache):
        self.wallet_cache = wallet_cache

    async def filter_signal(self, event: ParsedSwapEvent) -> FilterResult:
        """
        Filter signal based on wallet monitoring status.

        Returns FilterResult with status and timing.
        """
        start_time = time.perf_counter()

        try:
            # Get wallet from cache (O(1) lookup)
            entry, cache_hit = await self.wallet_cache.get(event.wallet_address)

            lookup_time_ms = (time.perf_counter() - start_time) * 1000

            # Warn if lookup exceeds limit
            if lookup_time_ms > MAX_LOOKUP_TIME_MS:
                logger.warning(
                    "filter_lookup_slow",
                    lookup_time_ms=lookup_time_ms,
                    limit_ms=MAX_LOOKUP_TIME_MS,
                    wallet=event.wallet_address[:8] + "...",
                )

            # Check blacklist first (AC4)
            if entry and entry.is_blacklisted:
                if LOG_BLACKLISTED_SIGNALS:
                    logger.info(
                        "signal_blocked_blacklisted",
                        wallet=event.wallet_address[:8] + "...",
                        token=event.token_address[:8] + "...",
                    )
                return FilterResult(
                    status=FilterStatus.BLOCKED_BLACKLISTED,
                    wallet_address=event.wallet_address,
                    is_monitored=entry.is_monitored if entry else False,
                    is_blacklisted=True,
                    lookup_time_ms=lookup_time_ms,
                    cache_hit=cache_hit,
                    wallet_metadata=entry,
                )

            # Check if monitored (AC2/AC3)
            is_monitored = entry.is_monitored if entry else False

            if not is_monitored:
                if LOG_DISCARDED_SIGNALS:
                    logger.debug(
                        "signal_discarded_not_monitored",
                        wallet=event.wallet_address[:8] + "...",
                    )
                return FilterResult(
                    status=FilterStatus.DISCARDED_NOT_MONITORED,
                    wallet_address=event.wallet_address,
                    is_monitored=False,
                    is_blacklisted=False,
                    lookup_time_ms=lookup_time_ms,
                    cache_hit=cache_hit,
                    wallet_metadata=entry,
                )

            # Signal passed - monitored and not blacklisted
            return FilterResult(
                status=FilterStatus.PASSED,
                wallet_address=event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
                lookup_time_ms=lookup_time_ms,
                cache_hit=cache_hit,
                wallet_metadata=entry,
            )

        except Exception as e:
            logger.error(
                "filter_error",
                wallet=event.wallet_address[:8] + "...",
                error=str(e),
            )
            return FilterResult(
                status=FilterStatus.ERROR,
                wallet_address=event.wallet_address,
                is_monitored=False,
                is_blacklisted=False,
                lookup_time_ms=(time.perf_counter() - start_time) * 1000,
                cache_hit=False,
            )

    def create_signal_context(
        self,
        event: ParsedSwapEvent,
        filter_result: FilterResult,
    ) -> SignalContext:
        """
        Create enriched signal context with wallet metadata.

        Called only for signals that passed filtering.
        """
        metadata = filter_result.wallet_metadata

        return SignalContext(
            wallet_address=event.wallet_address,
            token_address=event.token_address,
            direction=event.direction.value,
            amount_token=event.amount_token,
            amount_sol=event.amount_sol,
            timestamp=event.timestamp,
            tx_signature=event.tx_signature,
            cluster_id=metadata.cluster_id if metadata else None,
            is_cluster_leader=metadata.is_leader if metadata else False,
            wallet_reputation=metadata.reputation_score if metadata else 0.5,
            filter_status=filter_result.status,
            filter_time_ms=filter_result.lookup_time_ms,
        )
```

### 5. Signal Processing Pipeline Integration

```python
# src/walltrack/services/signal/pipeline.py
import structlog

from walltrack.core.models.signal_filter import FilterStatus, SignalContext
from walltrack.core.models.webhook import ParsedSwapEvent
from walltrack.services.signal.filter import SignalFilter
from walltrack.services.signal.wallet_cache import WalletCache

logger = structlog.get_logger(__name__)


class SignalPipeline:
    """
    Main signal processing pipeline.

    Orchestrates filtering, scoring, and trade eligibility.
    """

    def __init__(
        self,
        signal_filter: SignalFilter,
        # signal_scorer: SignalScorer,  # Story 3.4
        # threshold_checker: ThresholdChecker,  # Story 3.5
    ):
        self.signal_filter = signal_filter
        # self.signal_scorer = signal_scorer
        # self.threshold_checker = threshold_checker

    async def process_swap_event(self, event: ParsedSwapEvent) -> SignalContext | None:
        """
        Process swap event through the full pipeline.

        Returns SignalContext if signal passes filtering, None otherwise.
        """
        # Step 1: Filter signal (Story 3.2)
        filter_result = await self.signal_filter.filter_signal(event)

        if filter_result.status != FilterStatus.PASSED:
            logger.debug(
                "signal_filtered_out",
                status=filter_result.status.value,
                wallet=event.wallet_address[:8] + "...",
            )
            return None

        # Create enriched signal context
        signal_context = self.signal_filter.create_signal_context(
            event, filter_result
        )

        logger.info(
            "signal_passed_filter",
            wallet=event.wallet_address[:8] + "...",
            token=event.token_address[:8] + "...",
            direction=event.direction.value,
            cluster_id=signal_context.cluster_id,
            is_leader=signal_context.is_cluster_leader,
        )

        # Step 2: Score signal (Story 3.4 - to be implemented)
        # scored_signal = await self.signal_scorer.score(signal_context)

        # Step 3: Apply threshold (Story 3.5 - to be implemented)
        # trade_eligible = await self.threshold_checker.check(scored_signal)

        return signal_context


# Singleton pipeline instance
_pipeline: SignalPipeline | None = None


async def get_pipeline() -> SignalPipeline:
    """Get or create signal pipeline singleton."""
    global _pipeline

    if _pipeline is None:
        from walltrack.data.supabase.client import get_supabase_client
        from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

        client = get_supabase_client()
        wallet_repo = WalletRepository(client)
        wallet_cache = WalletCache(wallet_repo)
        await wallet_cache.initialize()

        signal_filter = SignalFilter(wallet_cache)
        _pipeline = SignalPipeline(signal_filter)

    return _pipeline
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/signals.py
from fastapi import APIRouter, Depends, Query

import structlog

from walltrack.services.signal.wallet_cache import WalletCache
from walltrack.services.signal.filter import SignalFilter

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/signals", tags=["signals"])


def get_wallet_cache() -> WalletCache:
    """Dependency for wallet cache."""
    from walltrack.services.signal.pipeline import get_pipeline
    import asyncio
    pipeline = asyncio.get_event_loop().run_until_complete(get_pipeline())
    return pipeline.signal_filter.wallet_cache


@router.get("/cache/stats")
async def get_cache_stats(
    cache: WalletCache = Depends(get_wallet_cache),
) -> dict:
    """Get wallet cache statistics."""
    return {
        "cache_size": len(cache._cache),
        "monitored_count": len(cache._monitored_set),
        "blacklist_count": len(cache._blacklist_set),
        "max_size": cache.max_size,
        "ttl_seconds": cache.ttl_seconds,
        "initialized": cache._initialized,
    }


@router.post("/cache/refresh")
async def refresh_cache(
    cache: WalletCache = Depends(get_wallet_cache),
) -> dict:
    """Force refresh of wallet cache sets."""
    await cache.refresh_sets()
    return {
        "status": "refreshed",
        "monitored_count": len(cache._monitored_set),
        "blacklist_count": len(cache._blacklist_set),
    }


@router.delete("/cache/{wallet_address}")
async def invalidate_cache_entry(
    wallet_address: str,
    cache: WalletCache = Depends(get_wallet_cache),
) -> dict:
    """Invalidate specific wallet from cache."""
    await cache.invalidate(wallet_address)
    return {"status": "invalidated", "wallet": wallet_address}
```

### 7. Unit Tests

```python
# tests/unit/services/signal/test_filter.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.models.signal_filter import (
    FilterResult,
    FilterStatus,
    WalletCacheEntry,
)
from walltrack.core.models.webhook import ParsedSwapEvent, SwapDirection
from walltrack.services.signal.filter import SignalFilter
from walltrack.services.signal.wallet_cache import WalletCache


@pytest.fixture
def sample_swap_event() -> ParsedSwapEvent:
    """Sample swap event for testing."""
    return ParsedSwapEvent(
        tx_signature="sig123",
        wallet_address="MonitoredWallet123456789012345678901234567",
        token_address="TokenMint12345678901234567890123456789012",
        direction=SwapDirection.BUY,
        amount_token=1000000,
        amount_sol=1.0,
        timestamp=datetime.now(timezone.utc),
        slot=123456,
        fee_lamports=5000,
    )


@pytest.fixture
def mock_wallet_cache() -> MagicMock:
    """Mock wallet cache."""
    cache = MagicMock(spec=WalletCache)
    cache.get = AsyncMock()
    return cache


class TestSignalFilter:
    """Tests for SignalFilter."""

    @pytest.mark.asyncio
    async def test_filter_monitored_wallet(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that monitored wallets pass filter."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
                cluster_id="cluster-123",
                is_leader=True,
                reputation_score=0.85,
            ),
            True,  # cache hit
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.PASSED
        assert result.is_monitored is True
        assert result.cache_hit is True
        assert result.wallet_metadata.cluster_id == "cluster-123"

    @pytest.mark.asyncio
    async def test_filter_non_monitored_wallet(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that non-monitored wallets are discarded."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=False,
                is_blacklisted=False,
            ),
            False,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.DISCARDED_NOT_MONITORED
        assert result.is_monitored is False

    @pytest.mark.asyncio
    async def test_filter_blacklisted_wallet(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that blacklisted wallets are blocked."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=True,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        assert result.status == FilterStatus.BLOCKED_BLACKLISTED
        assert result.is_blacklisted is True

    @pytest.mark.asyncio
    async def test_filter_lookup_time(
        self,
        sample_swap_event: ParsedSwapEvent,
        mock_wallet_cache: MagicMock,
    ):
        """Test that lookup time is within limit."""
        mock_wallet_cache.get.return_value = (
            WalletCacheEntry(
                wallet_address=sample_swap_event.wallet_address,
                is_monitored=True,
                is_blacklisted=False,
            ),
            True,
        )

        filter_service = SignalFilter(mock_wallet_cache)
        result = await filter_service.filter_signal(sample_swap_event)

        # Lookup should be < 50ms (AC1)
        assert result.lookup_time_ms < 50


class TestWalletCache:
    """Tests for WalletCache."""

    @pytest.mark.asyncio
    async def test_cache_initialization(self):
        """Test cache initializes with wallet data."""
        wallet_repo = AsyncMock()
        wallet_repo.get_monitored_wallets = AsyncMock(return_value=[
            MagicMock(
                wallet_address="wallet1",
                cluster_id="c1",
                is_leader=True,
                reputation_score=0.8,
            ),
        ])
        wallet_repo.get_blacklisted_wallets = AsyncMock(return_value=[
            MagicMock(wallet_address="blacklisted1"),
        ])

        cache = WalletCache(wallet_repo)
        await cache.initialize()

        assert cache._initialized is True
        assert "wallet1" in cache._monitored_set
        assert "blacklisted1" in cache._blacklist_set

    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        wallet_repo = AsyncMock()
        wallet_repo.get_monitored_wallets = AsyncMock(return_value=[])
        wallet_repo.get_blacklisted_wallets = AsyncMock(return_value=[])
        wallet_repo.get_by_address = AsyncMock(return_value=MagicMock(
            cluster_id=None,
            is_leader=False,
            reputation_score=0.5,
        ))

        cache = WalletCache(wallet_repo, max_size=2)
        await cache.initialize()

        # Add to monitored set for test
        cache._monitored_set = {"w1", "w2", "w3"}

        # Fill cache
        await cache.get("w1")
        await cache.get("w2")

        assert len(cache._cache) == 2

        # Add third - should evict oldest
        await cache.get("w3")

        assert len(cache._cache) == 2
        assert "w1" not in cache._cache  # Evicted
        assert "w3" in cache._cache
```

### 8. Scheduled Cache Refresh

```python
# src/walltrack/services/signal/cache_refresh.py
import asyncio

import structlog

from walltrack.services.signal.wallet_cache import WalletCache

logger = structlog.get_logger(__name__)


class CacheRefreshScheduler:
    """Periodically refreshes wallet cache sets."""

    def __init__(
        self,
        wallet_cache: WalletCache,
        refresh_interval_seconds: int = 60,
    ):
        self.wallet_cache = wallet_cache
        self.refresh_interval = refresh_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start background refresh task."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._refresh_loop())
        logger.info(
            "cache_refresh_started",
            interval_seconds=self.refresh_interval,
        )

    async def stop(self) -> None:
        """Stop background refresh task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("cache_refresh_stopped")

    async def _refresh_loop(self) -> None:
        """Background loop to refresh cache."""
        while self._running:
            try:
                await asyncio.sleep(self.refresh_interval)
                await self.wallet_cache.refresh_sets()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("cache_refresh_error", error=str(e))
```

---

## Implementation Tasks

- [ ] Create signal filter module
- [ ] Implement efficient wallet lookup (< 50ms)
- [ ] Add in-memory cache for monitored wallets
- [ ] Integrate blacklist check
- [ ] Log discarded signals at DEBUG level
- [ ] Pass filtered signals to scoring pipeline

## Definition of Done

- [ ] Only monitored wallet signals proceed
- [ ] Lookup time < 50ms
- [ ] Blacklisted wallets blocked
- [ ] Non-monitored signals discarded efficiently
