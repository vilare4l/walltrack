# Story 11.8: Exit Strategy - Simulation Engine

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: done
- **Priority**: P0 - Critical
- **Story Points**: 8
- **Depends on**: Story 11-7 (Exit Strategy CRUD), Story 10.5-7 (Price History)

## ⚠️ Important: Simulation unique

**Cette story implémente LE simulateur de stratégies de sortie.**

Epic 12 (Story 12-5: PositionSimulator) **DOIT réutiliser** ce moteur au lieu de créer un doublon.
Le `PositionSimulator` de 12-5 devient un **wrapper** autour de ce `ExitSimulationEngine`.

| Composant | Rôle |
|-----------|------|
| `ExitSimulationEngine` (11-8) | Core simulation logic |
| `PositionSimulator` (12-5) | Position-specific wrapper (uses 11-8) |
| `WhatIfCalculator` (11-8) | Open position analysis |

## User Story

**As a** trader,
**I want** to simulate exit strategies on historical data,
**So that** I can evaluate strategy performance before using it live.

## Acceptance Criteria

### AC 1: Simulate on Single Position
**Given** a closed position with price history
**When** I run simulation with a strategy
**Then** I get simulated exit points and P&L
**And** I can compare to actual exit

### AC 2: Simulate on Multiple Positions
**Given** multiple historical positions
**When** I run batch simulation
**Then** I get aggregate statistics
**And** win rate, avg P&L, max drawdown are calculated

### AC 3: Compare Strategies
**Given** two or more exit strategies
**When** I run comparison simulation
**Then** I see side-by-side results
**And** best performing strategy is highlighted

### AC 4: What-If Analysis
**Given** current open position with live price
**When** I simulate with different strategies
**Then** I see projected outcomes at current price
**And** I can see breakeven points

### AC 5: Rule Triggers Timeline
**Given** simulation results
**When** I view details
**Then** I see which rules triggered when
**And** timeline shows price path with trigger points

## Technical Specifications

### Simulation Engine

