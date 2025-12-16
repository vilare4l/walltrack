# Story 8.2: Backtest Engine Core

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: High
- **FR**: FR62

## User Story

**As an** operator,
**I want** a backtest engine that replays historical signals with configurable parameters,
**So that** I can see how different settings would have performed.

## Acceptance Criteria

### AC 1: Signal Replay
**Given** historical data exists for a date range
**When** backtest is initiated with parameters
**Then** signals are replayed in chronological order
**And** each signal is scored with provided parameters
**And** trade decisions are made based on new scores

### AC 2: Historical Scoring
**Given** a signal during backtest replay
**When** scoring is applied
**Then** wallet score uses historical value (or current if unavailable)
**And** cluster amplification uses historical cluster state
**And** token score uses historical token data

### AC 3: Trade Simulation
**Given** trade decision in backtest
**When** simulated trade executes
**Then** entry price uses historical price at signal time
**And** exit is determined by strategy and subsequent prices
**And** P&L is calculated from historical prices

### AC 4: Results Compilation
**Given** backtest completes
**When** results are compiled
**Then** all simulated trades are listed
**And** aggregate metrics are calculated
**And** comparison to actual results (if any) is available

## Technical Specifications

### Backtest Parameters Model

**src/walltrack/core/backtest/parameters.py:**
```python
"""Backtest parameter configuration."""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Scoring weights for backtest."""

    wallet_weight: Decimal = Decimal("0.30")
    cluster_weight: Decimal = Decimal("0.25")
    token_weight: Decimal = Decimal("0.25")
    context_weight: Decimal = Decimal("0.20")

    def validate_weights(self) -> bool:
        """Ensure weights sum to 1.0."""
        total = (
            self.wallet_weight
            + self.cluster_weight
            + self.token_weight
            + self.context_weight
        )
        return abs(total - Decimal("1.0")) < Decimal("0.01")


class ExitStrategyParams(BaseModel):
    """Exit strategy parameters for backtest."""

    stop_loss_pct: Decimal = Decimal("0.50")  # 50% loss
    take_profit_levels: list[dict] = Field(
        default_factory=lambda: [
            {"multiplier": 2.0, "sell_pct": 0.33},
            {"multiplier": 3.0, "sell_pct": 0.33},
        ]
    )
    trailing_stop_enabled: bool = True
    trailing_stop_activation: Decimal = Decimal("2.0")  # x2
    trailing_stop_distance: Decimal = Decimal("0.30")  # 30%
    moonbag_pct: Decimal = Decimal("0.34")


class BacktestParameters(BaseModel):
    """Complete backtest configuration."""

    # Date range
    start_date: datetime
    end_date: datetime

    # Scoring parameters
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: Decimal = Decimal("0.70")

    # Position sizing
    base_position_sol: Decimal = Decimal("0.1")
    high_conviction_multiplier: Decimal = Decimal("1.5")
    high_conviction_threshold: Decimal = Decimal("0.85")

    # Exit strategy
    exit_strategy: ExitStrategyParams = Field(default_factory=ExitStrategyParams)

    # Risk parameters
    max_concurrent_positions: int = 5
    max_daily_trades: int = 10

    # Simulation settings
    slippage_bps: int = 100  # 1%

    class Config:
        json_encoders = {Decimal: str}
```

### Backtest Result Model

