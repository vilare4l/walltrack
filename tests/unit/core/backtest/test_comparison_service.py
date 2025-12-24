"""Tests for comparison service."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestComparisonService:
    """Tests for ComparisonService class."""

    @pytest.fixture
    def sample_results(self) -> list:
        """Create sample backtest results for comparison."""
        from walltrack.core.backtest.results import BacktestMetrics, BacktestResult

        now = datetime.now(UTC)

        return [
            BacktestResult(
                id=uuid4(),
                name="Conservative",
                parameters={},
                started_at=now,
                completed_at=now,
                duration_seconds=1.0,
                trades=[],
                metrics=BacktestMetrics(
                    total_pnl=Decimal("50"),
                    win_rate=Decimal("0.70"),
                    total_trades=10,
                    profit_factor=Decimal("1.5"),
                    max_drawdown_pct=Decimal("10"),
                ),
            ),
            BacktestResult(
                id=uuid4(),
                name="Aggressive",
                parameters={},
                started_at=now,
                completed_at=now,
                duration_seconds=1.0,
                trades=[],
                metrics=BacktestMetrics(
                    total_pnl=Decimal("150"),
                    win_rate=Decimal("0.50"),
                    total_trades=20,
                    profit_factor=Decimal("2.0"),
                    max_drawdown_pct=Decimal("30"),
                ),
            ),
            BacktestResult(
                id=uuid4(),
                name="Balanced",
                parameters={},
                started_at=now,
                completed_at=now,
                duration_seconds=1.0,
                trades=[],
                metrics=BacktestMetrics(
                    total_pnl=Decimal("100"),
                    win_rate=Decimal("0.60"),
                    total_trades=15,
                    profit_factor=Decimal("1.8"),
                    max_drawdown_pct=Decimal("20"),
                ),
            ),
        ]


class TestCompareScenarios(TestComparisonService):
    """Tests for compare_scenarios method."""

    def test_compare_multiple_scenarios(self, sample_results: list) -> None:
        """Test comparing multiple scenarios."""
        from walltrack.core.backtest.comparison_service import ComparisonService

        service = ComparisonService()
        comparison = service.compare_scenarios(sample_results)

        assert len(comparison.scenarios) == 3
        assert len(comparison.metric_comparisons) > 0
        assert comparison.best_scenario_name in ["Conservative", "Aggressive", "Balanced"]

    def test_compare_requires_minimum_results(self) -> None:
        """Test that comparison requires at least 2 results."""
        from walltrack.core.backtest.comparison_service import ComparisonService
        from walltrack.core.backtest.results import BacktestMetrics, BacktestResult

        service = ComparisonService()

        single_result = [
            BacktestResult(
                id=uuid4(),
                name="Single",
                parameters={},
                started_at=datetime.now(UTC),
                completed_at=datetime.now(UTC),
                duration_seconds=1.0,
                trades=[],
                metrics=BacktestMetrics(),
            )
        ]

        with pytest.raises(ValueError, match="at least 2"):
            service.compare_scenarios(single_result)

    def test_rankings_are_calculated(self, sample_results: list) -> None:
        """Test that rankings are calculated for each metric."""
        from walltrack.core.backtest.comparison_service import ComparisonService

        service = ComparisonService()
        comparison = service.compare_scenarios(sample_results)

        # Check that PnL metric has rankings
        pnl_metric = next(
            (m for m in comparison.metric_comparisons if m.name == "total_pnl"), None
        )
        assert pnl_metric is not None
        assert pnl_metric.best_scenario == "Aggressive"  # Has highest PnL
        assert pnl_metric.rankings["Aggressive"] == 1

    def test_overall_rank_assigned(self, sample_results: list) -> None:
        """Test that overall ranks are assigned to summaries."""
        from walltrack.core.backtest.comparison_service import ComparisonService

        service = ComparisonService()
        comparison = service.compare_scenarios(sample_results)

        ranks = [s.overall_rank for s in comparison.scenarios]
        assert 1 in ranks
        assert 2 in ranks
        assert 3 in ranks


class TestComparePairDetailed(TestComparisonService):
    """Tests for compare_pair_detailed method."""

    def test_detailed_comparison_counts_trades(self) -> None:
        """Test detailed comparison counts trade differences."""
        from walltrack.core.backtest.comparison_service import ComparisonService
        from walltrack.core.backtest.results import (
            BacktestMetrics,
            BacktestResult,
            BacktestTrade,
        )

        now = datetime.now(UTC)

        # Create trades with different signal IDs
        trade1 = BacktestTrade(
            id=uuid4(),
            signal_id=uuid4(),
            token_address="Token1",
            entry_time=now,
            entry_price=Decimal("0.001"),
            position_size_sol=Decimal("0.1"),
            tokens_bought=Decimal("100"),
            realized_pnl=Decimal("10"),
            is_open=False,
        )
        trade2 = BacktestTrade(
            id=uuid4(),
            signal_id=uuid4(),
            token_address="Token2",
            entry_time=now,
            entry_price=Decimal("0.001"),
            position_size_sol=Decimal("0.1"),
            tokens_bought=Decimal("100"),
            realized_pnl=Decimal("-5"),
            is_open=False,
        )

        result_a = BacktestResult(
            id=uuid4(),
            name="A",
            parameters={},
            started_at=now,
            completed_at=now,
            duration_seconds=1.0,
            trades=[trade1],  # Only trade1
            metrics=BacktestMetrics(total_pnl=Decimal("10")),
        )

        result_b = BacktestResult(
            id=uuid4(),
            name="B",
            parameters={},
            started_at=now,
            completed_at=now,
            duration_seconds=1.0,
            trades=[trade2],  # Only trade2
            metrics=BacktestMetrics(total_pnl=Decimal("-5")),
        )

        service = ComparisonService()
        detailed = service.compare_pair_detailed(result_a, result_b)

        assert detailed.trades_only_a == 1
        assert detailed.trades_only_b == 1
        assert detailed.trades_both == 0
        assert len(detailed.divergence_points) == 2


class TestExportComparisonCsv(TestComparisonService):
    """Tests for export_comparison_csv method."""

    def test_export_csv(self, sample_results: list) -> None:
        """Test exporting comparison as CSV."""
        from walltrack.core.backtest.comparison_service import ComparisonService

        service = ComparisonService()
        comparison = service.compare_scenarios(sample_results)
        csv = service.export_comparison_csv(comparison)

        assert "Conservative" in csv
        assert "Aggressive" in csv
        assert "Balanced" in csv
        assert "Total P&L" in csv


class TestGetComparisonService:
    """Tests for singleton accessor."""

    def test_returns_singleton(self) -> None:
        """Test get_comparison_service returns singleton."""
        from walltrack.core.backtest.comparison_service import get_comparison_service

        service1 = get_comparison_service()
        service2 = get_comparison_service()

        assert service1 is service2
