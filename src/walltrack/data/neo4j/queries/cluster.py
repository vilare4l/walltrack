"""Cluster-related Neo4j queries."""

from datetime import datetime
from typing import Any

import structlog

from walltrack.data.models.cluster import (
    Cluster,
    ClusterMember,
    CommonAncestor,
    CoOccurrenceEdge,
    FundingEdge,
    FundingNode,
    FundingTree,
    SyncBuyEdge,
)
from walltrack.data.neo4j.client import Neo4jClient

log = structlog.get_logger()


class ClusterQueries:
    """Neo4j queries for cluster analysis."""

    def __init__(self, client: Neo4jClient) -> None:
        self._client = client

    # =========================================================================
    # FUNDED_BY Relationships
    # =========================================================================

    async def create_funding_edge(self, edge: FundingEdge) -> bool:
        """Create a FUNDED_BY relationship between wallets."""
        query = """
        MATCH (source:Wallet {address: $source})
        MATCH (target:Wallet {address: $target})
        MERGE (source)-[r:FUNDED_BY]->(target)
        ON CREATE SET
            r.amount_sol = $amount,
            r.timestamp = datetime($timestamp),
            r.tx_signature = $tx_sig,
            r.strength = $strength,
            r.created_at = datetime()
        ON MATCH SET
            r.amount_sol = r.amount_sol + $amount,
            r.strength = CASE WHEN $strength > r.strength THEN $strength ELSE r.strength END,
            r.updated_at = datetime()
        RETURN r
        """
        result = await self._client.execute_query(
            query,
            {
                "source": edge.source_wallet,
                "target": edge.target_wallet,
                "amount": edge.amount_sol,
                "timestamp": edge.timestamp.isoformat(),
                "tx_sig": edge.tx_signature,
                "strength": edge.strength,
            },
        )
        return len(result) > 0

    async def get_funding_sources(
        self, wallet_address: str, min_amount: float = 0.1
    ) -> list[FundingEdge]:
        """Get wallets that funded the given wallet."""
        query = """
        MATCH (source:Wallet)-[r:FUNDED_BY]->(target:Wallet {address: $address})
        WHERE r.amount_sol >= $min_amount
        RETURN source.address as source,
               target.address as target,
               r.amount_sol as amount,
               r.timestamp as timestamp,
               r.tx_signature as tx_sig,
               r.strength as strength
        ORDER BY r.amount_sol DESC
        """
        results = await self._client.execute_query(
            query, {"address": wallet_address, "min_amount": min_amount}
        )
        edges = []
        for r in results:
            ts = r.get("timestamp")
            if ts is not None and hasattr(ts, "to_native"):
                ts = ts.to_native()
            elif isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                ts = datetime.utcnow()

            edges.append(
                FundingEdge(
                    source_wallet=r["source"],
                    target_wallet=r["target"],
                    amount_sol=r["amount"] or 0.0,
                    timestamp=ts,
                    tx_signature=r.get("tx_sig") or "",
                    strength=r.get("strength") or 0.0,
                )
            )
        return edges

    async def get_funding_tree(
        self, wallet_address: str, max_depth: int = 3
    ) -> FundingTree:
        """Get the complete funding tree for a wallet."""
        query = """
        MATCH path = (source:Wallet)-[:FUNDED_BY*1..$depth]->(target:Wallet {address: $address})
        WITH source, target, path, length(path) as depth
        UNWIND relationships(path) as r
        WITH DISTINCT source, depth,
             startNode(r).address as from_addr,
             endNode(r).address as to_addr,
             r.amount_sol as amount,
             r.timestamp as timestamp,
             r.tx_signature as tx_sig,
             r.strength as strength
        RETURN from_addr, to_addr, amount, timestamp, tx_sig, strength, depth
        ORDER BY depth, amount DESC
        """
        results = await self._client.execute_query(
            query, {"address": wallet_address, "depth": max_depth}
        )

        nodes_map: dict[str, FundingNode] = {}
        edges: list[FundingEdge] = []
        max_d = 0

        for r in results:
            from_addr = r["from_addr"]
            depth = r["depth"]
            max_d = max(max_d, depth)

            ts = r.get("timestamp")
            if ts is not None and hasattr(ts, "to_native"):
                ts = ts.to_native()
            elif isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            else:
                ts = datetime.utcnow()

            if from_addr not in nodes_map:
                nodes_map[from_addr] = FundingNode(
                    address=from_addr,
                    level=depth,
                    total_funded=r["amount"] or 0.0,
                    funding_count=1,
                    first_funding=ts,
                    last_funding=ts,
                )
            else:
                node = nodes_map[from_addr]
                nodes_map[from_addr] = FundingNode(
                    address=from_addr,
                    level=min(node.level, depth),
                    total_funded=node.total_funded + (r["amount"] or 0.0),
                    funding_count=node.funding_count + 1,
                    first_funding=min(node.first_funding, ts) if node.first_funding else ts,
                    last_funding=max(node.last_funding, ts) if node.last_funding else ts,
                )

            edges.append(
                FundingEdge(
                    source_wallet=from_addr,
                    target_wallet=r["to_addr"],
                    amount_sol=r["amount"] or 0.0,
                    timestamp=ts,
                    tx_signature=r.get("tx_sig") or "",
                    strength=r.get("strength") or 0.0,
                )
            )

        return FundingTree(
            root_wallet=wallet_address,
            nodes=list(nodes_map.values()),
            edges=edges,
            max_depth=max_d,
        )

    async def find_common_ancestors(
        self, wallet_addresses: list[str], max_depth: int = 3
    ) -> list[CommonAncestor]:
        """Find common funding ancestors between wallets."""
        query = """
        UNWIND $addresses as addr
        MATCH (source:Wallet)-[:FUNDED_BY*1..$depth]->(target:Wallet {address: addr})
        WITH source.address as ancestor, collect(DISTINCT addr) as funded_wallets
        WHERE size(funded_wallets) > 1
        RETURN ancestor, funded_wallets, size(funded_wallets) as count
        ORDER BY count DESC
        """
        results = await self._client.execute_query(
            query, {"addresses": wallet_addresses, "depth": max_depth}
        )
        return [
            CommonAncestor(
                ancestor_address=r["ancestor"],
                wallets_funded=r["funded_wallets"],
                total_descendants=r["count"],
            )
            for r in results
        ]

    # =========================================================================
    # BUYS_WITH Relationships (Synchronized Buying)
    # =========================================================================

    async def create_sync_buy_edge(self, edge: SyncBuyEdge) -> bool:
        """Create a BUYS_WITH relationship for synchronized buying."""
        query = """
        MATCH (a:Wallet {address: $wallet_a})
        MATCH (b:Wallet {address: $wallet_b})
        MERGE (a)-[r:BUYS_WITH]-(b)
        ON CREATE SET
            r.tokens = [$token],
            r.time_deltas = [$delta],
            r.correlation_score = $score,
            r.occurrences = 1,
            r.created_at = datetime()
        ON MATCH SET
            r.tokens = CASE WHEN NOT $token IN r.tokens THEN r.tokens + $token ELSE r.tokens END,
            r.time_deltas = r.time_deltas + $delta,
            r.occurrences = r.occurrences + 1,
            r.correlation_score = (r.correlation_score + $score) / 2,
            r.updated_at = datetime()
        RETURN r
        """
        result = await self._client.execute_query(
            query,
            {
                "wallet_a": edge.wallet_a,
                "wallet_b": edge.wallet_b,
                "token": edge.token_mint,
                "delta": edge.time_delta_seconds,
                "score": edge.correlation_score,
            },
        )
        return len(result) > 0

    async def get_sync_buyers(
        self, wallet_address: str, min_occurrences: int = 2
    ) -> list[SyncBuyEdge]:
        """Get wallets that buy in sync with the given wallet."""
        query = """
        MATCH (a:Wallet {address: $address})-[r:BUYS_WITH]-(b:Wallet)
        WHERE r.occurrences >= $min_occ
        RETURN b.address as other,
               r.tokens[0] as token,
               r.time_deltas[0] as delta,
               r.correlation_score as score,
               r.occurrences as occurrences
        ORDER BY r.occurrences DESC
        """
        results = await self._client.execute_query(
            query, {"address": wallet_address, "min_occ": min_occurrences}
        )
        return [
            SyncBuyEdge(
                wallet_a=wallet_address,
                wallet_b=r["other"],
                token_mint=r.get("token") or "",
                time_delta_seconds=r.get("delta") or 0,
                correlation_score=r.get("score") or 0.0,
                occurrences=r.get("occurrences") or 1,
            )
            for r in results
        ]

    # =========================================================================
    # CO_OCCURS Relationships
    # =========================================================================

    async def create_cooccurrence_edge(self, edge: CoOccurrenceEdge) -> bool:
        """Create a CO_OCCURS relationship."""
        query = """
        MATCH (a:Wallet {address: $wallet_a})
        MATCH (b:Wallet {address: $wallet_b})
        MERGE (a)-[r:CO_OCCURS]-(b)
        ON CREATE SET
            r.shared_tokens = $tokens,
            r.occurrence_count = $count,
            r.jaccard_similarity = $jaccard,
            r.created_at = datetime()
        ON MATCH SET
            r.shared_tokens = [t IN r.shared_tokens WHERE NOT t IN $tokens] + $tokens,
            r.occurrence_count = r.occurrence_count + $count,
            r.jaccard_similarity = $jaccard,
            r.updated_at = datetime()
        RETURN r
        """
        result = await self._client.execute_query(
            query,
            {
                "wallet_a": edge.wallet_a,
                "wallet_b": edge.wallet_b,
                "tokens": edge.shared_tokens,
                "count": edge.occurrence_count,
                "jaccard": edge.jaccard_similarity,
            },
        )
        return len(result) > 0

    async def get_cooccurring_wallets(
        self, wallet_address: str, min_similarity: float = 0.3
    ) -> list[CoOccurrenceEdge]:
        """Get wallets that co-occur with the given wallet."""
        query = """
        MATCH (a:Wallet {address: $address})-[r:CO_OCCURS]-(b:Wallet)
        WHERE r.jaccard_similarity >= $min_sim
        RETURN b.address as other,
               r.shared_tokens as tokens,
               r.occurrence_count as count,
               r.jaccard_similarity as jaccard
        ORDER BY r.jaccard_similarity DESC
        """
        results = await self._client.execute_query(
            query, {"address": wallet_address, "min_sim": min_similarity}
        )
        return [
            CoOccurrenceEdge(
                wallet_a=wallet_address,
                wallet_b=r["other"],
                shared_tokens=r.get("tokens") or [],
                occurrence_count=r.get("count") or 1,
                jaccard_similarity=r.get("jaccard") or 0.0,
            )
            for r in results
        ]

    # =========================================================================
    # Cluster Operations
    # =========================================================================

    async def create_cluster(self, cluster: Cluster) -> bool:
        """Create a cluster node and MEMBER_OF relationships."""
        # Create cluster node
        query = """
        CREATE (c:Cluster {
            id: $id,
            name: $name,
            leader_address: $leader,
            size: $size,
            cohesion_score: $cohesion,
            signal_multiplier: $multiplier,
            created_at: datetime()
        })
        RETURN c
        """
        await self._client.execute_query(
            query,
            {
                "id": cluster.id,
                "name": cluster.name or f"Cluster-{cluster.id[:8]}",
                "leader": cluster.leader_address,
                "size": len(cluster.members),
                "cohesion": cluster.cohesion_score,
                "multiplier": cluster.signal_multiplier,
            },
        )

        # Create MEMBER_OF relationships
        for member in cluster.members:
            member_query = """
            MATCH (w:Wallet {address: $address})
            MATCH (c:Cluster {id: $cluster_id})
            MERGE (w)-[r:MEMBER_OF]->(c)
            SET r.role = $role,
                r.join_reason = $reason,
                r.influence_score = $influence,
                r.joined_at = datetime()
            """
            await self._client.execute_query(
                member_query,
                {
                    "address": member.address,
                    "cluster_id": cluster.id,
                    "role": member.role,
                    "reason": member.join_reason,
                    "influence": member.influence_score,
                },
            )

        return True

    async def get_cluster(self, cluster_id: str) -> Cluster | None:
        """Get a cluster by ID with all members."""
        query = """
        MATCH (c:Cluster {id: $id})
        OPTIONAL MATCH (w:Wallet)-[r:MEMBER_OF]->(c)
        RETURN c, collect({
            address: w.address,
            role: r.role,
            join_reason: r.join_reason,
            influence_score: r.influence_score
        }) as members
        """
        results = await self._client.execute_query(query, {"id": cluster_id})
        if not results:
            return None

        r = results[0]
        c = r["c"]
        members = [
            ClusterMember(
                address=m["address"],
                role=m.get("role") or "member",
                join_reason=m.get("join_reason") or "unknown",
                influence_score=m.get("influence_score") or 0.0,
            )
            for m in r["members"]
            if m.get("address")
        ]

        return Cluster(
            id=c["id"],
            name=c.get("name"),
            leader_address=c.get("leader_address"),
            members=members,
            size=len(members),
            cohesion_score=c.get("cohesion_score") or 0.0,
            signal_multiplier=c.get("signal_multiplier") or 1.0,
        )

    async def get_wallet_clusters(self, wallet_address: str) -> list[Cluster]:
        """Get all clusters a wallet belongs to."""
        query = """
        MATCH (w:Wallet {address: $address})-[r:MEMBER_OF]->(c:Cluster)
        RETURN c.id as cluster_id
        """
        results = await self._client.execute_query(query, {"address": wallet_address})
        clusters = []
        for r in results:
            cluster = await self.get_cluster(r["cluster_id"])
            if cluster:
                clusters.append(cluster)
        return clusters

    async def get_all_clusters(self, limit: int = 50) -> list[Cluster]:
        """Get all clusters."""
        query = """
        MATCH (c:Cluster)
        RETURN c.id as id
        ORDER BY c.size DESC
        LIMIT $limit
        """
        results = await self._client.execute_query(query, {"limit": limit})
        clusters = []
        for r in results:
            cluster = await self.get_cluster(r["id"])
            if cluster:
                clusters.append(cluster)
        return clusters

    async def delete_cluster(self, cluster_id: str) -> bool:
        """Delete a cluster and its relationships."""
        query = """
        MATCH (c:Cluster {id: $id})
        OPTIONAL MATCH ()-[r:MEMBER_OF]->(c)
        DELETE r, c
        """
        await self._client.execute_query(query, {"id": cluster_id})
        return True

    # =========================================================================
    # Cluster Detection Queries
    # =========================================================================

    async def find_connected_wallets(
        self, min_connections: int = 2
    ) -> list[dict[str, Any]]:
        """Find wallets with multiple relationship types."""
        query = """
        MATCH (w:Wallet)
        OPTIONAL MATCH (w)-[f:FUNDED_BY]-()
        OPTIONAL MATCH (w)-[b:BUYS_WITH]-()
        OPTIONAL MATCH (w)-[c:CO_OCCURS]-()
        WITH w,
             count(DISTINCT f) as funding_count,
             count(DISTINCT b) as sync_buy_count,
             count(DISTINCT c) as cooccur_count
        WHERE funding_count + sync_buy_count + cooccur_count >= $min_conn
        RETURN w.address as address,
               funding_count,
               sync_buy_count,
               cooccur_count,
               funding_count + sync_buy_count + cooccur_count as total
        ORDER BY total DESC
        """
        return await self._client.execute_query(query, {"min_conn": min_connections})

    async def find_cluster_candidates(
        self, min_shared_connections: int = 2
    ) -> list[dict[str, Any]]:
        """Find groups of wallets that should be clustered together."""
        query = """
        MATCH (a:Wallet)-[r1]-(b:Wallet)-[r2]-(c:Wallet)
        WHERE a <> c AND type(r1) IN ['FUNDED_BY', 'BUYS_WITH', 'CO_OCCURS']
        AND type(r2) IN ['FUNDED_BY', 'BUYS_WITH', 'CO_OCCURS']
        WITH a, b, c, count(*) as connections
        WHERE connections >= $min_shared
        WITH collect(DISTINCT a.address) as addrs_a,
             collect(DISTINCT b.address) as addrs_b,
             collect(DISTINCT c.address) as addrs_c,
             connections
        RETURN addrs_a + addrs_b + addrs_c as wallets, connections
        ORDER BY connections DESC
        LIMIT 100
        """
        return await self._client.execute_query(query, {"min_shared": min_shared_connections})

    async def calculate_cluster_cohesion(self, wallet_addresses: list[str]) -> float:
        """Calculate cohesion score for a set of wallets."""
        if len(wallet_addresses) < 2:
            return 0.0

        query = """
        UNWIND $addresses as addr1
        UNWIND $addresses as addr2
        WITH addr1, addr2 WHERE addr1 < addr2
        MATCH (a:Wallet {address: addr1}), (b:Wallet {address: addr2})
        OPTIONAL MATCH (a)-[r]-(b) WHERE type(r) IN ['FUNDED_BY', 'BUYS_WITH', 'CO_OCCURS']
        WITH count(DISTINCT [addr1, addr2]) as pairs, count(r) as connections
        RETURN toFloat(connections) / toFloat(pairs) as cohesion
        """
        results = await self._client.execute_query(query, {"addresses": wallet_addresses})
        if results:
            return results[0].get("cohesion") or 0.0
        return 0.0
