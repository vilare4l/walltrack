# Story 1.6: Wallet Decay Detection

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: ready
- **Priority**: Medium
- **FR**: FR4, FR5

## User Story

**As an** operator,
**I want** the system to detect when wallet performance degrades,
**So that** I can review and potentially remove underperforming wallets.

## Acceptance Criteria

### AC 1: Decay Detection
**Given** a wallet with at least 20 historical trades
**When** decay detection runs
**Then** rolling 20-trade window win rate is calculated
**And** comparison to lifetime win rate is made

### AC 2: Threshold Breach
**Given** rolling win rate drops below 40%
**When** decay threshold is breached
**Then** wallet is flagged with status "decay_detected"
**And** flag timestamp is recorded
**And** operator is notified (if notifications enabled)

### AC 3: Consecutive Losses
**Given** 3 consecutive losses from the same wallet
**When** the third loss is recorded
**Then** wallet score receives temporary downgrade
**And** downgrade is logged with reason

### AC 4: Recovery
**Given** wallet performance recovers (rolling win rate > 50%)
**When** next decay check runs
**Then** decay flag is cleared
**And** score downgrade is removed

## Technical Specifications

### Decay Detector Implementation

**src/walltrack/discovery/decay_detector.py:**
```python
"""Wallet decay detection for identifying underperforming wallets."""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from walltrack.config.settings import get_settings
from walltrack.data.models.wallet import Wallet, WalletStatus
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.data.supabase.repositories.trade_repo import TradeRepository

log = structlog.get_logger()

# Configuration constants
ROLLING_WINDOW_SIZE = 20
MIN_TRADES_FOR_DECAY_CHECK = 20
DECAY_THRESHOLD = 0.40  # 40% win rate
RECOVERY_THRESHOLD = 0.50  # 50% win rate
CONSECUTIVE_LOSS_THRESHOLD = 3
SCORE_DOWNGRADE_FACTOR = 0.8  # Reduce score by 20%


class DecayEvent:
    """Represents a decay detection event."""

    def __init__(
        self,
        wallet_address: str,
        event_type: str,
        rolling_win_rate: float,
        lifetime_win_rate: float,
        consecutive_losses: int,
        score_before: float,
        score_after: float,
        timestamp: datetime,
    ) -> None:
        self.wallet_address = wallet_address
        self.event_type = event_type  # "decay_detected", "recovery", "consecutive_losses"
        self.rolling_win_rate = rolling_win_rate
        self.lifetime_win_rate = lifetime_win_rate
        self.consecutive_losses = consecutive_losses
        self.score_before = score_before
        self.score_after = score_after
        self.timestamp = timestamp

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/storage."""
        return {
            "wallet_address": self.wallet_address,
            "event_type": self.event_type,
            "rolling_win_rate": self.rolling_win_rate,
            "lifetime_win_rate": self.lifetime_win_rate,
            "consecutive_losses": self.consecutive_losses,
            "score_before": self.score_before,
            "score_after": self.score_after,
            "timestamp": self.timestamp.isoformat(),
        }


class DecayDetector:
    """Detects wallet performance decay and manages flagging."""

    def __init__(
        self,
        wallet_repo: WalletRepository,
        trade_repo: TradeRepository,
        notification_callback: Any | None = None,
    ) -> None:
        self.wallet_repo = wallet_repo
        self.trade_repo = trade_repo
        self.notify = notification_callback
        self.settings = get_settings()

    async def check_wallet_decay(self, wallet: Wallet) -> DecayEvent | None:
        """
        Check a single wallet for decay.

        Args:
            wallet: Wallet to check

        Returns:
            DecayEvent if state changed, None otherwise
        """
        # Get recent trades for rolling window
        recent_trades = await self.trade_repo.get_wallet_trades(
            wallet_address=wallet.address,
            limit=ROLLING_WINDOW_SIZE,
            order_by="executed_at",
            order_desc=True,
        )

        if len(recent_trades) < MIN_TRADES_FOR_DECAY_CHECK:
            log.debug(
                "insufficient_trades_for_decay",
                address=wallet.address,
                trades=len(recent_trades),
            )
            return None

        # Calculate rolling win rate
        wins = sum(1 for t in recent_trades if t.pnl > 0)
        rolling_win_rate = wins / len(recent_trades)

        # Update wallet's rolling win rate
        wallet.rolling_win_rate = rolling_win_rate

        # Check consecutive losses
        consecutive_losses = self._count_consecutive_losses(recent_trades)

        score_before = wallet.score
        event: DecayEvent | None = None

        # Check for decay
        if rolling_win_rate < DECAY_THRESHOLD:
            if wallet.status != WalletStatus.DECAY_DETECTED:
                # New decay detected
                event = await self._handle_decay_detected(
                    wallet, rolling_win_rate, consecutive_losses, score_before
                )

        # Check for recovery
        elif rolling_win_rate >= RECOVERY_THRESHOLD:
            if wallet.status == WalletStatus.DECAY_DETECTED:
                # Recovery detected
                event = await self._handle_recovery(
                    wallet, rolling_win_rate, consecutive_losses, score_before
                )

        # Check consecutive losses (independent of decay status)
        if consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
            if wallet.consecutive_losses < CONSECUTIVE_LOSS_THRESHOLD:
                # New consecutive loss threshold breach
                event = await self._handle_consecutive_losses(
                    wallet, rolling_win_rate, consecutive_losses, score_before
                )

        wallet.consecutive_losses = consecutive_losses

        # Save wallet changes
        await self.wallet_repo.update(wallet)

        return event

    async def check_all_wallets(
        self,
        batch_size: int = 100,
        max_concurrent: int = 20,
    ) -> list[DecayEvent]:
        """
        Check all active wallets for decay.

        Args:
            batch_size: Number of wallets to process per batch
            max_concurrent: Maximum concurrent checks

        Returns:
            List of decay events
        """
        log.info("decay_check_started")
        events: list[DecayEvent] = []

        # Get all wallets that can be checked (active or decay_detected)
        active_wallets = await self.wallet_repo.get_by_status(WalletStatus.ACTIVE, limit=batch_size)
        decay_wallets = await self.wallet_repo.get_by_status(WalletStatus.DECAY_DETECTED, limit=batch_size)

        all_wallets = active_wallets + decay_wallets

        if not all_wallets:
            log.info("no_wallets_to_check")
            return events

        log.info("checking_wallets", count=len(all_wallets))

        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_check(wallet: Wallet) -> DecayEvent | None:
            async with semaphore:
                try:
                    return await self.check_wallet_decay(wallet)
                except Exception as e:
                    log.error("decay_check_error", address=wallet.address, error=str(e))
                    return None

        results = await asyncio.gather(
            *[bounded_check(w) for w in all_wallets],
            return_exceptions=True,
        )

        events = [r for r in results if isinstance(r, DecayEvent)]

        log.info(
            "decay_check_completed",
            checked=len(all_wallets),
            events=len(events),
        )

        return events

    async def record_trade_outcome(
        self,
        wallet_address: str,
        is_win: bool,
        pnl: float,
    ) -> DecayEvent | None:
        """
        Record a trade outcome and check for decay implications.

        Called after each trade completes.

        Args:
            wallet_address: Wallet that made the trade
            is_win: Whether trade was profitable
            pnl: Profit/loss amount

        Returns:
            DecayEvent if triggered, None otherwise
        """
        wallet = await self.wallet_repo.get_by_address(wallet_address)
        if not wallet:
            log.warning("wallet_not_found_for_outcome", address=wallet_address)
            return None

        # Update consecutive losses
        if not is_win:
            wallet.consecutive_losses += 1
        else:
            wallet.consecutive_losses = 0

        # Check if consecutive loss threshold reached
        if wallet.consecutive_losses >= CONSECUTIVE_LOSS_THRESHOLD:
            score_before = wallet.score
            event = await self._handle_consecutive_losses(
                wallet,
                wallet.rolling_win_rate or 0.5,
                wallet.consecutive_losses,
                score_before,
            )
            await self.wallet_repo.update(wallet)
            return event

        await self.wallet_repo.update(wallet)
        return None

    async def _handle_decay_detected(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle decay detection."""
        wallet.status = WalletStatus.DECAY_DETECTED
        wallet.decay_detected_at = datetime.utcnow()
        wallet.score = max(wallet.score * SCORE_DOWNGRADE_FACTOR, 0.1)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="decay_detected",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.warning(
            "decay_detected",
            address=wallet.address,
            rolling_win_rate=f"{rolling_win_rate:.2%}",
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        # Send notification
        if self.notify:
            await self.notify(event)

        return event

    async def _handle_recovery(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle recovery from decay."""
        wallet.status = WalletStatus.ACTIVE
        wallet.decay_detected_at = None

        # Restore some score (not full - needs to prove itself)
        wallet.score = min(wallet.score / SCORE_DOWNGRADE_FACTOR * 0.9, 1.0)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="recovery",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.info(
            "decay_recovery",
            address=wallet.address,
            rolling_win_rate=f"{rolling_win_rate:.2%}",
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        if self.notify:
            await self.notify(event)

        return event

    async def _handle_consecutive_losses(
        self,
        wallet: Wallet,
        rolling_win_rate: float,
        consecutive_losses: int,
        score_before: float,
    ) -> DecayEvent:
        """Handle consecutive loss threshold breach."""
        # Apply smaller downgrade for consecutive losses
        downgrade = 0.95 ** (consecutive_losses - CONSECUTIVE_LOSS_THRESHOLD + 1)
        wallet.score = max(wallet.score * downgrade, 0.1)

        event = DecayEvent(
            wallet_address=wallet.address,
            event_type="consecutive_losses",
            rolling_win_rate=rolling_win_rate,
            lifetime_win_rate=wallet.profile.win_rate,
            consecutive_losses=consecutive_losses,
            score_before=score_before,
            score_after=wallet.score,
            timestamp=datetime.utcnow(),
        )

        log.warning(
            "consecutive_losses_detected",
            address=wallet.address,
            losses=consecutive_losses,
            score_change=f"{score_before:.3f} -> {wallet.score:.3f}",
        )

        if self.notify:
            await self.notify(event)

        return event

    def _count_consecutive_losses(self, trades: list[Any]) -> int:
        """Count consecutive losses from most recent trades."""
        consecutive = 0
        for trade in trades:  # trades already sorted by date desc
            if trade.pnl <= 0:
                consecutive += 1
            else:
                break
        return consecutive
```

