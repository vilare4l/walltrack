"""Tests for concentration limits tracking and enforcement.

Story 10.5-11: Tests token and cluster concentration limits.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.position_sizing import (
    ConcentrationMetrics,
    PositionSizeRequest,
    PositionSizingConfig,
    SizingDecision,
)
from walltrack.services.risk.concentration_checker import (
    ConcentrationChecker,
    reset_concentration_checker,
)
from walltrack.services.trade.position_sizer import PositionSizer


class TestConcentrationMetrics:
    """Tests for ConcentrationMetrics model."""

    def test_is_blocked_when_duplicate(self) -> None:
        """Test is_blocked is True when duplicate position exists."""
        metrics = ConcentrationMetrics(is_duplicate=True)
        assert metrics.is_blocked is True

    def test_is_blocked_when_token_limit_hit(self) -> None:
        """Test is_blocked is True when token limit hit."""
        metrics = ConcentrationMetrics(is_token_limit_hit=True)
        assert metrics.is_blocked is True

    def test_is_blocked_when_cluster_limit_hit(self) -> None:
        """Test is_blocked is True when cluster limit hit."""
        metrics = ConcentrationMetrics(is_cluster_limit_hit=True)
        assert metrics.is_blocked is True

    def test_is_blocked_when_cluster_max_positions(self) -> None:
        """Test is_blocked is True when cluster max positions reached."""
        metrics = ConcentrationMetrics(is_cluster_max_positions=True)
        assert metrics.is_blocked is True

    def test_not_blocked_when_ok(self) -> None:
        """Test is_blocked is False when no limits hit."""
        metrics = ConcentrationMetrics()
        assert metrics.is_blocked is False


class TestConcentrationChecker:
    """Tests for ConcentrationChecker."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Supabase client."""
        return MagicMock()

    @pytest.fixture(autouse=True)
    def reset_singleton(self) -> None:
        """Reset singleton between tests."""
        reset_concentration_checker()

    async def test_allows_first_position(self, mock_client: MagicMock) -> None:
        """Test allows trade when no existing positions."""
        # Mock empty portfolio
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        config = PositionSizingConfig(concentration_limits_enabled=True)
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenA123",
            requested_amount_sol=1.0,
            portfolio_value_sol=0.0,  # First position
        )

        assert metrics.is_blocked is False
        assert metrics.max_allowed_sol == 1.0

    async def test_blocks_duplicate_position(self, mock_client: MagicMock) -> None:
        """Test blocks when position already exists for token."""
        # Mock existing position
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 10.0, "unrealized_pnl": 0}])
        )
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"id": "existing-pos-id"}])
        )
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 10.0, "unrealized_pnl": 0}])
        )

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            block_duplicate_positions=True,
        )
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenA123",
            requested_amount_sol=1.0,
            portfolio_value_sol=100.0,
        )

        assert metrics.is_blocked is True
        assert metrics.is_duplicate is True
        assert "already exists" in (metrics.block_reason or "")
        assert metrics.max_allowed_sol == 0.0

    async def test_reduces_to_token_limit(self, mock_client: MagicMock) -> None:
        """Test reduces size to respect token concentration limit."""
        # Mock portfolio with 100 SOL, token already has 20 SOL (20%)
        # With 25% limit, only 5 more SOL allowed
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 100.0, "unrealized_pnl": 0}])
        )
        # No duplicate position
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        # Token already has 20 SOL
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 20.0, "unrealized_pnl": 0}])
        )

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            max_token_concentration_pct=25.0,
        )
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenA123",
            requested_amount_sol=10.0,  # Request 10 SOL
            portfolio_value_sol=100.0,
        )

        assert metrics.is_blocked is False
        assert metrics.was_adjusted is True
        assert metrics.max_allowed_sol == 5.0  # Only 5 SOL allowed (25 - 20)

    async def test_blocks_when_token_at_limit(self, mock_client: MagicMock) -> None:
        """Test blocks when token already at concentration limit."""
        # Mock portfolio with 100 SOL, token already has 25 SOL (25% = at limit)
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 100.0, "unrealized_pnl": 0}])
        )
        # No duplicate position
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        # Token already at 25 SOL
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 25.0, "unrealized_pnl": 0}])
        )

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            max_token_concentration_pct=25.0,
        )
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenA123",
            requested_amount_sol=5.0,
            portfolio_value_sol=100.0,
        )

        assert metrics.is_blocked is True
        assert metrics.is_token_limit_hit is True
        assert metrics.max_allowed_sol == 0.0

    async def test_blocks_cluster_max_positions(self, mock_client: MagicMock) -> None:
        """Test blocks when cluster max positions reached."""
        # Mock portfolio value
        mock_client.table.return_value.select.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"entry_amount_sol": 100.0, "unrealized_pnl": 0}])
        )
        # No duplicate
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        # Token has 0 SOL (new token)
        mock_client.table.return_value.select.return_value.eq.return_value.in_.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[
                {"entry_amount_sol": 10.0, "unrealized_pnl": 0},
                {"entry_amount_sol": 10.0, "unrealized_pnl": 0},
                {"entry_amount_sol": 10.0, "unrealized_pnl": 0},
            ])
        )

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            max_positions_per_cluster=3,
        )
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenNew123",
            requested_amount_sol=5.0,
            cluster_id="DeFi",
            portfolio_value_sol=100.0,
        )

        assert metrics.is_blocked is True
        assert metrics.is_cluster_max_positions is True
        assert "Max positions in cluster" in (metrics.block_reason or "")

    async def test_disabled_allows_all(self, mock_client: MagicMock) -> None:
        """Test all entries allowed when concentration limits disabled."""
        config = PositionSizingConfig(concentration_limits_enabled=False)
        checker = ConcentrationChecker(client=mock_client, config=config)

        metrics = await checker.check_entry(
            token_address="TokenA123",
            requested_amount_sol=1000.0,
            portfolio_value_sol=100.0,
        )

        assert metrics.is_blocked is False
        assert metrics.max_allowed_sol == 1000.0


