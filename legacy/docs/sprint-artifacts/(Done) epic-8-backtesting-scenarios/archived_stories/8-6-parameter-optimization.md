# Story 8.6: Parameter Optimization (Grid Search)

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: Medium
- **FR**: FR66

## User Story

**As an** operator,
**I want** to automatically search for optimal parameters,
**So that** I can find the best configuration without manual testing.

## Acceptance Criteria

### AC 1: Parameter Range Configuration
**Given** parameter optimization interface
**When** operator configures search
**Then** parameter ranges can be specified:
  - score_threshold: [0.65, 0.70, 0.75, 0.80]
  - stop_loss_pct: [30, 40, 50]
  - position_size_sol: [0.1, 0.2, 0.3]
**And** total combinations are calculated and shown

### AC 2: Grid Search Execution
**Given** grid search is started
**When** optimization runs
**Then** all parameter combinations are tested
**And** progress shows current/total combinations
**And** early results are displayed as they complete

### AC 3: Results Analysis
**Given** optimization completes
**When** results are compiled
**Then** best configuration by target metric is identified
**And** Pareto frontier (multi-objective) is shown
**And** parameter sensitivity analysis is available

### AC 4: Large Search Handling
**Given** large search space
**When** >100 combinations exist
**Then** warning is shown about execution time
**And** sampling option is available (test subset)
**And** smart search option (Bayesian) is available (future)

### AC 5: Apply Results
**Given** optimization result
**When** best params are identified
**Then** one-click apply to live/simulation is available
**And** comparison to current settings is shown
**And** recommendation confidence is indicated

## Technical Specifications

### Optimization Models

