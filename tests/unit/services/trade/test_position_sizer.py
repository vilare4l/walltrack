"""Unit tests for position sizer service."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from walltrack.services.trade.position_sizer import PositionSizer
from walltrack.models.position_sizing import (
    PositionSizingConfig,
    PositionSizeRequest,
    ConvictionTier,
    SizingDecision,
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