### Supabase Decay Events Table

**src/walltrack/data/supabase/migrations/003_decay_events.sql:**
```sql
-- Decay events table for tracking decay detection history
CREATE TABLE IF NOT EXISTS decay_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address VARCHAR(44) NOT NULL REFERENCES wallets(address),
    event_type VARCHAR(30) NOT NULL,
    rolling_win_rate DECIMAL(5, 4) NOT NULL,
    lifetime_win_rate DECIMAL(5, 4) NOT NULL,
    consecutive_losses INTEGER NOT NULL DEFAULT 0,
    score_before DECIMAL(5, 4) NOT NULL,
    score_after DECIMAL(5, 4) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),

    CONSTRAINT valid_event_type CHECK (
        event_type IN ('decay_detected', 'recovery', 'consecutive_losses')
    )
);

-- Index for querying by wallet
CREATE INDEX IF NOT EXISTS idx_decay_events_wallet ON decay_events(wallet_address);
CREATE INDEX IF NOT EXISTS idx_decay_events_type ON decay_events(event_type);
CREATE INDEX IF NOT EXISTS idx_decay_events_created ON decay_events(created_at DESC);

-- RLS policies
ALTER TABLE decay_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access" ON decay_events FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON decay_events FOR INSERT WITH CHECK (true);
```

