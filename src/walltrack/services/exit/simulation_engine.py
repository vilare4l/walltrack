"""Exit strategy simulation engine."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

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
    high: Decimal | None = None
    low: Decimal | None = None


@dataclass
class RuleTrigger:
    """Record of a rule being triggered."""

    timestamp: datetime
    rule_type: str
    trigger_pct: Decimal | None
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
    actual_exit_price: Decimal | None = None
    actual_exit_time: datetime | None = None
    actual_pnl_pct: Decimal | None = None
    pnl_difference: Decimal | None = None

    # Stats
    max_unrealized_gain_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    max_unrealized_loss_pct: Decimal = field(default_factory=lambda: Decimal("0"))
    hold_duration_hours: Decimal = field(default_factory=lambda: Decimal("0"))


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
    sharpe_ratio: Decimal | None = None


@dataclass
class StrategyComparison:
    """Comparison between multiple strategies."""

    strategies: list[str]
    results: dict[str, AggregateStats]  # strategy_id -> stats
    best_strategy_id: str
    best_by_metric: dict[str, str]  # metric -> strategy_id


class ExitSimulationEngine:
    """Simulates exit strategies on historical price data.

    Supports:
    - Single position simulation
    - Batch simulation across positions
    - Strategy comparison
    - What-if analysis on open positions
    """

    def __init__(self) -> None:
        self._price_repo: Any = None

    def _parse_timestamp(self, ts: datetime | str) -> datetime:
        """Parse timestamp from various formats."""
        if isinstance(ts, datetime):
            return ts
        ts_str = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)

    async def _get_price_repo(self) -> Any:
        """Get price history repository."""
        if self._price_repo is None:
            from walltrack.data.supabase.repositories.price_history_repo import (  # noqa: PLC0415
                get_price_history_repository,
            )

            self._price_repo = await get_price_history_repository()
        return self._price_repo

    async def simulate_position(
        self,
        strategy: ExitStrategy,
        position_id: str,
        entry_price: Decimal,
        entry_time: datetime,
        position_size_sol: Decimal,
        token_address: str | None = None,  # noqa: ARG002
        actual_exit: tuple[Decimal, datetime] | None = None,
        end_time: datetime | None = None,
        price_history: list[dict[str, Any]] | None = None,
    ) -> SimulationResult:
        """Simulate a strategy on a single position.

        Args:
            strategy: Exit strategy to simulate
            position_id: Position identifier
            entry_price: Entry price
            entry_time: Entry timestamp
            position_size_sol: Position size in SOL
            token_address: Token address (reserved for future use)
            actual_exit: Optional (price, time) of actual exit for comparison
            end_time: Optional end time for simulation (defaults to now)
            price_history: Optional pre-fetched price history

        Returns:
            SimulationResult with detailed trigger info
        """
        # Get price history if not provided
        if price_history is None:
            price_repo = await self._get_price_repo()
            end = end_time or datetime.now(UTC)

            prices_raw = await price_repo.get_history(
                position_id=position_id,
                start=entry_time,
                end=end,
            )

            if not prices_raw:
                raise ValueError(f"No price history for position {position_id}")

            # Convert to dicts for internal processing
            price_history = [
                {
                    "timestamp": p.recorded_at,
                    "price": p.price,
                }
                for p in prices_raw
            ]

        # Convert to PricePoints and sort by time
        price_points = [
            PricePoint(
                timestamp=self._parse_timestamp(p["timestamp"]),
                price=Decimal(str(p["price"])),
                high=Decimal(str(p.get("high", p["price"]))) if p.get("high") else None,
                low=Decimal(str(p.get("low", p["price"]))) if p.get("low") else None,
            )
            for p in price_history
        ]
        price_points.sort(key=lambda p: p.timestamp)

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

    def _simulate_on_prices(  # noqa: PLR0915
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
            max_gain = max(max_gain, pnl_pct)
            max_loss = min(max_loss, pnl_pct)

            # Update trailing high
            trailing_high_price = max(trailing_high_price, current_price)

            # Check time-based rules
            hold_hours = (price_point.timestamp - entry_time).total_seconds() / 3600

            # Check stagnation
            stagnation_triggered = (
                hold_hours >= strategy.stagnation_hours
                and abs(pnl_pct) <= strategy.stagnation_threshold_pct
            )
            if stagnation_triggered:
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
        hold_duration = Decimal(
            str((final_exit_time - entry_time).total_seconds() / 3600)
        )

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

    def _check_rule(  # noqa: PLR0911
        self,
        rule: ExitStrategyRule,
        pnl_pct: Decimal,
        current_price: Decimal,
        trailing_high_price: Decimal,
        hold_hours: float,
    ) -> bool:
        """Check if a rule is triggered."""
        if rule.trigger_pct is None:
            # Time-based rule or other non-price rules
            if rule.rule_type == "time_based":
                max_hours = rule.params.get("max_hours", 24)
                return hold_hours >= max_hours
            return False

        if rule.rule_type == "take_profit":
            return pnl_pct >= rule.trigger_pct

        if rule.rule_type == "stop_loss":
            return pnl_pct <= rule.trigger_pct  # trigger_pct is negative

        if rule.rule_type == "trailing_stop":
            activation_pct = Decimal(str(rule.params.get("activation_pct", 0)))
            # Check if trailing stop is activated and trailing high is valid
            if pnl_pct >= activation_pct and trailing_high_price > 0:
                drop_from_high = (
                    (trailing_high_price - current_price) / trailing_high_price
                ) * 100
                return drop_from_high >= abs(rule.trigger_pct)
            return False

        if rule.rule_type == "time_based":
            max_hours = rule.params.get("max_hours", 24)
            return hold_hours >= max_hours

        return False

    async def batch_simulate(
        self,
        strategy: ExitStrategy,
        positions: list[dict[str, Any]],
    ) -> tuple[list[SimulationResult], AggregateStats]:
        """Simulate strategy on multiple positions.

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
                    token_address=pos.get("token_address"),
                    actual_exit=(
                        (Decimal(str(pos["exit_price"])), pos["exit_time"])
                        if pos.get("exit_price")
                        else None
                    ),
                    price_history=pos.get("price_history"),
                )
                results.append(result)
            except Exception as e:
                logger.warning("simulation_error", position=pos["id"], error=str(e))

        stats = self._calculate_aggregate_stats(results)

        return results, stats

    def _calculate_aggregate_stats(
        self, results: list[SimulationResult]
    ) -> AggregateStats:
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
            win_rate=(
                Decimal(str(winning / total * 100)) if total > 0 else Decimal("0")
            ),
            total_pnl_pct=sum(pnls),
            avg_pnl_pct=sum(pnls) / len(pnls) if pnls else Decimal("0"),
            max_gain_pct=max(pnls) if pnls else Decimal("0"),
            max_loss_pct=min(pnls) if pnls else Decimal("0"),
            avg_hold_hours=(
                sum(hold_hours) / len(hold_hours) if hold_hours else Decimal("0")
            ),
        )

    async def compare_strategies(
        self,
        strategies: list[ExitStrategy],
        positions: list[dict[str, Any]],
    ) -> StrategyComparison:
        """Compare multiple strategies on the same positions.

        Returns comparison with best strategy highlighted.
        """
        all_stats: dict[str, AggregateStats] = {}

        for strategy in strategies:
            _, stats = await self.batch_simulate(strategy, positions)
            all_stats[strategy.id] = stats

        # Find best by each metric
        best_by_metric: dict[str, str] = {}

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
_simulation_engine: ExitSimulationEngine | None = None


async def get_simulation_engine() -> ExitSimulationEngine:
    """Get or create simulation engine singleton."""
    global _simulation_engine

    if _simulation_engine is None:
        _simulation_engine = ExitSimulationEngine()

    return _simulation_engine


def reset_simulation_engine() -> None:
    """Reset the singleton (for testing)."""
    global _simulation_engine
    _simulation_engine = None
