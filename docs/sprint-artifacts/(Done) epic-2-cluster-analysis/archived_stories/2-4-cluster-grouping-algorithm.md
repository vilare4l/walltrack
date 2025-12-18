# Story 2.4: Cluster Grouping Algorithm

## Story Info
- **Epic**: Epic 2 - Cluster Analysis & Graph Intelligence
- **Status**: done
- **Priority**: High
- **FR**: FR10

## User Story

**As an** operator,
**I want** wallets with strong relationships to be grouped into clusters,
**So that** I can analyze coordinated groups rather than individual wallets.

## Acceptance Criteria

### AC 1: Cluster Detection
**Given** wallets with FUNDED_BY, SYNCED_BUY, and CO_OCCURS relationships
**When** cluster detection algorithm runs
**Then** connected components are identified in the graph
**And** clusters are created as Cluster nodes in Neo4j
**And** MEMBER_OF edges link wallets to their cluster

### AC 2: Cluster Properties
**Given** a cluster is formed
**When** cluster properties are calculated
**Then** cluster size (wallet count) is stored
**And** cluster strength (avg relationship weight) is calculated
**And** cluster creation date is recorded

### AC 3: Cluster Updates
**Given** new relationships are added
**When** cluster recalculation runs
**Then** clusters are updated or merged as appropriate
**And** orphan wallets (no strong relationships) remain unclustered

### AC 4: Wallet-Cluster Association
**Given** a wallet belongs to a cluster
**When** wallet is queried
**Then** cluster_id is returned
**And** other cluster members are accessible

## Technical Notes

- FR10: Group related wallets into clusters
- Use Neo4j community detection or connected components algorithm
- Cluster node: (:Cluster {id, size, strength, created_at})
- Edge: (Wallet)-[:MEMBER_OF]->(Cluster)

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/cluster.py
"""Cluster models for wallet grouping."""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional
import uuid


class ClusterStatus(str, Enum):
    """Cluster status."""
    ACTIVE = "active"
    MERGED = "merged"
    DISSOLVED = "dissolved"


class Cluster(BaseModel):
    """A cluster of related wallets."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: Optional[str] = None
    size: int = Field(default=0, ge=0, description="Number of member wallets")
    strength: float = Field(default=0.0, ge=0, le=1, description="Average relationship strength")
    status: ClusterStatus = Field(default=ClusterStatus.ACTIVE)
    leader_address: Optional[str] = Field(default=None, description="Identified cluster leader")
    leader_score: float = Field(default=0.0)
    total_volume_sol: float = Field(default=0.0)
    avg_win_rate: float = Field(default=0.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        frozen = False


class ClusterMember(BaseModel):
    """A wallet's membership in a cluster."""

    wallet_address: str
    cluster_id: str
    is_leader: bool = Field(default=False)
    contribution_score: float = Field(default=0.0, description="Contribution to cluster strength")
    joined_at: datetime = Field(default_factory=datetime.utcnow)


class ClusterRelationship(BaseModel):
    """Summary of relationships within a cluster."""

    cluster_id: str
    funding_edges: int = Field(default=0)
    sync_edges: int = Field(default=0)
    cooccur_edges: int = Field(default=0)
    total_edge_weight: float = Field(default=0.0)
    density: float = Field(default=0.0, description="Edge density (edges/possible_edges)")


class ClusterDetectionResult(BaseModel):
    """Result of cluster detection."""

    clusters_created: int = Field(default=0)
    clusters_updated: int = Field(default=0)
    clusters_merged: int = Field(default=0)
    clusters_dissolved: int = Field(default=0)
    total_clustered_wallets: int = Field(default=0)
    orphan_wallets: int = Field(default=0)
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class ClusterSummary(BaseModel):
    """Summary view of a cluster."""

    id: str
    size: int
    strength: float
    status: ClusterStatus
    leader_address: Optional[str]
    top_members: list[str] = Field(default_factory=list)
    recent_tokens: list[str] = Field(default_factory=list)
    created_at: datetime
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/cluster.py
"""Cluster analysis constants."""

# Minimum relationship strength to consider for clustering
MIN_RELATIONSHIP_STRENGTH = 0.3

# Minimum cluster size to create
MIN_CLUSTER_SIZE = 2

# Maximum cluster size (prevent mega-clusters)
MAX_CLUSTER_SIZE = 100

