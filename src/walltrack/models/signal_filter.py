"""Signal filter domain models."""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class FilterStatus(str, Enum):
    """Status of signal filtering."""

    PASSED = "passed"
    DISCARDED_NOT_MONITORED = "discarded_not_monitored"
    BLOCKED_BLACKLISTED = "blocked_blacklisted"
    ERROR = "error"


class WalletCacheEntry(BaseModel):
    """Entry in the monitored wallets cache."""

    wallet_address: str
    is_monitored: bool = False
    is_blacklisted: bool = False
    cluster_id: str | None = None
    is_leader: bool = False
    reputation_score: float = Field(default=0.5, ge=0, le=1)
    cached_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    ttl_seconds: int = Field(default=300)  # 5 minutes

    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        elapsed = (datetime.now(UTC) - self.cached_at).total_seconds()
        return elapsed > self.ttl_seconds


class FilterResult(BaseModel):
    """Result of signal filtering."""

    status: FilterStatus
    wallet_address: str
    is_monitored: bool
    is_blacklisted: bool
    lookup_time_ms: float = Field(..., ge=0)
    cache_hit: bool = False
    wallet_metadata: WalletCacheEntry | None = None


class SignalContext(BaseModel):
    """Context attached to signal after filtering."""

    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"
    amount_token: float
    amount_sol: float
    timestamp: datetime
    tx_signature: str

    # Enriched from filter
    cluster_id: str | None = None
    is_cluster_leader: bool = False
    wallet_reputation: float = Field(default=0.5, ge=0, le=1)

    # Processing metadata
    filter_status: FilterStatus = FilterStatus.PASSED
    filter_time_ms: float = 0.0
