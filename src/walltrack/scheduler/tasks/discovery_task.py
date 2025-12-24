"""Wallet discovery scheduled task."""

from typing import Any

import structlog

from walltrack.data.models.wallet import DiscoveryResult
from walltrack.data.neo4j.client import get_neo4j_client
from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.profiler import WalletProfiler
from walltrack.discovery.pump_finder import PumpFinder
from walltrack.discovery.scanner import WalletDiscoveryScanner
from walltrack.services.helius.client import get_helius_client

log = structlog.get_logger()


async def run_discovery_task(
    min_price_change_pct: float = 100.0,
    min_volume_usd: float = 50000.0,
    max_token_age_hours: int = 72,
    early_window_minutes: int = 30,
    min_profit_pct: float = 50.0,
    max_tokens: int = 20,
    profile_immediately: bool = True,
) -> dict[str, Any]:
    """
    Run the full wallet discovery pipeline.

    Pipeline:
    1. Find tokens that have pumped recently (via DexScreener)
    2. For each pumped token, find early buyers who profited
    3. Store discovered wallets in Supabase and Neo4j
    4. Optionally profile the newly discovered wallets

    Args:
        min_price_change_pct: Minimum 24h price change to consider a pump
        min_volume_usd: Minimum 24h volume in USD
        max_token_age_hours: Maximum token age in hours
        early_window_minutes: Minutes after launch to consider "early buyer"
        min_profit_pct: Minimum profit percentage for wallet qualification
        max_tokens: Maximum number of pumped tokens to analyze
        profile_immediately: Whether to profile wallets after discovery

    Returns:
        Summary of discovery results
    """
    log.info(
        "discovery_task_starting",
        min_change=min_price_change_pct,
        min_volume=min_volume_usd,
        max_tokens=max_tokens,
    )

    # Initialize dependencies
    pump_finder = PumpFinder()
    supabase = await get_supabase_client()
    neo4j = await get_neo4j_client()
    helius = await get_helius_client()

    wallet_repo = WalletRepository(supabase)
    scanner = WalletDiscoveryScanner(wallet_repo, neo4j, helius)

    try:
        # Step 1: Find pumped tokens
        log.info("discovery_step_1_find_pumps")
        pumped_tokens = await pump_finder.find_pumped_tokens(
            min_price_change_pct=min_price_change_pct,
            min_volume_usd=min_volume_usd,
            max_age_hours=max_token_age_hours,
            limit=max_tokens,
        )

        if not pumped_tokens:
            log.info("no_pumped_tokens_found")
            return {
                "tokens_analyzed": 0,
                "new_wallets": 0,
                "updated_wallets": 0,
                "errors": [],
            }

        log.info("pumped_tokens_found", count=len(pumped_tokens))

        # Step 2: Discover wallets from each pumped token
        log.info("discovery_step_2_find_wallets")
        results: list[DiscoveryResult] = await scanner.discover_from_multiple_tokens(
            token_launches=pumped_tokens,
            early_window_minutes=early_window_minutes,
            min_profit_pct=min_profit_pct,
            max_concurrent=5,
        )

        # Aggregate results
        total_new = sum(r.new_wallets for r in results)
        total_updated = sum(r.updated_wallets for r in results)
        all_errors: list[str] = []
        for r in results:
            all_errors.extend(r.errors)

        log.info(
            "discovery_wallets_found",
            new_wallets=total_new,
            updated_wallets=total_updated,
        )

        # Step 3: Profile newly discovered wallets (optional)
        profiled_count = 0
        if profile_immediately and total_new > 0:
            log.info("discovery_step_3_profile_wallets")
            profiler = WalletProfiler(wallet_repo, helius)

            # Get addresses of newly discovered wallets
            # They'll have last_profiled_at = None
            unprofiled = await wallet_repo.get_unprofiled_wallets(limit=total_new + 10)
            addresses = [w.address for w in unprofiled]

            if addresses:
                profiled = await profiler.profile_batch(
                    addresses=addresses,
                    lookback_days=90,
                    max_concurrent=10,
                )
                profiled_count = len(profiled)
                log.info("wallets_profiled", count=profiled_count)

        result = {
            "tokens_analyzed": len(pumped_tokens),
            "new_wallets": total_new,
            "updated_wallets": total_updated,
            "profiled_wallets": profiled_count,
            "errors": all_errors[:10],  # Limit error list
        }

        log.info("discovery_task_completed", **result)
        return result

    finally:
        await pump_finder.close()


async def run_discovery_for_token(
    token_mint: str,
    early_window_minutes: int = 30,
    min_profit_pct: float = 50.0,
) -> DiscoveryResult:
    """
    Run discovery for a specific token.

    Useful for manual discovery or when you already know which token to analyze.

    Args:
        token_mint: Token mint address
        early_window_minutes: Minutes after launch to consider "early buyer"
        min_profit_pct: Minimum profit percentage for wallet qualification

    Returns:
        DiscoveryResult with counts and errors
    """
    log.info(
        "discovery_single_token_starting",
        token=token_mint,
    )

    # Initialize dependencies
    pump_finder = PumpFinder()
    supabase = await get_supabase_client()
    neo4j = await get_neo4j_client()
    helius = await get_helius_client()

    wallet_repo = WalletRepository(supabase)
    scanner = WalletDiscoveryScanner(wallet_repo, neo4j, helius)

    try:
        # Get token launch data
        token_launches = await pump_finder.find_tokens_by_addresses([token_mint])

        if not token_launches:
            log.warning("token_not_found", token=token_mint)
            return DiscoveryResult(
                token_mint=token_mint,
                new_wallets=0,
                updated_wallets=0,
                total_processed=0,
                duration_seconds=0,
                errors=["Token not found on DexScreener"],
            )

        # Run discovery
        result = await scanner.discover_from_token(
            token_launch=token_launches[0],
            early_window_minutes=early_window_minutes,
            min_profit_pct=min_profit_pct,
        )

        log.info(
            "discovery_single_token_completed",
            new=result.new_wallets,
            updated=result.updated_wallets,
        )

        return result

    finally:
        await pump_finder.close()


async def run_quick_discovery(
    max_tokens: int = 10,
) -> dict[str, int]:
    """
    Run a quick discovery with default parameters.

    Convenient for testing or quick runs.

    Args:
        max_tokens: Maximum tokens to analyze

    Returns:
        Summary of discovery results
    """
    result = await run_discovery_task(
        min_price_change_pct=100.0,
        min_volume_usd=50000.0,
        max_token_age_hours=48,
        early_window_minutes=30,
        min_profit_pct=50.0,
        max_tokens=max_tokens,
        profile_immediately=True,
    )

    return {
        "tokens": result["tokens_analyzed"],
        "new": result["new_wallets"],
        "updated": result["updated_wallets"],
    }