# Minimum edge weight to include in clustering
MIN_EDGE_WEIGHT_FUNDING = 0.1
MIN_EDGE_WEIGHT_SYNC = 2  # sync_count
MIN_EDGE_WEIGHT_COOCCUR = 3  # co_occurrence_count

# Cluster merge threshold (similarity to trigger merge)
CLUSTER_MERGE_SIMILARITY_THRESHOLD = 0.7

# Cluster dissolution threshold (inactive days)
CLUSTER_INACTIVE_DAYS_THRESHOLD = 30

# Relationship type weights for clustering
RELATIONSHIP_WEIGHTS = {
    "FUNDED_BY": 1.5,   # Funding is strongest indicator
    "SYNCED_BUY": 1.2,  # Sync buying is strong
    "CO_OCCURS": 1.0,   # Co-occurrence is baseline
}
```

### 3. Neo4j Schema & Queries

```python
# src/walltrack/data/neo4j/queries/cluster.py
"""Neo4j queries for cluster management."""


class ClusterQueries:
    """Cypher queries for Cluster nodes and MEMBER_OF edges."""

    # Create Cluster node
    CREATE_CLUSTER = """
    CREATE (c:Cluster {
        id: $cluster_id,
        name: $name,
        size: $size,
        strength: $strength,
        status: $status,
        leader_address: $leader_address,
        leader_score: $leader_score,
        total_volume_sol: $total_volume_sol,
        avg_win_rate: $avg_win_rate,
        created_at: datetime(),
        updated_at: datetime()
    })
    RETURN c
    """

    # Create MEMBER_OF edge
    CREATE_MEMBER_OF = """
    MATCH (w:Wallet {address: $wallet_address})
    MATCH (c:Cluster {id: $cluster_id})
    MERGE (w)-[r:MEMBER_OF]->(c)
    ON CREATE SET
        r.is_leader = $is_leader,
        r.contribution_score = $contribution_score,
        r.joined_at = datetime()
    ON MATCH SET
        r.is_leader = $is_leader,
        r.contribution_score = $contribution_score,
        r.updated_at = datetime()
    RETURN r
    """

    # Find connected components using Graph Data Science
    # Note: Requires GDS library
    DETECT_COMMUNITIES_GDS = """
    CALL gds.graph.project(
        'wallet_graph',
        'Wallet',
        {
            FUNDED_BY: {orientation: 'UNDIRECTED', properties: ['strength']},
            SYNCED_BUY: {orientation: 'UNDIRECTED', properties: ['sync_count']},
            CO_OCCURS: {orientation: 'UNDIRECTED', properties: ['count']}
        }
    )
    YIELD graphName
    CALL gds.wcc.stream('wallet_graph')
    YIELD nodeId, componentId
    WITH gds.util.asNode(nodeId) AS wallet, componentId
    RETURN wallet.address AS wallet_address, componentId AS cluster_id
    ORDER BY cluster_id
    """

    # Alternative: Native connected components (no GDS)
    DETECT_CONNECTED_COMPONENTS = """
    MATCH (w:Wallet)
    WHERE EXISTS((w)-[:FUNDED_BY|SYNCED_BUY|CO_OCCURS]-())
    WITH collect(w) AS wallets
    UNWIND wallets AS wallet
    MATCH path = (wallet)-[:FUNDED_BY|SYNCED_BUY|CO_OCCURS*1..5]-(connected:Wallet)
    WITH wallet, collect(DISTINCT connected) + [wallet] AS component
    WITH collect({wallet: wallet, component: component}) AS all_components
    // Merge overlapping components
    UNWIND all_components AS item
    WITH item.wallet AS wallet,
         reduce(merged = [], comp IN [c IN all_components WHERE item.wallet IN c.component | c.component] |
                apoc.coll.union(merged, comp)) AS final_component
    RETURN wallet.address AS wallet_address,
           apoc.coll.sort(final_component)[0].address AS cluster_seed
    """

    # Get cluster by ID
    GET_CLUSTER = """
    MATCH (c:Cluster {id: $cluster_id})
    RETURN c
    """

    # Get cluster members
    GET_CLUSTER_MEMBERS = """
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster {id: $cluster_id})
    RETURN w.address AS wallet_address,
           r.is_leader AS is_leader,
           r.contribution_score AS contribution_score,
           r.joined_at AS joined_at
    ORDER BY r.contribution_score DESC
    """

    # Get wallet's cluster
    GET_WALLET_CLUSTER = """
    MATCH (w:Wallet {address: $wallet_address})-[r:MEMBER_OF]->(c:Cluster)
    WHERE c.status = 'active'
    RETURN c.id AS cluster_id,
           c.size AS size,
           c.strength AS strength,
           c.leader_address AS leader,
           r.is_leader AS is_leader
    """

    # Calculate cluster strength
    CALCULATE_CLUSTER_STRENGTH = """
    MATCH (w1:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})<-[:MEMBER_OF]-(w2:Wallet)
    WHERE w1.address < w2.address
    OPTIONAL MATCH (w1)-[f:FUNDED_BY]-(w2)
    OPTIONAL MATCH (w1)-[s:SYNCED_BUY]-(w2)
    OPTIONAL MATCH (w1)-[o:CO_OCCURS]-(w2)
    WITH c,
         count(DISTINCT f) AS funding_edges,
         count(DISTINCT s) AS sync_edges,
         count(DISTINCT o) AS cooccur_edges,
         avg(COALESCE(f.strength, 0)) AS avg_funding_strength,
         avg(COALESCE(s.sync_count, 0)) AS avg_sync_count,
         avg(COALESCE(o.count, 0)) AS avg_cooccur_count
    RETURN funding_edges,
           sync_edges,
           cooccur_edges,
           avg_funding_strength,
           avg_sync_count,
           avg_cooccur_count
    """

    # Update cluster properties
    UPDATE_CLUSTER = """
    MATCH (c:Cluster {id: $cluster_id})
    SET c.size = $size,
        c.strength = $strength,
        c.leader_address = $leader_address,
        c.leader_score = $leader_score,
        c.updated_at = datetime()
    RETURN c
    """

    # Dissolve cluster (mark as dissolved, remove memberships)
    DISSOLVE_CLUSTER = """
    MATCH (c:Cluster {id: $cluster_id})
    SET c.status = 'dissolved',
        c.updated_at = datetime()
    WITH c
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c)
    DELETE r
    RETURN count(r) AS removed_members
    """

    # Merge clusters
    MERGE_CLUSTERS = """
    // Move members from source to target
    MATCH (w:Wallet)-[r:MEMBER_OF]->(source:Cluster {id: $source_cluster_id})
    MATCH (target:Cluster {id: $target_cluster_id})
    DELETE r
    CREATE (w)-[:MEMBER_OF {
        is_leader: false,
        contribution_score: 0,
        joined_at: datetime()
    }]->(target)
    WITH source, target, count(w) AS moved_count
    SET source.status = 'merged',
        source.updated_at = datetime(),
        target.size = target.size + moved_count,
        target.updated_at = datetime()
    RETURN moved_count
    """

    # Get all active clusters
    GET_ALL_CLUSTERS = """
    MATCH (c:Cluster)
    WHERE c.status = 'active'
    RETURN c.id AS id,
           c.size AS size,
           c.strength AS strength,
           c.leader_address AS leader_address,
           c.created_at AS created_at
    ORDER BY c.size DESC
    LIMIT $limit
    """

    # Get orphan wallets (no cluster)
    GET_ORPHAN_WALLETS = """
    MATCH (w:Wallet)
    WHERE NOT EXISTS((w)-[:MEMBER_OF]->(:Cluster {status: 'active'}))
    AND EXISTS((w)-[:FUNDED_BY|SYNCED_BUY|CO_OCCURS]-())
    RETURN w.address AS wallet_address
    LIMIT $limit
    """

    # Delete cluster and relationships
    DELETE_CLUSTER = """
    MATCH (c:Cluster {id: $cluster_id})
    OPTIONAL MATCH (w:Wallet)-[r:MEMBER_OF]->(c)
    DELETE r, c
    RETURN count(r) AS deleted_memberships
    """