**src/walltrack/core/backtest/optimizer.py:**
```python
"""Parameter optimization for backtesting."""

import asyncio
import itertools
from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.parameters import BacktestParameters, ScoringWeights, ExitStrategyParams
from walltrack.core.backtest.results import BacktestResult


class OptimizationObjective(str, Enum):
    """Objective to optimize for."""

    TOTAL_PNL = "total_pnl"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    SHARPE_RATIO = "sharpe_ratio"
    RISK_ADJUSTED = "risk_adjusted"  # PnL / Max Drawdown


class ParameterRange(BaseModel):
    """A parameter to optimize with its range."""

    name: str
    values: list[Any]
    display_name: Optional[str] = None

    @property
    def count(self) -> int:
        """Number of values to test."""
        return len(self.values)


class OptimizationConfig(BaseModel):
    """Configuration for optimization run."""

    # Date range
    start_date: datetime
    end_date: datetime

    # Parameters to optimize
    parameter_ranges: list[ParameterRange]

    # Objective
    objective: OptimizationObjective = OptimizationObjective.TOTAL_PNL
    secondary_objectives: list[OptimizationObjective] = Field(default_factory=list)

    # Execution settings
    max_workers: int = 4
    max_combinations: int = 500  # Limit for safety
    sample_if_exceed: bool = True
    random_seed: int = 42

    # Base parameters (fixed)
    base_params: dict = Field(default_factory=dict)

    @property
    def total_combinations(self) -> int:
        """Calculate total number of combinations."""
        if not self.parameter_ranges:
            return 0
        counts = [p.count for p in self.parameter_ranges]
        result = 1
        for c in counts:
            result *= c
        return result


class OptimizationResult(BaseModel):
    """Result of a single parameter combination."""

    combination_id: int
    parameters: dict

    # Backtest result
    backtest_result: Optional[BacktestResult] = None

    # Primary objective value
    objective_value: Decimal = Decimal("0")
    secondary_values: dict[str, Decimal] = Field(default_factory=dict)

    # Execution
    duration_seconds: float = 0
    error: Optional[str] = None


class OptimizationSummary(BaseModel):
    """Summary of optimization run."""

    id: UUID = Field(default_factory=uuid4)
    config: OptimizationConfig

    # Timing
    started_at: datetime
    completed_at: Optional[datetime] = None
    total_duration_seconds: float = 0

    # Results
    total_combinations: int
    completed_combinations: int = 0
    failed_combinations: int = 0
    results: list[OptimizationResult] = Field(default_factory=list)

    # Best results
    best_result: Optional[OptimizationResult] = None
    best_parameters: dict = Field(default_factory=dict)

    # Pareto frontier (multi-objective)
    pareto_frontier: list[OptimizationResult] = Field(default_factory=list)

    # Sensitivity analysis
    parameter_sensitivity: dict[str, dict] = Field(default_factory=dict)


class GridSearchOptimizer:
    """Grid search optimizer for backtest parameters."""

    def __init__(self, max_workers: int = 4) -> None:
        self._max_workers = max_workers
        self._cancelled = False

    async def optimize(
        self,
        config: OptimizationConfig,
        on_progress: Optional[callable] = None,
    ) -> OptimizationSummary:
        """Run grid search optimization."""
        self._cancelled = False
        started_at = datetime.now(UTC)

        # Generate all combinations
        combinations = self._generate_combinations(config)

        # Apply sampling if needed
        if len(combinations) > config.max_combinations and config.sample_if_exceed:
            import random
            random.seed(config.random_seed)
            combinations = random.sample(combinations, config.max_combinations)

        summary = OptimizationSummary(
            config=config,
            started_at=started_at,
            total_combinations=len(combinations),
        )

        # Run backtests
        semaphore = asyncio.Semaphore(config.max_workers)
        results = []

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
                    obj_value = self._get_objective_value(
                        bt_result, config.objective
                    )

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
        tasks = [
            run_combination(i, combo)
            for i, combo in enumerate(combinations)
        ]

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

        return summary

    def cancel(self) -> None:
        """Cancel the optimization run."""
        self._cancelled = True

    def _generate_combinations(
        self,
        config: OptimizationConfig,
    ) -> list[dict]:
        """Generate all parameter combinations."""
        if not config.parameter_ranges:
            return [{}]

        names = [p.name for p in config.parameter_ranges]
        value_lists = [p.values for p in config.parameter_ranges]

        combinations = []
        for values in itertools.product(*value_lists):
            combo = dict(zip(names, values))
            combinations.append(combo)

        return combinations

    def _build_params(
        self,
        base_params: dict,
        combination: dict,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestParameters:
        """Build BacktestParameters from combination."""
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
                params[key] = Decimal(str(value)) if isinstance(value, (int, float)) else value

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
        """Extract objective value from result."""
        metrics = result.metrics

        if objective == OptimizationObjective.TOTAL_PNL:
            return metrics.total_pnl
        elif objective == OptimizationObjective.WIN_RATE:
            return metrics.win_rate
        elif objective == OptimizationObjective.PROFIT_FACTOR:
            return metrics.profit_factor
        elif objective == OptimizationObjective.SHARPE_RATIO:
            return metrics.sharpe_ratio or Decimal("0")
        elif objective == OptimizationObjective.RISK_ADJUSTED:
            if metrics.max_drawdown_pct > 0:
                return metrics.total_pnl / metrics.max_drawdown_pct
            return metrics.total_pnl
        return Decimal("0")

    def _find_pareto_frontier(
        self,
        results: list[OptimizationResult],
    ) -> list[OptimizationResult]:
        """Find Pareto-optimal solutions for multi-objective optimization."""
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
        """Analyze parameter sensitivity."""
        sensitivity = {}

        for param in parameter_ranges:
            # Group results by parameter value
            by_value = {}
            for result in results:
                val = result.parameters.get(param.name)
                if val not in by_value:
                    by_value[val] = []
                by_value[val].append(float(result.objective_value))

            # Calculate average objective per value
            averages = {
                str(v): sum(objs) / len(objs)
                for v, objs in by_value.items()
                if objs
            }

            # Calculate sensitivity (variance across values)
            if averages:
                avg_values = list(averages.values())
                mean = sum(avg_values) / len(avg_values)
                variance = sum((x - mean) ** 2 for x in avg_values) / len(avg_values)

                sensitivity[param.name] = {
                    "averages_by_value": averages,
                    "best_value": max(averages.keys(), key=lambda k: averages[k]),
                    "sensitivity_score": variance ** 0.5,  # Standard deviation
                }

        return sensitivity


# Helper function to create common parameter ranges
def common_parameter_ranges() -> dict[str, list[Any]]:
    """Get common parameter ranges for optimization."""
    return {
        "score_threshold": [0.60, 0.65, 0.70, 0.75, 0.80, 0.85],
        "base_position_sol": [0.05, 0.10, 0.15, 0.20],
        "exit_strategy.stop_loss_pct": [0.30, 0.40, 0.50, 0.60],
        "max_concurrent_positions": [3, 5, 7, 10],
        "slippage_bps": [50, 100, 150],
    }
```

