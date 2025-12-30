"""Performance analysis orchestration for wallet metrics calculation.

This module coordinates the end-to-end flow of:
1. Fetching transaction history from Helius
2. Parsing transactions into SwapTransaction objects
3. Calculating performance metrics
4. Updating both Supabase and Neo4j databases

Example:
    # Analyze single wallet
    await analyze_wallet_performance("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")

    # Analyze all discovered wallets
    await analyze_all_wallets()
"""

import asyncio
from datetime import datetime

import structlog

from walltrack.core.analysis.performance_calculator import PerformanceCalculator
from walltrack.core.analysis.transaction_parser import parse_swap_transaction
from walltrack.data.models.transaction import SwapTransaction
from walltrack.data.models.wallet import PerformanceMetrics
from walltrack.data.neo4j.queries.wallet import update_wallet_performance_metrics as update_neo4j_metrics
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger(__name__)


class PerformanceOrchestrator:
    """Orchestrates wallet performance analysis workflow.

    Coordinates transaction fetching, parsing, calculation, and storage
    of performance metrics for wallets.

    Attributes:
        helius_client: Client for fetching transaction history.
        calculator: Engine for computing performance metrics.
        wallet_repo: Repository for updating Supabase database.

    Example:
        orchestrator = PerformanceOrchestrator(
            helius_client=helius_client,
            wallet_repo=wallet_repo
        )
        await orchestrator.analyze_wallet("wallet_address")
    """

    def __init__(
        self,
        helius_client: HeliusClient,
        wallet_repo: WalletRepository,
    ):
        """Initialize orchestrator with required dependencies.

        Args:
            helius_client: Configured Helius API client.
            wallet_repo: Wallet repository for database updates.
        """
        self.helius_client = helius_client
        self.calculator = PerformanceCalculator()
        self.wallet_repo = wallet_repo

    async def analyze_wallet_performance(
        self,
        wallet_address: str,
        token_launch_times: dict[str, datetime] | None = None,
    ) -> PerformanceMetrics:
        """Analyze performance metrics for a single wallet.

        Complete workflow:
        1. Fetch transaction history from Helius (SWAP transactions)
        2. Parse transactions into SwapTransaction objects
        3. Calculate performance metrics (win rate, PnL, entry delay)
        4. Update Supabase database with metrics
        5. Update Neo4j graph with metrics

        Args:
            wallet_address: Solana wallet address to analyze.
            token_launch_times: Optional dict mapping token_mint to launch datetime.
                               Used for entry_delay calculation.

        Returns:
            PerformanceMetrics object with calculated values.

        Raises:
            ValueError: If wallet_address is invalid.
            APIError: If Helius API call fails.
            DatabaseError: If database update fails.

        Example:
            metrics = await orchestrator.analyze_wallet_performance(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                token_launch_times={"token1": datetime(2024, 1, 1)}
            )
            print(f"Win Rate: {metrics.win_rate}%")
        """
        log.info(
            "starting_wallet_performance_analysis",
            wallet_address=wallet_address[:8] + "...",
        )

        # Step 1: Fetch transaction history from Helius
        log.debug("fetching_transactions_from_helius", wallet_address=wallet_address[:8] + "...")

        try:
            tx_response = await self.helius_client.get_wallet_transactions(
                wallet_address=wallet_address,
                limit=1000,  # Fetch up to 1000 SWAP transactions
                tx_type="SWAP",
            )
        except Exception as e:
            log.error(
                "helius_fetch_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        raw_transactions = tx_response if isinstance(tx_response, list) else []

        log.debug(
            "helius_transactions_fetched",
            wallet_address=wallet_address[:8] + "...",
            count=len(raw_transactions),
        )

        # Step 2: Parse transactions into SwapTransaction objects
        log.debug("parsing_transactions", count=len(raw_transactions))

        transactions: list[SwapTransaction] = []
        for raw_tx in raw_transactions:
            try:
                swap_tx = parse_swap_transaction(raw_tx, wallet_address)
                if swap_tx:
                    transactions.append(swap_tx)
            except Exception as e:
                log.warning(
                    "transaction_parse_failed",
                    signature=raw_tx.get("signature", "unknown"),
                    error=str(e),
                )
                continue

        log.info(
            "transactions_parsed",
            wallet_address=wallet_address[:8] + "...",
            total_raw=len(raw_transactions),
            parsed=len(transactions),
        )

        # Step 3: Calculate performance metrics
        log.debug("calculating_performance_metrics", transaction_count=len(transactions))

        try:
            metrics = self.calculator.calculate_metrics(
                transactions=transactions,
                token_launch_times=token_launch_times,
            )
        except Exception as e:
            log.error(
                "metrics_calculation_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        log.info(
            "metrics_calculated",
            wallet_address=wallet_address[:8] + "...",
            win_rate=f"{metrics.win_rate:.1f}%",
            pnl_total=f"{metrics.pnl_total:.4f} SOL",
            total_trades=metrics.total_trades,
            confidence=metrics.confidence,
        )

        # Step 4: Update Supabase database
        log.debug("updating_supabase", wallet_address=wallet_address[:8] + "...")

        try:
            await self.wallet_repo.update_performance_metrics(
                wallet_address=wallet_address,
                metrics=metrics,
            )
        except Exception as e:
            log.error(
                "supabase_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        # Step 5: Update Neo4j graph
        log.debug("updating_neo4j", wallet_address=wallet_address[:8] + "...")

        try:
            await update_neo4j_metrics(
                wallet_address=wallet_address,
                win_rate=metrics.win_rate,
                pnl_total=metrics.pnl_total,
                entry_delay_seconds=metrics.entry_delay_seconds,
                total_trades=metrics.total_trades,
            )
        except Exception as e:
            log.error(
                "neo4j_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            # Don't raise - Supabase is source of truth, Neo4j sync is secondary
            log.warning("neo4j_sync_failed_continuing", wallet_address=wallet_address[:8] + "...")

        log.info(
            "wallet_performance_analysis_complete",
            wallet_address=wallet_address[:8] + "...",
            win_rate=f"{metrics.win_rate:.1f}%",
            pnl_total=f"{metrics.pnl_total:.4f} SOL",
        )

        return metrics

    async def analyze_all_wallets(
        self,
        token_launch_times: dict[str, datetime] | None = None,
        max_concurrent: int = 5,
    ) -> dict[str, PerformanceMetrics]:
        """Analyze performance metrics for all discovered wallets.

        Fetches all wallets from Supabase and analyzes them concurrently
        with controlled concurrency to avoid API rate limits.

        Args:
            token_launch_times: Optional dict mapping token_mint to launch datetime.
            max_concurrent: Maximum number of concurrent wallet analyses (default: 5).

        Returns:
            Dict mapping wallet_address to PerformanceMetrics.
            Only successful analyses are included.

        Example:
            results = await orchestrator.analyze_all_wallets(
                token_launch_times=launch_times,
                max_concurrent=3
            )
            print(f"Analyzed {len(results)} wallets")
        """
        log.info("starting_bulk_wallet_analysis", max_concurrent=max_concurrent)

        # Fetch all wallets from Supabase
        try:
            wallets = await self.wallet_repo.get_all()
        except Exception as e:
            log.error("failed_to_fetch_wallets", error=str(e))
            raise

        wallet_addresses = [w.wallet_address for w in wallets]

        log.info(
            "wallets_fetched_for_analysis",
            total_wallets=len(wallet_addresses),
        )

        # Analyze wallets with controlled concurrency
        results: dict[str, PerformanceMetrics] = {}
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_with_semaphore(address: str) -> tuple[str, PerformanceMetrics | None]:
            """Analyze single wallet with semaphore control."""
            async with semaphore:
                try:
                    metrics = await self.analyze_wallet_performance(
                        wallet_address=address,
                        token_launch_times=token_launch_times,
                    )
                    return address, metrics
                except Exception as e:
                    log.error(
                        "wallet_analysis_failed",
                        wallet_address=address[:8] + "...",
                        error=str(e),
                    )
                    return address, None

        # Run analyses concurrently
        tasks = [analyze_with_semaphore(addr) for addr in wallet_addresses]
        completed = await asyncio.gather(*tasks, return_exceptions=False)

        # Collect successful results
        for address, metrics in completed:
            if metrics:
                results[address] = metrics

        success_count = len(results)
        failure_count = len(wallet_addresses) - success_count

        log.info(
            "bulk_wallet_analysis_complete",
            total_wallets=len(wallet_addresses),
            successful=success_count,
            failed=failure_count,
        )

        return results


async def analyze_wallet_performance(
    wallet_address: str,
    helius_client: HeliusClient,
    wallet_repo: WalletRepository,
    token_launch_times: dict[str, datetime] | None = None,
) -> PerformanceMetrics:
    """Convenience function to analyze a single wallet.

    Creates an orchestrator instance and runs the analysis.

    Args:
        wallet_address: Solana wallet address to analyze.
        helius_client: Configured Helius API client.
        wallet_repo: Wallet repository for database updates.
        token_launch_times: Optional token launch time mapping.

    Returns:
        PerformanceMetrics object.

    Example:
        metrics = await analyze_wallet_performance(
            wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
            helius_client=helius_client,
            wallet_repo=wallet_repo,
        )
    """
    orchestrator = PerformanceOrchestrator(
        helius_client=helius_client,
        wallet_repo=wallet_repo,
    )

    return await orchestrator.analyze_wallet_performance(
        wallet_address=wallet_address,
        token_launch_times=token_launch_times,
    )


async def analyze_all_wallets(
    helius_client: HeliusClient,
    wallet_repo: WalletRepository,
    token_launch_times: dict[str, datetime] | None = None,
    max_concurrent: int = 5,
) -> dict[str, PerformanceMetrics]:
    """Convenience function to analyze all wallets.

    Creates an orchestrator instance and runs bulk analysis.

    Args:
        helius_client: Configured Helius API client.
        wallet_repo: Wallet repository for database updates.
        token_launch_times: Optional token launch time mapping.
        max_concurrent: Maximum concurrent analyses.

    Returns:
        Dict mapping wallet_address to PerformanceMetrics.

    Example:
        results = await analyze_all_wallets(
            helius_client=helius_client,
            wallet_repo=wallet_repo,
            max_concurrent=3,
        )
    """
    orchestrator = PerformanceOrchestrator(
        helius_client=helius_client,
        wallet_repo=wallet_repo,
    )

    return await orchestrator.analyze_all_wallets(
        token_launch_times=token_launch_times,
        max_concurrent=max_concurrent,
    )