```

### 4. ClusterService

```python
# src/walltrack/core/services/cluster_service.py
"""Service for cluster detection and management."""
import structlog
from datetime import datetime, timedelta
from typing import Optional
import uuid

from walltrack.core.models.cluster import (
    Cluster, ClusterMember, ClusterStatus, ClusterRelationship,
    ClusterDetectionResult, ClusterSummary
)
from walltrack.core.constants.cluster import (
    MIN_RELATIONSHIP_STRENGTH, MIN_CLUSTER_SIZE, MAX_CLUSTER_SIZE,
    MIN_EDGE_WEIGHT_FUNDING, MIN_EDGE_WEIGHT_SYNC, MIN_EDGE_WEIGHT_COOCCUR,
    CLUSTER_MERGE_SIMILARITY_THRESHOLD, RELATIONSHIP_WEIGHTS
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries

logger = structlog.get_logger(__name__)


class ClusterService:
    """Manages wallet cluster detection and operations."""

    def __init__(self, neo4j_client: Neo4jClient):
        self.neo4j = neo4j_client
        self.queries = ClusterQueries()

    async def detect_clusters(self) -> ClusterDetectionResult:
        """
        Run cluster detection algorithm on the wallet graph.

        Uses connected components to identify wallet groups.

        Returns:
            ClusterDetectionResult with detection statistics
        """
        logger.info("starting_cluster_detection")

        # Get connected components
        components = await self._find_connected_components()

        clusters_created = 0
        clusters_updated = 0
        total_clustered = 0
        orphan_count = 0

        # Group wallets by component
        component_groups = {}
        for wallet, component_id in components:
            if component_id not in component_groups:
                component_groups[component_id] = []
            component_groups[component_id].append(wallet)

        for component_id, wallets in component_groups.items():
            if len(wallets) < MIN_CLUSTER_SIZE:
                orphan_count += len(wallets)
                continue

            if len(wallets) > MAX_CLUSTER_SIZE:
                # Split large clusters
                sub_clusters = self._split_large_cluster(wallets)
                for sub_wallets in sub_clusters:
                    await self._create_or_update_cluster(sub_wallets)
                    clusters_created += 1
                    total_clustered += len(sub_wallets)
            else:
                result = await self._create_or_update_cluster(wallets)
                if result["created"]:
                    clusters_created += 1
                else:
                    clusters_updated += 1
                total_clustered += len(wallets)

        # Handle cluster merges
        clusters_merged = await self._merge_similar_clusters()

        result = ClusterDetectionResult(
            clusters_created=clusters_created,
            clusters_updated=clusters_updated,
            clusters_merged=clusters_merged,
            total_clustered_wallets=total_clustered,
            orphan_wallets=orphan_count,
        )

        logger.info(
            "cluster_detection_complete",
            created=clusters_created,
            updated=clusters_updated,
            merged=clusters_merged,
            clustered=total_clustered,
            orphans=orphan_count,
        )

        return result

    async def _find_connected_components(self) -> list[tuple[str, str]]:
        """Find connected components in the wallet graph."""
        query = """
        MATCH (w:Wallet)
        WHERE EXISTS {
            (w)-[r:FUNDED_BY|SYNCED_BUY|CO_OCCURS]-()
            WHERE (r.strength IS NULL OR r.strength >= $min_strength)
               OR (r.sync_count IS NOT NULL AND r.sync_count >= $min_sync)
               OR (r.count IS NOT NULL AND r.count >= $min_cooccur)
        }
        WITH collect(w) AS wallets
        CALL {
            WITH wallets
            UNWIND wallets AS start
            MATCH path = (start)-[:FUNDED_BY|SYNCED_BUY|CO_OCCURS*1..10]-(connected:Wallet)
            WHERE connected IN wallets
            WITH start, collect(DISTINCT connected) AS reachable
            RETURN start.address AS wallet,
                   reduce(seed = start.address, w IN reachable |
                          CASE WHEN w.address < seed THEN w.address ELSE seed END) AS component
        }
        RETURN wallet, component
        """

        result = await self.neo4j.execute_read(
            query,
            {
                "min_strength": MIN_RELATIONSHIP_STRENGTH,
                "min_sync": MIN_EDGE_WEIGHT_SYNC,
                "min_cooccur": MIN_EDGE_WEIGHT_COOCCUR,
            }
        )

        return [(r["wallet"], r["component"]) for r in result]

    def _split_large_cluster(self, wallets: list[str]) -> list[list[str]]:
        """Split a large cluster into smaller sub-clusters."""
        # Simple chunking for now
        # Could be enhanced with community detection
        chunk_size = MAX_CLUSTER_SIZE
        return [wallets[i:i+chunk_size] for i in range(0, len(wallets), chunk_size)]

    async def _create_or_update_cluster(
        self,
        wallet_addresses: list[str],
    ) -> dict[str, bool]:
        """Create a new cluster or update existing one for wallets."""
        # Check if wallets already have a cluster
        existing_cluster = await self._get_existing_cluster(wallet_addresses)

        if existing_cluster:
            # Update existing cluster
            await self._update_cluster_members(existing_cluster, wallet_addresses)
            await self._recalculate_cluster_properties(existing_cluster)
            return {"created": False, "cluster_id": existing_cluster}
        else:
            # Create new cluster
            cluster_id = str(uuid.uuid4())

            # Calculate initial properties
            strength = await self._calculate_cluster_strength_for_wallets(wallet_addresses)

            # Create cluster node
            await self.neo4j.execute_write(
                self.queries.CREATE_CLUSTER,
                {
                    "cluster_id": cluster_id,
                    "name": None,
                    "size": len(wallet_addresses),
                    "strength": strength,
                    "status": ClusterStatus.ACTIVE.value,
                    "leader_address": None,
                    "leader_score": 0.0,
                    "total_volume_sol": 0.0,
                    "avg_win_rate": 0.0,
                }
            )

            # Create MEMBER_OF edges
            for wallet in wallet_addresses:
                await self.neo4j.execute_write(
                    self.queries.CREATE_MEMBER_OF,
                    {
                        "wallet_address": wallet,
                        "cluster_id": cluster_id,
                        "is_leader": False,
                        "contribution_score": 0.0,
                    }
                )

            return {"created": True, "cluster_id": cluster_id}

    async def _get_existing_cluster(
        self,
        wallet_addresses: list[str],
    ) -> Optional[str]:
        """Check if any of the wallets already belong to a cluster."""
        if not wallet_addresses:
            return None

        query = """
        UNWIND $wallets AS wallet_addr
        MATCH (w:Wallet {address: wallet_addr})-[:MEMBER_OF]->(c:Cluster {status: 'active'})
        RETURN c.id AS cluster_id, count(w) AS member_count
        ORDER BY member_count DESC
        LIMIT 1
        """

        result = await self.neo4j.execute_read(
            query,
            {"wallets": wallet_addresses}
        )

        if result and result[0]["member_count"] > len(wallet_addresses) * 0.5:
            return result[0]["cluster_id"]
        return None

    async def _update_cluster_members(
        self,
        cluster_id: str,
        wallet_addresses: list[str],
    ) -> None:
        """Update cluster membership for wallets."""
        for wallet in wallet_addresses:
            await self.neo4j.execute_write(
                self.queries.CREATE_MEMBER_OF,
                {
                    "wallet_address": wallet,
                    "cluster_id": cluster_id,
                    "is_leader": False,
                    "contribution_score": 0.0,
                }
            )

    async def _recalculate_cluster_properties(self, cluster_id: str) -> None:
        """Recalculate cluster size and strength."""
        # Get member count
        count_query = """
        MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
        RETURN count(w) AS size
        """
        count_result = await self.neo4j.execute_read(
            count_query,
            {"cluster_id": cluster_id}
        )
        size = count_result[0]["size"] if count_result else 0

        # Calculate strength
        strength_result = await self.neo4j.execute_read(
            self.queries.CALCULATE_CLUSTER_STRENGTH,
            {"cluster_id": cluster_id}
        )

        strength = 0.0
        if strength_result:
            r = strength_result[0]
            # Weighted average of relationship types
            total_edges = r["funding_edges"] + r["sync_edges"] + r["cooccur_edges"]
            if total_edges > 0:
                strength = (
                    r["avg_funding_strength"] * RELATIONSHIP_WEIGHTS["FUNDED_BY"] * r["funding_edges"] +
                    (r["avg_sync_count"] / 10) * RELATIONSHIP_WEIGHTS["SYNCED_BUY"] * r["sync_edges"] +
                    (r["avg_cooccur_count"] / 10) * RELATIONSHIP_WEIGHTS["CO_OCCURS"] * r["cooccur_edges"]
                ) / (total_edges * max(RELATIONSHIP_WEIGHTS.values()))

        # Update cluster
        await self.neo4j.execute_write(
            self.queries.UPDATE_CLUSTER,
            {
                "cluster_id": cluster_id,
                "size": size,
                "strength": min(strength, 1.0),
                "leader_address": None,  # Will be set by leader identification
                "leader_score": 0.0,
            }
        )

    async def _calculate_cluster_strength_for_wallets(
        self,
        wallet_addresses: list[str],
    ) -> float:
        """Calculate cluster strength for a set of wallets before cluster creation."""
        if len(wallet_addresses) < 2:
            return 0.0

        query = """
        UNWIND $wallets AS w1_addr
        UNWIND $wallets AS w2_addr
        MATCH (w1:Wallet {address: w1_addr}), (w2:Wallet {address: w2_addr})
        WHERE w1_addr < w2_addr
        OPTIONAL MATCH (w1)-[f:FUNDED_BY]-(w2)
        OPTIONAL MATCH (w1)-[s:SYNCED_BUY]-(w2)
        OPTIONAL MATCH (w1)-[o:CO_OCCURS]-(w2)
        WITH avg(COALESCE(f.strength, 0)) AS avg_f,
             avg(COALESCE(s.sync_count, 0)) AS avg_s,
             avg(COALESCE(o.count, 0)) AS avg_o,
             count(f) + count(s) + count(o) AS total_edges
        RETURN avg_f, avg_s, avg_o, total_edges
        """

        result = await self.neo4j.execute_read(
            query,
            {"wallets": wallet_addresses}
        )

        if not result or result[0]["total_edges"] == 0:
            return 0.0

        r = result[0]
        strength = (
            r["avg_f"] * RELATIONSHIP_WEIGHTS["FUNDED_BY"] +
            (r["avg_s"] / 10) * RELATIONSHIP_WEIGHTS["SYNCED_BUY"] +
            (r["avg_o"] / 10) * RELATIONSHIP_WEIGHTS["CO_OCCURS"]
        ) / sum(RELATIONSHIP_WEIGHTS.values())

        return min(strength, 1.0)

    async def _merge_similar_clusters(self) -> int:
        """Merge clusters that share many members or have high overlap."""
        # Find clusters with overlapping wallets
        overlap_query = """
        MATCH (w:Wallet)-[:MEMBER_OF]->(c1:Cluster {status: 'active'})
        MATCH (w)-[:FUNDED_BY|SYNCED_BUY|CO_OCCURS]-(w2:Wallet)-[:MEMBER_OF]->(c2:Cluster {status: 'active'})
        WHERE c1.id < c2.id
        WITH c1, c2, count(DISTINCT w) AS overlap_count
        MATCH (any:Wallet)-[:MEMBER_OF]->(c1)
        WITH c1, c2, overlap_count, count(any) AS c1_size
        WHERE toFloat(overlap_count) / c1_size >= $threshold
        RETURN c1.id AS source_id, c2.id AS target_id
        """

        result = await self.neo4j.execute_read(
            overlap_query,
            {"threshold": CLUSTER_MERGE_SIMILARITY_THRESHOLD}
        )

        merged_count = 0
        for r in result:
            await self.neo4j.execute_write(
                self.queries.MERGE_CLUSTERS,
                {
                    "source_cluster_id": r["source_id"],
                    "target_cluster_id": r["target_id"],
                }
            )
            merged_count += 1

        return merged_count

    async def get_cluster(self, cluster_id: str) -> Optional[Cluster]:
        """Get a cluster by ID."""
        result = await self.neo4j.execute_read(
            self.queries.GET_CLUSTER,
            {"cluster_id": cluster_id}
        )

        if not result:
            return None

        c = result[0]["c"]
        return Cluster(
            id=c["id"],
            name=c.get("name"),
            size=c["size"],
            strength=c["strength"],
            status=ClusterStatus(c["status"]),
            leader_address=c.get("leader_address"),
            leader_score=c.get("leader_score", 0.0),
            created_at=c["created_at"],
            updated_at=c["updated_at"],
        )

    async def get_cluster_members(
        self,
        cluster_id: str,
    ) -> list[ClusterMember]:
        """Get all members of a cluster."""
        result = await self.neo4j.execute_read(
            self.queries.GET_CLUSTER_MEMBERS,
            {"cluster_id": cluster_id}
        )

        return [
            ClusterMember(
                wallet_address=r["wallet_address"],
                cluster_id=cluster_id,
                is_leader=r["is_leader"],
                contribution_score=r["contribution_score"],
                joined_at=r["joined_at"],
            )
            for r in result
        ]

    async def get_wallet_cluster(
        self,
        wallet_address: str,
    ) -> Optional[ClusterSummary]:
        """Get the cluster a wallet belongs to."""
        result = await self.neo4j.execute_read(
            self.queries.GET_WALLET_CLUSTER,
            {"wallet_address": wallet_address}
        )

        if not result:
            return None

        r = result[0]
        return ClusterSummary(
            id=r["cluster_id"],
            size=r["size"],
            strength=r["strength"],
            status=ClusterStatus.ACTIVE,
            leader_address=r.get("leader"),
            created_at=datetime.utcnow(),  # Would need separate query
        )

    async def get_all_clusters(
        self,
        limit: int = 100,
    ) -> list[ClusterSummary]:
        """Get all active clusters."""
        result = await self.neo4j.execute_read(
            self.queries.GET_ALL_CLUSTERS,
            {"limit": limit}
        )

        return [
            ClusterSummary(
                id=r["id"],
                size=r["size"],
                strength=r["strength"],
                status=ClusterStatus.ACTIVE,
                leader_address=r.get("leader_address"),
                created_at=r["created_at"],
            )
            for r in result
        ]

    async def dissolve_cluster(self, cluster_id: str) -> int:
        """Dissolve a cluster and remove all memberships."""
        result = await self.neo4j.execute_write(
            self.queries.DISSOLVE_CLUSTER,
            {"cluster_id": cluster_id}
        )
        return result[0]["removed_members"] if result else 0
```

### 5. Scheduled Task

```python
# src/walltrack/tasks/cluster_detection.py
"""Scheduled task for cluster detection."""
import structlog
from datetime import datetime

from walltrack.core.services.cluster_service import ClusterService

logger = structlog.get_logger(__name__)


async def run_cluster_detection(
    cluster_service: ClusterService,
) -> None:
    """
    Run cluster detection algorithm.

    Called by scheduler (e.g., every 6 hours).
    """
    logger.info("starting_scheduled_cluster_detection")

    try:
        result = await cluster_service.detect_clusters()

        logger.info(
            "scheduled_cluster_detection_complete",
            created=result.clusters_created,
            updated=result.clusters_updated,
            merged=result.clusters_merged,
            clustered_wallets=result.total_clustered_wallets,
            orphans=result.orphan_wallets,
        )

    except Exception as e:
        logger.error("cluster_detection_failed", error=str(e))
        raise
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/clusters.py
"""Cluster management API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional

from walltrack.core.models.cluster import (
    Cluster, ClusterMember, ClusterDetectionResult, ClusterSummary
)
from walltrack.core.services.cluster_service import ClusterService
from walltrack.api.dependencies import get_cluster_service

router = APIRouter(prefix="/clusters", tags=["clusters"])


@router.post("/detect", response_model=ClusterDetectionResult)
async def detect_clusters(
    service: ClusterService = Depends(get_cluster_service),
) -> ClusterDetectionResult:
    """
    Run cluster detection algorithm on the wallet graph.
    """
    try:
        return await service.detect_clusters()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/", response_model=list[ClusterSummary])
async def list_clusters(
    limit: int = Query(default=100, ge=1, le=500),
    service: ClusterService = Depends(get_cluster_service),
) -> list[ClusterSummary]:
    """
    Get all active clusters.
    """
    try:
        return await service.get_all_clusters(limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cluster_id}", response_model=Optional[Cluster])
async def get_cluster(
    cluster_id: str,
    service: ClusterService = Depends(get_cluster_service),
) -> Optional[Cluster]:
    """
    Get cluster details by ID.
    """
    try:
        cluster = await service.get_cluster(cluster_id)
        if not cluster:
            raise HTTPException(status_code=404, detail="Cluster not found")
        return cluster
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{cluster_id}/members", response_model=list[ClusterMember])
async def get_cluster_members(
    cluster_id: str,
    service: ClusterService = Depends(get_cluster_service),
) -> list[ClusterMember]:
    """
    Get all members of a cluster.
    """
    try:
        return await service.get_cluster_members(cluster_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/wallet/{wallet_address}", response_model=Optional[ClusterSummary])
async def get_wallet_cluster(
    wallet_address: str,
    service: ClusterService = Depends(get_cluster_service),
) -> Optional[ClusterSummary]:
    """
    Get the cluster a wallet belongs to.
    """
    try:
        return await service.get_wallet_cluster(wallet_address)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{cluster_id}")
async def dissolve_cluster(
    cluster_id: str,
    service: ClusterService = Depends(get_cluster_service),
) -> dict:
    """
    Dissolve a cluster and remove all memberships.
    """
    try:
        removed = await service.dissolve_cluster(cluster_id)
        return {"dissolved": True, "removed_members": removed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

### 7. Unit Tests

```python
# tests/unit/core/services/test_cluster_service.py
"""Tests for ClusterService."""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock

from walltrack.core.services.cluster_service import ClusterService
from walltrack.core.models.cluster import Cluster, ClusterStatus


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j client."""
    client = AsyncMock()
    client.execute_read = AsyncMock(return_value=[])
    client.execute_write = AsyncMock(return_value=[{}])
    return client


@pytest.fixture
def service(mock_neo4j):
    """Create ClusterService with mock."""
    return ClusterService(mock_neo4j)


class TestDetectClusters:
    """Tests for detect_clusters."""

    @pytest.mark.asyncio
    async def test_creates_clusters_from_components(self, service, mock_neo4j):
        """Should create clusters from connected components."""
        # Mock connected components
        mock_neo4j.execute_read.side_effect = [
            # _find_connected_components
            [
                {"wallet": "wallet1", "component": "component1"},
                {"wallet": "wallet2", "component": "component1"},
                {"wallet": "wallet3", "component": "component1"},
            ],
            # _get_existing_cluster
            [],
            # _calculate_cluster_strength_for_wallets
            [{"avg_f": 0.5, "avg_s": 3, "avg_o": 2, "total_edges": 5}],
        ]

        result = await service.detect_clusters()

        assert result.clusters_created == 1
        assert result.total_clustered_wallets == 3

    @pytest.mark.asyncio
    async def test_handles_orphan_wallets(self, service, mock_neo4j):
        """Should count wallets without enough connections as orphans."""
        mock_neo4j.execute_read.return_value = [
            {"wallet": "lonely_wallet", "component": "solo_component"},
        ]

        result = await service.detect_clusters()

        assert result.orphan_wallets == 1
        assert result.clusters_created == 0


class TestGetCluster:
    """Tests for get_cluster."""

    @pytest.mark.asyncio
    async def test_returns_cluster(self, service, mock_neo4j):
        """Should return cluster by ID."""
        mock_neo4j.execute_read.return_value = [{
            "c": {
                "id": "cluster123",
                "name": "Test Cluster",
                "size": 5,
                "strength": 0.7,
                "status": "active",
                "leader_address": "leader1",
                "leader_score": 0.9,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
            }
        }]

        cluster = await service.get_cluster("cluster123")

        assert cluster is not None
        assert cluster.id == "cluster123"
        assert cluster.size == 5
        assert cluster.status == ClusterStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_returns_none_for_missing(self, service, mock_neo4j):
        """Should return None for non-existent cluster."""
        mock_neo4j.execute_read.return_value = []

        cluster = await service.get_cluster("nonexistent")

        assert cluster is None


class TestGetWalletCluster:
    """Tests for get_wallet_cluster."""

    @pytest.mark.asyncio
    async def test_returns_wallet_cluster(self, service, mock_neo4j):
        """Should return cluster for a wallet."""
        mock_neo4j.execute_read.return_value = [{
            "cluster_id": "cluster123",
            "size": 10,
            "strength": 0.8,
            "leader": "leader1",
            "is_leader": False,
        }]

        summary = await service.get_wallet_cluster("wallet123")

        assert summary is not None
        assert summary.id == "cluster123"
        assert summary.size == 10


class TestClusterStrengthCalculation:
    """Tests for cluster strength calculation."""

    @pytest.mark.asyncio
    async def test_calculates_strength_from_relationships(self, service, mock_neo4j):
        """Should calculate strength from relationship weights."""
        mock_neo4j.execute_read.return_value = [{
            "avg_f": 0.6,
            "avg_s": 5,
            "avg_o": 4,
            "total_edges": 10,
        }]

        strength = await service._calculate_cluster_strength_for_wallets(
            ["w1", "w2", "w3"]
        )

        assert 0 <= strength <= 1
        assert strength > 0
```

---

## Implementation Tasks

- [x] Implement cluster detection algorithm
- [x] Create Cluster nodes in Neo4j
- [x] Create MEMBER_OF edges
- [x] Calculate cluster properties (size, strength)
- [x] Implement cluster merge logic
- [x] Handle orphan wallets appropriately
- [x] Add cluster recalculation scheduling

## Definition of Done

- [x] Clusters identified from graph relationships
- [x] Cluster nodes created with properties
- [x] Wallets linked to clusters via MEMBER_OF
- [x] Cluster updates handle merges correctly
