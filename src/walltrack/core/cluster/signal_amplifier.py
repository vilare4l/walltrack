"""Cluster signal amplification - amplifies signals from clustered wallets."""


import structlog

from walltrack.data.models.cluster import Cluster, ClusterSignal
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.cluster import ClusterQueries
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository

log = structlog.get_logger()

# Signal multiplier bounds
MIN_MULTIPLIER = 1.0
MAX_MULTIPLIER = 3.0

# Thresholds for signal amplification
COHESION_THRESHOLD = 0.3  # Minimum cohesion for amplification
MIN_CLUSTER_SIZE = 3


class SignalAmplifier:
    """Amplifies trading signals based on cluster participation."""

    def __init__(
        self,
        neo4j_client: Neo4jClient,
        wallet_repo: WalletRepository,
    ) -> None:
        self._neo4j = neo4j_client
        self._wallet_repo = wallet_repo
        self._queries = ClusterQueries(neo4j_client)

    async def calculate_cluster_multiplier(self, cluster_id: str) -> float:
        """
        Calculate signal multiplier for a cluster.

        Multiplier is based on:
        1. Cluster size (more members = stronger signal)
        2. Cohesion score (tighter clusters = stronger signal)
        3. Member performance (better performers = stronger signal)
        4. Leader presence (having a clear leader = stronger signal)

        Returns:
            Multiplier between 1.0 and 3.0
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            return MIN_MULTIPLIER

        # Base multiplier
        multiplier = MIN_MULTIPLIER

        # 1. Size factor (max +0.5 for 10+ members)
        size_bonus = min(0.5, (cluster.size - MIN_CLUSTER_SIZE) * 0.1)
        if cluster.size >= MIN_CLUSTER_SIZE:
            multiplier += size_bonus

        # 2. Cohesion factor (max +0.8 for high cohesion)
        if cluster.cohesion_score >= COHESION_THRESHOLD:
            cohesion_bonus = cluster.cohesion_score * 0.8
            multiplier += cohesion_bonus

        # 3. Performance factor (max +0.5 for high-performing members)
        perf_bonus = await self._calculate_performance_bonus(cluster)
        multiplier += perf_bonus

        # 4. Leader factor (max +0.2 for clear leader)
        if cluster.leader_address:
            multiplier += 0.2

        # Clamp to bounds
        return min(MAX_MULTIPLIER, max(MIN_MULTIPLIER, multiplier))

    async def _calculate_performance_bonus(self, cluster: Cluster) -> float:
        """Calculate bonus based on member performance."""
        if not cluster.members:
            return 0.0

        win_rates: list[float] = []
        for member in cluster.members[:10]:  # Sample top 10 members
            wallet = await self._wallet_repo.get_by_address(member.wallet_address)
            if wallet and wallet.profile.win_rate is not None:
                win_rates.append(wallet.profile.win_rate)

        if not win_rates:
            return 0.0

        avg_win_rate = sum(win_rates) / len(win_rates)
        # Bonus scales from 0 (50% WR) to 0.5 (100% WR)
        # Note: win_rate is already 0-1, so 0.5 = 50%
        return max(0.0, (avg_win_rate - 0.5) * 1.0)

    async def update_cluster_multipliers(self) -> dict[str, float]:
        """
        Update signal multipliers for all clusters.

        Returns:
            Dict mapping cluster_id to new multiplier
        """
        clusters = await self._queries.get_all_clusters()
        results: dict[str, float] = {}

        for cluster in clusters:
            multiplier = await self.calculate_cluster_multiplier(cluster.id)
            await self._set_cluster_multiplier(cluster.id, multiplier)
            results[cluster.id] = multiplier

        log.info(
            "multipliers_updated",
            cluster_count=len(clusters),
            avg_multiplier=sum(results.values()) / len(results) if results else 0,
        )

        return results

    async def _set_cluster_multiplier(
        self, cluster_id: str, multiplier: float
    ) -> None:
        """Update cluster signal multiplier in Neo4j."""
        query = """
        MATCH (c:Cluster {id: $cluster_id})
        SET c.signal_multiplier = $multiplier
        """
        await self._neo4j.execute_query(
            query, {"cluster_id": cluster_id, "multiplier": multiplier}
        )

    async def get_amplified_signal(
        self,
        wallet_address: str,
        token_mint: str,
        base_signal: float,
    ) -> ClusterSignal:
        """
        Get amplified signal for a wallet's activity on a token.

        Args:
            wallet_address: The wallet generating the signal
            token_mint: The token being traded
            base_signal: The base signal strength (0-1)

        Returns:
            ClusterSignal with amplified strength and context
        """
        # Get wallet's clusters
        wallet_clusters = await self._get_wallet_clusters(wallet_address)

        if not wallet_clusters:
            return ClusterSignal(
                wallet_address=wallet_address,
                token_mint=token_mint,
                base_strength=base_signal,
                amplified_strength=base_signal,
                cluster_id=None,
                participating_wallets=[wallet_address],
                amplification_reason="no_cluster",
            )

        # Use the cluster with highest multiplier
        best_cluster = max(wallet_clusters, key=lambda c: c.signal_multiplier)
        multiplier = best_cluster.signal_multiplier

        # Check if other cluster members are also active on this token
        active_members = await self._find_active_cluster_members(
            best_cluster.id, token_mint
        )

        # Additional boost if multiple members are active
        if len(active_members) > 1:
            member_boost = min(0.5, len(active_members) * 0.1)
            multiplier = min(MAX_MULTIPLIER, multiplier + member_boost)

        amplified = min(1.0, base_signal * multiplier)

        reason = self._get_amplification_reason(
            best_cluster, len(active_members), multiplier
        )

        return ClusterSignal(
            wallet_address=wallet_address,
            token_mint=token_mint,
            base_strength=base_signal,
            amplified_strength=amplified,
            cluster_id=best_cluster.id,
            participating_wallets=active_members,
            amplification_reason=reason,
        )

    async def _get_wallet_clusters(self, wallet_address: str) -> list[Cluster]:
        """Get all clusters containing this wallet."""
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

    async def _find_active_cluster_members(
        self, cluster_id: str, token_mint: str
    ) -> list[str]:
        """Find cluster members who have recently traded a token."""
        # Get cluster members
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            return []

        active: list[str] = []
        for member in cluster.members:
            # Check if member has this token in discovery_tokens
            wallet = await self._wallet_repo.get_by_address(member.wallet_address)
            if wallet and token_mint in (wallet.discovery_tokens or []):
                active.append(member.wallet_address)

        return active

    def _get_amplification_reason(
        self, cluster: Cluster, active_count: int, multiplier: float
    ) -> str:
        """Generate human-readable amplification reason."""
        reasons: list[str] = []

        if cluster.size >= 5:
            reasons.append(f"large_cluster({cluster.size})")
        if cluster.cohesion_score >= 0.5:
            reasons.append(f"high_cohesion({cluster.cohesion_score:.2f})")
        if cluster.leader_address:
            reasons.append("has_leader")
        if active_count > 1:
            reasons.append(f"active_members({active_count})")

        return ",".join(reasons) if reasons else f"base_cluster_multiplier({multiplier:.2f})"

    async def detect_cluster_convergence(
        self, token_mint: str, min_cluster_wallets: int = 3
    ) -> list[ClusterSignal]:
        """
        Detect when multiple cluster members converge on a token.

        This is a strong signal - multiple coordinated wallets
        showing interest in the same token.

        Args:
            token_mint: Token to check
            min_cluster_wallets: Minimum cluster wallets needed for convergence

        Returns:
            List of ClusterSignals for detected convergences
        """
        # Get all active wallets and filter by token
        all_wallets = await self._wallet_repo.get_active_wallets(limit=500)
        token_wallets = [
            w.address for w in all_wallets
            if token_mint in (w.discovery_tokens or [])
        ]

        if len(token_wallets) < min_cluster_wallets:
            return []

        # Group by cluster
        cluster_wallets: dict[str, list[str]] = {}
        for address in token_wallets:
            clusters = await self._get_wallet_clusters(address)
            for cluster in clusters:
                if cluster.id not in cluster_wallets:
                    cluster_wallets[cluster.id] = []
                cluster_wallets[cluster.id].append(address)

        # Generate signals for clusters with enough convergence
        signals: list[ClusterSignal] = []
        for cluster_id, addresses in cluster_wallets.items():
            if len(addresses) >= min_cluster_wallets:
                target_cluster = await self._queries.get_cluster(cluster_id)
                if not target_cluster:
                    continue

                # Calculate convergence strength
                convergence_ratio = len(addresses) / target_cluster.size
                base_signal = min(1.0, convergence_ratio * 2)  # 50% participation = 1.0
                amplified = await self.get_amplified_signal(
                    addresses[0], token_mint, base_signal
                )
                amplified.participating_wallets = addresses
                reason = f"cluster_convergence({len(addresses)}/{target_cluster.size})"
                amplified.amplification_reason = reason
                signals.append(amplified)

        log.info(
            "convergence_detected",
            token=token_mint[:16],
            cluster_signals=len(signals),
        )

        return signals

    async def get_cluster_activity_score(
        self, cluster_id: str, hours: int = 24  # noqa: ARG002
    ) -> float:
        """
        Calculate recent activity score for a cluster.

        Returns a score 0-1 based on recent trading activity.
        """
        cluster = await self._queries.get_cluster(cluster_id)
        if not cluster:
            return 0.0

        # Count recently active members
        # This would ideally check transaction timestamps
        # For now, use a simpler heuristic based on discovery_tokens count
        active_count = 0
        for member in cluster.members:
            wallet = await self._wallet_repo.get_by_address(member.wallet_address)
            if wallet and len(wallet.discovery_tokens or []) > 0:
                active_count += 1

        return active_count / cluster.size if cluster.size > 0 else 0.0
