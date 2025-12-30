"""Neo4j queries for wallet operations.

This module provides functions to create and manage wallet nodes in Neo4j graph database.
Wallet nodes are used for relationship tracking and graph-based analysis.
"""

import structlog

from walltrack.data.neo4j.client import get_neo4j_client

log = structlog.get_logger(__name__)


async def create_wallet_node(wallet_address: str) -> dict[str, any]:
    """Create or update a wallet node in Neo4j.

    Uses MERGE to ensure idempotent operation - creates node if it doesn't exist,
    or returns existing node if it does. This prevents duplicate wallet nodes.

    Args:
        wallet_address: Solana wallet address (unique identifier).

    Returns:
        Dict with wallet node properties after creation/merge.

    Example:
        node = await create_wallet_node("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
        # Returns: {"wallet_address": "9xQeWvG...", "created": true/false}

    Note:
        - MERGE is idempotent (safe to call multiple times)
        - Node label: "Wallet"
        - Property: wallet_address (unique)
        - Additional properties can be added later via update queries
    """
    client = await get_neo4j_client()

    query = """
    MERGE (w:Wallet {wallet_address: $wallet_address})
    ON CREATE SET w.created_at = datetime()
    RETURN w.wallet_address AS wallet_address,
           w.created_at AS created_at,
           (w.created_at = datetime()) AS was_created
    """

    log.info(
        "creating_wallet_node_neo4j",
        wallet_address=wallet_address[:8] + "...",
    )

    try:
        result = await client.execute_query(
            query,
            parameters={"wallet_address": wallet_address},
        )

        if not result:
            log.error(
                "wallet_node_creation_failed_no_result",
                wallet_address=wallet_address[:8] + "...",
            )
            return {}

        node_data = result[0]

        log.info(
            "wallet_node_created_or_merged",
            wallet_address=wallet_address[:8] + "...",
            was_created=node_data.get("was_created", False),
        )

        return {
            "wallet_address": node_data.get("wallet_address"),
            "created_at": str(node_data.get("created_at")),
            "was_created": node_data.get("was_created", False),
        }

    except Exception as e:
        log.error(
            "wallet_node_creation_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        raise


async def get_wallet_node(wallet_address: str) -> dict[str, any] | None:
    """Retrieve a wallet node from Neo4j by address.

    Args:
        wallet_address: Solana wallet address to search for.

    Returns:
        Dict with wallet node properties if found, None if not exists.

    Example:
        node = await get_wallet_node("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
        # Returns: {"wallet_address": "9xQeWvG...", "created_at": "..."}
    """
    client = await get_neo4j_client()

    query = """
    MATCH (w:Wallet {wallet_address: $wallet_address})
    RETURN w.wallet_address AS wallet_address,
           w.created_at AS created_at
    """

    log.debug(
        "fetching_wallet_node_neo4j",
        wallet_address=wallet_address[:8] + "...",
    )

    try:
        result = await client.execute_query(
            query,
            parameters={"wallet_address": wallet_address},
        )

        if not result:
            log.debug(
                "wallet_node_not_found",
                wallet_address=wallet_address[:8] + "...",
            )
            return None

        node_data = result[0]

        return {
            "wallet_address": node_data.get("wallet_address"),
            "created_at": str(node_data.get("created_at")),
        }

    except Exception as e:
        log.error(
            "wallet_node_fetch_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        raise


async def update_wallet_performance_metrics(
    wallet_address: str,
    win_rate: float,
    pnl_total: float,
    entry_delay_seconds: int,
    total_trades: int,
) -> dict[str, any]:
    """Update performance metrics for a wallet node in Neo4j.

    Args:
        wallet_address: Solana wallet address to update.
        win_rate: Win rate percentage (0.0-100.0).
        pnl_total: Total PnL in SOL.
        entry_delay_seconds: Average seconds between token launch and first buy.
        total_trades: Total number of trades analyzed.

    Returns:
        Dict with updated wallet node properties.

    Example:
        result = await update_wallet_performance_metrics(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            win_rate=78.5,
            pnl_total=15.25,
            entry_delay_seconds=3600,
            total_trades=25,
        )
    """
    client = await get_neo4j_client()

    query = """
    MATCH (w:Wallet {wallet_address: $wallet_address})
    SET w.win_rate = $win_rate,
        w.pnl_total = $pnl_total,
        w.entry_delay_seconds = $entry_delay_seconds,
        w.total_trades = $total_trades,
        w.metrics_updated_at = datetime()
    RETURN w.wallet_address AS wallet_address,
           w.win_rate AS win_rate,
           w.pnl_total AS pnl_total,
           w.entry_delay_seconds AS entry_delay_seconds,
           w.total_trades AS total_trades
    """

    log.info(
        "updating_wallet_performance_metrics_neo4j",
        wallet_address=wallet_address[:8] + "...",
        win_rate=win_rate,
        total_trades=total_trades,
    )

    try:
        result = await client.execute_query(
            query,
            parameters={
                "wallet_address": wallet_address,
                "win_rate": win_rate,
                "pnl_total": pnl_total,
                "entry_delay_seconds": entry_delay_seconds,
                "total_trades": total_trades,
            },
        )

        if not result:
            log.error(
                "wallet_performance_update_failed_no_result",
                wallet_address=wallet_address[:8] + "...",
            )
            return {}

        node_data = result[0]

        log.info(
            "wallet_performance_metrics_updated",
            wallet_address=wallet_address[:8] + "...",
            win_rate=node_data.get("win_rate"),
            pnl_total=node_data.get("pnl_total"),
        )

        return {
            "wallet_address": node_data.get("wallet_address"),
            "win_rate": node_data.get("win_rate"),
            "pnl_total": node_data.get("pnl_total"),
            "entry_delay_seconds": node_data.get("entry_delay_seconds"),
            "total_trades": node_data.get("total_trades"),
        }

    except Exception as e:
        log.error(
            "wallet_performance_update_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        raise


async def update_wallet_behavioral_profile(
    wallet_address: str,
    position_size_style: str,
    position_size_avg: float,
    hold_duration_avg: int,
    hold_duration_style: str,
) -> dict[str, any]:
    """Update behavioral profiling properties for a wallet node in Neo4j.

    Args:
        wallet_address: Solana wallet address to update.
        position_size_style: Position size classification (small, medium, large).
        position_size_avg: Average position size in SOL.
        hold_duration_avg: Average hold duration in seconds.
        hold_duration_style: Hold duration style (scalper, day_trader, swing_trader, position_trader).

    Returns:
        Dict with updated wallet node properties.

    Example:
        result = await update_wallet_behavioral_profile(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            position_size_style="medium",
            position_size_avg=2.5,
            hold_duration_avg=7200,
            hold_duration_style="day_trader",
        )
    """
    client = await get_neo4j_client()

    query = """
    MATCH (w:Wallet {wallet_address: $wallet_address})
    SET w.position_size_style = $position_size_style,
        w.position_size_avg = $position_size_avg,
        w.hold_duration_avg = $hold_duration_avg,
        w.hold_duration_style = $hold_duration_style,
        w.behavioral_updated_at = datetime()
    RETURN w.wallet_address AS wallet_address,
           w.position_size_style AS position_size_style,
           w.position_size_avg AS position_size_avg,
           w.hold_duration_avg AS hold_duration_avg,
           w.hold_duration_style AS hold_duration_style
    """

    log.info(
        "updating_wallet_behavioral_profile_neo4j",
        wallet_address=wallet_address[:8] + "...",
        position_size_style=position_size_style,
        hold_duration_style=hold_duration_style,
    )

    try:
        result = await client.execute_query(
            query,
            parameters={
                "wallet_address": wallet_address,
                "position_size_style": position_size_style,
                "position_size_avg": position_size_avg,
                "hold_duration_avg": hold_duration_avg,
                "hold_duration_style": hold_duration_style,
            },
        )

        if not result:
            log.error(
                "wallet_behavioral_update_failed_no_result",
                wallet_address=wallet_address[:8] + "...",
            )
            return {}

        node_data = result[0]

        log.info(
            "wallet_behavioral_profile_updated",
            wallet_address=wallet_address[:8] + "...",
            position_size_style=node_data.get("position_size_style"),
            hold_duration_style=node_data.get("hold_duration_style"),
        )

        return {
            "wallet_address": node_data.get("wallet_address"),
            "position_size_style": node_data.get("position_size_style"),
            "position_size_avg": node_data.get("position_size_avg"),
            "hold_duration_avg": node_data.get("hold_duration_avg"),
            "hold_duration_style": node_data.get("hold_duration_style"),
        }

    except Exception as e:
        log.error(
            "wallet_behavioral_update_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        raise


async def delete_wallet_node(wallet_address: str) -> bool:
    """Delete a wallet node from Neo4j.

    Removes the wallet node and all its relationships from the graph.

    Args:
        wallet_address: Solana wallet address to delete.

    Returns:
        True if node was deleted, False if node didn't exist.

    Warning:
        This also deletes all relationships connected to this wallet node.
        Use with caution in production.

    Example:
        deleted = await delete_wallet_node("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
        # Returns: True if deleted, False if not found
    """
    client = await get_neo4j_client()

    query = """
    MATCH (w:Wallet {wallet_address: $wallet_address})
    DETACH DELETE w
    RETURN count(w) AS deleted_count
    """

    log.info(
        "deleting_wallet_node_neo4j",
        wallet_address=wallet_address[:8] + "...",
    )

    try:
        result = await client.execute_query(
            query,
            parameters={"wallet_address": wallet_address},
        )

        deleted_count = result[0].get("deleted_count", 0) if result else 0

        if deleted_count > 0:
            log.info(
                "wallet_node_deleted",
                wallet_address=wallet_address[:8] + "...",
            )
            return True
        else:
            log.debug(
                "wallet_node_not_found_for_deletion",
                wallet_address=wallet_address[:8] + "...",
            )
            return False

    except Exception as e:
        log.error(
            "wallet_node_deletion_error",
            wallet_address=wallet_address[:8] + "...",
            error=str(e),
        )
        raise
