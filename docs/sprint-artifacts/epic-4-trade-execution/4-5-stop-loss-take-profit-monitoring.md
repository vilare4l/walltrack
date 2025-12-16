# Story 4.5: Stop-Loss and Take-Profit Monitoring

## Story Info
- **Epic**: Epic 4 - Automated Trade Execution & Position Management
- **Status**: ready
- **Priority**: High
- **FR**: FR21, FR22

## User Story

**As an** operator,
**I want** the system to monitor and execute stop-loss and take-profit levels,
**So that** positions are closed at predetermined prices.

## Acceptance Criteria

### AC 1: Level Calculation
**Given** an open position with assigned exit strategy
**When** position is created
**Then** stop-loss price is calculated from entry price and strategy
**And** take-profit levels are calculated for each tier
**And** levels are stored with position

### AC 2: Price Monitoring
**Given** position monitoring loop
**When** current price is fetched
**Then** price is compared against stop-loss level
**And** price is compared against each take-profit level

### AC 3: Stop-Loss Trigger
**Given** price hits stop-loss
**When** stop-loss is triggered
**Then** full remaining position is sold
**And** trade is recorded with exit_reason = "stop_loss"
**And** position is closed

### AC 4: Take-Profit Trigger
**Given** price hits take-profit level N
**When** take-profit is triggered
**Then** configured percentage at that level is sold
**And** partial sale is recorded
**And** remaining position continues with next levels

### AC 5: Moonbag Handling
**Given** all take-profit levels hit (except moonbag)
**When** moonbag_pct > 0
**Then** moonbag portion remains open
**And** moonbag follows its own stop (or rides to zero)

## Technical Notes

- FR21: Set and monitor stop-loss levels
- FR22: Set and monitor take-profit levels
- Implement in `src/walltrack/core/execution/exit_manager.py`
- Price monitoring via DexScreener or on-chain polling

---

## Technical Specification

### 1. Data Models

```python
# src/walltrack/models/position.py
from __future__ import annotations
from enum import Enum
from datetime import datetime
from decimal import Decimal
from pydantic import BaseModel, Field, field_validator, computed_field
import uuid


class PositionStatus(str, Enum):
    """Status of a position."""
    PENDING = "pending"          # Trade submitted, not confirmed
    OPEN = "open"                # Active position
    PARTIAL_EXIT = "partial_exit"  # Some take profits hit
    CLOSING = "closing"          # Exit in progress
    CLOSED = "closed"            # Fully exited
    MOONBAG = "moonbag"          # Only moonbag remains


class ExitReason(str, Enum):
    """Reason for position exit."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TRAILING_STOP = "trailing_stop"
    TIME_LIMIT = "time_limit"
    STAGNATION = "stagnation"
    MANUAL = "manual"
    MOONBAG_STOP = "moonbag_stop"


class CalculatedLevel(BaseModel):
    """A calculated price level (SL or TP)."""

    level_type: str = Field(..., description="stop_loss, take_profit_1, etc.")
    trigger_price: float = Field(..., gt=0)
    sell_percentage: float = Field(..., ge=0, le=100)
    is_triggered: bool = Field(default=False)
    triggered_at: datetime | None = Field(None)
    tx_signature: str | None = Field(None)


class PositionLevels(BaseModel):
    """All calculated exit levels for a position."""

    entry_price: float = Field(..., gt=0)
    stop_loss_price: float = Field(..., gt=0)
    take_profit_levels: list[CalculatedLevel] = Field(default_factory=list)
    trailing_stop_activation_price: float | None = Field(None)
    trailing_stop_current_price: float | None = Field(None)  # Updates as price rises
    moonbag_stop_price: float | None = Field(None)

    @computed_field
    @property
    def next_take_profit(self) -> CalculatedLevel | None:
        """Get next un-triggered take profit level."""
        for level in self.take_profit_levels:
            if not level.is_triggered:
                return level
        return None

    @computed_field
    @property
    def all_take_profits_hit(self) -> bool:
        """Check if all take profit levels have been triggered."""
        return all(level.is_triggered for level in self.take_profit_levels)


class Position(BaseModel):
    """An open or closed trading position."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    signal_id: str = Field(..., description="Source signal ID")
    token_address: str = Field(...)
    token_symbol: str | None = Field(None)

    # Status
    status: PositionStatus = Field(default=PositionStatus.PENDING)

    # Entry details
    entry_tx_signature: str | None = Field(None)
    entry_price: float = Field(..., gt=0)
    entry_amount_sol: float = Field(..., gt=0)
    entry_amount_tokens: float = Field(..., gt=0)
    entry_time: datetime = Field(default_factory=datetime.utcnow)

    # Current state
    current_amount_tokens: float = Field(..., ge=0)
    realized_pnl_sol: float = Field(default=0.0)

    # Exit strategy
    exit_strategy_id: str = Field(...)
    conviction_tier: str = Field(...)  # "high" or "standard"
    levels: PositionLevels | None = Field(None)

    # Moonbag tracking
    is_moonbag: bool = Field(default=False)
    moonbag_percentage: float = Field(default=0.0)

    # Exit details (when closed)
    exit_reason: ExitReason | None = Field(None)
    exit_time: datetime | None = Field(None)
    exit_price: float | None = Field(None)
    exit_tx_signatures: list[str] = Field(default_factory=list)

    # Tracking
    last_price_check: datetime | None = Field(None)
    peak_price: float | None = Field(None)  # For trailing stop
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def current_value_multiple(self) -> float | None:
        """Current price as multiple of entry (e.g., 2.0 = 2x)."""
        if self.peak_price and self.entry_price > 0:
            return self.peak_price / self.entry_price
        return None

    @computed_field
    @property
    def is_in_profit(self) -> bool:
        """Check if position is currently profitable."""
        if self.peak_price:
            return self.peak_price > self.entry_price
        return False


class ExitExecution(BaseModel):
    """Record of an exit execution (partial or full)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str = Field(...)
    exit_reason: ExitReason
    trigger_level: str = Field(..., description="stop_loss, take_profit_1, etc.")

    # Execution details
    sell_percentage: float = Field(..., ge=0, le=100)
    amount_tokens_sold: float = Field(..., ge=0)
    amount_sol_received: float = Field(..., ge=0)
    exit_price: float = Field(..., gt=0)
    tx_signature: str = Field(...)

    # P&L
    realized_pnl_sol: float = Field(...)

    executed_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Level Calculator

```python
# src/walltrack/services/execution/level_calculator.py
from __future__ import annotations

