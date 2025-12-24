"""Backtest parameter configuration."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Scoring weights for backtest.

    Weights should sum to 1.0 for proper score normalization.
    """

    wallet_weight: Decimal = Decimal("0.30")
    cluster_weight: Decimal = Decimal("0.25")
    token_weight: Decimal = Decimal("0.25")
    context_weight: Decimal = Decimal("0.20")

    def validate_weights(self) -> bool:
        """Ensure weights sum to 1.0.

        Returns:
            True if weights sum to approximately 1.0.
        """
        total = (
            self.wallet_weight
            + self.cluster_weight
            + self.token_weight
            + self.context_weight
        )
        return abs(total - Decimal("1.0")) < Decimal("0.01")


class ExitStrategyParams(BaseModel):
    """Exit strategy parameters for backtest.

    Defines stop-loss, take-profit, and trailing stop behavior.
    """

    stop_loss_pct: Decimal = Decimal("0.50")  # 50% loss
    take_profit_levels: list[dict] = Field(
        default_factory=lambda: [
            {"multiplier": 2.0, "sell_pct": 0.33},
            {"multiplier": 3.0, "sell_pct": 0.33},
        ]
    )
    trailing_stop_enabled: bool = True
    trailing_stop_activation: Decimal = Decimal("2.0")  # x2
    trailing_stop_distance: Decimal = Decimal("0.30")  # 30%
    moonbag_pct: Decimal = Decimal("0.34")


class BacktestParameters(BaseModel):
    """Complete backtest configuration.

    Contains all parameters needed to run a backtest scenario.
    """

    # Date range
    start_date: datetime
    end_date: datetime

    # Scoring parameters
    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: Decimal = Decimal("0.70")

    # Position sizing
    base_position_sol: Decimal = Decimal("0.1")
    high_conviction_multiplier: Decimal = Decimal("1.5")
    high_conviction_threshold: Decimal = Decimal("0.85")

    # Exit strategy
    exit_strategy: ExitStrategyParams = Field(default_factory=ExitStrategyParams)

    # Risk parameters
    max_concurrent_positions: int = 5
    max_daily_trades: int = 10

    # Simulation settings
    slippage_bps: int = 100  # 1%

    model_config = {"json_encoders": {Decimal: str}}
