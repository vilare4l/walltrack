"""Parameter optimization for backtesting."""

import asyncio
import itertools
import random
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

import structlog
from pydantic import BaseModel, Field

from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.parameters import (
    BacktestParameters,
    ExitStrategyParams,
    ScoringWeights,
)
from walltrack.core.backtest.results import BacktestResult

log = structlog.get_logger()


class OptimizationObjective(str, Enum):
    """Objective to optimize for."""

    TOTAL_PNL = "total_pnl"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    RISK_ADJUSTED = "risk_adjusted"


class ParameterRange(BaseModel):
    """A parameter to optimize with its range.

    Defines the values to test for a single parameter.
    """

    name: str
    values: list[Any]
    display_name: str | None = None

    @property
    def count(self) -> int:
        """Number of values to test.

        Returns:
            Count of values in the range.
        """
        return len(self.values)


class OptimizationConfig(BaseModel):
    """Configuration for optimization run.

    Defines date range, parameters to optimize, and execution settings.
    """

    # Date range
    start_date: datetime
    end_date: datetime

    # Parameters to optimize
    parameter_ranges: list[ParameterRange] = Field(default_factory=list)

    # Objective
    objective: OptimizationObjective = OptimizationObjective.TOTAL_PNL
    secondary_objectives: list[OptimizationObjective] = Field(default_factory=list)

    # Execution settings
    max_workers: int = 4
    max_combinations: int = 500
    sample_if_exceed: bool = True
    random_seed: int = 42

    # Base parameters (fixed)
    base_params: dict = Field(default_factory=dict)

    @property
    def total_combinations(self) -> int:
        """Calculate total number of combinations.

        Returns:
            Total combinations to test.
        """
        if not self.parameter_ranges:
            return 0
        result = 1
        for p in self.parameter_ranges:
            result *= p.count
        return result


class OptimizationResult(BaseModel):
    """Result of a single parameter combination.

    Contains the backtest result and objective values.
    """

    combination_id: int
    parameters: dict

    # Backtest result
    backtest_result: BacktestResult | None = None

    # Primary objective value
    objective_value: Decimal = Decimal("0")
    secondary_values: dict[str, Decimal] = Field(default_factory=dict)

    # Execution
    duration_seconds: float = 0
    error: str | None = None


class OptimizationSummary(BaseModel):
    """Summary of optimization run.

    Contains all results, best configuration, and analysis.
    """

    config: OptimizationConfig

    # Timing
    started_at: datetime
    completed_at: datetime | None = None
    total_duration_seconds: float = 0

    # Results
    total_combinations: int
    completed_combinations: int = 0
    failed_combinations: int = 0
    results: list[OptimizationResult] = Field(default_factory=list)

    # Best results
    best_result: OptimizationResult | None = None
    best_parameters: dict = Field(default_factory=dict)

    # Pareto frontier
    pareto_frontier: list[OptimizationResult] = Field(default_factory=list)

    # Sensitivity analysis
    parameter_sensitivity: dict[str, dict] = Field(default_factory=dict)


