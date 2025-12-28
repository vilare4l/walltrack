"""Migrate Neo4j HAS_MEMBER relationships to MEMBER_OF.

Story 13-2: Fix Neo4j Relationship Naming

This script converts any existing HAS_MEMBER relationships (Cluster -> Wallet)
to MEMBER_OF relationships (Wallet -> Cluster) for consistency.

Usage:
    python -m scripts.migrate_neo4j_relationships
"""

import asyncio

import structlog

from walltrack.data.neo4j.client import get_neo4j_client

log = structlog.get_logger()


async def migrate_relationships() -> dict[str, int]:
    """
    Migrate HAS_MEMBER to MEMBER_OF relationships.

    Returns:
        Dict with migration statistics
    """
    client = await get_neo4j_client()

    # Count existing HAS_MEMBER relationships
    count_query = """
    MATCH ()-[r:HAS_MEMBER]->()
    RETURN count(r) as count
    """
    count_result = await client.execute_query(count_query, {})
    has_member_count = count_result[0]["count"] if count_result else 0

    log.info("migration_starting", has_member_count=has_member_count)

    if has_member_count == 0:
        log.info("no_migration_needed")
        return {"migrated": 0, "deleted": 0}

    # Migrate: Create MEMBER_OF from HAS_MEMBER and delete HAS_MEMBER
    migrate_query = """
    MATCH (c:Cluster)-[r:HAS_MEMBER]->(w:Wallet)
    MERGE (w)-[new:MEMBER_OF]->(c)
    SET new.role = r.role,
        new.join_reason = r.join_reason,
        new.influence_score = r.influence_score,
        new.connection_count = r.connection_count,
        new.joined_at = r.joined_at
    DELETE r
    RETURN count(new) as migrated
    """
    migrate_result = await client.execute_query(migrate_query, {})
    migrated_count = migrate_result[0]["migrated"] if migrate_result else 0

    # Verify no HAS_MEMBER remain
    verify_result = await client.execute_query(count_query, {})
    remaining = verify_result[0]["count"] if verify_result else 0

    log.info(
        "migration_complete",
        migrated=migrated_count,
        remaining_has_member=remaining,
    )

    return {
        "migrated": migrated_count,
        "remaining_has_member": remaining,
    }


async def verify_member_of_consistency() -> dict[str, int]:
    """
    Verify MEMBER_OF relationships are consistent.

    Returns:
        Dict with verification statistics
    """
    client = await get_neo4j_client()

    # Count MEMBER_OF relationships
    member_of_query = """
    MATCH (w:Wallet)-[r:MEMBER_OF]->(c:Cluster)
    RETURN count(r) as count
    """
    result = await client.execute_query(member_of_query, {})
    member_of_count = result[0]["count"] if result else 0

    # Count clusters
    cluster_query = """
    MATCH (c:Cluster)
    RETURN count(c) as count
    """
    cluster_result = await client.execute_query(cluster_query, {})
    cluster_count = cluster_result[0]["count"] if cluster_result else 0

    # Count wallets in clusters
    wallet_query = """
    MATCH (w:Wallet)-[:MEMBER_OF]->(:Cluster)
    RETURN count(DISTINCT w) as count
    """
    wallet_result = await client.execute_query(wallet_query, {})
    wallet_count = wallet_result[0]["count"] if wallet_result else 0

    stats = {
        "member_of_relationships": member_of_count,
        "clusters": cluster_count,
        "wallets_in_clusters": wallet_count,
    }

    log.info("verification_complete", **stats)
    return stats


async def main() -> None:
    """Run the migration."""
    log.info("neo4j_relationship_migration_starting")

    try:
        # Run migration
        migration_stats = await migrate_relationships()

        # Verify consistency
        verify_stats = await verify_member_of_consistency()

        log.info(
            "migration_finished",
            migration=migration_stats,
            verification=verify_stats,
        )

    except Exception as e:
        log.error("migration_failed", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
