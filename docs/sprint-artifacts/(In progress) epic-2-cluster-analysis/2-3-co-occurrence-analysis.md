# Story 2.3: Co-occurrence Analysis on Early Tokens

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: ready
- **Priority**: High
- **FR**: FR9

## User Story

**As an** operator,
**I want** to identify wallets that consistently appear together on early token entries,
**So that** I can detect wallets that may share insider information.

## Acceptance Criteria

### AC 1: Co-occurrence Detection
**Given** historical trade data for wallets
**When** co-occurrence analysis runs
**Then** tokens where wallet entered in first 10 minutes are identified
**And** other wallets that entered the same tokens early are found
**And** co-occurrence count per wallet pair is calculated

### AC 2: Threshold Flagging
**Given** wallets A and B appeared together on 5+ early tokens
**When** co-occurrence threshold is met
**Then** relationship is flagged as "high_co_occurrence"
**And** CO_OCCURS edge is created/updated in Neo4j
**And** shared tokens list is stored

### AC 3: Associates Query
**Given** co-occurrence data exists
**When** operator queries a wallet's associates
**Then** all wallets with co-occurrence > threshold are returned
**And** shared token count and list are provided

## Technical Notes

- FR9: Identify wallets appearing together on multiple early tokens
- Store in Neo4j: (Wallet)-[:CO_OCCURS {count, tokens}]->(Wallet)
- Run as periodic batch job via APScheduler

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/cooccurrence.py
"""Co-occurrence analysis models."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional


class CoOccurrenceFlag(str, Enum):
    """Co-occurrence relationship flags."""
    NORMAL = "normal"
    HIGH_CO_OCCURRENCE = "high_co_occurrence"
    VERY_HIGH_CO_OCCURRENCE = "very_high_co_occurrence"


class CoOccursEdge(BaseModel):
    """CO_OCCURS relationship between wallets."""

    wallet_a: str = Field(..., description="First wallet")
    wallet_b: str = Field(..., description="Second wallet")
    co_occurrence_count: int = Field(default=0, description="Number of shared early entries")
    shared_tokens: list[str] = Field(default_factory=list, description="Tokens both entered early")
    flag: CoOccurrenceFlag = Field(default=CoOccurrenceFlag.NORMAL)
    avg_entry_delta_seconds: float = Field(default=0.0, description="Average time between their entries")
    first_co_occurrence: datetime
    last_co_occurrence: datetime
    strength: float = Field(default=0.0, ge=0, le=1, description="Relationship strength")

    class Config:
        frozen = True


class EarlyEntry(BaseModel):
    """A wallet's early entry into a token."""

    wallet_address: str
    token_address: str
    entry_timestamp: datetime
    token_launch_timestamp: datetime
    entry_delay_seconds: float = Field(..., description="Seconds after launch")
    amount_sol: float
    tx_signature: str


class CoOccurrenceEvent(BaseModel):
    """A single co-occurrence event on a token."""

    token_address: str
    token_symbol: Optional[str] = None
    launch_timestamp: datetime
    early_wallets: list[str] = Field(..., description="Wallets that entered within first 10 min")
    entry_times: dict[str, datetime] = Field(default_factory=dict)


class CoOccurrenceAnalysisResult(BaseModel):
    """Result of co-occurrence analysis."""

    tokens_analyzed: int = Field(default=0)
    early_entries_found: int = Field(default=0)
    co_occurrence_pairs: int = Field(default=0)
    edges_created: int = Field(default=0)
    edges_updated: int = Field(default=0)
    high_co_occurrence_pairs: int = Field(default=0)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class WalletAssociate(BaseModel):
    """An associate wallet with co-occurrence relationship."""

    wallet_address: str
    co_occurrence_count: int
    shared_tokens: list[str]
    flag: CoOccurrenceFlag
    strength: float
    last_co_occurrence: datetime
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/cooccurrence.py
"""Co-occurrence analysis constants."""

# Time window for "early" entry (seconds from token launch)
EARLY_ENTRY_WINDOW_SECONDS = 600  # 10 minutes

