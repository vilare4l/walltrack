"""Unit tests for position sizer service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from walltrack.services.trade.position_sizer import PositionSizer
from walltrack.models.position_sizing import (
    PositionSizingConfig,
    PositionSizeRequest,
    ConvictionTier,
    SizingDecision,
    SizingMode,
)


@pytest.fixture
def default_config() -> PositionSizingConfig:
    """Create default position sizing config."""
    return PositionSizingConfig(
        base_position_pct=2.0,
        min_position_sol=0.01,
        max_position_sol=1.0,
        high_conviction_multiplier=1.5,
        standard_conviction_multiplier=1.0,
        high_conviction_threshold=0.85,
        min_conviction_threshold=0.70,
        max_concurrent_positions=5,
        max_capital_allocation_pct=50.0,
        reserve_sol=0.05,
    )


@pytest.fixture
def position_sizer(default_config: PositionSizingConfig) -> PositionSizer:
    """Create position sizer with mock repo."""
    mock_repo = MagicMock()
    mock_repo.get_config = AsyncMock(return_value=default_config)
    mock_repo.save_audit = AsyncMock(return_value="audit-id")

    sizer = PositionSizer(config_repo=mock_repo)
    sizer._config_cache = default_config
    return sizer


class TestConvictionTiers:
    """Tests for conviction tier determination."""

    async def test_high_conviction_score(self, position_sizer: PositionSizer) -> None:
        """Test high conviction for score >= 0.85."""
        request = PositionSizeRequest(
            signal_score=0.90,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.conviction_tier == ConvictionTier.HIGH
        assert result.multiplier == 1.5

    async def test_standard_conviction_score(self, position_sizer: PositionSizer) -> None:
        """Test standard conviction for score 0.70-0.84."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.conviction_tier == ConvictionTier.STANDARD
        assert result.multiplier == 1.0

    async def test_low_score_skipped(self, position_sizer: PositionSizer) -> None:
        """Test scores below threshold are skipped."""
        request = PositionSizeRequest(
            signal_score=0.65,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.conviction_tier == ConvictionTier.NONE
        assert result.decision == SizingDecision.SKIPPED_LOW_SCORE
        assert result.final_size_sol == 0
        assert not result.should_trade


class TestSizeCalculation:
    """Tests for position size calculation."""

    async def test_base_size_calculation(self, position_sizer: PositionSizer) -> None:
        """Test base size is 2% of available capital (capped by allocation %)."""
        request = PositionSizeRequest(
            signal_score=0.75,  # Standard conviction
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        # Total capital = 10.0
        # Max allocation = 10.0 * 50% = 5.0
        # Usable = 10.0 - 0.05 reserve = 9.95
        # Capital for base = min(9.95, 5.0) = 5.0
        # Base = 5.0 * 2% = 0.10
        # With 1.0x multiplier = 0.10
        assert result.base_size_sol == pytest.approx(0.10, rel=0.01)
        assert result.final_size_sol == pytest.approx(0.10, rel=0.01)
        assert result.should_trade

    async def test_high_conviction_multiplier_applied(
        self, position_sizer: PositionSizer
    ) -> None:
        """Test 1.5x multiplier for high conviction."""
        request = PositionSizeRequest(
            signal_score=0.90,  # High conviction
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        # Capital for base = min(9.95, 5.0) = 5.0
        # Base = 5.0 * 2% = 0.10
        # With 1.5x multiplier = 0.15
        assert result.multiplier == 1.5
        assert result.calculated_size_sol == pytest.approx(0.15, rel=0.01)


class TestLimitsAndValidation:
    """Tests for limit enforcement."""

    async def test_max_position_limit(self, position_sizer: PositionSizer) -> None:
        """Test position capped at max_position_sol."""
        request = PositionSizeRequest(
            signal_score=0.95,
            available_balance_sol=100.0,  # Large balance
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.final_size_sol == 1.0  # Capped at max
        assert result.reduction_applied is True
        assert result.decision == SizingDecision.REDUCED

    async def test_max_concurrent_positions_blocks(
        self, position_sizer: PositionSizer
    ) -> None:
        """Test trade blocked when max positions reached."""
        request = PositionSizeRequest(
            signal_score=0.90,
            available_balance_sol=10.0,
            current_position_count=5,  # At max
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.SKIPPED_MAX_POSITIONS
        assert result.final_size_sol == 0
        assert not result.should_trade

    async def test_insufficient_balance_skips(
        self, position_sizer: PositionSizer
    ) -> None:
        """Test trade skipped when balance insufficient."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=0.06,  # Just above reserve
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        # Usable = 0.06 - 0.05 = 0.01
        # Base = 0.01 * 2% = 0.0002, below min 0.01
        assert result.decision in [
            SizingDecision.SKIPPED_MIN_SIZE,
            SizingDecision.SKIPPED_NO_BALANCE,
        ]
        assert not result.should_trade


class TestConfigValidation:
    """Tests for config model validation."""

    def test_threshold_ordering_validated(self) -> None:
        """Test high threshold must be > min threshold."""
        with pytest.raises(ValueError, match="high_conviction_threshold must be"):
            PositionSizingConfig(
                high_conviction_threshold=0.70,
                min_conviction_threshold=0.75,
            )

    def test_position_limits_validated(self) -> None:
        """Test max must be >= min."""
        with pytest.raises(ValueError, match="max_position_sol must be"):
            PositionSizingConfig(
                min_position_sol=1.0,
                max_position_sol=0.5,
            )

    def test_valid_config_passes(self) -> None:
        """Test valid config passes validation."""
        config = PositionSizingConfig(
            base_position_pct=3.0,
            high_conviction_threshold=0.90,
            min_conviction_threshold=0.75,
        )
        assert config.base_position_pct == 3.0


class TestShouldTradeProperty:
    """Tests for should_trade property."""

    async def test_approved_should_trade(self, position_sizer: PositionSizer) -> None:
        """Test approved decision means should_trade=True."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.APPROVED
        assert result.should_trade is True

    async def test_reduced_should_trade(self, position_sizer: PositionSizer) -> None:
        """Test reduced decision means should_trade=True."""
        request = PositionSizeRequest(
            signal_score=0.95,
            available_balance_sol=100.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.REDUCED
        assert result.should_trade is True

    async def test_skipped_should_not_trade(self, position_sizer: PositionSizer) -> None:
        """Test skipped decision means should_trade=False."""
        request = PositionSizeRequest(
            signal_score=0.50,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
        )

        result = await position_sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.SKIPPED_LOW_SCORE
        assert result.should_trade is False


class TestRiskBasedSizing:
    """Tests for risk-based position sizing (Story 10.5-8)."""

    @pytest.fixture
    def risk_based_config(self) -> PositionSizingConfig:
        """Create risk-based sizing config."""
        return PositionSizingConfig(
            sizing_mode=SizingMode.RISK_BASED,
            risk_per_trade_pct=1.0,  # 1% risk per trade
            default_stop_loss_pct=10.0,  # 10% stop loss
            min_position_sol=0.1,
            max_position_sol=100.0,
            high_conviction_multiplier=1.5,
            standard_conviction_multiplier=1.0,
            high_conviction_threshold=0.85,
            min_conviction_threshold=0.70,
            max_concurrent_positions=5,
            max_capital_allocation_pct=80.0,
            reserve_sol=0.05,
        )

    @pytest.fixture
    def risk_based_sizer(self, risk_based_config: PositionSizingConfig) -> PositionSizer:
        """Create position sizer with risk-based config."""
        mock_repo = MagicMock()
        mock_repo.get_config = AsyncMock(return_value=risk_based_config)
        mock_repo.save_audit = AsyncMock(return_value="audit-id")

        sizer = PositionSizer(config_repo=mock_repo)
        sizer._config_cache = risk_based_config
        return sizer

    async def test_basic_risk_based_calculation(
        self, risk_based_sizer: PositionSizer
    ) -> None:
        """Test: 1% risk on 1000 SOL with 10% SL = 100 SOL position."""
        request = PositionSizeRequest(
            signal_score=0.75,  # Standard conviction (1.0x multiplier)
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=10.0,  # 10% stop loss
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        # max_risk = 1000 * 1% = 10 SOL
        # position = 10 / 0.10 = 100 SOL
        assert result.sizing_mode == SizingMode.RISK_BASED
        assert result.base_size_sol == pytest.approx(100.0, rel=0.01)
        assert result.final_size_sol == pytest.approx(100.0, rel=0.01)
        assert result.risk_amount_sol == pytest.approx(10.0, rel=0.01)  # 100 * 10%
        assert result.stop_loss_pct_used == 10.0
        assert result.should_trade

    async def test_tighter_stop_larger_position(
        self, risk_based_sizer: PositionSizer, risk_based_config: PositionSizingConfig
    ) -> None:
        """Test: Tighter SL allows larger position (capped at max)."""
        # Update max to see the raw calculation
        risk_based_config.max_position_sol = 500.0
        risk_based_sizer._config_cache = risk_based_config

        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=5.0,  # Tighter 5% stop loss
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        # max_risk = 1000 * 1% = 10 SOL
        # position = 10 / 0.05 = 200 SOL
        assert result.base_size_sol == pytest.approx(200.0, rel=0.01)
        assert result.final_size_sol == pytest.approx(200.0, rel=0.01)
        assert result.risk_amount_sol == pytest.approx(10.0, rel=0.01)  # Still 10 SOL
        assert result.stop_loss_pct_used == 5.0

    async def test_wider_stop_smaller_position(
        self, risk_based_sizer: PositionSizer
    ) -> None:
        """Test: Wider SL requires smaller position to maintain risk."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=20.0,  # Wider 20% stop loss
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        # max_risk = 1000 * 1% = 10 SOL
        # position = 10 / 0.20 = 50 SOL
        assert result.base_size_sol == pytest.approx(50.0, rel=0.01)
        assert result.final_size_sol == pytest.approx(50.0, rel=0.01)
        assert result.risk_amount_sol == pytest.approx(10.0, rel=0.01)  # Still 10 SOL
        assert result.stop_loss_pct_used == 20.0

    async def test_high_conviction_multiplier_applied(
        self, risk_based_sizer: PositionSizer
    ) -> None:
        """Test: High conviction applies 1.5x multiplier."""
        request = PositionSizeRequest(
            signal_score=0.90,  # High conviction
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=10.0,
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        # max_risk = 1000 * 1% = 10 SOL
        # base position = 10 / 0.10 = 100 SOL
        # with 1.5x multiplier = 150 SOL (but capped at 100 by max_position)
        assert result.multiplier == 1.5
        assert result.calculated_size_sol == pytest.approx(150.0, rel=0.01)
        assert result.final_size_sol == pytest.approx(100.0, rel=0.01)  # Capped
        assert result.reduction_applied is True

    async def test_max_position_cap(
        self, risk_based_sizer: PositionSizer, risk_based_config: PositionSizingConfig
    ) -> None:
        """Test: Position capped at max_position_sol."""
        risk_based_config.max_position_sol = 50.0
        risk_based_sizer._config_cache = risk_based_config

        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=10.0,
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        # base position = 100 SOL, capped at 50
        assert result.base_size_sol == pytest.approx(100.0, rel=0.01)
        assert result.final_size_sol == pytest.approx(50.0, rel=0.01)
        assert result.reduction_applied is True
        assert "max_position_sol" in str(result.reduction_reason)

    async def test_uses_default_stop_loss_when_not_provided(
        self, risk_based_sizer: PositionSizer
    ) -> None:
        """Test: Uses config default_stop_loss_pct when not in request."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=1000.0,
            current_position_count=0,
            current_allocated_sol=0,
            # stop_loss_pct not provided, should use default 10%
        )

        result = await risk_based_sizer.calculate_size(request, audit=False)

        assert result.stop_loss_pct_used == 10.0  # Default
        assert result.base_size_sol == pytest.approx(100.0, rel=0.01)

    async def test_fixed_percent_mode_ignores_stop_loss(
        self, position_sizer: PositionSizer
    ) -> None:
        """Test: Fixed percent mode ignores stop_loss_pct."""
        request = PositionSizeRequest(
            signal_score=0.75,
            available_balance_sol=10.0,
            current_position_count=0,
            current_allocated_sol=0,
            stop_loss_pct=5.0,  # Should be ignored in fixed_percent mode
        )

        result = await position_sizer.calculate_size(request, audit=False)

        # Fixed percent uses base_position_pct, not risk calculation
        assert result.sizing_mode == SizingMode.FIXED_PERCENT
        # Should use same calculation as before stop_loss was added
        assert result.base_size_sol == pytest.approx(0.10, rel=0.01)
