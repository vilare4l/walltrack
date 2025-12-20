"""Models for signal accuracy tracking."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class AccuracyTrend(str, Enum):
    """Accuracy trend direction."""

    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class RetrospectiveOutcome(str, Enum):
    """Outcome classification for non-traded signals."""

    MISSED_OPPORTUNITY = "missed_opportunity"
    BULLET_DODGED = "bullet_dodged"
    UNCERTAIN = "uncertain"


class SignalAccuracyMetrics(BaseModel):
    """Accuracy metrics for signals."""

    period_start: datetime = Field(..., description="Start of measurement period")
    period_end: datetime = Field(..., description="End of measurement period")
    total_signals: int = Field(default=0, description="Total signals generated")
    traded_signals: int = Field(default=0, description="Signals that became trades")
    winning_trades: int = Field(default=0, description="Trades that were profitable")
    losing_trades: int = Field(default=0, description="Trades that were losses")
    avg_score_winners: Decimal = Field(
        default=Decimal("0"), description="Average score of winning signals"
    )
    avg_score_losers: Decimal = Field(
        default=Decimal("0"), description="Average score of losing signals"
    )
    optimal_threshold: Decimal = Field(
        default=Decimal("0.6"), description="Threshold that would maximize profit"
    )

    @computed_field
    @property
    def signal_to_trade_rate(self) -> Decimal:
        """Percentage of signals that became trades."""
        if self.total_signals == 0:
            return Decimal("0")
        return (Decimal(self.traded_signals) / Decimal(self.total_signals)) * 100

    @computed_field
    @property
    def signal_to_win_rate(self) -> Decimal:
        """Percentage of traded signals that won."""
        if self.traded_signals == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.traded_signals)) * 100

    @computed_field
    @property
    def score_differential(self) -> Decimal:
        """Difference between winner and loser average scores."""
        return self.avg_score_winners - self.avg_score_losers


class ThresholdAnalysis(BaseModel):
    """Analysis of different threshold effectiveness."""

    threshold: Decimal = Field(..., description="Score threshold")
    would_trade_count: int = Field(default=0, description="Signals above threshold")
    would_win_count: int = Field(default=0, description="Would-be wins")
    would_lose_count: int = Field(default=0, description="Would-be losses")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at threshold")
    total_pnl: Decimal = Field(default=Decimal("0"), description="Total PnL at threshold")
    profit_factor: Decimal = Field(
        default=Decimal("0"), description="Profit factor at threshold"
    )


class RetrospectiveSignal(BaseModel):
    """Signal that was not traded with retrospective analysis."""

    signal_id: UUID = Field(..., description="Signal ID")
    signal_score: Decimal = Field(..., description="Signal score")
    token_address: str = Field(..., description="Token address")
    wallet_address: str = Field(..., description="Originating wallet")
    signal_timestamp: datetime = Field(..., description="When signal was generated")
    threshold_at_time: Decimal = Field(
        ..., description="Trading threshold at signal time"
    )
    outcome: RetrospectiveOutcome = Field(..., description="Retrospective classification")
    estimated_pnl: Decimal | None = Field(
        default=None, description="Estimated PnL if traded"
    )
    price_at_signal: Decimal | None = Field(
        default=None, description="Token price at signal"
    )
    peak_price_after: Decimal | None = Field(
        default=None, description="Peak price in window"
    )
    min_price_after: Decimal | None = Field(
        default=None, description="Min price in window"
    )


class RetrospectiveAnalysis(BaseModel):
    """Summary of retrospective analysis."""

    period_start: datetime = Field(..., description="Analysis period start")
    period_end: datetime = Field(..., description="Analysis period end")
    total_non_traded: int = Field(default=0, description="Total non-traded signals")
    missed_opportunities: int = Field(
        default=0, description="Signals that would have won"
    )
    bullets_dodged: int = Field(default=0, description="Signals that would have lost")
    uncertain: int = Field(default=0, description="Uncertain outcomes")
    total_missed_pnl: Decimal = Field(
        default=Decimal("0"), description="PnL from missed opportunities"
    )
    total_avoided_loss: Decimal = Field(
        default=Decimal("0"), description="Loss avoided by not trading"
    )
    signals: list[RetrospectiveSignal] = Field(default_factory=list)

    @computed_field
    @property
    def net_impact(self) -> Decimal:
        """Net impact: missed PnL minus avoided losses."""
        return self.total_missed_pnl - self.total_avoided_loss


class AccuracySnapshot(BaseModel):
    """Point-in-time accuracy snapshot for trend analysis."""

    id: UUID = Field(..., description="Snapshot ID")
    snapshot_date: datetime = Field(..., description="Date of snapshot")
    signal_to_win_rate: Decimal = Field(..., description="Win rate at snapshot")
    sample_size: int = Field(..., description="Number of trades in sample")
    avg_signal_score: Decimal = Field(..., description="Average signal score")
    score_differential: Decimal = Field(..., description="Winner vs loser score diff")


class AccuracyTrendAnalysis(BaseModel):
    """Accuracy trend over time."""

    period_start: datetime = Field(..., description="Trend analysis start")
    period_end: datetime = Field(..., description="Trend analysis end")
    snapshots: list[AccuracySnapshot] = Field(default_factory=list)
    trend: AccuracyTrend = Field(..., description="Overall trend direction")
    trend_slope: Decimal = Field(
        default=Decimal("0"), description="Trend slope (% change per week)"
    )
    start_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at start")
    end_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at end")
    confidence: Decimal = Field(default=Decimal("0"), description="Trend confidence 0-1")

    @computed_field
    @property
    def win_rate_change(self) -> Decimal:
        """Total win rate change over period."""
        return self.end_win_rate - self.start_win_rate


class FactorAccuracyBreakdown(BaseModel):
    """Accuracy broken down by scoring factor."""

    factor_name: str = Field(..., description="Factor name")
    high_score_win_rate: Decimal = Field(
        default=Decimal("0"), description="Win rate when factor score high"
    )
    low_score_win_rate: Decimal = Field(
        default=Decimal("0"), description="Win rate when factor score low"
    )
    is_predictive: bool = Field(default=False, description="Whether factor is predictive")
    correlation_with_outcome: Decimal = Field(
        default=Decimal("0"), description="Correlation with trade outcome"
    )
    recommended_weight_adjustment: str = Field(
        default="none", description="Weight adjustment recommendation"
    )

    @computed_field
    @property
    def win_rate_lift(self) -> Decimal:
        """Win rate difference when factor is high vs low."""
        return self.high_score_win_rate - self.low_score_win_rate
