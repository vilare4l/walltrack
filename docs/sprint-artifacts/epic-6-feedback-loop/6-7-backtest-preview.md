# Story 6.7: Backtest Preview

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: Medium
- **FR**: FR47

## User Story

**As an** operator,
**I want** to preview how parameter changes would have performed historically,
**So that** I can make informed adjustments.

## Acceptance Criteria

### AC 1: Backtest Configuration
**Given** backtest panel in dashboard
**When** operator configures backtest
**Then** parameters can be adjusted:
- Scoring weights
- Threshold
- Position sizing
- Exit strategy

### AC 2: Backtest Execution
**Given** backtest parameters set
**When** backtest is run
**Then** historical signals are re-scored with new parameters
**And** simulated trades are calculated
**And** simulated PnL is computed

### AC 3: Results Display
**Given** backtest completes
**When** results are displayed
**Then** comparison shows:
- Actual performance vs simulated performance
- Number of trades difference
- Win rate difference
- PnL difference

### AC 4: Trade Comparison
**Given** backtest results
**When** operator reviews
**Then** trade-by-trade comparison is available
**And** "what would have changed" is highlighted

### AC 5: Apply Settings
**Given** backtest is satisfactory
**When** operator wants to apply
**Then** "Apply These Settings" button is available
**And** confirmation shows what will change
**And** settings are updated on confirm

### AC 6: Performance
**Given** large historical dataset
**When** backtest runs
**Then** progress indicator shows status
**And** backtest completes in reasonable time (< 30 seconds for 6 months)

## Technical Notes

- FR47: Run backtest preview on parameter changes
- Implement in `src/walltrack/core/feedback/backtester.py`
- UI in `src/walltrack/ui/components/backtest.py`
- Consider caching historical signals for performance

---

## Technical Specification

### 1. Pydantic Models

```python
# src/walltrack/core/feedback/models/backtest.py
"""Backtest preview models for parameter optimization."""

from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field, computed_field


class BacktestStatus(str, Enum):
    """Status of a backtest run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExitStrategy(str, Enum):
    """Exit strategy options for backtest."""
    TRAILING_STOP = "trailing_stop"
    FIXED_TARGETS = "fixed_targets"
    TIME_BASED = "time_based"
    HYBRID = "hybrid"


class ScoringWeights(BaseModel):
    """Scoring weights for backtest configuration."""
    wallet_score_weight: Decimal = Field(default=Decimal("0.3"), ge=0, le=1)
    token_metrics_weight: Decimal = Field(default=Decimal("0.25"), ge=0, le=1)
    liquidity_weight: Decimal = Field(default=Decimal("0.2"), ge=0, le=1)
    holder_distribution_weight: Decimal = Field(default=Decimal("0.15"), ge=0, le=1)
    momentum_weight: Decimal = Field(default=Decimal("0.1"), ge=0, le=1)

    @computed_field
    @property
    def total_weight(self) -> Decimal:
        """Sum of all weights."""
        return (
            self.wallet_score_weight +
            self.token_metrics_weight +
            self.liquidity_weight +
            self.holder_distribution_weight +
            self.momentum_weight
        )

    @computed_field
    @property
    def is_valid(self) -> bool:
        """Check if weights sum to 1.0."""
        return abs(self.total_weight - Decimal("1.0")) < Decimal("0.01")


class PositionSizingConfig(BaseModel):
    """Position sizing configuration."""
    base_position_sol: Decimal = Field(default=Decimal("0.1"), gt=0)
    max_position_sol: Decimal = Field(default=Decimal("0.5"), gt=0)
    scale_with_confidence: bool = Field(default=True)
    confidence_multiplier: Decimal = Field(default=Decimal("1.5"), ge=1)


class ExitStrategyConfig(BaseModel):
    """Exit strategy configuration."""
    strategy: ExitStrategy = Field(default=ExitStrategy.TRAILING_STOP)
    stop_loss_percent: Decimal = Field(default=Decimal("15"), ge=1, le=50)
    take_profit_percent: Decimal = Field(default=Decimal("50"), ge=5, le=500)
    trailing_stop_percent: Decimal = Field(default=Decimal("10"), ge=1, le=30)
    max_hold_minutes: int = Field(default=60, ge=5, le=1440)


class BacktestConfig(BaseModel):
    """Complete backtest configuration."""
    # Date range
    start_date: date
    end_date: date

    # Scoring parameters
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: Decimal = Field(default=Decimal("70"), ge=0, le=100)

    # Position sizing
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)

    # Exit strategy
    exit_strategy: ExitStrategyConfig = Field(default_factory=ExitStrategyConfig)

    # Simulation settings
    slippage_percent: Decimal = Field(default=Decimal("1.0"), ge=0, le=10)
    include_gas_costs: bool = Field(default=True)
    gas_cost_sol: Decimal = Field(default=Decimal("0.0001"))

    @computed_field
    @property
    def date_range_days(self) -> int:
        """Number of days in backtest range."""
        return (self.end_date - self.start_date).days + 1


class HistoricalSignal(BaseModel):
    """Historical signal for backtesting."""
    id: str
    timestamp: datetime
    token_address: str
    source_wallet: str

    # Original scoring
    original_score: Decimal
    original_factors: dict[str, Decimal] = Field(default_factory=dict)

    # What actually happened
    was_traded: bool
    actual_entry_price: Optional[Decimal] = None
    actual_exit_price: Optional[Decimal] = None
    actual_pnl_sol: Optional[Decimal] = None

    # Price data for simulation
    price_at_signal: Decimal
    price_history: list[tuple[datetime, Decimal]] = Field(default_factory=list)
    max_price_after: Optional[Decimal] = None
    min_price_after: Optional[Decimal] = None


class SimulatedTrade(BaseModel):
    """Simulated trade from backtest."""
    signal_id: str
    token_address: str
    source_wallet: str

    # Simulated parameters
    simulated_score: Decimal
    would_trade: bool
    entry_price: Decimal
    exit_price: Decimal
    exit_reason: str

    # Position sizing
    position_size_sol: Decimal

    # Results
    gross_pnl_sol: Decimal
    slippage_cost_sol: Decimal
    gas_cost_sol: Decimal

    @computed_field
    @property
    def net_pnl_sol(self) -> Decimal:
        """Net PnL after costs."""
        return self.gross_pnl_sol - self.slippage_cost_sol - self.gas_cost_sol

    @computed_field
    @property
    def pnl_percent(self) -> Decimal:
        """PnL as percentage of position."""
        if self.position_size_sol == 0:
            return Decimal("0")
        return (self.net_pnl_sol / self.position_size_sol * 100).quantize(Decimal("0.01"))

    @computed_field
    @property
    def is_win(self) -> bool:
        """Whether the trade was profitable."""
        return self.net_pnl_sol > 0


class PerformanceMetrics(BaseModel):
    """Performance metrics for a backtest or actual period."""
    total_trades: int = Field(default=0)
    winning_trades: int = Field(default=0)
    losing_trades: int = Field(default=0)

    total_pnl_sol: Decimal = Field(default=Decimal("0"))
    gross_profit_sol: Decimal = Field(default=Decimal("0"))
    gross_loss_sol: Decimal = Field(default=Decimal("0"))

    average_win_sol: Decimal = Field(default=Decimal("0"))
    average_loss_sol: Decimal = Field(default=Decimal("0"))

    max_drawdown_sol: Decimal = Field(default=Decimal("0"))
    max_consecutive_losses: int = Field(default=0)

    @computed_field
    @property
    def win_rate(self) -> Decimal:
        """Win rate percentage."""
        if self.total_trades == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.total_trades) * 100).quantize(Decimal("0.01"))

    @computed_field
    @property
    def profit_factor(self) -> Optional[Decimal]:
        """Profit factor (gross profit / gross loss)."""
        if self.gross_loss_sol == 0:
            return None
        return (self.gross_profit_sol / self.gross_loss_sol).quantize(Decimal("0.01"))

    @computed_field
    @property
    def expectancy(self) -> Decimal:
        """Expected value per trade."""
        if self.total_trades == 0:
            return Decimal("0")
        return (self.total_pnl_sol / Decimal(self.total_trades)).quantize(Decimal("0.0001"))


class MetricsComparison(BaseModel):
    """Comparison between actual and simulated metrics."""
    actual: PerformanceMetrics
    simulated: PerformanceMetrics

    @computed_field
    @property
    def pnl_difference_sol(self) -> Decimal:
        """Difference in PnL (simulated - actual)."""
        return self.simulated.total_pnl_sol - self.actual.total_pnl_sol

    @computed_field
    @property
    def pnl_improvement_percent(self) -> Optional[Decimal]:
        """Percentage improvement in PnL."""
        if self.actual.total_pnl_sol == 0:
            return None
        return ((self.pnl_difference_sol / abs(self.actual.total_pnl_sol)) * 100).quantize(Decimal("0.01"))

    @computed_field
    @property
    def trade_count_difference(self) -> int:
        """Difference in trade count."""
        return self.simulated.total_trades - self.actual.total_trades

    @computed_field
    @property
    def win_rate_difference(self) -> Decimal:
        """Difference in win rate (percentage points)."""
        return self.simulated.win_rate - self.actual.win_rate

    @computed_field
    @property
    def is_improvement(self) -> bool:
        """Whether simulated performance is better."""
        # Consider it an improvement if PnL is better and win rate isn't significantly worse
        pnl_better = self.pnl_difference_sol > Decimal("0.01")
        win_rate_acceptable = self.win_rate_difference > Decimal("-5")
        return pnl_better and win_rate_acceptable


class TradeComparison(BaseModel):
    """Comparison of a single trade between actual and simulated."""
    signal_id: str
    token_address: str
    timestamp: datetime

    # Actual
    actual_traded: bool
    actual_pnl_sol: Optional[Decimal] = None

    # Simulated
    simulated_traded: bool
    simulated_pnl_sol: Optional[Decimal] = None

    @computed_field
    @property
    def outcome_changed(self) -> bool:
        """Whether the trading decision changed."""
        return self.actual_traded != self.simulated_traded

    @computed_field
    @property
    def pnl_changed(self) -> bool:
        """Whether PnL changed significantly."""
        if self.actual_pnl_sol is None and self.simulated_pnl_sol is None:
            return False
        if self.actual_pnl_sol is None or self.simulated_pnl_sol is None:
            return True
        return abs(self.simulated_pnl_sol - self.actual_pnl_sol) > Decimal("0.001")

    @computed_field
    @property
    def change_description(self) -> str:
        """Human-readable description of change."""
        if not self.actual_traded and self.simulated_traded:
            return f"NEW TRADE: Would gain {self.simulated_pnl_sol:.4f} SOL"
        elif self.actual_traded and not self.simulated_traded:
            return f"SKIPPED: Would avoid {self.actual_pnl_sol:.4f} SOL loss" if self.actual_pnl_sol and self.actual_pnl_sol < 0 else "SKIPPED"
        elif self.pnl_changed:
            diff = (self.simulated_pnl_sol or Decimal("0")) - (self.actual_pnl_sol or Decimal("0"))
            return f"PnL changed by {diff:+.4f} SOL"
        return "No change"


class BacktestProgress(BaseModel):
    """Progress update during backtest execution."""
    backtest_id: str
    status: BacktestStatus
    signals_processed: int
    total_signals: int
    current_phase: str
    elapsed_seconds: int
    estimated_remaining_seconds: Optional[int] = None

    @computed_field
    @property
    def progress_percent(self) -> Decimal:
        """Progress as percentage."""
        if self.total_signals == 0:
            return Decimal("0")
        return (Decimal(self.signals_processed) / Decimal(self.total_signals) * 100).quantize(Decimal("0.1"))


class BacktestResult(BaseModel):
    """Complete result of a backtest run."""
    id: str
    config: BacktestConfig
    status: BacktestStatus

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None

    # Signal counts
    total_signals_analyzed: int = Field(default=0)
    signals_above_threshold: int = Field(default=0)

    # Metrics comparison
    metrics_comparison: Optional[MetricsComparison] = None

    # Simulated trades
    simulated_trades: list[SimulatedTrade] = Field(default_factory=list)

    # Trade comparisons
    trade_comparisons: list[TradeComparison] = Field(default_factory=list)

    # Error info
    error_message: Optional[str] = None

    @computed_field
    @property
    def is_successful(self) -> bool:
        """Whether backtest completed successfully."""
        return self.status == BacktestStatus.COMPLETED and self.error_message is None

    @computed_field
    @property
    def trades_changed_count(self) -> int:
        """Number of trades with changed outcomes."""
        return sum(1 for tc in self.trade_comparisons if tc.outcome_changed or tc.pnl_changed)


class ApplySettingsRequest(BaseModel):
    """Request to apply backtest settings to production."""
    backtest_id: str
    confirm_apply: bool = Field(default=False)
    apply_scoring_weights: bool = Field(default=True)
    apply_threshold: bool = Field(default=True)
    apply_position_sizing: bool = Field(default=True)
    apply_exit_strategy: bool = Field(default=True)


class ApplySettingsResult(BaseModel):
    """Result of applying backtest settings."""
    success: bool
    backtest_id: str
    applied_at: datetime
    changes_applied: list[str] = Field(default_factory=list)
    previous_values: dict = Field(default_factory=dict)
    error_message: Optional[str] = None
```

