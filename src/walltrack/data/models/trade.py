"""Trade domain models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class TradeStatus(str, Enum):
    """Trade execution status."""

    PENDING = "pending"
    EXECUTING = "executing"
    FILLED = "filled"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TradeResult(str, Enum):
    """Trade outcome result."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"
    OPEN = "open"


class TradeCreate(BaseModel):
    """Schema for creating a new trade."""

    signal_id: str = Field(description="Reference to originating signal")
    wallet_address: str = Field(description="Source wallet that triggered")
    token_address: str = Field(description="Token to trade")
    side: str = Field(description="buy or sell")
    amount_sol: float = Field(gt=0, description="Amount in SOL")
    exit_strategy: str = Field(default="balanced", description="Exit strategy name")


class Trade(BaseModel):
    """Complete trade model with all fields."""

    id: str = Field(description="Unique identifier")
    signal_id: str = Field(description="Reference to originating signal")
    wallet_address: str = Field(description="Source wallet")
    token_address: str = Field(description="Token mint address")
    token_symbol: str | None = Field(default=None)
    side: str = Field(description="buy or sell")
    status: TradeStatus = Field(default=TradeStatus.PENDING)
    result: TradeResult = Field(default=TradeResult.OPEN)

    # Entry details
    entry_amount_sol: float = Field(gt=0, description="Entry amount in SOL")
    entry_price: float | None = Field(default=None, description="Entry price")
    entry_tx: str | None = Field(default=None, description="Entry transaction signature")
    entry_at: datetime | None = Field(default=None)

    # Exit details
    exit_amount_sol: float | None = Field(default=None)
    exit_price: float | None = Field(default=None)
    exit_tx: str | None = Field(default=None)
    exit_at: datetime | None = Field(default=None)

    # Performance
    pnl_sol: float | None = Field(default=None, description="Profit/loss in SOL")
    pnl_percent: float | None = Field(default=None, description="Profit/loss percentage")
    exit_strategy: str = Field(default="balanced")
    moonbag_remaining: float = Field(default=0, description="Moonbag amount kept")

    # Metadata
    score_at_entry: float | None = Field(default=None, description="Signal score at entry")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        from_attributes = True
