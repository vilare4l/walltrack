"""Wallet domain models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WalletStatus(str, Enum):
    """Wallet tracking status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    BLACKLISTED = "blacklisted"
    DECAYED = "decayed"


class WalletMetrics(BaseModel):
    """Performance metrics for a wallet."""

    win_rate: float = Field(ge=0, le=1, description="Win rate (0-1)")
    avg_gain: float = Field(description="Average gain percentage")
    avg_loss: float = Field(description="Average loss percentage")
    total_trades: int = Field(ge=0, description="Total number of trades")
    profitable_trades: int = Field(ge=0, description="Number of profitable trades")
    avg_hold_time_hours: float = Field(ge=0, description="Average hold time in hours")
    last_trade_at: datetime | None = Field(default=None, description="Last trade timestamp")


class WalletCreate(BaseModel):
    """Schema for creating a new wallet."""

    address: str = Field(min_length=32, max_length=44, description="Solana wallet address")
    label: str | None = Field(default=None, description="Optional label for the wallet")
    source: str = Field(default="manual", description="How the wallet was discovered")


class Wallet(BaseModel):
    """Complete wallet model with all fields."""

    id: str = Field(description="Unique identifier")
    address: str = Field(min_length=32, max_length=44, description="Solana wallet address")
    label: str | None = Field(default=None, description="Optional label")
    status: WalletStatus = Field(default=WalletStatus.ACTIVE)
    score: float = Field(ge=0, le=1, default=0.5, description="Wallet quality score (0-1)")
    metrics: WalletMetrics | None = Field(default=None)
    cluster_id: str | None = Field(default=None, description="Associated cluster ID")
    source: str = Field(default="manual", description="Discovery source")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        """Pydantic config."""

        from_attributes = True