import structlog

from walltrack.models.position import (
    Position,
    PositionLevels,
    CalculatedLevel,
)
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

            take_profit_levels.append(CalculatedLevel(
                level_type=f"take_profit_{i + 1}",
                trigger_price=trigger_price,
                sell_percentage=tp.sell_percentage,
                is_triggered=False,
            ))

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
            stop_loss=round(stop_loss_price, 6),
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

        # Trailing stop is active - update trailing price
        # Only update if price went higher
        if levels.trailing_stop_current_price is None or current_price > levels.trailing_stop_current_price:
            # Calculate new trailing stop price
            # distance_percentage = 30 means 30% below peak
            distance_multiplier = 1 - (strategy.trailing_stop.distance_percentage / 100)
            new_trailing_price = current_price * distance_multiplier

            levels.trailing_stop_current_price = new_trailing_price

            logger.debug(
                "trailing_stop_updated",
                peak_price=current_price,
                trailing_price=round(new_trailing_price, 6),
            )

        return levels


def get_level_calculator() -> LevelCalculator:
    """Get level calculator instance."""
    return LevelCalculator()
```

### 3. Exit Manager Service

```python
# src/walltrack/services/execution/exit_manager.py
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Optional

import structlog

from walltrack.models.position import (
    Position,
    PositionStatus,
    ExitReason,
    CalculatedLevel,
    ExitExecution,
)
from walltrack.models.exit_strategy import ExitStrategy
from walltrack.services.execution.level_calculator import (
    LevelCalculator,
    get_level_calculator,
)
from walltrack.services.trade.executor import TradeExecutor, get_trade_executor
from walltrack.models.trade import TradeRequest, SwapDirection
from walltrack.repositories.position_repository import (
    PositionRepository,
    get_position_repository,
)
from walltrack.repositories.exit_strategy_repository import (
    ExitStrategyRepository,
    get_exit_strategy_repository,
)

logger = structlog.get_logger()


