"""Tests for drawdown-based size reduction.

Story 10.5-9: Tests drawdown calculation and position size reduction.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.position_sizing import (
    DrawdownMetrics,
    DrawdownReductionTier,
    PositionSizeRequest,
    PositionSizingConfig,
    SizingDecision,
)
from walltrack.services.risk.drawdown_calculator import (
    DrawdownCalculator,
    reset_drawdown_calculator,
)
from walltrack.services.trade.position_sizer import PositionSizer


class TestDrawdownMetrics:
    """Tests for DrawdownMetrics model."""

    def test_at_peak_when_no_drawdown(self) -> None:
        """Test is_at_peak returns True when at peak."""
        metrics = DrawdownMetrics(
            peak_capital_sol=100.0,
            current_capital_sol=100.0,
            drawdown_pct=0.0,
        )
        assert metrics.is_at_peak is True

    def test_not_at_peak_when_in_drawdown(self) -> None:
        """Test is_at_peak returns False when in drawdown."""
        metrics = DrawdownMetrics(
            peak_capital_sol=100.0,
            current_capital_sol=90.0,
            drawdown_pct=10.0,
        )
        assert metrics.is_at_peak is False

    def test_at_peak_with_tiny_drawdown(self) -> None:
        """Test is_at_peak returns True for very small drawdown."""
        metrics = DrawdownMetrics(
            peak_capital_sol=100.0,
            current_capital_sol=99.99,
            drawdown_pct=0.009,  # Less than 0.01%
        )
        assert metrics.is_at_peak is True


class TestDrawdownReductionTiers:
    """Tests for DrawdownReductionTier configuration."""

    def test_tiers_sorted_by_threshold(self) -> None:
        """Test that tiers are automatically sorted by threshold."""
        config = PositionSizingConfig(
            drawdown_reduction_tiers=[
                DrawdownReductionTier(threshold_pct=15.0, size_reduction_pct=50.0),
                DrawdownReductionTier(threshold_pct=5.0, size_reduction_pct=0.0),
                DrawdownReductionTier(threshold_pct=20.0, size_reduction_pct=100.0),
                DrawdownReductionTier(threshold_pct=10.0, size_reduction_pct=25.0),
            ]
        )

        thresholds = [t.threshold_pct for t in config.drawdown_reduction_tiers]
        assert thresholds == [5.0, 10.0, 15.0, 20.0]

    def test_default_tiers(self) -> None:
        """Test default tier configuration."""
        config = PositionSizingConfig()

        assert len(config.drawdown_reduction_tiers) == 4
        assert config.drawdown_reduction_tiers[0].threshold_pct == 5.0
        assert config.drawdown_reduction_tiers[0].size_reduction_pct == 0.0
        assert config.drawdown_reduction_tiers[3].threshold_pct == 20.0
        assert config.drawdown_reduction_tiers[3].size_reduction_pct == 100.0


class TestDrawdownCalculator:
    """Tests for DrawdownCalculator."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        client = MagicMock()
        return client

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_drawdown_calculator()

    async def test_calculate_drawdown_at_peak(self, mock_client: MagicMock) -> None:
        """Test drawdown calculation when at peak."""
        # Mock current capital = peak capital
        mock_client.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"total_value_sol": "100.0"}])
        )
        mock_client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[{"total_value_sol": "100.0", "timestamp": datetime.now(UTC).isoformat()}]
            )
        )

        calc = DrawdownCalculator(client=mock_client)
        metrics = await calc.calculate()

        assert metrics.drawdown_pct == 0.0
        assert metrics.is_at_peak is True

    async def test_calculate_with_provided_capital(self) -> None:
        """Test calculation with explicitly provided current capital."""
        mock_client = MagicMock()
        # Only mock peak query
        mock_client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[{"total_value_sol": "100.0", "timestamp": datetime.now(UTC).isoformat()}]
            )
        )

        calc = DrawdownCalculator(client=mock_client)
        metrics = await calc.calculate(current_capital_sol=90.0)

        # Peak is 100, current is 90, so 10% drawdown
        assert metrics.drawdown_pct == 10.0
        assert metrics.peak_capital_sol == 100.0
        assert metrics.current_capital_sol == 90.0

    async def test_calculate_days_since_peak(self, mock_client: MagicMock) -> None:
        """Test days since peak calculation."""
        peak_date = datetime.now(UTC) - timedelta(days=5)
        mock_client.table.return_value.select.return_value.gte.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[{"total_value_sol": "100.0", "timestamp": peak_date.isoformat()}]
            )
        )

        calc = DrawdownCalculator(client=mock_client)
        metrics = await calc.calculate(current_capital_sol=95.0)

        assert metrics.days_since_peak == 5


