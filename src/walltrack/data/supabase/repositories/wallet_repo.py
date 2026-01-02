"""Wallet repository for Supabase.

This module provides a repository pattern for accessing the wallets table
in Supabase, managing wallet discovery and performance metrics.

Table schema expected:
    wallets (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        wallet_address TEXT UNIQUE NOT NULL,
        discovery_count INTEGER DEFAULT 1,
        discovery_tokens TEXT[] DEFAULT '{}',
        discovered_at TIMESTAMPTZ DEFAULT NOW(),
        score DECIMAL(3,2),
        win_rate DECIMAL(5,2),
        pnl_total DECIMAL(20,8),
        entry_delay_seconds INTEGER,
        total_trades INTEGER DEFAULT 0,
        metrics_last_updated TIMESTAMPTZ,
        metrics_confidence TEXT DEFAULT 'unknown',
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""

from datetime import UTC, datetime

import structlog

from walltrack.data.models.wallet import PerformanceMetrics, Wallet, WalletStatus, WatchlistDecision
from walltrack.data.neo4j.queries import wallet as neo4j_wallet
from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger(__name__)


class WalletRepository:
    """Repository for accessing wallets table in Supabase.

    Provides CRUD operations for wallet records with specialized
    methods for wallet discovery and performance metrics updates.

    Attributes:
        _client: SupabaseClient instance for database operations.

    Example:
        client = await get_supabase_client()
        repo = WalletRepository(client)
        wallet = await repo.get_by_address("9xQeWvG...")
        await repo.update_performance_metrics("9xQeWvG...", metrics)
    """

    TABLE_NAME = "wallets"

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize repository with Supabase client.

        Args:
            client: Connected SupabaseClient instance.
        """
        self._client = client

    async def upsert_wallet(self, wallet: Wallet) -> Wallet:
        """Upsert wallet (insert or update on conflict).

        Args:
            wallet: Wallet model to upsert.

        Returns:
            Upserted Wallet model.

        Note:
            Uses wallet_address as the unique constraint for conflict resolution.
            On conflict, updates wallet fields.
        """
        try:
            # Prepare record for upsert
            now = datetime.now(UTC).isoformat()
            record = {
                "wallet_address": wallet.wallet_address,
                "discovery_date": wallet.discovery_date.isoformat()
                if wallet.discovery_date
                else now,
                "token_source": wallet.token_source,
                "score": wallet.score,
                "win_rate": wallet.win_rate,
                "pnl_total": wallet.pnl_total,
                "entry_delay_seconds": wallet.entry_delay_seconds,
                "total_trades": wallet.total_trades,
                "metrics_last_updated": wallet.metrics_last_updated.isoformat()
                if wallet.metrics_last_updated
                else None,
                "metrics_confidence": wallet.metrics_confidence,
                "decay_status": wallet.decay_status,
                "is_blacklisted": wallet.is_blacklisted,
                "updated_at": now,
            }

            # Perform upsert
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .upsert(record, on_conflict="wallet_address")
                .execute()
            )

            if not result.data:
                msg = f"Failed to upsert wallet {wallet.wallet_address}"
                raise ValueError(msg)

            log.info(
                "wallet_upserted",
                wallet_address=wallet.wallet_address[:8] + "...",
            )

            return Wallet(**result.data[0])

        except Exception as e:
            log.error(
                "wallet_upsert_failed",
                wallet_address=wallet.wallet_address[:8] + "...",
                error=str(e),
            )
            raise

    async def get_by_address(self, wallet_address: str) -> Wallet | None:
        """Get wallet by address.

        Args:
            wallet_address: Solana wallet address.

        Returns:
            Wallet if found, None otherwise.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .eq("wallet_address", wallet_address)
                .maybe_single()
                .execute()
            )

            if result.data:
                return Wallet(**result.data)
            return None

        except Exception as e:
            log.warning(
                "wallet_get_by_address_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return None

    async def get_all(self, limit: int = 1000) -> list[Wallet]:
        """Get all wallets from database.

        Args:
            limit: Maximum number of wallets to return.

        Returns:
            List of Wallet models ordered by score descending.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .order("score", desc=True, nullsfirst=False)
                .limit(limit)
                .execute()
            )

            wallets = []
            for row in result.data or []:
                wallets.append(Wallet(**row))

            return wallets

        except Exception as e:
            log.warning("wallets_get_all_failed", error=str(e))
            return []

    async def get_count(self) -> int:
        """Get total count of wallets in database.

        Returns:
            Number of wallets stored.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .execute()
            )

            return result.count or 0

        except Exception as e:
            log.warning("wallets_count_failed", error=str(e))
            return 0

    async def update_performance_metrics(
        self,
        wallet_address: str,
        metrics: PerformanceMetrics,
    ) -> bool:
        """Update wallet performance metrics.

        Updates the performance metrics fields (win_rate, pnl_total,
        entry_delay_seconds, total_trades, metrics_confidence) for
        the specified wallet.

        Args:
            wallet_address: Solana wallet address.
            metrics: PerformanceMetrics object with calculated values.

        Returns:
            True if update successful, False otherwise.

        Example:
            metrics = PerformanceMetrics(
                win_rate=75.0,
                pnl_total=2.5,
                entry_delay_seconds=3600,
                total_trades=10,
                confidence="medium",
            )
            success = await repo.update_performance_metrics(
                "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                metrics
            )
        """
        try:
            # Prepare update record
            now = datetime.now(UTC).isoformat()
            update_data = {
                "win_rate": metrics.win_rate,
                "pnl_total": metrics.pnl_total,
                "entry_delay_seconds": metrics.entry_delay_seconds,
                "total_trades": metrics.total_trades,
                "metrics_confidence": metrics.confidence,
                "metrics_last_updated": now,
                "updated_at": now,
            }

            # Execute update
            await (
                self._client.client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            log.info(
                "wallet_performance_metrics_updated",
                wallet_address=wallet_address[:8] + "...",
                win_rate=f"{metrics.win_rate:.1f}%",
                pnl_total=f"{metrics.pnl_total:+.4f} SOL",
                total_trades=metrics.total_trades,
                confidence=metrics.confidence,
            )

            return True

        except Exception as e:
            log.error(
                "wallet_performance_metrics_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return False

    async def update_behavioral_profile(
        self,
        wallet_address: str,
        position_size_style: str,
        position_size_avg: float,
        hold_duration_avg: int,
        hold_duration_style: str,
        behavioral_confidence: str,
    ) -> bool:
        """Update wallet behavioral profiling fields.

        Updates the behavioral profiling fields (position_size_style,
        position_size_avg, hold_duration_avg, hold_duration_style,
        behavioral_confidence, behavioral_last_updated) for the specified wallet.

        Args:
            wallet_address: Solana wallet address.
            position_size_style: Position size classification (small, medium, large).
            position_size_avg: Average position size in SOL.
            hold_duration_avg: Average hold duration in seconds.
            hold_duration_style: Hold duration classification (scalper, day_trader, etc.).
            behavioral_confidence: Confidence level (unknown, low, medium, high).

        Returns:
            True if update successful, False otherwise.

        Example:
            success = await repo.update_behavioral_profile(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                position_size_style="medium",
                position_size_avg=2.5,
                hold_duration_avg=7200,
                hold_duration_style="day_trader",
                behavioral_confidence="medium",
            )
        """
        try:
            # Prepare update record
            now = datetime.now(UTC).isoformat()
            update_data = {
                "position_size_style": position_size_style,
                "position_size_avg": position_size_avg,
                "hold_duration_avg": hold_duration_avg,
                "hold_duration_style": hold_duration_style,
                "behavioral_confidence": behavioral_confidence,
                "behavioral_last_updated": now,
                "updated_at": now,
            }

            # Execute update
            await (
                self._client.client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            log.info(
                "wallet_behavioral_profile_updated",
                wallet_address=wallet_address[:8] + "...",
                position_style=position_size_style,
                hold_style=hold_duration_style,
                confidence=behavioral_confidence,
            )

            return True

        except Exception as e:
            log.error(
                "wallet_behavioral_profile_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return False

    async def update_behavioral_profile_full(
        self,
        wallet_address: str,
        position_size_style: str,
        position_size_avg: float,
        hold_duration_avg: int,
        hold_duration_style: str,
        behavioral_confidence: str,
    ) -> bool:
        """Update behavioral profile in both Supabase and Neo4j.

        This is the integrated method that synchronizes behavioral profiling
        data across both databases. It updates:
        - Supabase: wallets table behavioral fields
        - Neo4j: Wallet node behavioral properties

        Args:
            wallet_address: Solana wallet address.
            position_size_style: Position size classification (small, medium, large).
            position_size_avg: Average position size in SOL.
            hold_duration_avg: Average hold duration in seconds.
            hold_duration_style: Hold duration classification (scalper, day_trader, etc.).
            behavioral_confidence: Confidence level (unknown, low, medium, high).

        Returns:
            True if both updates successful, False otherwise.

        Note:
            Updates are performed sequentially. If Supabase fails, Neo4j is not called.
            If Neo4j fails, Supabase changes are already committed (not transactional).

        Example:
            success = await repo.update_behavioral_profile_full(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                position_size_style="medium",
                position_size_avg=2.5,
                hold_duration_avg=7200,
                hold_duration_style="day_trader",
                behavioral_confidence="medium",
            )
        """
        # Step 0: Fetch current state for rollback in case of failure
        current_wallet = await self.get_by_address(wallet_address)
        if not current_wallet:
            log.error(
                "behavioral_profile_full_update_wallet_not_found",
                wallet_address=wallet_address[:8] + "...",
            )
            return False

        # Store original values for rollback
        original_position_size_style = current_wallet.position_size_style
        original_position_size_avg = current_wallet.position_size_avg
        original_hold_duration_avg = current_wallet.hold_duration_avg
        original_hold_duration_style = current_wallet.hold_duration_style
        original_behavioral_confidence = current_wallet.behavioral_confidence

        # Step 1: Update Supabase
        supabase_success = await self.update_behavioral_profile(
            wallet_address=wallet_address,
            position_size_style=position_size_style,
            position_size_avg=position_size_avg,
            hold_duration_avg=hold_duration_avg,
            hold_duration_style=hold_duration_style,
            behavioral_confidence=behavioral_confidence,
        )

        if not supabase_success:
            log.error(
                "behavioral_profile_full_update_failed_supabase",
                wallet_address=wallet_address[:8] + "...",
            )
            return False

        # Step 2: Update Neo4j
        try:
            await neo4j_wallet.update_wallet_behavioral_profile(
                wallet_address=wallet_address,
                position_size_style=position_size_style,
                position_size_avg=position_size_avg,
                hold_duration_avg=hold_duration_avg,
                hold_duration_style=hold_duration_style,
            )

            log.info(
                "behavioral_profile_full_update_complete",
                wallet_address=wallet_address[:8] + "...",
            )

            return True

        except Exception as e:
            log.error(
                "behavioral_profile_full_update_failed_neo4j",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            # Rollback Supabase to original state
            log.warning(
                "behavioral_profile_rollback_supabase",
                wallet_address=wallet_address[:8] + "...",
            )
            await self.update_behavioral_profile(
                wallet_address=wallet_address,
                position_size_style=original_position_size_style,
                position_size_avg=original_position_size_avg,
                hold_duration_avg=original_hold_duration_avg,
                hold_duration_style=original_hold_duration_style,
                behavioral_confidence=original_behavioral_confidence,
            )
            return False

    async def update_decay_status(
        self,
        wallet_address: str,
        decay_status: str,
        score: float,
        rolling_win_rate: float | None,
        consecutive_losses: int,
        last_activity_date: datetime | None,
    ) -> bool:
        """Update wallet decay detection fields.

        Updates decay_status, score, rolling_win_rate, consecutive_losses,
        and last_activity_date for the specified wallet.

        Args:
            wallet_address: Solana wallet address.
            decay_status: New decay status (ok, flagged, downgraded, dormant).
            score: Updated wallet score (0.1 to 1.0).
            rolling_win_rate: Win rate over most recent trades (0.0 to 1.0).
            consecutive_losses: Number of consecutive losing trades.
            last_activity_date: Date of last trading activity.

        Returns:
            True if update successful, False otherwise.

        Example:
            success = await repo.update_decay_status(
                wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
                decay_status="flagged",
                score=0.68,
                rolling_win_rate=0.35,
                consecutive_losses=0,
                last_activity_date=datetime.now(UTC),
            )
        """
        try:
            # Prepare update record
            now = datetime.now(UTC).isoformat()
            update_data = {
                "decay_status": decay_status,
                "score": score,
                "rolling_win_rate": rolling_win_rate,
                "consecutive_losses": consecutive_losses,
                "last_activity_date": (
                    last_activity_date.isoformat() if last_activity_date else None
                ),
                "updated_at": now,
            }

            # Execute update
            await (
                self._client.client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            log.info(
                "wallet_decay_status_updated",
                wallet_address=wallet_address[:8] + "...",
                decay_status=decay_status,
                score=f"{score:.4f}",
                rolling_win_rate=(
                    f"{rolling_win_rate:.2%}" if rolling_win_rate is not None else "N/A"
                ),
                consecutive_losses=consecutive_losses,
            )

            return True

        except Exception as e:
            log.error(
                "wallet_decay_status_update_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return False

    async def update_status(
        self,
        wallet_address: str,
        status: WalletStatus,
    ) -> None:
        """Update wallet status (simple status transition).

        Updates only the wallet_status column. Use this for simple
        status transitions (e.g., discovered → profiled).

        For watchlist status updates with metadata (score, reason),
        use update_watchlist_status() instead.

        Args:
            wallet_address: Solana wallet address.
            status: New wallet status.

        Raises:
            Exception: If Supabase update fails.

        Example:
            # Mark wallet as profiled after analysis
            await repo.update_status(
                "9xQeWvG...",
                WalletStatus.PROFILED
            )
        """
        try:
            response = await (
                self._client.client.table("wallets")
                .update({"wallet_status": status.value})
                .eq("wallet_address", wallet_address)
                .execute()
            )

            if not response.data:
                log.warning(
                    "wallet_status_update_no_match",
                    wallet_address=wallet_address[:8] + "...",
                    status=status.value,
                )
            else:
                log.info(
                    "wallet_status_updated",
                    wallet_address=wallet_address[:8] + "...",
                    status=status.value,
                )

        except Exception as e:
            log.error(
                "wallet_status_update_failed",
                wallet_address=wallet_address[:8] + "...",
                status=status.value,
                error=str(e),
            )
            raise

    async def update_watchlist_status(
        self,
        wallet_address: str,
        decision: WatchlistDecision,
        manual: bool = False,
        previous_status: WalletStatus | None = None,
    ) -> None:
        """Update wallet watchlist status and metadata.

        Updates wallet_status, watchlist_score, watchlist_reason,
        watchlist_added_date (if status='watchlisted'), and manual_override.

        Also synchronizes watchlist status to Neo4j wallet node (best-effort).

        Args:
            wallet_address: Solana wallet address.
            decision: WatchlistDecision with status, score, and reason.
            manual: Whether this is a manual override (default: False).
            previous_status: Previous wallet status for transition logging (optional).

        Raises:
            Exception: If Supabase update fails (Neo4j sync is best-effort).

        Example:
            decision = WatchlistDecision(
                status=WalletStatus.WATCHLISTED,
                score=Decimal("0.8523"),
                reason="Meets all criteria",
                timestamp=datetime.utcnow(),
            )
            await repo.update_watchlist_status(
                "9xQeWvG...",
                decision,
                manual=False,
                previous_status=WalletStatus.PROFILED
            )
        """
        # Step 1: Update Supabase (critical - will raise on failure)
        try:
            # Prepare update record
            now = datetime.now(UTC).isoformat()
            update_data = {
                "wallet_status": decision.status.value,
                "watchlist_score": float(decision.score),
                "watchlist_reason": decision.reason,
                "manual_override": manual,
                "updated_at": now,
            }

            # Set watchlist_added_date if status changed to 'watchlisted'
            if decision.status == WalletStatus.WATCHLISTED:
                update_data["watchlist_added_date"] = now

            # Execute Supabase update
            await (
                self._client.client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            # Log status transition (AC1: "status transition is logged with timestamp and reason")
            if previous_status:
                log.info(
                    "wallet_status_transition",
                    wallet_address=wallet_address[:8] + "...",
                    transition=f"{previous_status.value} → {decision.status.value}",
                    score=float(decision.score),
                    reason=decision.reason,
                    timestamp=now,
                    manual=manual,
                )
            else:
                log.info(
                    "wallet_watchlist_status_updated_supabase",
                    wallet_address=wallet_address[:8] + "...",
                    status=decision.status.value,
                    score=float(decision.score),
                    manual=manual,
                )

        except Exception as e:
            log.error(
                "wallet_watchlist_status_update_failed_supabase",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        # Step 2: Synchronize to Neo4j (best-effort - non-fatal)
        try:
            await neo4j_wallet.update_wallet_watchlist_status(
                wallet_address=wallet_address,
                status=decision.status.value,
                score=float(decision.score),
            )

            log.debug(
                "wallet_watchlist_status_synced_neo4j",
                wallet_address=wallet_address[:8] + "...",
            )

        except Exception as neo4j_error:
            # Neo4j sync failure is non-fatal (best-effort pattern)
            log.warning(
                "wallet_watchlist_status_neo4j_sync_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(neo4j_error),
            )

    async def get_wallets_by_status(self, status: WalletStatus) -> list[Wallet]:
        """Get all wallets with specified status.

        Args:
            status: WalletStatus to filter by.

        Returns:
            List of Wallet models with matching status, ordered by watchlist_score descending.

        Example:
            watchlisted_wallets = await repo.get_wallets_by_status(WalletStatus.WATCHLISTED)
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("*")
                .eq("wallet_status", status.value)
                .order("watchlist_score", desc=True, nullsfirst=False)
                .execute()
            )

            wallets = []
            for row in result.data or []:
                wallets.append(Wallet(**row))

            log.info(
                "wallets_fetched_by_status",
                status=status.value,
                count=len(wallets),
            )

            return wallets

        except Exception as e:
            log.error(
                "wallets_get_by_status_failed",
                status=status.value,
                error=str(e),
            )
            return []

    async def get_watchlist_count(self) -> int:
        """Get count of wallets with 'watchlisted' status.

        Returns:
            Number of watchlisted wallets.

        Example:
            count = await repo.get_watchlist_count()
            # count = 42
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("id", count="exact")
                .eq("wallet_status", WalletStatus.WATCHLISTED.value)
                .execute()
            )

            count = result.count or 0
            log.debug("watchlist_count_fetched", count=count)
            return count

        except Exception as e:
            log.error("watchlist_count_failed", error=str(e))
            return 0

    async def blacklist_wallet(self, wallet_address: str, reason: str) -> None:
        """Blacklist a wallet with reason.

        Sets wallet_status to 'blacklisted' and stores reason in watchlist_reason.

        Args:
            wallet_address: Solana wallet address.
            reason: Reason for blacklisting (e.g., "Suspicious activity", "Scammer").

        Raises:
            Exception: If Supabase update fails (Neo4j sync is best-effort).

        Example:
            await repo.blacklist_wallet("9xQeWvG...", "Suspected bot activity")
        """
        # Step 1: Update Supabase (critical - will raise on failure)
        try:
            now = datetime.now(UTC).isoformat()
            update_data = {
                "wallet_status": WalletStatus.BLACKLISTED.value,
                "watchlist_reason": f"Blacklisted: {reason}",
                "manual_override": True,  # Blacklist is always manual
                "updated_at": now,
            }

            await (
                self._client.client.table(self.TABLE_NAME)
                .update(update_data)
                .eq("wallet_address", wallet_address)
                .execute()
            )

            log.warning(
                "wallet_blacklisted_supabase",
                wallet_address=wallet_address[:8] + "...",
                reason=reason,
            )

        except Exception as e:
            log.error(
                "wallet_blacklist_failed_supabase",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            raise

        # Step 2: Synchronize to Neo4j (best-effort - non-fatal)
        try:
            await neo4j_wallet.update_wallet_watchlist_status(
                wallet_address=wallet_address,
                status=WalletStatus.BLACKLISTED.value,
                score=0.0,  # Blacklisted wallets get 0 score
            )

            log.debug(
                "wallet_blacklisted_synced_neo4j",
                wallet_address=wallet_address[:8] + "...",
            )

        except Exception as neo4j_error:
            # Neo4j sync failure is non-fatal (best-effort pattern)
            log.warning(
                "wallet_blacklist_neo4j_sync_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(neo4j_error),
            )

    async def delete_by_address(self, wallet_address: str) -> bool:
        """Delete wallet by address.

        Args:
            wallet_address: Solana wallet address.

        Returns:
            True if deleted, False otherwise.
        """
        try:
            await (
                self._client.client.table(self.TABLE_NAME)
                .delete()
                .eq("wallet_address", wallet_address)
                .execute()
            )
            log.info("wallet_deleted", wallet_address=wallet_address[:8] + "...")
            return True

        except Exception as e:
            log.warning(
                "wallet_delete_failed",
                wallet_address=wallet_address[:8] + "...",
                error=str(e),
            )
            return False
