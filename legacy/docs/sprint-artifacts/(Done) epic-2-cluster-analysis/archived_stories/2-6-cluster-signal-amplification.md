# Story 2.6: Cluster Signal Amplification Logic

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: done
- **Priority**: Medium
- **FR**: FR12

## User Story

**As an** operator,
**I want** signals to be amplified when multiple cluster members move together,
**So that** coordinated insider activity gets higher priority.

## Acceptance Criteria

### AC 1: Cluster Activity Check
**Given** a signal from wallet A in cluster X
**When** signal processing checks cluster activity
**Then** recent signals from other cluster X members are queried
**And** if 2+ cluster members signaled same token in last 10 minutes, amplification applies

### AC 2: Amplification Factor
**Given** cluster amplification condition is met
**When** signal score is calculated
**Then** cluster_amplification_factor is added to scoring context
**And** factor is proportional to: number of cluster members, leader involvement

### AC 3: No Amplification
**Given** no other cluster members moved
**When** signal is processed
**Then** no amplification is applied
**And** signal proceeds with base scoring

### AC 4: Logging
**Given** amplification is applied
**When** signal is logged
**Then** amplification details are recorded (which members, timing)
**And** cluster contribution to final score is trackable

## Technical Notes

- FR12: Amplify signal score when multiple cluster wallets move together
- Implement in `src/walltrack/core/scoring/` (used by Epic 3)
- Store amplification rules in config (configurable thresholds)

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/amplification.py
"""Cluster signal amplification models."""
from datetime import datetime
from pydantic import BaseModel, Field
from typing import Optional


class ClusterActivity(BaseModel):
    """Activity from cluster members on a token."""

    cluster_id: str
    token_address: str
    active_members: list[str] = Field(default_factory=list)
    total_cluster_size: int = Field(default=0)
    participation_rate: float = Field(default=0.0)
    leader_participated: bool = Field(default=False)
    leader_address: Optional[str] = None
    first_signal_time: datetime
    last_signal_time: datetime
    window_seconds: int


class AmplificationFactor(BaseModel):
    """Calculated amplification factor for a signal."""

    base_factor: float = Field(default=1.0, ge=1.0)
    participation_bonus: float = Field(default=0.0, ge=0.0)
    leader_bonus: float = Field(default=0.0, ge=0.0)
    cluster_strength_bonus: float = Field(default=0.0, ge=0.0)
    final_factor: float = Field(default=1.0, ge=1.0)

    @property
    def total_bonus(self) -> float:
        return self.participation_bonus + self.leader_bonus + self.cluster_strength_bonus


class AmplificationResult(BaseModel):
    """Result of amplification check for a signal."""

    signal_id: Optional[str] = None
    wallet_address: str
    token_address: str
    cluster_id: Optional[str] = None
    amplification_applied: bool = Field(default=False)
    factor: AmplificationFactor = Field(default_factory=AmplificationFactor)
    cluster_activity: Optional[ClusterActivity] = None
    reason: str = Field(default="no_cluster")
    checked_at: datetime = Field(default_factory=datetime.utcnow)


class AmplificationConfig(BaseModel):
    """Configuration for amplification rules."""

    # Time window for checking cluster activity
    activity_window_seconds: int = Field(default=600)  # 10 minutes

    # Minimum members for amplification
    min_active_members: int = Field(default=2)

    # Base amplification factor when conditions met
    base_amplification: float = Field(default=1.2)

    # Bonus per additional member (capped)
    per_member_bonus: float = Field(default=0.05)
    max_member_bonus: float = Field(default=0.3)

    # Bonus if leader participates
    leader_bonus: float = Field(default=0.15)

    # Bonus based on cluster strength
    cluster_strength_multiplier: float = Field(default=0.2)

    # Maximum total amplification
    max_amplification: float = Field(default=1.8)
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/amplification.py
"""Cluster amplification constants."""

# Time window for cluster activity check (seconds)
AMPLIFICATION_WINDOW_SECONDS = 600  # 10 minutes

# Minimum cluster members acting together for amplification
MIN_ACTIVE_MEMBERS = 2

# Base amplification factor
BASE_AMPLIFICATION_FACTOR = 1.2

# Per-member bonus
PER_MEMBER_BONUS = 0.05
MAX_MEMBER_BONUS = 0.3

# Leader participation bonus
LEADER_PARTICIPATION_BONUS = 0.15

