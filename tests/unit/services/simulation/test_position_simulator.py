"""Tests for position simulator wrapper."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.services.exit.exit_strategy_service import ExitStrategy
from walltrack.services.exit.simulation_engine import SimulationResult
from walltrack.services.simulation.position_simulator import (
    PositionSimulator,
    reset_position_simulator,
)


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create mock simulation engine."""
    engine = MagicMock()
    engine.simulate_position = AsyncMock()
    return engine


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
        triggers=[],
    )


@pytest.fixture
def simulator() -> PositionSimulator:
    """Create simulator instance."""
    reset_position_simulator()
    return PositionSimulator()


@pytest.fixture
def sample_position_data() -> dict:
    """Create sample position data from database."""
    return {
        "id": "position-123",
        "entry_price": "1.0",
        "entry_time": "2024-01-01T10:00:00+00:00",
        "size_sol": "10.0",
        "token_address": "token-abc",
        "exit_price": None,
        "exit_time": None,
    }


class TestPositionSimulator:
    """Tests for PositionSimulator."""

    @pytest.mark.asyncio
    async def test_simulate_by_id_loads_position(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        sample_strategy: ExitStrategy,
        sample_position_data: dict,
        sample_simulation_result: SimulationResult,
    ) -> None:
        """simulate_by_id loads position from database."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_engine.simulate_position.return_value = sample_simulation_result

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            patch.object(simulator, "_get_engine", return_value=mock_engine),
        ):
            result = await simulator.simulate_by_id("position-123", sample_strategy)

        assert result == sample_simulation_result
        mock_client.table.assert_called_with("positions")
        mock_engine.simulate_position.assert_called_once()

    @pytest.mark.asyncio
    async def test_simulate_by_id_with_actual_exit(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        sample_strategy: ExitStrategy,
        sample_simulation_result: SimulationResult,
    ) -> None:
        """simulate_by_id passes actual exit data when available."""
        position_data = {
            "id": "position-123",
            "entry_price": "1.0",
            "entry_time": "2024-01-01T10:00:00Z",
            "size_sol": "10.0",
            "token_address": "token-abc",
            "exit_price": "1.5",
            "exit_time": "2024-01-01T12:00:00Z",
        }
        mock_client.execute.return_value = MagicMock(data=position_data)
        mock_engine.simulate_position.return_value = sample_simulation_result

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            patch.object(simulator, "_get_engine", return_value=mock_engine),
        ):
            await simulator.simulate_by_id("position-123", sample_strategy)

        call_kwargs = mock_engine.simulate_position.call_args.kwargs
        assert call_kwargs["actual_exit"] is not None
        assert call_kwargs["actual_exit"][0] == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_simulate_by_id_position_not_found(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        sample_strategy: ExitStrategy,
    ) -> None:
        """simulate_by_id raises error when position not found."""
        mock_client.execute.return_value = MagicMock(data=None)

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            pytest.raises(ValueError, match="Position not found"),
        ):
            await simulator.simulate_by_id("invalid-id", sample_strategy)

    @pytest.mark.asyncio
    async def test_batch_simulate_positions(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        sample_strategy: ExitStrategy,
        sample_position_data: dict,
        sample_simulation_result: SimulationResult,
    ) -> None:
        """batch_simulate_positions simulates multiple positions."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_engine.simulate_position.return_value = sample_simulation_result

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            patch.object(simulator, "_get_engine", return_value=mock_engine),
        ):
            results = await simulator.batch_simulate_positions(
                ["pos-1", "pos-2", "pos-3"],
                sample_strategy,
            )

        assert len(results) == 3
        assert mock_engine.simulate_position.call_count == 3

    @pytest.mark.asyncio
    async def test_batch_simulate_handles_errors(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        sample_strategy: ExitStrategy,
        sample_position_data: dict,
        sample_simulation_result: SimulationResult,
    ) -> None:
        """batch_simulate_positions continues on error."""
        # First succeeds, second fails, third succeeds
        mock_client.execute.side_effect = [
            MagicMock(data=sample_position_data),
            MagicMock(data=None),  # Will cause ValueError
            MagicMock(data=sample_position_data),
        ]
        mock_engine.simulate_position.return_value = sample_simulation_result

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            patch.object(simulator, "_get_engine", return_value=mock_engine),
        ):
            results = await simulator.batch_simulate_positions(
                ["pos-1", "pos-2", "pos-3"],
                sample_strategy,
            )

        # Only 2 succeeded (pos-2 failed)
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_compare_strategies(
        self,
        simulator: PositionSimulator,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        sample_strategy: ExitStrategy,
        sample_position_data: dict,
        sample_simulation_result: SimulationResult,
    ) -> None:
        """compare_strategies simulates multiple strategies."""
        mock_client.execute.return_value = MagicMock(data=sample_position_data)
        mock_engine.simulate_position.return_value = sample_simulation_result

        now = datetime.now(UTC)
        strategy2 = ExitStrategy(
            id="strategy-456",
            name="Strategy 2",
            description="Test 2",
            version=1,
            status="active",
            rules=[],
            max_hold_hours=168,
            stagnation_hours=6,
            stagnation_threshold_pct=Decimal("5.0"),
            created_at=now,
            updated_at=now,
        )

        with (
            patch.object(simulator, "_get_client", return_value=mock_client),
            patch.object(simulator, "_get_engine", return_value=mock_engine),
        ):
            results = await simulator.compare_strategies(
                "position-123",
                [sample_strategy, strategy2],
            )

        assert len(results) == 2
        assert sample_strategy.id in results
        assert strategy2.id in results


class TestParseDatetime:
    """Tests for datetime parsing."""

    def test_parse_iso_format(self) -> None:
        """Parse ISO format datetime."""
        simulator = PositionSimulator()
        result = simulator._parse_datetime("2024-01-01T10:00:00+00:00")
        assert result.year == 2024
        assert result.month == 1
        assert result.hour == 10

    def test_parse_z_suffix(self) -> None:
        """Parse datetime with Z suffix."""
        simulator = PositionSimulator()
        result = simulator._parse_datetime("2024-01-01T10:00:00Z")
        assert result.year == 2024
        assert result.month == 1
        assert result.hour == 10
