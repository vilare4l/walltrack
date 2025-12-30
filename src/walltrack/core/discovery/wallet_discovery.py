"""Wallet discovery service for extracting smart money wallets from early profitable buyers.

This module provides functionality to discover wallet addresses from token transactions
by analyzing early profitable buyers via Helius transaction history API.

Approach: Find wallets that bought within 30min of token launch AND sold with >50% profit.
This identifies "smart money" - traders who captured the pump, not bag holders.

Classes:
    WalletDiscoveryService: Main service for wallet discovery operations
"""

from datetime import UTC, datetime

import structlog

from walltrack.data.models.token import Token
from walltrack.data.models.wallet import WalletCreate
from walltrack.data.neo4j.services.wallet_sync import sync_wallet_to_neo4j
from walltrack.data.repositories.wallet_repository import WalletRepository
from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.services.helius.client import HeliusClient
from walltrack.services.helius.models import SwapDetails, Transaction

log = structlog.get_logger(__name__)

# Known program addresses to exclude (DEX contracts, protocols)
KNOWN_PROGRAM_ADDRESSES = {
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",  # Jupiter Aggregator
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",  # Orca Whirlpools
    "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",  # Serum DEX V3
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL Token Program
    "11111111111111111111111111111111",  # System Program
}


class WalletDiscoveryService:
    """Service for discovering smart money wallet addresses from early profitable buyers.

    Discovers wallets by analyzing transaction history via Helius API.
    Identifies "smart money" using two filters:
    - Filter #1: Early Entry (bought within 30min of token launch)
    - Filter #2: Profitable Exit (sold with >50% profit)

    Attributes:
        helius_client: Helius API client for fetching transaction history.
        wallet_repository: Repository for wallet storage operations.
        token_repository: Repository for token operations.

    Example:
        service = WalletDiscoveryService()
        wallets = await service.discover_wallets_from_token("token_mint_address")
        # Returns list of wallet addresses (early profitable buyers)
    """

    def __init__(
        self,
        helius_client: HeliusClient | None = None,
        wallet_repository: WalletRepository | None = None,
        token_repository: TokenRepository | None = None,
        max_transactions: int = 5000,  # FIXED: Configurable instead of hardcoded 1000
        early_window_minutes: int = 30,  # FIXED: Configurable early entry window
        min_profit_ratio: float = 0.50,  # FIXED: Configurable minimum profit (50%)
    ) -> None:
        """Initialize wallet discovery service.

        Args:
            helius_client: Optional Helius client (creates default if None).
            wallet_repository: Optional wallet repo (creates default if None).
            token_repository: Optional token repo (will be created lazily if None).
            max_transactions: Max transactions to fetch from Helius (default: 5000,
                             capped at 1000 due to Helius API limit).
            early_window_minutes: Early entry window in minutes (default: 30).
            min_profit_ratio: Minimum profit ratio to qualify (default: 0.50 = 50%).

        Note:
            - max_transactions is automatically capped at 1000 (Helius API limit)
            - Helius API has rate limits, consider pagination for very popular tokens
            - Business logic (early_window, min_profit) is now configurable
        """
        self.helius_client = helius_client or HeliusClient()
        self.wallet_repository = wallet_repository or WalletRepository()
        self._token_repository = token_repository
        
        # FIXED: Configurable business logic parameters
        # Cap max_transactions at 1000 (Helius API limit)
        self.max_transactions = min(max_transactions, 1000)
        self.early_window_minutes = early_window_minutes
        self.min_profit_ratio = min_profit_ratio
        
        log.debug(
            "wallet_discovery_service_initialized",
            max_transactions=self.max_transactions,  # Log capped value
            early_window_minutes=early_window_minutes,
            min_profit_ratio=min_profit_ratio,
        )

    async def _get_token_repository(self) -> TokenRepository:
        """Get or create TokenRepository instance (lazy initialization).

        Returns:
            TokenRepository instance.
        """
        if self._token_repository is None:
            from walltrack.data.supabase.client import get_supabase_client

            supabase_client = await get_supabase_client()
            self._token_repository = TokenRepository(supabase_client)
            log.debug("token_repository_initialized_lazily")
        return self._token_repository

    async def discover_wallets_from_token(
        self,
        token_address: str,
        token_created_at: str | None = None,
    ) -> list[str]:
        """Discover early profitable buyer wallet addresses for a token.

        Analyzes transaction history to find "smart money" - wallets that:
        1. Bought within 30min of token launch (early entry)
        2. Sold with >50% profit (profitable exit)

        This approach finds traders who PERFORMED (captured the pump),
        not bag holders who still hold (no performance guarantee).

        Logic:
            1. Parse token launch time to timestamp
            2. Fetch swap transactions via Helius API
            3. Parse BUY and SELL transactions for each wallet using SwapDetails
            4. Filter #1: Early Entry (earliest BUY within 30min of launch)
            5. Filter #2: Profitable Exit (SELL with >50% profit)
            6. Return unique wallet addresses that match BOTH filters

        Args:
            token_address: Solana token mint address (base58 format).
            token_created_at: Token launch timestamp (ISO format).
                             If None, fetches from database.

        Returns:
            List of wallet addresses (early profitable buyers).
            Returns empty list if no profitable buyers found.

        Note:
            - Excludes known program addresses (DEX contracts)
            - Handles partial transactions (BUY without SELL = skip)
            - Max 1000 transactions analyzed (Helius limit)
        """
        # FIXED: Validate token_address format (Solana base58, 32-44 chars)
        if not (32 <= len(token_address) <= 44):
            log.error(
                "invalid_token_address_length",
                token_address=token_address,
                length=len(token_address),
            )
            return []

        base58_chars = set("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz")
        if not set(token_address).issubset(base58_chars):
            log.error(
                "invalid_token_address_characters",
                token_address=token_address,
            )
            return []

        log.info(
            "discovering_early_profitable_buyers",
            token_address=token_address[:8] + "...",
        )

        # Fetch token_created_at from database if not provided
        if not token_created_at:
            token_repo = await self._get_token_repository()
            token = await token_repo.get_by_mint(token_address)

            if not token or not token.created_at:
                log.warning(
                    "token_not_found_or_no_created_at",
                    token_address=token_address[:8] + "...",
                )
                return []

            # Convert datetime to ISO format for parsing
            token_created_at = token.created_at.isoformat()
            log.debug(
                "token_created_at_fetched_from_database",
                token_address=token_address[:8] + "...",
                created_at=token_created_at,
            )

        # Parse token launch time to Unix timestamp
        # FIXED: Added timezone awareness to prevent local timezone issues
        token_launch_dt = datetime.fromisoformat(token_created_at)

        # Force UTC if no timezone info (defensive programming)
        if token_launch_dt.tzinfo is None:
            token_launch_dt = token_launch_dt.replace(tzinfo=UTC)
            log.warning(
                "token_created_at_missing_timezone_assuming_utc",
                token_address=token_address[:8] + "...",
            )

        token_launch_timestamp = int(token_launch_dt.timestamp())

        # Fetch swap transactions for this token
        # FIXED: Use configurable max_transactions instead of hardcoded 1000
        transactions_data = await self.helius_client.get_token_transactions(
            token_mint=token_address,
            limit=self.max_transactions,
            tx_type="SWAP",
        )

        log.debug(
            "fetched_transactions_from_helius",
            token_address=token_address[:8] + "...",
            transaction_count=len(transactions_data) if transactions_data else 0,
            max_limit=self.max_transactions,
        )

        if not transactions_data:
            log.debug(
                "no_transactions_found",
                token_address=token_address[:8] + "...",
            )
            return []

        # Parse transactions into Pydantic models
        # NOTE: Potential memory issue for very popular tokens with 5000+ transactions
        # Consider streaming/batch processing if memory usage becomes problematic
        transactions = [Transaction(**tx_data) for tx_data in transactions_data]

        # Group transactions by wallet address (extract from tokenTransfers)
        wallet_swaps: dict[str, list[Transaction]] = {}
        for tx in transactions:
            # Extract wallet addresses from token transfers (participants in this token's swaps)
            for token_transfer in tx.token_transfers:
                # Only process transfers of THIS token (not other tokens in the swap)
                if token_transfer.mint != token_address:
                    continue

                # Wallet is either sender or receiver of tokens
                for wallet_addr in {
                    token_transfer.from_user_account,
                    token_transfer.to_user_account,
                }:
                    # Filter out program addresses
                    if wallet_addr in KNOWN_PROGRAM_ADDRESSES:
                        continue

                    # Track this wallet's transactions
                    if wallet_addr not in wallet_swaps:
                        wallet_swaps[wallet_addr] = []
                    wallet_swaps[wallet_addr].append(tx)

        # Apply early profitable buyer filtering
        profitable_buyers: list[str] = []

        for wallet_address, txs in wallet_swaps.items():
            # Parse swaps for this wallet using SwapDetails
            buy_swaps: list[SwapDetails] = []
            sell_swaps: list[SwapDetails] = []

            for tx in txs:
                swap = SwapDetails.from_transaction(tx, wallet_address, token_address)
                if not swap:
                    continue

                if swap.direction == "BUY":
                    buy_swaps.append(swap)
                elif swap.direction == "SELL":
                    sell_swaps.append(swap)

            # Skip if no BUY or no SELL (incomplete trade)
            if not buy_swaps or not sell_swaps:
                log.debug(
                    "wallet_skipped_incomplete_trade",
                    wallet_address=wallet_address[:8] + "...",
                    buys=len(buy_swaps),
                    sells=len(sell_swaps),
                )
                continue

            # Find earliest BUY timestamp
            earliest_buy = min(buy_swaps, key=lambda s: s.timestamp)

            # Filter #1: Early Entry (configurable window after token launch)
            # FIXED: Use configurable early_window_minutes instead of hardcoded 30
            time_since_launch = earliest_buy.timestamp - token_launch_timestamp
            early_window_seconds = self.early_window_minutes * 60

            if time_since_launch > early_window_seconds:
                log.debug(
                    "wallet_filtered_late_entry",
                    wallet_address=wallet_address[:8] + "...",
                    minutes_after_launch=time_since_launch // 60,
                )
                continue

            # Calculate total BUY and SELL amounts (SOL and tokens)
            total_buy_sol = sum(swap.sol_amount for swap in buy_swaps)
            total_sell_sol = sum(swap.sol_amount for swap in sell_swaps)
            total_tokens_bought = sum(swap.token_amount for swap in buy_swaps)
            total_tokens_sold = sum(swap.token_amount for swap in sell_swaps)

            # Filter #2a: Check for complete or near-complete position exit
            # FIXED: Verify wallet sold at least 90% of tokens to avoid counting partial sells
            if total_tokens_bought == 0 or total_buy_sol == 0:
                continue

            sell_ratio = total_tokens_sold / total_tokens_bought

            if sell_ratio < 0.90:  # Must sell at least 90% of position
                log.debug(
                    "wallet_filtered_incomplete_exit",
                    wallet_address=wallet_address[:8] + "...",
                    sold_percent=int(sell_ratio * 100),
                )
                continue

            # Filter #2b: Profitable Exit (configurable minimum profit)
            # FIXED: Use configurable min_profit_ratio instead of hardcoded 0.50
            profit_ratio = (total_sell_sol - total_buy_sol) / total_buy_sol

            if profit_ratio < self.min_profit_ratio:
                log.debug(
                    "wallet_filtered_insufficient_profit",
                    wallet_address=wallet_address[:8] + "...",
                    profit_percent=int(profit_ratio * 100),
                )
                continue

            # Wallet passed BOTH filters → early profitable buyer!
            profitable_buyers.append(wallet_address)
            log.debug(
                "profitable_buyer_found",
                wallet_address=wallet_address[:8] + "...",
                minutes_after_launch=time_since_launch // 60,
                profit_percent=int(profit_ratio * 100),
            )

        log.info(
            "early_profitable_buyers_discovered",
            token_address=token_address[:8] + "...",
            total_wallets=len(wallet_swaps),
            profitable_buyers=len(profitable_buyers),
        )

        return profitable_buyers

    async def run_wallet_discovery(self) -> dict[str, int]:
        """Run complete wallet discovery orchestration.

        Discovers wallets from all tokens that haven't been processed yet,
        stores new wallets in both Supabase and Neo4j, and updates token flags.

        Process:
            1. Fetch tokens where wallets_discovered = False
            2. For each token: discover wallet holders
            3. For each discovered wallet:
               - Create in Supabase (idempotent - PRIMARY KEY prevents duplicates)
               - Sync to Neo4j (idempotent - MERGE prevents duplicates)
            4. Mark token as processed (wallets_discovered = TRUE)
            5. Return statistics

        Returns:
            Dict with stats:
                - tokens_processed: Number of tokens processed
                - wallets_discovered: Total wallets found across all tokens
                - wallets_new: New wallets inserted (excluding duplicates)
                - wallets_existing: Wallets already in database (duplicates)
                - errors: Number of errors encountered

        Note:
            - Multi-token logic: Same wallet from multiple tokens stored once
            - PRIMARY KEY on wallet_address prevents duplicates
            - First token discovery is kept as token_source
            - Errors are logged but don't stop the entire process
            - FIXED: Removed TOCTOU race condition by relying on idempotent operations

        Example:
            service = WalletDiscoveryService()
            stats = await service.run_wallet_discovery()
            # Returns: {"tokens_processed": 5, "wallets_discovered": 120, ...}
        """
        log.info("starting_wallet_discovery_orchestration")

        tokens_processed = 0
        wallets_discovered_total = 0
        wallets_new = 0
        wallets_existing = 0
        errors = 0

        try:
            # 1. Get tokens where wallets not yet discovered
            token_repo = await self._get_token_repository()
            tokens = await token_repo.get_undiscovered_tokens()

            if not tokens:
                log.info("no_tokens_to_discover_wallets_from")
                return {
                    "tokens_processed": 0,
                    "wallets_discovered": 0,
                    "wallets_new": 0,
                    "wallets_existing": 0,
                    "errors": 0,
                }

            log.info("tokens_to_process", count=len(tokens))

            # 2. Process each token
            for token in tokens:
                try:
                    log.info(
                        "processing_token_for_wallet_discovery",
                        token_mint=token.mint[:8] + "...",
                    )

                    # 2a. Discover wallets from this token
                    wallet_addresses = await self.discover_wallets_from_token(token.mint)

                    wallets_discovered_total += len(wallet_addresses)

                    # 2b. Process each discovered wallet
                    for wallet_address in wallet_addresses:
                        try:
                            # Create wallet in Supabase (idempotent - PRIMARY KEY prevents duplicates)
                            # FIXED: No pre-check to avoid TOCTOU race condition
                            wallet_create = WalletCreate(
                                wallet_address=wallet_address,
                                token_source=token.mint,
                            )

                            created_wallet = await self.wallet_repository.create_wallet(
                                wallet_create
                            )

                            if created_wallet:
                                # New wallet created
                                wallets_new += 1
                                log.info(
                                    "new_wallet_created",
                                    wallet_address=wallet_address[:8] + "...",
                                    token_source=token.mint[:8] + "...",
                                )
                            else:
                                # Wallet already exists (duplicate)
                                wallets_existing += 1
                                log.debug(
                                    "wallet_already_exists",
                                    wallet_address=wallet_address[:8] + "...",
                                )

                            # FIXED: ALWAYS sync to Neo4j (idempotent MERGE operation)
                            # This ensures consistency even if wallet was created in a previous run
                            sync_result = await sync_wallet_to_neo4j(wallet_address)
                            
                            if not sync_result:
                                # Neo4j sync failed - log for manual retry
                                errors += 1
                                log.error(
                                    "neo4j_sync_failed_needs_retry",
                                    wallet_address=wallet_address[:8] + "...",
                                    token_source=token.mint[:8] + "...",
                                )

                        except Exception as e:
                            errors += 1
                            log.error(
                                "wallet_processing_error",
                                wallet_address=wallet_address[:8] + "...",
                                error=str(e),
                            )
                            # Continue with next wallet

                    # 3. Mark token as discovered
                    # NOTE: Non-atomic workflow - if crash occurs after creating wallets but before
                    # marking token, wallets exist but token will be re-processed (idempotent operations
                    # prevent duplicates but waste resources). Consider using DB transactions or
                    # marking token BEFORE wallet creation for better consistency.
                    await token_repo.mark_wallets_discovered(token.mint)
                    tokens_processed += 1

                    log.info(
                        "token_discovery_completed",
                        token_mint=token.mint[:8] + "...",
                        wallets_found=len(wallet_addresses),
                    )

                except Exception as e:
                    errors += 1
                    log.error(
                        "token_processing_error",
                        token_mint=token.mint[:8] + "...",
                        error=str(e),
                    )
                    # Continue with next token

        except Exception as e:
            log.error("wallet_discovery_orchestration_error", error=str(e))
            errors += 1

        stats = {
            "tokens_processed": tokens_processed,
            "wallets_discovered": wallets_discovered_total,
            "wallets_new": wallets_new,
            "wallets_existing": wallets_existing,
            "errors": errors,
        }

        log.info("wallet_discovery_orchestration_completed", **stats)

        return stats
