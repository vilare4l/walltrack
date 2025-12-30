"""Service for synchronizing wallets from Supabase to Neo4j.

This module provides functions to sync discovered wallet addresses
from Supabase PostgreSQL to Neo4j graph database for relationship tracking.
"""

import structlog

from walltrack.data.neo4j.queries.wallet import create_wallet_node

log = structlog.get_logger(__name__)


async def sync_wallet_to_neo4j(wallet_address: str) -> bool:
    """Sync a wallet address from Supabase to Neo4j.

    Creates or updates a wallet node in Neo4j graph database.
    This is called after a wallet is created in Supabase to ensure
    the wallet exists in both databases.

    Args:
        wallet_address: Solana wallet address to sync.

    Returns:
        True if sync successful, False if failed.

    Note:
        - Idempotent: Safe to call multiple times (MERGE prevents duplicates)
        - Neo4j node will be created if it doesn't exist
        - If node exists, no changes are made (MERGE behavior)
        - Call this after WalletRepository.create_wallet()

    Example:
        # After creating wallet in Supabase
        wallet = await wallet_repo.create_wallet(wallet_create_data)
        if wallet:
            await sync_wallet_to_neo4j(wallet.wallet_address)
    """
    log.info(
        "syncing_wallet_to_neo4j",
        wallet_address=wallet_address[:8] + "...",
    )

    try:
        result = await create_wallet_node(wallet_address)

        if result and result.get("wallet_address"):
            was_created = result.get("was_created", False)
            log.info(
                "wallet_synced_to_neo4j",
                wallet_address=wallet_address[:8] + "...",
                was_created=was_created,
            )
            return True
        else:
            log.error(
                "wallet_sync_failed_no_result",
                wallet_address=wallet_address[:8] + "...",
            )
            return False

    except Exception as e:
        log.error(
            "wallet_sync_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        # Don't raise - sync failures shouldn't block wallet creation in Supabase
        # Log error and return False to indicate failure
        return False


async def sync_batch_wallets_to_neo4j(wallet_addresses: list[str]) -> dict[str, int]:
    """Sync multiple wallet addresses to Neo4j in batch.

    Useful for bulk sync operations (e.g., migrating existing wallets).

    Args:
        wallet_addresses: List of Solana wallet addresses to sync.

    Returns:
        Dict with counts: {"success": N, "failed": M, "total": T}

    Example:
        wallets = ["addr1", "addr2", "addr3"]
        result = await sync_batch_wallets_to_neo4j(wallets)
        # Returns: {"success": 2, "failed": 1, "total": 3}
    """
    success_count = 0
    failed_count = 0
    total = len(wallet_addresses)

    log.info(
        "syncing_batch_wallets_to_neo4j",
        total=total,
    )

    for wallet_address in wallet_addresses:
        success = await sync_wallet_to_neo4j(wallet_address)
        if success:
            success_count += 1
        else:
            failed_count += 1

    log.info(
        "batch_wallet_sync_completed",
        total=total,
        success=success_count,
        failed=failed_count,
    )

    return {
        "success": success_count,
        "failed": failed_count,
        "total": total,
    }
