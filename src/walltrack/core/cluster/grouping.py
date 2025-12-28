"""Cluster grouping algorithm - forms clusters from related wallets."""

from uuid import uuid4

import structlog

from walltrack.data.models.cluster import (
    Cluster,
    ClusterMember,
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries

log = structlog.get_logger()

# Minimum edges required to form a cluster
MIN_CLUSTER_EDGES = 2
MIN_CLUSTER_SIZE = 3


class ClusterGrouper:
    """Groups related wallets into clusters based on graph relationships."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        min_cluster_size: int = MIN_CLUSTER_SIZE,
        min_edges: int = MIN_CLUSTER_EDGES,
    ) -> None:
        self._neo4j = neo4j_client
        self._queries = ClusterQueries(neo4j_client)
        self._min_cluster_size = min_cluster_size
        self._min_edges = min_edges

    async def find_clusters(self) -> list[Cluster]:
        """
        Find all clusters in the graph using connected component analysis.

        Uses a combination of FUNDED_BY, BUYS_WITH, and CO_OCCURS relationships
        to identify related wallet groups.

        Returns:
            List of detected clusters
        """
        log.info("finding_clusters")

        # Get cluster candidates - groups of related wallets
        candidates = await self._queries.find_cluster_candidates(
            min_shared_connections=self._min_edges
        )

        clusters: list[Cluster] = []
        processed_wallets: set[str] = set()

        # Group candidates by their connection patterns
        for candidate in candidates:
            wallet_address = candidate.get("address", "")
            if not wallet_address or wallet_address in processed_wallets:
                continue

            # Find all wallets connected to this one using direct query
            connected = await self._find_connected_wallets_for(wallet_address)

            # Filter to wallets not already in a cluster
            cluster_wallets = [
                w for w in connected if w not in processed_wallets
            ]

            if len(cluster_wallets) >= self._min_cluster_size:
                cluster = await self._create_cluster(cluster_wallets)
                if cluster:
                    clusters.append(cluster)
                    processed_wallets.update(cluster_wallets)

        log.info("clusters_found", count=len(clusters))
        return clusters

    async def _find_connected_wallets_for(
        self, wallet_address: str, max_depth: int = 3  # noqa: ARG002
    ) -> list[str]:
        """Find all wallets connected to a specific wallet."""
        query = """
        MATCH (start:Wallet {address: $address})
        MATCH path = (start)-[:FUNDED_BY|BUYS_WITH|CO_OCCURS*1..3]-(connected:Wallet)
        WHERE connected <> start
        RETURN DISTINCT connected.address as address
        LIMIT 100
        """
        results = await self._neo4j.execute_query(
            query, {"address": wallet_address}
        )
        return [r["address"] for r in results if r.get("address")]

    async def _create_cluster(self, wallet_addresses: list[str]) -> Cluster | None:
        """Create a cluster from a set of wallet addresses."""
        if len(wallet_addresses) < self._min_cluster_size:
            return None

        cluster_id = str(uuid4())

        # Calculate cohesion score
        cohesion = await self._queries.calculate_cluster_cohesion(wallet_addresses)

        # Build member list with connection counts
        members: list[ClusterMember] = []
        for address in wallet_addresses:
            edge_count = await self._get_wallet_edge_count(address, wallet_addresses)
            members.append(
                ClusterMember(
                    wallet_address=address,
                    join_reason="graph_analysis",
                    connection_count=edge_count,
                )
            )

        # Sort by connection count (leader candidates at top)
        members.sort(key=lambda m: m.connection_count, reverse=True)

        cluster = Cluster(
            id=cluster_id,
            name=None,
            members=members,
            leader_address=None,  # Will be set by LeaderDetector
            size=len(members),
            cohesion_score=cohesion,
            signal_multiplier=1.0,  # Will be set by SignalAmplifier
        )

        # Store in Neo4j
        await self._queries.create_cluster(cluster)

        log.info(
            "cluster_created",
            cluster_id=cluster_id,
            size=len(members),
            cohesion=cohesion,
        )

        return cluster

    async def _get_wallet_edge_count(
        self, wallet: str, cluster_wallets: list[str]
    ) -> int:
        """Count edges from wallet to other cluster members."""
        query = """
        MATCH (w:Wallet {address: $wallet})
        MATCH (w)-[r:FUNDED_BY|BUYS_WITH|CO_OCCURS]-(other:Wallet)
        WHERE other.address IN $cluster_wallets AND other.address <> $wallet
        RETURN count(DISTINCT r) as edge_count
        """
        results = await self._neo4j.execute_query(
            query, {"wallet": wallet, "cluster_wallets": cluster_wallets}
        )
        return results[0]["edge_count"] if results else 0

    async def expand_cluster(
        self, cluster_id: str, max_new_members: int = 10
    ) -> list[str]:
        """
        Find wallets that could be added to an existing cluster.

        Args:
            cluster_id: ID of cluster to expand
            max_new_members: Maximum new members to add

        Returns:
            List of newly added wallet addresses
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            return []

        existing_addresses = {m.wallet_address for m in cluster.members}

        # Find wallets connected to cluster members but not in cluster
        query = """
        MATCH (m:Wallet)-[:MEMBER_OF]->(c:Cluster {id: $cluster_id})
        MATCH (m)-[r:FUNDED_BY|BUYS_WITH|CO_OCCURS]-(candidate:Wallet)
        WHERE NOT (candidate)-[:MEMBER_OF]->(c)
        WITH candidate, count(DISTINCT r) as connections
        WHERE connections >= $min_connections
        RETURN candidate.address as address, connections
        ORDER BY connections DESC
        LIMIT $limit
        """
        results = await self._neo4j.execute_query(
            query,
            {
                "cluster_id": cluster_id,
                "min_connections": self._min_edges,
                "limit": max_new_members,
            },
        )

        added: list[str] = []
        for result in results:
            address = result["address"]
            if address not in existing_addresses:
                # Add to cluster
                member = ClusterMember(
                    wallet_address=address,
                    join_reason="cluster_expansion",
                    connection_count=result["connections"],
                )
                await self._add_member_to_cluster(cluster_id, member)
                added.append(address)

        if added:
            # Recalculate cohesion
            all_addresses = list(existing_addresses) + added
            new_cohesion = await self._queries.calculate_cluster_cohesion(all_addresses)
            await self._update_cluster_cohesion(cluster_id, new_cohesion)

        return added

    async def _add_member_to_cluster(
        self, cluster_id: str, member: ClusterMember
    ) -> None:
        """Add a member to a cluster in Neo4j."""
        query = """
        MATCH (c:Cluster {id: $cluster_id})
        MATCH (w:Wallet {address: $address})
        MERGE (w)-[r:MEMBER_OF]->(c)
        SET r.join_reason = $join_reason,
            r.connection_count = $connection_count,
            c.size = c.size + 1
        """
        await self._neo4j.execute_query(
            query,
            {
                "cluster_id": cluster_id,
                "address": member.wallet_address,
                "join_reason": member.join_reason,
                "connection_count": member.connection_count,
            },
        )

    async def _update_cluster_cohesion(
        self, cluster_id: str, cohesion: float
    ) -> None:
        """Update cluster cohesion score."""
        query = """
        MATCH (c:Cluster {id: $cluster_id})
        SET c.cohesion_score = $cohesion
        """
        await self._neo4j.execute_query(
            query, {"cluster_id": cluster_id, "cohesion": cohesion}
        )

    async def merge_clusters(
        self, cluster_ids: list[str], new_name: str | None = None
    ) -> Cluster | None:
        """
        Merge multiple clusters into one.

        Args:
            cluster_ids: IDs of clusters to merge
            new_name: Optional name for the merged cluster

        Returns:
            The merged cluster or None if merge failed
        """
        if len(cluster_ids) < 2:
            return None

        # Collect all members from all clusters
        all_members: list[ClusterMember] = []
        for cid in cluster_ids:
            cluster = await self._queries.get_cluster(cid)
            if cluster:
                all_members.extend(cluster.members)

        if not all_members:
            return None

        # Deduplicate members
        seen: set[str] = set()
        unique_members: list[ClusterMember] = []
        for member in all_members:
            if member.wallet_address not in seen:
                seen.add(member.wallet_address)
                unique_members.append(member)

        # Create new merged cluster
        addresses = [m.wallet_address for m in unique_members]
        cohesion = await self._queries.calculate_cluster_cohesion(addresses)

        merged = Cluster(
            id=str(uuid4()),
            name=new_name,
            members=unique_members,
            leader_address=None,
            size=len(unique_members),
            cohesion_score=cohesion,
            signal_multiplier=1.0,
        )

        # Store merged cluster
        await self._queries.create_cluster(merged)

        # Delete old clusters
        for cid in cluster_ids:
            await self._delete_cluster(cid)

        log.info(
            "clusters_merged",
            original_count=len(cluster_ids),
            new_cluster_id=merged.id,
            member_count=len(unique_members),
        )

        return merged

    async def _delete_cluster(self, cluster_id: str) -> None:
        """Delete a cluster from Neo4j."""
        query = """
        MATCH (c:Cluster {id: $cluster_id})
        DETACH DELETE c
        """
        await self._neo4j.execute_query(query, {"cluster_id": cluster_id})

    async def get_wallet_clusters(self, wallet_address: str) -> list[Cluster]:
        """Get all clusters a wallet belongs to."""
        query = """
        MATCH (w:Wallet {address: $address})-[:MEMBER_OF]->(c:Cluster)
        RETURN c.id as cluster_id
        """
        results = await self._neo4j.execute_query(query, {"address": wallet_address})

        clusters: list[Cluster] = []
        for result in results:
            cluster = await self._queries.get_cluster(result["cluster_id"])
            if cluster:
                clusters.append(cluster)

        return clusters

    async def create_cluster_from_members(
        self, member_addresses: list[str]
    ) -> str | None:
        """
        Create a new cluster from a list of wallet addresses.

        Used by NetworkOnboarder for automatic cluster formation.

        Args:
            member_addresses: List of wallet addresses to form cluster

        Returns:
            New cluster ID or None if creation failed
        """
        if len(member_addresses) < self._min_cluster_size:
            log.debug(
                "not_enough_members_for_cluster",
                count=len(member_addresses),
                min_required=self._min_cluster_size,
            )
            return None

        cluster = await self._create_cluster(member_addresses)
        return cluster.id if cluster else None

    async def add_members_to_cluster(
        self, cluster_id: str, addresses: list[str]
    ) -> int:
        """
        Add members to an existing cluster.

        Used by NetworkOnboarder when merging into existing cluster.

        Args:
            cluster_id: ID of cluster to add to
            addresses: Wallet addresses to add

        Returns:
            Number of members added
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            log.warning("cluster_not_found", cluster_id=cluster_id)
            return 0

        existing = {m.wallet_address for m in cluster.members}
        added = 0

        for address in addresses:
            if address not in existing:
                edge_count = await self._get_wallet_edge_count(address, addresses)
                member = ClusterMember(
                    wallet_address=address,
                    join_reason="network_onboarding",
                    connection_count=edge_count,
                )
                await self._add_member_to_cluster(cluster_id, member)
                added += 1

        if added > 0:
            # Recalculate cohesion
            all_addresses = list(existing) + [
                a for a in addresses if a not in existing
            ]
            new_cohesion = await self._queries.calculate_cluster_cohesion(all_addresses)
            await self._update_cluster_cohesion(cluster_id, new_cohesion)

            log.info(
                "members_added_to_cluster",
                cluster_id=cluster_id,
                added=added,
                new_cohesion=new_cohesion,
            )

        return added