# Cluster strength multiplier
CLUSTER_STRENGTH_MULTIPLIER = 0.2

# Maximum amplification factor
MAX_AMPLIFICATION_FACTOR = 1.8

# Minimum cluster strength for amplification
MIN_CLUSTER_STRENGTH = 0.3
```

### 3. Neo4j Queries

```python
# src/walltrack/data/neo4j/queries/amplification.py
"""Neo4j queries for cluster amplification."""


class AmplificationQueries:
    """Cypher queries for amplification checks."""

    # Get cluster activity for a token within time window
    GET_CLUSTER_ACTIVITY = """
    MATCH (w:Wallet {address: $wallet_address})-[:MEMBER_OF]->(c:Cluster {status: 'active'})
    WITH c
    MATCH (member:Wallet)-[r:MEMBER_OF]->(c)
    WITH c, collect(member.address) AS members, count(member) AS cluster_size,
         c.leader_address AS leader, c.strength AS strength
    MATCH (m:Wallet)-[:EXECUTED]->(t:Trade)
    WHERE m.address IN members
      AND t.token_address = $token_address
      AND t.type = 'buy'
      AND t.executed_at >= datetime($since)
    WITH c, cluster_size, leader, strength,
         collect(DISTINCT m.address) AS active_members,
         min(t.executed_at) AS first_signal,
         max(t.executed_at) AS last_signal
    RETURN c.id AS cluster_id,
           cluster_size,
           active_members,
           size(active_members) AS active_count,
           leader,
           leader IN active_members AS leader_participated,
           strength,
           first_signal,
           last_signal
    """

    # Get recent signals from cluster for token
    GET_CLUSTER_SIGNALS = """
    MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    WITH collect(w.address) AS members
    MATCH (m:Wallet)-[:GENERATED]->(s:Signal)
    WHERE m.address IN members
      AND s.token_address = $token_address
      AND s.created_at >= datetime($since)
    RETURN m.address AS wallet,
           s.id AS signal_id,
           s.created_at AS signal_time,
           s.score AS signal_score
    ORDER BY s.created_at ASC
    """

    # Get wallet's cluster with leader info
    GET_WALLET_CLUSTER_INFO = """
    MATCH (w:Wallet {address: $wallet_address})-[r:MEMBER_OF]->(c:Cluster {status: 'active'})
    RETURN c.id AS cluster_id,
           c.size AS cluster_size,
           c.strength AS cluster_strength,
           c.leader_address AS leader_address,
           r.is_leader AS is_leader
    """
```

### 4. ClusterAmplifier Service

```python
# src/walltrack/core/scoring/cluster_amplifier.py
"""Service for calculating cluster signal amplification."""
import structlog
from datetime import datetime, timedelta
from typing import Optional