### Decay Events Repository

**src/walltrack/data/supabase/repositories/decay_event_repo.py:**
```python
"""Repository for decay events."""

from datetime import datetime
from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.discovery.decay_detector import DecayEvent

log = structlog.get_logger()


class DecayEventRepository:
    """Repository for decay event storage."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client
        self.table = "decay_events"

    async def create(self, event: DecayEvent) -> str:
        """Store a decay event. Returns event ID."""
        data = {
            "wallet_address": event.wallet_address,
            "event_type": event.event_type,
            "rolling_win_rate": event.rolling_win_rate,
            "lifetime_win_rate": event.lifetime_win_rate,
            "consecutive_losses": event.consecutive_losses,
            "score_before": event.score_before,
            "score_after": event.score_after,
            "created_at": event.timestamp.isoformat(),
        }

        response = await self.client.table(self.table).insert(data).execute()
        event_id = response.data[0]["id"]

        log.info(
            "decay_event_stored",
            event_id=event_id,
            wallet=event.wallet_address,
            type=event.event_type,
        )

        return event_id

    async def get_wallet_events(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get decay events for a wallet."""
        response = await (
            self.client.table(self.table)
            .select("*")
            .eq("wallet_address", wallet_address)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data

    async def get_recent_events(
        self,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get recent decay events."""
        query = self.client.table(self.table).select("*")

        if event_type:
            query = query.eq("event_type", event_type)

        response = await (
            query
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data
```

