"""Models for pattern analysis and insights."""

from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class PatternType(str, Enum):
    """Types of patterns analyzed."""

    TIME_OF_DAY = "time_of_day"
    DAY_OF_WEEK = "day_of_week"
    WALLET = "wallet"
    TOKEN_CHARACTERISTIC = "token_characteristic"
    CLUSTER_VS_SOLO = "cluster_vs_solo"
    ENTRY_SCORE_RANGE = "entry_score_range"
    POSITION_SIZE = "position_size"


class PatternSentiment(str, Enum):
    """Pattern sentiment classification."""

    POSITIVE = "positive"  # Correlated with success
    NEGATIVE = "negative"  # Correlated with failure
    NEUTRAL = "neutral"  # No significant correlation


class SignificanceLevel(str, Enum):
    """Statistical significance level."""

    HIGH = "high"  # p < 0.01
    MEDIUM = "medium"  # p < 0.05
    LOW = "low"  # p < 0.10
    NONE = "none"  # p >= 0.10


class Pattern(BaseModel):
    """Identified trading pattern."""

    id: UUID = Field(..., description="Pattern ID")
    pattern_type: PatternType = Field(..., description="Type of pattern")
    pattern_name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="Pattern description")
    sentiment: PatternSentiment = Field(..., description="Positive or negative pattern")
    win_rate: Decimal = Field(..., ge=0, le=100, description="Win rate for this pattern %")
    baseline_win_rate: Decimal = Field(
        ..., ge=0, le=100, description="Overall win rate for comparison"
    )
    sample_size: int = Field(..., ge=0, description="Number of trades matching pattern")
    significance: SignificanceLevel = Field(..., description="Statistical significance")
    p_value: Decimal | None = Field(default=None, description="P-value of correlation")
    suggested_action: str = Field(..., description="Actionable recommendation")
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @computed_field
    @property
    def win_rate_delta(self) -> Decimal:
        """Difference from baseline win rate."""
        return self.win_rate - self.baseline_win_rate

    @computed_field
    @property
    def is_actionable(self) -> bool:
        """Whether pattern has enough significance to act on."""
        return self.sample_size >= 20 and self.significance in [
            SignificanceLevel.HIGH,
            SignificanceLevel.MEDIUM,
        ]


class TimePattern(BaseModel):
    """Time-based pattern analysis."""

    hour: int | None = Field(default=None, ge=0, le=23, description="Hour of day (UTC)")
    day_of_week: int | None = Field(
        default=None, ge=0, le=6, description="Day of week (0=Monday)"
    )
    trade_count: int = Field(default=0, description="Trades in this slot")
    win_count: int = Field(default=0, description="Wins in this slot")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate %")
    avg_pnl: Decimal = Field(default=Decimal("0"), description="Average PnL")
    total_pnl: Decimal = Field(default=Decimal("0"), description="Total PnL")


class WalletPattern(BaseModel):
    """Wallet-based performance pattern."""

    wallet_address: str = Field(..., description="Wallet address")
    wallet_score: Decimal = Field(..., description="Current wallet score")
    trade_count: int = Field(default=0, description="Total trades from wallet")
    win_count: int = Field(default=0, description="Wins from wallet")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate %")
    avg_pnl: Decimal = Field(default=Decimal("0"), description="Average PnL")
    is_top_performer: bool = Field(default=False, description="Top 20% performer")
    is_underperformer: bool = Field(default=False, description="Bottom 20% performer")


class TokenPattern(BaseModel):
    """Token characteristic pattern."""

    characteristic: str = Field(..., description="Token characteristic name")
    characteristic_value: str = Field(..., description="Characteristic value/range")
    trade_count: int = Field(default=0)
    win_rate: Decimal = Field(default=Decimal("0"))
    avg_pnl: Decimal = Field(default=Decimal("0"))


class ClusterPattern(BaseModel):
    """Cluster vs solo trade pattern."""

    is_cluster_trade: bool = Field(..., description="Whether trade was cluster-based")
    trade_count: int = Field(default=0)
    win_count: int = Field(default=0)
    win_rate: Decimal = Field(default=Decimal("0"))
    avg_pnl: Decimal = Field(default=Decimal("0"))


class PatternAnalysisResult(BaseModel):
    """Complete pattern analysis results."""

    id: UUID = Field(..., description="Analysis ID")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    trade_count: int = Field(..., description="Total trades analyzed")
    baseline_win_rate: Decimal = Field(..., description="Overall win rate")
    patterns: list[Pattern] = Field(default_factory=list, description="Identified patterns")
    time_patterns: list[TimePattern] = Field(default_factory=list)
    wallet_patterns: list[WalletPattern] = Field(default_factory=list)
    token_patterns: list[TokenPattern] = Field(default_factory=list)
    cluster_patterns: list[ClusterPattern] = Field(default_factory=list)
    top_positive_patterns: list[Pattern] = Field(default_factory=list)
    top_negative_patterns: list[Pattern] = Field(default_factory=list)


class PatternAlert(BaseModel):
    """Alert for significant pattern detection."""

    id: UUID = Field(..., description="Alert ID")
    pattern_id: UUID = Field(..., description="Pattern ID")
    pattern_type: PatternType = Field(..., description="Pattern type")
    pattern_name: str = Field(..., description="Pattern name")
    sentiment: PatternSentiment = Field(..., description="Positive or negative")
    message: str = Field(..., description="Alert message")
    suggested_action: str = Field(..., description="Recommended action")
    acknowledged: bool = Field(default=False, description="Whether alert was acknowledged")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
