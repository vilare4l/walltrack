"""Wallet domain models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class WalletStatus(str, Enum):
    """Wallet status enum."""

    ACTIVE = "active"
    DECAY_DETECTED = "decay_detected"
    BLACKLISTED = "blacklisted"
    INSUFFICIENT_DATA = "insufficient_data"


class WalletProfile(BaseModel):
    """Wallet performance profile."""

    win_rate: float = Field(default=0.0, ge=0.0, le=1.0, description="Win rate (0-1)")
    total_pnl: float = Field(default=0.0, description="Total PnL in USD")
    avg_pnl_per_trade: float = Field(default=0.0, description="Average PnL per trade")
    total_trades: int = Field(default=0, ge=0, description="Total number of trades")
    timing_percentile: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="How early they enter (0=earliest, 1=latest)",
    )
    avg_hold_time_hours: float = Field(
        default=0.0, ge=0.0, description="Average hold time in hours"
    )
    preferred_hours: list[int] = Field(
        default_factory=list, description="Active trading hours (0-23)"
    )
    avg_position_size_sol: float = Field(
        default=0.0, ge=0.0, description="Average position size in SOL"
    )


class Wallet(BaseModel):
    """Wallet domain model."""

    address: str = Field(
        ..., min_length=32, max_length=44, description="Solana wallet address"
    )
    status: WalletStatus = Field(
        default=WalletStatus.ACTIVE, description="Current wallet status"
    )
    score: float = Field(
        default=0.5, ge=0.0, le=1.0, description="Wallet trust score (0-1)"
    )
    profile: WalletProfile = Field(
        default_factory=WalletProfile, description="Performance profile"
    )

    # Discovery metadata
    discovered_at: datetime = Field(
        default_factory=datetime.utcnow, description="First discovery timestamp"
    )
    discovery_count: int = Field(
        default=1, ge=1, description="Times discovered from token launches"
    )
    discovery_tokens: list[str] = Field(
        default_factory=list, description="Token mints from discovery"
    )

    # Decay tracking
    decay_detected_at: datetime | None = Field(
        default=None, description="Decay detection timestamp"
    )
    consecutive_losses: int = Field(
        default=0, ge=0, description="Current consecutive loss count"
    )
    rolling_win_rate: float | None = Field(
        default=None, description="Rolling 20-trade win rate"
    )

    # Blacklist
    blacklisted_at: datetime | None = Field(
        default=None, description="Blacklist timestamp"
    )
    blacklist_reason: str | None = Field(
        default=None, description="Reason for blacklisting"
    )

    # Timestamps
    last_profiled_at: datetime | None = Field(
        default=None, description="Last profile update"
    )
    last_signal_at: datetime | None = Field(
        default=None, description="Last signal from this wallet"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )

    def is_trackable(self) -> bool:
        """Check if wallet can be tracked for signals."""
        return self.status not in (
            WalletStatus.BLACKLISTED,
            WalletStatus.INSUFFICIENT_DATA,
        )

    def has_sufficient_data(self) -> bool:
        """Check if wallet has enough trades for analysis."""
        return self.profile.total_trades >= 5


class DiscoveryResult(BaseModel):
    """Result of wallet discovery process."""

    new_wallets: int = Field(
        default=0, ge=0, description="Count of new wallets discovered"
    )
    updated_wallets: int = Field(
        default=0, ge=0, description="Count of existing wallets updated"
    )
    total_processed: int = Field(
        default=0, ge=0, description="Total wallets processed"
    )
    token_mint: str = Field(..., description="Token mint address that was analyzed")
    duration_seconds: float = Field(..., ge=0, description="Processing duration")
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )


class TokenLaunch(BaseModel):
    """Token launch data for discovery."""

    mint: str = Field(..., description="Token mint address")
    symbol: str = Field(default="", description="Token symbol")
    launch_time: datetime = Field(..., description="Token launch timestamp")
    peak_mcap: float = Field(default=0.0, ge=0, description="Peak market cap in USD")
    current_mcap: float = Field(
        default=0.0, ge=0, description="Current market cap in USD"
    )
    volume_24h: float = Field(default=0.0, ge=0, description="24h volume in USD")
