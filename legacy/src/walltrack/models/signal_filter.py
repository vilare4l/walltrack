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
    """Entry in the monitored wallets cache.

    Epic 14 Story 14-5: Removed cluster_id and is_leader fields.
    Cluster data is now fetched directly from Neo4j via ClusterService.
    """

    wallet_address: str
    is_monitored: bool = False
    is_blacklisted: bool = False
    # REMOVED: cluster_id: str | None = None (use ClusterService instead)
    # REMOVED: is_leader: bool = False (use ClusterService instead)
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


class ProcessingResult(BaseModel):
    """Result of full pipeline processing.

    Epic 14 Simplification:
    - wallet_score: Primary score from wallet reputation
    - cluster_boost: Multiplier from cluster participation (1.0-1.8x)
    - position_multiplier: Used for sizing (equals cluster_boost)
    - Removed: token_score, context_score, conviction_tier (deprecated)
    """

    # Processing outcome
    passed: bool
    reason: str = ""

    # Signal identification
    tx_signature: str | None = None
    wallet_address: str | None = None
    token_address: str | None = None

    # Scoring results (simplified in Epic 14)
    score: float | None = None  # Final score (wallet_score * cluster_boost)
    wallet_score: float | None = None  # Wallet reputation score
    cluster_boost: float | None = None  # Cluster multiplier (1.0-1.8x)

    # Deprecated fields (kept for backward compatibility)
    token_score: float | None = None  # DEPRECATED: Now binary gate in scorer
    context_score: float | None = None  # DEPRECATED: Removed in Epic 14
    cluster_score: float | None = None  # DEPRECATED: Use cluster_boost instead
    conviction_tier: str | None = None  # DEPRECATED: Use position_multiplier

    # Threshold result
    position_multiplier: float | None = None  # Size multiplier (equals cluster_boost)

    # Execution status
    trade_queued: bool = False
    signal_id: str | None = None
    position_id: str | None = None

    # Timing
    processing_time_ms: float = 0.0
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