class TestPositionSizerConcentrationIntegration:
    """Tests for concentration limits in PositionSizer."""

    @pytest.fixture
    def mock_concentration_checker(self) -> MagicMock:
        """Create mock concentration checker."""
        return MagicMock(spec=ConcentrationChecker)

    async def test_no_block_when_under_limit(
        self, mock_concentration_checker: MagicMock
    ) -> None:
        """Test no blocking when concentration under limit."""
        metrics = ConcentrationMetrics(
            token_address="TokenA123",
            requested_amount_sol=1.0,
            max_allowed_sol=1.0,
        )
        mock_concentration_checker.check_entry = AsyncMock(return_value=metrics)
        mock_concentration_checker.update_config = MagicMock()

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            # Disable other features to isolate test
            drawdown_reduction_enabled=False,
            daily_loss_limit_enabled=False,
        )
        sizer = PositionSizer(concentration_checker=mock_concentration_checker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
            token_address="TokenA123",
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision in (SizingDecision.APPROVED, SizingDecision.REDUCED)
        assert result.concentration_blocked is False
        assert result.concentration_metrics is not None

    async def test_blocks_when_duplicate(
        self, mock_concentration_checker: MagicMock
    ) -> None:
        """Test blocking when duplicate position exists."""
        metrics = ConcentrationMetrics(
            token_address="TokenA123",
            is_duplicate=True,
            block_reason="Position already exists for this token",
            max_allowed_sol=0.0,
        )
        mock_concentration_checker.check_entry = AsyncMock(return_value=metrics)
        mock_concentration_checker.update_config = MagicMock()

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            drawdown_reduction_enabled=False,
            daily_loss_limit_enabled=False,
        )
        sizer = PositionSizer(concentration_checker=mock_concentration_checker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
            token_address="TokenA123",
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.BLOCKED_DUPLICATE
        assert result.concentration_blocked is True
        assert result.final_size_sol == 0
        assert result.should_trade is False

    async def test_blocks_when_concentration_limit_hit(
        self, mock_concentration_checker: MagicMock
    ) -> None:
        """Test blocking when concentration limit hit."""
        metrics = ConcentrationMetrics(
            token_address="TokenA123",
            is_token_limit_hit=True,
            block_reason="Token concentration at limit (25%)",
            max_allowed_sol=0.0,
        )
        mock_concentration_checker.check_entry = AsyncMock(return_value=metrics)
        mock_concentration_checker.update_config = MagicMock()

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            drawdown_reduction_enabled=False,
            daily_loss_limit_enabled=False,
        )
        sizer = PositionSizer(concentration_checker=mock_concentration_checker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
            token_address="TokenA123",
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.BLOCKED_CONCENTRATION
        assert result.concentration_blocked is True

    async def test_reduces_size_when_adjusted(
        self, mock_concentration_checker: MagicMock
    ) -> None:
        """Test size reduction when concentration adjusted."""
        # This mock will receive whatever size the sizer calculates,
        # then return an adjusted lower max_allowed
        metrics = ConcentrationMetrics(
            token_address="TokenA123",
            requested_amount_sol=0.5,
            max_allowed_sol=0.05,  # Reduced to 0.05 SOL
            was_adjusted=True,
        )
        mock_concentration_checker.check_entry = AsyncMock(return_value=metrics)
        mock_concentration_checker.update_config = MagicMock()

        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            drawdown_reduction_enabled=False,
            daily_loss_limit_enabled=False,
        )
        sizer = PositionSizer(concentration_checker=mock_concentration_checker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
            token_address="TokenA123",
        )

        result = await sizer.calculate_size(request, audit=False)

        assert result.decision == SizingDecision.REDUCED
        assert result.concentration_adjusted is True
        assert result.final_size_sol == 0.05  # Reduced to concentration limit
        assert result.pre_concentration_size_sol > 0.05  # Was higher before

    async def test_disabled_concentration_limit(
        self, mock_concentration_checker: MagicMock
    ) -> None:
        """Test that concentration limits can be disabled."""
        config = PositionSizingConfig(
            concentration_limits_enabled=False,
            drawdown_reduction_enabled=False,
            daily_loss_limit_enabled=False,
        )
        sizer = PositionSizer(concentration_checker=mock_concentration_checker)
        sizer._config_cache = config

        request = PositionSizeRequest(
            signal_score=0.85,
            available_balance_sol=10.0,
            current_position_count=0,
            token_address="TokenA123",
        )

        result = await sizer.calculate_size(request, audit=False)

        # Should not have called concentration checker
        mock_concentration_checker.check_entry.assert_not_called()
        assert result.concentration_metrics is not None
        # Metrics should show no adjustment since limits disabled
        assert result.concentration_blocked is False


