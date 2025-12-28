"""Win rate circuit breaker manager."""

from collections import deque
from datetime import datetime
from decimal import Decimal

import structlog

from walltrack.data.supabase import SupabaseClient, get_supabase_client
from walltrack.models.risk import (
    CircuitBreakerTrigger,
    CircuitBreakerType,
    SystemStatus,
    TradeRecord,
    WinRateAnalysis,
    WinRateCheckResult,
    WinRateConfig,
    WinRateSnapshot,
)

logger = structlog.get_logger(__name__)


class WinRateCircuitBreaker:
    """
    Manages win rate-based circuit breaker logic.

    Uses rolling window to calculate win rate and triggers pause
    when it falls below threshold.
    """

    def __init__(self, config: WinRateConfig) -> None:
        """Initialize with configuration."""
        self.config = config
        self._supabase: SupabaseClient | None = None
        self._trade_window: deque[TradeRecord] = deque(maxlen=config.window_size)
        self._is_breached = False

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load recent trades from database on startup."""
        db = await self._get_db()

        # Load last N trades
        result = (
            await db.table("trades")
            .select("id, closed_at, pnl_percent")
            .not_("closed_at", "is", "null")
            .order("closed_at", desc=True)
            .limit(self.config.window_size)
            .execute()
        )

        if result.data:
            # Oldest first for deque
            for row in reversed(result.data):
                record = TradeRecord(
                    trade_id=row["id"],
                    closed_at=datetime.fromisoformat(row["closed_at"]),
                    is_win=Decimal(str(row["pnl_percent"])) > Decimal("0"),
                    pnl_percent=Decimal(str(row["pnl_percent"])),
                )
                self._trade_window.append(record)

        logger.info(
            "win_rate_circuit_breaker_initialized",
            trades_loaded=len(self._trade_window),
            window_size=self.config.window_size,
        )

    def add_trade(self, trade: TradeRecord) -> None:
        """Add a completed trade to the rolling window."""
        self._trade_window.append(trade)

    def calculate_snapshot(self) -> WinRateSnapshot:
        """Calculate current win rate snapshot."""
        trades = list(self._trade_window)
        winning = sum(1 for t in trades if t.is_win)
        losing = len(trades) - winning

        return WinRateSnapshot(
            window_size=self.config.window_size,
            trades_in_window=len(trades),
            winning_trades=winning,
            losing_trades=losing,
        )

    async def check_win_rate(self) -> WinRateCheckResult:
        """
        Check if win rate is below threshold.

        Returns check result with breach status and optional trigger.
        """
        snapshot = self.calculate_snapshot()

        # Check if we have sufficient history
        has_sufficient = snapshot.trades_in_window >= self.config.minimum_trades
        is_caution = not has_sufficient and self.config.enable_caution_flag

        # Only check threshold if sufficient history
        is_breached = False
        trigger = None

        if has_sufficient:
            is_breached = snapshot.win_rate_percent < self.config.threshold_percent

            if is_breached:
                trigger = await self._create_trigger(snapshot)
                self._is_breached = True

        # Build message
        if is_caution:
            message = (
                f"Caution: Only {snapshot.trades_in_window} trades "
                f"(need {self.config.minimum_trades} for circuit breaker)"
            )
        elif is_breached:
            message = (
                f"Win rate {snapshot.win_rate_percent:.1f}% below "
                f"threshold {self.config.threshold_percent}%"
            )
        else:
            message = (
                f"Win rate {snapshot.win_rate_percent:.1f}% "
                f"(threshold: {self.config.threshold_percent}%)"
            )

        return WinRateCheckResult(
            snapshot=snapshot,
            threshold_percent=self.config.threshold_percent,
            is_breached=is_breached,
            is_caution=is_caution,
            trigger=trigger,
            message=message,
        )

    async def _create_trigger(self, snapshot: WinRateSnapshot) -> CircuitBreakerTrigger:
        """Create and persist circuit breaker trigger record."""
        db = await self._get_db()

        trigger = CircuitBreakerTrigger(
            breaker_type=CircuitBreakerType.WIN_RATE,
            threshold_value=self.config.threshold_percent,
            actual_value=snapshot.win_rate_percent,
            capital_at_trigger=Decimal("0"),  # Not applicable
            peak_capital_at_trigger=Decimal("0"),
        )

        result = (
            await db.table("circuit_breaker_triggers")
            .insert(trigger.model_dump(exclude={"id", "is_active"}, mode="json"))
            .execute()
        )

        trigger.id = result.data[0]["id"]

        # Update system status
        await db.table("system_config").upsert(
            {
                "key": "system_status",
                "value": SystemStatus.PAUSED_WIN_RATE.value,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

        logger.warning(
            "win_rate_circuit_breaker_triggered",
            win_rate=str(snapshot.win_rate_percent),
            threshold=str(self.config.threshold_percent),
            trades_in_window=snapshot.trades_in_window,
        )

        return trigger

    async def analyze_recent_trades(self) -> WinRateAnalysis:
        """
        Provide detailed analysis of recent trades.

        Useful for investigating why win rate dropped.
        """
        snapshot = self.calculate_snapshot()
        trades = list(self._trade_window)

        if not trades:
            return WinRateAnalysis(
                snapshot=snapshot,
                recent_trades=[],
                losing_streak_current=0,
                winning_streak_current=0,
                avg_win_pnl_percent=Decimal("0"),
                avg_loss_pnl_percent=Decimal("0"),
                profit_factor=Decimal("0"),
                largest_win_percent=Decimal("0"),
                largest_loss_percent=Decimal("0"),
            )

        # Calculate streaks (from most recent)
        losing_streak = 0
        winning_streak = 0
        for trade in reversed(trades):
            if trade.is_win:
                if losing_streak == 0:
                    winning_streak += 1
                else:
                    break
            elif winning_streak == 0:
                losing_streak += 1
            else:
                break

        # Calculate averages
        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        avg_win = (
            sum(t.pnl_percent for t in wins) / len(wins) if wins else Decimal("0")
        )
        avg_loss = (
            sum(t.pnl_percent for t in losses) / len(losses) if losses else Decimal("0")
        )

        # Profit factor
        total_wins = sum(t.pnl_percent for t in wins)
        total_losses = abs(sum(t.pnl_percent for t in losses))
        profit_factor = (
            total_wins / total_losses if total_losses > 0 else Decimal("999")
        )

        return WinRateAnalysis(
            snapshot=snapshot,
            recent_trades=trades[-20:],  # Last 20 for display
            losing_streak_current=losing_streak,
            winning_streak_current=winning_streak,
            avg_win_pnl_percent=avg_win,
            avg_loss_pnl_percent=avg_loss,
            profit_factor=profit_factor,
            largest_win_percent=max(
                (t.pnl_percent for t in wins), default=Decimal("0")
            ),
            largest_loss_percent=min(
                (t.pnl_percent for t in losses), default=Decimal("0")
            ),
        )

    async def reset(self, operator_id: str, clear_history: bool = False) -> None:
        """
        Reset circuit breaker (requires manual action).

        Args:
            operator_id: ID of operator performing reset
            clear_history: If True, clears the trade window
        """
        db = await self._get_db()

        # Mark active trigger as reset
        await (
            db.table("circuit_breaker_triggers")
            .update(
                {
                    "reset_at": datetime.utcnow().isoformat(),
                    "reset_by": operator_id,
                }
            )
            .eq("breaker_type", CircuitBreakerType.WIN_RATE.value)
            .is_("reset_at", "null")
            .execute()
        )

        if clear_history:
            self._trade_window.clear()

        self._is_breached = False

        # Update system status
        await db.table("system_config").upsert(
            {
                "key": "system_status",
                "value": SystemStatus.RUNNING.value,
                "updated_at": datetime.utcnow().isoformat(),
            }
        ).execute()

        logger.info(
            "win_rate_circuit_breaker_reset",
            operator_id=operator_id,
            history_cleared=clear_history,
        )

    async def record_trade_snapshot(self) -> None:
        """Record current win rate to history for tracking."""
        db = await self._get_db()
        snapshot = self.calculate_snapshot()

        await db.table("win_rate_snapshots").insert(
            {
                "timestamp": datetime.utcnow().isoformat(),
                "window_size": snapshot.window_size,
                "trades_in_window": snapshot.trades_in_window,
                "winning_trades": snapshot.winning_trades,
                "win_rate_percent": str(snapshot.win_rate_percent),
            }
        ).execute()

    @property
    def can_trade(self) -> bool:
        """Whether trading is currently allowed."""
        return not self._is_breached


# Singleton instance
_win_rate_breaker: WinRateCircuitBreaker | None = None


async def get_win_rate_circuit_breaker(
    config: WinRateConfig | None = None,
) -> WinRateCircuitBreaker:
    """Get or create win rate circuit breaker singleton."""
    global _win_rate_breaker

    if _win_rate_breaker is None:
        if config is None:
            db = await get_supabase_client()
            result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "win_rate_config")
                .single()
                .execute()
            )
            config = WinRateConfig(**result.data["value"])

        _win_rate_breaker = WinRateCircuitBreaker(config)
        await _win_rate_breaker.initialize()

    return _win_rate_breaker


def reset_win_rate_circuit_breaker() -> None:
    """Reset the singleton for testing."""
    global _win_rate_breaker
    _win_rate_breaker = None
