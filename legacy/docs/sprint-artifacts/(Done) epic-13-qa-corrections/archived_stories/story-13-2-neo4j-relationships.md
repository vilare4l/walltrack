# Story 13-2: Fix Neo4j Relationship Naming

## Priority: CRITICAL

## Problem Statement

Two different relationship names are used for cluster membership, causing cluster operations to fail:

- `ClusterQueries` (cluster.py) uses: `MEMBER_OF` (Wallet -> Cluster)
- `ClusterGrouper` (grouping.py) uses: `HAS_MEMBER` (Cluster -> Wallet)
- `SignalAmplifier` uses: `HAS_MEMBER`

## Impact

1. `create_cluster()` creates MEMBER_OF but `expand_cluster()` queries HAS_MEMBER
2. `SignalAmplifier._get_wallet_clusters()` returns empty because it queries HAS_MEMBER
3. Signal amplification based on cluster membership is broken
4. Cluster expansion fails silently

## Files Affected

1. `src/walltrack/data/neo4j/queries/cluster.py`
   - Lines 367, 390, 428, 459: Uses MEMBER_OF

2. `src/walltrack/core/cluster/grouping.py`
   - Lines 177, 179, 223, 325: Uses HAS_MEMBER

3. `src/walltrack/core/cluster/signal_amplifier.py`
   - Lines 193, 196: Uses HAS_MEMBER

## Solution

Standardize on `MEMBER_OF` (Wallet -> Cluster) as it is the semantic direction:
"A wallet IS A MEMBER OF a cluster"

### Changes Required

1. **grouping.py** - Change HAS_MEMBER to MEMBER_OF with reversed direction:
   ```python
   # Before:
   MATCH (c:Cluster {id: $cluster_id})-[:HAS_MEMBER]->(m:Wallet)
   # After:
   MATCH (m:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
   ```

2. **signal_amplifier.py** - Same pattern:
   ```python
   # Before:
   MATCH (c:Cluster)-[:HAS_MEMBER]->(w:Wallet {address: $address})
   # After:
   MATCH (w:Wallet {address: $address})-[:MEMBER_OF]->(c:Cluster)
   ```

3. **Data Migration** - If HAS_MEMBER relationships exist:
   ```cypher
   MATCH (c:Cluster)-[r:HAS_MEMBER]->(w:Wallet)
   MERGE (w)-[:MEMBER_OF]->(c)
   DELETE r
   ```

## Acceptance Criteria

- [ ] All files use `MEMBER_OF` consistently
- [ ] Direction is always `(Wallet)-[:MEMBER_OF]->(Cluster)`
- [ ] Data migration script for existing HAS_MEMBER relationships
- [ ] Unit tests verify cluster queries return members
- [ ] Signal amplification test passes with cluster membership

## Files to Modify

- `src/walltrack/core/cluster/grouping.py`
- `src/walltrack/core/cluster/signal_amplifier.py`
- CREATE: `scripts/migrate_neo4j_relationships.py`

## Testing

```python
# Test: Create cluster, verify members queryable
cluster_id = await cluster_queries.create_cluster(name="Test", members=["addr1", "addr2"])
cluster = await cluster_queries.get_cluster(cluster_id)
assert len(cluster.members) == 2

# Test: Signal amplification finds cluster
clusters = await signal_amplifier._get_wallet_clusters("addr1")
assert len(clusters) == 1
```

## Estimated Effort

1-2 hours
