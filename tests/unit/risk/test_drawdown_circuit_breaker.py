"""Unit tests for DrawdownCircuitBreaker."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.risk.circuit_breaker import DrawdownCircuitBreaker
from walltrack.models.risk import (
    CircuitBreakerType,
    DrawdownConfig,
)


@pytest.fixture
def drawdown_config() -> DrawdownConfig:
    """Create a test drawdown config."""
    return DrawdownConfig(
        threshold_percent=Decimal("20.0"),
        initial_capital=Decimal("1000.0"),
    )


@pytest.fixture
def breaker(drawdown_config: DrawdownConfig) -> DrawdownCircuitBreaker:
    """Create a test DrawdownCircuitBreaker."""
    return DrawdownCircuitBreaker(drawdown_config)


class TestDrawdownCalculation:
    """Test drawdown calculation logic."""

    def test_initial_state_no_drawdown(self, breaker: DrawdownCircuitBreaker) -> None:
        """Initial capital has zero drawdown."""
        snapshot = breaker.calculate_drawdown(Decimal("1000.0"))

        assert snapshot.capital == Decimal("1000.0")
        assert snapshot.peak_capital == Decimal("1000.0")
        assert snapshot.drawdown_percent == Decimal("0")

    def test_capital_increase_updates_peak(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Peak capital increases with new highs."""
        snapshot = breaker.calculate_drawdown(Decimal("1500.0"))

        assert snapshot.peak_capital == Decimal("1500.0")
        assert snapshot.drawdown_percent == Decimal("0")

    def test_capital_decrease_creates_drawdown(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Capital decrease creates drawdown from peak."""
        # First go up
        breaker.calculate_drawdown(Decimal("1500.0"))

        # Then go down
        snapshot = breaker.calculate_drawdown(Decimal("1200.0"))

        assert snapshot.capital == Decimal("1200.0")
        assert snapshot.peak_capital == Decimal("1500.0")
        # (1500 - 1200) / 1500 = 0.2 = 20%
        assert snapshot.drawdown_percent == Decimal("20.0")

    def test_peak_never_decreases(self, breaker: DrawdownCircuitBreaker) -> None:
        """Peak capital never decreases even with losses."""
        breaker.calculate_drawdown(Decimal("2000.0"))
        breaker.calculate_drawdown(Decimal("1000.0"))
        breaker.calculate_drawdown(Decimal("800.0"))

        assert breaker._peak_capital == Decimal("2000.0")

    def test_drawdown_with_zero_peak(self) -> None:
        """Handle edge case of zero peak capital."""
        config = DrawdownConfig(
            threshold_percent=Decimal("20.0"),
            initial_capital=Decimal("0.0001"),  # Minimum valid
        )
        breaker = DrawdownCircuitBreaker(config)
        breaker._peak_capital = Decimal("0")

        snapshot = breaker.calculate_drawdown(Decimal("100.0"))

        # Should update peak and have 0% drawdown
        assert snapshot.peak_capital == Decimal("100.0")
        assert snapshot.drawdown_percent == Decimal("0")


class TestCircuitBreakerTrigger:
    """Test circuit breaker trigger logic."""

    @pytest.mark.asyncio
    async def test_no_trigger_below_threshold(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """No trigger when drawdown below threshold."""
        mock_db = MagicMock()

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            result = await breaker.check_drawdown(Decimal("900.0"))

            # 10% drawdown, threshold is 20%
            assert result.is_breached is False
            assert result.trigger is None

    @pytest.mark.asyncio
    async def test_trigger_at_threshold(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Trigger when drawdown equals threshold."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        async def mock_execute_insert() -> MagicMock:
            result = MagicMock()
            result.data = [{"id": "trigger-123"}]
            return result

        async def mock_execute_upsert() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute_insert

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            result = await breaker.check_drawdown(Decimal("800.0"))

            # 20% drawdown = threshold
            assert result.is_breached is True
            assert result.trigger is not None
            assert result.trigger.breaker_type == CircuitBreakerType.DRAWDOWN

    @pytest.mark.asyncio
    async def test_trigger_above_threshold(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Trigger when drawdown exceeds threshold."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = [{"id": "trigger-456"}]
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            result = await breaker.check_drawdown(Decimal("700.0"))

            # 30% drawdown > 20% threshold
            assert result.is_breached is True
            assert result.drawdown_percent == Decimal("30.0")


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality."""

    @pytest.mark.asyncio
    async def test_reset_updates_database(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Reset updates database records."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.is_.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await breaker.reset("operator-1")

            # Verify trigger was marked as reset
            mock_db.table.assert_any_call("circuit_breaker_triggers")

    @pytest.mark.asyncio
    async def test_reset_with_new_peak(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Reset can set new peak capital."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.is_.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        breaker._current_capital = Decimal("800.0")

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await breaker.reset("operator-1", new_peak=Decimal("800.0"))

            assert breaker._peak_capital == Decimal("800.0")

    @pytest.mark.asyncio
    async def test_reset_without_new_peak_uses_current(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Reset without new peak uses current capital as new peak."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.update.return_value = mock_table
        mock_table.eq.return_value = mock_table
        mock_table.is_.return_value = mock_table
        mock_table.upsert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        breaker._current_capital = Decimal("750.0")

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await breaker.reset("operator-1")

            assert breaker._peak_capital == Decimal("750.0")


class TestBlockedSignals:
    """Test signal blocking functionality."""

    @pytest.mark.asyncio
    async def test_block_signal_records_to_db(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Blocked signals are recorded to database."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            blocked = await breaker.block_signal(
                "signal-123", {"token": "PUMP", "action": "buy"}
            )

            assert blocked.signal_id == "signal-123"
            assert blocked.breaker_type == CircuitBreakerType.DRAWDOWN
            mock_db.table.assert_called_with("blocked_signals")

    @pytest.mark.asyncio
    async def test_block_signal_includes_reason(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Blocked signal includes threshold info in reason."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.insert.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            blocked = await breaker.block_signal("signal-456", {})

            assert "20.0%" in blocked.reason


class TestDrawdownProperty:
    """Test current_drawdown_percent property."""

    def test_current_drawdown_percent(self, breaker: DrawdownCircuitBreaker) -> None:
        """Current drawdown percent is calculated correctly."""
        breaker._peak_capital = Decimal("1000.0")
        breaker._current_capital = Decimal("850.0")

        assert breaker.current_drawdown_percent == Decimal("15.0")

    def test_current_drawdown_percent_zero_peak(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Zero peak capital returns zero drawdown."""
        breaker._peak_capital = Decimal("0")
        breaker._current_capital = Decimal("100.0")

        assert breaker.current_drawdown_percent == Decimal("0")


class TestInitialize:
    """Test initialization from database."""

    @pytest.mark.asyncio
    async def test_initialize_loads_from_db(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Initialize loads latest snapshot from database."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = [
                {"capital": "1500.0", "peak_capital": "2000.0"}
            ]
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await breaker.initialize()

            assert breaker._current_capital == Decimal("1500.0")
            assert breaker._peak_capital == Decimal("2000.0")

    @pytest.mark.asyncio
    async def test_initialize_no_snapshots(
        self, breaker: DrawdownCircuitBreaker
    ) -> None:
        """Initialize with no existing snapshots uses config values."""
        mock_db = MagicMock()
        mock_table = MagicMock()
        mock_db.table.return_value = mock_table
        mock_table.select.return_value = mock_table
        mock_table.order.return_value = mock_table
        mock_table.limit.return_value = mock_table

        async def mock_execute() -> MagicMock:
            result = MagicMock()
            result.data = []
            return result

        mock_table.execute = mock_execute

        with patch.object(breaker, "_get_db", new_callable=AsyncMock) as mock_get_db:
            mock_get_db.return_value = mock_db
            await breaker.initialize()

            # Should keep initial config values
            assert breaker._current_capital == Decimal("1000.0")
            assert breaker._peak_capital == Decimal("1000.0")