class ExitCheckResult:
    """Result of checking exit conditions."""

    def __init__(
        self,
        should_exit: bool,
        exit_reason: ExitReason | None = None,
        level: CalculatedLevel | None = None,
        sell_percentage: float = 0,
        is_full_exit: bool = False,
    ):
        self.should_exit = should_exit
        self.exit_reason = exit_reason
        self.level = level
        self.sell_percentage = sell_percentage
        self.is_full_exit = is_full_exit


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
    ):
        self._calculator = level_calculator or get_level_calculator()
        self._executor = trade_executor
        self._position_repo = position_repo
        self._strategy_repo = strategy_repo
        self._running = False

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._executor is None:
            self._executor = await get_trade_executor()
        if self._position_repo is None:
            self._position_repo = await get_position_repository()
        if self._strategy_repo is None:
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

        # 1. Check stop-loss (full exit)
        if current_price <= levels.stop_loss_price:
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
                elif levels.moonbag_stop_price is None:
                    # Ride to zero - no exit
                    return ExitCheckResult(should_exit=False)
            else:
                return ExitCheckResult(
                    should_exit=True,
                    exit_reason=ExitReason.STOP_LOSS,
                    sell_percentage=100,
                    is_full_exit=True,
                )

        # 2. Check trailing stop (if active)
        if (
            levels.trailing_stop_current_price is not None
            and current_price <= levels.trailing_stop_current_price
        ):
            # Determine what to sell
            # Trailing stop sells all non-moonbag portion
            sell_pct = 100 - strategy.moonbag.percentage if strategy.moonbag.has_moonbag else 100

            logger.info(
                "trailing_stop_triggered",
                position_id=position.id[:8],
                current_price=current_price,
                trailing_price=levels.trailing_stop_current_price,
            )

            return ExitCheckResult(
                should_exit=True,
                exit_reason=ExitReason.TRAILING_STOP,
                sell_percentage=sell_pct,
                is_full_exit=not strategy.moonbag.has_moonbag,
            )

        # 3. Check take-profit levels (partial exits)
        next_tp = levels.next_take_profit
        if next_tp and current_price >= next_tp.trigger_price:
            logger.info(
                "take_profit_triggered",
                position_id=position.id[:8],
                level=next_tp.level_type,
                current_price=current_price,
                trigger_price=next_tp.trigger_price,
            )

            # Calculate actual sell percentage accounting for moonbag
            # If moonbag = 34%, remaining tradeable = 66%
            # If TP says sell 50%, we sell 50% of 66% = 33%
            remaining_tradeable = 100 - strategy.moonbag.percentage
            actual_sell_pct = (next_tp.sell_percentage / 100) * remaining_tradeable

            return ExitCheckResult(
                should_exit=True,
                exit_reason=ExitReason.TAKE_PROFIT,
                level=next_tp,
                sell_percentage=actual_sell_pct,
                is_full_exit=False,
            )

        return ExitCheckResult(should_exit=False)

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
        tokens_to_sell = position.current_amount_tokens * (check_result.sell_percentage / 100)

        # Estimate SOL value (for trade request)
        estimated_sol = tokens_to_sell * current_price

        logger.info(
            "executing_exit",
            position_id=position.id[:8],
            reason=check_result.exit_reason.value,
            sell_percentage=check_result.sell_percentage,
            tokens=tokens_to_sell,
        )

        # Execute sell trade
        trade_request = TradeRequest(
            signal_id=position.signal_id,
            token_address=position.token_address,
            direction=SwapDirection.SELL,
            amount_sol=estimated_sol,  # This will be adjusted by actual sell
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
        exit_value = trade_result.output_amount / 1_000_000_000 if trade_result.output_amount else 0
        realized_pnl = exit_value - entry_value

        # Create execution record
        execution = ExitExecution(
            position_id=position.id,
            exit_reason=check_result.exit_reason,
            trigger_level=check_result.level.level_type if check_result.level else "stop_loss",
            sell_percentage=check_result.sell_percentage,
            amount_tokens_sold=tokens_to_sell,
            amount_sol_received=exit_value,
            exit_price=current_price,
            tx_signature=trade_result.tx_signature,
            realized_pnl_sol=realized_pnl,
        )

        # Update position state
        await self._update_position_after_exit(
            position, execution, check_result, current_price
        )

        logger.info(
            "exit_executed",
            position_id=position.id[:8],
            reason=check_result.exit_reason.value,
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
```

### 4. Price Monitor Service

```python
# src/walltrack/services/execution/price_monitor.py
from __future__ import annotations
import asyncio
from datetime import datetime
from typing import Callable, Optional

import structlog

from walltrack.models.position import Position, PositionStatus
from walltrack.services.execution.exit_manager import ExitManager, get_exit_manager
from walltrack.services.token.fetcher import TokenFetcher, get_token_fetcher
from walltrack.repositories.position_repository import (
    PositionRepository,
    get_position_repository,
)

logger = structlog.get_logger()


class PriceMonitor:
    """Monitors prices for open positions and triggers exits.

    Runs a continuous loop checking prices against exit levels.
    """

    def __init__(
        self,
        exit_manager: ExitManager | None = None,
        token_fetcher: TokenFetcher | None = None,
        position_repo: PositionRepository | None = None,
        poll_interval_seconds: float = 5.0,
    ):
        self._exit_manager = exit_manager
        self._token_fetcher = token_fetcher
        self._position_repo = position_repo
        self._poll_interval = poll_interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    async def initialize(self) -> None:
        """Initialize dependencies."""
        if self._exit_manager is None:
            self._exit_manager = await get_exit_manager()
        if self._token_fetcher is None:
            self._token_fetcher = await get_token_fetcher()
        if self._position_repo is None:
            self._position_repo = await get_position_repository()

        logger.info("price_monitor_initialized", poll_interval=self._poll_interval)

    async def start(self) -> None:
        """Start the price monitoring loop."""
        if self._running:
            logger.warning("price_monitor_already_running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitoring_loop())
        logger.info("price_monitor_started")

    async def stop(self) -> None:
        """Stop the price monitoring loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("price_monitor_stopped")

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_positions()
            except Exception as e:
                logger.error("price_monitor_error", error=str(e))

            await asyncio.sleep(self._poll_interval)

    async def _check_all_positions(self) -> None:
        """Check all open positions for exit conditions."""
        # Get all open positions
        open_positions = await self._position_repo.list_open()

        if not open_positions:
            return

        logger.debug("checking_positions", count=len(open_positions))

        # Group positions by token for efficient price fetching
        tokens_to_check: dict[str, list[Position]] = {}
        for position in open_positions:
            if position.token_address not in tokens_to_check:
                tokens_to_check[position.token_address] = []
            tokens_to_check[position.token_address].append(position)

        # Fetch prices and process positions
        for token_address, positions in tokens_to_check.items():
            try:
                # Fetch current price
                token_data = await self._token_fetcher.fetch(token_address)
                if not token_data.success or token_data.characteristics is None:
                    logger.warning(
                        "price_fetch_failed",
                        token=token_address[:8],
                    )
                    continue

                current_price = token_data.characteristics.price_usd

                # Process each position for this token
                for position in positions:
                    await self._exit_manager.process_position(position, current_price)

            except Exception as e:
                logger.error(
                    "position_check_error",
                    token=token_address[:8],
                    error=str(e),
                )

    async def check_single_position(self, position_id: str) -> bool:
        """Check a single position immediately.

        Args:
            position_id: Position ID to check

        Returns:
            True if exit was triggered
        """
        position = await self._position_repo.get_by_id(position_id)
        if not position or position.status not in [
            PositionStatus.OPEN,
            PositionStatus.PARTIAL_EXIT,
            PositionStatus.MOONBAG,
        ]:
            return False

        # Fetch price
        token_data = await self._token_fetcher.fetch(position.token_address)
        if not token_data.success or token_data.characteristics is None:
            return False

        current_price = token_data.characteristics.price_usd

        # Process
        execution = await self._exit_manager.process_position(position, current_price)
        return execution is not None


# Singleton
_price_monitor: PriceMonitor | None = None


async def get_price_monitor() -> PriceMonitor:
    """Get or create price monitor singleton."""
    global _price_monitor
    if _price_monitor is None:
        _price_monitor = PriceMonitor()
        await _price_monitor.initialize()
    return _price_monitor
```

### 5. Repository

```python
# src/walltrack/repositories/position_repository.py
from __future__ import annotations
from datetime import datetime
from typing import Optional

import structlog
from supabase import AsyncClient

from walltrack.models.position import (
    Position,
    PositionStatus,
    PositionLevels,
    CalculatedLevel,
    ExitExecution,
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger()


class PositionRepository:
    """Repository for position storage and retrieval."""

    def __init__(self, client: AsyncClient):
        self._client = client

    async def create(self, position: Position) -> Position:
        """Create new position."""
        data = self._serialize_position(position)

        result = await (
            self._client.table("positions")
            .insert(data)
            .execute()
        )

        logger.info("position_created", id=position.id[:8], token=position.token_address[:8])
        return self._deserialize_position(result.data[0])

    async def update(self, position: Position) -> Position:
        """Update position."""
        position.updated_at = datetime.utcnow()
        data = self._serialize_position(position)

        result = await (
            self._client.table("positions")
            .update(data)
            .eq("id", position.id)
            .execute()
        )

        return self._deserialize_position(result.data[0])

    async def get_by_id(self, position_id: str) -> Position | None:
        """Get position by ID."""
        result = await (
            self._client.table("positions")
            .select("*")
            .eq("id", position_id)
            .single()
            .execute()
        )

        if result.data:
            return self._deserialize_position(result.data)
        return None

    async def list_open(self) -> list[Position]:
        """List all open positions."""
        result = await (
            self._client.table("positions")
            .select("*")
            .in_("status", ["open", "partial_exit", "moonbag"])
            .execute()
        )

        return [self._deserialize_position(row) for row in result.data]

    async def list_by_token(self, token_address: str) -> list[Position]:
        """List positions for a specific token."""
        result = await (
            self._client.table("positions")
            .select("*")
            .eq("token_address", token_address)
            .order("created_at", desc=True)
            .execute()
        )

        return [self._deserialize_position(row) for row in result.data]

    async def count_open(self) -> int:
        """Count open positions."""
        result = await (
            self._client.table("positions")
            .select("id", count="exact")
            .in_("status", ["open", "partial_exit", "moonbag"])
            .execute()
        )

        return result.count or 0

    async def save_exit_execution(self, execution: ExitExecution) -> None:
        """Save exit execution record."""
        data = {
            "id": execution.id,
            "position_id": execution.position_id,
            "exit_reason": execution.exit_reason.value,
            "trigger_level": execution.trigger_level,
            "sell_percentage": execution.sell_percentage,
            "amount_tokens_sold": execution.amount_tokens_sold,
            "amount_sol_received": execution.amount_sol_received,
            "exit_price": execution.exit_price,
            "tx_signature": execution.tx_signature,
            "realized_pnl_sol": execution.realized_pnl_sol,
            "executed_at": execution.executed_at.isoformat(),
        }

        await (
            self._client.table("exit_executions")
            .insert(data)
            .execute()
        )

    def _serialize_position(self, position: Position) -> dict:
        """Serialize position for database."""
        levels_data = None
        if position.levels:
            levels_data = {
                "entry_price": position.levels.entry_price,
                "stop_loss_price": position.levels.stop_loss_price,
                "take_profit_levels": [
                    {
                        "level_type": tp.level_type,
                        "trigger_price": tp.trigger_price,
                        "sell_percentage": tp.sell_percentage,
                        "is_triggered": tp.is_triggered,
                        "triggered_at": tp.triggered_at.isoformat() if tp.triggered_at else None,
                        "tx_signature": tp.tx_signature,
                    }
                    for tp in position.levels.take_profit_levels
                ],
                "trailing_stop_activation_price": position.levels.trailing_stop_activation_price,
                "trailing_stop_current_price": position.levels.trailing_stop_current_price,
                "moonbag_stop_price": position.levels.moonbag_stop_price,
            }

        return {
            "id": position.id,
            "signal_id": position.signal_id,
            "token_address": position.token_address,
            "token_symbol": position.token_symbol,
            "status": position.status.value,
            "entry_tx_signature": position.entry_tx_signature,
            "entry_price": position.entry_price,
            "entry_amount_sol": position.entry_amount_sol,
            "entry_amount_tokens": position.entry_amount_tokens,
            "entry_time": position.entry_time.isoformat(),
            "current_amount_tokens": position.current_amount_tokens,
            "realized_pnl_sol": position.realized_pnl_sol,
            "exit_strategy_id": position.exit_strategy_id,
            "conviction_tier": position.conviction_tier,
            "levels": levels_data,
            "is_moonbag": position.is_moonbag,
            "moonbag_percentage": position.moonbag_percentage,
            "exit_reason": position.exit_reason.value if position.exit_reason else None,
            "exit_time": position.exit_time.isoformat() if position.exit_time else None,
            "exit_price": position.exit_price,
            "exit_tx_signatures": position.exit_tx_signatures,
            "last_price_check": position.last_price_check.isoformat() if position.last_price_check else None,
            "peak_price": position.peak_price,
            "created_at": position.created_at.isoformat(),
            "updated_at": position.updated_at.isoformat(),
        }

    def _deserialize_position(self, data: dict) -> Position:
        """Deserialize position from database."""
        levels = None
        if data.get("levels"):
            lvl = data["levels"]
            tp_levels = [
                CalculatedLevel(
                    level_type=tp["level_type"],
                    trigger_price=tp["trigger_price"],
                    sell_percentage=tp["sell_percentage"],
                    is_triggered=tp.get("is_triggered", False),
                    triggered_at=datetime.fromisoformat(tp["triggered_at"]) if tp.get("triggered_at") else None,
                    tx_signature=tp.get("tx_signature"),
                )
                for tp in lvl.get("take_profit_levels", [])
            ]
            levels = PositionLevels(
                entry_price=lvl["entry_price"],
                stop_loss_price=lvl["stop_loss_price"],
                take_profit_levels=tp_levels,
                trailing_stop_activation_price=lvl.get("trailing_stop_activation_price"),
                trailing_stop_current_price=lvl.get("trailing_stop_current_price"),
                moonbag_stop_price=lvl.get("moonbag_stop_price"),
            )

        from walltrack.models.position import ExitReason
        exit_reason = None
        if data.get("exit_reason"):
            exit_reason = ExitReason(data["exit_reason"])

        return Position(
            id=data["id"],
            signal_id=data["signal_id"],
            token_address=data["token_address"],
            token_symbol=data.get("token_symbol"),
            status=PositionStatus(data["status"]),
            entry_tx_signature=data.get("entry_tx_signature"),
            entry_price=data["entry_price"],
            entry_amount_sol=data["entry_amount_sol"],
            entry_amount_tokens=data["entry_amount_tokens"],
            entry_time=datetime.fromisoformat(data["entry_time"].replace("Z", "+00:00")),
            current_amount_tokens=data["current_amount_tokens"],
            realized_pnl_sol=data.get("realized_pnl_sol", 0),
            exit_strategy_id=data["exit_strategy_id"],
            conviction_tier=data["conviction_tier"],
            levels=levels,
            is_moonbag=data.get("is_moonbag", False),
            moonbag_percentage=data.get("moonbag_percentage", 0),
            exit_reason=exit_reason,
            exit_time=datetime.fromisoformat(data["exit_time"].replace("Z", "+00:00")) if data.get("exit_time") else None,
            exit_price=data.get("exit_price"),
            exit_tx_signatures=data.get("exit_tx_signatures", []),
            last_price_check=datetime.fromisoformat(data["last_price_check"].replace("Z", "+00:00")) if data.get("last_price_check") else None,
            peak_price=data.get("peak_price"),
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
        )


# Singleton
_repo: PositionRepository | None = None


async def get_position_repository() -> PositionRepository:
    """Get or create position repository singleton."""
    global _repo
    if _repo is None:
        client = await get_supabase_client()
        _repo = PositionRepository(client)
    return _repo
```

### 6. Unit Tests

```python
# tests/unit/services/execution/test_exit_manager.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

from walltrack.services.execution.exit_manager import ExitManager, ExitCheckResult
from walltrack.services.execution.level_calculator import LevelCalculator
from walltrack.models.position import (
    Position,
    PositionStatus,
    PositionLevels,
    CalculatedLevel,
    ExitReason,
)
from walltrack.models.exit_strategy import (
    ExitStrategy,
    TakeProfitLevel,
    TrailingStopConfig,
    MoonbagConfig,
)


@pytest.fixture
def strategy():
    """Create test exit strategy."""
    return ExitStrategy(
        id="test-strategy",
        name="Test Strategy",
        take_profit_levels=[
            TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
            TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
        ],
        stop_loss=0.5,  # -50%
        trailing_stop=TrailingStopConfig(enabled=False),
        moonbag=MoonbagConfig(percentage=0),
    )


@pytest.fixture
def position_with_levels():
    """Create test position with calculated levels."""
    levels = PositionLevels(
        entry_price=0.001,
        stop_loss_price=0.0005,  # -50%
        take_profit_levels=[
            CalculatedLevel(
                level_type="take_profit_1",
                trigger_price=0.002,  # 2x
                sell_percentage=50,
            ),
            CalculatedLevel(
                level_type="take_profit_2",
                trigger_price=0.003,  # 3x
                sell_percentage=100,
            ),
        ],
    )

    return Position(
        id="test-position",
        signal_id="test-signal",
        token_address="TokenAddress123456789012345678901234567890123",
        status=PositionStatus.OPEN,
        entry_price=0.001,
        entry_amount_sol=0.1,
        entry_amount_tokens=100,
        current_amount_tokens=100,
        exit_strategy_id="test-strategy",
        conviction_tier="standard",
        levels=levels,
    )


class TestLevelCalculator:
    """Tests for level calculator."""

    def test_calculate_stop_loss(self):
        """Test stop loss calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,  # -50%
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.stop_loss_price == 0.0005  # 50% of entry

    def test_calculate_take_profits(self):
        """Test take profit level calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            take_profit_levels=[
                TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
                TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
            ],
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert len(levels.take_profit_levels) == 2
        assert levels.take_profit_levels[0].trigger_price == 0.002  # 2x
        assert levels.take_profit_levels[1].trigger_price == 0.003  # 3x

    def test_calculate_trailing_stop_activation(self):
        """Test trailing stop activation price calculation."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        assert levels.trailing_stop_activation_price == 0.002  # 2x


class TestExitManagerCheckConditions:
    """Tests for exit condition checking."""

    def test_stop_loss_triggered(self, position_with_levels, strategy):
        """Test stop loss detection."""
        manager = ExitManager()

        # Price at stop loss level
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0005,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.STOP_LOSS
        assert result.sell_percentage == 100
        assert result.is_full_exit is True

    def test_take_profit_triggered(self, position_with_levels, strategy):
        """Test take profit detection."""
        manager = ExitManager()

        # Price at first TP level
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.002,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.TAKE_PROFIT
        assert result.level.level_type == "take_profit_1"
        assert result.is_full_exit is False

    def test_no_exit_between_levels(self, position_with_levels, strategy):
        """Test no exit when price is between levels."""
        manager = ExitManager()

        # Price between entry and first TP
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0015,
            strategy=strategy,
        )

        assert result.should_exit is False

    def test_moonbag_not_sold_on_stop_loss(self, position_with_levels):
        """Test moonbag ignores normal stop loss."""
        position_with_levels.is_moonbag = True
        position_with_levels.levels.moonbag_stop_price = None  # Ride to zero

        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=None),
        )

        manager = ExitManager()

        # Price at stop loss
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0005,
            strategy=strategy,
        )

        assert result.should_exit is False  # Moonbag rides to zero

    def test_moonbag_sold_at_moonbag_stop(self, position_with_levels):
        """Test moonbag sold when moonbag stop hit."""
        position_with_levels.is_moonbag = True
        position_with_levels.levels.moonbag_stop_price = 0.0002  # -80%

        strategy = ExitStrategy(
            name="Test",
            stop_loss=0.5,
            moonbag=MoonbagConfig(percentage=50, stop_loss=0.8),
        )

        manager = ExitManager()

        # Price at moonbag stop
        result = manager.check_exit_conditions(
            position_with_levels,
            current_price=0.0001,
            strategy=strategy,
        )

        assert result.should_exit is True
        assert result.exit_reason == ExitReason.MOONBAG_STOP


