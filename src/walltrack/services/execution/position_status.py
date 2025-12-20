"""Position status calculation service.

Provides status metrics for positions including unrealized PnL,
multipliers, and time held.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from walltrack.models.position import Position

logger = structlog.get_logger()


@dataclass
class PositionMetrics:
    """Calculated metrics for a position."""

    # PnL
    unrealized_pnl_sol: float
    unrealized_pnl_pct: float
    realized_pnl_sol: float

    # Price metrics
    current_price: float
    entry_price: float
    peak_price: float | None
    multiplier: float

    # Time
    hours_held: float

    # Status
    is_profitable: bool
    is_moonbag: bool

    # Exit level info
    stop_loss_price: float | None
    next_take_profit_price: float | None
    trailing_stop_active: bool
    trailing_stop_price: float | None


class PositionStatusService:
    """Service for calculating position status and metrics."""

    def calculate_metrics(
        self,
        position: Position,
        current_price: float,
    ) -> PositionMetrics:
        """Calculate all metrics for a position.

        Args:
            position: Position to calculate metrics for
            current_price: Current token price

        Returns:
            PositionMetrics with all calculated values
        """
        now = datetime.utcnow()

        # Calculate unrealized PnL
        current_value = position.current_amount_tokens * current_price
        cost_basis = position.current_amount_tokens * position.entry_price
        unrealized_pnl = current_value - cost_basis
        unrealized_pnl_pct = (
            (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0
        )

        # Calculate multiplier
        multiplier = (
            current_price / position.entry_price if position.entry_price > 0 else 1.0
        )

        # Time held
        hours_held = (now - position.entry_time).total_seconds() / 3600

        # Peak price
        peak_price = position.peak_price
        if peak_price is None or current_price > peak_price:
            peak_price = current_price

        # Exit level info
        stop_loss_price = None
        next_tp_price = None
        trailing_stop_active = False
        trailing_stop_price = None

        if position.levels:
            stop_loss_price = position.levels.stop_loss_price
            next_tp = position.levels.next_take_profit
            if next_tp:
                next_tp_price = next_tp.trigger_price
            if position.levels.trailing_stop_current_price:
                trailing_stop_active = True
                trailing_stop_price = position.levels.trailing_stop_current_price

        return PositionMetrics(
            unrealized_pnl_sol=unrealized_pnl,
            unrealized_pnl_pct=unrealized_pnl_pct,
            realized_pnl_sol=position.realized_pnl_sol,
            current_price=current_price,
            entry_price=position.entry_price,
            peak_price=peak_price,
            multiplier=multiplier,
            hours_held=hours_held,
            is_profitable=unrealized_pnl > 0,
            is_moonbag=position.is_moonbag,
            stop_loss_price=stop_loss_price,
            next_take_profit_price=next_tp_price,
            trailing_stop_active=trailing_stop_active,
            trailing_stop_price=trailing_stop_price,
        )

    def format_summary(
        self,
        position: Position,
        metrics: PositionMetrics,
    ) -> dict:
        """Format position summary for display.

        Args:
            position: Position
            metrics: Calculated metrics

        Returns:
            Dict with display-ready values
        """
        # Format profit indicator
        pnl_sign = "+" if metrics.unrealized_pnl_sol >= 0 else ""
        pnl_display = f"{pnl_sign}{metrics.unrealized_pnl_pct:.1f}%"

        # Format multiplier
        multiplier_display = f"x{metrics.multiplier:.2f}"

        # Format time held
        if metrics.hours_held < 1:
            time_display = f"{int(metrics.hours_held * 60)}m"
        elif metrics.hours_held < 24:
            time_display = f"{metrics.hours_held:.1f}h"
        else:
            days = metrics.hours_held / 24
            time_display = f"{days:.1f}d"

        return {
            "id": position.id[:8],
            "token": position.token_symbol or position.token_address[:8],
            "status": position.status.value,
            "pnl": pnl_display,
            "multiplier": multiplier_display,
            "time_held": time_display,
            "entry_price": position.entry_price,
            "current_price": metrics.current_price,
            "unrealized_pnl_sol": round(metrics.unrealized_pnl_sol, 4),
            "realized_pnl_sol": round(metrics.realized_pnl_sol, 4),
            "is_moonbag": metrics.is_moonbag,
        }


# Singleton
_position_status_service: PositionStatusService | None = None


def get_position_status_service() -> PositionStatusService:
    """Get or create position status service singleton."""
    global _position_status_service
    if _position_status_service is None:
        _position_status_service = PositionStatusService()
    return _position_status_service