### 2. Service Layer

```python
# src/walltrack/core/feedback/services/backtester.py
"""Backtest preview service for parameter optimization."""

import structlog
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, AsyncGenerator
import uuid

from ..models.backtest import (
    BacktestConfig, BacktestStatus, BacktestResult, BacktestProgress,
    HistoricalSignal, SimulatedTrade, PerformanceMetrics, MetricsComparison,
    TradeComparison, ScoringWeights, ApplySettingsRequest, ApplySettingsResult
)
from ...db.supabase_client import get_supabase_client

logger = structlog.get_logger(__name__)


class BacktestService:
    """Service for running backtest previews."""

    def __init__(self):
        self._supabase = None
        self._running_backtests: dict[str, BacktestProgress] = {}
        self._signal_cache: dict[str, list[HistoricalSignal]] = {}
        self._cache_ttl_minutes = 30

    async def _get_supabase(self):
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def run_backtest(
        self,
        config: BacktestConfig,
        progress_callback: Optional[callable] = None
    ) -> BacktestResult:
        """
        Run a backtest with the given configuration.

        Target completion time: < 30 seconds for 6 months of data.
        """
        backtest_id = str(uuid.uuid4())
        started_at = datetime.utcnow()

        logger.info(
            "backtest_started",
            backtest_id=backtest_id,
            start_date=str(config.start_date),
            end_date=str(config.end_date)
        )

        # Initialize progress
        progress = BacktestProgress(
            backtest_id=backtest_id,
            status=BacktestStatus.RUNNING,
            signals_processed=0,
            total_signals=0,
            current_phase="Loading signals",
            elapsed_seconds=0
        )
        self._running_backtests[backtest_id] = progress

        try:
            # Phase 1: Load historical signals
            signals = await self._load_historical_signals(config)
            progress.total_signals = len(signals)
            progress.current_phase = "Rescoring signals"

            if progress_callback:
                await progress_callback(progress)

            # Phase 2: Rescore signals with new weights
            rescored_signals = []
            for i, signal in enumerate(signals):
                rescored = await self._rescore_signal(signal, config.scoring_weights)
                rescored_signals.append(rescored)

                progress.signals_processed = i + 1
                progress.elapsed_seconds = int((datetime.utcnow() - started_at).total_seconds())

                # Estimate remaining time
                if i > 0:
                    avg_time_per_signal = progress.elapsed_seconds / (i + 1)
                    remaining_signals = len(signals) - i - 1
                    progress.estimated_remaining_seconds = int(avg_time_per_signal * remaining_signals)

                # Callback every 10 signals to reduce overhead
                if progress_callback and i % 10 == 0:
                    await progress_callback(progress)

            # Phase 3: Simulate trades
            progress.current_phase = "Simulating trades"
            if progress_callback:
                await progress_callback(progress)

            simulated_trades = await self._simulate_trades(rescored_signals, config)

            # Phase 4: Calculate metrics
            progress.current_phase = "Calculating metrics"
            if progress_callback:
                await progress_callback(progress)

            actual_metrics = await self._calculate_actual_metrics(config)
            simulated_metrics = self._calculate_simulated_metrics(simulated_trades)

            metrics_comparison = MetricsComparison(
                actual=actual_metrics,
                simulated=simulated_metrics
            )

            # Phase 5: Build trade comparisons
            trade_comparisons = await self._build_trade_comparisons(
                signals, simulated_trades
            )

            # Complete
            completed_at = datetime.utcnow()
            duration_seconds = int((completed_at - started_at).total_seconds())

            result = BacktestResult(
                id=backtest_id,
                config=config,
                status=BacktestStatus.COMPLETED,
                started_at=started_at,
                completed_at=completed_at,
                duration_seconds=duration_seconds,
                total_signals_analyzed=len(signals),
                signals_above_threshold=sum(1 for s in rescored_signals if s.original_score >= config.score_threshold),
                metrics_comparison=metrics_comparison,
                simulated_trades=simulated_trades,
                trade_comparisons=trade_comparisons
            )

            # Store result
            await self._store_backtest_result(result)

            logger.info(
                "backtest_completed",
                backtest_id=backtest_id,
                duration_seconds=duration_seconds,
                signals_analyzed=len(signals),
                simulated_trades=len(simulated_trades)
            )

            return result

        except Exception as e:
            logger.error("backtest_failed", backtest_id=backtest_id, error=str(e))

            return BacktestResult(
                id=backtest_id,
                config=config,
                status=BacktestStatus.FAILED,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                error_message=str(e)
            )

        finally:
            if backtest_id in self._running_backtests:
                del self._running_backtests[backtest_id]

    async def _load_historical_signals(
        self,
        config: BacktestConfig
    ) -> list[HistoricalSignal]:
        """Load historical signals for the date range."""
        # Check cache first
        cache_key = f"{config.start_date}_{config.end_date}"
        if cache_key in self._signal_cache:
            logger.debug("using_cached_signals", cache_key=cache_key)
            return self._signal_cache[cache_key]

        supabase = await self._get_supabase()

        # Load signals
        response = await supabase.table("signals").select(
            "id, timestamp, token_address, source_wallet, score, score_factors"
        ).gte(
            "timestamp", config.start_date.isoformat()
        ).lte(
            "timestamp", f"{config.end_date}T23:59:59"
        ).execute()

        signal_data = response.data or []

        # Load corresponding trades
        trades_response = await supabase.table("trade_outcomes").select(
            "signal_id, entry_price, exit_price, realized_pnl_sol"
        ).gte(
            "entry_timestamp", config.start_date.isoformat()
        ).lte(
            "entry_timestamp", f"{config.end_date}T23:59:59"
        ).execute()

        trades_by_signal = {t["signal_id"]: t for t in (trades_response.data or [])}

        # Load price history for each token (batch)
        token_addresses = list(set(s["token_address"] for s in signal_data))
        price_histories = await self._load_price_histories(
            token_addresses, config.start_date, config.end_date
        )

        # Build HistoricalSignal objects
        signals = []
        for s in signal_data:
            trade = trades_by_signal.get(s["id"])
            price_history = price_histories.get(s["token_address"], [])

            # Find price at signal time and max/min after
            signal_time = datetime.fromisoformat(s["timestamp"].replace("Z", "+00:00"))
            prices_after = [
                (t, p) for t, p in price_history
                if t >= signal_time
            ]

            price_at_signal = Decimal("0")
            max_price_after = None
            min_price_after = None

            if prices_after:
                price_at_signal = prices_after[0][1]
                max_price_after = max(p for _, p in prices_after)
                min_price_after = min(p for _, p in prices_after)

            signal = HistoricalSignal(
                id=s["id"],
                timestamp=signal_time,
                token_address=s["token_address"],
                source_wallet=s["source_wallet"],
                original_score=Decimal(str(s.get("score", 0))),
                original_factors=s.get("score_factors", {}),
                was_traded=trade is not None,
                actual_entry_price=Decimal(str(trade["entry_price"])) if trade else None,
                actual_exit_price=Decimal(str(trade["exit_price"])) if trade else None,
                actual_pnl_sol=Decimal(str(trade["realized_pnl_sol"])) if trade else None,
                price_at_signal=price_at_signal,
                price_history=prices_after[:100],  # Limit for memory
                max_price_after=max_price_after,
                min_price_after=min_price_after
            )
            signals.append(signal)

        # Cache results
        self._signal_cache[cache_key] = signals

        return signals

    async def _load_price_histories(
        self,
        token_addresses: list[str],
        start_date,
        end_date
    ) -> dict[str, list[tuple[datetime, Decimal]]]:
        """Load price histories for tokens."""
        supabase = await self._get_supabase()

        # Batch load price data
        response = await supabase.table("token_prices").select(
            "token_address, timestamp, price"
        ).in_("token_address", token_addresses).gte(
            "timestamp", start_date.isoformat()
        ).lte(
            "timestamp", f"{end_date}T23:59:59"
        ).order("timestamp").execute()

        # Group by token
        histories: dict[str, list[tuple[datetime, Decimal]]] = {}
        for row in (response.data or []):
            addr = row["token_address"]
            if addr not in histories:
                histories[addr] = []
            histories[addr].append((
                datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00")),
                Decimal(str(row["price"]))
            ))

        return histories

    async def _rescore_signal(
        self,
        signal: HistoricalSignal,
        weights: ScoringWeights
    ) -> HistoricalSignal:
        """Rescore a signal with new weights."""
        factors = signal.original_factors

        # Calculate new score with new weights
        new_score = (
            Decimal(str(factors.get("wallet_score", 0))) * weights.wallet_score_weight +
            Decimal(str(factors.get("token_metrics", 0))) * weights.token_metrics_weight +
            Decimal(str(factors.get("liquidity", 0))) * weights.liquidity_weight +
            Decimal(str(factors.get("holder_distribution", 0))) * weights.holder_distribution_weight +
            Decimal(str(factors.get("momentum", 0))) * weights.momentum_weight
        ) * 100  # Scale to 0-100

        # Create copy with new score
        return HistoricalSignal(
            id=signal.id,
            timestamp=signal.timestamp,
            token_address=signal.token_address,
            source_wallet=signal.source_wallet,
            original_score=new_score.quantize(Decimal("0.01")),
            original_factors=signal.original_factors,
            was_traded=signal.was_traded,
            actual_entry_price=signal.actual_entry_price,
            actual_exit_price=signal.actual_exit_price,
            actual_pnl_sol=signal.actual_pnl_sol,
            price_at_signal=signal.price_at_signal,
            price_history=signal.price_history,
            max_price_after=signal.max_price_after,
            min_price_after=signal.min_price_after
        )

    async def _simulate_trades(
        self,
        signals: list[HistoricalSignal],
        config: BacktestConfig
    ) -> list[SimulatedTrade]:
        """Simulate trades based on rescored signals."""
        simulated_trades = []

        for signal in signals:
            # Would we trade this signal?
            would_trade = signal.original_score >= config.score_threshold

            if not would_trade:
                continue

            if signal.price_at_signal == 0:
                continue

            # Calculate position size
            position_size = config.position_sizing.base_position_sol
            if config.position_sizing.scale_with_confidence:
                confidence_factor = signal.original_score / Decimal("100")
                position_size = min(
                    position_size * confidence_factor * config.position_sizing.confidence_multiplier,
                    config.position_sizing.max_position_sol
                )

            # Simulate exit
            entry_price = signal.price_at_signal
            exit_price, exit_reason = self._simulate_exit(signal, config)

            # Calculate PnL
            if entry_price > 0:
                price_change_percent = ((exit_price - entry_price) / entry_price) * 100
                gross_pnl = position_size * (price_change_percent / 100)
            else:
                gross_pnl = Decimal("0")

            # Apply costs
            slippage_cost = position_size * (config.slippage_percent / 100)
            gas_cost = config.gas_cost_sol if config.include_gas_costs else Decimal("0")

            trade = SimulatedTrade(
                signal_id=signal.id,
                token_address=signal.token_address,
                source_wallet=signal.source_wallet,
                simulated_score=signal.original_score,
                would_trade=True,
                entry_price=entry_price,
                exit_price=exit_price,
                exit_reason=exit_reason,
                position_size_sol=position_size.quantize(Decimal("0.0001")),
                gross_pnl_sol=gross_pnl.quantize(Decimal("0.0001")),
                slippage_cost_sol=slippage_cost.quantize(Decimal("0.0001")),
                gas_cost_sol=gas_cost
            )
            simulated_trades.append(trade)

        return simulated_trades

    def _simulate_exit(
        self,
        signal: HistoricalSignal,
        config: BacktestConfig
    ) -> tuple[Decimal, str]:
        """Simulate exit based on price history and exit strategy."""
        entry_price = signal.price_at_signal
        exit_config = config.exit_strategy

        if not signal.price_history or entry_price == 0:
            return entry_price, "no_data"

        # Calculate target prices
        stop_loss_price = entry_price * (1 - exit_config.stop_loss_percent / 100)
        take_profit_price = entry_price * (1 + exit_config.take_profit_percent / 100)

        # Track trailing stop
        peak_price = entry_price
        trailing_stop_price = entry_price * (1 - exit_config.trailing_stop_percent / 100)

        # Simulate through price history
        for timestamp, price in signal.price_history:
            # Check time limit
            hold_duration = (timestamp - signal.timestamp).total_seconds() / 60
            if hold_duration >= exit_config.max_hold_minutes:
                return price, "time_limit"

            # Update trailing stop
            if price > peak_price:
                peak_price = price
                trailing_stop_price = peak_price * (1 - exit_config.trailing_stop_percent / 100)

            # Check exits
            if price <= stop_loss_price:
                return stop_loss_price, "stop_loss"

            if price >= take_profit_price:
                return take_profit_price, "take_profit"

            if price <= trailing_stop_price and peak_price > entry_price:
                return trailing_stop_price, "trailing_stop"

        # If we get here, use last known price
        if signal.price_history:
            return signal.price_history[-1][1], "end_of_data"

        return entry_price, "no_exit"

    async def _calculate_actual_metrics(
        self,
        config: BacktestConfig
    ) -> PerformanceMetrics:
        """Calculate actual metrics for the date range."""
        supabase = await self._get_supabase()

        response = await supabase.table("trade_outcomes").select("*").gte(
            "exit_timestamp", config.start_date.isoformat()
        ).lte(
            "exit_timestamp", f"{config.end_date}T23:59:59"
        ).execute()

        trades = response.data or []

        if not trades:
            return PerformanceMetrics()

        winning = [t for t in trades if Decimal(str(t.get("realized_pnl_sol", 0))) > 0]
        losing = [t for t in trades if Decimal(str(t.get("realized_pnl_sol", 0))) <= 0]

        total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in trades)
        gross_profit = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in winning)
        gross_loss = sum(abs(Decimal(str(t.get("realized_pnl_sol", 0)))) for t in losing)

        avg_win = gross_profit / len(winning) if winning else Decimal("0")
        avg_loss = gross_loss / len(losing) if losing else Decimal("0")

        # Calculate max drawdown
        max_drawdown = self._calculate_max_drawdown(trades)

        # Calculate max consecutive losses
        max_consecutive = self._calculate_max_consecutive_losses(trades)

        return PerformanceMetrics(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_sol=total_pnl.quantize(Decimal("0.0001")),
            gross_profit_sol=gross_profit.quantize(Decimal("0.0001")),
            gross_loss_sol=gross_loss.quantize(Decimal("0.0001")),
            average_win_sol=avg_win.quantize(Decimal("0.0001")),
            average_loss_sol=avg_loss.quantize(Decimal("0.0001")),
            max_drawdown_sol=max_drawdown.quantize(Decimal("0.0001")),
            max_consecutive_losses=max_consecutive
        )

    def _calculate_simulated_metrics(
        self,
        trades: list[SimulatedTrade]
    ) -> PerformanceMetrics:
        """Calculate metrics from simulated trades."""
        if not trades:
            return PerformanceMetrics()

        winning = [t for t in trades if t.is_win]
        losing = [t for t in trades if not t.is_win]

        total_pnl = sum(t.net_pnl_sol for t in trades)
        gross_profit = sum(t.net_pnl_sol for t in winning)
        gross_loss = sum(abs(t.net_pnl_sol) for t in losing)

        avg_win = gross_profit / len(winning) if winning else Decimal("0")
        avg_loss = gross_loss / len(losing) if losing else Decimal("0")

        # Calculate max drawdown from simulated trades
        max_drawdown = Decimal("0")
        peak = Decimal("0")
        cumulative = Decimal("0")

        for trade in trades:
            cumulative += trade.net_pnl_sol
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        # Max consecutive losses
        max_consecutive = 0
        current_consecutive = 0
        for trade in trades:
            if not trade.is_win:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return PerformanceMetrics(
            total_trades=len(trades),
            winning_trades=len(winning),
            losing_trades=len(losing),
            total_pnl_sol=total_pnl.quantize(Decimal("0.0001")),
            gross_profit_sol=gross_profit.quantize(Decimal("0.0001")),
            gross_loss_sol=gross_loss.quantize(Decimal("0.0001")),
            average_win_sol=avg_win.quantize(Decimal("0.0001")),
            average_loss_sol=avg_loss.quantize(Decimal("0.0001")),
            max_drawdown_sol=max_drawdown.quantize(Decimal("0.0001")),
            max_consecutive_losses=max_consecutive
        )

    def _calculate_max_drawdown(self, trades: list[dict]) -> Decimal:
        """Calculate maximum drawdown from trade list."""
        max_drawdown = Decimal("0")
        peak = Decimal("0")
        cumulative = Decimal("0")

        for trade in sorted(trades, key=lambda t: t.get("exit_timestamp", "")):
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            cumulative += pnl
            if cumulative > peak:
                peak = cumulative
            drawdown = peak - cumulative
            if drawdown > max_drawdown:
                max_drawdown = drawdown

        return max_drawdown

    def _calculate_max_consecutive_losses(self, trades: list[dict]) -> int:
        """Calculate maximum consecutive losses."""
        max_consecutive = 0
        current_consecutive = 0

        for trade in sorted(trades, key=lambda t: t.get("exit_timestamp", "")):
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            if pnl <= 0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return max_consecutive

    async def _build_trade_comparisons(
        self,
        signals: list[HistoricalSignal],
        simulated_trades: list[SimulatedTrade]
    ) -> list[TradeComparison]:
        """Build trade-by-trade comparisons."""
        simulated_by_signal = {t.signal_id: t for t in simulated_trades}

        comparisons = []
        for signal in signals:
            simulated = simulated_by_signal.get(signal.id)

            comparison = TradeComparison(
                signal_id=signal.id,
                token_address=signal.token_address,
                timestamp=signal.timestamp,
                actual_traded=signal.was_traded,
                actual_pnl_sol=signal.actual_pnl_sol,
                simulated_traded=simulated is not None,
                simulated_pnl_sol=simulated.net_pnl_sol if simulated else None
            )
            comparisons.append(comparison)

        # Sort by change impact (changed outcomes first)
        comparisons.sort(key=lambda c: (not c.outcome_changed, not c.pnl_changed))

        return comparisons

    async def _store_backtest_result(self, result: BacktestResult):
        """Store backtest result in database."""
        supabase = await self._get_supabase()

        await supabase.table("backtest_results").insert({
            "id": result.id,
            "config": result.config.model_dump(mode="json"),
            "status": result.status.value,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "duration_seconds": result.duration_seconds,
            "total_signals_analyzed": result.total_signals_analyzed,
            "metrics_comparison": result.metrics_comparison.model_dump(mode="json") if result.metrics_comparison else None,
            "trade_comparisons_count": len(result.trade_comparisons),
            "error_message": result.error_message
        }).execute()

    async def apply_settings(
        self,
        request: ApplySettingsRequest
    ) -> ApplySettingsResult:
        """Apply backtest settings to production configuration."""
        if not request.confirm_apply:
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.utcnow(),
                error_message="confirm_apply must be True to apply settings"
            )

        supabase = await self._get_supabase()

        # Load backtest result
        response = await supabase.table("backtest_results").select("*").eq(
            "id", request.backtest_id
        ).single().execute()

        if not response.data:
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.utcnow(),
                error_message="Backtest not found"
            )

        config_data = response.data["config"]
        config = BacktestConfig(**config_data)

        changes_applied = []
        previous_values = {}

        try:
            # Apply scoring weights
            if request.apply_scoring_weights:
                prev = await self._get_current_weights()
                await self._apply_scoring_weights(config.scoring_weights)
                changes_applied.append("scoring_weights")
                previous_values["scoring_weights"] = prev

            # Apply threshold
            if request.apply_threshold:
                prev = await self._get_current_threshold()
                await self._apply_threshold(config.score_threshold)
                changes_applied.append("score_threshold")
                previous_values["score_threshold"] = prev

            # Apply position sizing
            if request.apply_position_sizing:
                prev = await self._get_current_position_sizing()
                await self._apply_position_sizing(config.position_sizing)
                changes_applied.append("position_sizing")
                previous_values["position_sizing"] = prev

            # Apply exit strategy
            if request.apply_exit_strategy:
                prev = await self._get_current_exit_strategy()
                await self._apply_exit_strategy(config.exit_strategy)
                changes_applied.append("exit_strategy")
                previous_values["exit_strategy"] = prev

            logger.info(
                "backtest_settings_applied",
                backtest_id=request.backtest_id,
                changes=changes_applied
            )

            return ApplySettingsResult(
                success=True,
                backtest_id=request.backtest_id,
                applied_at=datetime.utcnow(),
                changes_applied=changes_applied,
                previous_values=previous_values
            )

        except Exception as e:
            logger.error("failed_to_apply_settings", error=str(e))
            return ApplySettingsResult(
                success=False,
                backtest_id=request.backtest_id,
                applied_at=datetime.utcnow(),
                error_message=str(e)
            )

    async def _get_current_weights(self) -> dict:
        """Get current scoring weights."""
        supabase = await self._get_supabase()
        response = await supabase.table("scoring_weights").select("*").eq(
            "is_active", True
        ).single().execute()
        return response.data if response.data else {}

    async def _apply_scoring_weights(self, weights: ScoringWeights):
        """Apply new scoring weights."""
        supabase = await self._get_supabase()

        # Deactivate current weights
        await supabase.table("scoring_weights").update(
            {"is_active": False}
        ).eq("is_active", True).execute()

        # Insert new weights
        await supabase.table("scoring_weights").insert({
            "wallet_score_weight": float(weights.wallet_score_weight),
            "token_metrics_weight": float(weights.token_metrics_weight),
            "liquidity_weight": float(weights.liquidity_weight),
            "holder_distribution_weight": float(weights.holder_distribution_weight),
            "momentum_weight": float(weights.momentum_weight),
            "is_active": True,
            "created_at": datetime.utcnow().isoformat()
        }).execute()

    async def _get_current_threshold(self) -> Decimal:
        """Get current score threshold."""
        supabase = await self._get_supabase()
        response = await supabase.table("system_config").select("value").eq(
            "key", "score_threshold"
        ).single().execute()
        return Decimal(str(response.data["value"])) if response.data else Decimal("70")

    async def _apply_threshold(self, threshold: Decimal):
        """Apply new score threshold."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert({
            "key": "score_threshold",
            "value": float(threshold),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def _get_current_position_sizing(self) -> dict:
        """Get current position sizing config."""
        supabase = await self._get_supabase()
        response = await supabase.table("system_config").select("value").eq(
            "key", "position_sizing"
        ).single().execute()
        return response.data["value"] if response.data else {}

    async def _apply_position_sizing(self, config):
        """Apply new position sizing config."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert({
            "key": "position_sizing",
            "value": config.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def _get_current_exit_strategy(self) -> dict:
        """Get current exit strategy config."""
        supabase = await self._get_supabase()
        response = await supabase.table("system_config").select("value").eq(
            "key", "exit_strategy"
        ).single().execute()
        return response.data["value"] if response.data else {}

    async def _apply_exit_strategy(self, config):
        """Apply new exit strategy config."""
        supabase = await self._get_supabase()
        await supabase.table("system_config").upsert({
            "key": "exit_strategy",
            "value": config.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    def get_progress(self, backtest_id: str) -> Optional[BacktestProgress]:
        """Get progress of a running backtest."""
        return self._running_backtests.get(backtest_id)

    def clear_cache(self):
        """Clear the signal cache."""
        self._signal_cache.clear()
        logger.info("backtest_signal_cache_cleared")


# Singleton instance
_backtest_service: Optional[BacktestService] = None


async def get_backtest_service() -> BacktestService:
    """Get the singleton backtest service instance."""
    global _backtest_service
    if _backtest_service is None:
        _backtest_service = BacktestService()
    return _backtest_service
```