from walltrack.core.models.amplification import (
    ClusterActivity, AmplificationFactor, AmplificationResult,
    AmplificationConfig
)
from walltrack.core.constants.amplification import (
    AMPLIFICATION_WINDOW_SECONDS, MIN_ACTIVE_MEMBERS,
    BASE_AMPLIFICATION_FACTOR, PER_MEMBER_BONUS, MAX_MEMBER_BONUS,
    LEADER_PARTICIPATION_BONUS, CLUSTER_STRENGTH_MULTIPLIER,
    MAX_AMPLIFICATION_FACTOR, MIN_CLUSTER_STRENGTH
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.amplification import AmplificationQueries

logger = structlog.get_logger(__name__)


class ClusterAmplifier:
    """Calculates signal amplification based on cluster activity."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        config: Optional[AmplificationConfig] = None,
    ):
        self.neo4j = neo4j_client
        self.queries = AmplificationQueries()
        self.config = config or AmplificationConfig()

    async def check_amplification(
        self,
        wallet_address: str,
        token_address: str,
        signal_id: Optional[str] = None,
    ) -> AmplificationResult:
        """
        Check if a signal should be amplified based on cluster activity.

        Args:
            wallet_address: Wallet generating the signal
            token_address: Token being traded
            signal_id: Optional signal ID for logging

        Returns:
            AmplificationResult with factor and details
        """
        logger.debug(
            "checking_amplification",
            wallet=wallet_address,
            token=token_address,
        )

        # Check if wallet is in a cluster
        cluster_info = await self._get_wallet_cluster(wallet_address)

        if not cluster_info:
            return AmplificationResult(
                signal_id=signal_id,
                wallet_address=wallet_address,
                token_address=token_address,
                amplification_applied=False,
                reason="wallet_not_in_cluster",
            )

        # Check cluster activity on this token
        activity = await self._get_cluster_activity(
            wallet_address,
            token_address,
            cluster_info["cluster_id"],
        )

        if not activity or activity.active_members and len(activity.active_members) < MIN_ACTIVE_MEMBERS:
            return AmplificationResult(
                signal_id=signal_id,
                wallet_address=wallet_address,
                token_address=token_address,
                cluster_id=cluster_info["cluster_id"],
                amplification_applied=False,
                reason="insufficient_cluster_activity",
            )

        # Check cluster strength threshold
        if cluster_info["cluster_strength"] < MIN_CLUSTER_STRENGTH:
            return AmplificationResult(
                signal_id=signal_id,
                wallet_address=wallet_address,
                token_address=token_address,
                cluster_id=cluster_info["cluster_id"],
                amplification_applied=False,
                reason="cluster_strength_below_threshold",
            )

        # Calculate amplification factor
        factor = self._calculate_amplification_factor(
            activity=activity,
            cluster_strength=cluster_info["cluster_strength"],
        )

        result = AmplificationResult(
            signal_id=signal_id,
            wallet_address=wallet_address,
            token_address=token_address,
            cluster_id=cluster_info["cluster_id"],
            amplification_applied=True,
            factor=factor,
            cluster_activity=activity,
            reason="amplification_applied",
        )

        logger.info(
            "amplification_calculated",
            wallet=wallet_address,
            token=token_address,
            cluster=cluster_info["cluster_id"],
            factor=factor.final_factor,
            active_members=len(activity.active_members),
            leader_participated=activity.leader_participated,
        )

        return result

    async def _get_wallet_cluster(
        self,
        wallet_address: str,
    ) -> Optional[dict]:
        """Get cluster info for a wallet."""
        result = await self.neo4j.execute_read(
            self.queries.GET_WALLET_CLUSTER_INFO,
            {"wallet_address": wallet_address}
        )

        if not result:
            return None

        return {
            "cluster_id": result[0]["cluster_id"],
            "cluster_size": result[0]["cluster_size"],
            "cluster_strength": result[0]["cluster_strength"],
            "leader_address": result[0]["leader_address"],
            "is_leader": result[0]["is_leader"],
        }

    async def _get_cluster_activity(
        self,
        wallet_address: str,
        token_address: str,
        cluster_id: str,
    ) -> Optional[ClusterActivity]:
        """Get cluster activity on a token within the time window."""
        since = datetime.utcnow() - timedelta(seconds=self.config.activity_window_seconds)

        result = await self.neo4j.execute_read(
            self.queries.GET_CLUSTER_ACTIVITY,
            {
                "wallet_address": wallet_address,
                "token_address": token_address,
                "since": since.isoformat(),
            }
        )

        if not result:
            return None

        r = result[0]
        active_members = r.get("active_members", [])

        if not active_members:
            return None

        return ClusterActivity(
            cluster_id=r["cluster_id"],
            token_address=token_address,
            active_members=active_members,
            total_cluster_size=r["cluster_size"],
            participation_rate=len(active_members) / max(r["cluster_size"], 1),
            leader_participated=r.get("leader_participated", False),
            leader_address=r.get("leader"),
            first_signal_time=r["first_signal"],
            last_signal_time=r["last_signal"],
            window_seconds=self.config.activity_window_seconds,
        )

    def _calculate_amplification_factor(
        self,
        activity: ClusterActivity,
        cluster_strength: float,
    ) -> AmplificationFactor:
        """Calculate the amplification factor based on activity."""
        # Start with base factor
        base = self.config.base_amplification

        # Participation bonus (more members = higher bonus)
        extra_members = len(activity.active_members) - self.config.min_active_members
        participation_bonus = min(
            extra_members * self.config.per_member_bonus,
            self.config.max_member_bonus
        )

        # Leader bonus
        leader_bonus = (
            self.config.leader_bonus
            if activity.leader_participated
            else 0.0
        )

        # Cluster strength bonus
        strength_bonus = cluster_strength * self.config.cluster_strength_multiplier

        # Calculate final factor (capped)
        final_factor = min(
            base + participation_bonus + leader_bonus + strength_bonus,
            self.config.max_amplification
        )

        return AmplificationFactor(
            base_factor=base,
            participation_bonus=participation_bonus,
            leader_bonus=leader_bonus,
            cluster_strength_bonus=strength_bonus,
            final_factor=final_factor,
        )

    async def get_cluster_signals(
        self,
        cluster_id: str,
        token_address: str,
        window_seconds: Optional[int] = None,
    ) -> list[dict]:
        """Get recent signals from cluster members for a token."""
        window = window_seconds or self.config.activity_window_seconds
        since = datetime.utcnow() - timedelta(seconds=window)

        result = await self.neo4j.execute_read(
            self.queries.GET_CLUSTER_SIGNALS,
            {
                "cluster_id": cluster_id,
                "token_address": token_address,
                "since": since.isoformat(),
            }
        )

        return [
            {
                "wallet": r["wallet"],
                "signal_id": r["signal_id"],
                "signal_time": r["signal_time"],
                "signal_score": r["signal_score"],
            }
            for r in result
        ]
```

### 5. Integration with Scoring Engine

```python
# src/walltrack/core/scoring/signal_scorer.py (snippet)
"""Signal scoring engine integration."""
from typing import Optional

from walltrack.core.scoring.cluster_amplifier import ClusterAmplifier
from walltrack.core.models.amplification import AmplificationResult


class SignalScorer:
    """Scores signals with cluster amplification support."""

    def __init__(
        self,
        # ... other dependencies
        cluster_amplifier: ClusterAmplifier,
    ):
        self.cluster_amplifier = cluster_amplifier
        # ...

    async def score_signal(
        self,
        wallet_address: str,
        token_address: str,
        base_score: float,
        signal_id: Optional[str] = None,
    ) -> dict:
        """
        Score a signal with optional cluster amplification.

        Args:
            wallet_address: Wallet generating signal
            token_address: Token being traded
            base_score: Base score before amplification
            signal_id: Optional signal ID

        Returns:
            dict with final_score, amplification_result, etc.
        """
        # Check for cluster amplification
        amplification = await self.cluster_amplifier.check_amplification(
            wallet_address=wallet_address,
            token_address=token_address,
            signal_id=signal_id,
        )

        # Apply amplification if applicable
        amplified_score = base_score
        if amplification.amplification_applied:
            amplified_score = base_score * amplification.factor.final_factor

        return {
            "base_score": base_score,
            "final_score": amplified_score,
            "amplification_applied": amplification.amplification_applied,
            "amplification_factor": amplification.factor.final_factor,
            "amplification_result": amplification,
        }
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/amplification.py
"""Cluster amplification API endpoints."""
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from walltrack.core.models.amplification import AmplificationResult
from walltrack.core.scoring.cluster_amplifier import ClusterAmplifier
from walltrack.api.dependencies import get_cluster_amplifier

router = APIRouter(prefix="/amplification", tags=["amplification"])


@router.get("/check", response_model=AmplificationResult)
async def check_amplification(
    wallet_address: str,
    token_address: str,
    signal_id: Optional[str] = None,
    amplifier: ClusterAmplifier = Depends(get_cluster_amplifier),
) -> AmplificationResult:
    """
    Check if a signal should be amplified based on cluster activity.
    """
    try:
        return await amplifier.check_amplification(
            wallet_address=wallet_address,
            token_address=token_address,
            signal_id=signal_id,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cluster/{cluster_id}/signals")
async def get_cluster_signals(
    cluster_id: str,
    token_address: str,
    window_seconds: int = 600,
    amplifier: ClusterAmplifier = Depends(get_cluster_amplifier),
) -> list[dict]:
    """
    Get recent signals from cluster members for a specific token.
    """
    try:
        return await amplifier.get_cluster_signals(
            cluster_id=cluster_id,
            token_address=token_address,
            window_seconds=window_seconds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 7. Unit Tests

```python
# tests/unit/core/scoring/test_cluster_amplifier.py
"""Tests for ClusterAmplifier."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

from walltrack.core.scoring.cluster_amplifier import ClusterAmplifier
from walltrack.core.models.amplification import (
    ClusterActivity, AmplificationConfig
)


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    return client


@pytest.fixture
def config():
    """Test amplification config."""
    return AmplificationConfig(
        activity_window_seconds=600,
        min_active_members=2,
        base_amplification=1.2,
        per_member_bonus=0.05,
        max_member_bonus=0.3,
        leader_bonus=0.15,
        max_amplification=1.8,
    )


@pytest.fixture
def amplifier(mock_neo4j, config):
    """Create ClusterAmplifier with mocks."""
    return ClusterAmplifier(mock_neo4j, config)


class TestCheckAmplification:
    """Tests for check_amplification."""

    @pytest.mark.asyncio
    async def test_no_amplification_without_cluster(self, amplifier, mock_neo4j):
        """Should return no amplification if wallet not in cluster."""
        mock_neo4j.execute_read.return_value = []

        result = await amplifier.check_amplification("wallet1", "token1")

        assert result.amplification_applied is False
        assert result.reason == "wallet_not_in_cluster"

    @pytest.mark.asyncio
    async def test_amplification_with_cluster_activity(self, amplifier, mock_neo4j):
        """Should apply amplification when cluster members are active."""
        # Mock wallet cluster info
        mock_neo4j.execute_read.side_effect = [
            [{
                "cluster_id": "cluster1",
                "cluster_size": 5,
                "cluster_strength": 0.7,
                "leader_address": "leader1",
                "is_leader": False,
            }],
            [{
                "cluster_id": "cluster1",
                "cluster_size": 5,
                "active_members": ["wallet1", "wallet2", "wallet3"],
                "active_count": 3,
                "leader": "leader1",
                "leader_participated": True,
                "strength": 0.7,
                "first_signal": datetime.utcnow() - timedelta(minutes=5),
                "last_signal": datetime.utcnow(),
            }],
        ]

        result = await amplifier.check_amplification("wallet1", "token1")

        assert result.amplification_applied is True
        assert result.factor.final_factor > 1.0
        assert result.cluster_activity is not None


class TestCalculateAmplificationFactor:
    """Tests for _calculate_amplification_factor."""

    def test_base_amplification(self, amplifier, config):
        """Should apply base amplification."""
        activity = ClusterActivity(
            cluster_id="c1",
            token_address="t1",
            active_members=["w1", "w2"],
            total_cluster_size=5,
            participation_rate=0.4,
            leader_participated=False,
            first_signal_time=datetime.utcnow(),
            last_signal_time=datetime.utcnow(),
            window_seconds=600,
        )

        factor = amplifier._calculate_amplification_factor(activity, 0.5)

        assert factor.base_factor == config.base_amplification
        assert factor.final_factor >= config.base_amplification

    def test_leader_bonus(self, amplifier, config):
        """Should add leader bonus when leader participates."""
        activity_with_leader = ClusterActivity(
            cluster_id="c1",
            token_address="t1",
            active_members=["w1", "w2"],
            total_cluster_size=5,
            participation_rate=0.4,
            leader_participated=True,
            leader_address="w1",
            first_signal_time=datetime.utcnow(),
            last_signal_time=datetime.utcnow(),
            window_seconds=600,
        )

        activity_without_leader = ClusterActivity(
            cluster_id="c1",
            token_address="t1",
            active_members=["w1", "w2"],
            total_cluster_size=5,
            participation_rate=0.4,
            leader_participated=False,
            first_signal_time=datetime.utcnow(),
            last_signal_time=datetime.utcnow(),
            window_seconds=600,
        )

        factor_with = amplifier._calculate_amplification_factor(activity_with_leader, 0.5)
        factor_without = amplifier._calculate_amplification_factor(activity_without_leader, 0.5)

        assert factor_with.leader_bonus == config.leader_bonus
        assert factor_without.leader_bonus == 0.0
        assert factor_with.final_factor > factor_without.final_factor

    def test_max_amplification_cap(self, amplifier, config):
        """Should cap amplification at maximum."""
        activity = ClusterActivity(
            cluster_id="c1",
            token_address="t1",
            active_members=["w1", "w2", "w3", "w4", "w5", "w6", "w7", "w8"],
            total_cluster_size=10,
            participation_rate=0.8,
            leader_participated=True,
            leader_address="w1",
            first_signal_time=datetime.utcnow(),
            last_signal_time=datetime.utcnow(),
            window_seconds=600,
        )

        factor = amplifier._calculate_amplification_factor(activity, 1.0)

        assert factor.final_factor <= config.max_amplification
```

---

## Implementation Tasks

- [x] Create cluster activity query
- [x] Implement 10-minute window check
- [x] Calculate amplification factor
- [x] Integrate with signal scoring engine
- [x] Log amplification details
- [x] Make thresholds configurable

## Definition of Done

- [x] Cluster activity detected correctly
- [x] Amplification applied when conditions met
- [x] Factor proportional to cluster activity
- [x] Amplification details logged
