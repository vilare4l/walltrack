"""Tests for backtest dashboard component."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestFormatScenarioForDisplay:
    """Tests for scenario display formatting."""

    def test_format_single_scenario(self) -> None:
        """Test formatting a single scenario for table display."""
        from walltrack.ui.components.backtest_dashboard import format_scenario_for_display
        from walltrack.core.backtest.scenario import Scenario, ScenarioCategory

        scenario = Scenario(
            name="Test Scenario",
            description="A test scenario",
            category=ScenarioCategory.CONSERVATIVE,
            score_threshold=Decimal("0.75"),
            base_position_sol=Decimal("0.1"),
        )

        result = format_scenario_for_display(scenario)

        assert result["Name"] == "Test Scenario"
        assert result["Category"] == "conservative"
        assert result["Threshold"] == 0.75
        assert result["Position Size"] == 0.1
        assert "Stop Loss" in result

    def test_format_preset_scenario(self) -> None:
        """Test formatting a preset scenario."""
        from walltrack.ui.components.backtest_dashboard import format_scenario_for_display
        from walltrack.core.backtest.scenario import Scenario

        scenario = Scenario(
            name="Preset",
            is_preset=True,
        )

        result = format_scenario_for_display(scenario)

        assert result["Preset"] == "Yes"


class TestFormatBatchForDisplay:
    """Tests for batch display formatting."""

    def test_format_batch(self) -> None:
        """Test formatting a batch for table display."""
        from walltrack.ui.components.backtest_dashboard import format_batch_for_display
        from walltrack.core.backtest.batch import BatchRun, BatchStatus

        batch = BatchRun(
            name="Test Batch",
            scenario_ids=[uuid4(), uuid4()],
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 1, 31, tzinfo=UTC),
            status=BatchStatus.COMPLETED,
            created_at=datetime(2024, 2, 1, 12, 0, tzinfo=UTC),
        )

        result = format_batch_for_display(batch)

        assert result["Name"] == "Test Batch"
        assert result["Scenarios"] == 2
        assert result["Status"] == "completed"
        assert "2024-01-01" in result["Date Range"]


class TestCreateComparisonChartData:
    """Tests for comparison chart data creation."""

    def test_create_chart_data(self) -> None:
        """Test creating chart data from results."""
        from walltrack.ui.components.backtest_dashboard import create_comparison_chart_data

        results = [
            {"name": "A", "total_pnl": 100, "win_rate": 0.6},
            {"name": "B", "total_pnl": 50, "win_rate": 0.7},
        ]

        chart_data = create_comparison_chart_data(results)

        assert "names" in chart_data
        assert "pnls" in chart_data
        assert "win_rates" in chart_data
        assert chart_data["names"] == ["A", "B"]
        assert chart_data["pnls"] == [100, 50]
        assert chart_data["win_rates"] == [60, 70]

    def test_empty_results(self) -> None:
        """Test with empty results."""
        from walltrack.ui.components.backtest_dashboard import create_comparison_chart_data

        chart_data = create_comparison_chart_data([])

        assert chart_data["names"] == []
        assert chart_data["pnls"] == []


class TestCreateComparisonChart:
    """Tests for comparison chart creation."""

    def test_chart_structure(self) -> None:
        """Test chart has correct structure."""
        from walltrack.ui.components.backtest_dashboard import create_comparison_chart

        results = [
            {"name": "A", "total_pnl": 100, "win_rate": 0.6},
            {"name": "B", "total_pnl": 50, "win_rate": 0.7},
        ]

        fig = create_comparison_chart(results)

        assert fig is not None
        assert len(fig.data) == 2  # Two bar traces
        assert fig.layout.title.text == "Scenario Comparison"

    def test_empty_chart(self) -> None:
        """Test chart with empty results."""
        from walltrack.ui.components.backtest_dashboard import create_comparison_chart

        fig = create_comparison_chart([])

        assert fig is not None


class TestCreateEquityChart:
    """Tests for equity curve chart creation."""

    def test_equity_chart_structure(self) -> None:
        """Test equity chart has correct structure."""
        from walltrack.ui.components.backtest_dashboard import create_equity_chart

        equity_curves = {
            "A": [
                {"timestamp": datetime(2024, 1, 1, tzinfo=UTC), "equity": 100},
                {"timestamp": datetime(2024, 1, 2, tzinfo=UTC), "equity": 110},
            ],
            "B": [
                {"timestamp": datetime(2024, 1, 1, tzinfo=UTC), "equity": 100},
                {"timestamp": datetime(2024, 1, 2, tzinfo=UTC), "equity": 95},
            ],
        }

        fig = create_equity_chart(equity_curves)

        assert fig is not None
        assert len(fig.data) == 2  # Two line traces
        assert fig.layout.title.text == "Equity Curves"

    def test_empty_equity_chart(self) -> None:
        """Test equity chart with empty data."""
        from walltrack.ui.components.backtest_dashboard import create_equity_chart

        fig = create_equity_chart({})

        assert fig is not None


class TestFormatComparisonTableData:
    """Tests for comparison table data formatting."""

    def test_format_comparison_data(self) -> None:
        """Test formatting comparison data for table."""
        from walltrack.ui.components.backtest_dashboard import format_comparison_table_data
        from walltrack.core.backtest.comparison import ScenarioSummary
        from walltrack.core.backtest.results import BacktestMetrics

        summaries = [
            ScenarioSummary(
                scenario_id=uuid4(),
                scenario_name="Test",
                metrics=BacktestMetrics(
                    total_pnl=Decimal("100"),
                    win_rate=Decimal("0.6"),
                    total_trades=10,
                    max_drawdown_pct=Decimal("20"),
                    profit_factor=Decimal("1.5"),
                ),
                overall_rank=1,
            ),
        ]

        table_data = format_comparison_table_data(summaries)

        assert len(table_data) == 1
        assert table_data[0]["Scenario"] == "Test"
        assert table_data[0]["Total P&L"] == 100.0
        assert table_data[0]["Rank"] == 1


class TestParseParameterRanges:
    """Tests for parameter range parsing."""

    def test_parse_comma_separated(self) -> None:
        """Test parsing comma-separated values."""
        from walltrack.ui.components.backtest_dashboard import parse_parameter_range

        result = parse_parameter_range("0.65, 0.70, 0.75, 0.80")

        assert len(result) == 4
        assert Decimal("0.65") in result
        assert Decimal("0.80") in result

    def test_parse_invalid(self) -> None:
        """Test parsing invalid input."""
        from walltrack.ui.components.backtest_dashboard import parse_parameter_range

        result = parse_parameter_range("invalid, data")

        assert result == []


class TestValidateScenarioForm:
    """Tests for scenario form validation."""

    def test_valid_form(self) -> None:
        """Test validation of valid form data."""
        from walltrack.ui.components.backtest_dashboard import validate_scenario_form

        errors = validate_scenario_form(
            name="Test",
            score_threshold=0.7,
            wallet_weight=0.3,
            cluster_weight=0.25,
            token_weight=0.25,
            context_weight=0.2,
        )

        assert errors == []

    def test_empty_name(self) -> None:
        """Test validation with empty name."""
        from walltrack.ui.components.backtest_dashboard import validate_scenario_form

        errors = validate_scenario_form(
            name="",
            score_threshold=0.7,
            wallet_weight=0.3,
            cluster_weight=0.25,
            token_weight=0.25,
            context_weight=0.2,
        )

        assert "Name is required" in errors

    def test_invalid_weights(self) -> None:
        """Test validation with weights not summing to 1."""
        from walltrack.ui.components.backtest_dashboard import validate_scenario_form

        errors = validate_scenario_form(
            name="Test",
            score_threshold=0.7,
            wallet_weight=0.5,
            cluster_weight=0.5,
            token_weight=0.5,
            context_weight=0.5,
        )

        assert any("weights must sum to 1.0" in e for e in errors)
