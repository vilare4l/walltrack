"""Scenario configuration for backtesting."""

import json
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from walltrack.core.backtest.parameters import (
    BacktestParameters,
    ExitStrategyParams,
    ScoringWeights,
)


class ScenarioCategory(str, Enum):
    """Categories for organizing scenarios."""

    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"
    EXPERIMENTAL = "experimental"
    OPTIMIZATION = "optimization"
    CUSTOM = "custom"


class Scenario(BaseModel):
    """A named backtest scenario configuration.

    Encapsulates all parameters needed for a backtest run
    with validation and conversion utilities.
    """

    id: UUID = Field(default_factory=uuid4)
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    category: ScenarioCategory = ScenarioCategory.CUSTOM
    tags: list[str] = Field(default_factory=list)

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
    slippage_bps: int = 100

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
    is_preset: bool = False

    @field_validator("score_threshold")
    @classmethod
    def validate_threshold(cls, v: Decimal) -> Decimal:
        """Ensure threshold is between 0 and 1.

        Args:
            v: Score threshold value.

        Returns:
            Validated threshold.

        Raises:
            ValueError: If threshold is out of range.
        """
        if not (0 <= v <= 1):
            raise ValueError("Score threshold must be between 0 and 1")
        return v

    @field_validator("max_concurrent_positions")
    @classmethod
    def validate_max_positions(cls, v: int) -> int:
        """Ensure max positions is reasonable.

        Args:
            v: Max concurrent positions value.

        Returns:
            Validated max positions.

        Raises:
            ValueError: If value is out of range.
        """
        if not (1 <= v <= 50):
            raise ValueError("Max concurrent positions must be between 1 and 50")
        return v

    def to_backtest_params(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> BacktestParameters:
        """Convert scenario to backtest parameters.

        Args:
            start_date: Backtest start date.
            end_date: Backtest end date.

        Returns:
            BacktestParameters configured from this scenario.
        """
        return BacktestParameters(
            start_date=start_date,
            end_date=end_date,
            scoring_weights=self.scoring_weights,
            score_threshold=self.score_threshold,
            base_position_sol=self.base_position_sol,
            high_conviction_multiplier=self.high_conviction_multiplier,
            high_conviction_threshold=self.high_conviction_threshold,
            exit_strategy=self.exit_strategy,
            max_concurrent_positions=self.max_concurrent_positions,
            max_daily_trades=self.max_daily_trades,
            slippage_bps=self.slippage_bps,
        )

    def to_json(self) -> str:
        """Export scenario as JSON.

        Returns:
            JSON string representation of scenario.
        """
        return json.dumps(self.model_dump(mode="json"), indent=2)

    @classmethod
    def from_json(cls, json_str: str) -> "Scenario":
        """Import scenario from JSON.

        Args:
            json_str: JSON string to parse.

        Returns:
            Scenario instance.
        """
        data = json.loads(json_str)
        return cls(**data)

    model_config = {"json_encoders": {Decimal: str}}


# Preset scenarios
PRESET_SCENARIOS = [
    Scenario(
        id=uuid4(),
        name="Conservative",
        description="Lower risk with tighter stops and smaller positions",
        category=ScenarioCategory.CONSERVATIVE,
        is_preset=True,
        score_threshold=Decimal("0.80"),
        base_position_sol=Decimal("0.05"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.30"),
            take_profit_levels=[
                {"multiplier": 1.5, "sell_pct": 0.50},
                {"multiplier": 2.0, "sell_pct": 0.50},
            ],
            trailing_stop_enabled=False,
            moonbag_pct=Decimal("0"),
        ),
        max_concurrent_positions=3,
    ),
    Scenario(
        id=uuid4(),
        name="Balanced",
        description="Moderate risk with standard exit strategy",
        category=ScenarioCategory.MODERATE,
        is_preset=True,
        score_threshold=Decimal("0.70"),
        base_position_sol=Decimal("0.1"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.50"),
            take_profit_levels=[
                {"multiplier": 2.0, "sell_pct": 0.33},
                {"multiplier": 3.0, "sell_pct": 0.33},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("2.0"),
            trailing_stop_distance=Decimal("0.30"),
            moonbag_pct=Decimal("0.34"),
        ),
        max_concurrent_positions=5,
    ),
    Scenario(
        id=uuid4(),
        name="Aggressive Moonbag",
        description="Higher risk seeking moonshots with large moonbag",
        category=ScenarioCategory.AGGRESSIVE,
        is_preset=True,
        score_threshold=Decimal("0.65"),
        base_position_sol=Decimal("0.15"),
        high_conviction_multiplier=Decimal("2.0"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.60"),
            take_profit_levels=[
                {"multiplier": 3.0, "sell_pct": 0.25},
                {"multiplier": 5.0, "sell_pct": 0.25},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("3.0"),
            trailing_stop_distance=Decimal("0.40"),
            moonbag_pct=Decimal("0.50"),
        ),
        max_concurrent_positions=7,
    ),
    Scenario(
        id=uuid4(),
        name="Quick Flip",
        description="Fast exits targeting quick profits",
        category=ScenarioCategory.MODERATE,
        is_preset=True,
        score_threshold=Decimal("0.75"),
        base_position_sol=Decimal("0.1"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.20"),
            take_profit_levels=[
                {"multiplier": 1.3, "sell_pct": 0.50},
                {"multiplier": 1.5, "sell_pct": 0.50},
            ],
            trailing_stop_enabled=False,
            moonbag_pct=Decimal("0"),
        ),
        max_concurrent_positions=10,
    ),
    Scenario(
        id=uuid4(),
        name="Diamond Hands",
        description="Long-term holds seeking massive multipliers",
        category=ScenarioCategory.AGGRESSIVE,
        is_preset=True,
        score_threshold=Decimal("0.85"),
        base_position_sol=Decimal("0.2"),
        exit_strategy=ExitStrategyParams(
            stop_loss_pct=Decimal("0.70"),
            take_profit_levels=[
                {"multiplier": 5.0, "sell_pct": 0.25},
                {"multiplier": 10.0, "sell_pct": 0.25},
            ],
            trailing_stop_enabled=True,
            trailing_stop_activation=Decimal("5.0"),
            trailing_stop_distance=Decimal("0.50"),
            moonbag_pct=Decimal("0.50"),
        ),
        max_concurrent_positions=3,
    ),
]
