# Story 2.2: Synchronized Buying Pattern Detection (SYNCED_BUY)

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: ready
- **Priority**: High
- **FR**: FR8

## User Story

**As an** operator,
**I want** the system to detect when wallets buy the same token within a short time window,
**So that** I can identify coordinated buying behavior.

## Acceptance Criteria

### AC 1: Sync Detection
**Given** transaction history for monitored wallets
**When** sync detection analysis runs
**Then** wallets buying the same token within 5 minutes are identified
**And** SYNCED_BUY edges are created in Neo4j between the wallets
**And** edge properties include: token address, time delta, buy amounts

### AC 2: Relationship Query
**Given** wallets A and B bought token X within 3 minutes
**When** the relationship is queried
**Then** SYNCED_BUY edge is returned with token and timing details
**And** sync count (how many times they've synced) is available

### AC 3: Results Summary
**Given** sync detection completes
**When** results are summarized
**Then** count of new SYNCED_BUY relationships is provided
**And** wallets with highest sync frequency are highlighted

## Technical Notes

- Implement sync detection in `src/walltrack/discovery/scanner.py` or dedicated module
- FR8: Detect synchronized buying patterns within 5 min
- Neo4j edge: (Wallet)-[:SYNCED_BUY {token, time_delta, count}]->(Wallet)

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/sync.py
"""Synchronized buying pattern models."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class SyncedBuyEdge(BaseModel):
    """SYNCED_BUY relationship between wallets."""

    wallet_a: str = Field(..., description="First wallet in sync pair")
    wallet_b: str = Field(..., description="Second wallet in sync pair")
    token_address: str = Field(..., description="Token they bought")
    time_delta_seconds: float = Field(..., ge=0, description="Time between buys")
    wallet_a_amount: float = Field(..., ge=0, description="Amount wallet A bought")
    wallet_b_amount: float = Field(..., ge=0, description="Amount wallet B bought")
    wallet_a_timestamp: datetime
    wallet_b_timestamp: datetime
    tx_signature_a: str
    tx_signature_b: str

    class Config:
        frozen = True


class SyncedBuyRelationship(BaseModel):
    """Aggregated SYNCED_BUY relationship between two wallets."""

    wallet_a: str
    wallet_b: str
    sync_count: int = Field(default=1, description="Times they've synced")
    tokens_synced: list[str] = Field(default_factory=list, description="Tokens bought together")
    avg_time_delta_seconds: float = Field(default=0.0)
    first_sync: datetime
    last_sync: datetime
    total_volume_usd: float = Field(default=0.0)


class SyncEvent(BaseModel):
    """A single synchronized buying event."""

    token_address: str
    token_symbol: Optional[str] = None
    participants: list[str] = Field(..., description="Wallets that bought within window")
    buy_timestamps: list[datetime] = Field(default_factory=list)
    time_span_seconds: float = Field(..., description="Time from first to last buy")
    total_buy_amount_sol: float = Field(default=0.0)


class SyncDetectionResult(BaseModel):
    """Result of sync detection analysis."""

    analysis_window_hours: int
    tokens_analyzed: int = Field(default=0)
    sync_events_found: int = Field(default=0)
    edges_created: int = Field(default=0)
    edges_updated: int = Field(default=0)
    high_frequency_pairs: list[SyncedBuyRelationship] = Field(default_factory=list)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class WalletSyncProfile(BaseModel):
    """Sync statistics for a single wallet."""

    wallet_address: str
    total_syncs: int = Field(default=0)
    unique_sync_partners: int = Field(default=0)
    tokens_synced_on: int = Field(default=0)
    top_sync_partners: list[str] = Field(default_factory=list)
    avg_sync_time_delta_seconds: float = Field(default=0.0)
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/sync.py
"""Sync detection constants."""

# Time window for synchronized buys (seconds)
SYNC_WINDOW_SECONDS = 300  # 5 minutes

# Minimum buys in window to consider as sync event
MIN_SYNC_PARTICIPANTS = 2

# High-frequency threshold (sync count)
HIGH_FREQUENCY_SYNC_THRESHOLD = 5

# Analysis lookback window (hours)
DEFAULT_ANALYSIS_WINDOW_HOURS = 24

# Maximum time delta to consider as "synchronized"
MAX_SYNC_TIME_DELTA_SECONDS = 300

# Minimum token amount to consider (filter dust)
MIN_TOKEN_BUY_AMOUNT_SOL = 0.01
```

### 3. Neo4j Schema & Queries

```python
# src/walltrack/data/neo4j/queries/sync.py
"""Neo4j queries for SYNCED_BUY relationships."""


class SyncQueries:
    """Cypher queries for SYNCED_BUY edges."""

    # Create or update SYNCED_BUY edge
    CREATE_SYNCED_BUY = """
    MATCH (a:Wallet {address: $wallet_a})
    MATCH (b:Wallet {address: $wallet_b})
    MERGE (a)-[r:SYNCED_BUY]->(b)
    ON CREATE SET
        r.sync_count = 1,
        r.tokens = [$token_address],
        r.avg_time_delta = $time_delta_seconds,
        r.first_sync = datetime($first_timestamp),
        r.last_sync = datetime($last_timestamp),
        r.total_volume = $total_amount,
        r.created_at = datetime()
    ON MATCH SET
        r.sync_count = r.sync_count + 1,
        r.tokens = CASE
            WHEN NOT $token_address IN r.tokens
            THEN r.tokens + [$token_address]
            ELSE r.tokens END,
        r.avg_time_delta = (r.avg_time_delta * (r.sync_count - 1) + $time_delta_seconds) / r.sync_count,
        r.last_sync = datetime($last_timestamp),
        r.total_volume = r.total_volume + $total_amount,
        r.updated_at = datetime()
    RETURN r, r.sync_count AS new_count
    """

    # Get sync relationship between two wallets
    GET_SYNC_RELATIONSHIP = """
    MATCH (a:Wallet {address: $wallet_a})-[r:SYNCED_BUY]-(b:Wallet {address: $wallet_b})
    RETURN r.sync_count AS sync_count,
           r.tokens AS tokens,
           r.avg_time_delta AS avg_time_delta,
           r.first_sync AS first_sync,
           r.last_sync AS last_sync,
           r.total_volume AS total_volume
    """

    # Get all sync partners for a wallet
    GET_SYNC_PARTNERS = """
    MATCH (w:Wallet {address: $wallet_address})-[r:SYNCED_BUY]-(partner:Wallet)
    RETURN partner.address AS partner_address,
           r.sync_count AS sync_count,
           r.tokens AS tokens,
           r.avg_time_delta AS avg_time_delta,
           r.last_sync AS last_sync
    ORDER BY r.sync_count DESC
    LIMIT $limit
    """

    # Get high-frequency sync pairs
    GET_HIGH_FREQUENCY_PAIRS = """
    MATCH (a:Wallet)-[r:SYNCED_BUY]->(b:Wallet)
    WHERE r.sync_count >= $min_sync_count
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.sync_count AS sync_count,
           r.tokens AS tokens,
           r.avg_time_delta AS avg_time_delta,
           r.first_sync AS first_sync,
           r.last_sync AS last_sync,
           r.total_volume AS total_volume
    ORDER BY r.sync_count DESC
    LIMIT $limit
    """

    # Find wallets that sync on a specific token
    GET_SYNCS_BY_TOKEN = """
    MATCH (a:Wallet)-[r:SYNCED_BUY]->(b:Wallet)
    WHERE $token_address IN r.tokens
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.sync_count AS sync_count,
           r.last_sync AS last_sync
    ORDER BY r.sync_count DESC
    """

    # Get wallet sync profile
    GET_WALLET_SYNC_PROFILE = """
    MATCH (w:Wallet {address: $wallet_address})-[r:SYNCED_BUY]-(partner:Wallet)
    WITH w,
         count(DISTINCT partner) AS unique_partners,
         sum(r.sync_count) AS total_syncs,
         avg(r.avg_time_delta) AS avg_delta,
         collect(DISTINCT partner.address)[..5] AS top_partners,
         reduce(tokens = [], rel IN collect(r) | tokens + rel.tokens) AS all_tokens
    RETURN unique_partners,
           total_syncs,
           avg_delta,
           top_partners,
           size(apoc.coll.toSet(all_tokens)) AS tokens_count
    """

    # Delete sync edge
    DELETE_SYNCED_BUY = """
    MATCH (a:Wallet {address: $wallet_a})-[r:SYNCED_BUY]-(b:Wallet {address: $wallet_b})
    DELETE r
    RETURN count(r) AS deleted_count
    """

    # Get all sync edges for cluster detection
    GET_ALL_SYNC_EDGES = """
    MATCH (a:Wallet)-[r:SYNCED_BUY]->(b:Wallet)
    WHERE r.sync_count >= $min_sync_count
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.sync_count AS weight
    """
```

### 4. SyncDetector Service

```python
# src/walltrack/core/services/sync_detector.py
"""Service for detecting synchronized buying patterns."""
import structlog
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from typing import Optional

from walltrack.core.models.sync import (
    SyncedBuyEdge, SyncedBuyRelationship, SyncEvent,
    SyncDetectionResult, WalletSyncProfile
)
from walltrack.core.constants.sync import (
    SYNC_WINDOW_SECONDS, MIN_SYNC_PARTICIPANTS,
    HIGH_FREQUENCY_SYNC_THRESHOLD, DEFAULT_ANALYSIS_WINDOW_HOURS,
    MIN_TOKEN_BUY_AMOUNT_SOL
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.sync import SyncQueries
from walltrack.data.supabase.repositories.trade import TradeRepository

logger = structlog.get_logger(__name__)


class SyncDetector:
    """Detects synchronized buying patterns between wallets."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        trade_repo: TradeRepository,
    ):
        self.neo4j = neo4j_client
        self.trade_repo = trade_repo
        self.queries = SyncQueries()

    async def detect_synced_buys(
        self,
        hours_back: int = DEFAULT_ANALYSIS_WINDOW_HOURS,
        wallet_addresses: Optional[list[str]] = None,
    ) -> SyncDetectionResult:
        """
        Analyze recent buys to detect synchronized patterns.

        Args:
            hours_back: Hours to look back for analysis
            wallet_addresses: Specific wallets to analyze (None = all monitored)

        Returns:
            SyncDetectionResult with detection statistics
        """
        logger.info("detecting_synced_buys", hours_back=hours_back)

        since = datetime.utcnow() - timedelta(hours=hours_back)

        # Fetch recent buy transactions
        buys = await self._fetch_recent_buys(since, wallet_addresses)

        # Group buys by token
        buys_by_token = self._group_buys_by_token(buys)

        edges_created = 0
        edges_updated = 0
        sync_events = []

        # Analyze each token's buys for sync patterns
        for token_address, token_buys in buys_by_token.items():
            events = self._find_sync_events(token_address, token_buys)

            for event in events:
                sync_events.append(event)

                # Create edges between all participants
                result = await self._create_sync_edges(event)
                edges_created += result["created"]
                edges_updated += result["updated"]

        # Get high-frequency pairs
        high_freq_pairs = await self.get_high_frequency_pairs(
            min_count=HIGH_FREQUENCY_SYNC_THRESHOLD
        )

        result = SyncDetectionResult(
            analysis_window_hours=hours_back,
            tokens_analyzed=len(buys_by_token),
            sync_events_found=len(sync_events),
            edges_created=edges_created,
            edges_updated=edges_updated,
            high_frequency_pairs=high_freq_pairs,
        )

        logger.info(
            "sync_detection_complete",
            tokens=len(buys_by_token),
            events=len(sync_events),
            edges=edges_created + edges_updated,
        )

        return result

    async def _fetch_recent_buys(
        self,
        since: datetime,
        wallet_addresses: Optional[list[str]] = None,
    ) -> list[dict]:
        """Fetch recent buy transactions from trade repository."""
        trades = await self.trade_repo.get_trades_since(
            since=since,
            trade_type="buy",
            wallet_addresses=wallet_addresses,
            min_amount_sol=MIN_TOKEN_BUY_AMOUNT_SOL,
        )

        return [
            {
                "wallet_address": t.wallet_address,
                "token_address": t.token_address,
                "amount_sol": t.amount_sol,
                "timestamp": t.executed_at,
                "tx_signature": t.tx_signature,
            }
            for t in trades
        ]

    def _group_buys_by_token(self, buys: list[dict]) -> dict[str, list[dict]]:
        """Group buy transactions by token address."""
        by_token = defaultdict(list)
        for buy in buys:
            by_token[buy["token_address"]].append(buy)
        return dict(by_token)

    def _find_sync_events(
        self,
        token_address: str,
        buys: list[dict],
    ) -> list[SyncEvent]:
        """
        Find synchronized buy events for a token.

        Uses sliding window to detect wallets buying within SYNC_WINDOW_SECONDS.
        """
        if len(buys) < MIN_SYNC_PARTICIPANTS:
            return []

        # Sort by timestamp
        sorted_buys = sorted(buys, key=lambda x: x["timestamp"])
        events = []

        # Sliding window approach
        i = 0
        while i < len(sorted_buys):
            window_start = sorted_buys[i]["timestamp"]
            window_end = window_start + timedelta(seconds=SYNC_WINDOW_SECONDS)

            # Collect all buys within window
            window_buys = []
            j = i
            while j < len(sorted_buys) and sorted_buys[j]["timestamp"] <= window_end:
                window_buys.append(sorted_buys[j])
                j += 1

            # Get unique wallets in window
            unique_wallets = set(b["wallet_address"] for b in window_buys)

            if len(unique_wallets) >= MIN_SYNC_PARTICIPANTS:
                # This is a sync event
                participants = list(unique_wallets)
                timestamps = [b["timestamp"] for b in window_buys]
                total_amount = sum(b["amount_sol"] for b in window_buys)

                time_span = (max(timestamps) - min(timestamps)).total_seconds()

                event = SyncEvent(
                    token_address=token_address,
                    participants=participants,
                    buy_timestamps=timestamps,
                    time_span_seconds=time_span,
                    total_buy_amount_sol=total_amount,
                )
                events.append(event)

                # Skip to end of window to avoid duplicate events
                i = j
            else:
                i += 1

        return events

    async def _create_sync_edges(self, event: SyncEvent) -> dict[str, int]:
        """Create SYNCED_BUY edges for all participant pairs."""
        created = 0
        updated = 0

        # Create edges between all pairs
        for wallet_a, wallet_b in combinations(sorted(event.participants), 2):
            # Calculate time delta for this pair
            time_delta = event.time_span_seconds / max(len(event.participants) - 1, 1)

            result = await self.neo4j.execute_write(
                self.queries.CREATE_SYNCED_BUY,
                {
                    "wallet_a": wallet_a,
                    "wallet_b": wallet_b,
                    "token_address": event.token_address,
                    "time_delta_seconds": time_delta,
                    "first_timestamp": min(event.buy_timestamps).isoformat(),
                    "last_timestamp": max(event.buy_timestamps).isoformat(),
                    "total_amount": event.total_buy_amount_sol / len(event.participants),
                }
            )

            if result:
                record = result[0]
                new_count = record.get("new_count", 1)
                if new_count == 1:
                    created += 1
                else:
                    updated += 1

        return {"created": created, "updated": updated}

    async def get_sync_relationship(
        self,
        wallet_a: str,
        wallet_b: str,
    ) -> Optional[SyncedBuyRelationship]:
        """Get sync relationship between two wallets."""
        result = await self.neo4j.execute_read(
            self.queries.GET_SYNC_RELATIONSHIP,
            {"wallet_a": wallet_a, "wallet_b": wallet_b}
        )

        if not result:
            return None

        record = result[0]
        return SyncedBuyRelationship(
            wallet_a=wallet_a,
            wallet_b=wallet_b,
            sync_count=record["sync_count"],
            tokens_synced=record.get("tokens", []),
            avg_time_delta_seconds=record.get("avg_time_delta", 0.0),
            first_sync=record["first_sync"],
            last_sync=record["last_sync"],
            total_volume_usd=record.get("total_volume", 0.0),
        )

    async def get_sync_partners(
        self,
        wallet_address: str,
        limit: int = 20,
    ) -> list[SyncedBuyRelationship]:
        """Get all sync partners for a wallet."""
        result = await self.neo4j.execute_read(
            self.queries.GET_SYNC_PARTNERS,
            {"wallet_address": wallet_address, "limit": limit}
        )

        partners = []
        for record in result:
            rel = SyncedBuyRelationship(
                wallet_a=wallet_address,
                wallet_b=record["partner_address"],
                sync_count=record["sync_count"],
                tokens_synced=record.get("tokens", []),
                avg_time_delta_seconds=record.get("avg_time_delta", 0.0),
                first_sync=record.get("first_sync", datetime.utcnow()),
                last_sync=record["last_sync"],
            )
            partners.append(rel)

        return partners

    async def get_high_frequency_pairs(
        self,
        min_count: int = HIGH_FREQUENCY_SYNC_THRESHOLD,
        limit: int = 50,
    ) -> list[SyncedBuyRelationship]:
        """Get wallet pairs with high sync frequency."""
        result = await self.neo4j.execute_read(
            self.queries.GET_HIGH_FREQUENCY_PAIRS,
            {"min_sync_count": min_count, "limit": limit}
        )

        pairs = []
        for record in result:
            rel = SyncedBuyRelationship(
                wallet_a=record["wallet_a"],
                wallet_b=record["wallet_b"],
                sync_count=record["sync_count"],
                tokens_synced=record.get("tokens", []),
                avg_time_delta_seconds=record.get("avg_time_delta", 0.0),
                first_sync=record["first_sync"],
                last_sync=record["last_sync"],
                total_volume_usd=record.get("total_volume", 0.0),
            )
            pairs.append(rel)

        return pairs

    async def get_wallet_sync_profile(
        self,
        wallet_address: str,
    ) -> Optional[WalletSyncProfile]:
        """Get sync statistics for a wallet."""
        result = await self.neo4j.execute_read(
            self.queries.GET_WALLET_SYNC_PROFILE,
            {"wallet_address": wallet_address}
        )

        if not result:
            return None

        record = result[0]
        return WalletSyncProfile(
            wallet_address=wallet_address,
            total_syncs=record.get("total_syncs", 0),
            unique_sync_partners=record.get("unique_partners", 0),
            tokens_synced_on=record.get("tokens_count", 0),
            top_sync_partners=record.get("top_partners", []),
            avg_sync_time_delta_seconds=record.get("avg_delta", 0.0),
        )

    async def get_syncs_by_token(
        self,
        token_address: str,
    ) -> list[SyncedBuyRelationship]:
        """Get all sync relationships involving a specific token."""
        result = await self.neo4j.execute_read(
            self.queries.GET_SYNCS_BY_TOKEN,
            {"token_address": token_address}
        )

        syncs = []
        for record in result:
            rel = SyncedBuyRelationship(
                wallet_a=record["wallet_a"],
                wallet_b=record["wallet_b"],
                sync_count=record["sync_count"],
                tokens_synced=[token_address],
                first_sync=record.get("last_sync", datetime.utcnow()),
                last_sync=record["last_sync"],
            )
            syncs.append(rel)

        return syncs
