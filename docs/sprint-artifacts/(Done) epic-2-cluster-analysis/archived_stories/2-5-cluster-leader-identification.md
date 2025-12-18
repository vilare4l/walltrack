# Story 2.5: Cluster Leader Identification

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: done
- **Priority**: Medium
- **FR**: FR11

## User Story

**As an** operator,
**I want** to identify which wallets lead movements within a cluster,
**So that** I can prioritize signals from leaders over followers.

## Acceptance Criteria

### AC 1: Leader Analysis
**Given** a cluster with multiple wallets
**When** leader analysis runs
**Then** wallets that consistently act first are identified
**And** "leader_score" is calculated per wallet (based on timing precedence)
**And** top N leaders per cluster are flagged

### AC 2: Leader Score Calculation
**Given** wallet A consistently buys 1-5 minutes before other cluster members
**When** leader score is calculated
**Then** wallet A receives high leader_score
**And** wallet A is marked as cluster leader

### AC 3: Cluster Query with Leaders
**Given** a cluster has identified leaders
**When** cluster is queried
**Then** leader wallets are returned with their leader_score
**And** leader status is visible in dashboard

### AC 4: Signal Processing Integration
**Given** signal comes from a cluster leader
**When** signal is processed (in Epic 3)
**Then** leader status is available for scoring amplification

## Technical Notes

