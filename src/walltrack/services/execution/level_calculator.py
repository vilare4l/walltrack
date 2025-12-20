"""Level calculator for stop-loss and take-profit prices.

Calculates trigger prices from entry price and exit strategy.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from walltrack.models.position import CalculatedLevel, PositionLevels

if TYPE_CHECKING:
    from walltrack.models.exit_strategy import ExitStrategy

logger = structlog.get_logger()


class LevelCalculator:
    """Calculates stop-loss and take-profit price levels from strategy."""

    def calculate_levels(
        self,
        entry_price: float,
        strategy: ExitStrategy,
    ) -> PositionLevels:
        """Calculate all exit levels for a position.

        Args:
            entry_price: Position entry price
            strategy: Exit strategy to apply

        Returns:
            PositionLevels with all calculated trigger prices
        """
        # Calculate stop-loss price
        # stop_loss = 0.5 means -50%, so price = entry * (1 - 0.5) = entry * 0.5
        stop_loss_price = entry_price * (1 - strategy.stop_loss)

        # Calculate take-profit levels
        take_profit_levels = []
        for i, tp in enumerate(strategy.take_profit_levels):
            # trigger_multiplier = 2.0 means 2x, so price = entry * 2
            trigger_price = entry_price * tp.trigger_multiplier

            take_profit_levels.append(
                CalculatedLevel(
                    level_type=f"take_profit_{i + 1}",
                    trigger_price=trigger_price,
                    sell_percentage=tp.sell_percentage,
                    is_triggered=False,
                )
            )

        # Calculate trailing stop activation price
        trailing_activation = None
        if strategy.trailing_stop.enabled:
            trailing_activation = entry_price * strategy.trailing_stop.activation_multiplier

        # Calculate moonbag stop price
        moonbag_stop = None
        if strategy.moonbag.has_moonbag and strategy.moonbag.stop_loss is not None:
            # Moonbag stop is relative to entry price
            moonbag_stop = entry_price * (1 - strategy.moonbag.stop_loss)

        levels = PositionLevels(
            entry_price=entry_price,
            stop_loss_price=stop_loss_price,
            take_profit_levels=take_profit_levels,
            trailing_stop_activation_price=trailing_activation,
            moonbag_stop_price=moonbag_stop,
        )

        logger.info(
            "exit_levels_calculated",
            entry_price=entry_price,
            stop_loss=round(stop_loss_price, 8),
            take_profit_count=len(take_profit_levels),
            trailing_activation=trailing_activation,
        )

        return levels

    def recalculate_trailing_stop(
        self,
        levels: PositionLevels,
        current_price: float,
        strategy: ExitStrategy,
    ) -> PositionLevels:
        """Recalculate trailing stop based on new price peak.

        Args:
            levels: Current position levels
            current_price: Latest price
            strategy: Exit strategy

        Returns:
            Updated levels with new trailing stop
        """
        if not strategy.trailing_stop.enabled:
            return levels

        # Check if trailing stop should activate
        if levels.trailing_stop_activation_price is None:
            return levels

        if current_price < levels.trailing_stop_activation_price:
            # Not activated yet
            return levels

        # distance_percentage = 30 means 30% below peak
        distance_multiplier = 1 - (strategy.trailing_stop.distance_percentage / 100)

        # Trailing stop is active - update trailing price only if price is a new peak
        current_trailing = levels.trailing_stop_current_price
        if current_trailing is None:
            # First activation
            new_trailing_price = current_price * distance_multiplier
            levels.trailing_stop_current_price = new_trailing_price

            logger.debug(
                "trailing_stop_updated",
                peak_price=current_price,
                trailing_price=round(new_trailing_price, 8),
            )
        else:
            # Calculate implied peak from current trailing stop
            # trailing = peak * distance_multiplier, so peak = trailing / distance_multiplier
            implied_peak = current_trailing / distance_multiplier

            # Only update if current price is above the implied peak
            if current_price > implied_peak:
                new_trailing_price = current_price * distance_multiplier
                levels.trailing_stop_current_price = new_trailing_price

                logger.debug(
                    "trailing_stop_updated",
                    peak_price=current_price,
                    trailing_price=round(new_trailing_price, 8),
                )

        return levels


def get_level_calculator() -> LevelCalculator:
    """Get level calculator instance."""
    return LevelCalculator()
