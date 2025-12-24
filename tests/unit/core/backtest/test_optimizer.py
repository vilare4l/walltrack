"""Tests for parameter optimization."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestOptimizationObjective:
    """Tests for OptimizationObjective enum."""

    def test_objective_values(self) -> None:
        """Test objective enum values."""
        from walltrack.core.backtest.optimizer import OptimizationObjective

        assert OptimizationObjective.TOTAL_PNL.value == "total_pnl"
        assert OptimizationObjective.WIN_RATE.value == "win_rate"
        assert OptimizationObjective.PROFIT_FACTOR.value == "profit_factor"
        assert OptimizationObjective.RISK_ADJUSTED.value == "risk_adjusted"


class TestParameterRange:
    """Tests for ParameterRange model."""

    def test_parameter_range_creation(self) -> None:
        """Test creating a parameter range."""
        from walltrack.core.backtest.optimizer import ParameterRange

        param = ParameterRange(
            name="score_threshold",
            values=[0.65, 0.70, 0.75, 0.80],
            display_name="Score Threshold",
        )

        assert param.name == "score_threshold"
        assert param.count == 4
        assert param.display_name == "Score Threshold"

    def test_count_property(self) -> None:
        """Test count property."""
        from walltrack.core.backtest.optimizer import ParameterRange

        param = ParameterRange(
            name="position_size",
            values=[0.1, 0.2, 0.3],
        )

        assert param.count == 3


class TestOptimizationConfig:
    """Tests for OptimizationConfig model."""

    def test_config_creation(self) -> None:
        """Test creating optimization config."""
        from walltrack.core.backtest.optimizer import (
            OptimizationConfig,
            OptimizationObjective,
            ParameterRange,
        )

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
            parameter_ranges=[
                ParameterRange(name="threshold", values=[0.7, 0.8]),
                ParameterRange(name="size", values=[0.1, 0.2, 0.3]),
            ],
            objective=OptimizationObjective.TOTAL_PNL,
        )

        assert config.total_combinations == 6  # 2 * 3

    def test_total_combinations_empty(self) -> None:
        """Test total combinations with no ranges."""
        from walltrack.core.backtest.optimizer import OptimizationConfig

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
            parameter_ranges=[],
        )

        assert config.total_combinations == 0


class TestOptimizationResult:
    """Tests for OptimizationResult model."""

    def test_result_creation(self) -> None:
        """Test creating optimization result."""
        from walltrack.core.backtest.optimizer import OptimizationResult

        result = OptimizationResult(
            combination_id=0,
            parameters={"threshold": 0.7},
            objective_value=Decimal("100"),
        )

        assert result.combination_id == 0
        assert result.objective_value == Decimal("100")


class TestOptimizationSummary:
    """Tests for OptimizationSummary model."""

    def test_summary_creation(self) -> None:
        """Test creating optimization summary."""
        from walltrack.core.backtest.optimizer import (
            OptimizationConfig,
            OptimizationSummary,
        )

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
            parameter_ranges=[],
        )

        summary = OptimizationSummary(
            config=config,
            started_at=datetime.now(UTC),
            total_combinations=10,
        )

        assert summary.total_combinations == 10
        assert summary.completed_combinations == 0
        assert summary.best_result is None


class TestGridSearchOptimizer:
    """Tests for GridSearchOptimizer class."""

    @pytest.fixture
    def optimizer(self):
        """Create optimizer instance."""
        from walltrack.core.backtest.optimizer import GridSearchOptimizer

        return GridSearchOptimizer(max_workers=2)

    def test_generate_combinations(self, optimizer) -> None:
        """Test combination generation."""
        from walltrack.core.backtest.optimizer import (
            OptimizationConfig,
            ParameterRange,
        )

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
            parameter_ranges=[
                ParameterRange(name="a", values=[1, 2]),
                ParameterRange(name="b", values=["x", "y", "z"]),
            ],
        )

        combinations = optimizer._generate_combinations(config)

        assert len(combinations) == 6
        assert {"a": 1, "b": "x"} in combinations
        assert {"a": 2, "b": "z"} in combinations

    @pytest.mark.asyncio
    async def test_optimize_runs_backtests(self, optimizer, mocker) -> None:
        """Test that optimize runs backtests for each combination."""
        from walltrack.core.backtest.optimizer import (
            OptimizationConfig,
            OptimizationObjective,
            ParameterRange,
        )
        from walltrack.core.backtest.results import BacktestMetrics, BacktestResult

        # Mock BacktestEngine
        mock_result = BacktestResult(
            id=uuid4(),
            name="Test",
            parameters={},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_seconds=1.0,
            trades=[],
            metrics=BacktestMetrics(total_pnl=Decimal("50")),
        )

        mock_engine_class = mocker.patch(
            "walltrack.core.backtest.optimizer.BacktestEngine"
        )
        mock_engine_class.return_value.run = mocker.AsyncMock(return_value=mock_result)

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 1, 31, tzinfo=UTC),
            parameter_ranges=[
                ParameterRange(name="score_threshold", values=[Decimal("0.7"), Decimal("0.8")]),
            ],
            objective=OptimizationObjective.TOTAL_PNL,
        )

        summary = await optimizer.optimize(config)

        assert summary.completed_combinations == 2
        assert summary.best_result is not None

    @pytest.mark.asyncio
    async def test_cancellation(self, optimizer, mocker) -> None:
        """Test optimization cancellation."""
        from walltrack.core.backtest.optimizer import (
            OptimizationConfig,
            ParameterRange,
        )
        from walltrack.core.backtest.results import BacktestMetrics, BacktestResult

        mock_result = BacktestResult(
            id=uuid4(),
            name="Test",
            parameters={},
            started_at=datetime.now(UTC),
            completed_at=datetime.now(UTC),
            duration_seconds=1.0,
            trades=[],
            metrics=BacktestMetrics(total_pnl=Decimal("50")),
        )

        mock_engine_class = mocker.patch(
            "walltrack.core.backtest.optimizer.BacktestEngine"
        )
        mock_engine_class.return_value.run = mocker.AsyncMock(return_value=mock_result)

        config = OptimizationConfig(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 1, 31, tzinfo=UTC),
            parameter_ranges=[
                ParameterRange(name="score_threshold", values=[Decimal("0.7")]),
            ],
        )

        optimizer.cancel()
        summary = await optimizer.optimize(config)

        # All should be cancelled/errored
        assert summary.completed_combinations == 0

    def test_sensitivity_analysis(self, optimizer) -> None:
        """Test parameter sensitivity analysis."""
        from walltrack.core.backtest.optimizer import (
            OptimizationResult,
            ParameterRange,
        )

        results = [
            OptimizationResult(
                combination_id=0,
                parameters={"threshold": 0.7},
                objective_value=Decimal("100"),
            ),
            OptimizationResult(
                combination_id=1,
                parameters={"threshold": 0.8},
                objective_value=Decimal("150"),
            ),
            OptimizationResult(
                combination_id=2,
                parameters={"threshold": 0.7},
                objective_value=Decimal("90"),
            ),
            OptimizationResult(
                combination_id=3,
                parameters={"threshold": 0.8},
                objective_value=Decimal("160"),
            ),
        ]

        ranges = [ParameterRange(name="threshold", values=[0.7, 0.8])]

        sensitivity = optimizer._analyze_sensitivity(results, ranges)

        assert "threshold" in sensitivity
        assert sensitivity["threshold"]["best_value"] == "0.8"

    def test_pareto_frontier(self, optimizer) -> None:
        """Test Pareto frontier calculation."""
        from walltrack.core.backtest.optimizer import OptimizationResult

        results = [
            OptimizationResult(
                combination_id=0,
                parameters={},
                objective_value=Decimal("100"),
                secondary_values={"win_rate": Decimal("0.6")},
            ),
            OptimizationResult(
                combination_id=1,
                parameters={},
                objective_value=Decimal("80"),
                secondary_values={"win_rate": Decimal("0.8")},
            ),
            OptimizationResult(
                combination_id=2,
                parameters={},
                objective_value=Decimal("50"),
                secondary_values={"win_rate": Decimal("0.5")},
            ),
        ]

        frontier = optimizer._find_pareto_frontier(results)

        # Results 0 and 1 should be on frontier (neither dominates the other)
        # Result 2 is dominated by both
        assert len(frontier) == 2


class TestCommonParameterRanges:
    """Tests for common parameter ranges helper."""

    def test_common_ranges_exist(self) -> None:
        """Test common parameter ranges are defined."""
        from walltrack.core.backtest.optimizer import common_parameter_ranges

        ranges = common_parameter_ranges()

        assert "score_threshold" in ranges
        assert "base_position_sol" in ranges
        assert len(ranges["score_threshold"]) > 0