### 3. Database Schema (SQL)

```sql
-- Backtest results storage
CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY,
    config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    total_signals_analyzed INTEGER DEFAULT 0,
    signals_above_threshold INTEGER DEFAULT 0,
    metrics_comparison JSONB,
    trade_comparisons_count INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for listing backtests
CREATE INDEX IF NOT EXISTS idx_backtest_results_created
ON backtest_results (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_backtest_results_status
ON backtest_results (status);

-- Signal cache for performance
CREATE TABLE IF NOT EXISTS signal_cache (
    cache_key VARCHAR(100) PRIMARY KEY,
    signals JSONB NOT NULL,
    cached_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_signal_cache_expires
ON signal_cache (expires_at);

-- Price history for backtesting (if not already exists)
CREATE TABLE IF NOT EXISTS token_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_address VARCHAR(44) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price NUMERIC(20, 10) NOT NULL,
    volume_24h NUMERIC(20, 4),
    UNIQUE(token_address, timestamp)
);

CREATE INDEX IF NOT EXISTS idx_token_prices_lookup
ON token_prices (token_address, timestamp);

-- Applied settings history
CREATE TABLE IF NOT EXISTS applied_settings_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID REFERENCES backtest_results(id),
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    changes_applied TEXT[] NOT NULL,
    previous_values JSONB NOT NULL,
    applied_by VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX IF NOT EXISTS idx_applied_settings_backtest
ON applied_settings_history (backtest_id);

-- Function to clean up expired cache
CREATE OR REPLACE FUNCTION cleanup_expired_signal_cache()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM signal_cache WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;
```

