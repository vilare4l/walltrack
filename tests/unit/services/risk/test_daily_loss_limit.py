"""Tests for daily loss limit tracking and enforcement.

Story 10.5-10: Tests daily P&L calculation and limit enforcement.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.position_sizing import (
    DailyLossMetrics,
    PositionSizeRequest,
    PositionSizingConfig,
    SizingDecision,
)
from walltrack.services.risk.daily_loss_tracker import (
    DailyLossTracker,
    reset_daily_loss_tracker,
)
from walltrack.services.trade.position_sizer import PositionSizer


class TestDailyLossMetrics:
    """Tests for DailyLossMetrics model."""

    def test_limit_usage_zero_when_profitable(self) -> None:
        """Test limit_usage_pct is 0 when profitable."""
        metrics = DailyLossMetrics(
            total_pnl_sol=5.0,
            pnl_pct=5.0,
            daily_limit_pct=5.0,
        )
        assert metrics.limit_usage_pct == 0.0

    def test_limit_usage_percentage_calculated(self) -> None:
        """Test limit_usage_pct calculation."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-2.5,
            pnl_pct=-2.5,  # 2.5% loss
            daily_limit_pct=5.0,  # 5% limit
        )
        # 2.5% / 5% = 50% usage
        assert metrics.limit_usage_pct == 50.0

    def test_limit_usage_caps_at_100(self) -> None:
        """Test limit_usage_pct caps at 100%."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-10.0,
            pnl_pct=-10.0,  # 10% loss
            daily_limit_pct=5.0,  # 5% limit
        )
        assert metrics.limit_usage_pct == 100.0


class TestDailyLossTracker:
    """Tests for DailyLossTracker."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        return client

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_daily_loss_tracker()

    async def test_no_loss_returns_full_limit(self, mock_client: MagicMock) -> None:
        """Test metrics when no losses today."""
        # Mock no closed positions today
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        # Mock no open positions
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tracker = DailyLossTracker(
            client=mock_client,
            daily_limit_pct=5.0,
        )

        metrics = await tracker.get_daily_metrics(starting_capital_sol=100.0)

        assert metrics.total_pnl_sol == 0.0
        assert metrics.is_limit_hit is False
        assert metrics.is_warning_zone is False
        assert metrics.limit_remaining_pct == 5.0

    async def test_loss_under_limit_allowed(self, mock_client: MagicMock) -> None:
        """Test that trading is allowed when loss is under limit."""
        # Mock closed position with -3 SOL realized P&L (3% of 100 starting)
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"realized_pnl": -3.0}])
        )
        # Mock no unrealized P&L
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tracker = DailyLossTracker(
            client=mock_client,
            daily_limit_pct=5.0,
        )

        allowed, reason, metrics = await tracker.is_entry_allowed(
            starting_capital_sol=100.0
        )

        assert allowed is True
        assert reason is None
        assert metrics.is_limit_hit is False
        assert metrics.limit_remaining_pct == 2.0  # 5% - 3%

    async def test_loss_at_limit_blocks_entries(self, mock_client: MagicMock) -> None:
        """Test that entries are blocked when loss reaches limit."""
        # Mock closed position with -5 SOL realized P&L (5% of 100)
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"realized_pnl": -5.0}])
        )
        # Mock no unrealized P&L
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tracker = DailyLossTracker(
            client=mock_client,
            daily_limit_pct=5.0,
        )

        allowed, reason, metrics = await tracker.is_entry_allowed(
            starting_capital_sol=100.0
        )

        assert allowed is False
        assert "Daily loss limit reached" in reason
        assert metrics.is_limit_hit is True
        assert metrics.limit_remaining_pct == 0.0

    async def test_warning_zone_at_80_percent(self, mock_client: MagicMock) -> None:
        """Test warning zone triggered at 80% of limit."""
        # Mock closed position with -4 SOL realized P&L (4% = 80% of 5% limit)
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"realized_pnl": -4.0}])
        )
        # Mock no unrealized P&L
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        tracker = DailyLossTracker(
            client=mock_client,
            daily_limit_pct=5.0,
            warning_threshold_pct=80.0,
        )

        allowed, reason, metrics = await tracker.is_entry_allowed(
            starting_capital_sol=100.0
        )

        assert allowed is True  # Still allowed
        assert metrics.is_warning_zone is True
        assert metrics.is_limit_hit is False

    async def test_unrealized_pnl_included(self, mock_client: MagicMock) -> None:
        """Test that unrealized P&L is included in calculation."""
        # Mock closed position with -2 SOL realized
        mock_client.table.return_value.select.return_value.eq.return_value.gte.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"realized_pnl": -2.0}])
        )
        # Mock open position with -3 SOL unrealized
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"unrealized_pnl": -3.0}])
        )

        tracker = DailyLossTracker(
            client=mock_client,
            daily_limit_pct=5.0,
        )

        metrics = await tracker.get_daily_metrics(starting_capital_sol=100.0)

        # Total: -2 + -3 = -5 SOL = 5%
        assert metrics.total_pnl_sol == -5.0
        assert metrics.realized_pnl_sol == -2.0
        assert metrics.unrealized_pnl_sol == -3.0
        assert metrics.is_limit_hit is True


