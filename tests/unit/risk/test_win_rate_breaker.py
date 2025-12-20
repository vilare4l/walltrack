"""Tests for win rate circuit breaker (Story 5-3)."""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from walltrack.models.risk import (
    CircuitBreakerType,
    WinRateConfig,
    TradeRecord,
    WinRateSnapshot,
)
from walltrack.core.risk.win_rate_breaker import (
    WinRateCircuitBreaker,
    get_win_rate_circuit_breaker,
    reset_win_rate_circuit_breaker,
)


@pytest.fixture
def win_rate_config() -> WinRateConfig:
    """Create test configuration."""
    return WinRateConfig(
        threshold_percent=Decimal("40.0"),
        window_size=50,
        minimum_trades=20,
        enable_caution_flag=True,
    )


@pytest.fixture
def breaker(win_rate_config: WinRateConfig) -> WinRateCircuitBreaker:
    """Create test breaker instance."""
    return WinRateCircuitBreaker(win_rate_config)


def make_trade(trade_id: str, is_win: bool, pnl: Decimal) -> TradeRecord:
    """Helper to create trade records."""
    return TradeRecord(
        trade_id=trade_id,
        closed_at=datetime.utcnow(),
        is_win=is_win,
        pnl_percent=pnl,
    )


class TestWinRateCalculation:
    """Test win rate calculation logic (AC 1)."""

    def test_empty_window_zero_rate(self, breaker: WinRateCircuitBreaker) -> None:
        """Empty window returns zero win rate."""
        snapshot = breaker.calculate_snapshot()

        assert snapshot.trades_in_window == 0
        assert snapshot.win_rate_percent == Decimal("0")

    def test_all_wins_100_percent(self, breaker: WinRateCircuitBreaker) -> None:
        """All winning trades gives 100% win rate."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        snapshot = breaker.calculate_snapshot()

        assert snapshot.win_rate_percent == Decimal("100")
        assert snapshot.winning_trades == 10
        assert snapshot.losing_trades == 0

    def test_all_losses_zero_percent(self, breaker: WinRateCircuitBreaker) -> None:
        """All losing trades gives 0% win rate."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", False, Decimal("-10")))

        snapshot = breaker.calculate_snapshot()

        assert snapshot.win_rate_percent == Decimal("0")
        assert snapshot.winning_trades == 0
        assert snapshot.losing_trades == 10

    def test_mixed_results_correct_rate(self, breaker: WinRateCircuitBreaker) -> None:
        """Mixed results calculate correct win rate."""
        # 6 wins, 4 losses = 60% win rate
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(4):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        snapshot = breaker.calculate_snapshot()

        assert snapshot.trades_in_window == 10
        assert snapshot.winning_trades == 6
        assert snapshot.losing_trades == 4
        assert snapshot.win_rate_percent == Decimal("60")

    def test_window_size_respected(self, breaker: WinRateCircuitBreaker) -> None:
        """Window size limits number of trades kept."""
        # Add more than window size
        for i in range(60):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        assert len(breaker._trade_window) == 50

    def test_rolling_window_removes_oldest(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Rolling window removes oldest trades first."""
        # Fill window with losses
        for i in range(50):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        assert breaker.calculate_snapshot().win_rate_percent == Decimal("0")

        # Add 25 wins (replace half the window)
        for i in range(25):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))

        snapshot = breaker.calculate_snapshot()
        assert snapshot.trades_in_window == 50
        assert snapshot.winning_trades == 25
        assert snapshot.win_rate_percent == Decimal("50")


class TestInsufficientHistory:
    """Test handling of insufficient trade history (AC 4)."""

    @pytest.mark.asyncio
    async def test_caution_flag_below_minimum(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Caution flag when below minimum trades."""
        # Add 10 trades (below minimum of 20)
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        result = await breaker.check_win_rate()

        assert result.is_caution is True
        assert result.is_breached is False
        assert "Caution" in result.message
        assert "10" in result.message
        assert "20" in result.message

    @pytest.mark.asyncio
    async def test_no_trigger_below_minimum(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """No circuit breaker trigger below minimum trades even with low win rate."""
        # Add 10 losing trades (below minimum)
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", False, Decimal("-10")))

        result = await breaker.check_win_rate()

        # Even with 0% win rate, no trigger
        assert result.is_breached is False
        assert result.trigger is None
        assert result.is_caution is True

    @pytest.mark.asyncio
    async def test_caution_disabled(self, win_rate_config: WinRateConfig) -> None:
        """Caution flag can be disabled."""
        config = win_rate_config.model_copy(update={"enable_caution_flag": False})
        breaker = WinRateCircuitBreaker(config)

        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        result = await breaker.check_win_rate()

        assert result.is_caution is False
        assert result.is_breached is False

    def test_snapshot_has_sufficient_history_property(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Snapshot correctly reports sufficient history."""
        # Below threshold
        for i in range(15):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        snapshot = breaker.calculate_snapshot()
        assert snapshot.has_sufficient_history is False

        # Add more to meet threshold
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i + 15}", True, Decimal("20")))

        snapshot = breaker.calculate_snapshot()
        assert snapshot.has_sufficient_history is True


class TestCircuitBreakerTrigger:
    """Test circuit breaker trigger logic (AC 2)."""

    @pytest.mark.asyncio
    async def test_no_trigger_above_threshold(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """No trigger when win rate above threshold."""
        # 50% win rate (above 40% threshold)
        for i in range(15):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(15):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        result = await breaker.check_win_rate()

        assert result.is_breached is False
        assert result.trigger is None
        assert result.snapshot.win_rate_percent == Decimal("50")

    @pytest.mark.asyncio
    async def test_no_trigger_at_exact_threshold(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """No trigger when win rate exactly at threshold."""
        # 40% win rate (exactly at 40% threshold)
        for i in range(8):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(12):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        result = await breaker.check_win_rate()

        assert result.is_breached is False  # Not < threshold
        assert result.trigger is None
        assert result.snapshot.win_rate_percent == Decimal("40")

    @pytest.mark.asyncio
    async def test_trigger_below_threshold(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Trigger when win rate below threshold."""
        # 30% win rate (below 40% threshold)
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(14):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "trigger-123"}])
        )
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            result = await breaker.check_win_rate()

            assert result.is_breached is True
            assert result.trigger is not None
            assert result.trigger.breaker_type == CircuitBreakerType.WIN_RATE
            assert result.snapshot.win_rate_percent == Decimal("30")

    @pytest.mark.asyncio
    async def test_trigger_updates_system_status(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Trigger updates system status to paused_win_rate."""
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(14):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "trigger-123"}])
        )
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.check_win_rate()

            # Verify system_config was updated
            calls = mock_db.table.call_args_list
            system_config_called = any(
                call[0][0] == "system_config" for call in calls
            )
            assert system_config_called


class TestTradeAnalysis:
    """Test trade analysis functionality (AC 3)."""

    @pytest.mark.asyncio
    async def test_empty_trades_analysis(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis handles empty trade window."""
        analysis = await breaker.analyze_recent_trades()

        assert analysis.losing_streak_current == 0
        assert analysis.winning_streak_current == 0
        assert analysis.profit_factor == Decimal("0")
        assert len(analysis.recent_trades) == 0

    @pytest.mark.asyncio
    async def test_analysis_calculates_losing_streak(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis calculates current losing streak."""
        # WWWLLL (current losing streak of 3)
        for i in range(3):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(3):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.losing_streak_current == 3
        assert analysis.winning_streak_current == 0

    @pytest.mark.asyncio
    async def test_analysis_calculates_winning_streak(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis calculates current winning streak."""
        # LLLWWW (current winning streak of 3)
        for i in range(3):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))
        for i in range(3):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.winning_streak_current == 3
        assert analysis.losing_streak_current == 0

    @pytest.mark.asyncio
    async def test_analysis_profit_factor(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis calculates profit factor correctly."""
        # +60 from wins, -30 from losses = profit factor 2.0
        for i in range(3):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(3):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.profit_factor == Decimal("2")

    @pytest.mark.asyncio
    async def test_analysis_average_pnl(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis calculates average PnL correctly."""
        breaker.add_trade(make_trade("w1", True, Decimal("20")))
        breaker.add_trade(make_trade("w2", True, Decimal("30")))
        breaker.add_trade(make_trade("l1", False, Decimal("-10")))
        breaker.add_trade(make_trade("l2", False, Decimal("-20")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.avg_win_pnl_percent == Decimal("25")  # (20+30)/2
        assert analysis.avg_loss_pnl_percent == Decimal("-15")  # (-10+-20)/2

    @pytest.mark.asyncio
    async def test_analysis_largest_trades(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis finds largest win and loss."""
        breaker.add_trade(make_trade("w1", True, Decimal("20")))
        breaker.add_trade(make_trade("w2", True, Decimal("50")))
        breaker.add_trade(make_trade("l1", False, Decimal("-10")))
        breaker.add_trade(make_trade("l2", False, Decimal("-30")))

        analysis = await breaker.analyze_recent_trades()

        assert analysis.largest_win_percent == Decimal("50")
        assert analysis.largest_loss_percent == Decimal("-30")

    @pytest.mark.asyncio
    async def test_analysis_limits_recent_trades(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Analysis limits recent_trades to 20."""
        for i in range(30):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        analysis = await breaker.analyze_recent_trades()

        assert len(analysis.recent_trades) == 20


class TestCircuitBreakerReset:
    """Test circuit breaker reset functionality (AC 3)."""

    @pytest.mark.asyncio
    async def test_reset_marks_trigger_as_reset(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Reset marks trigger as reset in database."""
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.reset("operator-1")

            mock_db.table.assert_any_call("circuit_breaker_triggers")

    @pytest.mark.asyncio
    async def test_reset_updates_system_status(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Reset updates system status to running."""
        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.reset("operator-1")

            # Verify system_config upsert was called
            calls = mock_db.table.call_args_list
            system_config_called = any(
                call[0][0] == "system_config" for call in calls
            )
            assert system_config_called

    @pytest.mark.asyncio
    async def test_reset_without_clear_history(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Reset preserves trade history by default."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.reset("operator-1", clear_history=False)

            assert len(breaker._trade_window) == 10

    @pytest.mark.asyncio
    async def test_reset_with_clear_history(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Reset can clear trade history."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        mock_db = MagicMock()
        mock_db.table.return_value.update.return_value.eq.return_value.is_.return_value.execute = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.reset("operator-1", clear_history=True)

            assert len(breaker._trade_window) == 0


class TestCanTrade:
    """Test can_trade property."""

    @pytest.mark.asyncio
    async def test_can_trade_above_threshold(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """can_trade is True when above threshold."""
        for i in range(15):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(15):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        await breaker.check_win_rate()
        assert breaker.can_trade is True

    @pytest.mark.asyncio
    async def test_can_trade_false_when_breached(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """can_trade is False when circuit breaker triggered."""
        for i in range(6):
            breaker.add_trade(make_trade(f"w{i}", True, Decimal("20")))
        for i in range(14):
            breaker.add_trade(make_trade(f"l{i}", False, Decimal("-10")))

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "trigger-123"}])
        )
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.check_win_rate()
            assert breaker.can_trade is False


class TestRecordSnapshot:
    """Test snapshot recording to database."""

    @pytest.mark.asyncio
    async def test_record_trade_snapshot(
        self, breaker: WinRateCircuitBreaker
    ) -> None:
        """Record snapshot persists to database."""
        for i in range(10):
            breaker.add_trade(make_trade(f"t{i}", True, Decimal("20")))

        mock_db = MagicMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        with patch.object(
            breaker, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await breaker.record_trade_snapshot()

            mock_db.table.assert_called_with("win_rate_snapshots")


class TestSingletonManagement:
    """Test singleton instance management."""

    def test_reset_singleton(self) -> None:
        """Reset clears singleton instance."""
        reset_win_rate_circuit_breaker()
        # Just verify it doesn't error

    @pytest.mark.asyncio
    async def test_get_singleton_creates_instance(self) -> None:
        """get_win_rate_circuit_breaker creates instance."""
        reset_win_rate_circuit_breaker()

        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data={
                    "value": {
                        "threshold_percent": "40.0",
                        "window_size": 50,
                        "minimum_trades": 20,
                        "enable_caution_flag": True,
                    }
                }
            )
        )
        mock_db.table.return_value.select.return_value.not_.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch(
            "walltrack.core.risk.win_rate_breaker.get_supabase_client",
            new_callable=AsyncMock,
            return_value=mock_db,
        ):
            breaker = await get_win_rate_circuit_breaker()
            assert breaker is not None

        reset_win_rate_circuit_breaker()