- FR11: Identify cluster leaders
- Store leader_score on Wallet node or MEMBER_OF edge
- Calculate based on temporal analysis of coordinated buys

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/leader.py
"""Leader identification models."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class LeaderScore(BaseModel):
    """Leader score for a wallet within a cluster."""

    wallet_address: str
    cluster_id: str
    leader_score: float = Field(default=0.0, ge=0, le=1)
    timing_precedence: float = Field(default=0.0, description="How often first to act")
    follower_count: int = Field(default=0, description="Wallets that follow this one")
    avg_lead_time_seconds: float = Field(default=0.0, description="Avg seconds ahead of followers")
    trade_count: int = Field(default=0, description="Trades analyzed for scoring")
    is_leader: bool = Field(default=False)
    calculated_at: datetime = Field(default_factory=datetime.utcnow)


class TimingEvent(BaseModel):
    """A single timing event in cluster trading."""

    token_address: str
    first_wallet: str
    first_timestamp: datetime
    followers: list[str] = Field(default_factory=list)
    follow_times: dict[str, float] = Field(default_factory=dict, description="wallet -> seconds after leader")


class LeaderAnalysisResult(BaseModel):
    """Result of leader analysis for a cluster."""

    cluster_id: str
    wallets_analyzed: int = Field(default=0)
    trades_analyzed: int = Field(default=0)
    leaders_identified: int = Field(default=0)
    top_leader_address: Optional[str] = None
    top_leader_score: float = Field(default=0.0)
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)


class ClusterLeaders(BaseModel):
    """Leaders for a cluster."""

    cluster_id: str
    leaders: list[LeaderScore] = Field(default_factory=list)
    primary_leader: Optional[str] = None
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/leader.py
"""Leader identification constants."""

# Minimum trades to calculate leader score
MIN_TRADES_FOR_LEADER_SCORE = 5

# Maximum leaders per cluster
MAX_LEADERS_PER_CLUSTER = 3

# Leader score threshold (above this = leader)
LEADER_SCORE_THRESHOLD = 0.6

# Time window for considering "first mover" (seconds)
FIRST_MOVER_WINDOW_SECONDS = 300  # 5 minutes

# Minimum lead time to count as leading (seconds)
MIN_LEAD_TIME_SECONDS = 30

# Leader score component weights
SCORE_WEIGHT_TIMING_PRECEDENCE = 0.4
SCORE_WEIGHT_FOLLOWER_COUNT = 0.3
SCORE_WEIGHT_CONSISTENCY = 0.3

# Analysis lookback window (days)
LEADER_ANALYSIS_WINDOW_DAYS = 30
```

### 3. Neo4j Queries

```python
# src/walltrack/data/neo4j/queries/leader.py
"""Neo4j queries for leader identification."""


class LeaderQueries:
    """Cypher queries for leader analysis."""

    # Update leader score on MEMBER_OF edge
    UPDATE_LEADER_SCORE = """
    MATCH (w:Wallet {address: $wallet_address})-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    SET r.leader_score = $leader_score,
        r.timing_precedence = $timing_precedence,
        r.follower_count = $follower_count,
        r.avg_lead_time = $avg_lead_time,
        r.is_leader = $is_leader,
        r.score_updated_at = datetime()
    RETURN r
    """

    # Get cluster leaders
    GET_CLUSTER_LEADERS = """
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    WHERE r.is_leader = true
    RETURN w.address AS wallet_address,
           r.leader_score AS leader_score,
           r.timing_precedence AS timing_precedence,
           r.follower_count AS follower_count,
           r.avg_lead_time AS avg_lead_time
    ORDER BY r.leader_score DESC
    LIMIT $limit
    """

    # Get all member scores for a cluster
    GET_CLUSTER_MEMBER_SCORES = """
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    RETURN w.address AS wallet_address,
           r.leader_score AS leader_score,
           r.is_leader AS is_leader,
           r.timing_precedence AS timing_precedence
    ORDER BY r.leader_score DESC
    """

    # Set primary cluster leader
    SET_CLUSTER_LEADER = """
    MATCH (c:Cluster {id: $cluster_id})
    SET c.leader_address = $leader_address,
        c.leader_score = $leader_score,
        c.updated_at = datetime()
    RETURN c
    """

    # Check if wallet is leader in any cluster
    IS_WALLET_LEADER = """
    MATCH (w:Wallet {address: $wallet_address})-[r:MEMBER_OF]->(c:Cluster {status: 'active'})
    WHERE r.is_leader = true
    RETURN c.id AS cluster_id,
           r.leader_score AS leader_score,
           c.size AS cluster_size
    """

    # Get timing data for cluster trades
    GET_CLUSTER_TRADE_TIMING = """
    MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    WITH collect(w.address) AS members
    MATCH (m:Wallet)-[:EXECUTED]->(t:Trade)
    WHERE m.address IN members
      AND t.type = 'buy'
      AND t.executed_at >= datetime($since)
    WITH t.token_address AS token,
         collect({wallet: m.address, time: t.executed_at}) AS trades
    WHERE size(trades) >= 2
    RETURN token,
           trades
    ORDER BY size(trades) DESC
    """

    # Reset all leader flags in cluster
    RESET_CLUSTER_LEADERS = """
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    SET r.is_leader = false
    RETURN count(r) AS reset_count
    """
```

### 4. LeaderIdentifier Service

```python
# src/walltrack/core/services/leader_identifier.py
"""Service for identifying cluster leaders."""
import structlog
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from walltrack.core.models.leader import (
    LeaderScore, TimingEvent, LeaderAnalysisResult, ClusterLeaders
)
from walltrack.core.constants.leader import (
    MIN_TRADES_FOR_LEADER_SCORE, MAX_LEADERS_PER_CLUSTER,
    LEADER_SCORE_THRESHOLD, FIRST_MOVER_WINDOW_SECONDS,
    MIN_LEAD_TIME_SECONDS, LEADER_ANALYSIS_WINDOW_DAYS,
    SCORE_WEIGHT_TIMING_PRECEDENCE, SCORE_WEIGHT_FOLLOWER_COUNT,
    SCORE_WEIGHT_CONSISTENCY
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.leader import LeaderQueries
from walltrack.data.supabase.repositories.trade import TradeRepository

logger = structlog.get_logger(__name__)


class LeaderIdentifier:
    """Identifies leaders within wallet clusters."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        trade_repo: TradeRepository,
    ):
        self.neo4j = neo4j_client
        self.trade_repo = trade_repo
        self.queries = LeaderQueries()

    async def analyze_cluster_leaders(
        self,
        cluster_id: str,
        days_back: int = LEADER_ANALYSIS_WINDOW_DAYS,
    ) -> LeaderAnalysisResult:
        """
        Analyze cluster to identify leaders based on timing patterns.

        Args:
            cluster_id: Cluster to analyze
            days_back: Days of trade history to analyze

        Returns:
            LeaderAnalysisResult with analysis statistics
        """
        logger.info("analyzing_cluster_leaders", cluster_id=cluster_id, days_back=days_back)

        since = datetime.utcnow() - timedelta(days=days_back)

        # Get cluster members
        members = await self._get_cluster_members(cluster_id)
        if len(members) < 2:
            return LeaderAnalysisResult(cluster_id=cluster_id, wallets_analyzed=len(members))

        # Get trade timing data
        timing_events = await self._get_timing_events(cluster_id, members, since)

        if not timing_events:
            return LeaderAnalysisResult(cluster_id=cluster_id, wallets_analyzed=len(members))

        # Calculate leader scores
        scores = self._calculate_leader_scores(members, timing_events)

        # Reset existing leader flags
        await self.neo4j.execute_write(
            self.queries.RESET_CLUSTER_LEADERS,
            {"cluster_id": cluster_id}
        )

        # Update scores and identify leaders
        leaders_identified = 0
        top_leader = None
        top_score = 0.0

        for wallet, score_data in scores.items():
            is_leader = (
                score_data["score"] >= LEADER_SCORE_THRESHOLD and
                leaders_identified < MAX_LEADERS_PER_CLUSTER
            )

            if is_leader:
                leaders_identified += 1

            if score_data["score"] > top_score:
                top_score = score_data["score"]
                top_leader = wallet

            await self.neo4j.execute_write(
                self.queries.UPDATE_LEADER_SCORE,
                {
                    "wallet_address": wallet,
                    "cluster_id": cluster_id,
                    "leader_score": score_data["score"],
                    "timing_precedence": score_data["timing_precedence"],
                    "follower_count": score_data["follower_count"],
                    "avg_lead_time": score_data["avg_lead_time"],
                    "is_leader": is_leader,
                }
            )

        # Set primary cluster leader
        if top_leader:
            await self.neo4j.execute_write(
                self.queries.SET_CLUSTER_LEADER,
                {
                    "cluster_id": cluster_id,
                    "leader_address": top_leader,
                    "leader_score": top_score,
                }
            )

        result = LeaderAnalysisResult(
            cluster_id=cluster_id,
            wallets_analyzed=len(members),
            trades_analyzed=len(timing_events),
            leaders_identified=leaders_identified,
            top_leader_address=top_leader,
            top_leader_score=top_score,
        )

        logger.info(
            "cluster_leader_analysis_complete",
            cluster_id=cluster_id,
            leaders=leaders_identified,
            top_leader=top_leader,
        )

        return result

    async def _get_cluster_members(self, cluster_id: str) -> list[str]:
        """Get all wallet addresses in a cluster."""
        query = """
        MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
        RETURN w.address AS address
        """
        result = await self.neo4j.execute_read(query, {"cluster_id": cluster_id})
        return [r["address"] for r in result]

    async def _get_timing_events(
        self,
        cluster_id: str,
        members: list[str],
        since: datetime,
    ) -> list[TimingEvent]:
        """Get trade timing events for cluster members."""
        # Get trades from repository
        trades = await self.trade_repo.get_trades_for_wallets(
            wallet_addresses=members,
            since=since,
            trade_type="buy",
        )

        # Group by token
        trades_by_token = defaultdict(list)
        for trade in trades:
            trades_by_token[trade.token_address].append({
                "wallet": trade.wallet_address,
                "timestamp": trade.executed_at,
            })

        events = []
        for token, token_trades in trades_by_token.items():
            if len(token_trades) < 2:
                continue

            # Sort by time
            sorted_trades = sorted(token_trades, key=lambda x: x["timestamp"])

            first_trade = sorted_trades[0]
            first_wallet = first_trade["wallet"]
            first_time = first_trade["timestamp"]

            # Find followers within window
            followers = []
            follow_times = {}

            for trade in sorted_trades[1:]:
                delta = (trade["timestamp"] - first_time).total_seconds()
                if delta <= FIRST_MOVER_WINDOW_SECONDS and delta >= MIN_LEAD_TIME_SECONDS:
                    if trade["wallet"] != first_wallet:
                        followers.append(trade["wallet"])
                        follow_times[trade["wallet"]] = delta

            if followers:
                event = TimingEvent(
                    token_address=token,
                    first_wallet=first_wallet,
                    first_timestamp=first_time,
                    followers=followers,
                    follow_times=follow_times,
                )
                events.append(event)

        return events

    def _calculate_leader_scores(
        self,
        members: list[str],
        timing_events: list[TimingEvent],
    ) -> dict[str, dict]:
        """Calculate leader scores based on timing events."""
        # Initialize score data
        score_data = {
            wallet: {
                "first_count": 0,
                "total_events": 0,
                "follower_counts": [],
                "lead_times": [],
            }
            for wallet in members
        }

        # Count first-mover instances and followers
        for event in timing_events:
            first_wallet = event.first_wallet
            if first_wallet in score_data:
                score_data[first_wallet]["first_count"] += 1
                score_data[first_wallet]["follower_counts"].append(len(event.followers))
                if event.follow_times:
                    avg_follow_time = sum(event.follow_times.values()) / len(event.follow_times)
                    score_data[first_wallet]["lead_times"].append(avg_follow_time)

            # Mark participation
            for wallet in [event.first_wallet] + event.followers:
                if wallet in score_data:
                    score_data[wallet]["total_events"] += 1

        # Calculate final scores
        results = {}
        total_events = len(timing_events)

        for wallet, data in score_data.items():
            if data["total_events"] < MIN_TRADES_FOR_LEADER_SCORE:
                results[wallet] = {
                    "score": 0.0,
                    "timing_precedence": 0.0,
                    "follower_count": 0,
                    "avg_lead_time": 0.0,
                }
                continue

            # Timing precedence: how often they're first
            timing_precedence = data["first_count"] / max(data["total_events"], 1)

            # Follower count: average followers when leading
            avg_followers = (
                sum(data["follower_counts"]) / len(data["follower_counts"])
                if data["follower_counts"] else 0
            )
            # Normalize to 0-1 (cap at 5 followers = 1.0)
            follower_score = min(avg_followers / 5, 1.0)

            # Consistency: lead times should be similar (low variance = high consistency)
            avg_lead_time = (
                sum(data["lead_times"]) / len(data["lead_times"])
                if data["lead_times"] else 0
            )

            # Consistency score: presence across events
            consistency = data["total_events"] / max(total_events, 1)

            # Final score
            score = (
                SCORE_WEIGHT_TIMING_PRECEDENCE * timing_precedence +
                SCORE_WEIGHT_FOLLOWER_COUNT * follower_score +
                SCORE_WEIGHT_CONSISTENCY * consistency
            )

            results[wallet] = {
                "score": min(score, 1.0),
                "timing_precedence": timing_precedence,
                "follower_count": int(avg_followers),
                "avg_lead_time": avg_lead_time,
            }

        return results

    async def get_cluster_leaders(
        self,
        cluster_id: str,
        limit: int = MAX_LEADERS_PER_CLUSTER,
    ) -> list[LeaderScore]:
        """Get identified leaders for a cluster."""
        result = await self.neo4j.execute_read(
            self.queries.GET_CLUSTER_LEADERS,
            {"cluster_id": cluster_id, "limit": limit}
        )

        return [
            LeaderScore(
                wallet_address=r["wallet_address"],
                cluster_id=cluster_id,
                leader_score=r["leader_score"],
                timing_precedence=r.get("timing_precedence", 0.0),
                follower_count=r.get("follower_count", 0),
                avg_lead_time_seconds=r.get("avg_lead_time", 0.0),
                is_leader=True,
            )
            for r in result
        ]

    async def is_wallet_leader(
        self,
        wallet_address: str,
    ) -> Optional[LeaderScore]:
        """Check if a wallet is a leader in any cluster."""
        result = await self.neo4j.execute_read(
            self.queries.IS_WALLET_LEADER,
            {"wallet_address": wallet_address}
        )

        if not result:
            return None

        r = result[0]
        return LeaderScore(
            wallet_address=wallet_address,
            cluster_id=r["cluster_id"],
            leader_score=r["leader_score"],
            is_leader=True,
        )