### 4. API Routes

```python
# src/walltrack/api/routes/backtest.py
"""Backtest preview API routes."""

from datetime import date, timedelta
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional
import asyncio
import json

from ...core.feedback.models.backtest import (
    BacktestConfig, BacktestResult, BacktestProgress, BacktestStatus,
    ScoringWeights, PositionSizingConfig, ExitStrategyConfig,
    ApplySettingsRequest, ApplySettingsResult
)
from ...core.feedback.services.backtester import (
    get_backtest_service, BacktestService
)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.post("/run", response_model=BacktestResult)
async def run_backtest(
    config: BacktestConfig,
    service: BacktestService = Depends(get_backtest_service)
) -> BacktestResult:
    """
    Run a backtest with the given configuration.

    Target completion time: < 30 seconds for 6 months of data.
    """
    # Validate date range
    if config.end_date < config.start_date:
        raise HTTPException(status_code=400, detail="end_date must be >= start_date")

    if config.date_range_days > 180:
        raise HTTPException(
            status_code=400,
            detail="Date range cannot exceed 180 days for performance reasons"
        )

    # Validate weights
    if not config.scoring_weights.is_valid:
        raise HTTPException(
            status_code=400,
            detail=f"Scoring weights must sum to 1.0, got {config.scoring_weights.total_weight}"
        )

    return await service.run_backtest(config)


@router.post("/run/stream")
async def run_backtest_stream(
    config: BacktestConfig,
    service: BacktestService = Depends(get_backtest_service)
) -> StreamingResponse:
    """
    Run a backtest and stream progress updates.

    Returns Server-Sent Events with progress and final result.
    """
    async def generate():
        result_holder = {"result": None}

        async def progress_callback(progress: BacktestProgress):
            data = progress.model_dump_json()
            yield f"data: {data}\n\n"

        # Run backtest in background
        async def run():
            result_holder["result"] = await service.run_backtest(
                config, progress_callback
            )

        task = asyncio.create_task(run())

        # Stream progress
        while not task.done():
            await asyncio.sleep(0.5)

        await task

        # Send final result
        if result_holder["result"]:
            final_data = result_holder["result"].model_dump_json()
            yield f"event: complete\ndata: {final_data}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream"
    )


@router.get("/progress/{backtest_id}", response_model=Optional[BacktestProgress])
async def get_backtest_progress(
    backtest_id: str,
    service: BacktestService = Depends(get_backtest_service)
) -> Optional[BacktestProgress]:
    """Get progress of a running backtest."""
    progress = service.get_progress(backtest_id)
    if not progress:
        raise HTTPException(status_code=404, detail="Backtest not found or completed")
    return progress


@router.get("/result/{backtest_id}", response_model=BacktestResult)
async def get_backtest_result(
    backtest_id: str,
    service: BacktestService = Depends(get_backtest_service)
) -> BacktestResult:
    """Get result of a completed backtest."""
    from ...core.db.supabase_client import get_supabase_client

    supabase = await get_supabase_client()
    response = await supabase.table("backtest_results").select("*").eq(
        "id", backtest_id
    ).single().execute()

    if not response.data:
        raise HTTPException(status_code=404, detail="Backtest result not found")

    return BacktestResult(
        id=response.data["id"],
        config=BacktestConfig(**response.data["config"]),
        status=BacktestStatus(response.data["status"]),
        started_at=response.data["started_at"],
        completed_at=response.data.get("completed_at"),
        duration_seconds=response.data.get("duration_seconds"),
        total_signals_analyzed=response.data.get("total_signals_analyzed", 0),
        error_message=response.data.get("error_message")
    )


@router.get("/history")
async def list_backtest_history(
    limit: int = 20,
    service: BacktestService = Depends(get_backtest_service)
) -> list[dict]:
    """List recent backtest results."""
    from ...core.db.supabase_client import get_supabase_client

    supabase = await get_supabase_client()
    response = await supabase.table("backtest_results").select(
        "id, status, started_at, completed_at, duration_seconds, total_signals_analyzed, metrics_comparison"
    ).order("created_at", desc=True).limit(limit).execute()

    return response.data or []


@router.post("/apply", response_model=ApplySettingsResult)
async def apply_backtest_settings(
    request: ApplySettingsRequest,
    service: BacktestService = Depends(get_backtest_service)
) -> ApplySettingsResult:
    """
    Apply settings from a successful backtest to production.

    Requires confirm_apply=True for safety.
    """
    return await service.apply_settings(request)


@router.get("/defaults", response_model=BacktestConfig)
async def get_default_config() -> BacktestConfig:
    """Get default backtest configuration."""
    return BacktestConfig(
        start_date=date.today() - timedelta(days=30),
        end_date=date.today()
    )


@router.post("/cache/clear")
async def clear_cache(
    service: BacktestService = Depends(get_backtest_service)
) -> dict:
    """Clear the signal cache for fresh data."""
    service.clear_cache()
    return {"status": "cache_cleared"}
```