**src/walltrack/services/exit/simulation_engine.py:**
```python
"""Exit strategy simulation engine."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

import structlog

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyRule,
)

logger = structlog.get_logger(__name__)


@dataclass
class PricePoint:
    """Single price point in history."""
    timestamp: datetime
    price: Decimal
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None


@dataclass
class RuleTrigger:
    """Record of a rule being triggered."""
    timestamp: datetime
    rule_type: str
    trigger_pct: Optional[Decimal]
    price_at_trigger: Decimal
    pnl_pct: Decimal
    exit_pct: Decimal
    cumulative_exit_pct: Decimal


@dataclass
class SimulationResult:
    """Result of simulating a strategy on a position."""
    strategy_id: str
    strategy_name: str
    position_id: str
    entry_price: Decimal
    entry_time: datetime

    # Exit simulation
    triggers: list[RuleTrigger]
    final_exit_price: Decimal
    final_exit_time: datetime
    final_pnl_pct: Decimal
    final_pnl_sol: Decimal

    # Comparison with actual (if position was closed)
    actual_exit_price: Optional[Decimal] = None
    actual_exit_time: Optional[datetime] = None
    actual_pnl_pct: Optional[Decimal] = None
    pnl_difference: Optional[Decimal] = None

    # Stats
    max_unrealized_gain_pct: Decimal = Decimal("0")
    max_unrealized_loss_pct: Decimal = Decimal("0")
    hold_duration_hours: Decimal = Decimal("0")


@dataclass
class AggregateStats:
    """Aggregate statistics for batch simulation."""
    total_positions: int
    winning_positions: int
    losing_positions: int
    win_rate: Decimal
    total_pnl_pct: Decimal
    avg_pnl_pct: Decimal
    max_gain_pct: Decimal
    max_loss_pct: Decimal
    avg_hold_hours: Decimal
    sharpe_ratio: Optional[Decimal] = None


@dataclass
class StrategyComparison:
    """Comparison between multiple strategies."""
    strategies: list[str]
    results: dict[str, AggregateStats]  # strategy_id -> stats
    best_strategy_id: str
    best_by_metric: dict[str, str]  # metric -> strategy_id


class ExitSimulationEngine:
    """
    Simulates exit strategies on historical price data.

    Supports:
    - Single position simulation
    - Batch simulation across positions
    - Strategy comparison
    - What-if analysis on open positions
    """

    def __init__(self):
        self._price_service = None

    async def _get_price_service(self):
        """Get price history service."""
        if self._price_service is None:
            from walltrack.services.pricing.price_history_service import get_price_history_service
            self._price_service = await get_price_history_service()
        return self._price_service

    async def simulate_position(
        self,
        strategy: ExitStrategy,
        position_id: str,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        token_address: str,
        actual_exit: Optional[tuple[Decimal, datetime]] = None,
        end_time: Optional[datetime] = None,
    ) -> SimulationResult:
        """
        Simulate a strategy on a single position.

        Args:
            strategy: Exit strategy to simulate
            position_id: Position identifier
            entry_price: Entry price
            entry_time: Entry timestamp
            position_size_sol: Position size in SOL
            token_address: Token address for price history
            actual_exit: Optional (price, time) of actual exit for comparison
            end_time: Optional end time for simulation (defaults to now)

        Returns:
            SimulationResult with detailed trigger info
        """
        # Get price history
        price_service = await self._get_price_service()
        end = end_time or datetime.utcnow()

        prices = await price_service.get_price_history(
            token_address=token_address,
            start_time=entry_time,
            end_time=end,
        )

        if not prices:
            raise ValueError(f"No price history for {token_address}")

        # Convert to PricePoints
        price_points = [
            PricePoint(
                timestamp=p["timestamp"],
                price=Decimal(str(p["price"])),
                high=Decimal(str(p.get("high", p["price"]))),
                low=Decimal(str(p.get("low", p["price"]))),
            )
            for p in prices
        ]

        # Run simulation
        result = self._simulate_on_prices(
            strategy=strategy,
            position_id=position_id,
            entry_price=entry_price,
            entry_time=entry_time,
            position_size_sol=position_size_sol,
            prices=price_points,
        )

        # Add actual comparison if provided
        if actual_exit:
            actual_price, actual_time = actual_exit
            result.actual_exit_price = actual_price
            result.actual_exit_time = actual_time
            result.actual_pnl_pct = ((actual_price - entry_price) / entry_price) * 100
            result.pnl_difference = result.final_pnl_pct - result.actual_pnl_pct

        return result

    def _simulate_on_prices(
        self,
        strategy: ExitStrategy,
        position_id: str,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        prices: list[PricePoint],
    ) -> SimulationResult:
        """Core simulation logic on price series."""
        triggers: list[RuleTrigger] = []
        cumulative_exit_pct = Decimal("0")
        remaining_position_pct = Decimal("100")

        max_gain = Decimal("0")
        max_loss = Decimal("0")

        # Trailing stop state
        trailing_activated = False
        trailing_high_price = entry_price

        # Sort rules by priority
        active_rules = [r for r in strategy.rules if r.enabled]
        active_rules.sort(key=lambda r: r.priority)

        for price_point in prices:
            if remaining_position_pct <= 0:
                break

            current_price = price_point.price
            pnl_pct = ((current_price - entry_price) / entry_price) * 100

            # Track max unrealized
            if pnl_pct > max_gain:
                max_gain = pnl_pct
            if pnl_pct < max_loss:
                max_loss = pnl_pct

            # Update trailing high
            if current_price > trailing_high_price:
                trailing_high_price = current_price

            # Check time-based rules
            hold_hours = (price_point.timestamp - entry_time).total_seconds() / 3600

            # Check stagnation
            if hold_hours >= strategy.stagnation_hours:
                if abs(pnl_pct) <= strategy.stagnation_threshold_pct:
                    # Stagnation exit
                    trigger = RuleTrigger(
                        timestamp=price_point.timestamp,
                        rule_type="stagnation",
                        trigger_pct=strategy.stagnation_threshold_pct,
                        price_at_trigger=current_price,
                        pnl_pct=pnl_pct,
                        exit_pct=remaining_position_pct,
                        cumulative_exit_pct=Decimal("100"),
                    )
                    triggers.append(trigger)
                    remaining_position_pct = Decimal("0")
                    break

            # Check max hold time
            if hold_hours >= strategy.max_hold_hours:
                trigger = RuleTrigger(
                    timestamp=price_point.timestamp,
                    rule_type="max_hold_time",
                    trigger_pct=None,
                    price_at_trigger=current_price,
                    pnl_pct=pnl_pct,
                    exit_pct=remaining_position_pct,
                    cumulative_exit_pct=Decimal("100"),
                )
                triggers.append(trigger)
                remaining_position_pct = Decimal("0")
                break

            # Check rules
            for rule in active_rules:
                if remaining_position_pct <= 0:
                    break

                triggered = self._check_rule(
                    rule=rule,
                    pnl_pct=pnl_pct,
                    current_price=current_price,
                    entry_price=entry_price,
                    trailing_high_price=trailing_high_price,
                    hold_hours=hold_hours,
                )

                if triggered:
                    exit_amount = min(rule.exit_pct, remaining_position_pct)
                    cumulative_exit_pct += exit_amount
                    remaining_position_pct -= exit_amount

                    trigger = RuleTrigger(
                        timestamp=price_point.timestamp,
                        rule_type=rule.rule_type,
                        trigger_pct=rule.trigger_pct,
                        price_at_trigger=current_price,
                        pnl_pct=pnl_pct,
                        exit_pct=exit_amount,
                        cumulative_exit_pct=cumulative_exit_pct,
                    )
                    triggers.append(trigger)

        # Calculate final results
        if triggers:
            # Weighted average exit price/pnl
            total_weight = Decimal("0")
            weighted_pnl = Decimal("0")
            weighted_price = Decimal("0")

            for t in triggers:
                weight = t.exit_pct / 100
                total_weight += weight
                weighted_pnl += t.pnl_pct * weight
                weighted_price += t.price_at_trigger * weight

            final_pnl_pct = weighted_pnl
            final_exit_price = weighted_price
            final_exit_time = triggers[-1].timestamp
        else:
            # No exit triggered, use last price
            last_price = prices[-1] if prices else PricePoint(entry_time, entry_price)
            final_pnl_pct = ((last_price.price - entry_price) / entry_price) * 100
            final_exit_price = last_price.price
            final_exit_time = last_price.timestamp

        final_pnl_sol = position_size_sol * (final_pnl_pct / 100)
        hold_duration = Decimal(str((final_exit_time - entry_time).total_seconds() / 3600))

        return SimulationResult(
            strategy_id=strategy.id,
            strategy_name=strategy.name,
            position_id=position_id,
            entry_price=entry_price,
            entry_time=entry_time,
            triggers=triggers,
            final_exit_price=final_exit_price,
            final_exit_time=final_exit_time,
            final_pnl_pct=final_pnl_pct,
            final_pnl_sol=final_pnl_sol,
            max_unrealized_gain_pct=max_gain,
            max_unrealized_loss_pct=max_loss,
            hold_duration_hours=hold_duration,
        )

    def _check_rule(
        self,
        rule: ExitStrategyRule,
        pnl_pct: Decimal,
        current_price: Decimal,
        entry_price: Decimal,
        trailing_high_price: Decimal,
        hold_hours: float,
    ) -> bool:
        """Check if a rule is triggered."""
        if rule.rule_type == "take_profit":
            return pnl_pct >= rule.trigger_pct

        elif rule.rule_type == "stop_loss":
            return pnl_pct <= rule.trigger_pct  # trigger_pct is negative

        elif rule.rule_type == "trailing_stop":
            activation_pct = rule.params.get("activation_pct", 0)
            # Check if trailing stop is activated
            if pnl_pct >= activation_pct:
                # Check trailing condition
                drop_from_high = ((trailing_high_price - current_price) / trailing_high_price) * 100
                return drop_from_high >= abs(rule.trigger_pct)
            return False

        elif rule.rule_type == "time_based":
            max_hours = rule.params.get("max_hours", 24)
            return hold_hours >= max_hours

        return False

    async def batch_simulate(
        self,
        strategy: ExitStrategy,
        positions: list[dict],
    ) -> tuple[list[SimulationResult], AggregateStats]:
        """
        Simulate strategy on multiple positions.

        Args:
            strategy: Exit strategy to simulate
            positions: List of position dicts with required fields

        Returns:
            (list of results, aggregate stats)
        """
        results = []

        for pos in positions:
            try:
                result = await self.simulate_position(
                    strategy=strategy,
                    position_id=pos["id"],
                    entry_price=Decimal(str(pos["entry_price"])),
                    entry_time=pos["entry_time"],
                    position_size_sol=Decimal(str(pos["size_sol"])),
                    token_address=pos["token_address"],
                    actual_exit=(
                        Decimal(str(pos["exit_price"])),
                        pos["exit_time"]
                    ) if pos.get("exit_price") else None,
                )
                results.append(result)
            except Exception as e:
                logger.warning("simulation_error", position=pos["id"], error=str(e))

        stats = self._calculate_aggregate_stats(results)

        return results, stats

    def _calculate_aggregate_stats(self, results: list[SimulationResult]) -> AggregateStats:
        """Calculate aggregate statistics from results."""
        if not results:
            return AggregateStats(
                total_positions=0,
                winning_positions=0,
                losing_positions=0,
                win_rate=Decimal("0"),
                total_pnl_pct=Decimal("0"),
                avg_pnl_pct=Decimal("0"),
                max_gain_pct=Decimal("0"),
                max_loss_pct=Decimal("0"),
                avg_hold_hours=Decimal("0"),
            )

        pnls = [r.final_pnl_pct for r in results]
        hold_hours = [r.hold_duration_hours for r in results]

        winning = sum(1 for p in pnls if p > 0)
        losing = sum(1 for p in pnls if p <= 0)
        total = len(results)

        return AggregateStats(
            total_positions=total,
            winning_positions=winning,
            losing_positions=losing,
            win_rate=Decimal(str(winning / total * 100)) if total > 0 else Decimal("0"),
            total_pnl_pct=sum(pnls),
            avg_pnl_pct=sum(pnls) / len(pnls) if pnls else Decimal("0"),
            max_gain_pct=max(pnls) if pnls else Decimal("0"),
            max_loss_pct=min(pnls) if pnls else Decimal("0"),
            avg_hold_hours=sum(hold_hours) / len(hold_hours) if hold_hours else Decimal("0"),
        )

    async def compare_strategies(
        self,
        strategies: list[ExitStrategy],
        positions: list[dict],
    ) -> StrategyComparison:
        """
        Compare multiple strategies on the same positions.

        Returns comparison with best strategy highlighted.
        """
        all_stats: dict[str, AggregateStats] = {}

        for strategy in strategies:
            _, stats = await self.batch_simulate(strategy, positions)
            all_stats[strategy.id] = stats

        # Find best by each metric
        best_by_metric = {}

        # Best win rate
        best_wr = max(all_stats.items(), key=lambda x: x[1].win_rate)
        best_by_metric["win_rate"] = best_wr[0]

        # Best avg PnL
        best_pnl = max(all_stats.items(), key=lambda x: x[1].avg_pnl_pct)
        best_by_metric["avg_pnl"] = best_pnl[0]

        # Best total PnL
        best_total = max(all_stats.items(), key=lambda x: x[1].total_pnl_pct)
        best_by_metric["total_pnl"] = best_total[0]

        # Overall best (by total PnL)
        best_strategy_id = best_total[0]

        return StrategyComparison(
            strategies=[s.id for s in strategies],
            results=all_stats,
            best_strategy_id=best_strategy_id,
            best_by_metric=best_by_metric,
        )


# Singleton
_simulation_engine: Optional[ExitSimulationEngine] = None


async def get_simulation_engine() -> ExitSimulationEngine:
    """Get or create simulation engine singleton."""
    global _simulation_engine

    if _simulation_engine is None:
        _simulation_engine = ExitSimulationEngine()

    return _simulation_engine
```

