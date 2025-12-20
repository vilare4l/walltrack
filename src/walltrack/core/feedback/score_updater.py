"""Wallet score update service."""

from collections import deque
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from .score_models import (
    BatchUpdateRequest,
    BatchUpdateResult,
    ScoreUpdateConfig,
    ScoreUpdateInput,
    ScoreUpdateResult,
    ScoreUpdateType,
    WalletMetrics,
    WalletScoreHistory,
)

logger = structlog.get_logger()


class WalletScoreUpdater:
    """Updates wallet scores based on trade outcomes."""

    def __init__(self, supabase_client, config: ScoreUpdateConfig | None = None):
        """Initialize WalletScoreUpdater.

        Args:
            supabase_client: Supabase client instance
            config: Optional score update configuration
        """
        self.supabase = supabase_client
        self.config = config or ScoreUpdateConfig()
        self._rolling_windows: dict[str, deque] = {}
        self._metrics_cache: dict[str, WalletMetrics] = {}

    async def update_from_trade(
        self,
        update_input: ScoreUpdateInput,
    ) -> ScoreUpdateResult:
        """Update wallet score based on trade outcome.

        Args:
            update_input: Trade outcome data

        Returns:
            ScoreUpdateResult with new score and flags
        """
        # Get current metrics (from cache or database)
        metrics = await self.get_wallet_metrics(update_input.wallet_address)

        if metrics is None:
            # Initialize new wallet
            metrics = WalletMetrics(
                wallet_address=update_input.wallet_address,
                current_score=Decimal("0.5"),  # Start at neutral
            )

        previous_score = metrics.current_score

        # Calculate score change
        if update_input.is_win:
            score_change = self._calculate_win_impact(update_input.pnl_percent)
        else:
            score_change = self._calculate_loss_impact(update_input.pnl_percent)

        # Apply change with bounds
        new_score = max(Decimal("0"), min(Decimal("1"), previous_score + score_change))

        # Update metrics
        metrics.current_score = new_score
        metrics.lifetime_trades += 1
        metrics.lifetime_pnl += update_input.pnl_sol
        metrics.last_trade_timestamp = datetime.now(UTC)
        metrics.last_score_update = datetime.now(UTC)

        if update_input.is_win:
            metrics.lifetime_wins += 1
        else:
            metrics.lifetime_losses += 1

        # Update rolling window
        self._update_rolling_window(
            update_input.wallet_address,
            update_input.is_win,
            update_input.pnl_sol,
        )
        await self._recalculate_rolling_metrics(metrics)

        # Check for flags
        triggered_flag = False
        triggered_blacklist = False

        if new_score < self.config.decay_flag_threshold and not metrics.is_flagged:
            metrics.is_flagged = True
            triggered_flag = True
            logger.warning(
                "wallet_flagged_for_decay",
                wallet=update_input.wallet_address,
                score=float(new_score),
                threshold=float(self.config.decay_flag_threshold),
            )

        if new_score < self.config.blacklist_threshold and not metrics.is_blacklisted:
            metrics.is_blacklisted = True
            triggered_blacklist = True
            logger.warning(
                "wallet_blacklisted",
                wallet=update_input.wallet_address,
                score=float(new_score),
                threshold=float(self.config.blacklist_threshold),
            )

        # Update cache
        self._metrics_cache[update_input.wallet_address] = metrics

        # Persist changes
        await self._save_metrics(metrics)

        # Record history
        await self._record_history(
            wallet_address=update_input.wallet_address,
            score=new_score,
            previous_score=previous_score,
            change=score_change,
            update_type=ScoreUpdateType.TRADE_OUTCOME,
            trade_id=update_input.trade_id,
        )

        result = ScoreUpdateResult(
            wallet_address=update_input.wallet_address,
            previous_score=previous_score,
            new_score=new_score,
            score_change=score_change,
            update_type=ScoreUpdateType.TRADE_OUTCOME,
            trade_id=update_input.trade_id,
            triggered_flag=triggered_flag,
            triggered_blacklist=triggered_blacklist,
        )

        logger.info(
            "wallet_score_updated",
            wallet=update_input.wallet_address,
            previous=float(previous_score),
            new=float(new_score),
            change=float(score_change),
            is_win=update_input.is_win,
        )

        return result

    async def batch_update(
        self,
        request: BatchUpdateRequest,
    ) -> BatchUpdateResult:
        """Process batch of score updates efficiently.

        Args:
            request: Batch update request

        Returns:
            BatchUpdateResult with individual results
        """
        result = BatchUpdateResult()

        # Group by wallet for efficiency
        by_wallet: dict[str, list[ScoreUpdateInput]] = {}
        for update in request.updates:
            if update.wallet_address not in by_wallet:
                by_wallet[update.wallet_address] = []
            by_wallet[update.wallet_address].append(update)

        for wallet, updates in by_wallet.items():
            for update in updates:
                try:
                    update_result = await self.update_from_trade(update)
                    result.results.append(update_result)
                    result.successful += 1
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"{wallet}: {e!s}")
                    logger.error(
                        "batch_update_failed",
                        wallet=wallet,
                        error=str(e),
                    )

        result.total_processed = result.successful + result.failed
        return result

    async def manual_adjust(
        self,
        wallet_address: str,
        adjustment: Decimal,
        reason: str,
    ) -> ScoreUpdateResult:
        """Manually adjust wallet score.

        Args:
            wallet_address: Wallet to adjust
            adjustment: Score adjustment (-1 to 1)
            reason: Reason for adjustment

        Returns:
            ScoreUpdateResult
        """
        metrics = await self.get_wallet_metrics(wallet_address)
        if not metrics:
            raise ValueError(f"Wallet {wallet_address} not found")

        previous_score = metrics.current_score
        new_score = max(Decimal("0"), min(Decimal("1"), previous_score + adjustment))

        metrics.current_score = new_score
        metrics.last_score_update = datetime.now(UTC)

        # Update flags based on new score
        metrics.is_flagged = new_score < self.config.decay_flag_threshold
        metrics.is_blacklisted = new_score < self.config.blacklist_threshold

        # Update cache
        self._metrics_cache[wallet_address] = metrics

        await self._save_metrics(metrics)
        await self._record_history(
            wallet_address=wallet_address,
            score=new_score,
            previous_score=previous_score,
            change=adjustment,
            update_type=ScoreUpdateType.MANUAL_ADJUSTMENT,
            reason=reason,
        )

        return ScoreUpdateResult(
            wallet_address=wallet_address,
            previous_score=previous_score,
            new_score=new_score,
            score_change=adjustment,
            update_type=ScoreUpdateType.MANUAL_ADJUSTMENT,
            triggered_flag=metrics.is_flagged,
            triggered_blacklist=metrics.is_blacklisted,
        )

    async def get_wallet_metrics(self, wallet_address: str) -> WalletMetrics | None:
        """Get current metrics for a wallet.

        Args:
            wallet_address: Wallet address

        Returns:
            WalletMetrics if found, None otherwise
        """
        # Check cache first
        if wallet_address in self._metrics_cache:
            return self._metrics_cache[wallet_address]

        # Query database
        result = (
            await self.supabase.table("wallet_metrics")
            .select("*")
            .eq("wallet_address", wallet_address)
            .single()
            .execute()
        )

        if result.data:
            metrics = self._deserialize_metrics(result.data)
            self._metrics_cache[wallet_address] = metrics
            return metrics
        return None

    async def get_score_history(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[WalletScoreHistory]:
        """Get score history for a wallet.

        Args:
            wallet_address: Wallet address
            limit: Maximum entries to return

        Returns:
            List of WalletScoreHistory entries
        """
        result = (
            await self.supabase.table("wallet_score_history")
            .select("*")
            .eq("wallet_address", wallet_address)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )

        return [self._deserialize_history(h) for h in result.data]

    async def get_flagged_wallets(self) -> list[WalletMetrics]:
        """Get all wallets flagged for decay.

        Returns:
            List of flagged WalletMetrics
        """
        result = (
            await self.supabase.table("wallet_metrics")
            .select("*")
            .eq("is_flagged", True)
            .eq("is_blacklisted", False)
            .execute()
        )

        return [self._deserialize_metrics(w) for w in result.data]

    def _calculate_win_impact(self, pnl_percent: Decimal) -> Decimal:
        """Calculate score increase for a winning trade.

        Args:
            pnl_percent: Profit percentage

        Returns:
            Score increase amount
        """
        base = self.config.base_win_increase

        # Additional bonus based on profit magnitude
        profit_bonus = (abs(pnl_percent) / 10) * self.config.profit_multiplier

        total = base + profit_bonus
        return min(total, self.config.max_win_increase)

    def _calculate_loss_impact(self, pnl_percent: Decimal) -> Decimal:
        """Calculate score decrease for a losing trade.

        Args:
            pnl_percent: Loss percentage

        Returns:
            Score decrease amount (negative)
        """
        base = self.config.base_loss_decrease

        # Additional penalty based on loss magnitude
        loss_penalty = (abs(pnl_percent) / 10) * self.config.loss_multiplier

        total = base + loss_penalty
        return -min(total, self.config.max_loss_decrease)

    def _update_rolling_window(
        self,
        wallet_address: str,
        is_win: bool,
        pnl_sol: Decimal,
    ) -> None:
        """Update rolling window for wallet.

        Args:
            wallet_address: Wallet address
            is_win: Whether trade was a win
            pnl_sol: PnL in SOL
        """
        if wallet_address not in self._rolling_windows:
            self._rolling_windows[wallet_address] = deque(
                maxlen=self.config.rolling_window_trades
            )

        self._rolling_windows[wallet_address].append(
            {
                "is_win": is_win,
                "pnl_sol": pnl_sol,
                "timestamp": datetime.now(UTC),
            }
        )

    async def _recalculate_rolling_metrics(self, metrics: WalletMetrics) -> None:
        """Recalculate rolling metrics from window.

        Args:
            metrics: WalletMetrics to update
        """
        window = self._rolling_windows.get(metrics.wallet_address, deque())

        metrics.rolling_trades = len(window)
        metrics.rolling_wins = sum(1 for t in window if t["is_win"])
        metrics.rolling_pnl = sum(t["pnl_sol"] for t in window)

    async def _save_metrics(self, metrics: WalletMetrics) -> None:
        """Save wallet metrics to database.

        Args:
            metrics: Metrics to save
        """
        data = {
            "wallet_address": metrics.wallet_address,
            "current_score": str(metrics.current_score),
            "lifetime_trades": metrics.lifetime_trades,
            "lifetime_wins": metrics.lifetime_wins,
            "lifetime_losses": metrics.lifetime_losses,
            "lifetime_pnl": str(metrics.lifetime_pnl),
            "rolling_trades": metrics.rolling_trades,
            "rolling_wins": metrics.rolling_wins,
            "rolling_pnl": str(metrics.rolling_pnl),
            "last_trade_timestamp": metrics.last_trade_timestamp.isoformat()
            if metrics.last_trade_timestamp
            else None,
            "last_score_update": metrics.last_score_update.isoformat(),
            "is_flagged": metrics.is_flagged,
            "is_blacklisted": metrics.is_blacklisted,
        }
        await self.supabase.table("wallet_metrics").upsert(data).execute()

    async def _record_history(
        self,
        wallet_address: str,
        score: Decimal,
        previous_score: Decimal,
        change: Decimal,
        update_type: ScoreUpdateType,
        trade_id: UUID | None = None,
        reason: str | None = None,
    ) -> None:
        """Record score history entry.

        Args:
            wallet_address: Wallet address
            score: New score
            previous_score: Previous score
            change: Score change
            update_type: Type of update
            trade_id: Associated trade ID
            reason: Optional reason
        """
        history = WalletScoreHistory(
            id=uuid4(),
            wallet_address=wallet_address,
            score=score,
            previous_score=previous_score,
            change=change,
            update_type=update_type,
            trade_id=trade_id,
            reason=reason,
        )

        data = {
            "id": str(history.id),
            "wallet_address": history.wallet_address,
            "score": str(history.score),
            "previous_score": str(history.previous_score),
            "change": str(history.change),
            "update_type": history.update_type.value,
            "trade_id": str(history.trade_id) if history.trade_id else None,
            "reason": history.reason,
            "created_at": history.created_at.isoformat(),
        }
        await self.supabase.table("wallet_score_history").insert(data).execute()

    def _deserialize_metrics(self, data: dict) -> WalletMetrics:
        """Deserialize wallet metrics from database.

        Args:
            data: Raw database record

        Returns:
            WalletMetrics instance
        """
        return WalletMetrics(
            wallet_address=data["wallet_address"],
            current_score=Decimal(data["current_score"]),
            lifetime_trades=data.get("lifetime_trades", 0),
            lifetime_wins=data.get("lifetime_wins", 0),
            lifetime_losses=data.get("lifetime_losses", 0),
            lifetime_pnl=Decimal(data.get("lifetime_pnl", "0")),
            rolling_trades=data.get("rolling_trades", 0),
            rolling_wins=data.get("rolling_wins", 0),
            rolling_pnl=Decimal(data.get("rolling_pnl", "0")),
            last_trade_timestamp=datetime.fromisoformat(data["last_trade_timestamp"])
            if data.get("last_trade_timestamp")
            else None,
            last_score_update=datetime.fromisoformat(data["last_score_update"])
            if data.get("last_score_update")
            else datetime.now(UTC),
            is_flagged=data.get("is_flagged", False),
            is_blacklisted=data.get("is_blacklisted", False),
        )

    def _deserialize_history(self, data: dict) -> WalletScoreHistory:
        """Deserialize score history from database.

        Args:
            data: Raw database record

        Returns:
            WalletScoreHistory instance
        """
        return WalletScoreHistory(
            id=UUID(data["id"]),
            wallet_address=data["wallet_address"],
            score=Decimal(data["score"]),
            previous_score=Decimal(data["previous_score"]),
            change=Decimal(data["change"]),
            update_type=ScoreUpdateType(data["update_type"]),
            trade_id=UUID(data["trade_id"]) if data.get("trade_id") else None,
            reason=data.get("reason"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# Singleton instance
_score_updater: WalletScoreUpdater | None = None


async def get_score_updater(supabase_client) -> WalletScoreUpdater:
    """Get or create WalletScoreUpdater singleton.

    Args:
        supabase_client: Supabase client instance

    Returns:
        WalletScoreUpdater singleton instance
    """
    global _score_updater
    if _score_updater is None:
        _score_updater = WalletScoreUpdater(supabase_client)
    return _score_updater
