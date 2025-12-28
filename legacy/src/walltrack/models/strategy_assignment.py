"""Score-based strategy assignment models.

Defines models for automatic and manual strategy assignment
based on signal conviction scores.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AssignmentSource(str, Enum):
    """Source of strategy assignment."""

    SCORE_BASED = "score_based"
    MANUAL_OVERRIDE = "manual_override"
    DEFAULT_FALLBACK = "default_fallback"


class ScoreRange(BaseModel):
    """A score range for strategy mapping."""

    min_score: float = Field(..., ge=0, le=1)
    max_score: float = Field(..., ge=0, le=1)
    strategy_id: str = Field(...)

    def contains(self, score: float) -> bool:
        """Check if score falls within this range.

        Args:
            score: Score to check (0.0 to 1.0)

        Returns:
            True if score is within range (inclusive)
        """
        return self.min_score <= score <= self.max_score


class StrategyMappingConfig(BaseModel):
    """Configuration for score-to-strategy mapping.

    Default mapping:
    - Score >= 0.90: Diamond Hands (high conviction)
    - Score 0.80-0.89: Moonbag Aggressive
    - Score 0.70-0.79: Balanced
    - Score < 0.70: Default fallback
    """

    mappings: list[ScoreRange] = Field(
        default_factory=lambda: [
            ScoreRange(
                min_score=0.90, max_score=1.00, strategy_id="preset-diamond-hands"
            ),
            ScoreRange(
                min_score=0.80, max_score=0.89, strategy_id="preset-moonbag-aggressive"
            ),
            ScoreRange(min_score=0.70, max_score=0.79, strategy_id="preset-balanced"),
        ]
    )

    default_strategy_id: str = Field(
        default="preset-balanced",
        description="Strategy to use when no score range matches",
    )

    enabled: bool = Field(
        default=True,
        description="Enable score-based assignment (vs always use default)",
    )

    def get_strategy_for_score(self, score: float) -> tuple[str, bool]:
        """Get strategy ID for a given score.

        Args:
            score: Signal conviction score (0.0 to 1.0)

        Returns:
            Tuple of (strategy_id, is_default)
        """
        if not self.enabled:
            return self.default_strategy_id, True

        for mapping in self.mappings:
            if mapping.contains(score):
                return mapping.strategy_id, False

        return self.default_strategy_id, True


class StrategyAssignment(BaseModel):
    """Result of strategy assignment for a position."""

    position_id: str
    signal_id: str
    signal_score: float

    assigned_strategy_id: str
    assignment_source: AssignmentSource

    # For score-based
    matched_range: ScoreRange | None = Field(default=None)

    # For manual override
    override_by: str | None = Field(default=None, description="Operator who overrode")
    override_reason: str | None = Field(default=None)

    assigned_at: datetime = Field(default_factory=datetime.utcnow)


class ManualOverride(BaseModel):
    """Manual strategy override request."""

    position_id: str
    new_strategy_id: str
    override_by: str = Field(..., description="Operator identifier")
    reason: str | None = Field(default=None, description="Reason for override")


class OverrideLog(BaseModel):
    """Log entry for strategy overrides."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    position_id: str
    previous_strategy_id: str
    new_strategy_id: str
    override_by: str
    reason: str | None = Field(default=None)
    overridden_at: datetime = Field(default_factory=datetime.utcnow)