class TestPositionSizerDrawdownReduction:
    """Tests for drawdown reduction in PositionSizer."""

    @pytest.fixture
    def mock_drawdown_calculator(self) -> DrawdownCalculator:
        """Create mock drawdown calculator."""
        calc = MagicMock(spec=DrawdownCalculator)
        return calc

    async def test_no_reduction_when_at_peak(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test no reduction applied when at peak (0% drawdown)."""
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=100.0,
                drawdown_pct=0.0,
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.APPROVED
        assert result.drawdown_reduction_pct == 0.0
        assert result.final_size_sol > 0

    async def test_no_reduction_below_first_tier(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test no reduction when drawdown is below first tier."""
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=97.0,
                drawdown_pct=3.0,  # Below 5% first tier
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.APPROVED
        assert result.drawdown_reduction_pct == 0.0

    async def test_tier_10_pct_applies_25_pct_reduction(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test 10% drawdown tier applies 25% size reduction."""
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=88.0,
                drawdown_pct=12.0,  # Between 10% and 15%
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.drawdown_reduction_pct == 25.0
        assert result.pre_drawdown_size_sol > result.final_size_sol
        # Verify 25% reduction was applied
        expected_size = result.pre_drawdown_size_sol * 0.75
        assert abs(result.final_size_sol - expected_size) < 0.0001

    async def test_tier_15_pct_applies_50_pct_reduction(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test 15% drawdown tier applies 50% size reduction."""
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=82.0,
                drawdown_pct=18.0,  # Between 15% and 20%
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.drawdown_reduction_pct == 50.0
        # Verify 50% reduction was applied
        expected_size = result.pre_drawdown_size_sol * 0.50
        assert abs(result.final_size_sol - expected_size) < 0.0001

    async def test_tier_20_pct_blocks_trading(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test 20%+ drawdown blocks trading (100% reduction)."""
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=75.0,
                drawdown_pct=25.0,  # Above 20%
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.BLOCKED_DRAWDOWN
        assert result.final_size_sol == 0
        assert result.drawdown_reduction_pct == 100.0
        assert result.should_trade is False

    async def test_recovery_restores_normal_sizing(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test that recovery from drawdown restores normal sizing."""
        # First call: in drawdown (15% tier)
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=82.0,
                drawdown_pct=18.0,
            )
        )

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result1 = await sizer.calculate_size(request, audit=False)
        assert result1.drawdown_reduction_pct == 50.0

        # Second call: recovered (below 5% first tier)
        mock_drawdown_calculator.calculate = AsyncMock(
            return_value=DrawdownMetrics(
                peak_capital_sol=100.0,
                current_capital_sol=98.0,
                drawdown_pct=2.0,
            )
        )

        result2 = await sizer.calculate_size(request, audit=False)
        assert result2.drawdown_reduction_pct == 0.0
        assert result2.final_size_sol > result1.final_size_sol

    async def test_disabled_drawdown_reduction(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test that drawdown reduction can be disabled."""
        config = PositionSizingConfig(drawdown_reduction_enabled=False)
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        # Should not have called drawdown calculator
        mock_drawdown_calculator.calculate.assert_not_called()
        assert result.drawdown_reduction_pct == 0.0
        assert result.drawdown_metrics is None

    async def test_drawdown_metrics_in_result(
        self, mock_drawdown_calculator: MagicMock
    ) -> None:
        """Test drawdown metrics are included in result."""
        metrics = DrawdownMetrics(
            peak_capital_sol=100.0,
            current_capital_sol=88.0,
            drawdown_pct=12.0,
            peak_date=datetime.now(UTC) - timedelta(days=3),
            days_since_peak=3,
        )
        mock_drawdown_calculator.calculate = AsyncMock(return_value=metrics)

        config = PositionSizingConfig()
        sizer = PositionSizer(drawdown_calculator=mock_drawdown_calculator)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.drawdown_metrics is not None
        assert result.drawdown_metrics.drawdown_pct == 12.0
        assert result.drawdown_metrics.days_since_peak == 3