### Scheduled Decay Check Task

**src/walltrack/scheduler/tasks/decay_check_task.py:**
```python
"""Scheduled task for periodic decay detection."""

import structlog

from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.trade_repo import TradeRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.decay_detector import DecayDetector, DecayEvent

log = structlog.get_logger()


async def run_decay_check(
    wallet_repo: WalletRepository,
    trade_repo: TradeRepository,
    event_repo: DecayEventRepository,
) -> None:
    """
    Run periodic decay detection for all wallets.

    Should be scheduled to run every 1-4 hours.
    """
    log.info("scheduled_decay_check_started")

    async def store_and_notify(event: DecayEvent) -> None:
        """Store event and trigger notifications."""
        await event_repo.create(event)

    detector = DecayDetector(
        wallet_repo=wallet_repo,
        trade_repo=trade_repo,
        notification_callback=store_and_notify,
    )

    events = await detector.check_all_wallets()

    # Log summary
    decay_count = sum(1 for e in events if e.event_type == "decay_detected")
    recovery_count = sum(1 for e in events if e.event_type == "recovery")
    loss_count = sum(1 for e in events if e.event_type == "consecutive_losses")

    log.info(
        "scheduled_decay_check_completed",
        decay_detected=decay_count,
        recoveries=recovery_count,
        consecutive_losses=loss_count,
    )
```

### Decay Detection API