### 5. Gradio UI Component

```python
# src/walltrack/ui/components/backtest.py
"""Backtest preview Gradio component."""

import gradio as gr
import plotly.graph_objects as go
from datetime import date, timedelta
from decimal import Decimal
import asyncio
from typing import Optional

from ...core.feedback.services.backtester import get_backtest_service
from ...core.feedback.models.backtest import (
    BacktestConfig, BacktestResult, BacktestProgress, BacktestStatus,
    ScoringWeights, PositionSizingConfig, ExitStrategyConfig, ExitStrategy,
    ApplySettingsRequest, MetricsComparison
)


def create_metrics_comparison_display(comparison: MetricsComparison) -> str:
    """Create HTML for metrics comparison."""
    actual = comparison.actual
    simulated = comparison.simulated

    pnl_color = "green" if comparison.pnl_difference_sol >= 0 else "red"
    wr_color = "green" if comparison.win_rate_difference >= 0 else "red"

    improvement_text = "IMPROVEMENT" if comparison.is_improvement else "NO IMPROVEMENT"
    improvement_color = "green" if comparison.is_improvement else "orange"

    return f"""
    <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 16px; padding: 16px;">
        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <h4 style="color: #888; margin: 0 0 12px 0;">Actual Performance</h4>
            <div style="color: white;">Total PnL: <b>{float(actual.total_pnl_sol):.4f}</b> SOL</div>
            <div style="color: white;">Win Rate: <b>{float(actual.win_rate):.1f}%</b></div>
            <div style="color: white;">Trades: <b>{actual.total_trades}</b></div>
            <div style="color: white;">Profit Factor: <b>{float(actual.profit_factor or 0):.2f}</b></div>
        </div>

        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px;">
            <h4 style="color: #888; margin: 0 0 12px 0;">Simulated Performance</h4>
            <div style="color: white;">Total PnL: <b>{float(simulated.total_pnl_sol):.4f}</b> SOL</div>
            <div style="color: white;">Win Rate: <b>{float(simulated.win_rate):.1f}%</b></div>
            <div style="color: white;">Trades: <b>{simulated.total_trades}</b></div>
            <div style="color: white;">Profit Factor: <b>{float(simulated.profit_factor or 0):.2f}</b></div>
        </div>

        <div style="background: #1a1a2e; padding: 16px; border-radius: 8px; border: 2px solid {improvement_color};">
            <h4 style="color: {improvement_color}; margin: 0 0 12px 0;">{improvement_text}</h4>
            <div style="color: {pnl_color};">PnL Change: <b>{float(comparison.pnl_difference_sol):+.4f}</b> SOL</div>
            <div style="color: {wr_color};">Win Rate: <b>{float(comparison.win_rate_difference):+.1f}</b>pp</div>
            <div style="color: white;">Trade Count: <b>{comparison.trade_count_difference:+d}</b></div>
        </div>
    </div>
    """


def create_trade_comparison_table(result: BacktestResult) -> list[list]:
    """Create table data for trade comparisons."""
    rows = []
    for tc in result.trade_comparisons[:50]:  # Limit to 50 for display
        rows.append([
            tc.timestamp.strftime("%Y-%m-%d %H:%M"),
            tc.token_address[:8] + "...",
            "Yes" if tc.actual_traded else "No",
            f"{float(tc.actual_pnl_sol or 0):.4f}" if tc.actual_pnl_sol else "-",
            "Yes" if tc.simulated_traded else "No",
            f"{float(tc.simulated_pnl_sol or 0):.4f}" if tc.simulated_pnl_sol else "-",
            tc.change_description
        ])
    return rows


def create_pnl_comparison_chart(result: BacktestResult) -> go.Figure:
    """Create chart comparing actual vs simulated PnL."""
    fig = go.Figure()

    # Build cumulative PnL series
    actual_cumulative = []
    simulated_cumulative = []
    timestamps = []

    actual_total = Decimal("0")
    simulated_total = Decimal("0")

    for tc in sorted(result.trade_comparisons, key=lambda x: x.timestamp):
        timestamps.append(tc.timestamp)

        if tc.actual_pnl_sol:
            actual_total += tc.actual_pnl_sol
        actual_cumulative.append(float(actual_total))

        if tc.simulated_pnl_sol:
            simulated_total += tc.simulated_pnl_sol
        simulated_cumulative.append(float(simulated_total))

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=actual_cumulative,
        mode='lines',
        name='Actual',
        line=dict(color='#60a5fa', width=2)
    ))

    fig.add_trace(go.Scatter(
        x=timestamps,
        y=simulated_cumulative,
        mode='lines',
        name='Simulated',
        line=dict(color='#4ade80', width=2, dash='dash')
    ))

    fig.update_layout(
        title='Cumulative PnL: Actual vs Simulated',
        template='plotly_dark',
        height=400,
        yaxis=dict(title='Cumulative PnL (SOL)'),
        xaxis=dict(title='Date'),
        legend=dict(x=0, y=1.1, orientation='h'),
        hovermode='x unified'
    )

    return fig


def create_backtest_panel() -> gr.Blocks:
    """Create the complete backtest preview panel."""

    with gr.Blocks() as panel:
        gr.Markdown("## 🔬 Backtest Preview")
        gr.Markdown("Test how parameter changes would have performed historically before applying them.")

        # State
        backtest_result = gr.State(None)

        with gr.Tabs():
            # Configuration Tab
            with gr.Tab("Configuration"):
                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Date Range")
                        start_date = gr.Textbox(
                            label="Start Date",
                            value=(date.today() - timedelta(days=30)).isoformat()
                        )
                        end_date = gr.Textbox(
                            label="End Date",
                            value=date.today().isoformat()
                        )

                    with gr.Column():
                        gr.Markdown("### Score Threshold")
                        score_threshold = gr.Slider(
                            minimum=0, maximum=100, value=70, step=1,
                            label="Minimum Score to Trade"
                        )

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Scoring Weights")
                        wallet_weight = gr.Slider(0, 1, 0.3, step=0.05, label="Wallet Score")
                        token_weight = gr.Slider(0, 1, 0.25, step=0.05, label="Token Metrics")
                        liquidity_weight = gr.Slider(0, 1, 0.2, step=0.05, label="Liquidity")
                        holder_weight = gr.Slider(0, 1, 0.15, step=0.05, label="Holder Distribution")
                        momentum_weight = gr.Slider(0, 1, 0.1, step=0.05, label="Momentum")
                        weight_sum = gr.Textbox(label="Weight Sum", value="1.00", interactive=False)

                    with gr.Column():
                        gr.Markdown("### Position Sizing")
                        base_position = gr.Number(value=0.1, label="Base Position (SOL)")
                        max_position = gr.Number(value=0.5, label="Max Position (SOL)")
                        scale_confidence = gr.Checkbox(value=True, label="Scale with Confidence")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Exit Strategy")
                        exit_strategy = gr.Dropdown(
                            choices=["trailing_stop", "fixed_targets", "time_based", "hybrid"],
                            value="trailing_stop",
                            label="Strategy"
                        )
                        stop_loss = gr.Slider(1, 50, 15, step=1, label="Stop Loss %")
                        take_profit = gr.Slider(5, 500, 50, step=5, label="Take Profit %")
                        trailing_stop = gr.Slider(1, 30, 10, step=1, label="Trailing Stop %")
                        max_hold = gr.Slider(5, 1440, 60, step=5, label="Max Hold (minutes)")

                    with gr.Column():
                        gr.Markdown("### Simulation Settings")
                        slippage = gr.Slider(0, 10, 1.0, step=0.1, label="Slippage %")
                        include_gas = gr.Checkbox(value=True, label="Include Gas Costs")
                        gas_cost = gr.Number(value=0.0001, label="Gas Cost (SOL)")

                run_btn = gr.Button("🚀 Run Backtest", variant="primary", size="lg")
                progress_text = gr.Textbox(label="Progress", interactive=False, visible=False)

            # Results Tab
            with gr.Tab("Results"):
                results_status = gr.Markdown("Run a backtest to see results.")
                metrics_html = gr.HTML()
                pnl_chart = gr.Plot(label="PnL Comparison")

            # Trade Comparison Tab
            with gr.Tab("Trade Comparison"):
                trade_table = gr.Dataframe(
                    headers=["Time", "Token", "Actual Trade", "Actual PnL", "Simulated Trade", "Simulated PnL", "Change"],
                    label="Trade-by-Trade Comparison"
                )
                trades_changed = gr.Textbox(label="Trades with Changes", interactive=False)

            # Apply Settings Tab
            with gr.Tab("Apply Settings"):
                apply_status = gr.Markdown("Run a successful backtest first.")

                with gr.Row():
                    apply_weights = gr.Checkbox(value=True, label="Apply Scoring Weights")
                    apply_threshold = gr.Checkbox(value=True, label="Apply Threshold")
                    apply_sizing = gr.Checkbox(value=True, label="Apply Position Sizing")
                    apply_exit = gr.Checkbox(value=True, label="Apply Exit Strategy")

                gr.Markdown("⚠️ **Warning:** This will modify your live trading parameters!")

                confirm_apply = gr.Checkbox(value=False, label="I confirm I want to apply these settings")
                apply_btn = gr.Button("Apply Settings", variant="stop")
                apply_result = gr.Textbox(label="Result", interactive=False)

        # Update weight sum
        def update_weight_sum(w, t, l, h, m):
            total = w + t + l + h + m
            color = "green" if abs(total - 1.0) < 0.01 else "red"
            return f"{total:.2f}"

        for w in [wallet_weight, token_weight, liquidity_weight, holder_weight, momentum_weight]:
            w.change(
                fn=update_weight_sum,
                inputs=[wallet_weight, token_weight, liquidity_weight, holder_weight, momentum_weight],
                outputs=[weight_sum]
            )

        # Run backtest
        async def run_backtest_handler(
            start, end, threshold,
            w_wallet, w_token, w_liquidity, w_holder, w_momentum,
            base_pos, max_pos, scale_conf,
            exit_strat, sl, tp, ts, hold,
            slip, gas_incl, gas
        ):
            service = await get_backtest_service()

            config = BacktestConfig(
                start_date=date.fromisoformat(start),
                end_date=date.fromisoformat(end),
                scoring_weights=ScoringWeights(
                    wallet_score_weight=Decimal(str(w_wallet)),
                    token_metrics_weight=Decimal(str(w_token)),
                    liquidity_weight=Decimal(str(w_liquidity)),
                    holder_distribution_weight=Decimal(str(w_holder)),
                    momentum_weight=Decimal(str(w_momentum))
                ),
                score_threshold=Decimal(str(threshold)),
                position_sizing=PositionSizingConfig(
                    base_position_sol=Decimal(str(base_pos)),
                    max_position_sol=Decimal(str(max_pos)),
                    scale_with_confidence=scale_conf
                ),
                exit_strategy=ExitStrategyConfig(
                    strategy=ExitStrategy(exit_strat),
                    stop_loss_percent=Decimal(str(sl)),
                    take_profit_percent=Decimal(str(tp)),
                    trailing_stop_percent=Decimal(str(ts)),
                    max_hold_minutes=int(hold)
                ),
                slippage_percent=Decimal(str(slip)),
                include_gas_costs=gas_incl,
                gas_cost_sol=Decimal(str(gas))
            )

            result = await service.run_backtest(config)

            if result.is_successful and result.metrics_comparison:
                metrics_display = create_metrics_comparison_display(result.metrics_comparison)
                chart = create_pnl_comparison_chart(result)
                table_data = create_trade_comparison_table(result)
                status = f"✅ Backtest completed in {result.duration_seconds}s - {result.total_signals_analyzed} signals analyzed"
                apply_status_text = "✅ Backtest successful! You can apply these settings."
                trades_changed_text = f"{result.trades_changed_count} trades would have different outcomes"
            else:
                metrics_display = f'<div style="color: red;">Backtest failed: {result.error_message}</div>'
                chart = go.Figure()
                table_data = []
                status = f"❌ Backtest failed: {result.error_message}"
                apply_status_text = "❌ Cannot apply settings from failed backtest."
                trades_changed_text = ""

            return (
                result,
                status,
                metrics_display,
                chart,
                table_data,
                trades_changed_text,
                apply_status_text
            )

        run_btn.click(
            fn=run_backtest_handler,
            inputs=[
                start_date, end_date, score_threshold,
                wallet_weight, token_weight, liquidity_weight, holder_weight, momentum_weight,
                base_position, max_position, scale_confidence,
                exit_strategy, stop_loss, take_profit, trailing_stop, max_hold,
                slippage, include_gas, gas_cost
            ],
            outputs=[
                backtest_result,
                results_status,
                metrics_html,
                pnl_chart,
                trade_table,
                trades_changed,
                apply_status
            ]
        )

        # Apply settings
        async def apply_settings_handler(result, weights, threshold, sizing, exit_s, confirm):
            if not result or not result.is_successful:
                return "No successful backtest to apply"

            if not confirm:
                return "Please confirm to apply settings"

            service = await get_backtest_service()

            request = ApplySettingsRequest(
                backtest_id=result.id,
                confirm_apply=True,
                apply_scoring_weights=weights,
                apply_threshold=threshold,
                apply_position_sizing=sizing,
                apply_exit_strategy=exit_s
            )

            apply_result = await service.apply_settings(request)

            if apply_result.success:
                return f"✅ Settings applied successfully!\nChanges: {', '.join(apply_result.changes_applied)}"
            else:
                return f"❌ Failed to apply: {apply_result.error_message}"

        apply_btn.click(
            fn=apply_settings_handler,
            inputs=[backtest_result, apply_weights, apply_threshold, apply_sizing, apply_exit, confirm_apply],
            outputs=[apply_result]
        )

    return panel
```

