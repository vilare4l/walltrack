"""Wallet Performance Analysis Orchestrator (Story 3.2 - Task 5).

This module orchestrates the complete wallet performance analysis flow:
1. Fetch transaction history from Helius API
2. Parse transactions into SwapTransaction objects
3. Calculate performance metrics (win rate, PnL, entry delay)
4. Update wallet records in Supabase and Neo4j

Example:
    analyzer = WalletPerformanceAnalyzer(helius_client, supabase_client, neo4j_client)
    success = await analyzer.analyze_wallet("9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin")
"""

from datetime import datetime

import structlog

from walltrack.core.analysis.performance_calculator import PerformanceCalculator
from walltrack.core.analysis.transaction_parser import TransactionParser
from walltrack.data.models.wallet import PerformanceMetrics
from walltrack.data.neo4j.queries.wallet import update_wallet_performance_metrics
from walltrack.data.supabase.client import SupabaseClient
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger(__name__)


class WalletPerformanceAnalyzer:
    """Orchestrates wallet performance analysis across all data sources.

    Coordinates the flow between:
    - Helius API (transaction history)
    - Transaction parser (raw data → SwapTransaction)
    - Performance calculator (metrics computation)
    - Supabase + Neo4j (persistence)

    Attributes:
        helius_client: HeliusClient for fetching transaction history.
        wallet_repo: WalletRepository for Supabase operations.
        parser: TransactionParser for parsing Helius responses.
        calculator: PerformanceCalculator for metrics calculation.

    Example:
        analyzer = WalletPerformanceAnalyzer(helius_client, supabase_client)
        success = await analyzer.analyze_wallet("9xQeWvG...")
        if success:
            print("Wallet performance metrics updated!")
    """

    def __init__(
        self,
        helius_client: HeliusClient,
        supabase_client: SupabaseClient,
    ) -> None:
        """Initialize the analyzer with required clients.

        Args:
            helius_client: HeliusClient instance for API calls.
            supabase_client: SupabaseClient instance for database operations.
        """
        self.helius_client = helius_client
        self.wallet_repo = WalletRepository(supabase_client)
        self.parser = TransactionParser()
        self.calculator = PerformanceCalculator()

        log.info("wallet_performance_analyzer_initialized")

    async def analyze_wallet(
        self,
        wallet_address: str,
        token_launch_times: dict[str, datetime] | None = None,
        transaction_limit: int = 100,
    ) -> bool:
        """Analyze wallet performance and update metrics in database.

        Complete orchestration flow:
        1. Fetch transaction history from Helius API
        2. Parse transactions into SwapTransaction objects
        3. Calculate performance metrics
        4. Update Supabase wallet record
        5. Update Neo4j wallet node (if exists)

        Args:
            wallet_address: Solana wallet address to analyze.
            token_launch_times: Optional dict mapping token_mint to launch datetime.
                               Used for entry_delay_seconds calculation.
            transaction_limit: Max number of transactions to fetch (default: 100).

        Returns:
            True if analysis completed successfully and metrics were updated.
            False if analysis failed or wallet doesn't exist.

        Example:
            # Analyze wallet with token launch times
            launch_times = {
                "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": datetime(2024, 1, 1)
            }
            success = await analyzer.analyze_wallet(
                "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                token_launch_times=launch_times
            )
        """
        log.info(
            "wallet_performance_analysis_started",
            wallet_address=wallet_address[:8] + "...",
        )

        try:
            # Step 1: Verify wallet exists in database
            wallet = await self.wallet_repo.get_by_address(wallet_address)
            if not wallet:
                log.warning(
                    "wallet_not_found_in_database",
                    wallet_address=wallet_address[:8] + "...",
                )
                return False

            # Step 2: Fetch transaction history from Helius
            log.debug(
                "fetching_transaction_history",
                wallet_address=wallet_address[:8] + "...",
                limit=transaction_limit,
            )
            raw_transactions = await self.helius_client.get_wallet_transactions(
                wallet_address=wallet_address,
                limit=transaction_limit,
                tx_type="SWAP",  # Only get swap transactions
            )

            # Step 3: Parse transactions
            log.debug(
                "parsing_transactions",
                raw_count=len(raw_transactions),
            )
            swap_transactions = []
            for raw_tx in raw_transactions:
                parsed_tx = self.parser.parse_swap_transaction(raw_tx, wallet_address)
                if parsed_tx:
                    swap_transactions.append(parsed_tx)

            log.info(
                "transactions_parsed",
                total_raw=len(raw_transactions),
                total_swaps=len(swap_transactions),
            )

            # Step 4: Calculate performance metrics
            log.debug("calculating_performance_metrics")
            metrics = self.calculator.calculate_metrics(
                transactions=swap_transactions,
                token_launch_times=token_launch_times,
            )

            log.info(
                "metrics_calculated",
                win_rate=f"{metrics.win_rate:.1f}%",
                pnl_total=f"{metrics.pnl_total:+.4f} SOL",
                total_trades=metrics.total_trades,
                confidence=metrics.confidence,
            )

            # Step 5: Update Supabase wallet record
            log.debug("updating_supabase_wallet_record")
            supabase_success = await self.wallet_repo.update_performance_metrics(
                wallet_address=wallet_address,
                metrics=metrics,
            )

            if not supabase_success:
                log.error(
                    "supabase_update_failed",
                    wallet_address=wallet_address[:8] + "...",
                )
                return False

            # Step 6: Update Neo4j wallet node (if exists)
            log.debug("updating_neo4j_wallet_node")
            try:
                await update_wallet_performance_metrics(
                    wallet_address=wallet_address,
                    win_rate=metrics.win_rate,
                    pnl_total=metrics.pnl_total,
                    entry_delay_seconds=metrics.entry_delay_seconds,
                    total_trades=metrics.total_trades,
                )
                log.debug("neo4j_update_successful")
            except Exception as neo4j_error:
                # Neo4j update failure is not critical - wallet might not exist in graph
                log.warning(
                    "neo4j_update_failed_non_critical",
                    wallet_address=wallet_address[:8] + "...",
                    error=str(neo4j_error),
                )

            log.info(
                "wallet_performance_analysis_completed",
                wallet_address=wallet_address[:8] + "...",
                win_rate=f"{metrics.win_rate:.1f}%",
                pnl_total=f"{metrics.pnl_total:+.4f} SOL",
            )

            return True

        except Exception as e:
            log.error(
                "wallet_performance_analysis_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
                error_type=type(e).__name__,
            )
            return False

    async def analyze_all_wallets(
        self,
        token_launch_times: dict[str, datetime] | None = None,
        transaction_limit: int = 100,
    ) -> dict[str, int]:
        """Analyze performance for all wallets in database.

        Iterates through all wallets and runs analysis for each.
        Non-blocking: continues even if individual analyses fail.

        Args:
            token_launch_times: Optional dict mapping token_mint to launch datetime.
            transaction_limit: Max transactions to fetch per wallet (default: 100).

        Returns:
            Dict with success/failure counts:
            {
                "total": 100,
                "successful": 85,
                "failed": 15
            }

        Example:
            results = await analyzer.analyze_all_wallets()
            print(f"Analyzed {results['successful']}/{results['total']} wallets")
        """
        log.info("bulk_wallet_performance_analysis_started")

        # Get all wallets from database
        wallets = await self.wallet_repo.get_all(limit=10000)
        total = len(wallets)

        log.info("wallets_retrieved_for_analysis", total_count=total)

        results = {
            "total": total,
            "successful": 0,
            "failed": 0,
        }

        # Analyze each wallet
        for idx, wallet in enumerate(wallets, start=1):
            log.debug(
                "analyzing_wallet_batch_progress",
                current=idx,
                total=total,
                wallet_address=wallet.wallet_address[:8] + "...",
            )

            success = await self.analyze_wallet(
                wallet_address=wallet.wallet_address,
                token_launch_times=token_launch_times,
                transaction_limit=transaction_limit,
            )

            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1

        log.info(
            "bulk_wallet_performance_analysis_completed",
            total=results["total"],
            successful=results["successful"],
            failed=results["failed"],
            success_rate=f"{(results['successful'] / total * 100):.1f}%"
            if total > 0
            else "0.0%",
        )

        return results