**src/walltrack/api/routes/decay.py:**
```python
"""Decay detection API routes."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from walltrack.api.dependencies import (
    get_decay_detector,
    get_decay_event_repo,
    get_wallet_repo,
)
from walltrack.data.supabase.repositories.decay_event_repo import DecayEventRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository
from walltrack.discovery.decay_detector import DecayDetector

router = APIRouter(prefix="/decay", tags=["decay"])


class DecayCheckResponse(BaseModel):
    """Response from decay check."""

    events_detected: int
    decay_detected: int
    recoveries: int
    consecutive_losses: int


class DecayEventResponse(BaseModel):
    """Decay event response model."""

    id: str
    wallet_address: str
    event_type: str
    rolling_win_rate: float
    lifetime_win_rate: float
    consecutive_losses: int
    score_before: float
    score_after: float
    created_at: str


@router.post("/check", response_model=DecayCheckResponse)
async def run_decay_check(
    detector: Annotated[DecayDetector, Depends(get_decay_detector)],
) -> DecayCheckResponse:
    """
    Manually trigger decay check for all wallets.

    This is normally run on a schedule, but can be triggered manually.
    """
    events = await detector.check_all_wallets()

    return DecayCheckResponse(
        events_detected=len(events),
        decay_detected=sum(1 for e in events if e.event_type == "decay_detected"),
        recoveries=sum(1 for e in events if e.event_type == "recovery"),
        consecutive_losses=sum(1 for e in events if e.event_type == "consecutive_losses"),
    )


@router.post("/check/{address}")
async def check_wallet_decay(
    address: str,
    detector: Annotated[DecayDetector, Depends(get_decay_detector)],
    wallet_repo: Annotated[WalletRepository, Depends(get_wallet_repo)],
) -> dict[str, Any]:
    """Check decay for a specific wallet."""
    wallet = await wallet_repo.get_by_address(address)
    if not wallet:
        return {"error": "Wallet not found"}

    event = await detector.check_wallet_decay(wallet)

    return {
        "wallet": address,
        "event": event.to_dict() if event else None,
        "current_status": wallet.status.value,
        "rolling_win_rate": wallet.rolling_win_rate,
        "consecutive_losses": wallet.consecutive_losses,
    }


@router.get("/events", response_model=list[DecayEventResponse])
async def get_decay_events(
    repo: Annotated[DecayEventRepository, Depends(get_decay_event_repo)],
    event_type: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DecayEventResponse]:
    """Get recent decay events."""
    events = await repo.get_recent_events(event_type=event_type, limit=limit)
    return [DecayEventResponse(**e) for e in events]


@router.get("/events/{address}", response_model=list[DecayEventResponse])
async def get_wallet_decay_events(
    address: str,
    repo: Annotated[DecayEventRepository, Depends(get_decay_event_repo)],
    limit: int = Query(default=20, ge=1, le=100),
) -> list[DecayEventResponse]:
    """Get decay events for a specific wallet."""
    events = await repo.get_wallet_events(wallet_address=address, limit=limit)
    return [DecayEventResponse(**e) for e in events]
```

### Unit Tests

