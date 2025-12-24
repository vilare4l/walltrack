"""Tests for scenario comparison models."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestMetricRanking:
    """Tests for MetricRanking enum."""

    def test_ranking_values(self) -> None:
        """Test ranking enum values."""
        from walltrack.core.backtest.comparison import MetricRanking

        assert MetricRanking.HIGHER_BETTER.value == "higher_better"
        assert MetricRanking.LOWER_BETTER.value == "lower_better"


class TestComparisonMetric:
    """Tests for ComparisonMetric model."""

    def test_comparison_metric_creation(self) -> None:
        """Test creating a comparison metric."""
        from walltrack.core.backtest.comparison import ComparisonMetric, MetricRanking

        metric = ComparisonMetric(
            name="total_pnl",
            display_name="Total P&L",
            ranking=MetricRanking.HIGHER_BETTER,
            values={"A": Decimal("100"), "B": Decimal("50")},
            best_scenario="A",
            best_value=Decimal("100"),
            worst_scenario="B",
            worst_value=Decimal("50"),
            rankings={"A": 1, "B": 2},
        )

        assert metric.name == "total_pnl"
        assert metric.best_scenario == "A"
        assert metric.rankings["A"] == 1


class TestScenarioSummary:
    """Tests for ScenarioSummary model."""

    def test_summary_creation(self) -> None:
        """Test creating a scenario summary."""
        from walltrack.core.backtest.comparison import ScenarioSummary
        from walltrack.core.backtest.results import BacktestMetrics

        summary = ScenarioSummary(
            scenario_id=uuid4(),
            scenario_name="Test Scenario",
            metrics=BacktestMetrics(total_pnl=Decimal("100")),
        )

        assert summary.scenario_name == "Test Scenario"
        assert summary.overall_rank == 0
        assert summary.weighted_score == Decimal("0")


class TestScenarioComparison:
    """Tests for ScenarioComparison model."""

    def test_comparison_creation(self) -> None:
        """Test creating a scenario comparison."""
        from walltrack.core.backtest.comparison import (
            ScenarioComparison,
            ScenarioSummary,
        )
        from walltrack.core.backtest.results import BacktestMetrics

        comparison = ScenarioComparison(
            batch_id=uuid4(),
            compared_at=datetime.now(UTC),
            scenarios=[
                ScenarioSummary(
                    scenario_id=uuid4(),
                    scenario_name="A",
                    metrics=BacktestMetrics(),
                ),
                ScenarioSummary(
                    scenario_id=uuid4(),
                    scenario_name="B",
                    metrics=BacktestMetrics(),
                ),
            ],
            metric_comparisons=[],
            best_scenario_id=uuid4(),
            best_scenario_name="A",
        )

        assert len(comparison.scenarios) == 2
        assert comparison.best_scenario_name == "A"
        assert "total_pnl" in comparison.ranking_weights


class TestDivergencePoint:
    """Tests for DivergencePoint model."""

    def test_divergence_point_creation(self) -> None:
        """Test creating a divergence point."""
        from walltrack.core.backtest.comparison import DivergencePoint

        divergence = DivergencePoint(
            timestamp=datetime.now(UTC),
            signal_id=uuid4(),
            token_address="Token123",
            decisions={"A": "traded", "B": "skipped"},
            scores={"A": Decimal("0.85"), "B": Decimal("0.65")},
            outcomes={"A": Decimal("50")},
        )

        assert divergence.decisions["A"] == "traded"
        assert divergence.decisions["B"] == "skipped"


class TestDetailedComparison:
    """Tests for DetailedComparison model."""

    def test_detailed_comparison_creation(self) -> None:
        """Test creating a detailed comparison."""
        from walltrack.core.backtest.comparison import DetailedComparison

        detailed = DetailedComparison(
            scenario_a="Scenario A",
            scenario_b="Scenario B",
            trades_only_a=5,
            trades_only_b=3,
            trades_both=10,
            divergence_points=[],
            pnl_difference=Decimal("100"),
            pnl_difference_significant=True,
        )

        assert detailed.trades_only_a == 5
        assert detailed.trades_both == 10
        assert detailed.pnl_difference_significant is True
