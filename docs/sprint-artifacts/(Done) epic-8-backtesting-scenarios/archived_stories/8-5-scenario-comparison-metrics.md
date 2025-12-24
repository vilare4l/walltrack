# Story 8.5: Scenario Comparison & Metrics

## Story Info
- **Epic**: Epic 8 - Backtesting & Scenario Analysis
- **Status**: ready
- **Priority**: Medium
- **FR**: FR65

## User Story

**As an** operator,
**I want** to compare results across multiple scenarios,
**So that** I can identify the best performing configuration.

## Acceptance Criteria

### AC 1: Side-by-Side Comparison
**Given** multiple backtest results exist
**When** comparison view is opened
**Then** key metrics are shown side-by-side:
  - Total P&L
  - Win rate
  - Total trades
  - Max drawdown
  - Profit factor
  - Sharpe ratio

### AC 2: Ranking
**Given** comparison table
**When** metrics are displayed
**Then** best value per metric is highlighted
**And** ranking by each metric is available
**And** overall ranking (weighted) is calculated

### AC 3: Detailed Comparison
**Given** detailed comparison
**When** operator drills down
**Then** trade-by-trade differences are shown
**And** divergence points are identified (where scenarios differ)
**And** statistical significance is indicated

### AC 4: Apply Winner
**Given** comparison results
**When** operator selects winner
**Then** winning scenario parameters can be applied to live
**And** confirmation shows all changes
**And** audit log records parameter change source

## Technical Specifications

### Comparison Models

**src/walltrack/core/backtest/comparison.py:**
```python
"""Scenario comparison utilities."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from walltrack.core.backtest.results import BacktestResult, BacktestMetrics


class MetricRanking(str, Enum):
    """How to rank a metric (higher or lower is better)."""

    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"


class ComparisonMetric(BaseModel):
    """A single metric comparison across scenarios."""

    name: str
    display_name: str
    ranking: MetricRanking

    # Values per scenario
    values: dict[str, Decimal]  # scenario_name -> value

    # Rankings
    best_scenario: str
    best_value: Decimal
    worst_scenario: str
    worst_value: Decimal
    rankings: dict[str, int]  # scenario_name -> rank (1 = best)


class ScenarioSummary(BaseModel):
    """Summary of a single scenario's performance."""

    scenario_id: UUID
    scenario_name: str
    metrics: BacktestMetrics

    # Rankings across metrics
    overall_rank: int = 0
    rank_by_pnl: int = 0
    rank_by_win_rate: int = 0
    rank_by_drawdown: int = 0
    rank_by_profit_factor: int = 0

    # Score
    weighted_score: Decimal = Decimal("0")


class ScenarioComparison(BaseModel):
    """Complete comparison of multiple scenarios."""

    batch_id: UUID
    compared_at: datetime

    # Scenarios
    scenarios: list[ScenarioSummary]

    # Metric comparisons
    metric_comparisons: list[ComparisonMetric]

    # Best overall
    best_scenario_id: UUID
    best_scenario_name: str

    # Configuration weights for overall ranking
    ranking_weights: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "total_pnl": Decimal("0.30"),
            "win_rate": Decimal("0.20"),
            "profit_factor": Decimal("0.20"),
            "max_drawdown": Decimal("0.15"),
            "sharpe_ratio": Decimal("0.15"),
        }
    )


class DivergencePoint(BaseModel):
    """A point where scenarios made different decisions."""

    timestamp: datetime
    signal_id: UUID
    token_address: str

    # Decisions by scenario
    decisions: dict[str, str]  # scenario_name -> "traded" | "skipped"

    # Scores by scenario
    scores: dict[str, Decimal]

    # Outcomes (if traded)
    outcomes: dict[str, Decimal]  # scenario_name -> pnl


class DetailedComparison(BaseModel):
    """Detailed trade-by-trade comparison."""

    scenario_a: str
    scenario_b: str

    # Summary
    trades_only_a: int  # Trades that only A made
    trades_only_b: int  # Trades that only B made
    trades_both: int    # Trades both made

    # Divergence analysis
    divergence_points: list[DivergencePoint]

    # Statistical significance
    pnl_difference: Decimal
    pnl_difference_significant: bool
    confidence_level: Decimal = Decimal("0.95")
```

