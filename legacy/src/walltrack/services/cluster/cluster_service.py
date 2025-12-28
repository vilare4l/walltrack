"""Service for cluster data queries - direct from Neo4j.

Epic 14 Story 14-5: Replaces cached cluster data in WalletCache.
Always returns fresh data from source of truth (Neo4j).
Latency target: <20ms per query.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from walltrack.data.neo4j.client import Neo4jClient

log = structlog.get_logger(__name__)


@dataclass
class ClusterInfo:
    """Cluster information for a wallet."""

    cluster_id: str | None
    is_leader: bool
    amplification_factor: float
    cluster_size: int


class ClusterService:
    """
    Direct Neo4j queries for cluster data.

    Replaces cached cluster data in WalletCache.
    Always returns fresh data from source of truth.
    """

    def __init__(self, neo4j: Neo4jClient | None = None) -> None:
        """Initialize ClusterService.

        Args:
            neo4j: Neo4j client for queries. If None, returns defaults.
        """
        self._neo4j = neo4j

    async def get_wallet_cluster_info(self, wallet_address: str) -> ClusterInfo:
        """
        Get cluster info for a wallet directly from Neo4j.

        Args:
            wallet_address: Wallet to look up

        Returns:
            ClusterInfo with cluster_id, is_leader, amplification_factor
            Returns defaults if not in cluster or Neo4j unavailable
        """
        if self._neo4j is None:
            return ClusterInfo(
                cluster_id=None,
                is_leader=False,
                amplification_factor=1.0,
                cluster_size=0,
            )

        try:
            query = """
            MATCH (w:Wallet {address: $address})-[:MEMBER_OF]->(c:Cluster)
            RETURN c.id as cluster_id,
                   c.leader_address = w.address as is_leader,
                   coalesce(c.amplification_factor, 1.0) as amplification_factor,
                   c.size as cluster_size
            LIMIT 1
            """
            results = await self._neo4j.execute_query(
                query, {"address": wallet_address}
            )

            if not results:
                return ClusterInfo(
                    cluster_id=None,
                    is_leader=False,
                    amplification_factor=1.0,
                    cluster_size=0,
                )

            r = results[0]
            return ClusterInfo(
                cluster_id=r["cluster_id"],
                is_leader=r["is_leader"],
                amplification_factor=r["amplification_factor"],
                cluster_size=r["cluster_size"] or 0,
            )

        except Exception as e:
            log.warning(
                "cluster_info_query_failed",
                wallet=wallet_address[:8],
                error=str(e),
            )
            return ClusterInfo(
                cluster_id=None,
                is_leader=False,
                amplification_factor=1.0,
                cluster_size=0,
            )


# Module-level singleton
_cluster_service: ClusterService | None = None


async def get_cluster_service(
    neo4j: Neo4jClient | None = None,
) -> ClusterService:
    """Get or create ClusterService singleton.

    Args:
        neo4j: Neo4j client for queries

    Returns:
        ClusterService singleton instance
    """
    global _cluster_service
    if _cluster_service is None:
        _cluster_service = ClusterService(neo4j=neo4j)
    return _cluster_service


def reset_cluster_service() -> None:
    """Reset cluster service singleton (for testing)."""
    global _cluster_service
    _cluster_service = None
