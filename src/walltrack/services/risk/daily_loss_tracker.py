"""Tracks daily P&L and enforces loss limits.

Story 10.5-10: Implements daily loss tracking and limit enforcement.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import structlog

from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.models.position_sizing import DailyLossMetrics

logger = structlog.get_logger(__name__)


class DailyLossTracker:
    """Tracks daily P&L and enforces loss limits.

    Features:
    - Calculates realized + unrealized P&L for the day
    - Blocks new entries when daily loss limit reached
    - Allows exits even when limit hit (to limit losses)
    - Resets automatically at midnight UTC
    """

    def __init__(
        self,
        client: SupabaseClient | None = None,
        daily_limit_pct: float = 5.0,
        warning_threshold_pct: float = 80.0,
    ) -> None:
        """Initialize daily loss tracker.

        Args:
            client: Optional Supabase client
            daily_limit_pct: Maximum daily loss as % of starting capital
            warning_threshold_pct: Warn when this % of limit is used
        """
        self._client = client
        self.daily_limit_pct = daily_limit_pct
        self.warning_threshold_pct = warning_threshold_pct

    async def _get_client(self) -> SupabaseClient:
        """Get or create Supabase client."""
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    async def get_daily_metrics(
        self,
        starting_capital_sol: float | None = None,
    ) -> DailyLossMetrics:
        """Get current daily P&L metrics.

        Args:
            starting_capital_sol: Optional override for starting capital

        Returns:
            DailyLossMetrics with current state
        """
        client = await self._get_client()
        today = datetime.now(UTC).date()
        today_start = datetime(today.year, today.month, today.day, tzinfo=UTC)

        # Get starting capital (from snapshot or calculate)
        if starting_capital_sol is None:
            starting_capital_sol = await self._get_starting_capital(client, today)

        # Get realized P&L (closed positions today)
        realized_pnl = await self._get_realized_pnl(client, today_start)

        # Get unrealized P&L (open positions)
        unrealized_pnl = await self._get_unrealized_pnl(client)

        total_pnl = realized_pnl + unrealized_pnl

        # Calculate P&L percentage
        pnl_pct = (
            (total_pnl / starting_capital_sol) * 100
            if starting_capital_sol > 0
            else 0.0
        )

        # Check limits
        is_limit_hit = False
        is_warning_zone = False
        limit_remaining_pct = self.daily_limit_pct

        if total_pnl < 0:
            loss_pct = abs(pnl_pct)
            limit_remaining_pct = max(0.0, self.daily_limit_pct - loss_pct)

            if loss_pct >= self.daily_limit_pct:
                is_limit_hit = True
            elif loss_pct >= self.daily_limit_pct * (self.warning_threshold_pct / 100):
                is_warning_zone = True

        metrics = DailyLossMetrics(
            date=today_start,
            realized_pnl_sol=realized_pnl,
            unrealized_pnl_sol=unrealized_pnl,
            total_pnl_sol=total_pnl,
            starting_capital_sol=starting_capital_sol,
            pnl_pct=pnl_pct,
            daily_limit_pct=self.daily_limit_pct,
            limit_remaining_pct=limit_remaining_pct,
            is_limit_hit=is_limit_hit,
            is_warning_zone=is_warning_zone,
        )

        logger.debug(
            "daily_loss_calculated",
            total_pnl=round(total_pnl, 4),
            pnl_pct=round(pnl_pct, 2),
            limit_hit=is_limit_hit,
            warning_zone=is_warning_zone,
        )

        return metrics

    async def is_entry_allowed(
        self,
        starting_capital_sol: float | None = None,
    ) -> tuple[bool, str | None, DailyLossMetrics]:
        """Check if new entries are allowed.

        Args:
            starting_capital_sol: Optional override for starting capital

        Returns:
            Tuple of (allowed, reason, metrics)
        """
        metrics = await self.get_daily_metrics(starting_capital_sol)

        if metrics.is_limit_hit:
            reason = (
                f"Daily loss limit reached: {metrics.pnl_pct:.2f}% "
                f"(limit: {metrics.daily_limit_pct}%)"
            )
            logger.warning("entry_blocked_daily_limit", reason=reason)
            return False, reason, metrics

        if metrics.is_warning_zone:
            logger.info(
                "daily_limit_warning",
                pnl_pct=round(metrics.pnl_pct, 2),
                limit=metrics.daily_limit_pct,
                remaining=round(metrics.limit_remaining_pct, 2),
            )

        return True, None, metrics

    async def _get_starting_capital(
        self,
        client: SupabaseClient,
        today: date,
    ) -> float:
        """Get capital at start of day.

        Priority:
        1. Daily snapshot for today
        2. Latest portfolio snapshot from yesterday
        3. Sum of current positions entry values
        """
        # Try daily_snapshots table first
        try:
            result = await client.table("daily_snapshots").select(
                "starting_capital"
            ).eq("date", today.isoformat()).execute()

            if result.data:
                return float(result.data[0]["starting_capital"])
        except Exception as e:
            logger.debug("daily_snapshot_not_found", error=str(e))

        # Fallback: get latest portfolio snapshot from before today
        try:
            today_start = datetime(today.year, today.month, today.day, tzinfo=UTC)
            result = await client.table("portfolio_snapshots").select(
                "total_value_sol"
            ).lt("timestamp", today_start.isoformat()).order(
                "timestamp", desc=True
            ).limit(1).execute()

            if result.data:
                return float(result.data[0]["total_value_sol"])
        except Exception as e:
            logger.debug("portfolio_snapshot_not_found", error=str(e))

        # Final fallback: sum current positions
        try:
            result = await client.table("positions").select(
                "entry_amount_sol"
            ).execute()

            total = sum(float(row.get("entry_amount_sol", 0) or 0) for row in result.data)
            return max(total, 10.0)  # Minimum default
        except Exception as e:
            logger.warning("starting_capital_calculation_failed", error=str(e))
            return 10.0

    async def _get_realized_pnl(
        self,
        client: SupabaseClient,
        today_start: datetime,
    ) -> float:
        """Get realized P&L from positions closed today."""
        try:
            result = await client.table("positions").select(
                "realized_pnl"
            ).eq("status", "closed").gte(
                "closed_at", today_start.isoformat()
            ).execute()

            return sum(float(row.get("realized_pnl", 0) or 0) for row in result.data)
        except Exception as e:
            logger.warning("realized_pnl_fetch_failed", error=str(e))
            return 0.0

    async def _get_unrealized_pnl(self, client: SupabaseClient) -> float:
        """Get unrealized P&L from open positions."""
        try:
            result = await client.table("positions").select(
                "unrealized_pnl"
            ).in_("status", ["open", "partial_exit"]).execute()

            return sum(float(row.get("unrealized_pnl", 0) or 0) for row in result.data)
        except Exception as e:
            logger.warning("unrealized_pnl_fetch_failed", error=str(e))
            return 0.0


# Singleton
_tracker: DailyLossTracker | None = None


async def get_daily_loss_tracker(
    daily_limit_pct: float = 5.0,
    warning_threshold_pct: float = 80.0,
) -> DailyLossTracker:
    """Get or create daily loss tracker singleton.

    Args:
        daily_limit_pct: Maximum daily loss as % of starting capital
        warning_threshold_pct: Warn when this % of limit is used

    Returns:
        DailyLossTracker instance
    """
    global _tracker
    if _tracker is None:
        _tracker = DailyLossTracker(
            daily_limit_pct=daily_limit_pct,
            warning_threshold_pct=warning_threshold_pct,
        )
    return _tracker


def reset_daily_loss_tracker() -> None:
    """Reset singleton for testing."""
    global _tracker
    _tracker = None