### 6. Unit Tests

```python
# tests/unit/feedback/test_backtester.py
"""Tests for backtest service."""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch, MagicMock

from src.walltrack.core.feedback.models.backtest import (
    BacktestConfig, BacktestStatus, BacktestResult, BacktestProgress,
    ScoringWeights, PositionSizingConfig, ExitStrategyConfig, ExitStrategy,
    HistoricalSignal, SimulatedTrade, PerformanceMetrics, MetricsComparison,
    TradeComparison, ApplySettingsRequest, ApplySettingsResult
)
from src.walltrack.core.feedback.services.backtester import (
    BacktestService, get_backtest_service
)


class TestScoringWeights:
    """Test ScoringWeights model."""

    def test_total_weight_valid(self):
        """Test valid weight sum."""
        weights = ScoringWeights(
            wallet_score_weight=Decimal("0.3"),
            token_metrics_weight=Decimal("0.25"),
            liquidity_weight=Decimal("0.2"),
            holder_distribution_weight=Decimal("0.15"),
            momentum_weight=Decimal("0.1")
        )
        assert weights.is_valid is True
        assert weights.total_weight == Decimal("1.0")

    def test_total_weight_invalid(self):
        """Test invalid weight sum."""
        weights = ScoringWeights(
            wallet_score_weight=Decimal("0.5"),
            token_metrics_weight=Decimal("0.5"),
            liquidity_weight=Decimal("0.5"),
            holder_distribution_weight=Decimal("0.5"),
            momentum_weight=Decimal("0.5")
        )
        assert weights.is_valid is False


class TestBacktestConfig:
    """Test BacktestConfig model."""

    def test_date_range_days(self):
        """Test date range calculation."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )
        assert config.date_range_days == 31

    def test_default_values(self):
        """Test default configuration values."""
        config = BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )
        assert config.score_threshold == Decimal("70")
        assert config.slippage_percent == Decimal("1.0")
        assert config.include_gas_costs is True


class TestSimulatedTrade:
    """Test SimulatedTrade model."""

    def test_net_pnl_calculation(self):
        """Test net PnL after costs."""
        trade = SimulatedTrade(
            signal_id="test",
            token_address="token123",
            source_wallet="wallet123",
            simulated_score=Decimal("80"),
            would_trade=True,
            entry_price=Decimal("1.0"),
            exit_price=Decimal("1.5"),
            exit_reason="take_profit",
            position_size_sol=Decimal("0.1"),
            gross_pnl_sol=Decimal("0.05"),
            slippage_cost_sol=Decimal("0.001"),
            gas_cost_sol=Decimal("0.0001")
        )

        assert trade.net_pnl_sol == Decimal("0.0489")
        assert trade.is_win is True

    def test_pnl_percent(self):
        """Test PnL percentage calculation."""
        trade = SimulatedTrade(
            signal_id="test",
            token_address="token123",
            source_wallet="wallet123",
            simulated_score=Decimal("80"),
            would_trade=True,
            entry_price=Decimal("1.0"),
            exit_price=Decimal("1.1"),
            exit_reason="take_profit",
            position_size_sol=Decimal("0.1"),
            gross_pnl_sol=Decimal("0.01"),
            slippage_cost_sol=Decimal("0.001"),
            gas_cost_sol=Decimal("0.0001")
        )

        # net_pnl = 0.01 - 0.001 - 0.0001 = 0.0089
        # pnl_percent = 0.0089 / 0.1 * 100 = 8.9%
        assert trade.pnl_percent == Decimal("8.90")


class TestPerformanceMetrics:
    """Test PerformanceMetrics model."""

    def test_win_rate(self):
        """Test win rate calculation."""
        metrics = PerformanceMetrics(
            total_trades=100,
            winning_trades=65,
            losing_trades=35
        )
        assert metrics.win_rate == Decimal("65.00")

    def test_profit_factor(self):
        """Test profit factor calculation."""
        metrics = PerformanceMetrics(
            gross_profit_sol=Decimal("10.0"),
            gross_loss_sol=Decimal("5.0")
        )
        assert metrics.profit_factor == Decimal("2.00")

    def test_expectancy(self):
        """Test expectancy calculation."""
        metrics = PerformanceMetrics(
            total_trades=10,
            total_pnl_sol=Decimal("1.0")
        )
        assert metrics.expectancy == Decimal("0.1000")


class TestMetricsComparison:
    """Test MetricsComparison model."""

    def test_improvement_detection(self):
        """Test improvement detection."""
        actual = PerformanceMetrics(
            total_trades=100,
            winning_trades=50,
            losing_trades=50,
            total_pnl_sol=Decimal("1.0")
        )

        simulated = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            total_pnl_sol=Decimal("2.0")
        )

        comparison = MetricsComparison(actual=actual, simulated=simulated)

        assert comparison.pnl_difference_sol == Decimal("1.0")
        assert comparison.is_improvement is True

    def test_no_improvement(self):
        """Test when simulated is worse."""
        actual = PerformanceMetrics(
            total_trades=100,
            winning_trades=60,
            losing_trades=40,
            total_pnl_sol=Decimal("2.0")
        )

        simulated = PerformanceMetrics(
            total_trades=100,
            winning_trades=40,
            losing_trades=60,
            total_pnl_sol=Decimal("0.5")
        )

        comparison = MetricsComparison(actual=actual, simulated=simulated)

        assert comparison.pnl_difference_sol == Decimal("-1.5")
        assert comparison.is_improvement is False


class TestTradeComparison:
    """Test TradeComparison model."""

    def test_outcome_changed_new_trade(self):
        """Test detecting new trade that would be made."""
        comparison = TradeComparison(
            signal_id="test",
            token_address="token123",
            timestamp=datetime.now(),
            actual_traded=False,
            actual_pnl_sol=None,
            simulated_traded=True,
            simulated_pnl_sol=Decimal("0.05")
        )

        assert comparison.outcome_changed is True
        assert "NEW TRADE" in comparison.change_description

    def test_outcome_changed_skipped(self):
        """Test detecting trade that would be skipped."""
        comparison = TradeComparison(
            signal_id="test",
            token_address="token123",
            timestamp=datetime.now(),
            actual_traded=True,
            actual_pnl_sol=Decimal("-0.02"),
            simulated_traded=False,
            simulated_pnl_sol=None
        )

        assert comparison.outcome_changed is True
        assert "SKIPPED" in comparison.change_description


class TestBacktestService:
    """Test BacktestService."""

    @pytest.fixture
    def service(self):
        """Create service instance."""
        return BacktestService()

    @pytest.fixture
    def sample_config(self):
        """Create sample backtest config."""
        return BacktestConfig(
            start_date=date(2024, 1, 1),
            end_date=date(2024, 1, 31)
        )

    @pytest.fixture
    def sample_signal(self):
        """Create sample historical signal."""
        return HistoricalSignal(
            id="signal-1",
            timestamp=datetime(2024, 1, 15, 10, 0),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={
                "wallet_score": 0.8,
                "token_metrics": 0.7,
                "liquidity": 0.6,
                "holder_distribution": 0.5,
                "momentum": 0.4
            },
            was_traded=True,
            actual_entry_price=Decimal("1.0"),
            actual_exit_price=Decimal("1.2"),
            actual_pnl_sol=Decimal("0.02"),
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5), Decimal("1.1")),
                (datetime(2024, 1, 15, 10, 10), Decimal("1.2")),
                (datetime(2024, 1, 15, 10, 15), Decimal("1.15")),
            ],
            max_price_after=Decimal("1.2"),
            min_price_after=Decimal("1.0")
        )

    @pytest.mark.asyncio
    async def test_rescore_signal(self, service, sample_signal):
        """Test signal rescoring with new weights."""
        new_weights = ScoringWeights(
            wallet_score_weight=Decimal("0.4"),
            token_metrics_weight=Decimal("0.3"),
            liquidity_weight=Decimal("0.15"),
            holder_distribution_weight=Decimal("0.1"),
            momentum_weight=Decimal("0.05")
        )

        rescored = await service._rescore_signal(sample_signal, new_weights)

        # Original score was 75, new score will be different
        assert rescored.original_score != Decimal("75")
        assert rescored.id == sample_signal.id

    def test_simulate_exit_take_profit(self, service, sample_signal, sample_config):
        """Test exit simulation hitting take profit."""
        # With default config, take profit at 50%
        exit_price, exit_reason = service._simulate_exit(sample_signal, sample_config)

        # Price went up to 1.2 (20%), didn't hit 50% TP
        # Should exit at trailing stop or end of data
        assert exit_reason in ["trailing_stop", "end_of_data", "time_limit"]

    def test_simulate_exit_stop_loss(self, service, sample_config):
        """Test exit simulation hitting stop loss."""
        signal = HistoricalSignal(
            id="signal-sl",
            timestamp=datetime(2024, 1, 15, 10, 0),
            token_address="token123",
            source_wallet="wallet123",
            original_score=Decimal("75"),
            original_factors={},
            was_traded=False,
            price_at_signal=Decimal("1.0"),
            price_history=[
                (datetime(2024, 1, 15, 10, 0), Decimal("1.0")),
                (datetime(2024, 1, 15, 10, 5), Decimal("0.9")),
                (datetime(2024, 1, 15, 10, 10), Decimal("0.8")),  # Below 15% SL
            ],
            max_price_after=Decimal("1.0"),
            min_price_after=Decimal("0.8")
        )

        exit_price, exit_reason = service._simulate_exit(signal, sample_config)

        assert exit_reason == "stop_loss"
        assert exit_price == Decimal("0.85")  # 15% below entry

    def test_calculate_simulated_metrics(self, service):
        """Test simulated metrics calculation."""
        trades = [
            SimulatedTrade(
                signal_id="1",
                token_address="t1",
                source_wallet="w1",
                simulated_score=Decimal("80"),
                would_trade=True,
                entry_price=Decimal("1.0"),
                exit_price=Decimal("1.2"),
                exit_reason="take_profit",
                position_size_sol=Decimal("0.1"),
                gross_pnl_sol=Decimal("0.02"),
                slippage_cost_sol=Decimal("0.001"),
                gas_cost_sol=Decimal("0.0001")
            ),
            SimulatedTrade(
                signal_id="2",
                token_address="t2",
                source_wallet="w1",
                simulated_score=Decimal("75"),
                would_trade=True,
                entry_price=Decimal("1.0"),
                exit_price=Decimal("0.9"),
                exit_reason="stop_loss",
                position_size_sol=Decimal("0.1"),
                gross_pnl_sol=Decimal("-0.01"),
                slippage_cost_sol=Decimal("0.001"),
                gas_cost_sol=Decimal("0.0001")
            ),
        ]

        metrics = service._calculate_simulated_metrics(trades)

        assert metrics.total_trades == 2
        assert metrics.winning_trades == 1
        assert metrics.losing_trades == 1
        assert metrics.win_rate == Decimal("50.00")

    def test_calculate_max_drawdown(self, service):
        """Test max drawdown calculation."""
        trades = [
            {"exit_timestamp": "2024-01-01T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-02T10:00:00Z", "realized_pnl_sol": "0.2"},
            {"exit_timestamp": "2024-01-03T10:00:00Z", "realized_pnl_sol": "-0.25"},
            {"exit_timestamp": "2024-01-04T10:00:00Z", "realized_pnl_sol": "-0.1"},
            {"exit_timestamp": "2024-01-05T10:00:00Z", "realized_pnl_sol": "0.15"},
        ]

        max_dd = service._calculate_max_drawdown(trades)

        # Peak at 0.3, trough at -0.05, drawdown = 0.35
        assert max_dd == Decimal("0.35")

    def test_calculate_max_consecutive_losses(self, service):
        """Test max consecutive losses calculation."""
        trades = [
            {"exit_timestamp": "2024-01-01T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-02T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-03T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-04T10:00:00Z", "realized_pnl_sol": "-0.05"},
            {"exit_timestamp": "2024-01-05T10:00:00Z", "realized_pnl_sol": "0.1"},
            {"exit_timestamp": "2024-01-06T10:00:00Z", "realized_pnl_sol": "-0.02"},
        ]

        max_consecutive = service._calculate_max_consecutive_losses(trades)

        assert max_consecutive == 3

    def test_get_progress(self, service):
        """Test progress tracking."""
        # No progress initially
        assert service.get_progress("nonexistent") is None

    def test_clear_cache(self, service):
        """Test cache clearing."""
        service._signal_cache["test_key"] = []
        assert len(service._signal_cache) == 1

        service.clear_cache()
        assert len(service._signal_cache) == 0


@pytest.mark.asyncio
async def test_get_backtest_service_singleton():
    """Test singleton pattern for backtest service."""
    service1 = await get_backtest_service()
    service2 = await get_backtest_service()

    assert service1 is service2
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/feedback/models/backtest.py`
- [ ] Create `src/walltrack/core/feedback/services/backtester.py`
- [ ] Create `src/walltrack/ui/components/backtest.py`
- [ ] Create `src/walltrack/api/routes/backtest.py`
- [ ] Add database tables for backtest storage
- [ ] Implement signal caching for performance
- [ ] Add progress streaming endpoint
- [ ] Implement settings application with rollback
- [ ] Add tests for all components
- [ ] Ensure < 30s completion time

## Definition of Done

- [ ] Backtest configurable with multiple parameters
- [ ] Historical signals re-scored correctly
- [ ] Comparison shows actual vs simulated
- [ ] Settings can be applied after review
- [ ] Progress indicator during execution
- [ ] Completion time < 30 seconds for 6 months of data
- [ ] All unit tests pass