## Usage Example

```python
from walltrack.core.backtest.optimizer import (
    GridSearchOptimizer,
    OptimizationConfig,
    OptimizationObjective,
    ParameterRange,
)

# Define parameter ranges
config = OptimizationConfig(
    start_date=datetime(2024, 1, 1),
    end_date=datetime(2024, 6, 30),
    parameter_ranges=[
        ParameterRange(
            name="score_threshold",
            values=[0.65, 0.70, 0.75, 0.80],
        ),
        ParameterRange(
            name="base_position_sol",
            values=[0.1, 0.15, 0.2],
        ),
        ParameterRange(
            name="exit_strategy.stop_loss_pct",
            values=[0.30, 0.40, 0.50],
        ),
    ],
    objective=OptimizationObjective.TOTAL_PNL,
    secondary_objectives=[OptimizationObjective.WIN_RATE],
    max_workers=4,
)

# Total combinations: 4 * 3 * 3 = 36

optimizer = GridSearchOptimizer()
summary = await optimizer.optimize(
    config,
    on_progress=lambda done, total: print(f"{done}/{total}"),
)

print(f"Best parameters: {summary.best_parameters}")
print(f"Best P&L: {summary.best_result.objective_value}")
```

## Implementation Tasks

- [ ] Create optimization models
- [ ] Implement GridSearchOptimizer
- [ ] Implement parameter combination generation
- [ ] Implement parallel execution
- [ ] Implement Pareto frontier calculation
- [ ] Implement sensitivity analysis
- [ ] Add cancellation support
- [ ] Write unit tests

## Definition of Done

- [x] Grid search tests all combinations
- [x] Progress reporting works
- [x] Best parameters are identified
- [x] Pareto frontier is calculated (multi-objective)
- [x] Sensitivity analysis provides insights
- [x] Large search spaces are handled
- [x] Tests cover optimization scenarios

---

## Dev Agent Record

### Implementation Summary
- **Status**: Complete
- **Tests**: 13 passing
- **Linting**: Clean
- **Dependencies Added**: pytest-mock

### Files Created
- `src/walltrack/core/backtest/optimizer.py` - GridSearchOptimizer and models
- `tests/unit/core/backtest/test_optimizer.py` - 13 tests

### Key Components
- `OptimizationObjective` - Enum for optimization targets (total_pnl, win_rate, profit_factor, risk_adjusted)
- `ParameterRange` - Defines parameter values to test
- `OptimizationConfig` - Configuration for optimization run (date range, parameters, objectives, workers)
- `OptimizationResult` - Result of a single parameter combination
- `OptimizationSummary` - Complete optimization results with best parameters, Pareto frontier, sensitivity
- `GridSearchOptimizer` - Main optimizer class with async execution
- `common_parameter_ranges()` - Helper with common parameter configurations

### Key Features
- Parallel execution with semaphore-based concurrency control
- Sampling for large search spaces (>max_combinations)
- Pareto frontier for multi-objective optimization
- Sensitivity analysis per parameter
- Cancellation support
- Progress callbacks

### Linting Fixes
- Import order (structlog at top)
- Top-level import for random
- Refactored _get_objective_value to use dictionary mapping (PLR0911)
