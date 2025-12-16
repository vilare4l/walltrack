"""Signal domain models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SignalType(str, Enum):
    """Type of trading signal."""

    BUY = "buy"
    SELL = "sell"


class SignalSource(str, Enum):
    """Source of the signal."""

    WEBHOOK = "webhook"
    SCANNER = "scanner"
    MANUAL = "manual"


class SignalScore(BaseModel):
    """Breakdown of signal scoring factors."""

    wallet_score: float = Field(ge=0, le=1, description="Source wallet quality")
    token_score: float = Field(ge=0, le=1, description="Token quality/liquidity")
    timing_score: float = Field(ge=0, le=1, description="Entry timing quality")
    cluster_score: float = Field(ge=0, le=1, description="Cluster confirmation bonus")
    final_score: float = Field(ge=0, le=1, description="Combined weighted score")

    @property
    def passes_threshold(self) -> bool:
        """Check if signal passes minimum threshold (0.7)."""
        return self.final_score >= 0.7


class SignalCreate(BaseModel):
    """Schema for creating a new signal."""

    wallet_address: str = Field(description="Source wallet address")
    token_address: str = Field(description="Token mint address")
    signal_type: SignalType = Field(description="Buy or sell signal")
    amount_sol: float = Field(gt=0, description="Transaction amount in SOL")
    source: SignalSource = Field(default=SignalSource.WEBHOOK)
    tx_signature: str | None = Field(default=None, description="Transaction signature")


class Signal(BaseModel):
    """Complete signal model with all fields."""

    id: str = Field(description="Unique identifier")
    wallet_id: str = Field(description="Reference to wallet")
    wallet_address: str = Field(description="Source wallet address")
    token_address: str = Field(description="Token mint address")
    token_symbol: str | None = Field(default=None, description="Token symbol if known")
    signal_type: SignalType
    amount_sol: float = Field(gt=0)
    source: SignalSource
    tx_signature: str | None = Field(default=None)
    score: SignalScore | None = Field(default=None)
    processed: bool = Field(default=False)
    trade_id: str | None = Field(default=None, description="Resulting trade if executed")
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        from_attributes = True
