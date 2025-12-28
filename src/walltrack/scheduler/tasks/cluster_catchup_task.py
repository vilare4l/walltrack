"""Scheduler task for catching up orphan wallets with clustering.

Epic 14 Story 14-5: Cluster Catchup Scheduler
- Finds wallets with status='active' but no MEMBER_OF relationship
- Processes up to batch_size wallets per run
- Calls NetworkOnboarder.onboard_wallet() for each
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from walltrack.data.neo4j.client import Neo4jClient
    from walltrack.services.wallet.network_onboarder import NetworkOnboarder

log = structlog.get_logger(__name__)


async def run_cluster_catchup(
    neo4j: Neo4jClient,
    network_onboarder: NetworkOnboarder,
    batch_size: int = 50,
    min_age_hours: int = 1,
) -> dict[str, int | float]:
    """
    Find and cluster orphan wallets.

    Args:
        neo4j: Neo4j client for queries
        network_onboarder: Service to handle clustering
        batch_size: Max wallets to process per run
        min_age_hours: Only process wallets older than this

    Returns:
        Dict with processing stats
    """
    start_time = datetime.utcnow()
    min_created = datetime.utcnow() - timedelta(hours=min_age_hours)

    log.info(
        "cluster_catchup_started",
        batch_size=batch_size,
        min_age_hours=min_age_hours,
    )

    # Find orphan wallets (active, no cluster, old enough)
    query = """
    MATCH (w:Wallet)
    WHERE w.status = 'active'
    AND w.created_at < $min_created
    AND NOT (w)-[:MEMBER_OF]->(:Cluster)
    RETURN w.address as address
    ORDER BY w.score DESC
    LIMIT $limit
    """

    orphans = await neo4j.execute_query(
        query,
        {
            "min_created": min_created.isoformat(),
            "limit": batch_size,
        },
    )

    if not orphans:
        log.info("cluster_catchup_no_orphans")
        duration = (datetime.utcnow() - start_time).total_seconds()
        return {"processed": 0, "clusters_formed": 0, "duration_seconds": duration}

    processed = 0
    clusters_formed = 0
    errors = 0

    # Reset onboarder state for this batch
    network_onboarder.reset()

    for record in orphans:
        wallet_address = record["address"]
        try:
            result = await network_onboarder.onboard_wallet(
                address=wallet_address,
                tx_history=[],  # No tx_history available for catchup
                depth=0,
            )
            processed += 1
            if result.cluster_formed:
                clusters_formed += 1

        except Exception as e:
            log.error(
                "cluster_catchup_wallet_failed",
                wallet=wallet_address[:8],
                error=str(e),
            )
            errors += 1

    duration = (datetime.utcnow() - start_time).total_seconds()

    log.info(
        "cluster_catchup_completed",
        orphans_found=len(orphans),
        processed=processed,
        clusters_formed=clusters_formed,
        errors=errors,
        duration_seconds=duration,
    )

    return {
        "orphans_found": len(orphans),
        "processed": processed,
        "clusters_formed": clusters_formed,
        "errors": errors,
        "duration_seconds": duration,
    }