class GridSearchOptimizer:
    """Grid search optimizer for backtest parameters.

    Tests all parameter combinations and finds optimal configuration.
    """

    def __init__(self, max_workers: int = 4) -> None:
        """Initialize the optimizer.

        Args:
            max_workers: Maximum concurrent backtests.
        """
        self._max_workers = max_workers
        self._cancelled = False

    async def optimize(
        self,
        config: OptimizationConfig,
        on_progress: Callable[[int, int], None] | None = None,
    ) -> OptimizationSummary:
        """Run grid search optimization.

        Args:
            config: Optimization configuration.
            on_progress: Optional progress callback (done, total).

        Returns:
            OptimizationSummary with all results.
        """
        started_at = datetime.now(UTC)

        # Generate all combinations
        combinations = self._generate_combinations(config)

        # Apply sampling if needed
        if len(combinations) > config.max_combinations and config.sample_if_exceed:
            random.seed(config.random_seed)
            combinations = random.sample(combinations, config.max_combinations)

        summary = OptimizationSummary(
            config=config,
            started_at=started_at,
            total_combinations=len(combinations),
        )

        # Run backtests
        semaphore = asyncio.Semaphore(config.max_workers)
        results: list[OptimizationResult] = []

        async def run_combination(combo_id: int, params: dict) -> OptimizationResult:
            async with semaphore:
                if self._cancelled:
                    return OptimizationResult(
                        combination_id=combo_id,
                        parameters=params,
                        error="Cancelled",
                    )

                start = datetime.now(UTC)
                try:
                    # Build backtest parameters
                    backtest_params = self._build_params(
                        config.base_params,
                        params,
                        config.start_date,
                        config.end_date,
                    )

                    engine = BacktestEngine(backtest_params)
                    bt_result = await engine.run(name=f"Opt_{combo_id}")

                    # Extract objective value
                    obj_value = self._get_objective_value(bt_result, config.objective)

                    # Extract secondary objectives
                    secondary = {}
                    for sec_obj in config.secondary_objectives:
                        secondary[sec_obj.value] = self._get_objective_value(
                            bt_result, sec_obj
                        )

                    return OptimizationResult(
                        combination_id=combo_id,
                        parameters=params,
                        backtest_result=bt_result,
                        objective_value=obj_value,
                        secondary_values=secondary,
                        duration_seconds=(datetime.now(UTC) - start).total_seconds(),
                    )

                except Exception as e:
                    return OptimizationResult(
                        combination_id=combo_id,
                        parameters=params,
                        error=str(e),
                        duration_seconds=(datetime.now(UTC) - start).total_seconds(),
                    )

        # Execute all combinations
        tasks = [run_combination(i, combo) for i, combo in enumerate(combinations)]

        for coro in asyncio.as_completed(tasks):
            result = await coro
            results.append(result)

            if result.error:
                summary.failed_combinations += 1
            else:
                summary.completed_combinations += 1

            if on_progress:
                on_progress(
                    summary.completed_combinations + summary.failed_combinations,
                    summary.total_combinations,
                )

        # Sort results by objective
        valid_results = [r for r in results if r.backtest_result]
        valid_results.sort(key=lambda r: r.objective_value, reverse=True)

        summary.results = results
        summary.completed_at = datetime.now(UTC)
        summary.total_duration_seconds = (
            summary.completed_at - summary.started_at
        ).total_seconds()

        # Find best result
        if valid_results:
            summary.best_result = valid_results[0]
            summary.best_parameters = valid_results[0].parameters

        # Calculate Pareto frontier
        if config.secondary_objectives:
            summary.pareto_frontier = self._find_pareto_frontier(valid_results)

        # Calculate sensitivity
        summary.parameter_sensitivity = self._analyze_sensitivity(
            valid_results, config.parameter_ranges
        )

        log.info(
            "optimization_completed",
            total=summary.total_combinations,
            completed=summary.completed_combinations,
            best_pnl=(
                float(summary.best_result.objective_value)
                if summary.best_result
                else None
            ),
        )

        return summary

    def cancel(self) -> None:
        """Cancel the optimization run."""
        self._cancelled = True

    def _generate_combinations(self, config: OptimizationConfig) -> list[dict]:
        """Generate all parameter combinations.

        Args:
            config: Optimization configuration.

        Returns:
            List of parameter dictionaries.
        """
        if not config.parameter_ranges:
            return [{}]

        names = [p.name for p in config.parameter_ranges]
        value_lists = [p.values for p in config.parameter_ranges]

        combinations = []
        for values in itertools.product(*value_lists):
            combo = dict(zip(names, values, strict=False))
            combinations.append(combo)

        return combinations

    def _build_params(
        self,
        base_params: dict,
        combination: dict,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestParameters:
        """Build BacktestParameters from combination.

        Args:
            base_params: Base fixed parameters.
            combination: Variable parameters for this run.
            start_date: Backtest start date.
            end_date: Backtest end date.

        Returns:
            Complete BacktestParameters.
        """
        params = {**base_params}

        # Apply combination values
        for key, value in combination.items():
            if "." in key:
                # Nested parameter (e.g., "scoring_weights.wallet_weight")
                parts = key.split(".")
                if parts[0] == "scoring_weights":
                    if "scoring_weights" not in params:
                        params["scoring_weights"] = {}
                    params["scoring_weights"][parts[1]] = Decimal(str(value))
                elif parts[0] == "exit_strategy":
                    if "exit_strategy" not in params:
                        params["exit_strategy"] = {}
                    params["exit_strategy"][parts[1]] = Decimal(str(value))
            else:
                params[key] = (
                    Decimal(str(value)) if isinstance(value, int | float) else value
                )

        # Build scoring weights if provided
        scoring_weights = None
        if "scoring_weights" in params:
            scoring_weights = ScoringWeights(**params.pop("scoring_weights"))

        # Build exit strategy if provided
        exit_strategy = None
        if "exit_strategy" in params:
            exit_strategy = ExitStrategyParams(**params.pop("exit_strategy"))

        return BacktestParameters(
            start_date=start_date,
            end_date=end_date,
            scoring_weights=scoring_weights or ScoringWeights(),
            exit_strategy=exit_strategy or ExitStrategyParams(),
            **params,
        )

    def _get_objective_value(
        self,
        result: BacktestResult,
        objective: OptimizationObjective,
    ) -> Decimal:
        """Extract objective value from result.

        Args:
            result: Backtest result.
            objective: Objective to extract.

        Returns:
            Objective value as Decimal.
        """
        metrics = result.metrics

        objective_map: dict[OptimizationObjective, Decimal] = {
            OptimizationObjective.TOTAL_PNL: metrics.total_pnl,
            OptimizationObjective.WIN_RATE: metrics.win_rate,
            OptimizationObjective.PROFIT_FACTOR: metrics.profit_factor,
            OptimizationObjective.SHARPE_RATIO: metrics.sharpe_ratio or Decimal("0"),
            OptimizationObjective.RISK_ADJUSTED: (
                metrics.total_pnl / metrics.max_drawdown_pct
                if metrics.max_drawdown_pct > 0
                else metrics.total_pnl
            ),
        }

        return objective_map.get(objective, Decimal("0"))

    def _find_pareto_frontier(
        self,
        results: list[OptimizationResult],
    ) -> list[OptimizationResult]:
        """Find Pareto-optimal solutions.

        Args:
            results: All optimization results.

        Returns:
            List of non-dominated results.
        """
        if not results:
            return []

        frontier = []
        for result in results:
            is_dominated = False
            for other in results:
                if other is result:
                    continue

                # Check if other dominates result
                primary_better = other.objective_value > result.objective_value
                all_secondary_better = all(
                    other.secondary_values.get(k, Decimal("0")) >= v
                    for k, v in result.secondary_values.items()
                )
                if primary_better and all_secondary_better:
                    is_dominated = True
                    break

            if not is_dominated:
                frontier.append(result)

        return frontier

    def _analyze_sensitivity(
        self,
        results: list[OptimizationResult],
        parameter_ranges: list[ParameterRange],
    ) -> dict[str, dict]:
        """Analyze parameter sensitivity.

        Args:
            results: Optimization results.
            parameter_ranges: Parameter definitions.

        Returns:
            Sensitivity analysis per parameter.
        """
        sensitivity: dict[str, dict] = {}

        for param in parameter_ranges:
            # Group results by parameter value
            by_value: dict[Any, list[float]] = {}
            for result in results:
                val = result.parameters.get(param.name)
                if val not in by_value:
                    by_value[val] = []
                by_value[val].append(float(result.objective_value))

            # Calculate average objective per value
            averages = {
                str(v): sum(objs) / len(objs) for v, objs in by_value.items() if objs
            }

            # Calculate sensitivity (variance across values)
            if averages:
                avg_values = list(averages.values())
                mean = sum(avg_values) / len(avg_values)
                variance = sum((x - mean) ** 2 for x in avg_values) / len(avg_values)

                sensitivity[param.name] = {
                    "averages_by_value": averages,
                    "best_value": max(averages.keys(), key=lambda k: averages[k]),
                    "sensitivity_score": variance**0.5,
                }

        return sensitivity


def common_parameter_ranges() -> dict[str, list[Any]]:
    """Get common parameter ranges for optimization.

    Returns:
        Dictionary of parameter names to value lists.
    """
    return {
        "score_threshold": [0.60, 0.65, 0.70, 0.75, 0.80, 0.85],
        "base_position_sol": [0.05, 0.10, 0.15, 0.20],
        "exit_strategy.stop_loss_pct": [0.30, 0.40, 0.50, 0.60],
        "max_concurrent_positions": [3, 5, 7, 10],
        "slippage_bps": [50, 100, 150],
    }
