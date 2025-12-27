"""Calculates portfolio drawdown metrics.

Story 10.5-9: Implements drawdown calculation from portfolio snapshots.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog

from walltrack.data.supabase.client import SupabaseClient, get_supabase_client
from walltrack.models.position_sizing import DrawdownMetrics

logger = structlog.get_logger(__name__)


class DrawdownCalculator:
    """Calculates portfolio drawdown from peak.

    Uses portfolio snapshots to track high-water mark
    over a configurable lookback period.
    """

    def __init__(
        self,
        lookback_days: int = 30,
        client: SupabaseClient | None = None,
    ) -> None:
        """Initialize drawdown calculator.

        Args:
            lookback_days: Days to look back for peak calculation
            client: Optional Supabase client
        """
        self.lookback_days = lookback_days
        self._client = client

    async def _get_client(self) -> SupabaseClient:
        """Get or create Supabase client."""
        if self._client is None:
            self._client = await get_supabase_client()
        return self._client

    async def calculate(
        self,
        current_capital_sol: float | None = None,
    ) -> DrawdownMetrics:
        """Calculate current drawdown metrics.

        Args:
            current_capital_sol: Optional current capital (fetches if not provided)

        Returns:
            DrawdownMetrics with current drawdown state
        """
        client = await self._get_client()

        # Get current portfolio value if not provided
        if current_capital_sol is None:
            current_capital_sol = await self._get_current_capital(client)

        # Get peak value in lookback period
        peak_capital_sol, peak_date = await self._get_peak_capital(client)

        # If no history, use current as peak
        if peak_capital_sol == 0:
            peak_capital_sol = current_capital_sol
            peak_date = datetime.now(UTC)

        # Calculate drawdown percentage
        if peak_capital_sol > 0:
            drawdown_pct = ((peak_capital_sol - current_capital_sol) / peak_capital_sol) * 100
            drawdown_pct = max(0.0, drawdown_pct)  # Can't be negative
        else:
            drawdown_pct = 0.0

        days_since_peak = (datetime.now(UTC) - peak_date).days

        metrics = DrawdownMetrics(
            peak_capital_sol=peak_capital_sol,
            current_capital_sol=current_capital_sol,
            drawdown_pct=drawdown_pct,
            peak_date=peak_date,
            days_since_peak=days_since_peak,
        )

        logger.debug(
            "drawdown_calculated",
            current=current_capital_sol,
            peak=peak_capital_sol,
            drawdown_pct=round(drawdown_pct, 2),
            days_since_peak=days_since_peak,
        )

        return metrics

    async def _get_current_capital(self, client: SupabaseClient) -> float:
        """Get current portfolio capital from snapshots.

        Falls back to calculating from wallet + positions if no snapshot.
        """
        try:
            result = await client.table("portfolio_snapshots").select(
                "total_value_sol"
            ).order("timestamp", desc=True).limit(1).execute()

            if result.data:
                return float(result.data[0]["total_value_sol"])
        except Exception as e:
            logger.warning("portfolio_snapshot_fetch_failed", error=str(e))

        # Fallback: calculate from positions
        return await self._calculate_portfolio_value(client)

    async def _get_peak_capital(self, client: SupabaseClient) -> tuple[float, datetime]:
        """Get peak capital in lookback period."""
        cutoff = datetime.now(UTC) - timedelta(days=self.lookback_days)

        try:
            result = await client.table("portfolio_snapshots").select(
                "total_value_sol, timestamp"
            ).gte("timestamp", cutoff.isoformat()).order(
                "total_value_sol", desc=True
            ).limit(1).execute()

            if result.data:
                timestamp_str = result.data[0]["timestamp"]
                # Handle various timestamp formats
                if isinstance(timestamp_str, str):
                    if timestamp_str.endswith("Z"):
                        timestamp_str = timestamp_str.replace("Z", "+00:00")
                    peak_date = datetime.fromisoformat(timestamp_str)
                else:
                    peak_date = timestamp_str

                return (
                    float(result.data[0]["total_value_sol"]),
                    peak_date,
                )
        except Exception as e:
            logger.warning("peak_capital_fetch_failed", error=str(e))

        return 0.0, datetime.now(UTC)

    async def _calculate_portfolio_value(self, client: SupabaseClient) -> float:
        """Calculate portfolio value from open positions.

        Used as fallback when no snapshots available.
        """
        try:
            result = await client.table("positions").select(
                "entry_amount_sol, unrealized_pnl"
            ).eq("status", "open").execute()

            total = 0.0
            for row in result.data:
                entry = float(row.get("entry_amount_sol", 0) or 0)
                pnl = float(row.get("unrealized_pnl", 0) or 0)
                total += entry + pnl

            return total
        except Exception as e:
            logger.warning("portfolio_value_calculation_failed", error=str(e))
            return 0.0


# Singleton
_calculator: DrawdownCalculator | None = None


async def get_drawdown_calculator(
    lookback_days: int = 30,
) -> DrawdownCalculator:
    """Get or create drawdown calculator singleton.

    Args:
        lookback_days: Days to look back for peak calculation

    Returns:
        DrawdownCalculator instance
    """
    global _calculator
    if _calculator is None:
        _calculator = DrawdownCalculator(lookback_days=lookback_days)
    return _calculator


def reset_drawdown_calculator() -> None:
    """Reset singleton for testing."""
    global _calculator
    _calculator = None
