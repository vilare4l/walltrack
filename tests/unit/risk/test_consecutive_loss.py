"""Unit tests for ConsecutiveLossManager."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.risk.consecutive_loss import ConsecutiveLossManager
from walltrack.models.risk import (
    ConsecutiveLossConfig,
    SizingMode,
    TradeOutcome,
    TradeResult,
)


@pytest.fixture
def loss_config() -> ConsecutiveLossConfig:
    """Create a test consecutive loss config."""
    return ConsecutiveLossConfig(
        reduction_threshold=3,
        reduction_factor=Decimal("0.5"),
        critical_threshold=5,
        critical_action="pause",
    )


@pytest.fixture
def manager(loss_config: ConsecutiveLossConfig) -> ConsecutiveLossManager:
    """Create a test ConsecutiveLossManager."""
    return ConsecutiveLossManager(loss_config)


@pytest.fixture
def losing_trade() -> TradeResult:
    """Create a losing trade result."""
    return TradeResult(
        trade_id="trade-001",
        outcome=TradeOutcome.LOSS,
        pnl_percent=Decimal("-10.0"),
        pnl_absolute=Decimal("-50.0"),
        entry_price=Decimal("100.0"),
        exit_price=Decimal("90.0"),
        token_address="0xabc123",
    )


@pytest.fixture
def winning_trade() -> TradeResult:
    """Create a winning trade result."""
    return TradeResult(
        trade_id="trade-002",
        outcome=TradeOutcome.WIN,
        pnl_percent=Decimal("20.0"),
        pnl_absolute=Decimal("100.0"),
        entry_price=Decimal("100.0"),
        exit_price=Decimal("120.0"),
        token_address="0xabc123",
    )


def _create_mock_db() -> MagicMock:
    """Create a mock database client."""
    mock_db = MagicMock()
    mock_table = MagicMock()
    mock_db.table.return_value = mock_table
    mock_table.upsert.return_value = mock_table
    mock_table.insert.return_value = mock_table
    mock_table.update.return_value = mock_table
    mock_table.eq.return_value = mock_table
    mock_table.is_.return_value = mock_table

    async def mock_execute() -> MagicMock:
        result = MagicMock()
        result.data = [{}]
        return result

    mock_table.execute = mock_execute
    return mock_db


class TestLossTracking:
    """Test consecutive loss tracking."""

    @pytest.mark.asyncio
    async def test_first_loss_starts_count(
        self, manager: ConsecutiveLossManager, losing_trade: TradeResult
    ) -> None:
        """First loss starts the counter."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            state = await manager.record_trade_outcome(losing_trade)

            assert state.consecutive_loss_count == 1
            assert state.sizing_mode == SizingMode.NORMAL
            assert state.streak_started_at is not None

    @pytest.mark.asyncio
    async def test_consecutive_losses_increment(
        self, manager: ConsecutiveLossManager, losing_trade: TradeResult
    ) -> None:
        """Consecutive losses increment counter."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await manager.record_trade_outcome(losing_trade)
            state = await manager.record_trade_outcome(losing_trade)

            assert state.consecutive_loss_count == 2

    @pytest.mark.asyncio
    async def test_breakeven_does_not_affect_streak(
        self, manager: ConsecutiveLossManager, losing_trade: TradeResult
    ) -> None:
        """Breakeven trade does not affect loss streak."""
        mock_db = _create_mock_db()

        breakeven_trade = TradeResult(
            trade_id="trade-003",
            outcome=TradeOutcome.BREAKEVEN,
            pnl_percent=Decimal("0.0"),
            pnl_absolute=Decimal("0.0"),
            entry_price=Decimal("100.0"),
            exit_price=Decimal("100.0"),
            token_address="0xabc123",
        )

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await manager.record_trade_outcome(losing_trade)
            state = await manager.record_trade_outcome(breakeven_trade)

            assert state.consecutive_loss_count == 1  # Not reset


class TestPositionSizeReduction:
    """Test position size reduction logic."""

    @pytest.mark.asyncio
    async def test_reduction_at_threshold(
        self, manager: ConsecutiveLossManager, losing_trade: TradeResult
    ) -> None:
        """Position size reduced at threshold."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            # Record 3 losses (threshold)
            for _ in range(3):
                state = await manager.record_trade_outcome(losing_trade)

            assert state.sizing_mode == SizingMode.REDUCED
            assert state.current_size_factor == Decimal("0.5")

    def test_size_calculation_normal(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Size calculation returns full size in normal mode."""
        result = manager.calculate_adjusted_size(Decimal("100.0"))

        assert result.adjusted_size == Decimal("100.0")
        assert result.size_factor == Decimal("1.0")
        assert result.sizing_mode == SizingMode.NORMAL

    def test_size_calculation_reduced(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Size calculation applies reduction factor."""
        manager._state.sizing_mode = SizingMode.REDUCED
        manager._state.current_size_factor = Decimal("0.5")
        manager._state.consecutive_loss_count = 3

        result = manager.calculate_adjusted_size(Decimal("100.0"))

        assert result.adjusted_size == Decimal("50.0")
        assert result.size_factor == Decimal("0.5")
        assert "Reduced" in result.reason

    def test_size_calculation_paused(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Size calculation returns zero when paused."""
        manager._state.sizing_mode = SizingMode.PAUSED
        manager._state.current_size_factor = Decimal("0")
        manager._state.consecutive_loss_count = 5

        result = manager.calculate_adjusted_size(Decimal("100.0"))

        assert result.adjusted_size == Decimal("0")
        assert "paused" in result.reason.lower()


class TestCriticalThreshold:
    """Test critical threshold handling."""

    @pytest.mark.asyncio
    async def test_critical_pause(
        self, manager: ConsecutiveLossManager, losing_trade: TradeResult
    ) -> None:
        """Critical threshold pauses trading."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            # Record 5 losses (critical threshold)
            for _ in range(5):
                state = await manager.record_trade_outcome(losing_trade)

            assert state.sizing_mode == SizingMode.PAUSED
            assert state.current_size_factor == Decimal("0")
            assert manager.can_trade is False

    @pytest.mark.asyncio
    async def test_critical_further_reduce(
        self, losing_trade: TradeResult
    ) -> None:
        """Critical threshold with further_reduce action."""
        config = ConsecutiveLossConfig(
            reduction_threshold=3,
            reduction_factor=Decimal("0.5"),
            critical_threshold=5,
            critical_action="further_reduce",
            further_reduction_factor=Decimal("0.25"),
        )
        manager = ConsecutiveLossManager(config)
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            for _ in range(5):
                state = await manager.record_trade_outcome(losing_trade)

            assert state.sizing_mode == SizingMode.CRITICAL
            assert state.current_size_factor == Decimal("0.25")
            assert manager.can_trade is True  # Still allowed but reduced


class TestRecovery:
    """Test recovery on winning trade."""

    @pytest.mark.asyncio
    async def test_win_resets_streak(
        self,
        manager: ConsecutiveLossManager,
        losing_trade: TradeResult,
        winning_trade: TradeResult,
    ) -> None:
        """Winning trade resets loss streak."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            # Record 3 losses
            for _ in range(3):
                await manager.record_trade_outcome(losing_trade)

            # Win resets
            state = await manager.record_trade_outcome(winning_trade)

            assert state.consecutive_loss_count == 0
            assert state.sizing_mode == SizingMode.NORMAL
            assert state.current_size_factor == Decimal("1.0")
            assert manager.can_trade is True

    @pytest.mark.asyncio
    async def test_win_from_critical_resets(
        self,
        manager: ConsecutiveLossManager,
        losing_trade: TradeResult,
        winning_trade: TradeResult,
    ) -> None:
        """Winning trade resets even from critical/paused state."""
        mock_db = _create_mock_db()

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            # Record 5 losses (critical)
            for _ in range(5):
                await manager.record_trade_outcome(losing_trade)

            # Win resets everything
            state = await manager.record_trade_outcome(winning_trade)

            assert state.consecutive_loss_count == 0
            assert state.sizing_mode == SizingMode.NORMAL


class TestManualReset:
    """Test manual reset functionality."""

    @pytest.mark.asyncio
    async def test_manual_reset_clears_state(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Manual reset clears all state."""
        mock_db = _create_mock_db()

        manager._state.consecutive_loss_count = 5
        manager._state.sizing_mode = SizingMode.PAUSED
        manager._state.current_size_factor = Decimal("0")

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            state = await manager.manual_reset("operator-1")

            assert state.consecutive_loss_count == 0
            assert state.sizing_mode == SizingMode.NORMAL
            assert state.current_size_factor == Decimal("1.0")
            assert manager.can_trade is True


class TestStateProperties:
    """Test state property methods."""

    def test_can_trade_normal(self, manager: ConsecutiveLossManager) -> None:
        """can_trade returns True in normal mode."""
        manager._state.sizing_mode = SizingMode.NORMAL
        assert manager.can_trade is True

    def test_can_trade_reduced(self, manager: ConsecutiveLossManager) -> None:
        """can_trade returns True in reduced mode."""
        manager._state.sizing_mode = SizingMode.REDUCED
        assert manager.can_trade is True

    def test_can_trade_paused(self, manager: ConsecutiveLossManager) -> None:
        """can_trade returns False in paused mode."""
        manager._state.sizing_mode = SizingMode.PAUSED
        assert manager.can_trade is False

    def test_state_property(self, manager: ConsecutiveLossManager) -> None:
        """state property returns current state."""
        manager._state.consecutive_loss_count = 3
        assert manager.state.consecutive_loss_count == 3


class TestInitialize:
    """Test initialization from database."""

    @pytest.mark.asyncio
    async def test_initialize_loads_state(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Initialize loads existing state from database."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = {
                "value": {
                    "consecutive_loss_count": 2,
                    "sizing_mode": "normal",
                    "current_size_factor": "1.0",
                }
            }
            return result

        mock_table.execute = mock_execute

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await manager.initialize()

            assert manager._state.consecutive_loss_count == 2

    @pytest.mark.asyncio
    async def test_initialize_no_existing_state(
        self, manager: ConsecutiveLossManager
    ) -> None:
        """Initialize with no existing state uses defaults."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.single.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = None
            return result

        mock_table.execute = mock_execute

        with patch.object(manager, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await manager.initialize()

            assert manager._state.consecutive_loss_count == 0
            assert manager._state.sizing_mode == SizingMode.NORMAL
