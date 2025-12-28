"""Automatic network discovery and cluster formation.

Epic 14 Story 14-4: Automatic Network Onboarding
- Called after wallet profiling to auto-discover network
- Forms clusters when >= 3 qualified wallets connected
- Stores cluster membership in Neo4j (not WalletCache)

Epic 14 Story 14-5: Cluster data now in Neo4j only
- WalletCache no longer stores cluster_id/is_leader
- Use ClusterService to fetch cluster info at scoring time
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from walltrack.core.cluster.funding_analyzer import FundingAnalyzer
    from walltrack.core.cluster.grouping import ClusterGrouper
    from walltrack.core.cluster.leader_detection import LeaderDetector
    from walltrack.core.cluster.signal_amplifier import SignalAmplifier
    from walltrack.core.cluster.sync_detector import SyncBuyDetector
    from walltrack.data.neo4j.client import Neo4jClient
    from walltrack.services.signal.wallet_cache import WalletCache

logger = structlog.get_logger(__name__)


@dataclass
class OnboardingConfig:
    """Configuration for network onboarding."""

    max_depth: int = 1
    min_quick_score: float = 0.4
    min_cluster_size: int = 3
    max_network_size: int = 20
    sync_window_seconds: int = 300  # 5 minutes


@dataclass
class OnboardingResult:
    """Result of network onboarding."""

    wallet_address: str
    funding_edges_created: int = 0
    sync_buy_edges_created: int = 0
    network_wallets_found: int = 0
    cluster_formed: bool = False
    cluster_id: str | None = None
    cluster_size: int = 0
    leader_address: str | None = None


@dataclass
class _ClusterFormationResult:
    """Internal result for cluster formation."""

    formed: bool = False
    cluster_id: str | None = None
    size: int = 0
    leader: str | None = None


class NetworkOnboarder:
    """
    Automatic network discovery and cluster formation.

    Called after wallet profiling to:
    1. Analyze funding relationships (reuses tx_history)
    2. Detect synchronized buying patterns
    3. Discover connected network (1-hop)
    4. Auto-form clusters when >= 3 qualified wallets
    5. Detect leaders and calculate multipliers
    6. Update WalletCache with cluster data
    """

    def __init__(
        self,
        neo4j: Neo4jClient,
        wallet_cache: WalletCache,
        funding_analyzer: FundingAnalyzer,
        sync_detector: SyncBuyDetector,
        cluster_grouper: ClusterGrouper,
        leader_detector: LeaderDetector,
        signal_amplifier: SignalAmplifier,
        config: OnboardingConfig | None = None,
    ) -> None:
        """Initialize network onboarder.

        Args:
            neo4j: Neo4j client for graph queries
            wallet_cache: Wallet cache for cluster updates
            funding_analyzer: Funding relationship analyzer
            sync_detector: Synchronized buy detector
            cluster_grouper: Cluster formation service
            leader_detector: Leader detection service
            signal_amplifier: Signal amplification service
            config: Onboarding configuration
        """
        self._neo4j = neo4j
        self._wallet_cache = wallet_cache
        self._funding_analyzer = funding_analyzer
        self._sync_detector = sync_detector
        self._cluster_grouper = cluster_grouper
        self._leader_detector = leader_detector
        self._signal_amplifier = signal_amplifier
        self._config = config or OnboardingConfig()
        self._processed: set[str] = set()

    async def onboard_wallet(
        self,
        address: str,
        tx_history: list[dict[str, Any]],
        depth: int = 0,
    ) -> OnboardingResult:
        """
        Onboard a wallet into the network.

        Args:
            address: Wallet address to onboard
            tx_history: Transaction history (reused from profiling)
            depth: Current recursion depth (0 = initial wallet)

        Returns:
            OnboardingResult with edges created and cluster info
        """
        if address in self._processed:
            logger.debug("wallet_already_processed", wallet=address[:8])
            return OnboardingResult(wallet_address=address)

        self._processed.add(address)
        logger.info(
            "onboarding_wallet",
            wallet=address[:8],
            depth=depth,
            tx_count=len(tx_history),
        )

        # Step 1: Analyze Funding (reuse tx_history)
        funding_edges = await self._analyze_funding(address, tx_history)

        # Step 2: Analyze Sync Buys (for recent tokens in tx_history)
        sync_edges = await self._analyze_sync_buys(address, tx_history)

        # Step 3: Discover Network (1-hop)
        network_wallets = await self._discover_network(address)

        # Step 4: Quick-score and filter network wallets
        qualified_wallets = await self._filter_qualified(network_wallets, address)

        # Step 5: Recurse if depth allows (for already-profiled wallets only)
        if depth < self._config.max_depth:
            for wallet_addr in qualified_wallets[: self._config.max_network_size]:
                if wallet_addr not in self._processed:
                    await self._maybe_recurse(wallet_addr, depth + 1)

        # Step 6: Auto-form cluster if enough qualified wallets
        cluster_result = await self._maybe_form_cluster(address, qualified_wallets)

        logger.info(
            "wallet_onboarded",
            wallet=address[:8],
            funding_edges=funding_edges,
            sync_edges=sync_edges,
            network_found=len(network_wallets),
            cluster_formed=cluster_result.formed,
        )

        return OnboardingResult(
            wallet_address=address,
            funding_edges_created=funding_edges,
            sync_buy_edges_created=sync_edges,
            network_wallets_found=len(network_wallets),
            cluster_formed=cluster_result.formed,
            cluster_id=cluster_result.cluster_id,
            cluster_size=cluster_result.size,
            leader_address=cluster_result.leader,
        )

    async def _analyze_funding(
        self, address: str, tx_history: list[dict[str, Any]]
    ) -> int:
        """Analyze funding relationships from tx_history.

        Args:
            address: Wallet address being analyzed
            tx_history: Transaction history to analyze

        Returns:
            Number of funding edges created
        """
        try:
            # FundingAnalyzer now accepts tx_history to avoid duplicate API call
            edges = await self._funding_analyzer.analyze_wallet_funding(
                address, tx_history=tx_history
            )
            return len(edges)
        except Exception as e:
            logger.warning(
                "funding_analysis_failed",
                wallet=address[:8],
                error=str(e),
            )
            return 0

    async def _analyze_sync_buys(
        self, address: str, tx_history: list[dict[str, Any]]
    ) -> int:
        """Detect synchronized buying patterns.

        Args:
            address: Wallet address being analyzed
            tx_history: Transaction history to extract tokens from

        Returns:
            Number of sync buy edges created
        """
        # Extract recent token addresses from tx_history
        recent_tokens = self._extract_recent_tokens(tx_history)

        if not recent_tokens:
            return 0

        edges_created = 0
        # Limit to 5 recent tokens to avoid API overload
        for token_address in recent_tokens[:5]:
            try:
                # For sync detection, we need other wallets that traded this token
                # The detector will find them in Neo4j
                edges = await self._sync_detector.detect_sync_buys_for_token(
                    token_address, wallet_addresses=[address]
                )
                edges_created += len(edges)
            except Exception as e:
                logger.debug(
                    "sync_detection_failed",
                    token=token_address[:8],
                    error=str(e),
                )

        return edges_created

    def _extract_recent_tokens(self, tx_history: list[dict[str, Any]]) -> list[str]:
        """Extract unique token addresses from recent transactions.

        Args:
            tx_history: Transaction history

        Returns:
            List of unique token addresses
        """
        tokens: set[str] = set()
        for tx in tx_history[:50]:  # Last 50 transactions
            # Check for token transfers
            for transfer in tx.get("tokenTransfers", []):
                mint = transfer.get("mint")
                if mint:
                    tokens.add(mint)
            # Check for swap type
            if tx.get("type") == "SWAP":
                token = tx.get("token_address") or tx.get("tokenMint")
                if token:
                    tokens.add(token)
        return list(tokens)

    async def _discover_network(self, address: str) -> list[str]:
        """Discover connected wallets via 1-hop query.

        Args:
            address: Wallet address to find connections for

        Returns:
            List of connected wallet addresses
        """
        query = """
        MATCH (w:Wallet {address: $address})-[:FUNDED_BY|BUYS_WITH|CO_OCCURS]-(connected:Wallet)
        WHERE connected.address <> $address
        RETURN DISTINCT connected.address as address
        LIMIT $limit
        """
        try:
            results = await self._neo4j.execute_query(
                query,
                {"address": address, "limit": self._config.max_network_size},
            )
            return [r["address"] for r in results if r.get("address")]
        except Exception as e:
            logger.warning(
                "network_discovery_failed",
                wallet=address[:8],
                error=str(e),
            )
            return []

    async def _filter_qualified(
        self, addresses: list[str], exclude: str
    ) -> list[str]:
        """Filter wallets by quick score.

        Args:
            addresses: Wallet addresses to filter
            exclude: Address to exclude from results

        Returns:
            List of qualified wallet addresses
        """
        qualified = []
        for addr in addresses:
            if addr == exclude:
                continue
            score = await self._quick_score(addr)
            if score >= self._config.min_quick_score:
                qualified.append(addr)
        return qualified

    async def _quick_score(self, address: str) -> float:
        """Quick scoring using Neo4j data only.

        Args:
            address: Wallet address to score

        Returns:
            Quick score between 0.0 and 1.0
        """
        query = """
        MATCH (w:Wallet {address: $address})
        RETURN w.tx_count as tx_count, w.win_rate as win_rate
        """
        try:
            results = await self._neo4j.execute_query(query, {"address": address})
            if not results:
                return 0.0

            data = results[0]
            tx_count = data.get("tx_count") or 0
            win_rate = data.get("win_rate") or 0

            # Simple score: tx_count normalized + win_rate
            tx_score = min(1.0, tx_count / 100)
            return (tx_score * 0.3) + (win_rate * 0.7)
        except Exception:
            return 0.0

    async def _maybe_recurse(self, address: str, depth: int) -> None:
        """Recurse for already-profiled wallets.

        Args:
            address: Wallet address to potentially recurse into
            depth: Current recursion depth
        """
        # Only recurse for wallets already in our system
        cached, _ = await self._wallet_cache.get(address)
        if cached and cached.is_monitored:
            # Already profiled, recurse without tx_history
            await self.onboard_wallet(address, tx_history=[], depth=depth)

    async def _maybe_form_cluster(
        self, address: str, qualified: list[str]
    ) -> _ClusterFormationResult:
        """Form cluster if enough qualified wallets.

        Args:
            address: Root wallet address
            qualified: List of qualified connected wallets

        Returns:
            Cluster formation result
        """
        all_members = [address] + qualified

        if len(all_members) < self._config.min_cluster_size:
            logger.debug(
                "not_enough_for_cluster",
                count=len(all_members),
                min_required=self._config.min_cluster_size,
            )
            return _ClusterFormationResult()

        # Check for existing cluster overlap
        existing_cluster = await self._find_existing_cluster(all_members)

        cluster_id: str | None = None

        if existing_cluster:
            # Merge into existing cluster
            cluster_id = existing_cluster
            await self._cluster_grouper.add_members_to_cluster(cluster_id, all_members)
            logger.info(
                "members_merged_to_cluster",
                cluster_id=cluster_id[:8],
                member_count=len(all_members),
            )
        else:
            # Create new cluster
            cluster_id = await self._cluster_grouper.create_cluster_from_members(
                all_members
            )
            logger.info(
                "new_cluster_created",
                cluster_id=cluster_id[:8] if cluster_id else "none",
                member_count=len(all_members),
            )

        if not cluster_id:
            return _ClusterFormationResult()

        # Detect leader
        leader = await self._leader_detector.detect_cluster_leader(cluster_id)

        # Calculate multiplier
        await self._signal_amplifier.calculate_cluster_multiplier(cluster_id)

        # Epic 14 Story 14-5: Cluster membership stored in Neo4j only.
        # ClusterService fetches cluster info at scoring time.
        # No WalletCache update needed.

        return _ClusterFormationResult(
            formed=True,
            cluster_id=cluster_id,
            size=len(all_members),
            leader=leader,
        )

    async def _find_existing_cluster(self, addresses: list[str]) -> str | None:
        """Find if any address is already in a cluster.

        Args:
            addresses: Wallet addresses to check

        Returns:
            Existing cluster ID or None
        """
        query = """
        MATCH (w:Wallet)-[:MEMBER_OF]->(c:Cluster)
        WHERE w.address IN $addresses
        RETURN c.id as cluster_id
        LIMIT 1
        """
        try:
            results = await self._neo4j.execute_query(query, {"addresses": addresses})
            return results[0]["cluster_id"] if results else None
        except Exception:
            return None

    async def rebuild_all_clusters(self) -> dict[str, int]:
        """Rebuild all clusters from scratch.

        This is the manual "Rebuild All" operation.

        Returns:
            Dict with operation counts
        """
        logger.info("rebuilding_all_clusters")

        # Step 1: Run cluster discovery
        clusters = await self._cluster_grouper.find_clusters()

        # Step 2: Detect leaders for all clusters
        leaders_detected = 0
        for cluster in clusters:
            leader = await self._leader_detector.detect_cluster_leader(cluster.id)
            if leader:
                leaders_detected += 1

        # Step 3: Calculate multipliers
        multipliers = await self._signal_amplifier.update_cluster_multipliers()

        # Epic 14 Story 14-5: Cluster membership stored in Neo4j only.
        # ClusterService fetches cluster info at scoring time.
        # No WalletCache update needed.

        logger.info(
            "clusters_rebuilt",
            clusters_found=len(clusters),
            leaders_detected=leaders_detected,
            multipliers_set=len(multipliers),
        )

        return {
            "clusters_found": len(clusters),
            "leaders_detected": leaders_detected,
            "multipliers_set": len(multipliers),
        }

    def reset(self) -> None:
        """Reset processed set for new batch."""
        self._processed.clear()

    def update_config(self, config: OnboardingConfig) -> None:
        """Update onboarding configuration.

        Args:
            config: New configuration
        """
        self._config = config
        logger.info(
            "onboarding_config_updated",
            max_depth=config.max_depth,
            min_cluster_size=config.min_cluster_size,
            min_quick_score=config.min_quick_score,
        )


# Module-level singleton
_network_onboarder: NetworkOnboarder | None = None


async def get_network_onboarder(
    neo4j: Neo4jClient,
    wallet_cache: WalletCache,
    funding_analyzer: FundingAnalyzer,
    sync_detector: SyncBuyDetector,
    cluster_grouper: ClusterGrouper,
    leader_detector: LeaderDetector,
    signal_amplifier: SignalAmplifier,
    config: OnboardingConfig | None = None,
) -> NetworkOnboarder:
    """Get or create network onboarder singleton.

    Args:
        neo4j: Neo4j client
        wallet_cache: Wallet cache
        funding_analyzer: Funding analyzer
        sync_detector: Sync detector
        cluster_grouper: Cluster grouper
        leader_detector: Leader detector
        signal_amplifier: Signal amplifier
        config: Optional configuration

    Returns:
        NetworkOnboarder singleton instance
    """
    global _network_onboarder
    if _network_onboarder is None:
        _network_onboarder = NetworkOnboarder(
            neo4j=neo4j,
            wallet_cache=wallet_cache,
            funding_analyzer=funding_analyzer,
            sync_detector=sync_detector,
            cluster_grouper=cluster_grouper,
            leader_detector=leader_detector,
            signal_amplifier=signal_amplifier,
            config=config,
        )
    return _network_onboarder


def reset_network_onboarder() -> None:
    """Reset network onboarder singleton (for testing)."""
    global _network_onboarder
    _network_onboarder = None
