"""Cluster leader identification - finds the most influential wallet in clusters."""


import structlog

from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()


class LeaderDetector:
    """Detects cluster leaders based on multiple criteria."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        wallet_repo: WalletRepository,
    ) -> None:
        self._neo4j = neo4j_client
        self._wallet_repo = wallet_repo
        self._queries = ClusterQueries(neo4j_client)

    async def detect_cluster_leader(self, cluster_id: str) -> str | None:
        """
        Detect the leader of a cluster.

        Leader is determined by:
        1. Funding influence (wallets that fund others)
        2. Trading timing (first to buy in sync patterns)
        3. Connection centrality (most connections to other members)
        4. Performance metrics (highest win rate)

        Args:
            cluster_id: ID of cluster to analyze

        Returns:
            Address of the detected leader or None
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster or len(cluster.members) < 2:
            return None

        log.info("detecting_cluster_leader", cluster_id=cluster_id)

        member_addresses = [m.wallet_address for m in cluster.members]

        # Calculate scores for each member
        scores: dict[str, float] = {}
        for address in member_addresses:
            score = await self._calculate_leader_score(address, member_addresses)
            scores[address] = score

        # Find highest scoring member
        if not scores:
            return None

        leader_address = max(scores, key=lambda a: scores[a])
        leader_score = scores[leader_address]

        # Only assign leader if score is above threshold
        if leader_score < 0.3:
            log.info(
                "no_clear_leader",
                cluster_id=cluster_id,
                highest_score=leader_score,
            )
            return None

        # Update cluster with leader
        await self._set_cluster_leader(cluster_id, leader_address)

        log.info(
            "leader_detected",
            cluster_id=cluster_id,
            leader=leader_address[:16],
            score=leader_score,
        )

        return leader_address

    async def _calculate_leader_score(
        self, wallet_address: str, cluster_members: list[str]
    ) -> float:
        """Calculate leadership score for a wallet within its cluster."""
        scores: list[float] = []

        # 1. Funding influence (30% weight)
        funding_score = await self._get_funding_influence_score(
            wallet_address, cluster_members
        )
        scores.append(funding_score * 0.30)

        # 2. Timing leadership (25% weight)
        timing_score = await self._get_timing_leadership_score(
            wallet_address, cluster_members
        )
        scores.append(timing_score * 0.25)

        # 3. Connection centrality (25% weight)
        centrality_score = await self._get_centrality_score(
            wallet_address, cluster_members
        )
        scores.append(centrality_score * 0.25)

        # 4. Performance metrics (20% weight)
        performance_score = await self._get_performance_score(wallet_address)
        scores.append(performance_score * 0.20)

        return sum(scores)

    async def _get_funding_influence_score(
        self, wallet: str, cluster_members: list[str]
    ) -> float:
        """
        Calculate funding influence score.

        Higher score for wallets that fund other cluster members.
        """
        query = """
        MATCH (funder:Wallet {address: $wallet})-[r:FUNDED_BY]->(funded:Wallet)
        WHERE funded.address IN $members AND funded.address <> $wallet
        RETURN count(r) as funded_count, sum(r.amount_sol) as total_funded
        """
        results = await self._neo4j.execute_query(
            query, {"wallet": wallet, "members": cluster_members}
        )

        if not results or not results[0]["funded_count"]:
            # Check if this wallet is a funding source (reverse direction)
            reverse_query = """
            MATCH (funded:Wallet)-[r:FUNDED_BY]->(funder:Wallet {address: $wallet})
            WHERE funded.address IN $members AND funded.address <> $wallet
            RETURN count(r) as funded_count, sum(r.amount_sol) as total_funded
            """
            results = await self._neo4j.execute_query(
                reverse_query, {"wallet": wallet, "members": cluster_members}
            )

        if not results:
            return 0.0

        funded_count = results[0].get("funded_count", 0) or 0
        max_fundable = len(cluster_members) - 1

        return min(1.0, funded_count / max_fundable) if max_fundable > 0 else 0.0

    async def _get_timing_leadership_score(
        self, wallet: str, cluster_members: list[str]
    ) -> float:
        """
        Calculate timing leadership score.

        Higher score for wallets that buy first in sync patterns.
        """
        query = """
        MATCH (w:Wallet {address: $wallet})-[r:BUYS_WITH]-(other:Wallet)
        WHERE other.address IN $members
        WITH r.time_delta_seconds as delta,
             CASE WHEN r.wallet_a = $wallet THEN 1 ELSE -1 END as direction
        RETURN count(*) as sync_count,
               sum(CASE WHEN delta * direction < 0 THEN 1 ELSE 0 END) as first_count
        """
        results = await self._neo4j.execute_query(
            query, {"wallet": wallet, "members": cluster_members}
        )

        if not results or results[0]["sync_count"] == 0:
            return 0.0

        sync_count = results[0]["sync_count"]
        first_count = results[0].get("first_count", 0) or 0

        return first_count / sync_count if sync_count > 0 else 0.0

    async def _get_centrality_score(
        self, wallet: str, cluster_members: list[str]
    ) -> float:
        """
        Calculate connection centrality score.

        Higher score for wallets connected to more cluster members.
        """
        query = """
        MATCH (w:Wallet {address: $wallet})-[r:FUNDED_BY|BUYS_WITH|CO_OCCURS]-(other:Wallet)
        WHERE other.address IN $members AND other.address <> $wallet
        RETURN count(DISTINCT other) as connected_count
        """
        results = await self._neo4j.execute_query(
            query, {"wallet": wallet, "members": cluster_members}
        )

        if not results:
            return 0.0

        connected = results[0].get("connected_count", 0) or 0
        max_connections = len(cluster_members) - 1

        return connected / max_connections if max_connections > 0 else 0.0

    async def _get_performance_score(self, wallet: str) -> float:
        """
        Calculate performance score based on wallet metrics.

        Uses win rate and ROI from wallet record.
        """
        wallet_data = await self._wallet_repo.get_by_address(wallet)
        if not wallet_data:
            return 0.0

        # win_rate is already 0-1
        win_rate = wallet_data.profile.win_rate or 0.0

        # Use total_pnl as performance indicator (cap at $10k for scoring)
        pnl = wallet_data.profile.total_pnl or 0.0
        pnl_score = min(1.0, max(0.0, pnl / 10000.0))

        # Combined score (weighted average)
        return (win_rate * 0.6) + (pnl_score * 0.4)

    async def _set_cluster_leader(self, cluster_id: str, leader_address: str) -> None:
        """Update cluster with leader address."""
        query = """
        MATCH (c:Cluster {id: $cluster_id})
        SET c.leader_address = $leader_address
        """
        await self._neo4j.execute_query(
            query, {"cluster_id": cluster_id, "leader_address": leader_address}
        )

    async def detect_all_cluster_leaders(self) -> dict[str, str | None]:
        """
        Detect leaders for all clusters.

        Returns:
            Dict mapping cluster_id to leader_address (or None)
        """
        clusters = await self._queries.get_all_clusters()
        results: dict[str, str | None] = {}

        for cluster in clusters:
            leader = await self.detect_cluster_leader(cluster.id)
            results[cluster.id] = leader

        log.info(
            "all_leaders_detected",
            cluster_count=len(clusters),
            with_leader=sum(1 for v in results.values() if v),
        )

        return results

    async def get_leader_followers(
        self, leader_address: str
    ) -> list[tuple[str, float]]:
        """
        Get wallets that follow a leader.

        Returns list of (wallet_address, follow_strength) tuples.
        """
        query = """
        MATCH (leader:Wallet {address: $leader})-[:FUNDED_BY|BUYS_WITH|CO_OCCURS]-(follower:Wallet)
        WITH follower, count(*) as connection_strength
        RETURN follower.address as address, connection_strength
        ORDER BY connection_strength DESC
        """
        results = await self._neo4j.execute_query(query, {"leader": leader_address})

        # Normalize strengths
        max_strength = max((r["connection_strength"] for r in results), default=1)

        return [
            (r["address"], r["connection_strength"] / max_strength)
            for r in results
        ]

    async def rank_cluster_members(
        self, cluster_id: str
    ) -> list[tuple[str, float]]:
        """
        Rank all cluster members by their leadership score.

        Returns:
            List of (address, score) tuples sorted by score descending
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            return []

        member_addresses = [m.wallet_address for m in cluster.members]
        scores: list[tuple[str, float]] = []

        for address in member_addresses:
            score = await self._calculate_leader_score(address, member_addresses)
            scores.append((address, score))

        return sorted(scores, key=lambda x: x[1], reverse=True)