**src/walltrack/core/backtest/results.py:**
```python
"""Backtest result models."""

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class BacktestTrade(BaseModel):
    """A simulated trade in backtest."""

    id: UUID
    signal_id: UUID
    token_address: str

    # Entry
    entry_time: datetime
    entry_price: Decimal
    position_size_sol: Decimal
    tokens_bought: Decimal

    # Exit
    exit_time: Optional[datetime] = None
    exit_price: Optional[Decimal] = None
    exit_reason: Optional[str] = None

    # Partial exits
    partial_exits: list[dict] = Field(default_factory=list)

    # P&L
    realized_pnl: Optional[Decimal] = None
    realized_pnl_pct: Optional[Decimal] = None

    # Status
    is_open: bool = True

    @computed_field
    @property
    def is_winner(self) -> Optional[bool]:
        """Check if trade was profitable."""
        if self.realized_pnl is None:
            return None
        return self.realized_pnl > 0


class BacktestMetrics(BaseModel):
    """Aggregate metrics from backtest."""

    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    open_trades: int = 0

    # P&L metrics
    total_pnl: Decimal = Decimal("0")
    total_pnl_pct: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")

    # Risk metrics
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")

    # Ratios
    win_rate: Decimal = Decimal("0")
    sharpe_ratio: Optional[Decimal] = None
    sortino_ratio: Optional[Decimal] = None

    # Timing
    average_hold_time_hours: Decimal = Decimal("0")

    # Signal metrics
    signals_processed: int = 0
    signals_traded: int = 0
    signals_skipped: int = 0

    def calculate_from_trades(self, trades: list[BacktestTrade]) -> None:
        """Calculate metrics from trade list."""
        self.total_trades = len(trades)

        closed_trades = [t for t in trades if not t.is_open]
        self.open_trades = len([t for t in trades if t.is_open])

        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if t.is_winner is False]

        self.winning_trades = len(winners)
        self.losing_trades = len(losers)

        if self.total_trades > 0:
            self.win_rate = Decimal(str(self.winning_trades / self.total_trades))

        # P&L calculations
        self.total_pnl = sum(
            t.realized_pnl for t in closed_trades if t.realized_pnl
        ) or Decimal("0")

        if winners:
            self.average_win = sum(t.realized_pnl for t in winners) / len(winners)
            self.largest_win = max(t.realized_pnl for t in winners)

        if losers:
            self.average_loss = sum(t.realized_pnl for t in losers) / len(losers)
            self.largest_loss = min(t.realized_pnl for t in losers)

        # Profit factor
        gross_profit = sum(t.realized_pnl for t in winners if t.realized_pnl) or Decimal("0")
        gross_loss = abs(sum(t.realized_pnl for t in losers if t.realized_pnl)) or Decimal("1")
        self.profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit


class BacktestResult(BaseModel):
    """Complete backtest result."""

    id: UUID
    name: str
    parameters: dict

    # Timing
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    # Results
    trades: list[BacktestTrade]
    metrics: BacktestMetrics

    # Equity curve
    equity_curve: list[dict] = Field(default_factory=list)

    # Comparison to actual (if available)
    actual_pnl: Optional[Decimal] = None
    actual_trades: Optional[int] = None
    pnl_difference: Optional[Decimal] = None
```

### Backtest Engine