```

### 5. Scheduled Task

```python
# src/walltrack/tasks/sync_detection.py
"""Scheduled task for sync detection."""
import structlog
from datetime import datetime

from walltrack.core.services.sync_detector import SyncDetector
from walltrack.core.constants.sync import DEFAULT_ANALYSIS_WINDOW_HOURS

logger = structlog.get_logger(__name__)


async def run_sync_detection(
    detector: SyncDetector,
    hours_back: int = DEFAULT_ANALYSIS_WINDOW_HOURS,
) -> None:
    """
    Run sync detection analysis.

    Called by scheduler (e.g., every hour).
    """
    logger.info("starting_scheduled_sync_detection", hours_back=hours_back)

    try:
        result = await detector.detect_synced_buys(hours_back=hours_back)

        logger.info(
            "scheduled_sync_detection_complete",
            events=result.sync_events_found,
            edges_created=result.edges_created,
            high_freq_pairs=len(result.high_frequency_pairs),
        )

        # Alert on high-frequency pairs
        if result.high_frequency_pairs:
            logger.warning(
                "high_frequency_sync_pairs_detected",
                count=len(result.high_frequency_pairs),
                top_pair={
                    "wallets": [
                        result.high_frequency_pairs[0].wallet_a,
                        result.high_frequency_pairs[0].wallet_b,
                    ],
                    "sync_count": result.high_frequency_pairs[0].sync_count,
                }
            )

    except Exception as e:
        logger.error("sync_detection_failed", error=str(e))
        raise
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/sync.py
"""Sync detection API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from walltrack.core.models.sync import (
    SyncDetectionResult, SyncedBuyRelationship, WalletSyncProfile
)
from walltrack.core.services.sync_detector import SyncDetector
from walltrack.core.constants.sync import (
    DEFAULT_ANALYSIS_WINDOW_HOURS, HIGH_FREQUENCY_SYNC_THRESHOLD
)
from walltrack.api.dependencies import get_sync_detector

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/detect", response_model=SyncDetectionResult)
async def detect_synced_buys(
    hours_back: int = Query(default=DEFAULT_ANALYSIS_WINDOW_HOURS, ge=1, le=168),
    wallet_addresses: Optional[list[str]] = None,
    detector: SyncDetector = Depends(get_sync_detector),
) -> SyncDetectionResult:
    """
    Run sync detection analysis on recent trades.
    """
    try:
        return await detector.detect_synced_buys(hours_back, wallet_addresses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationship", response_model=Optional[SyncedBuyRelationship])
async def get_sync_relationship(
    wallet_a: str = Query(...),
    wallet_b: str = Query(...),
    detector: SyncDetector = Depends(get_sync_detector),
) -> Optional[SyncedBuyRelationship]:
    """
    Get sync relationship between two wallets.
    """
    try:
        return await detector.get_sync_relationship(wallet_a, wallet_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/partners", response_model=list[SyncedBuyRelationship])
async def get_sync_partners(
    wallet_address: str,
    limit: int = Query(default=20, ge=1, le=100),
    detector: SyncDetector = Depends(get_sync_detector),
) -> list[SyncedBuyRelationship]:
    """
    Get all wallets that have synced buys with the given wallet.
    """
    try:
        return await detector.get_sync_partners(wallet_address, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/profile", response_model=Optional[WalletSyncProfile])
async def get_wallet_sync_profile(
    wallet_address: str,
    detector: SyncDetector = Depends(get_sync_detector),
) -> Optional[WalletSyncProfile]:
    """
    Get sync statistics for a wallet.
    """
    try:
        return await detector.get_wallet_sync_profile(wallet_address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/high-frequency", response_model=list[SyncedBuyRelationship])
async def get_high_frequency_pairs(
    min_count: int = Query(default=HIGH_FREQUENCY_SYNC_THRESHOLD, ge=2),
    limit: int = Query(default=50, ge=1, le=200),
    detector: SyncDetector = Depends(get_sync_detector),
) -> list[SyncedBuyRelationship]:
    """
    Get wallet pairs with high sync frequency (potential coordination).
    """
    try:
        return await detector.get_high_frequency_pairs(min_count, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/token/{token_address}", response_model=list[SyncedBuyRelationship])
async def get_syncs_by_token(
    token_address: str,
    detector: SyncDetector = Depends(get_sync_detector),
) -> list[SyncedBuyRelationship]:
    """
    Get all sync relationships involving a specific token.
    """
    try:
        return await detector.get_syncs_by_token(token_address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 7. Unit Tests

```python
# tests/unit/core/services/test_sync_detector.py
"""Tests for SyncDetector service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.services.sync_detector import SyncDetector
from walltrack.core.models.sync import SyncEvent, SyncedBuyRelationship


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    client.execute_write = AsyncMock(return_value=[{"new_count": 1}])
    return client