```

### 5. API Endpoints

```python
# src/walltrack/api/routes/leaders.py
"""Leader identification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from walltrack.core.models.leader import (
    LeaderScore, LeaderAnalysisResult
)
from walltrack.core.services.leader_identifier import LeaderIdentifier
from walltrack.core.constants.leader import LEADER_ANALYSIS_WINDOW_DAYS
from walltrack.api.dependencies import get_leader_identifier

router = APIRouter(prefix="/leaders", tags=["leaders"])


@router.post("/cluster/{cluster_id}/analyze", response_model=LeaderAnalysisResult)
async def analyze_cluster_leaders(
    cluster_id: str,
    days_back: int = Query(default=LEADER_ANALYSIS_WINDOW_DAYS, ge=1, le=90),
    identifier: LeaderIdentifier = Depends(get_leader_identifier),
) -> LeaderAnalysisResult:
    """
    Analyze cluster to identify leaders based on timing patterns.
    """
    try:
        return await identifier.analyze_cluster_leaders(cluster_id, days_back)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/{cluster_id}", response_model=list[LeaderScore])
async def get_cluster_leaders(
    cluster_id: str,
    limit: int = Query(default=3, ge=1, le=10),
    identifier: LeaderIdentifier = Depends(get_leader_identifier),
) -> list[LeaderScore]:
    """
    Get identified leaders for a cluster.
    """
    try:
        return await identifier.get_cluster_leaders(cluster_id, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet/{wallet_address}", response_model=Optional[LeaderScore])
async def is_wallet_leader(
    wallet_address: str,
    identifier: LeaderIdentifier = Depends(get_leader_identifier),
) -> Optional[LeaderScore]:
    """
    Check if a wallet is a leader in any cluster.
    """
    try:
        return await identifier.is_wallet_leader(wallet_address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 6. Unit Tests

```python
# tests/unit/core/services/test_leader_identifier.py
"""Tests for LeaderIdentifier service."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.services.leader_identifier import LeaderIdentifier
from walltrack.core.models.leader import TimingEvent, LeaderScore


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    client.execute_write = AsyncMock(return_value=[{}])
    return client