# Threshold for high co-occurrence flag
HIGH_CO_OCCURRENCE_THRESHOLD = 5

# Threshold for very high co-occurrence flag
VERY_HIGH_CO_OCCURRENCE_THRESHOLD = 10

# Minimum entries to consider a wallet for analysis
MIN_EARLY_ENTRIES_FOR_ANALYSIS = 3

# Analysis lookback window (days)
DEFAULT_ANALYSIS_WINDOW_DAYS = 30

# Strength calculation factors
STRENGTH_COUNT_WEIGHT = 0.5
STRENGTH_RECENCY_WEIGHT = 0.3
STRENGTH_CONSISTENCY_WEIGHT = 0.2

# Maximum shared tokens to store on edge
MAX_SHARED_TOKENS_STORED = 50
```

### 3. Neo4j Schema & Queries

```python
# src/walltrack/data/neo4j/queries/cooccurrence.py
"""Neo4j queries for CO_OCCURS relationships."""


class CoOccurrenceQueries:
    """Cypher queries for CO_OCCURS edges."""

    # Create or update CO_OCCURS edge
    CREATE_CO_OCCURS = """
    MATCH (a:Wallet {address: $wallet_a})
    MATCH (b:Wallet {address: $wallet_b})
    MERGE (a)-[r:CO_OCCURS]->(b)
    ON CREATE SET
        r.count = 1,
        r.tokens = [$token_address],
        r.flag = $flag,
        r.avg_entry_delta = $entry_delta,
        r.first_co_occurrence = datetime($timestamp),
        r.last_co_occurrence = datetime($timestamp),
        r.strength = $strength,
        r.created_at = datetime()
    ON MATCH SET
        r.count = r.count + 1,
        r.tokens = CASE
            WHEN size(r.tokens) < $max_tokens AND NOT $token_address IN r.tokens
            THEN r.tokens + [$token_address]
            ELSE r.tokens END,
        r.flag = CASE
            WHEN r.count + 1 >= $very_high_threshold THEN 'very_high_co_occurrence'
            WHEN r.count + 1 >= $high_threshold THEN 'high_co_occurrence'
            ELSE r.flag END,
        r.avg_entry_delta = (r.avg_entry_delta * r.count + $entry_delta) / (r.count + 1),
        r.last_co_occurrence = datetime($timestamp),
        r.strength = $strength,
        r.updated_at = datetime()
    RETURN r, r.count AS new_count
    """

    # Get co-occurrence relationship between two wallets
    GET_CO_OCCURRENCE = """
    MATCH (a:Wallet {address: $wallet_a})-[r:CO_OCCURS]-(b:Wallet {address: $wallet_b})
    RETURN r.count AS count,
           r.tokens AS tokens,
           r.flag AS flag,
           r.avg_entry_delta AS avg_entry_delta,
           r.first_co_occurrence AS first_co_occurrence,
           r.last_co_occurrence AS last_co_occurrence,
           r.strength AS strength
    """

    # Get all associates for a wallet
    GET_ASSOCIATES = """
    MATCH (w:Wallet {address: $wallet_address})-[r:CO_OCCURS]-(associate:Wallet)
    WHERE r.count >= $min_count
    RETURN associate.address AS wallet_address,
           r.count AS co_occurrence_count,
           r.tokens AS shared_tokens,
           r.flag AS flag,
           r.strength AS strength,
           r.last_co_occurrence AS last_co_occurrence
    ORDER BY r.count DESC
    LIMIT $limit
    """

    # Get high co-occurrence pairs
    GET_HIGH_CO_OCCURRENCE_PAIRS = """
    MATCH (a:Wallet)-[r:CO_OCCURS]->(b:Wallet)
    WHERE r.flag IN ['high_co_occurrence', 'very_high_co_occurrence']
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.count AS count,
           r.tokens AS tokens,
           r.flag AS flag,
           r.strength AS strength,
           r.last_co_occurrence AS last_co_occurrence
    ORDER BY r.count DESC
    LIMIT $limit
    """

    # Get wallets by co-occurrence on specific token
    GET_CO_OCCURS_ON_TOKEN = """
    MATCH (a:Wallet)-[r:CO_OCCURS]->(b:Wallet)
    WHERE $token_address IN r.tokens
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.count AS count,
           r.flag AS flag
    ORDER BY r.count DESC
    """

    # Update flag on existing edge
    UPDATE_FLAG = """
    MATCH (a:Wallet {address: $wallet_a})-[r:CO_OCCURS]-(b:Wallet {address: $wallet_b})
    SET r.flag = $flag,
        r.updated_at = datetime()
    RETURN r
    """

    # Get all CO_OCCURS edges for cluster analysis
    GET_ALL_CO_OCCURS_EDGES = """
    MATCH (a:Wallet)-[r:CO_OCCURS]->(b:Wallet)
    WHERE r.count >= $min_count
    RETURN a.address AS wallet_a,
           b.address AS wallet_b,
           r.count AS weight
    """

    # Delete co-occurrence edge
    DELETE_CO_OCCURS = """
    MATCH (a:Wallet {address: $wallet_a})-[r:CO_OCCURS]-(b:Wallet {address: $wallet_b})
    DELETE r
    RETURN count(r) AS deleted_count
    """

    # Get co-occurrence statistics for a wallet
    GET_WALLET_CO_OCCURRENCE_STATS = """
    MATCH (w:Wallet {address: $wallet_address})-[r:CO_OCCURS]-(associate:Wallet)
    WITH w,
         count(DISTINCT associate) AS total_associates,
         sum(r.count) AS total_co_occurrences,
         avg(r.strength) AS avg_strength,
         collect(DISTINCT r.flag) AS flags,
         reduce(tokens = [], rel IN collect(r) | tokens + rel.tokens) AS all_tokens
    RETURN total_associates,
           total_co_occurrences,
           avg_strength,
           'high_co_occurrence' IN flags AS has_high_co_occurrence,
           size(apoc.coll.toSet(all_tokens)) AS unique_shared_tokens
    """
