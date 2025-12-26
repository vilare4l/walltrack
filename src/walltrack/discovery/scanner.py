"""Wallet discovery engine for finding smart money wallets."""

import asyncio
import time
from datetime import datetime, timedelta
from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import (
    DiscoveryResult,
    TokenLaunch,
    Wallet,
    WalletProfile,
    WalletStatus,
)
from walltrack.data.neo4j.client import Neo4jClient
from walltrack.data.neo4j.queries.wallet import WalletQueries
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.profiler import WalletProfiler
from walltrack.services.helius.client import HeliusClient

log = structlog.get_logger()


class WalletDiscoveryScanner:
    """Discovers high-performing wallets from successful token launches."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        neo4j_client: Neo4jClient,
        helius_client: HeliusClient,
    ) -> None:
        self.wallet_repo = wallet_repo
        self.neo4j = neo4j_client
        self.helius = helius_client
        self.settings = get_settings()

    async def discover_from_token(
        self,
        token_launch: TokenLaunch,
        early_window_minutes: int = 30,
        min_profit_pct: float = 50.0,
    ) -> DiscoveryResult:
        """
        Discover wallets from a single token launch.

        Args:
            token_launch: Token launch data
            early_window_minutes: Window for "early buyer" definition
            min_profit_pct: Minimum profit percentage to qualify

        Returns:
            DiscoveryResult with counts and duration
        """
        start_time = time.time()
        new_count = 0
        updated_count = 0
        errors: list[str] = []

        log.info(
            "discovery_started",
            token=token_launch.mint,
            symbol=token_launch.symbol,
            early_window=early_window_minutes,
        )

        try:
            # Get early buyers from Helius
            early_buyers = await self._get_early_buyers(
                token_launch.mint,
                token_launch.launch_time,
                early_window_minutes,
            )

            log.info("early_buyers_found", count=len(early_buyers), token=token_launch.mint)

            # Filter to profitable exits
            profitable_wallets = await self._filter_profitable_wallets(
                early_buyers,
                token_launch.mint,
                min_profit_pct,
            )

            log.info(
                "profitable_wallets_found",
                count=len(profitable_wallets),
                token=token_launch.mint,
            )

            # Store each wallet
            for wallet_data in profitable_wallets:
                try:
                    wallet = Wallet(
                        address=wallet_data["address"],
                        status=WalletStatus.ACTIVE,
                        score=0.5,  # Default score, will be updated by profiler
                        profile=WalletProfile(
                            total_pnl=wallet_data.get("pnl", 0),
                            total_trades=wallet_data.get("trades", 1),
                        ),
                        discovery_tokens=[token_launch.mint],
                    )

                    # Upsert to Supabase
                    _, is_new = await self.wallet_repo.upsert(wallet)

                    # Create/update in Neo4j
                    async with self.neo4j.session() as session:
                        await WalletQueries.create_or_update_wallet(session, wallet)

                    # Profile the wallet to get accurate win rate and score
                    try:
                        profiler = WalletProfiler(self.wallet_repo, self.helius)
                        profiled_wallet = await profiler.profile_wallet(
                            wallet.address, force_update=True
                        )
                        if profiled_wallet:
                            log.info(
                                "wallet_profiled",
                                address=wallet.address[:12],
                                score=f"{profiled_wallet.score:.2f}",
                                win_rate=f"{profiled_wallet.profile.win_rate:.1%}",
                            )
                        # Rate limit between profiles
                        await asyncio.sleep(2.0)
                    except Exception as profile_err:
                        log.warning(
                            "wallet_profiling_skipped",
                            address=wallet.address[:12],
                            error=str(profile_err)[:50],
                        )

                    if is_new:
                        new_count += 1
                    else:
                        updated_count += 1

                except Exception as e:
                    log.error(
                        "wallet_storage_error",
                        address=wallet_data.get("address"),
                        error=str(e),
                    )
                    errors.append(f"Failed to store {wallet_data.get('address')}: {e!s}")

        except Exception as e:
            log.error("discovery_error", token=token_launch.mint, error=str(e))
            errors.append(f"Discovery failed: {e!s}")

        duration = time.time() - start_time

        result = DiscoveryResult(
            new_wallets=new_count,
            updated_wallets=updated_count,
            total_processed=new_count + updated_count,
            token_mint=token_launch.mint,
            duration_seconds=duration,
            errors=errors,
        )

        log.info(
            "discovery_completed",
            token=token_launch.mint,
            new=new_count,
            updated=updated_count,
            duration=f"{duration:.2f}s",
        )

        return result

    async def discover_from_multiple_tokens(
        self,
        token_launches: list[TokenLaunch],
        early_window_minutes: int = 30,
        min_profit_pct: float = 50.0,
        max_concurrent: int = 1,
    ) -> list[DiscoveryResult]:
        """
        Discover wallets from multiple token launches sequentially.

        Args:
            token_launches: List of token launches to analyze
            early_window_minutes: Window for "early buyer" definition
            min_profit_pct: Minimum profit percentage
            max_concurrent: Maximum concurrent discoveries (set to 1 to avoid rate limiting)

        Returns:
            List of DiscoveryResult for each token
        """
        valid_results: list[DiscoveryResult] = []

        for i, token in enumerate(token_launches):
            # Add delay between tokens to avoid Helius rate limiting
            if i > 0:
                await asyncio.sleep(2.0)

            try:
                result = await self.discover_from_token(
                    token, early_window_minutes, min_profit_pct
                )
                valid_results.append(result)
            except Exception as e:
                log.error(
                    "discovery_batch_error",
                    token=token.mint,
                    error=str(e),
                )

        return valid_results

    async def _get_early_buyers(
        self,
        token_mint: str,
        launch_time: datetime,
        window_minutes: int,
    ) -> list[dict[str, Any]]:
        """Get wallets that bought within the early window."""
        end_time = launch_time + timedelta(minutes=window_minutes)

        # Use Helius to get token transactions (SWAP type for buys)
        transactions = await self.helius.get_token_transactions(
            mint=token_mint,
            start_time=launch_time,
            end_time=end_time,
            tx_type="SWAP",  # Helius uses SWAP for trades
            limit=100,
        )

        # Extract unique buyer addresses from token transfers
        buyers: dict[str, dict[str, Any]] = {}
        for tx in transactions:
            # Get fee payer as potential buyer
            fee_payer = tx.get("feePayer")

            # Also check token transfers for receiver addresses
            for transfer in tx.get("tokenTransfers", []):
                # If this transfer involves our token and has a receiver
                if transfer.get("mint") == token_mint:
                    receiver = transfer.get("toUserAccount")
                    if receiver and receiver not in buyers:
                        buyers[receiver] = {
                            "address": receiver,
                            "first_buy_time": tx.get("timestamp"),
                            "buy_amount": transfer.get("tokenAmount", 0),
                        }

            # Fee payer is often the buyer
            if fee_payer and fee_payer not in buyers:
                buyers[fee_payer] = {
                    "address": fee_payer,
                    "first_buy_time": tx.get("timestamp"),
                    "buy_amount": 0,
                }

        return list(buyers.values())

    async def _filter_profitable_wallets(
        self,
        wallets: list[dict[str, Any]],
        token_mint: str,
        min_profit_pct: float,
    ) -> list[dict[str, Any]]:
        """Filter wallets to those with profitable exits."""
        profitable: list[dict[str, Any]] = []

        for i, wallet_data in enumerate(wallets):
            address = wallet_data["address"]

            # Rate limiting: add longer delay between Helius API calls
            if i > 0:
                await asyncio.sleep(1.5)

            try:
                # Get wallet's transactions (SWAP type for sells)
                txs = await self.helius.get_token_transactions(
                    mint=token_mint,
                    wallet=address,
                    tx_type="SWAP",
                    limit=50,
                )

                if not txs:
                    continue

                # Look for sells (transfers out of this wallet for this token)
                sell_amount = 0
                for tx in txs:
                    for transfer in tx.get("tokenTransfers", []):
                        if transfer.get("mint") == token_mint:
                            from_account = transfer.get("fromUserAccount")
                            if from_account == address:
                                sell_amount += transfer.get("tokenAmount", 0)

                # Calculate PnL
                buy_amount = wallet_data.get("buy_amount", 0)

                if buy_amount > 0 and sell_amount > 0:
                    profit_pct = ((sell_amount - buy_amount) / buy_amount) * 100

                    if profit_pct >= min_profit_pct:
                        wallet_data["pnl"] = sell_amount - buy_amount
                        wallet_data["profit_pct"] = profit_pct
                        wallet_data["trades"] = len(txs)
                        profitable.append(wallet_data)
                elif min_profit_pct <= 0:
                    # Include wallets without sells if min_profit is 0 or negative
                    wallet_data["pnl"] = 0
                    wallet_data["profit_pct"] = 0
                    wallet_data["trades"] = len(txs)
                    profitable.append(wallet_data)

            except Exception as e:
                # Skip wallets that return 404 or other errors
                log.debug(
                    "wallet_filter_skipped",
                    address=address[:20],
                    error=str(e)[:50],
                )
                continue

        return profitable
