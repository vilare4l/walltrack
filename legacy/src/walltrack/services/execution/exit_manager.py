"""Exit manager for monitoring and executing position exits.

Monitors positions against stop-loss and take-profit levels,
executing exits when conditions are met.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

import structlog

from walltrack.models.position import (
    CalculatedLevel,
    ExitExecution,
    ExitReason,
    Position,
    PositionLevels,
    PositionStatus,
)
from walltrack.models.trade import SwapDirection, TradeRequest
from walltrack.services.execution.level_calculator import (
    LevelCalculator,
    get_level_calculator,
)
from walltrack.services.execution.time_exit_manager import (
    TimeExitManager,
    get_time_exit_manager,
)

if TYPE_CHECKING:
    from walltrack.data.supabase.repositories.exit_strategy_repo import (
        ExitStrategyRepository,
    )
    from walltrack.data.supabase.repositories.position_repo import PositionRepository
    from walltrack.models.exit_strategy import ExitStrategy
    from walltrack.services.trade.executor import TradeExecutor

logger = structlog.get_logger()


@dataclass
class ExitCheckResult:
    """Result of checking exit conditions."""

    should_exit: bool
    exit_reason: ExitReason | None = None
    level: CalculatedLevel | None = None
    sell_percentage: float = 0
    is_full_exit: bool = False


class ExitManager:
    """Monitors positions and executes exits based on price levels.

    Responsibilities:
    - Check price against stop-loss
    - Check price against take-profit levels
    - Update trailing stop as price rises
    - Execute partial and full exits
    - Handle moonbag transitions
    """

    def __init__(
        self,
        level_calculator: LevelCalculator | None = None,
        trade_executor: TradeExecutor | None = None,
        position_repo: PositionRepository | None = None,
        strategy_repo: ExitStrategyRepository | None = None,
        time_exit_manager: TimeExitManager | None = None,
    ) -> None:
        self._calculator = level_calculator or get_level_calculator()
        self._executor = trade_executor
        self._position_repo = position_repo
        self._strategy_repo = strategy_repo
        self._time_manager = time_exit_manager or get_time_exit_manager()

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._executor is None:
            from walltrack.services.trade.executor import (  # noqa: PLC0415
                get_trade_executor,
            )

            self._executor = await get_trade_executor()
        if self._position_repo is None:
            from walltrack.data.supabase.repositories.position_repo import (  # noqa: PLC0415
                get_position_repository,
            )

            self._position_repo = await get_position_repository()
        if self._strategy_repo is None:
            from walltrack.data.supabase.repositories.exit_strategy_repo import (  # noqa: PLC0415
                get_exit_strategy_repository,
            )

            self._strategy_repo = await get_exit_strategy_repository()

        logger.info("exit_manager_initialized")

    def check_exit_conditions(
        self,
        position: Position,
        current_price: float,
        strategy: ExitStrategy,
    ) -> ExitCheckResult:
        """Check if any exit condition is met.

        Args:
            position: Position to check
            current_price: Current token price
            strategy: Exit strategy

        Returns:
            ExitCheckResult indicating if/how to exit
        """
        if position.levels is None:
            logger.warning("position_has_no_levels", position_id=position.id)
            return ExitCheckResult(should_exit=False)

        levels = position.levels

        # Check conditions in priority order
        result = self._check_stop_loss(position, current_price, levels)
        if result:
            return result

        result = self._check_trailing_stop(position, current_price, levels, strategy)
        if result:
            return result

        result = self._check_take_profit(position, current_price, levels, strategy)
        if result:
            return result

        # Check time-based exits
        result = self._check_time_exits(position, current_price, strategy)
        if result:
            return result

        return ExitCheckResult(should_exit=False)

    def _check_stop_loss(
        self,
        position: Position,
        current_price: float,
        levels: PositionLevels,
    ) -> ExitCheckResult | None:
        """Check if stop-loss is triggered."""
        if current_price > levels.stop_loss_price:
            return None

        logger.info(
            "stop_loss_triggered",
            position_id=position.id[:8],
            current_price=current_price,
            stop_loss=levels.stop_loss_price,
        )

        # If moonbag, check moonbag stop instead
        if position.is_moonbag:
            if levels.moonbag_stop_price and current_price <= levels.moonbag_stop_price:
                return ExitCheckResult(
                    should_exit=True,
                    exit_reason=ExitReason.MOONBAG_STOP,
                    sell_percentage=100,
                    is_full_exit=True,
                )
            # Moonbag rides to zero if no moonbag stop - no exit
            return None

        return ExitCheckResult(
            should_exit=True,
            exit_reason=ExitReason.STOP_LOSS,
            sell_percentage=100,
            is_full_exit=True,
        )

    def _check_trailing_stop(
        self,
        position: Position,
        current_price: float,
        levels: PositionLevels,
        strategy: ExitStrategy,
    ) -> ExitCheckResult | None:
        """Check if trailing stop is triggered."""
        if levels.trailing_stop_current_price is None:
            return None
        if current_price > levels.trailing_stop_current_price:
            return None

        # Trailing stop sells all non-moonbag portion
        sell_pct = (
            100 - strategy.moonbag.percentage if strategy.moonbag.has_moonbag else 100
        )

        # Calculate profit metrics
        peak_price = position.peak_price or current_price
        peak_multiplier = peak_price / levels.entry_price if levels.entry_price > 0 else 0
        exit_multiplier = current_price / levels.entry_price if levels.entry_price > 0 else 0

        # Profit captured = (exit - entry) / (peak - entry) * 100
        peak_profit = peak_price - levels.entry_price
        exit_profit = current_price - levels.entry_price
        profit_captured_pct = (
            (exit_profit / peak_profit * 100) if peak_profit > 0 else 0
        )

        logger.info(
            "trailing_stop_triggered",
            position_id=position.id[:8],
            current_price=current_price,
            trailing_price=levels.trailing_stop_current_price,
            peak_price=peak_price,
            peak_multiplier=round(peak_multiplier, 2),
            exit_multiplier=round(exit_multiplier, 2),
            profit_captured_pct=round(profit_captured_pct, 1),
        )

        return ExitCheckResult(
            should_exit=True,
            exit_reason=ExitReason.TRAILING_STOP,
            sell_percentage=sell_pct,
            is_full_exit=not strategy.moonbag.has_moonbag,
        )

    def _check_take_profit(
        self,
        position: Position,
        current_price: float,
        levels: PositionLevels,
        strategy: ExitStrategy,
    ) -> ExitCheckResult | None:
        """Check if take-profit level is reached."""
        next_tp = levels.next_take_profit
        if not next_tp or current_price < next_tp.trigger_price:
            return None

        logger.info(
            "take_profit_triggered",
            position_id=position.id[:8],
            level=next_tp.level_type,
            current_price=current_price,
            trigger_price=next_tp.trigger_price,
        )

        # Calculate actual sell percentage accounting for moonbag
        remaining_tradeable = 100 - strategy.moonbag.percentage
        actual_sell_pct = (next_tp.sell_percentage / 100) * remaining_tradeable

        return ExitCheckResult(
            should_exit=True,
            exit_reason=ExitReason.TAKE_PROFIT,
            level=next_tp,
            sell_percentage=actual_sell_pct,
            is_full_exit=False,
        )

    def _check_time_exits(
        self,
        position: Position,
        current_price: float,
        strategy: ExitStrategy,
    ) -> ExitCheckResult | None:
        """Check if time-based exit should trigger.

        Args:
            position: Position to check
            current_price: Current token price
            strategy: Exit strategy

        Returns:
            ExitCheckResult if time-based exit triggered, else None
        """
        if not strategy.has_time_limits:
            return None

        time_rules = strategy.time_rules
        time_result = self._time_manager.check_time_exits(
            position, time_rules, current_price
        )

        if not time_result.should_exit:
            return None

        # Time-based exits sell entire position
        return ExitCheckResult(
            should_exit=True,
            exit_reason=time_result.exit_reason,
            sell_percentage=100,
            is_full_exit=True,
        )

    async def execute_exit(
        self,
        position: Position,
        check_result: ExitCheckResult,
        current_price: float,
    ) -> ExitExecution | None:
        """Execute an exit based on check result.

        Args:
            position: Position to exit
            check_result: Result from check_exit_conditions
            current_price: Current price for execution

        Returns:
            ExitExecution record if successful
        """
        if not check_result.should_exit:
            return None

        # Calculate tokens to sell
        tokens_to_sell = position.current_amount_tokens * (
            check_result.sell_percentage / 100
        )

        # Estimate SOL value (for trade request)
        estimated_sol = tokens_to_sell * current_price

        logger.info(
            "executing_exit",
            position_id=position.id[:8],
            reason=check_result.exit_reason.value if check_result.exit_reason else None,
            sell_percentage=check_result.sell_percentage,
            tokens=tokens_to_sell,
        )

        # Execute sell trade
        trade_request = TradeRequest(
            signal_id=position.signal_id,
            token_address=position.token_address,
            direction=SwapDirection.SELL,
            amount_sol=max(estimated_sol, 0.001),  # Ensure minimum amount
            slippage_bps=200,  # Higher slippage for exits
        )

        trade_result = await self._executor.execute(trade_request)

        if not trade_result.success:
            logger.error(
                "exit_execution_failed",
                position_id=position.id[:8],
                error=trade_result.error_message,
            )
            return None

        # Calculate realized P&L
        entry_value = tokens_to_sell * position.entry_price
        exit_value = (
            trade_result.output_amount / 1_000_000_000
            if trade_result.output_amount
            else 0
        )
        realized_pnl = exit_value - entry_value

        # Create execution record
        execution = ExitExecution(
            position_id=position.id,
            exit_reason=check_result.exit_reason,
            trigger_level=(
                check_result.level.level_type if check_result.level else "stop_loss"
            ),
            sell_percentage=check_result.sell_percentage,
            amount_tokens_sold=tokens_to_sell,
            amount_sol_received=exit_value,
            exit_price=current_price,
            tx_signature=trade_result.tx_signature or "",
            realized_pnl_sol=realized_pnl,
        )

        # Update position state
        await self._update_position_after_exit(
            position, execution, check_result, current_price
        )

        # Save execution record
        await self._position_repo.save_exit_execution(execution)

        logger.info(
            "exit_executed",
            position_id=position.id[:8],
            reason=check_result.exit_reason.value if check_result.exit_reason else None,
            pnl=round(realized_pnl, 4),
            tx=trade_result.tx_signature[:16] if trade_result.tx_signature else None,
        )

        return execution

    async def _update_position_after_exit(
        self,
        position: Position,
        execution: ExitExecution,
        check_result: ExitCheckResult,
        current_price: float,
    ) -> None:
        """Update position state after an exit execution."""
        # Update remaining tokens
        position.current_amount_tokens -= execution.amount_tokens_sold
        position.realized_pnl_sol += execution.realized_pnl_sol
        position.exit_tx_signatures.append(execution.tx_signature)
        position.updated_at = datetime.utcnow()

        # Mark level as triggered if take-profit
        if check_result.level and position.levels:
            for level in position.levels.take_profit_levels:
                if level.level_type == check_result.level.level_type:
                    level.is_triggered = True
                    level.triggered_at = datetime.utcnow()
                    level.tx_signature = execution.tx_signature
                    break

        # Update position status
        if check_result.is_full_exit or position.current_amount_tokens <= 0:
            position.status = PositionStatus.CLOSED
            position.exit_reason = check_result.exit_reason
            position.exit_time = datetime.utcnow()
            position.exit_price = current_price
        elif position.levels and position.levels.all_take_profits_hit:
            # All TPs hit, only moonbag remains
            position.status = PositionStatus.MOONBAG
            position.is_moonbag = True
        else:
            position.status = PositionStatus.PARTIAL_EXIT

        # Save to database
        await self._position_repo.update(position)

    async def process_position(
        self,
        position: Position,
        current_price: float,
    ) -> ExitExecution | None:
        """Process a single position for exit conditions.

        Args:
            position: Position to process
            current_price: Current token price

        Returns:
            ExitExecution if exit was executed
        """
        # Get exit strategy
        strategy = await self._strategy_repo.get_by_id(position.exit_strategy_id)
        if not strategy:
            logger.error("strategy_not_found", strategy_id=position.exit_strategy_id)
            return None

        # Update peak price for trailing stop
        if position.peak_price is None or current_price > position.peak_price:
            position.peak_price = current_price

        # Update trailing stop levels if needed
        if position.levels and strategy.trailing_stop.enabled:
            position.levels = self._calculator.recalculate_trailing_stop(
                position.levels, current_price, strategy
            )

        # Check exit conditions
        check_result = self.check_exit_conditions(position, current_price, strategy)

        # Execute if needed
        if check_result.should_exit:
            return await self.execute_exit(position, check_result, current_price)

        # Update last check time
        position.last_price_check = datetime.utcnow()
        await self._position_repo.update(position)

        return None


# Singleton
_exit_manager: ExitManager | None = None


async def get_exit_manager() -> ExitManager:
    """Get or create exit manager singleton."""
    global _exit_manager
    if _exit_manager is None:
        _exit_manager = ExitManager()
        await _exit_manager.initialize()
    return _exit_manager
