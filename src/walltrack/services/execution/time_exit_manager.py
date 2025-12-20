"""Time-based exit rule management.

Handles max hold duration and stagnation-based exits.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import structlog

from walltrack.models.position import ExitReason, Position

if TYPE_CHECKING:
    from walltrack.models.exit_strategy import TimeRulesConfig

logger = structlog.get_logger()


@dataclass
class StagnationWindow:
    """Price tracking window for stagnation detection."""

    position_id: str
    window_start: datetime
    window_hours: int
    price_at_start: float

    def is_complete(self) -> bool:
        """Check if stagnation window has elapsed."""
        elapsed = datetime.utcnow() - self.window_start
        return elapsed >= timedelta(hours=self.window_hours)

    def calculate_movement_pct(self, current_price: float) -> float:
        """Calculate price movement percentage from window start."""
        if self.price_at_start <= 0:
            return 0.0
        movement = abs(current_price - self.price_at_start)
        return (movement / self.price_at_start) * 100


@dataclass
class TimeExitCheckResult:
    """Result of time-based exit check."""

    should_exit: bool
    exit_reason: ExitReason | None = None

    # Duration info
    hours_held: float = 0
    max_hold_hours: int | None = None

    # Stagnation info
    is_stagnant: bool = False
    stagnation_hours: int | None = None
    price_movement_pct: float | None = None
    stagnation_threshold_pct: float | None = None

    # Profit info
    current_price: float | None = None
    entry_price: float | None = None
    unrealized_pnl_pct: float | None = None


class TimeExitManager:
    """Manages time-based exit rules for positions.

    Handles:
    1. Max hold duration - forced exit after N hours
    2. Stagnation detection - exit if price movement < threshold over window
    """

    def __init__(self) -> None:
        """Initialize time exit manager."""
        self._stagnation_windows: dict[str, StagnationWindow] = {}

    def initialize_for_position(
        self,
        position: Position,
        time_rules: TimeRulesConfig,
    ) -> None:
        """Initialize time tracking for a new position.

        Args:
            position: The position to track
            time_rules: Time-based exit configuration
        """
        if time_rules.stagnation_exit_enabled:
            window = StagnationWindow(
                position_id=position.id,
                window_start=position.entry_time,
                window_hours=time_rules.stagnation_hours,
                price_at_start=position.entry_price,
            )
            self._stagnation_windows[position.id] = window

            logger.debug(
                "stagnation_tracking_initialized",
                position_id=position.id[:8],
                window_hours=time_rules.stagnation_hours,
                threshold_pct=time_rules.stagnation_threshold_pct,
            )

    def check_time_exits(
        self,
        position: Position,
        time_rules: TimeRulesConfig,
        current_price: float,
    ) -> TimeExitCheckResult:
        """Check all time-based exit conditions.

        Args:
            position: Position to check
            time_rules: Time-based exit configuration
            current_price: Current token price

        Returns:
            TimeExitCheckResult with exit decision and details
        """
        now = datetime.utcnow()
        hours_held = (now - position.entry_time).total_seconds() / 3600

        result = TimeExitCheckResult(
            should_exit=False,
            hours_held=hours_held,
            max_hold_hours=time_rules.max_hold_hours,
            current_price=current_price,
            entry_price=position.entry_price,
        )

        # Calculate unrealized PnL
        if position.entry_price > 0:
            pnl_pct = ((current_price - position.entry_price) / position.entry_price) * 100
            result.unrealized_pnl_pct = pnl_pct

        # 1. Check max hold duration
        if time_rules.max_hold_hours and hours_held >= time_rules.max_hold_hours:
            result.should_exit = True
            result.exit_reason = ExitReason.TIME_LIMIT

            logger.info(
                "max_hold_duration_triggered",
                position_id=position.id[:8],
                hours_held=round(hours_held, 1),
                max_hours=time_rules.max_hold_hours,
                current_price=current_price,
                unrealized_pnl_pct=round(result.unrealized_pnl_pct or 0, 2),
            )
            return result

        # 2. Check stagnation
        if time_rules.stagnation_exit_enabled:
            stagnation_result = self._check_stagnation(
                position,
                time_rules,
                current_price,
            )

            if stagnation_result.is_stagnant:
                result.should_exit = True
                result.exit_reason = ExitReason.STAGNATION
                result.is_stagnant = True
                result.stagnation_hours = time_rules.stagnation_hours
                result.price_movement_pct = stagnation_result.price_movement_pct
                result.stagnation_threshold_pct = time_rules.stagnation_threshold_pct

                logger.info(
                    "stagnation_exit_triggered",
                    position_id=position.id[:8],
                    hours_held=round(hours_held, 1),
                    stagnation_hours=time_rules.stagnation_hours,
                    price_movement_pct=round(stagnation_result.price_movement_pct or 0, 2),
                    threshold_pct=time_rules.stagnation_threshold_pct,
                    unrealized_pnl_pct=round(result.unrealized_pnl_pct or 0, 2),
                )
                return result

        return result

    def _check_stagnation(
        self,
        position: Position,
        time_rules: TimeRulesConfig,
        current_price: float,
    ) -> TimeExitCheckResult:
        """Check if position is stagnant.

        Args:
            position: Position to check
            time_rules: Time rules configuration
            current_price: Current token price

        Returns:
            TimeExitCheckResult with stagnation status
        """
        result = TimeExitCheckResult(
            should_exit=False,
            stagnation_hours=time_rules.stagnation_hours,
            stagnation_threshold_pct=time_rules.stagnation_threshold_pct,
        )

        window = self._stagnation_windows.get(position.id)

        if not window:
            # Initialize window if not exists
            window = StagnationWindow(
                position_id=position.id,
                window_start=datetime.utcnow(),
                window_hours=time_rules.stagnation_hours,
                price_at_start=current_price,
            )
            self._stagnation_windows[position.id] = window
            return result

        # Check if window has elapsed
        if not window.is_complete():
            return result

        # Calculate price movement
        movement_pct = window.calculate_movement_pct(current_price)
        result.price_movement_pct = movement_pct

        # Check if stagnant
        if movement_pct < time_rules.stagnation_threshold_pct:
            result.is_stagnant = True

            logger.debug(
                "stagnation_detected",
                position_id=position.id[:8],
                movement_pct=round(movement_pct, 2),
                threshold_pct=time_rules.stagnation_threshold_pct,
                window_hours=time_rules.stagnation_hours,
            )
        else:
            # Reset window for next check period
            self._reset_stagnation_window(
                position.id, current_price, time_rules.stagnation_hours
            )

        return result

    def _reset_stagnation_window(
        self,
        position_id: str,
        current_price: float,
        window_hours: int,
    ) -> None:
        """Reset stagnation window for new period.

        Args:
            position_id: Position ID
            current_price: Current price (becomes new baseline)
            window_hours: New window duration
        """
        self._stagnation_windows[position_id] = StagnationWindow(
            position_id=position_id,
            window_start=datetime.utcnow(),
            window_hours=window_hours,
            price_at_start=current_price,
        )

    def remove_position(self, position_id: str) -> None:
        """Remove time tracking for closed position.

        Args:
            position_id: Position ID to remove
        """
        self._stagnation_windows.pop(position_id, None)

    def get_hours_held(self, position: Position) -> float:
        """Get hours held for a position.

        Args:
            position: Position to check

        Returns:
            Hours since position opened
        """
        now = datetime.utcnow()
        return (now - position.entry_time).total_seconds() / 3600

    def get_time_remaining(
        self, position: Position, max_hold_hours: int | None
    ) -> float | None:
        """Get time remaining before max hold duration.

        Args:
            position: Position to check
            max_hold_hours: Max hold duration

        Returns:
            Hours remaining or None if no limit
        """
        if max_hold_hours is None:
            return None

        hours_held = self.get_hours_held(position)
        return max(0, max_hold_hours - hours_held)


# Singleton
_time_exit_manager: TimeExitManager | None = None


def get_time_exit_manager() -> TimeExitManager:
    """Get or create time exit manager singleton."""
    global _time_exit_manager
    if _time_exit_manager is None:
        _time_exit_manager = TimeExitManager()
    return _time_exit_manager