@pytest.fixture
def mock_trade_repo():
    """Mock trade repository."""
    repo = AsyncMock()
    repo.get_trades_since = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def detector(mock_neo4j, mock_trade_repo):
    """Create SyncDetector with mocks."""
    return SyncDetector(mock_neo4j, mock_trade_repo)


class TestFindSyncEvents:
    """Tests for _find_sync_events."""

    def test_detects_sync_within_window(self, detector):
        """Should detect wallets buying within 5 minutes."""
        now = datetime.utcnow()
        buys = [
            {"wallet_address": "wallet1", "timestamp": now, "amount_sol": 1.0},
            {"wallet_address": "wallet2", "timestamp": now + timedelta(seconds=60), "amount_sol": 2.0},
            {"wallet_address": "wallet3", "timestamp": now + timedelta(seconds=120), "amount_sol": 1.5},
        ]

        events = detector._find_sync_events("token123", buys)

        assert len(events) == 1
        assert len(events[0].participants) == 3
        assert events[0].time_span_seconds <= 300

    def test_ignores_buys_outside_window(self, detector):
        """Should not detect sync for buys > 5 minutes apart."""
        now = datetime.utcnow()
        buys = [
            {"wallet_address": "wallet1", "timestamp": now, "amount_sol": 1.0},
            {"wallet_address": "wallet2", "timestamp": now + timedelta(minutes=10), "amount_sol": 2.0},
        ]

        events = detector._find_sync_events("token123", buys)

        assert len(events) == 0

    def test_requires_minimum_participants(self, detector):
        """Should require at least 2 unique wallets."""
        now = datetime.utcnow()
        buys = [
            {"wallet_address": "wallet1", "timestamp": now, "amount_sol": 1.0},
            {"wallet_address": "wallet1", "timestamp": now + timedelta(seconds=60), "amount_sol": 2.0},
        ]

        events = detector._find_sync_events("token123", buys)

        assert len(events) == 0