**src/walltrack/core/backtest/engine.py:**
```python
"""Core backtest engine for signal replay."""

from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Optional
from uuid import uuid4

import structlog

from walltrack.core.backtest.collector import get_historical_collector
from walltrack.core.backtest.models import HistoricalSignal, PriceTimeline
from walltrack.core.backtest.parameters import BacktestParameters
from walltrack.core.backtest.results import (
    BacktestResult,
    BacktestTrade,
    BacktestMetrics,
)

log = structlog.get_logger()


class BacktestEngine:
    """Engine for replaying historical signals with different parameters."""

    def __init__(self, parameters: BacktestParameters) -> None:
        self._params = parameters
        self._trades: list[BacktestTrade] = []
        self._equity_curve: list[dict] = []
        self._current_capital = Decimal("1.0")  # Normalized
        self._peak_capital = Decimal("1.0")
        self._open_positions: dict[str, BacktestTrade] = {}

    async def run(self, name: str = "Backtest") -> BacktestResult:
        """Run the backtest."""
        started_at = datetime.now(UTC)

        collector = await get_historical_collector()

        # Get historical signals for date range
        signals = await collector.get_signals_for_range(
            start_date=self._params.start_date,
            end_date=self._params.end_date,
        )

        log.info(
            "backtest_started",
            name=name,
            signals=len(signals),
            start=self._params.start_date.isoformat(),
            end=self._params.end_date.isoformat(),
        )

        signals_traded = 0
        signals_skipped = 0

        # Process signals chronologically
        for signal in sorted(signals, key=lambda s: s.timestamp):
            # Rescore with backtest parameters
            new_score = self._rescore_signal(signal)

            # Check trade eligibility
            if new_score >= self._params.score_threshold:
                if self._can_open_position():
                    await self._open_trade(signal, new_score)
                    signals_traded += 1
                else:
                    signals_skipped += 1
            else:
                signals_skipped += 1

            # Update open positions (check exits)
            await self._update_positions(signal.timestamp)

            # Record equity curve point
            self._record_equity(signal.timestamp)

        # Close remaining open positions at end
        await self._close_all_positions(self._params.end_date)

        completed_at = datetime.now(UTC)

        # Calculate metrics
        metrics = BacktestMetrics()
        metrics.signals_processed = len(signals)
        metrics.signals_traded = signals_traded
        metrics.signals_skipped = signals_skipped
        metrics.calculate_from_trades(self._trades)

        # Calculate max drawdown
        metrics.max_drawdown_pct = self._calculate_max_drawdown()

        return BacktestResult(
            id=uuid4(),
            name=name,
            parameters=self._params.model_dump(mode="json"),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            trades=self._trades,
            metrics=metrics,
            equity_curve=self._equity_curve,
        )

    def _rescore_signal(self, signal: HistoricalSignal) -> Decimal:
        """Rescore a signal with backtest parameters."""
        weights = self._params.scoring_weights

        # Use stored score breakdown if available
        breakdown = signal.score_breakdown

        wallet_score = Decimal(str(breakdown.get("wallet", signal.wallet_score)))
        cluster_score = Decimal(str(breakdown.get("cluster", 0.5))) * signal.cluster_amplification
        token_score = Decimal(str(breakdown.get("token", 0.5)))
        context_score = Decimal(str(breakdown.get("context", 0.5)))

        new_score = (
            wallet_score * weights.wallet_weight
            + cluster_score * weights.cluster_weight
            + token_score * weights.token_weight
            + context_score * weights.context_weight
        )

        return min(max(new_score, Decimal("0")), Decimal("1"))

    def _can_open_position(self) -> bool:
        """Check if we can open a new position."""
        return len(self._open_positions) < self._params.max_concurrent_positions

    async def _open_trade(
        self,
        signal: HistoricalSignal,
        score: Decimal,
    ) -> BacktestTrade:
        """Open a simulated trade."""
        # Calculate position size
        position_size = self._params.base_position_sol
        if score >= self._params.high_conviction_threshold:
            position_size *= self._params.high_conviction_multiplier

        # Apply slippage to entry
        slippage = Decimal(str(self._params.slippage_bps)) / Decimal("10000")
        entry_price = signal.token_price_usd * (Decimal("1") + slippage)

        # Calculate tokens
        sol_price = Decimal("100")  # Simplified, should use historical
        usd_amount = position_size * sol_price
        tokens_bought = usd_amount / entry_price

        trade = BacktestTrade(
            id=uuid4(),
            signal_id=signal.id,
            token_address=signal.token_address,
            entry_time=signal.timestamp,
            entry_price=entry_price,
            position_size_sol=position_size,
            tokens_bought=tokens_bought,
        )

        self._trades.append(trade)
        self._open_positions[signal.token_address] = trade

        log.debug(
            "backtest_trade_opened",
            token=signal.token_address,
            entry_price=float(entry_price),
            score=float(score),
        )

        return trade

    async def _update_positions(self, current_time: datetime) -> None:
        """Check and update open positions for exits."""
        collector = await get_historical_collector()

        for token, trade in list(self._open_positions.items()):
            # Get current price
            prices = await collector.get_price_timeline(
                token_address=token,
                start_time=trade.entry_time,
                end_time=current_time,
            )

            if not prices:
                continue

            current_price = prices[-1].price_usd

            # Check stop-loss
            stop_price = trade.entry_price * (
                Decimal("1") - self._params.exit_strategy.stop_loss_pct
            )
            if current_price <= stop_price:
                await self._close_trade(trade, current_price, "stop_loss", current_time)
                continue

            # Check take-profit levels
            for level in self._params.exit_strategy.take_profit_levels:
                target_price = trade.entry_price * Decimal(str(level["multiplier"]))
                if current_price >= target_price:
                    # Simplified: close full position at first TP hit
                    await self._close_trade(
                        trade, current_price, "take_profit", current_time
                    )
                    break

    async def _close_trade(
        self,
        trade: BacktestTrade,
        exit_price: Decimal,
        exit_reason: str,
        exit_time: datetime,
    ) -> None:
        """Close a trade and calculate P&L."""
        # Apply slippage to exit
        slippage = Decimal(str(self._params.slippage_bps)) / Decimal("10000")
        actual_exit = exit_price * (Decimal("1") - slippage)

        # Calculate P&L
        entry_value = trade.entry_price * trade.tokens_bought
        exit_value = actual_exit * trade.tokens_bought
        pnl = exit_value - entry_value
        pnl_pct = (pnl / entry_value) * 100

        trade.exit_time = exit_time
        trade.exit_price = actual_exit
        trade.exit_reason = exit_reason
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pnl_pct
        trade.is_open = False

        # Update capital
        self._current_capital += pnl / (Decimal("100") * trade.position_size_sol)
        if self._current_capital > self._peak_capital:
            self._peak_capital = self._current_capital

        # Remove from open positions
        if trade.token_address in self._open_positions:
            del self._open_positions[trade.token_address]

        log.debug(
            "backtest_trade_closed",
            token=trade.token_address,
            pnl=float(pnl),
            reason=exit_reason,
        )

    async def _close_all_positions(self, end_time: datetime) -> None:
        """Close all remaining positions at backtest end."""
        collector = await get_historical_collector()

        for token, trade in list(self._open_positions.items()):
            prices = await collector.get_price_timeline(
                token_address=token,
                start_time=trade.entry_time,
                end_time=end_time,
            )

            if prices:
                exit_price = prices[-1].price_usd
            else:
                exit_price = trade.entry_price  # No change if no data

            await self._close_trade(trade, exit_price, "backtest_end", end_time)

    def _record_equity(self, timestamp: datetime) -> None:
        """Record equity curve point."""
        self._equity_curve.append({
            "timestamp": timestamp.isoformat(),
            "equity": float(self._current_capital),
            "open_positions": len(self._open_positions),
        })

    def _calculate_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown from equity curve."""
        if not self._equity_curve:
            return Decimal("0")

        peak = Decimal("0")
        max_dd = Decimal("0")

        for point in self._equity_curve:
            equity = Decimal(str(point["equity"]))
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak if peak > 0 else Decimal("0")
            if drawdown > max_dd:
                max_dd = drawdown

        return max_dd * 100  # Return as percentage
```

## Implementation Tasks

- [ ] Create BacktestParameters model
- [ ] Create BacktestResult and BacktestTrade models
- [ ] Implement BacktestEngine.run()
- [ ] Implement signal rescoring logic
- [ ] Implement trade simulation with historical prices
- [ ] Implement stop-loss and take-profit checks
- [ ] Calculate backtest metrics
- [ ] Generate equity curve
- [ ] Write unit tests with mock data

## Definition of Done

- [ ] Backtest engine replays signals correctly
- [ ] Scoring uses provided parameters
- [ ] Trade simulation uses historical prices
- [ ] Exit strategies are applied correctly
- [ ] Metrics are calculated accurately
- [ ] Equity curve is generated
- [ ] Tests cover all scenarios