### What-If Calculator

**src/walltrack/services/exit/what_if_calculator.py:**
```python
"""What-if analysis for exit strategies on open positions."""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Optional

from walltrack.services.exit.exit_strategy_service import ExitStrategy


@dataclass
class WhatIfScenario:
    """Projected outcome at a given price."""
    price: Decimal
    pnl_pct: Decimal
    pnl_sol: Decimal
    triggered_rules: list[str]
    action: str  # "hold", "partial_exit", "full_exit"
    exit_pct: Decimal


@dataclass
class WhatIfAnalysis:
    """Complete what-if analysis for a position."""
    position_id: str
    entry_price: Decimal
    current_price: Decimal
    position_size_sol: Decimal
    strategy_name: str

    # Key levels
    breakeven_price: Decimal
    stop_loss_price: Optional[Decimal]
    first_tp_price: Optional[Decimal]

    # Scenarios
    scenarios: list[WhatIfScenario]

    # Current state
    current_pnl_pct: Decimal
    current_pnl_sol: Decimal
    time_held_hours: Decimal


class WhatIfCalculator:
    """Calculate what-if scenarios for open positions."""

    def analyze(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        current_price: Decimal,
        position_size_sol: Decimal,
        entry_time: datetime,
        position_id: str = "current",
    ) -> WhatIfAnalysis:
        """
        Analyze what-if scenarios for a position.

        Generates scenarios at key price levels.
        """
        # Calculate key levels
        stop_loss_price = None
        first_tp_price = None

        for rule in strategy.rules:
            if rule.rule_type == "stop_loss" and rule.trigger_pct:
                stop_loss_price = entry_price * (1 + rule.trigger_pct / 100)
            elif rule.rule_type == "take_profit" and rule.trigger_pct:
                if first_tp_price is None:
                    first_tp_price = entry_price * (1 + rule.trigger_pct / 100)

        # Generate scenarios at different price points
        scenarios = []

        # Key price levels to analyze
        price_levels = self._generate_price_levels(
            entry_price=entry_price,
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            first_tp_price=first_tp_price,
        )

        for price in price_levels:
            scenario = self._calculate_scenario(
                strategy=strategy,
                entry_price=entry_price,
                test_price=price,
                position_size_sol=position_size_sol,
            )
            scenarios.append(scenario)

        # Current state
        current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
        current_pnl_sol = position_size_sol * (current_pnl_pct / 100)
        time_held = Decimal(str((datetime.utcnow() - entry_time).total_seconds() / 3600))

        return WhatIfAnalysis(
            position_id=position_id,
            entry_price=entry_price,
            current_price=current_price,
            position_size_sol=position_size_sol,
            strategy_name=strategy.name,
            breakeven_price=entry_price,
            stop_loss_price=stop_loss_price,
            first_tp_price=first_tp_price,
            scenarios=scenarios,
            current_pnl_pct=current_pnl_pct,
            current_pnl_sol=current_pnl_sol,
            time_held_hours=time_held,
        )

    def _generate_price_levels(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        stop_loss_price: Optional[Decimal],
        first_tp_price: Optional[Decimal],
    ) -> list[Decimal]:
        """Generate price levels to analyze."""
        levels = set()

        # Add entry and current
        levels.add(entry_price)
        levels.add(current_price)

        # Add stop loss and TP if defined
        if stop_loss_price:
            levels.add(stop_loss_price)
        if first_tp_price:
            levels.add(first_tp_price)

        # Add percentage steps
        for pct in [-20, -15, -10, -5, 0, 5, 10, 15, 20, 30, 50, 100]:
            price = entry_price * (1 + Decimal(pct) / 100)
            levels.add(price.quantize(Decimal("0.000001")))

        return sorted(levels)

    def _calculate_scenario(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        test_price: Decimal,
        position_size_sol: Decimal,
    ) -> WhatIfScenario:
        """Calculate scenario at a specific price."""
        pnl_pct = ((test_price - entry_price) / entry_price) * 100
        pnl_sol = position_size_sol * (pnl_pct / 100)

        # Check which rules would trigger
        triggered_rules = []
        total_exit_pct = Decimal("0")

        for rule in strategy.rules:
            if not rule.enabled:
                continue

            triggered = False

            if rule.rule_type == "take_profit" and rule.trigger_pct:
                triggered = pnl_pct >= rule.trigger_pct

            elif rule.rule_type == "stop_loss" and rule.trigger_pct:
                triggered = pnl_pct <= rule.trigger_pct

            if triggered:
                triggered_rules.append(rule.rule_type)
                total_exit_pct = min(total_exit_pct + rule.exit_pct, Decimal("100"))

        # Determine action
        if total_exit_pct >= 100:
            action = "full_exit"
        elif total_exit_pct > 0:
            action = "partial_exit"
        else:
            action = "hold"

        return WhatIfScenario(
            price=test_price,
            pnl_pct=pnl_pct,
            pnl_sol=pnl_sol,
            triggered_rules=triggered_rules,
            action=action,
            exit_pct=total_exit_pct,
        )
```

## Implementation Tasks

- [x] Create SimulationResult dataclass
- [x] Create AggregateStats dataclass
- [x] Create StrategyComparison dataclass
- [x] Implement ExitSimulationEngine class
- [x] Implement simulate_position() method
- [x] Implement _simulate_on_prices() core logic
- [x] Implement _check_rule() for all rule types
- [x] Implement batch_simulate() method
- [x] Implement compare_strategies() method
- [x] Create WhatIfCalculator class
- [x] Write unit tests with mock price data
- [x] Write integration tests

## Definition of Done

- [x] Single position simulation works
- [x] All rule types properly evaluated
- [x] Batch simulation calculates correct stats
- [x] Strategy comparison identifies best
- [x] What-if analysis generates scenarios
- [x] Tests pass with >90% coverage

## File List

### New Files
- `src/walltrack/services/exit/simulation_engine.py` - Main simulation engine
- `src/walltrack/services/exit/what_if_calculator.py` - What-if analysis
- `tests/unit/services/exit/test_simulation_engine.py` - Tests
- `tests/unit/services/exit/test_what_if.py` - What-if tests
