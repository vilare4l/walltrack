"""Scenario comparison models."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from walltrack.core.backtest.results import BacktestMetrics


class MetricRanking(str, Enum):
    """How to rank a metric for comparison."""

    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"


class ComparisonMetric(BaseModel):
    """A single metric comparison across scenarios.

    Tracks values, rankings, and best/worst performers for one metric.
    """

    name: str
    display_name: str
    ranking: MetricRanking

    # Values per scenario
    values: dict[str, Decimal] = Field(default_factory=dict)

    # Best/worst analysis
    best_scenario: str = ""
    best_value: Decimal = Decimal("0")
    worst_scenario: str = ""
    worst_value: Decimal = Decimal("0")

    # Rankings (1 = best)
    rankings: dict[str, int] = Field(default_factory=dict)


class ScenarioSummary(BaseModel):
    """Summary of a scenario for comparison.

    Contains key metrics and ranking information.
    """

    scenario_id: UUID
    scenario_name: str
    metrics: BacktestMetrics

    # Overall ranking (1 = best)
    overall_rank: int = 0
    weighted_score: Decimal = Decimal("0")


class ScenarioComparison(BaseModel):
    """Complete comparison of multiple scenarios.

    Contains all scenarios, metric comparisons, and rankings.
    """

    batch_id: UUID = Field(default_factory=uuid4)
    compared_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Scenarios being compared
    scenarios: list[ScenarioSummary] = Field(default_factory=list)

    # Per-metric comparisons
    metric_comparisons: list[ComparisonMetric] = Field(default_factory=list)

    # Overall best
    best_scenario_id: UUID | None = None
    best_scenario_name: str = ""

    # Weights for ranking
    ranking_weights: dict[str, Decimal] = Field(
        default_factory=lambda: {
            "total_pnl": Decimal("0.30"),
            "win_rate": Decimal("0.20"),
            "profit_factor": Decimal("0.20"),
            "max_drawdown_pct": Decimal("0.15"),
            "total_trades": Decimal("0.15"),
        }
    )


class DivergencePoint(BaseModel):
    """A point where two scenarios diverged.

    Captures when different scenarios made different decisions.
    """

    timestamp: datetime
    signal_id: UUID
    token_address: str

    # Decision per scenario
    decisions: dict[str, str] = Field(default_factory=dict)

    # Scores that led to decisions
    scores: dict[str, Decimal] = Field(default_factory=dict)

    # Outcomes (PnL) for scenarios that traded
    outcomes: dict[str, Decimal] = Field(default_factory=dict)


class DetailedComparison(BaseModel):
    """Detailed comparison between two scenarios.

    Provides in-depth analysis of differences.
    """

    scenario_a: str
    scenario_b: str

    # Trade overlap
    trades_only_a: int = 0
    trades_only_b: int = 0
    trades_both: int = 0

    # Divergence points
    divergence_points: list[DivergencePoint] = Field(default_factory=list)

    # PnL analysis
    pnl_difference: Decimal = Decimal("0")
    pnl_difference_significant: bool = False