**tests/unit/discovery/test_decay_detector.py:**
```python
"""Tests for decay detector."""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

from walltrack.data.models.wallet import Wallet, WalletProfile, WalletStatus
from walltrack.discovery.decay_detector import (
    DecayDetector,
    DECAY_THRESHOLD,
    RECOVERY_THRESHOLD,
    CONSECUTIVE_LOSS_THRESHOLD,
    ROLLING_WINDOW_SIZE,
)


@dataclass
class MockTrade:
    """Mock trade for testing."""
    pnl: float
    executed_at: datetime


@pytest.fixture
def mock_wallet_repo() -> AsyncMock:
    """Mock wallet repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def mock_trade_repo() -> AsyncMock:
    """Mock trade repository."""
    repo = AsyncMock()
    return repo


@pytest.fixture
def detector(mock_wallet_repo: AsyncMock, mock_trade_repo: AsyncMock) -> DecayDetector:
    """Create detector with mocked dependencies."""
    return DecayDetector(
        wallet_repo=mock_wallet_repo,
        trade_repo=mock_trade_repo,
    )


class TestDecayDetector:
    """Tests for DecayDetector."""

    async def test_decay_detected_below_threshold(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test decay detection when win rate drops below threshold."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 30% win rate (6/20) - below 40% threshold
        trades = [
            MockTrade(pnl=10, executed_at=datetime.utcnow()) if i < 6
            else MockTrade(pnl=-5, executed_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "decay_detected"
        assert wallet.status == WalletStatus.DECAY_DETECTED
        assert wallet.score < 0.7  # Score should be reduced

    async def test_recovery_above_threshold(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test recovery when win rate exceeds recovery threshold."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.DECAY_DETECTED,
            score=0.5,
            decay_detected_at=datetime.utcnow(),
            profile=WalletProfile(win_rate=0.55, total_trades=50),
        )

        # 55% win rate (11/20) - above 50% recovery threshold
        trades = [
            MockTrade(pnl=10, executed_at=datetime.utcnow()) if i < 11
            else MockTrade(pnl=-5, executed_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "recovery"
        assert wallet.status == WalletStatus.ACTIVE
        assert wallet.decay_detected_at is None

    async def test_consecutive_losses_downgrade(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test score downgrade on consecutive losses."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=0,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 3 consecutive losses at the start (most recent)
        trades = [MockTrade(pnl=-5, executed_at=datetime.utcnow()) for _ in range(3)]
        trades.extend([MockTrade(pnl=10, executed_at=datetime.utcnow()) for _ in range(17)])
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is not None
        assert event.event_type == "consecutive_losses"
        assert wallet.consecutive_losses == 3
        assert wallet.score < 0.8

    async def test_no_event_for_healthy_wallet(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test no event for healthy performing wallet."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=50),
        )

        # 60% win rate - healthy
        trades = [
            MockTrade(pnl=10, executed_at=datetime.utcnow()) if i < 12
            else MockTrade(pnl=-5, executed_at=datetime.utcnow())
            for i in range(20)
        ]
        mock_trade_repo.get_wallet_trades.return_value = trades

        event = await detector.check_wallet_decay(wallet)

        assert event is None
        assert wallet.status == WalletStatus.ACTIVE

    async def test_insufficient_trades_skipped(
        self,
        detector: DecayDetector,
        mock_trade_repo: AsyncMock,
    ) -> None:
        """Test that wallets with insufficient trades are skipped."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.7,
            profile=WalletProfile(win_rate=0.6, total_trades=10),
        )

        mock_trade_repo.get_wallet_trades.return_value = [
            MockTrade(pnl=-5, executed_at=datetime.utcnow())
            for _ in range(10)
        ]

        event = await detector.check_wallet_decay(wallet)

        assert event is None  # Not enough trades

    async def test_record_trade_outcome_loss(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test recording a losing trade outcome."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=2,
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        event = await detector.record_trade_outcome(
            wallet_address="test_wallet",
            is_win=False,
            pnl=-10,
        )

        # Third consecutive loss triggers event
        assert event is not None
        assert event.event_type == "consecutive_losses"
        assert wallet.consecutive_losses == 3

    async def test_record_trade_outcome_win_resets(
        self,
        detector: DecayDetector,
        mock_wallet_repo: AsyncMock,
    ) -> None:
        """Test that a winning trade resets consecutive losses."""
        wallet = Wallet(
            address="test_wallet",
            status=WalletStatus.ACTIVE,
            score=0.8,
            consecutive_losses=2,
        )
        mock_wallet_repo.get_by_address.return_value = wallet

        event = await detector.record_trade_outcome(
            wallet_address="test_wallet",
            is_win=True,
            pnl=20,
        )

        assert event is None
        assert wallet.consecutive_losses == 0
```

## Implementation Tasks

- [ ] Create `src/walltrack/discovery/decay_detector.py`
- [ ] Create `src/walltrack/data/supabase/migrations/003_decay_events.sql`
- [ ] Create `src/walltrack/data/supabase/repositories/decay_event_repo.py`
- [ ] Implement rolling window calculation
- [ ] Implement decay threshold detection
- [ ] Add flagging mechanism
- [ ] Implement consecutive loss tracking
- [ ] Add recovery detection
- [ ] Create `src/walltrack/scheduler/tasks/decay_check_task.py`
- [ ] Create `src/walltrack/api/routes/decay.py`
- [ ] Write unit tests

## Definition of Done

- [ ] Decay detection identifies underperforming wallets
- [ ] Wallets flagged when threshold breached
- [ ] Recovery clears flags appropriately
- [ ] Periodic checks run on schedule
- [ ] All unit tests pass
- [ ] mypy and ruff pass