@pytest.fixture
def mock_trade_repo():
    """Mock trade repository."""
    repo = AsyncMock()
    repo.get_trades_for_wallets = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def identifier(mock_neo4j, mock_trade_repo):
    """Create LeaderIdentifier with mocks."""
    return LeaderIdentifier(mock_neo4j, mock_trade_repo)


class TestCalculateLeaderScores:
    """Tests for _calculate_leader_scores."""

    def test_identifies_consistent_first_mover(self, identifier):
        """Should give high score to wallet that moves first consistently."""
        members = ["leader", "follower1", "follower2"]

        events = [
            TimingEvent(
                token_address="token1",
                first_wallet="leader",
                first_timestamp=datetime.utcnow() - timedelta(hours=1),
                followers=["follower1", "follower2"],
                follow_times={"follower1": 60, "follower2": 120},
            ),
            TimingEvent(
                token_address="token2",
                first_wallet="leader",
                first_timestamp=datetime.utcnow() - timedelta(hours=2),
                followers=["follower1"],
                follow_times={"follower1": 90},
            ),
        ]

        scores = identifier._calculate_leader_scores(members, events)

        assert scores["leader"]["score"] > scores["follower1"]["score"]
        assert scores["leader"]["timing_precedence"] > 0.5

    def test_requires_minimum_trades(self, identifier):
        """Should return zero score for wallets with few trades."""
        members = ["wallet1"]
        events = [
            TimingEvent(
                token_address="token1",
                first_wallet="wallet1",
                first_timestamp=datetime.utcnow(),
                followers=[],
                follow_times={},
            ),
        ]

        scores = identifier._calculate_leader_scores(members, events)

        assert scores["wallet1"]["score"] == 0.0


