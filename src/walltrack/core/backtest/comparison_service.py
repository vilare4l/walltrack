"""Scenario comparison service."""

from datetime import UTC, datetime
from decimal import Decimal

import structlog

from walltrack.core.backtest.comparison import (
    ComparisonMetric,
    DetailedComparison,
    DivergencePoint,
    MetricRanking,
    ScenarioComparison,
    ScenarioSummary,
)
from walltrack.core.backtest.results import BacktestResult

log = structlog.get_logger()

# Metric definitions for comparison
METRIC_DEFINITIONS: list[tuple[str, str, MetricRanking]] = [
    ("total_pnl", "Total P&L", MetricRanking.HIGHER_BETTER),
    ("win_rate", "Win Rate", MetricRanking.HIGHER_BETTER),
    ("profit_factor", "Profit Factor", MetricRanking.HIGHER_BETTER),
    ("max_drawdown_pct", "Max Drawdown %", MetricRanking.LOWER_BETTER),
    ("total_trades", "Total Trades", MetricRanking.HIGHER_BETTER),
]


class ComparisonService:
    """Service for comparing backtest scenarios.

    Provides methods to compare multiple scenarios, rank them,
    and identify divergence points.
    """

    def compare_scenarios(
        self,
        results: list[BacktestResult],
    ) -> ScenarioComparison:
        """Compare multiple scenario results.

        Args:
            results: List of backtest results to compare.

        Returns:
            ScenarioComparison with rankings and analysis.

        Raises:
            ValueError: If fewer than 2 results provided.
        """
        if len(results) < 2:
            raise ValueError("Comparison requires at least 2 results")

        comparison = ScenarioComparison(compared_at=datetime.now(UTC))

        # Create summaries
        for result in results:
            summary = ScenarioSummary(
                scenario_id=result.id,
                scenario_name=result.name,
                metrics=result.metrics,
            )
            comparison.scenarios.append(summary)

        # Compare each metric
        for name, display_name, ranking in METRIC_DEFINITIONS:
            metric = self._compare_metric(name, display_name, ranking, results)
            comparison.metric_comparisons.append(metric)

        # Calculate overall rankings
        self._calculate_overall_rankings(comparison)

        # Set best scenario
        best_summary = min(comparison.scenarios, key=lambda s: s.overall_rank)
        comparison.best_scenario_id = best_summary.scenario_id
        comparison.best_scenario_name = best_summary.scenario_name

        log.info(
            "scenarios_compared",
            count=len(results),
            best=comparison.best_scenario_name,
        )

        return comparison

    def _compare_metric(
        self,
        name: str,
        display_name: str,
        ranking: MetricRanking,
        results: list[BacktestResult],
    ) -> ComparisonMetric:
        """Compare a single metric across results.

        Args:
            name: Metric field name.
            display_name: Human-readable name.
            ranking: How to rank the metric.
            results: Results to compare.

        Returns:
            ComparisonMetric with values and rankings.
        """
        metric = ComparisonMetric(
            name=name,
            display_name=display_name,
            ranking=ranking,
        )

        # Extract values
        for result in results:
            value = getattr(result.metrics, name, Decimal("0"))
            if value is None:
                value = Decimal("0")
            metric.values[result.name] = value

        # Sort for ranking
        sorted_scenarios = sorted(
            metric.values.items(),
            key=lambda x: x[1],
            reverse=(ranking == MetricRanking.HIGHER_BETTER),
        )

        # Assign rankings
        for rank, (scenario_name, value) in enumerate(sorted_scenarios, 1):
            metric.rankings[scenario_name] = rank
            if rank == 1:
                metric.best_scenario = scenario_name
                metric.best_value = value
            if rank == len(sorted_scenarios):
                metric.worst_scenario = scenario_name
                metric.worst_value = value

        return metric

    def _calculate_overall_rankings(self, comparison: ScenarioComparison) -> None:
        """Calculate overall rankings based on weighted scores.

        Args:
            comparison: Comparison to update with rankings.
        """
        # Calculate weighted scores
        for summary in comparison.scenarios:
            weighted_score = Decimal("0")
            for metric in comparison.metric_comparisons:
                weight = comparison.ranking_weights.get(metric.name, Decimal("0"))
                rank = metric.rankings.get(summary.scenario_name, len(comparison.scenarios))
                # Lower rank = better, so invert for scoring
                max_rank = len(comparison.scenarios)
                score = Decimal(max_rank - rank + 1) / Decimal(max_rank)
                weighted_score += weight * score
            summary.weighted_score = weighted_score

        # Sort by weighted score (higher = better)
        sorted_summaries = sorted(
            comparison.scenarios,
            key=lambda s: s.weighted_score,
            reverse=True,
        )

        # Assign overall ranks
        for rank, summary in enumerate(sorted_summaries, 1):
            summary.overall_rank = rank

    def compare_pair_detailed(
        self,
        result_a: BacktestResult,
        result_b: BacktestResult,
    ) -> DetailedComparison:
        """Create detailed comparison between two scenarios.

        Args:
            result_a: First scenario result.
            result_b: Second scenario result.

        Returns:
            DetailedComparison with trade overlap and divergences.
        """
        detailed = DetailedComparison(
            scenario_a=result_a.name,
            scenario_b=result_b.name,
        )

        # Get signal IDs for each scenario
        signals_a = {t.signal_id for t in result_a.trades}
        signals_b = {t.signal_id for t in result_b.trades}

        # Calculate trade overlap
        detailed.trades_only_a = len(signals_a - signals_b)
        detailed.trades_only_b = len(signals_b - signals_a)
        detailed.trades_both = len(signals_a & signals_b)

        # Find divergence points
        all_signals = signals_a | signals_b
        for signal_id in all_signals:
            trade_a = next((t for t in result_a.trades if t.signal_id == signal_id), None)
            trade_b = next((t for t in result_b.trades if t.signal_id == signal_id), None)

            if (trade_a is None) != (trade_b is None):
                # One traded, one didn't - divergence
                divergence = DivergencePoint(
                    timestamp=trade_a.entry_time if trade_a else trade_b.entry_time,
                    signal_id=signal_id,
                    token_address=trade_a.token_address if trade_a else trade_b.token_address,
                    decisions={
                        result_a.name: "traded" if trade_a else "skipped",
                        result_b.name: "traded" if trade_b else "skipped",
                    },
                    outcomes={},
                )

                if trade_a and trade_a.realized_pnl:
                    divergence.outcomes[result_a.name] = trade_a.realized_pnl
                if trade_b and trade_b.realized_pnl:
                    divergence.outcomes[result_b.name] = trade_b.realized_pnl

                detailed.divergence_points.append(divergence)

        # PnL analysis
        pnl_a = result_a.metrics.total_pnl
        pnl_b = result_b.metrics.total_pnl
        detailed.pnl_difference = abs(pnl_a - pnl_b)
        # Significant if difference is > 10% of average
        avg_pnl = (abs(pnl_a) + abs(pnl_b)) / 2
        if avg_pnl > 0:
            detailed.pnl_difference_significant = (
                detailed.pnl_difference / avg_pnl > Decimal("0.10")
            )

        log.info(
            "detailed_comparison_created",
            scenario_a=result_a.name,
            scenario_b=result_b.name,
            divergences=len(detailed.divergence_points),
        )

        return detailed

    def export_comparison_csv(self, comparison: ScenarioComparison) -> str:
        """Export comparison as CSV string.

        Args:
            comparison: Comparison to export.

        Returns:
            CSV formatted string.
        """
        lines = []

        # Header
        scenario_names = [s.scenario_name for s in comparison.scenarios]
        header = ["Metric", *scenario_names]
        lines.append(",".join(header))

        # Metric rows
        for metric in comparison.metric_comparisons:
            row = [metric.display_name]
            for name in scenario_names:
                value = metric.values.get(name, Decimal("0"))
                row.append(str(value))
            lines.append(",".join(row))

        # Overall rank row
        rank_row = ["Overall Rank"]
        for name in scenario_names:
            summary = next((s for s in comparison.scenarios if s.scenario_name == name), None)
            rank_row.append(str(summary.overall_rank) if summary else "-")
        lines.append(",".join(rank_row))

        return "\n".join(lines)


# Singleton
_comparison_service: ComparisonService | None = None


def get_comparison_service() -> ComparisonService:
    """Get comparison service singleton.

    Returns:
        ComparisonService singleton instance.
    """
    global _comparison_service
    if _comparison_service is None:
        _comparison_service = ComparisonService()
    return _comparison_service