class TestDetectSyncedBuys:
    """Tests for detect_synced_buys."""

    @pytest.mark.asyncio
    async def test_creates_edges_for_sync_events(self, detector, mock_trade_repo, mock_neo4j):
        """Should create SYNCED_BUY edges for detected patterns."""
        now = datetime.utcnow()

        # Mock trades
        mock_trade = MagicMock()
        mock_trade.wallet_address = "wallet1"
        mock_trade.token_address = "token123"
        mock_trade.amount_sol = 1.0
        mock_trade.executed_at = now
        mock_trade.tx_signature = "sig1"

        mock_trade2 = MagicMock()
        mock_trade2.wallet_address = "wallet2"
        mock_trade2.token_address = "token123"
        mock_trade2.amount_sol = 2.0
        mock_trade2.executed_at = now + timedelta(seconds=60)
        mock_trade2.tx_signature = "sig2"

        mock_trade_repo.get_trades_since.return_value = [mock_trade, mock_trade2]

        result = await detector.detect_synced_buys(hours_back=24)

        assert result.sync_events_found == 1
        assert result.edges_created >= 1
        assert mock_neo4j.execute_write.called


class TestGetSyncPartners:
    """Tests for get_sync_partners."""

    @pytest.mark.asyncio
    async def test_returns_sync_partners(self, detector, mock_neo4j):
        """Should return wallets that synced with target."""
        mock_neo4j.execute_read.return_value = [
            {
                "partner_address": "partner1",
                "sync_count": 5,
                "tokens": ["token1", "token2"],
                "avg_time_delta": 120.0,
                "last_sync": datetime.utcnow(),
            }
        ]

        partners = await detector.get_sync_partners("wallet123")

        assert len(partners) == 1
        assert partners[0].wallet_b == "partner1"
        assert partners[0].sync_count == 5


