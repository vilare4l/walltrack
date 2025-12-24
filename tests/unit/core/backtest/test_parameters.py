"""Tests for backtest parameters."""

from decimal import Decimal

import pytest


class TestScoringWeights:
    """Tests for ScoringWeights model."""

    def test_default_weights_sum_to_one(self) -> None:
        """Test that default weights sum to 1.0."""
        from walltrack.core.backtest.parameters import ScoringWeights

        weights = ScoringWeights()
        assert weights.validate_weights() is True

    def test_custom_weights_validation(self) -> None:
        """Test validation with custom weights."""
        from walltrack.core.backtest.parameters import ScoringWeights

        weights = ScoringWeights(
            wallet_weight=Decimal("0.40"),
            cluster_weight=Decimal("0.30"),
            token_weight=Decimal("0.20"),
            context_weight=Decimal("0.10"),
        )
        assert weights.validate_weights() is True

    def test_invalid_weights_fail_validation(self) -> None:
        """Test that weights not summing to 1.0 fail validation."""
        from walltrack.core.backtest.parameters import ScoringWeights

        weights = ScoringWeights(
            wallet_weight=Decimal("0.50"),
            cluster_weight=Decimal("0.50"),
            token_weight=Decimal("0.50"),
            context_weight=Decimal("0.50"),
        )
        assert weights.validate_weights() is False


class TestExitStrategyParams:
    """Tests for ExitStrategyParams model."""

    def test_default_exit_strategy(self) -> None:
        """Test default exit strategy values."""
        from walltrack.core.backtest.parameters import ExitStrategyParams

        params = ExitStrategyParams()
        assert params.stop_loss_pct == Decimal("0.50")
        assert params.trailing_stop_enabled is True
        assert len(params.take_profit_levels) == 2

    def test_custom_exit_strategy(self) -> None:
        """Test custom exit strategy parameters."""
        from walltrack.core.backtest.parameters import ExitStrategyParams

        params = ExitStrategyParams(
            stop_loss_pct=Decimal("0.30"),
            trailing_stop_enabled=False,
            moonbag_pct=Decimal("0.50"),
        )
        assert params.stop_loss_pct == Decimal("0.30")
        assert params.trailing_stop_enabled is False
        assert params.moonbag_pct == Decimal("0.50")


class TestBacktestParameters:
    """Tests for BacktestParameters model."""

    def test_backtest_params_creation(self) -> None:
        """Test creating backtest parameters."""
        from datetime import UTC, datetime

        from walltrack.core.backtest.parameters import BacktestParameters

        params = BacktestParameters(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
        )

        assert params.score_threshold == Decimal("0.70")
        assert params.base_position_sol == Decimal("0.1")
        assert params.max_concurrent_positions == 5

    def test_backtest_params_with_custom_values(self) -> None:
        """Test backtest params with custom values."""
        from datetime import UTC, datetime

        from walltrack.core.backtest.parameters import (
            BacktestParameters,
            ScoringWeights,
        )

        params = BacktestParameters(
            start_date=datetime(2024, 1, 1, tzinfo=UTC),
            end_date=datetime(2024, 6, 30, tzinfo=UTC),
            scoring_weights=ScoringWeights(
                wallet_weight=Decimal("0.40"),
                cluster_weight=Decimal("0.20"),
                token_weight=Decimal("0.20"),
                context_weight=Decimal("0.20"),
            ),
            score_threshold=Decimal("0.80"),
            base_position_sol=Decimal("0.2"),
        )

        assert params.score_threshold == Decimal("0.80")
        assert params.base_position_sol == Decimal("0.2")
        assert params.scoring_weights.wallet_weight == Decimal("0.40")