### Comparison Service

**src/walltrack/core/backtest/comparison_service.py:**
```python
"""Service for comparing backtest scenarios."""

from datetime import datetime, UTC
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog

from walltrack.core.backtest.batch import BatchRun
from walltrack.core.backtest.comparison import (
    ScenarioComparison,
    ScenarioSummary,
    ComparisonMetric,
    MetricRanking,
    DetailedComparison,
    DivergencePoint,
)
from walltrack.core.backtest.results import BacktestResult

log = structlog.get_logger()


METRIC_DEFINITIONS = [
    ("total_pnl", "Total P&L", MetricRanking.HIGHER_BETTER),
    ("win_rate", "Win Rate", MetricRanking.HIGHER_BETTER),
    ("total_trades", "Total Trades", MetricRanking.HIGHER_BETTER),
    ("profit_factor", "Profit Factor", MetricRanking.HIGHER_BETTER),
    ("max_drawdown_pct", "Max Drawdown %", MetricRanking.LOWER_BETTER),
    ("average_win", "Avg Win", MetricRanking.HIGHER_BETTER),
    ("average_loss", "Avg Loss", MetricRanking.LOWER_BETTER),  # Less negative = better
    ("sharpe_ratio", "Sharpe Ratio", MetricRanking.HIGHER_BETTER),
]


class ComparisonService:
    """Service for comparing backtest results."""

    def compare_scenarios(
        self,
        results: list[BacktestResult],
        ranking_weights: Optional[dict[str, Decimal]] = None,
    ) -> ScenarioComparison:
        """Compare multiple backtest results."""
        if len(results) < 2:
            raise ValueError("Need at least 2 results to compare")

        # Build scenario summaries
        summaries = [
            ScenarioSummary(
                scenario_id=r.id,
                scenario_name=r.name,
                metrics=r.metrics,
            )
            for r in results
        ]

        # Build metric comparisons
        metric_comparisons = []
        for metric_name, display_name, ranking in METRIC_DEFINITIONS:
            values = {}
            for summary in summaries:
                value = getattr(summary.metrics, metric_name, None)
                if value is not None:
                    values[summary.scenario_name] = Decimal(str(value))

            if values:
                comparison = self._build_metric_comparison(
                    metric_name, display_name, ranking, values
                )
                metric_comparisons.append(comparison)

                # Apply rankings to summaries
                for summary in summaries:
                    rank = comparison.rankings.get(summary.scenario_name, 0)
                    if metric_name == "total_pnl":
                        summary.rank_by_pnl = rank
                    elif metric_name == "win_rate":
                        summary.rank_by_win_rate = rank
                    elif metric_name == "max_drawdown_pct":
                        summary.rank_by_drawdown = rank
                    elif metric_name == "profit_factor":
                        summary.rank_by_profit_factor = rank

        # Calculate overall scores and rankings
        weights = ranking_weights or {
            "total_pnl": Decimal("0.30"),
            "win_rate": Decimal("0.20"),
            "profit_factor": Decimal("0.20"),
            "max_drawdown_pct": Decimal("0.15"),
            "sharpe_ratio": Decimal("0.15"),
        }

        self._calculate_overall_scores(summaries, metric_comparisons, weights)

        # Sort by overall rank
        summaries.sort(key=lambda s: s.overall_rank)

        best = summaries[0]

        return ScenarioComparison(
            batch_id=results[0].id,  # Use first result's ID as reference
            compared_at=datetime.now(UTC),
            scenarios=summaries,
            metric_comparisons=metric_comparisons,
            best_scenario_id=best.scenario_id,
            best_scenario_name=best.scenario_name,
            ranking_weights=weights,
        )

    def _build_metric_comparison(
        self,
        name: str,
        display_name: str,
        ranking: MetricRanking,
        values: dict[str, Decimal],
    ) -> ComparisonMetric:
        """Build a metric comparison."""
        # Sort by value
        sorted_scenarios = sorted(
            values.items(),
            key=lambda x: x[1],
            reverse=(ranking == MetricRanking.HIGHER_BETTER),
        )

        # Build rankings
        rankings = {name: i + 1 for i, (name, _) in enumerate(sorted_scenarios)}

        best_name, best_val = sorted_scenarios[0]
        worst_name, worst_val = sorted_scenarios[-1]

        return ComparisonMetric(
            name=name,
            display_name=display_name,
            ranking=ranking,
            values=values,
            best_scenario=best_name,
            best_value=best_val,
            worst_scenario=worst_name,
            worst_value=worst_val,
            rankings=rankings,
        )

    def _calculate_overall_scores(
        self,
        summaries: list[ScenarioSummary],
        metrics: list[ComparisonMetric],
        weights: dict[str, Decimal],
    ) -> None:
        """Calculate weighted overall scores."""
        n_scenarios = len(summaries)

        for summary in summaries:
            score = Decimal("0")

            for metric in metrics:
                weight = weights.get(metric.name, Decimal("0"))
                rank = metric.rankings.get(summary.scenario_name, n_scenarios)

                # Convert rank to score (1st = 1.0, last = 0.0)
                rank_score = Decimal(str((n_scenarios - rank) / (n_scenarios - 1))) if n_scenarios > 1 else Decimal("1")
                score += weight * rank_score

            summary.weighted_score = score

        # Assign overall ranks based on score
        sorted_summaries = sorted(summaries, key=lambda s: s.weighted_score, reverse=True)
        for i, summary in enumerate(sorted_summaries):
            summary.overall_rank = i + 1

    def compare_pair_detailed(
        self,
        result_a: BacktestResult,
        result_b: BacktestResult,
    ) -> DetailedComparison:
        """Detailed comparison of two scenarios."""
        # Build trade sets by signal ID
        trades_a = {str(t.signal_id): t for t in result_a.trades}
        trades_b = {str(t.signal_id): t for t in result_b.trades}

        signals_a = set(trades_a.keys())
        signals_b = set(trades_b.keys())

        trades_only_a = len(signals_a - signals_b)
        trades_only_b = len(signals_b - signals_a)
        trades_both = len(signals_a & signals_b)

        # Find divergence points
        divergences = []

        # Signals A traded but B didn't
        for signal_id in signals_a - signals_b:
            trade = trades_a[signal_id]
            divergences.append(
                DivergencePoint(
                    timestamp=trade.entry_time,
                    signal_id=UUID(signal_id),
                    token_address=trade.token_address,
                    decisions={
                        result_a.name: "traded",
                        result_b.name: "skipped",
                    },
                    scores={},  # Would need signal data
                    outcomes={
                        result_a.name: trade.realized_pnl or Decimal("0"),
                    },
                )
            )

        # Signals B traded but A didn't
        for signal_id in signals_b - signals_a:
            trade = trades_b[signal_id]
            divergences.append(
                DivergencePoint(
                    timestamp=trade.entry_time,
                    signal_id=UUID(signal_id),
                    token_address=trade.token_address,
                    decisions={
                        result_a.name: "skipped",
                        result_b.name: "traded",
                    },
                    scores={},
                    outcomes={
                        result_b.name: trade.realized_pnl or Decimal("0"),
                    },
                )
            )

        # Sort by timestamp
        divergences.sort(key=lambda d: d.timestamp)

        # Calculate PnL difference and significance
        pnl_a = result_a.metrics.total_pnl
        pnl_b = result_b.metrics.total_pnl
        pnl_diff = pnl_a - pnl_b

        # Simple significance test (would use proper stats in production)
        significant = abs(pnl_diff) > (abs(pnl_a) + abs(pnl_b)) * Decimal("0.1")

        return DetailedComparison(
            scenario_a=result_a.name,
            scenario_b=result_b.name,
            trades_only_a=trades_only_a,
            trades_only_b=trades_only_b,
            trades_both=trades_both,
            divergence_points=divergences[:50],  # Limit to top 50
            pnl_difference=pnl_diff,
            pnl_difference_significant=significant,
        )

    def export_comparison_csv(
        self,
        comparison: ScenarioComparison,
    ) -> str:
        """Export comparison as CSV."""
        lines = []

        # Header
        header = ["Metric"] + [s.scenario_name for s in comparison.scenarios]
        lines.append(",".join(header))

        # Metrics
        for metric in comparison.metric_comparisons:
            row = [metric.display_name]
            for scenario in comparison.scenarios:
                val = metric.values.get(scenario.scenario_name, Decimal("0"))
                row.append(str(float(val)))
            lines.append(",".join(row))

        # Rankings
        lines.append("")
        lines.append(",".join(["Overall Rank"] + [str(s.overall_rank) for s in comparison.scenarios]))
        lines.append(",".join(["Weighted Score"] + [str(float(s.weighted_score)) for s in comparison.scenarios]))

        return "\n".join(lines)


# Singleton
_comparison_service: Optional[ComparisonService] = None


def get_comparison_service() -> ComparisonService:
    """Get comparison service singleton."""
    global _comparison_service
    if _comparison_service is None:
        _comparison_service = ComparisonService()
    return _comparison_service
```

