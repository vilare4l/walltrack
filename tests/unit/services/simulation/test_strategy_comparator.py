"""Tests for strategy comparator."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.services.exit.exit_strategy_service import ExitStrategy
from walltrack.services.exit.simulation_engine import RuleTrigger, SimulationResult
from walltrack.services.simulation.strategy_comparator import (
    ComparisonResult,
    StrategyComparator,
    StrategyComparisonRow,
    format_comparison_table,
    reset_strategy_comparator,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock Supabase client."""
    client = MagicMock()
    client.table = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.single = MagicMock(return_value=client)
    client.execute = AsyncMock()
    return client


@pytest.fixture
def mock_position_simulator() -> MagicMock:
    """Create mock position simulator."""
    simulator = MagicMock()
    simulator.compare_strategies = AsyncMock()
    return simulator


@pytest.fixture
def mock_strategy_service() -> MagicMock:
    """Create mock strategy service."""
    service = MagicMock()
    service.get = AsyncMock()
    service.list_all = AsyncMock()
    return service


@pytest.fixture
def sample_strategy() -> ExitStrategy:
    """Create sample strategy."""
    now = datetime.now(UTC)
    return ExitStrategy(
        id="strategy-123",
        name="Test Strategy",
        description="Test",
        version=1,
        status="active",
        rules=[],
        max_hold_hours=168,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("5.0"),
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def sample_simulation_result() -> SimulationResult:
    """Create sample simulation result."""
    now = datetime.now(UTC)
    return SimulationResult(
        position_id="position-123",
        strategy_id="strategy-123",
        strategy_name="Test Strategy",
        entry_price=Decimal("1.0"),
        entry_time=now,
        final_exit_price=Decimal("1.5"),
        final_exit_time=now,
        final_pnl_pct=Decimal("50.0"),
        final_pnl_sol=Decimal("5.0"),
        max_unrealized_gain_pct=Decimal("60.0"),
        max_unrealized_loss_pct=Decimal("10.0"),
        hold_duration_hours=Decimal("2.0"),
        triggers=[
            RuleTrigger(
                timestamp=now,
                rule_type="take_profit",
                trigger_pct=Decimal("50"),
                price_at_trigger=Decimal("1.5"),
                pnl_pct=Decimal("50.0"),
                exit_pct=Decimal("50"),
                cumulative_exit_pct=Decimal("50"),
            )
        ],
    )


@pytest.fixture
def sample_position_data() -> dict:
    """Create sample position data."""
    return {
        "id": "position-123",
        "entry_price": "1.0",
        "entry_time": "2024-01-01T10:00:00+00:00",
        "size_sol": "10.0",
        "token_address": "token-abc",
        "exit_price": "1.3",
        "exit_time": "2024-01-01T12:00:00+00:00",
        "pnl_pct": "30.0",
        "status": "closed",
    }


@pytest.fixture
def comparator() -> StrategyComparator:
    """Create comparator instance."""
    reset_strategy_comparator()
    return StrategyComparator()


class TestStrategyComparator:
    """Tests for StrategyComparator."""

    @pytest.mark.asyncio
    async def test_compare_multiple_strategies(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
        mock_position_simulator: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
        sample_simulation_result: SimulationResult,
        sample_position_data: dict,
    ) -> None:
        """compare returns comparison result for multiple strategies."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_strategy_service.get.return_value = sample_strategy
        mock_position_simulator.compare_strategies.return_value = {
            "strategy-123": sample_simulation_result,
        }

        with (
            patch.object(comparator, "_get_client", return_value=mock_client),
            patch.object(
                comparator,
                "_get_simulator",
                return_value=mock_position_simulator,
            ),
            patch.object(
                comparator,
                "_get_strategy_service",
                return_value=mock_strategy_service,
            ),
        ):
            result = await comparator.compare("position-123", ["strategy-123"])

        assert result is not None
        assert result.position_id == "position-123"
        assert len(result.rows) == 1
        assert result.best_strategy_id == "strategy-123"

    @pytest.mark.asyncio
    async def test_compare_calculates_delta(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
        mock_position_simulator: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
        sample_simulation_result: SimulationResult,
        sample_position_data: dict,
    ) -> None:
        """compare calculates delta vs actual correctly."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_strategy_service.get.return_value = sample_strategy
        mock_position_simulator.compare_strategies.return_value = {
            "strategy-123": sample_simulation_result,
        }

        with (
            patch.object(comparator, "_get_client", return_value=mock_client),
            patch.object(
                comparator,
                "_get_simulator",
                return_value=mock_position_simulator,
            ),
            patch.object(
                comparator,
                "_get_strategy_service",
                return_value=mock_strategy_service,
            ),
        ):
            result = await comparator.compare("position-123", ["strategy-123"])

        assert result is not None
        row = result.rows[0]
        # Simulated 50% - Actual 30% = +20% improvement
        assert row.delta_pct == Decimal("20.0")

    @pytest.mark.asyncio
    async def test_compare_identifies_best_strategy(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
        mock_position_simulator: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
        sample_position_data: dict,
    ) -> None:
        """compare identifies the best strategy."""
        now = datetime.now(UTC)

        # Two strategies with different results
        result1 = SimulationResult(
            position_id="position-123",
            strategy_id="strategy-1",
            strategy_name="Strategy 1",
            entry_price=Decimal("1.0"),
            entry_time=now,
            final_exit_price=Decimal("1.3"),
            final_exit_time=now,
            final_pnl_pct=Decimal("30.0"),
            final_pnl_sol=Decimal("3.0"),
            triggers=[],
        )
        result2 = SimulationResult(
            position_id="position-123",
            strategy_id="strategy-2",
            strategy_name="Strategy 2",
            entry_price=Decimal("1.0"),
            entry_time=now,
            final_exit_price=Decimal("1.5"),
            final_exit_time=now,
            final_pnl_pct=Decimal("50.0"),
            final_pnl_sol=Decimal("5.0"),
            triggers=[],
        )

        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_strategy_service.get.return_value = sample_strategy
        mock_position_simulator.compare_strategies.return_value = {
            "strategy-1": result1,
            "strategy-2": result2,
        }

        with (
            patch.object(comparator, "_get_client", return_value=mock_client),
            patch.object(
                comparator,
                "_get_simulator",
                return_value=mock_position_simulator,
            ),
            patch.object(
                comparator,
                "_get_strategy_service",
                return_value=mock_strategy_service,
            ),
        ):
            result = await comparator.compare(
                "position-123", ["strategy-1", "strategy-2"]
            )

        assert result is not None
        assert result.best_strategy_id == "strategy-2"
        assert result.best_strategy_name == "Strategy 2"

        # Check is_best flag
        for row in result.rows:
            if row.strategy_id == "strategy-2":
                assert row.is_best is True
            else:
                assert row.is_best is False

    @pytest.mark.asyncio
    async def test_compare_position_not_found(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
    ) -> None:
        """compare returns None when position not found."""
        mock_client.execute.return_value = MagicMock(data=None)

        with patch.object(comparator, "_get_client", return_value=mock_client):
            result = await comparator.compare("invalid-id", ["strategy-123"])

        assert result is None

    @pytest.mark.asyncio
    async def test_compare_no_strategies_found(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """compare returns None when no strategies found."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_strategy_service.get.return_value = None

        with (
            patch.object(comparator, "_get_client", return_value=mock_client),
            patch.object(
                comparator,
                "_get_strategy_service",
                return_value=mock_strategy_service,
            ),
        ):
            result = await comparator.compare("position-123", ["invalid-strategy"])

        assert result is None

    @pytest.mark.asyncio
    async def test_compare_all_active_strategies(
        self,
        comparator: StrategyComparator,
        mock_client: MagicMock,
        mock_position_simulator: MagicMock,
        mock_strategy_service: MagicMock,
        sample_strategy: ExitStrategy,
        sample_simulation_result: SimulationResult,
        sample_position_data: dict,
    ) -> None:
        """compare_all_active_strategies compares all active."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_strategy_service.get.return_value = sample_strategy
        mock_position_simulator.compare_strategies.return_value = {
            "strategy-123": sample_simulation_result,
        }

        with (
            patch.object(comparator, "_get_client", return_value=mock_client),
            patch.object(
                comparator,
                "_get_simulator",
                return_value=mock_position_simulator,
            ),
            patch.object(
                comparator,
                "_get_strategy_service",
                return_value=mock_strategy_service,
            ),
        ):
            result = await comparator.compare_all_active_strategies("position-123")

        assert result is not None
        mock_strategy_service.list_all.assert_called_once()


class TestFormatComparisonTable:
    """Tests for format_comparison_table."""

    def test_formats_markdown_table(self) -> None:
        """format_comparison_table creates valid markdown."""
        result = ComparisonResult(
            position_id="position-123",
            entry_price=Decimal("1.0"),
            actual_exit_price=Decimal("1.3"),
            actual_pnl_pct=Decimal("30.0"),
            rows=[
                StrategyComparisonRow(
                    strategy_id="s1",
                    strategy_name="Strategy 1",
                    simulated_pnl_pct=Decimal("50.0"),
                    simulated_pnl_sol=Decimal("5.0"),
                    actual_pnl_pct=Decimal("30.0"),
                    delta_pct=Decimal("20.0"),
                    delta_sol=Decimal("2.0"),
                    exit_time=datetime.now(UTC),
                    exit_types=["take_profit"],
                    is_best=True,
                ),
            ],
            best_strategy_id="s1",
            best_strategy_name="Strategy 1",
            best_improvement_pct=Decimal("20.0"),
        )

        md = format_comparison_table(result)

        assert "## Strategy Comparison" in md
        assert "position..." in md  # truncated ID (first 8 chars + ...)
        assert "Strategy 1" in md
        assert "+50.00%" in md  # simulated PnL
        assert "+20.00%" in md  # delta

    def test_handles_no_actual_exit(self) -> None:
        """format_comparison_table handles positions without actual exit."""
        result = ComparisonResult(
            position_id="position-123",
            entry_price=Decimal("1.0"),
            actual_exit_price=None,
            actual_pnl_pct=None,
            rows=[
                StrategyComparisonRow(
                    strategy_id="s1",
                    strategy_name="Strategy 1",
                    simulated_pnl_pct=Decimal("50.0"),
                    simulated_pnl_sol=Decimal("5.0"),
                    actual_pnl_pct=None,
                    delta_pct=None,
                    delta_sol=None,
                    exit_time=datetime.now(UTC),
                    exit_types=[],
                    is_best=True,
                ),
            ],
            best_strategy_id="s1",
            best_strategy_name="Strategy 1",
            best_improvement_pct=None,
        )

        md = format_comparison_table(result)

        assert "N/A" in md  # for actual P&L
        assert "-" in md  # for delta


class TestStrategyComparisonRow:
    """Tests for StrategyComparisonRow dataclass."""

    def test_creates_row(self) -> None:
        """StrategyComparisonRow initializes correctly."""
        row = StrategyComparisonRow(
            strategy_id="s1",
            strategy_name="Test",
            simulated_pnl_pct=Decimal("50"),
            simulated_pnl_sol=Decimal("5"),
            actual_pnl_pct=Decimal("30"),
            delta_pct=Decimal("20"),
            delta_sol=Decimal("2"),
            exit_time=datetime.now(UTC),
            exit_types=["take_profit", "stop_loss"],
            is_best=True,
        )

        assert row.strategy_id == "s1"
        assert row.is_best is True
        assert len(row.exit_types) == 2

    def test_default_values(self) -> None:
        """StrategyComparisonRow has correct defaults."""
        row = StrategyComparisonRow(
            strategy_id="s1",
            strategy_name="Test",
            simulated_pnl_pct=Decimal("50"),
            simulated_pnl_sol=Decimal("5"),
            actual_pnl_pct=None,
            delta_pct=None,
            delta_sol=None,
            exit_time=None,
        )

        assert row.exit_types == []
        assert row.is_best is False