class TestTrailingStopRecalculation:
    """Tests for trailing stop updates."""

    def test_trailing_stop_activates(self):
        """Test trailing stop activation at threshold."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # Price reaches activation (2x)
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.002, strategy=strategy
        )

        # Trailing stop should be 30% below 0.002 = 0.0014
        assert levels.trailing_stop_current_price == pytest.approx(0.0014, rel=0.01)

    def test_trailing_stop_moves_up(self):
        """Test trailing stop moves up with price."""
        calculator = LevelCalculator()
        strategy = ExitStrategy(
            name="Test",
            trailing_stop=TrailingStopConfig(
                enabled=True,
                activation_multiplier=2.0,
                distance_percentage=30,
            ),
        )

        levels = calculator.calculate_levels(entry_price=0.001, strategy=strategy)

        # First activation
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.002, strategy=strategy
        )
        first_trailing = levels.trailing_stop_current_price

        # Price goes higher
        levels = calculator.recalculate_trailing_stop(
            levels, current_price=0.003, strategy=strategy
        )

        # Trailing stop should have moved up
        assert levels.trailing_stop_current_price > first_trailing
```

### 7. Database Schema

```sql
-- migrations/008_positions.sql

-- Positions table
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    signal_id UUID NOT NULL,
    token_address TEXT NOT NULL,
    token_symbol TEXT,

    -- Status
    status TEXT NOT NULL DEFAULT 'pending',

    -- Entry details
    entry_tx_signature TEXT,
    entry_price DECIMAL(30, 18) NOT NULL,
    entry_amount_sol DECIMAL(20, 9) NOT NULL,
    entry_amount_tokens DECIMAL(30, 0) NOT NULL,
    entry_time TIMESTAMPTZ NOT NULL,

    -- Current state
    current_amount_tokens DECIMAL(30, 0) NOT NULL,
    realized_pnl_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,

    -- Exit strategy
    exit_strategy_id TEXT NOT NULL REFERENCES exit_strategies(id),
    conviction_tier TEXT NOT NULL,
    levels JSONB,

    -- Moonbag
    is_moonbag BOOLEAN NOT NULL DEFAULT false,
    moonbag_percentage DECIMAL(5, 2) NOT NULL DEFAULT 0,

    -- Exit details
    exit_reason TEXT,
    exit_time TIMESTAMPTZ,
    exit_price DECIMAL(30, 18),
    exit_tx_signatures TEXT[] NOT NULL DEFAULT '{}',

    -- Tracking
    last_price_check TIMESTAMPTZ,
    peak_price DECIMAL(30, 18),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('pending', 'open', 'partial_exit', 'closing', 'closed', 'moonbag')),
    CONSTRAINT valid_exit_reason CHECK (exit_reason IS NULL OR exit_reason IN (
        'stop_loss', 'take_profit', 'trailing_stop', 'time_limit', 'stagnation', 'manual', 'moonbag_stop'
    ))
);

CREATE INDEX IF NOT EXISTS idx_positions_status ON positions(status);
CREATE INDEX IF NOT EXISTS idx_positions_token ON positions(token_address);
CREATE INDEX IF NOT EXISTS idx_positions_created ON positions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_positions_open ON positions(status) WHERE status IN ('open', 'partial_exit', 'moonbag');

-- Exit executions table
CREATE TABLE IF NOT EXISTS exit_executions (
    id TEXT PRIMARY KEY,
    position_id TEXT NOT NULL REFERENCES positions(id) ON DELETE CASCADE,
    exit_reason TEXT NOT NULL,
    trigger_level TEXT NOT NULL,

    sell_percentage DECIMAL(5, 2) NOT NULL,
    amount_tokens_sold DECIMAL(30, 0) NOT NULL,
    amount_sol_received DECIMAL(20, 9) NOT NULL,
    exit_price DECIMAL(30, 18) NOT NULL,
    tx_signature TEXT NOT NULL,

    realized_pnl_sol DECIMAL(20, 9) NOT NULL,
    executed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_exit_executions_position ON exit_executions(position_id);
CREATE INDEX IF NOT EXISTS idx_exit_executions_reason ON exit_executions(exit_reason);

-- RLS Policies
ALTER TABLE positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE exit_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on positions"
ON positions FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on exit_executions"
ON exit_executions FOR ALL TO service_role USING (true);
```

## Implementation Tasks

- [ ] Create `src/walltrack/models/position.py` with Position and related models
- [ ] Create `src/walltrack/services/execution/level_calculator.py`
- [ ] Create `src/walltrack/services/execution/exit_manager.py`
- [ ] Create `src/walltrack/services/execution/price_monitor.py`
- [ ] Create `src/walltrack/repositories/position_repository.py`
- [ ] Calculate SL/TP levels from entry price and strategy
- [ ] Implement price monitoring loop (5s interval)
- [ ] Execute stop-loss full sells
- [ ] Execute take-profit partial sells
- [ ] Handle moonbag positions correctly
- [ ] Record exit reasons and tx signatures
- [ ] Add database migrations
- [ ] Write comprehensive unit tests

## Definition of Done

- [ ] SL/TP levels calculated correctly from strategy
- [ ] Price monitoring runs continuously
- [ ] Stop-loss executes full position sell
- [ ] Take-profit executes partial sells at each level
- [ ] Moonbag portion protected from normal stop-loss
- [ ] Moonbag follows its own stop or rides to zero
- [ ] All exits recorded with reason and tx signature
- [ ] Unit tests pass with >90% coverage