## Implementation Tasks

- [ ] Create comparison models (ComparisonMetric, ScenarioSummary, etc.)
- [ ] Implement ComparisonService.compare_scenarios()
- [ ] Implement ranking calculations
- [ ] Implement detailed pair comparison
- [ ] Add statistical significance testing
- [ ] Implement CSV export
- [ ] Write unit tests

## Definition of Done

- [x] Side-by-side metrics display correctly
- [x] Rankings are calculated accurately
- [x] Best/worst scenarios are identified
- [x] Divergence points are found
- [x] CSV export works
- [x] Tests cover comparison logic

---

## Dev Agent Record

### Implementation Summary
- **Status**: Complete
- **Tests**: 13 passing (7 model tests, 6 service tests)
- **Linting**: Clean

### Files Created
- `src/walltrack/core/backtest/comparison.py` - Comparison models (MetricRanking, ComparisonMetric, ScenarioSummary, ScenarioComparison, DivergencePoint, DetailedComparison)
- `src/walltrack/core/backtest/comparison_service.py` - ComparisonService with compare_scenarios(), compare_pair_detailed(), export_comparison_csv()
- `tests/unit/core/backtest/test_comparison.py` - Model tests (6 tests)
- `tests/unit/core/backtest/test_comparison_service.py` - Service tests (7 tests)

### Key Decisions
- Simplified comparison approach compared to spec - direct metric extraction vs summary-based
- Overall ranking uses weighted scores across 5 metrics (pnl, win_rate, profit_factor, drawdown, trades)
- Divergence points capture trade decisions that differed between scenarios
- CSV export includes metrics and rankings

### Test Coverage
- MetricRanking enum values
- ComparisonMetric creation and rankings
- ScenarioSummary with BacktestMetrics
- ScenarioComparison with default ranking weights
- DivergencePoint with decisions/outcomes
- DetailedComparison with trade overlap
- ComparisonService.compare_scenarios() with multiple results
- Minimum 2 results validation
- Ranking calculations (best scenario identification)
- Overall rank assignment
- Detailed comparison trade counting
- CSV export format
- Singleton pattern