class TestPositionSizerDailyLossIntegration:
    """Tests for daily loss limit in PositionSizer."""

    @pytest.fixture
    def mock_daily_loss_tracker(self) -> DailyLossTracker:
        """Create mock daily loss tracker."""
        tracker = MagicMock(spec=DailyLossTracker)
        return tracker

    async def test_no_block_when_under_limit(
        self, mock_daily_loss_tracker: MagicMock
    ) -> None:
        """Test no blocking when daily loss under limit."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-2.0,
            pnl_pct=-2.0,
            daily_limit_pct=5.0,
            limit_remaining_pct=3.0,
            is_limit_hit=False,
            is_warning_zone=False,
        )
        mock_daily_loss_tracker.is_entry_allowed = AsyncMock(
            return_value=(True, None, metrics)
        )

        config = PositionSizingConfig(
            daily_loss_limit_enabled=True,
            daily_loss_limit_pct=5.0,
            # Disable drawdown to isolate test
            drawdown_reduction_enabled=False,
        )
        sizer = PositionSizer(daily_loss_tracker=mock_daily_loss_tracker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision in (SizingDecision.APPROVED, SizingDecision.REDUCED)
        assert result.daily_loss_blocked is False
        assert result.daily_loss_metrics is not None
        assert result.daily_loss_metrics.pnl_pct == -2.0

    async def test_blocks_when_limit_hit(
        self, mock_daily_loss_tracker: MagicMock
    ) -> None:
        """Test blocking when daily loss limit hit."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-6.0,
            pnl_pct=-6.0,
            daily_limit_pct=5.0,
            limit_remaining_pct=0.0,
            is_limit_hit=True,
            is_warning_zone=False,
        )
        mock_daily_loss_tracker.is_entry_allowed = AsyncMock(
            return_value=(False, "Daily loss limit reached: -6.00% (limit: 5%)", metrics)
        )

        config = PositionSizingConfig(
            daily_loss_limit_enabled=True,
            daily_loss_limit_pct=5.0,
        )
        sizer = PositionSizer(daily_loss_tracker=mock_daily_loss_tracker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.BLOCKED_DAILY_LOSS
        assert result.daily_loss_blocked is True
        assert result.final_size_sol == 0
        assert result.should_trade is False

    async def test_disabled_daily_loss_limit(
        self, mock_daily_loss_tracker: MagicMock
    ) -> None:
        """Test that daily loss limit can be disabled."""
        config = PositionSizingConfig(
            daily_loss_limit_enabled=False,
            drawdown_reduction_enabled=False,
        )
        sizer = PositionSizer(daily_loss_tracker=mock_daily_loss_tracker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        # Should not have called daily loss tracker
        mock_daily_loss_tracker.is_entry_allowed.assert_not_called()
        assert result.daily_loss_metrics is None
        assert result.daily_loss_blocked is False

    async def test_daily_loss_check_before_other_checks(
        self, mock_daily_loss_tracker: MagicMock
    ) -> None:
        """Test daily loss check happens before conviction/position checks."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-6.0,
            pnl_pct=-6.0,
            daily_limit_pct=5.0,
            is_limit_hit=True,
        )
        mock_daily_loss_tracker.is_entry_allowed = AsyncMock(
            return_value=(False, "Daily loss limit reached", metrics)
        )

        config = PositionSizingConfig(
            daily_loss_limit_enabled=True,
            daily_loss_limit_pct=5.0,
        )
        sizer = PositionSizer(daily_loss_tracker=mock_daily_loss_tracker)
        sizer._config_cache = config

        # Even with perfect score and room for positions, should be blocked
        request = PositionSizeRequest(
            signal_score=0.95,  # High score
            available_balance_sol=100.0,  # Plenty of balance
            current_position_count=0,  # No positions
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.BLOCKED_DAILY_LOSS
        assert result.daily_loss_blocked is True

    async def test_warning_zone_allows_trading(
        self, mock_daily_loss_tracker: MagicMock
    ) -> None:
        """Test that warning zone still allows trading."""
        metrics = DailyLossMetrics(
            total_pnl_sol=-4.0,
            pnl_pct=-4.0,
            daily_limit_pct=5.0,
            limit_remaining_pct=1.0,
            is_limit_hit=False,
            is_warning_zone=True,
        )
        mock_daily_loss_tracker.is_entry_allowed = AsyncMock(
            return_value=(True, None, metrics)
        )

        config = PositionSizingConfig(
            daily_loss_limit_enabled=True,
            daily_loss_limit_pct=5.0,
            drawdown_reduction_enabled=False,
        )
        sizer = PositionSizer(daily_loss_tracker=mock_daily_loss_tracker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision in (SizingDecision.APPROVED, SizingDecision.REDUCED)
        assert result.daily_loss_blocked is False
        assert result.daily_loss_metrics.is_warning_zone is True


class TestDailyLossConfigValidation:
    """Tests for daily loss config fields."""

    def test_default_daily_loss_config(self) -> None:
        """Test default daily loss configuration."""
        config = PositionSizingConfig()

        assert config.daily_loss_limit_enabled is True
        assert config.daily_loss_limit_pct == 5.0
        assert config.daily_loss_warning_threshold_pct == 80.0

    def test_custom_daily_loss_config(self) -> None:
        """Test custom daily loss configuration."""
        config = PositionSizingConfig(
            daily_loss_limit_enabled=True,
            daily_loss_limit_pct=3.0,
            daily_loss_warning_threshold_pct=75.0,
        )

        assert config.daily_loss_limit_pct == 3.0
        assert config.daily_loss_warning_threshold_pct == 75.0

    def test_daily_loss_limit_bounds(self) -> None:
        """Test daily loss limit bounds."""
        # Valid: within bounds
        config = PositionSizingConfig(daily_loss_limit_pct=1.0)
        assert config.daily_loss_limit_pct == 1.0

        config = PositionSizingConfig(daily_loss_limit_pct=25.0)
        assert config.daily_loss_limit_pct == 25.0

        # Invalid: below minimum
        with pytest.raises(ValueError):
            PositionSizingConfig(daily_loss_limit_pct=0.5)

        # Invalid: above maximum
        with pytest.raises(ValueError):
            PositionSizingConfig(daily_loss_limit_pct=30.0)