class TestAnalyzeClusterLeaders:
    """Tests for analyze_cluster_leaders."""

    @pytest.mark.asyncio
    async def test_identifies_leaders(self, identifier, mock_neo4j, mock_trade_repo):
        """Should identify and flag cluster leaders."""
        # Mock cluster members
        mock_neo4j.execute_read.side_effect = [
            [{"address": "w1"}, {"address": "w2"}, {"address": "w3"}],  # members
        ]

        # Mock trades
        now = datetime.utcnow()
        trades = []
        for i, wallet in enumerate(["w1", "w2", "w3"]):
            trade = MagicMock()
            trade.wallet_address = wallet
            trade.token_address = "token1"
            trade.executed_at = now + timedelta(minutes=i)  # w1 always first
            trades.append(trade)

        mock_trade_repo.get_trades_for_wallets.return_value = trades * 5  # Multiple events

        result = await identifier.analyze_cluster_leaders("cluster123")

        assert result.cluster_id == "cluster123"
        assert result.wallets_analyzed == 3


class TestGetClusterLeaders:
    """Tests for get_cluster_leaders."""

    @pytest.mark.asyncio
    async def test_returns_leaders(self, identifier, mock_neo4j):
        """Should return identified leaders."""
        mock_neo4j.execute_read.return_value = [
            {
                "wallet_address": "leader1",
                "leader_score": 0.8,
                "timing_precedence": 0.7,
                "follower_count": 3,
                "avg_lead_time": 90.0,
            }
        ]

        leaders = await identifier.get_cluster_leaders("cluster123")

        assert len(leaders) == 1
        assert leaders[0].wallet_address == "leader1"
        assert leaders[0].leader_score == 0.8
        assert leaders[0].is_leader is True
```

---

## Implementation Tasks

- [x] Create leader analysis module
- [x] Implement timing precedence calculation
- [x] Calculate leader_score per wallet
- [x] Flag top N leaders per cluster
- [x] Store leader_score on Wallet node
- [x] Expose leader status for signal scoring

## Definition of Done

- [x] Leaders identified per cluster
- [x] Leader scores calculated accurately
- [x] Leader status queryable
- [x] Leader info available for scoring
