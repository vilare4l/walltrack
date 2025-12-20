"""Signal logging models for storage and queries."""

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SignalStatus(str, Enum):
    """Status of processed signal."""

    RECEIVED = "received"
    FILTERED_OUT = "filtered_out"
    SCORED = "scored"
    TRADE_ELIGIBLE = "trade_eligible"
    BELOW_THRESHOLD = "below_threshold"
    EXECUTED = "executed"
    FAILED = "failed"


class SignalLogEntry(BaseModel):
    """Complete signal log entry for storage."""

    # Identification
    id: str | None = None  # UUID from database
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str  # "buy" or "sell"

    # Transaction details
    amount_token: float = 0.0
    amount_sol: float = 0.0
    slot: int | None = None

    # Scoring (nullable if filtered before scoring)
    final_score: float | None = None
    wallet_score: float | None = None
    cluster_score: float | None = None
    token_score: float | None = None
    context_score: float | None = None

    # Status
    status: SignalStatus = SignalStatus.RECEIVED
    eligibility_status: str | None = None  # trade_eligible, below_threshold
    conviction_tier: str | None = None  # high, standard, none

    # Filtering info
    filter_status: str | None = None  # passed, discarded, blocked
    filter_reason: str | None = None

    # Linked trade (populated later in Epic 4)
    trade_id: str | None = None

    # Timing
    timestamp: datetime  # Original transaction time
    received_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_time_ms: float = 0.0

    # Metadata
    raw_factors: dict[str, Any] = Field(default_factory=dict)


class SignalLogFilter(BaseModel):
    """Filter criteria for querying signals."""

    # Date range
    start_date: datetime | None = None
    end_date: datetime | None = None

    # Wallet filter
    wallet_address: str | None = None

    # Score range
    min_score: float | None = None
    max_score: float | None = None

    # Status filter
    status: SignalStatus | None = None
    eligibility_status: str | None = None

    # Pagination
    limit: int = Field(default=100, le=1000)
    offset: int = Field(default=0, ge=0)

    # Sorting
    sort_by: str = "timestamp"
    sort_desc: bool = True


class SignalLogSummary(BaseModel):
    """Summary statistics for signals."""

    total_count: int = 0
    trade_eligible_count: int = 0
    below_threshold_count: int = 0
    filtered_count: int = 0
    executed_count: int = 0

    avg_score: float | None = None
    avg_processing_time_ms: float | None = None

    period_start: datetime | None = None
    period_end: datetime | None = None