class TestConcentrationConfigValidation:
    """Tests for concentration config fields."""

    def test_default_concentration_config(self) -> None:
        """Test default concentration configuration."""
        config = PositionSizingConfig()

        assert config.concentration_limits_enabled is True
        assert config.max_token_concentration_pct == 25.0
        assert config.max_cluster_concentration_pct == 50.0
        assert config.max_positions_per_cluster == 3
        assert config.block_duplicate_positions is True

    def test_custom_concentration_config(self) -> None:
        """Test custom concentration configuration."""
        config = PositionSizingConfig(
            concentration_limits_enabled=True,
            max_token_concentration_pct=20.0,
            max_cluster_concentration_pct=40.0,
            max_positions_per_cluster=5,
            block_duplicate_positions=False,
        )

        assert config.max_token_concentration_pct == 20.0
        assert config.max_cluster_concentration_pct == 40.0
        assert config.max_positions_per_cluster == 5
        assert config.block_duplicate_positions is False

    def test_token_concentration_bounds(self) -> None:
        """Test token concentration bounds."""
        # Valid: within bounds
        config = PositionSizingConfig(max_token_concentration_pct=10.0)
        assert config.max_token_concentration_pct == 10.0

        config = PositionSizingConfig(max_token_concentration_pct=100.0)
        assert config.max_token_concentration_pct == 100.0

        # Invalid: below minimum
        with pytest.raises(ValueError):
            PositionSizingConfig(max_token_concentration_pct=3.0)  # min is 5.0

    def test_cluster_concentration_bounds(self) -> None:
        """Test cluster concentration bounds."""
        # Valid: within bounds
        config = PositionSizingConfig(max_cluster_concentration_pct=20.0)
        assert config.max_cluster_concentration_pct == 20.0

        # Invalid: below minimum
        with pytest.raises(ValueError):
            PositionSizingConfig(max_cluster_concentration_pct=5.0)  # min is 10.0

    def test_max_positions_per_cluster_bounds(self) -> None:
        """Test max positions per cluster bounds."""
        # Valid: within bounds
        config = PositionSizingConfig(max_positions_per_cluster=1)
        assert config.max_positions_per_cluster == 1

        config = PositionSizingConfig(max_positions_per_cluster=10)
        assert config.max_positions_per_cluster == 10

        # Invalid: above maximum
        with pytest.raises(ValueError):
            PositionSizingConfig(max_positions_per_cluster=15)  # max is 10