```

### 4. CoOccurrenceAnalyzer Service

```python
# src/walltrack/core/services/cooccurrence_analyzer.py
"""Service for analyzing wallet co-occurrence patterns."""
import structlog
from collections import defaultdict
from datetime import datetime, timedelta
from itertools import combinations
from typing import Optional

from walltrack.core.models.cooccurrence import (
    CoOccursEdge, CoOccurrenceFlag, EarlyEntry,
    CoOccurrenceEvent, CoOccurrenceAnalysisResult, WalletAssociate
)
from walltrack.core.constants.cooccurrence import (
    EARLY_ENTRY_WINDOW_SECONDS, HIGH_CO_OCCURRENCE_THRESHOLD,
    VERY_HIGH_CO_OCCURRENCE_THRESHOLD, MIN_EARLY_ENTRIES_FOR_ANALYSIS,
    DEFAULT_ANALYSIS_WINDOW_DAYS, MAX_SHARED_TOKENS_STORED,
    STRENGTH_COUNT_WEIGHT, STRENGTH_RECENCY_WEIGHT, STRENGTH_CONSISTENCY_WEIGHT
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cooccurrence import CoOccurrenceQueries
from walltrack.data.supabase.repositories.trade import TradeRepository
from walltrack.data.supabase.repositories.token import TokenRepository

logger = structlog.get_logger(__name__)


class CoOccurrenceAnalyzer:
    """Analyzes co-occurrence patterns on early token entries."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        trade_repo: TradeRepository,
        token_repo: TokenRepository,
    ):
        self.neo4j = neo4j_client
        self.trade_repo = trade_repo
        self.token_repo = token_repo
        self.queries = CoOccurrenceQueries()

    async def analyze_co_occurrences(
        self,
        days_back: int = DEFAULT_ANALYSIS_WINDOW_DAYS,
        wallet_addresses: Optional[list[str]] = None,
    ) -> CoOccurrenceAnalysisResult:
        """
        Analyze co-occurrence patterns in early token entries.

        Args:
            days_back: Days to look back for analysis
            wallet_addresses: Specific wallets to analyze (None = all)

        Returns:
            CoOccurrenceAnalysisResult with analysis statistics
        """
        logger.info("analyzing_co_occurrences", days_back=days_back)

        since = datetime.utcnow() - timedelta(days=days_back)

        # Get tokens launched in the analysis window
        tokens = await self.token_repo.get_tokens_launched_since(since)

        early_entries_total = 0
        edges_created = 0
        edges_updated = 0
        co_occurrence_pairs = set()

        for token in tokens:
            # Get early entries for this token
            early_entries = await self._get_early_entries(
                token.address,
                token.launch_timestamp,
                wallet_addresses,
            )

            if len(early_entries) < MIN_EARLY_ENTRIES_FOR_ANALYSIS:
                continue

            early_entries_total += len(early_entries)

            # Create co-occurrence events
            event = CoOccurrenceEvent(
                token_address=token.address,
                token_symbol=token.symbol,
                launch_timestamp=token.launch_timestamp,
                early_wallets=[e.wallet_address for e in early_entries],
                entry_times={e.wallet_address: e.entry_timestamp for e in early_entries},
            )

            # Create edges for all pairs
            result = await self._create_co_occurrence_edges(event)
            edges_created += result["created"]
            edges_updated += result["updated"]

            # Track unique pairs
            for w1, w2 in combinations(sorted(event.early_wallets), 2):
                co_occurrence_pairs.add((w1, w2))

        # Count high co-occurrence pairs
        high_pairs = await self._count_high_co_occurrence_pairs()

        result = CoOccurrenceAnalysisResult(
            tokens_analyzed=len(tokens),
            early_entries_found=early_entries_total,
            co_occurrence_pairs=len(co_occurrence_pairs),
            edges_created=edges_created,
            edges_updated=edges_updated,
            high_co_occurrence_pairs=high_pairs,
        )

        logger.info(
            "co_occurrence_analysis_complete",
            tokens=len(tokens),
            pairs=len(co_occurrence_pairs),
            high_pairs=high_pairs,
        )

        return result

    async def _get_early_entries(
        self,
        token_address: str,
        launch_timestamp: datetime,
        wallet_addresses: Optional[list[str]] = None,
    ) -> list[EarlyEntry]:
        """Get wallets that entered within the early window."""
        cutoff = launch_timestamp + timedelta(seconds=EARLY_ENTRY_WINDOW_SECONDS)

        trades = await self.trade_repo.get_trades_for_token(
            token_address=token_address,
            trade_type="buy",
            before=cutoff,
            wallet_addresses=wallet_addresses,
        )

        entries = []
        seen_wallets = set()

        for trade in trades:
            # Only count first entry per wallet
            if trade.wallet_address in seen_wallets:
                continue
            seen_wallets.add(trade.wallet_address)

            entry_delay = (trade.executed_at - launch_timestamp).total_seconds()

            if entry_delay <= EARLY_ENTRY_WINDOW_SECONDS:
                entry = EarlyEntry(
                    wallet_address=trade.wallet_address,
                    token_address=token_address,
                    entry_timestamp=trade.executed_at,
                    token_launch_timestamp=launch_timestamp,
                    entry_delay_seconds=entry_delay,
                    amount_sol=trade.amount_sol,
                    tx_signature=trade.tx_signature,
                )
                entries.append(entry)

        return entries

    async def _create_co_occurrence_edges(
        self,
        event: CoOccurrenceEvent,
    ) -> dict[str, int]:
        """Create CO_OCCURS edges for all wallet pairs in event."""
        created = 0
        updated = 0

        wallets = sorted(event.early_wallets)

        for wallet_a, wallet_b in combinations(wallets, 2):
            # Calculate entry time delta
            time_a = event.entry_times.get(wallet_a, event.launch_timestamp)
            time_b = event.entry_times.get(wallet_b, event.launch_timestamp)
            entry_delta = abs((time_a - time_b).total_seconds())

            # Calculate strength
            strength = await self._calculate_strength(wallet_a, wallet_b)

            # Determine flag based on count
            flag = CoOccurrenceFlag.NORMAL.value

            result = await self.neo4j.execute_write(
                self.queries.CREATE_CO_OCCURS,
                {
                    "wallet_a": wallet_a,
                    "wallet_b": wallet_b,
                    "token_address": event.token_address,
                    "entry_delta": entry_delta,
                    "timestamp": event.launch_timestamp.isoformat(),
                    "flag": flag,
                    "strength": strength,
                    "max_tokens": MAX_SHARED_TOKENS_STORED,
                    "high_threshold": HIGH_CO_OCCURRENCE_THRESHOLD,
                    "very_high_threshold": VERY_HIGH_CO_OCCURRENCE_THRESHOLD,
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

    async def _calculate_strength(
        self,
        wallet_a: str,
        wallet_b: str,
    ) -> float:
        """
        Calculate relationship strength based on multiple factors.

        Strength = count_factor * 0.5 + recency_factor * 0.3 + consistency_factor * 0.2
        """
        result = await self.neo4j.execute_read(
            self.queries.GET_CO_OCCURRENCE,
            {"wallet_a": wallet_a, "wallet_b": wallet_b}
        )

        if not result:
            return 0.1  # New relationship, minimal strength

        record = result[0]
        count = record.get("count", 1)
        last_co = record.get("last_co_occurrence")
        avg_delta = record.get("avg_entry_delta", 0)

        # Count factor (normalized, cap at 20)
        count_factor = min(count / 20, 1.0)

        # Recency factor (decay over 30 days)
        recency_factor = 1.0
        if last_co:
            days_ago = (datetime.utcnow() - last_co).days
            recency_factor = max(0, 1 - (days_ago / 30))

        # Consistency factor (lower avg delta = more consistent = stronger)
        # Normalize: 0 seconds = 1.0, 600 seconds = 0
        consistency_factor = max(0, 1 - (avg_delta / EARLY_ENTRY_WINDOW_SECONDS))

        strength = (
            STRENGTH_COUNT_WEIGHT * count_factor +
            STRENGTH_RECENCY_WEIGHT * recency_factor +
            STRENGTH_CONSISTENCY_WEIGHT * consistency_factor
        )

        return min(strength, 1.0)

    async def _count_high_co_occurrence_pairs(self) -> int:
        """Count pairs with high co-occurrence flag."""
        result = await self.neo4j.execute_read(
            """
            MATCH ()-[r:CO_OCCURS]->()
            WHERE r.flag IN ['high_co_occurrence', 'very_high_co_occurrence']
            RETURN count(r) AS count
            """,
            {}
        )
        return result[0]["count"] if result else 0

    async def get_associates(
        self,
        wallet_address: str,
        min_count: int = 1,
        limit: int = 50,
    ) -> list[WalletAssociate]:
        """Get all associates for a wallet based on co-occurrence."""
        result = await self.neo4j.execute_read(
            self.queries.GET_ASSOCIATES,
            {
                "wallet_address": wallet_address,
                "min_count": min_count,
                "limit": limit,
            }
        )

        associates = []
        for record in result:
            associate = WalletAssociate(
                wallet_address=record["wallet_address"],
                co_occurrence_count=record["co_occurrence_count"],
                shared_tokens=record.get("shared_tokens", []),
                flag=CoOccurrenceFlag(record.get("flag", "normal")),
                strength=record.get("strength", 0.0),
                last_co_occurrence=record["last_co_occurrence"],
            )
            associates.append(associate)

        return associates

    async def get_high_co_occurrence_pairs(
        self,
        limit: int = 100,
    ) -> list[CoOccursEdge]:
        """Get all high co-occurrence pairs."""
        result = await self.neo4j.execute_read(
            self.queries.GET_HIGH_CO_OCCURRENCE_PAIRS,
            {"limit": limit}
        )

        pairs = []
        for record in result:
            edge = CoOccursEdge(
                wallet_a=record["wallet_a"],
                wallet_b=record["wallet_b"],
                co_occurrence_count=record["count"],
                shared_tokens=record.get("tokens", []),
                flag=CoOccurrenceFlag(record.get("flag", "normal")),
                strength=record.get("strength", 0.0),
                first_co_occurrence=record.get("last_co_occurrence", datetime.utcnow()),
                last_co_occurrence=record["last_co_occurrence"],
            )
            pairs.append(edge)

        return pairs

    async def get_co_occurrence(
        self,
        wallet_a: str,
        wallet_b: str,
    ) -> Optional[CoOccursEdge]:
        """Get co-occurrence data between two wallets."""
        result = await self.neo4j.execute_read(
            self.queries.GET_CO_OCCURRENCE,
            {"wallet_a": wallet_a, "wallet_b": wallet_b}
        )

        if not result:
            return None

        record = result[0]
        return CoOccursEdge(
            wallet_a=wallet_a,
            wallet_b=wallet_b,
            co_occurrence_count=record["count"],
            shared_tokens=record.get("tokens", []),
            flag=CoOccurrenceFlag(record.get("flag", "normal")),
            avg_entry_delta_seconds=record.get("avg_entry_delta", 0.0),
            first_co_occurrence=record["first_co_occurrence"],
            last_co_occurrence=record["last_co_occurrence"],
            strength=record.get("strength", 0.0),
        )
```

### 5. Scheduled Task

```python
# src/walltrack/tasks/cooccurrence_analysis.py
"""Scheduled task for co-occurrence analysis."""
import structlog
from datetime import datetime

from walltrack.core.services.cooccurrence_analyzer import CoOccurrenceAnalyzer
from walltrack.core.constants.cooccurrence import DEFAULT_ANALYSIS_WINDOW_DAYS

logger = structlog.get_logger(__name__)


async def run_co_occurrence_analysis(
    analyzer: CoOccurrenceAnalyzer,
    days_back: int = DEFAULT_ANALYSIS_WINDOW_DAYS,
) -> None:
    """
    Run co-occurrence analysis.

    Called by scheduler (e.g., daily at midnight).
    """
    logger.info("starting_scheduled_co_occurrence_analysis", days_back=days_back)

    try:
        result = await analyzer.analyze_co_occurrences(days_back=days_back)

        logger.info(
            "scheduled_co_occurrence_analysis_complete",
            tokens=result.tokens_analyzed,
            pairs=result.co_occurrence_pairs,
            high_pairs=result.high_co_occurrence_pairs,
        )

        # Alert on high co-occurrence pairs
        if result.high_co_occurrence_pairs > 0:
            logger.warning(
                "high_co_occurrence_pairs_detected",
                count=result.high_co_occurrence_pairs,
            )

    except Exception as e:
        logger.error("co_occurrence_analysis_failed", error=str(e))
        raise
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/cooccurrence.py
"""Co-occurrence analysis API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from walltrack.core.models.cooccurrence import (
    CoOccurrenceAnalysisResult, CoOccursEdge, WalletAssociate
)
from walltrack.core.services.cooccurrence_analyzer import CoOccurrenceAnalyzer
from walltrack.core.constants.cooccurrence import DEFAULT_ANALYSIS_WINDOW_DAYS
from walltrack.api.dependencies import get_cooccurrence_analyzer

router = APIRouter(prefix="/cooccurrence", tags=["cooccurrence"])


@router.post("/analyze", response_model=CoOccurrenceAnalysisResult)
async def analyze_co_occurrences(
    days_back: int = Query(default=DEFAULT_ANALYSIS_WINDOW_DAYS, ge=1, le=90),
    wallet_addresses: Optional[list[str]] = None,
    analyzer: CoOccurrenceAnalyzer = Depends(get_cooccurrence_analyzer),
) -> CoOccurrenceAnalysisResult:
    """
    Run co-occurrence analysis on recent token launches.
    """
    try:
        return await analyzer.analyze_co_occurrences(days_back, wallet_addresses)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{wallet_address}/associates", response_model=list[WalletAssociate])
async def get_associates(
    wallet_address: str,
    min_count: int = Query(default=1, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    analyzer: CoOccurrenceAnalyzer = Depends(get_cooccurrence_analyzer),
) -> list[WalletAssociate]:
    """
    Get wallets that frequently co-occur with the given wallet on early entries.
    """
    try:
        return await analyzer.get_associates(wallet_address, min_count, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/relationship", response_model=Optional[CoOccursEdge])
async def get_co_occurrence(
    wallet_a: str = Query(...),
    wallet_b: str = Query(...),
    analyzer: CoOccurrenceAnalyzer = Depends(get_cooccurrence_analyzer),
) -> Optional[CoOccursEdge]:
    """
    Get co-occurrence relationship between two wallets.
    """
    try:
        return await analyzer.get_co_occurrence(wallet_a, wallet_b)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/high-co-occurrence", response_model=list[CoOccursEdge])
async def get_high_co_occurrence_pairs(
    limit: int = Query(default=100, ge=1, le=500),
    analyzer: CoOccurrenceAnalyzer = Depends(get_cooccurrence_analyzer),
) -> list[CoOccursEdge]:
    """
    Get all wallet pairs with high co-occurrence (potential insider groups).
    """
    try:
        return await analyzer.get_high_co_occurrence_pairs(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 7. Unit Tests

```python
# tests/unit/core/services/test_cooccurrence_analyzer.py
"""Tests for CoOccurrenceAnalyzer service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.services.cooccurrence_analyzer import CoOccurrenceAnalyzer
from walltrack.core.models.cooccurrence import (
    CoOccurrenceFlag, CoOccursEdge, WalletAssociate
)


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
    repo.get_trades_for_token = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_token_repo():
    """Mock token repository."""
    repo = AsyncMock()
    repo.get_tokens_launched_since = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def analyzer(mock_neo4j, mock_trade_repo, mock_token_repo):
    """Create CoOccurrenceAnalyzer with mocks."""
    return CoOccurrenceAnalyzer(mock_neo4j, mock_trade_repo, mock_token_repo)


class TestGetEarlyEntries:
    """Tests for _get_early_entries."""

    @pytest.mark.asyncio
    async def test_filters_entries_within_window(self, analyzer, mock_trade_repo):
        """Should only return entries within 10 minutes of launch."""
        launch_time = datetime.utcnow() - timedelta(hours=1)

        # Mock trades at different times
        early_trade = MagicMock()
        early_trade.wallet_address = "wallet1"
        early_trade.executed_at = launch_time + timedelta(minutes=5)
        early_trade.amount_sol = 1.0
        early_trade.tx_signature = "sig1"

        late_trade = MagicMock()
        late_trade.wallet_address = "wallet2"
        late_trade.executed_at = launch_time + timedelta(minutes=15)
        late_trade.amount_sol = 2.0
        late_trade.tx_signature = "sig2"

        mock_trade_repo.get_trades_for_token.return_value = [early_trade, late_trade]

        entries = await analyzer._get_early_entries("token123", launch_time)

        assert len(entries) == 1
        assert entries[0].wallet_address == "wallet1"

    @pytest.mark.asyncio
    async def test_deduplicates_by_wallet(self, analyzer, mock_trade_repo):
        """Should only count first entry per wallet."""
        launch_time = datetime.utcnow() - timedelta(hours=1)

        trade1 = MagicMock()
        trade1.wallet_address = "wallet1"
        trade1.executed_at = launch_time + timedelta(minutes=2)
        trade1.amount_sol = 1.0
        trade1.tx_signature = "sig1"

        trade2 = MagicMock()
        trade2.wallet_address = "wallet1"
        trade2.executed_at = launch_time + timedelta(minutes=5)
        trade2.amount_sol = 2.0
        trade2.tx_signature = "sig2"

        mock_trade_repo.get_trades_for_token.return_value = [trade1, trade2]

        entries = await analyzer._get_early_entries("token123", launch_time)

        assert len(entries) == 1


class TestAnalyzeCoOccurrences:
    """Tests for analyze_co_occurrences."""

    @pytest.mark.asyncio
    async def test_creates_edges_for_co_occurring_wallets(
        self, analyzer, mock_token_repo, mock_trade_repo, mock_neo4j
    ):
        """Should create CO_OCCURS edges for wallets entering same token early."""
        launch_time = datetime.utcnow() - timedelta(hours=1)

        # Mock token
        mock_token = MagicMock()
        mock_token.address = "token123"
        mock_token.symbol = "TEST"
        mock_token.launch_timestamp = launch_time
        mock_token_repo.get_tokens_launched_since.return_value = [mock_token]

        # Mock multiple early entries
        trades = []
        for i in range(3):
            trade = MagicMock()
            trade.wallet_address = f"wallet{i}"
            trade.executed_at = launch_time + timedelta(minutes=i)
            trade.amount_sol = 1.0
            trade.tx_signature = f"sig{i}"
            trades.append(trade)

        mock_trade_repo.get_trades_for_token.return_value = trades

        result = await analyzer.analyze_co_occurrences(days_back=7)

        assert result.tokens_analyzed == 1
        assert result.early_entries_found == 3
        # 3 wallets = 3 pairs (C(3,2) = 3)
        assert result.co_occurrence_pairs == 3
        assert mock_neo4j.execute_write.called


class TestGetAssociates:
    """Tests for get_associates."""

    @pytest.mark.asyncio
    async def test_returns_associates(self, analyzer, mock_neo4j):
        """Should return wallet associates."""
        mock_neo4j.execute_read.return_value = [
            {
                "wallet_address": "associate1",
                "co_occurrence_count": 5,
                "shared_tokens": ["token1", "token2"],
                "flag": "high_co_occurrence",
                "strength": 0.8,
                "last_co_occurrence": datetime.utcnow(),
            }
        ]

        associates = await analyzer.get_associates("wallet123")

        assert len(associates) == 1
        assert associates[0].wallet_address == "associate1"
        assert associates[0].co_occurrence_count == 5
        assert associates[0].flag == CoOccurrenceFlag.HIGH_CO_OCCURRENCE


class TestGetHighCoOccurrencePairs:
    """Tests for get_high_co_occurrence_pairs."""

    @pytest.mark.asyncio
    async def test_returns_high_pairs(self, analyzer, mock_neo4j):
        """Should return pairs with high co-occurrence flag."""
        mock_neo4j.execute_read.return_value = [
            {
                "wallet_a": "wallet1",
                "wallet_b": "wallet2",
                "count": 10,
                "tokens": ["token1", "token2"],
                "flag": "very_high_co_occurrence",
                "strength": 0.9,
                "last_co_occurrence": datetime.utcnow(),
            }
        ]

        pairs = await analyzer.get_high_co_occurrence_pairs()

        assert len(pairs) == 1
        assert pairs[0].co_occurrence_count == 10
        assert pairs[0].flag == CoOccurrenceFlag.VERY_HIGH_CO_OCCURRENCE


class TestCalculateStrength:
    """Tests for _calculate_strength."""

    @pytest.mark.asyncio
    async def test_returns_minimal_for_new_relationship(self, analyzer, mock_neo4j):
        """Should return minimal strength for new relationships."""
        mock_neo4j.execute_read.return_value = []

        strength = await analyzer._calculate_strength("wallet1", "wallet2")

        assert strength == 0.1

    @pytest.mark.asyncio
    async def test_increases_with_count(self, analyzer, mock_neo4j):
        """Should increase strength with higher co-occurrence count."""
        mock_neo4j.execute_read.return_value = [
            {
                "count": 15,
                "last_co_occurrence": datetime.utcnow(),
                "avg_entry_delta": 60,
            }
        ]

        strength = await analyzer._calculate_strength("wallet1", "wallet2")

        assert strength > 0.5
```

---

## Implementation Tasks

- [ ] Create co-occurrence analysis module
- [ ] Implement early entry detection (first 10 minutes)
- [ ] Calculate co-occurrence counts per wallet pair
- [ ] Create CO_OCCURS edges in Neo4j
- [ ] Add threshold-based flagging
- [ ] Store shared tokens list on edges
- [ ] Schedule periodic batch job

## Definition of Done

- [ ] Co-occurrence analysis identifies wallet pairs
- [ ] CO_OCCURS edges created with counts and token lists
- [ ] High co-occurrence relationships flagged
- [ ] Associates queryable by wallet