class TestGetHighFrequencyPairs:
    """Tests for get_high_frequency_pairs."""

    @pytest.mark.asyncio
    async def test_returns_high_frequency_pairs(self, detector, mock_neo4j):
        """Should return pairs with sync_count >= threshold."""
        mock_neo4j.execute_read.return_value = [
            {
                "wallet_a": "wallet1",
                "wallet_b": "wallet2",
                "sync_count": 10,
                "tokens": ["token1"],
                "avg_time_delta": 60.0,
                "first_sync": datetime.utcnow() - timedelta(days=7),
                "last_sync": datetime.utcnow(),
                "total_volume": 100.0,
            }
        ]

        pairs = await detector.get_high_frequency_pairs(min_count=5)

        assert len(pairs) == 1
        assert pairs[0].sync_count == 10


class TestGroupBuysByToken:
    """Tests for _group_buys_by_token."""

    def test_groups_correctly(self, detector):
        """Should group buys by token address."""
        buys = [
            {"token_address": "token1", "wallet_address": "w1"},
            {"token_address": "token2", "wallet_address": "w2"},
            {"token_address": "token1", "wallet_address": "w3"},
        ]

        grouped = detector._group_buys_by_token(buys)

        assert len(grouped) == 2
        assert len(grouped["token1"]) == 2
        assert len(grouped["token2"]) == 1
```

---

## Implementation Tasks

- [ ] Create sync detection module
- [ ] Implement 5-minute window analysis
- [ ] Create SYNCED_BUY edge creation in Neo4j
- [ ] Track sync count per wallet pair
- [ ] Implement high-frequency sync highlighting
- [ ] Add results summary reporting

## Definition of Done

- [ ] Synchronized buying detected within 5-minute window
- [ ] SYNCED_BUY edges created with properties
- [ ] Sync count tracked per wallet pair
- [ ] High-frequency syncing wallets highlighted
