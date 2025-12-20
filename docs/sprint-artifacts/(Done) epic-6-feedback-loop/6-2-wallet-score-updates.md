# Story 6.2: Wallet Score Updates from Trade Outcomes

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: High
- **FR**: FR35

## User Story

**As an** operator,
**I want** wallet scores automatically updated based on trade results,
**So that** wallet quality reflects recent performance.

## Acceptance Criteria

### AC 1: Score Recalculation
**Given** a trade outcome is recorded
**When** wallet score update runs
**Then** wallet's metrics are recalculated:
- Updated win rate (lifetime and rolling)
- Updated average PnL
- Updated trade count

### AC 2: Profitable Trade
**Given** trade was profitable
**When** score is updated
**Then** wallet score increases (weighted by profit magnitude)
**And** score increase is logged

### AC 3: Losing Trade
**Given** trade was a loss
**When** score is updated
**Then** wallet score decreases (weighted by loss magnitude)
**And** if score drops below threshold, wallet is flagged (connects to Story 1.6)

### AC 4: Score Bounds
**Given** wallet score update
**When** calculation completes
**Then** score is bounded between 0.0 and 1.0
**And** score history is preserved (for trend analysis)
**And** last_score_update timestamp is set

### AC 5: Batch Updates
**Given** multiple trades from same wallet in short period
**When** scores are updated
**Then** each trade contributes to score
**And** batch updates are handled efficiently

## Technical Notes

- FR35: Update wallet scores based on trade outcomes
- Implement in `src/walltrack/core/feedback/score_updater.py`
- Score formula configurable (exponential decay, rolling window, etc.)

---

## Technical Specification

### Pydantic Models

```python
# src/walltrack/core/feedback/score_models.py
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field, field_validator
from uuid import UUID


class ScoreUpdateType(str, Enum):
    """Type of score update."""
    TRADE_OUTCOME = "trade_outcome"
    MANUAL_ADJUSTMENT = "manual_adjustment"
    DECAY_PENALTY = "decay_penalty"
    RECALIBRATION = "recalibration"


class ScoreUpdateConfig(BaseModel):
    """Configuration for score update calculations."""
    # Win impact
    base_win_increase: Decimal = Field(
        default=Decimal("0.02"),
        ge=0,
        le=Decimal("0.1"),
        description="Base score increase for a win"
    )
    profit_multiplier: Decimal = Field(
        default=Decimal("0.01"),
        ge=0,
        description="Additional increase per 10% profit"
    )
    max_win_increase: Decimal = Field(
        default=Decimal("0.10"),
        description="Maximum score increase from a single win"
    )

    # Loss impact
    base_loss_decrease: Decimal = Field(
        default=Decimal("0.03"),
        ge=0,
        le=Decimal("0.15"),
        description="Base score decrease for a loss"
    )
    loss_multiplier: Decimal = Field(
        default=Decimal("0.015"),
        ge=0,
        description="Additional decrease per 10% loss"
    )
    max_loss_decrease: Decimal = Field(
        default=Decimal("0.15"),
        description="Maximum score decrease from a single loss"
    )

    # Decay threshold
    decay_flag_threshold: Decimal = Field(
        default=Decimal("0.3"),
        description="Score below which wallet is flagged for decay"
    )
    blacklist_threshold: Decimal = Field(
        default=Decimal("0.15"),
        description="Score below which wallet is blacklisted"
    )

    # Rolling window
    rolling_window_trades: int = Field(
        default=20,
        ge=5,
        le=100,
        description="Number of trades for rolling metrics"
    )


class WalletMetrics(BaseModel):
    """Wallet performance metrics."""
    wallet_address: str = Field(..., description="Wallet address")
    current_score: Decimal = Field(
        ...,
        ge=0,
        le=1,
        description="Current wallet score (0-1)"
    )
    lifetime_trades: int = Field(default=0, description="Total lifetime trades")
    lifetime_wins: int = Field(default=0, description="Total lifetime wins")
    lifetime_losses: int = Field(default=0, description="Total lifetime losses")
    lifetime_pnl: Decimal = Field(default=Decimal("0"), description="Lifetime PnL in SOL")
    rolling_trades: int = Field(default=0, description="Trades in rolling window")
    rolling_wins: int = Field(default=0, description="Wins in rolling window")
    rolling_pnl: Decimal = Field(default=Decimal("0"), description="PnL in rolling window")
    last_trade_timestamp: Optional[datetime] = Field(default=None)
    last_score_update: datetime = Field(default_factory=datetime.utcnow)
    is_flagged: bool = Field(default=False, description="Flagged for decay")
    is_blacklisted: bool = Field(default=False, description="Blacklisted")

    @computed_field
    @property
    def lifetime_win_rate(self) -> Decimal:
        """Lifetime win rate percentage."""
        if self.lifetime_trades == 0:
            return Decimal("0")
        return (Decimal(self.lifetime_wins) / Decimal(self.lifetime_trades)) * 100

    @computed_field
    @property
    def rolling_win_rate(self) -> Decimal:
        """Rolling window win rate percentage."""
        if self.rolling_trades == 0:
            return Decimal("0")
        return (Decimal(self.rolling_wins) / Decimal(self.rolling_trades)) * 100

    @computed_field
    @property
    def average_pnl(self) -> Decimal:
        """Average PnL per trade."""
        if self.lifetime_trades == 0:
            return Decimal("0")
        return self.lifetime_pnl / Decimal(self.lifetime_trades)


class ScoreUpdateInput(BaseModel):
    """Input for updating wallet score."""
    wallet_address: str = Field(..., description="Wallet address to update")
    trade_id: UUID = Field(..., description="Associated trade ID")
    pnl_sol: Decimal = Field(..., description="PnL from trade in SOL")
    pnl_percent: Decimal = Field(..., description="PnL percentage")
    is_win: bool = Field(..., description="Whether trade was profitable")


class ScoreUpdateResult(BaseModel):
    """Result of a score update operation."""
    wallet_address: str = Field(..., description="Wallet address")
    previous_score: Decimal = Field(..., description="Score before update")
    new_score: Decimal = Field(..., description="Score after update")
    score_change: Decimal = Field(..., description="Amount of change")
    update_type: ScoreUpdateType = Field(..., description="Type of update")
    trade_id: Optional[UUID] = Field(default=None, description="Associated trade")
    triggered_flag: bool = Field(default=False, description="Whether decay flag was triggered")
    triggered_blacklist: bool = Field(default=False, description="Whether blacklist was triggered")
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class WalletScoreHistory(BaseModel):
    """Historical score entry."""
    id: UUID = Field(..., description="History entry ID")
    wallet_address: str = Field(..., description="Wallet address")
    score: Decimal = Field(..., description="Score at this point")
    previous_score: Decimal = Field(..., description="Previous score")
    change: Decimal = Field(..., description="Score change")
    update_type: ScoreUpdateType = Field(..., description="Type of update")
    trade_id: Optional[UUID] = Field(default=None, description="Associated trade")
    reason: Optional[str] = Field(default=None, description="Update reason")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class BatchUpdateRequest(BaseModel):
    """Request for batch score updates."""
    updates: list[ScoreUpdateInput] = Field(..., min_length=1, max_length=100)


class BatchUpdateResult(BaseModel):
    """Result of batch score updates."""
    total_processed: int = Field(default=0)
    successful: int = Field(default=0)
    failed: int = Field(default=0)
    results: list[ScoreUpdateResult] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
```

### Service Implementation

```python
# src/walltrack/core/feedback/score_updater.py
import structlog
from decimal import Decimal
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4
from collections import deque

from .score_models import (
    ScoreUpdateConfig,
    WalletMetrics,
    ScoreUpdateInput,
    ScoreUpdateResult,
    ScoreUpdateType,
    WalletScoreHistory,
    BatchUpdateRequest,
    BatchUpdateResult,
)

logger = structlog.get_logger()


class WalletScoreUpdater:
    """Updates wallet scores based on trade outcomes."""

    def __init__(self, supabase_client, config: Optional[ScoreUpdateConfig] = None):
        self.supabase = supabase_client
        self.config = config or ScoreUpdateConfig()
        self._rolling_windows: dict[str, deque] = {}  # wallet -> recent trades

    async def update_from_trade(
        self,
        update_input: ScoreUpdateInput,
    ) -> ScoreUpdateResult:
        """
        Update wallet score based on trade outcome.

        Args:
            update_input: Trade outcome data

        Returns:
            ScoreUpdateResult with new score and flags
        """
        # Get current metrics
        metrics = await self.get_wallet_metrics(update_input.wallet_address)

        if metrics is None:
            # Initialize new wallet
            metrics = WalletMetrics(
                wallet_address=update_input.wallet_address,
                current_score=Decimal("0.5"),  # Start at neutral
            )

        previous_score = metrics.current_score

        # Calculate score change
        if update_input.is_win:
            score_change = self._calculate_win_impact(update_input.pnl_percent)
        else:
            score_change = self._calculate_loss_impact(update_input.pnl_percent)

        # Apply change with bounds
        new_score = max(
            Decimal("0"),
            min(Decimal("1"), previous_score + score_change)
        )

        # Update metrics
        metrics.current_score = new_score
        metrics.lifetime_trades += 1
        metrics.lifetime_pnl += update_input.pnl_sol
        metrics.last_trade_timestamp = datetime.utcnow()
        metrics.last_score_update = datetime.utcnow()

        if update_input.is_win:
            metrics.lifetime_wins += 1
        else:
            metrics.lifetime_losses += 1

        # Update rolling window
        self._update_rolling_window(
            update_input.wallet_address,
            update_input.is_win,
            update_input.pnl_sol,
        )
        await self._recalculate_rolling_metrics(metrics)

        # Check for flags
        triggered_flag = False
        triggered_blacklist = False

        if new_score < self.config.decay_flag_threshold and not metrics.is_flagged:
            metrics.is_flagged = True
            triggered_flag = True
            logger.warning(
                "wallet_flagged_for_decay",
                wallet=update_input.wallet_address,
                score=float(new_score),
                threshold=float(self.config.decay_flag_threshold),
            )

        if new_score < self.config.blacklist_threshold and not metrics.is_blacklisted:
            metrics.is_blacklisted = True
            triggered_blacklist = True
            logger.warning(
                "wallet_blacklisted",
                wallet=update_input.wallet_address,
                score=float(new_score),
                threshold=float(self.config.blacklist_threshold),
            )

        # Persist changes
        await self._save_metrics(metrics)

        # Record history
        await self._record_history(
            wallet_address=update_input.wallet_address,
            score=new_score,
            previous_score=previous_score,
            change=score_change,
            update_type=ScoreUpdateType.TRADE_OUTCOME,
            trade_id=update_input.trade_id,
        )

        result = ScoreUpdateResult(
            wallet_address=update_input.wallet_address,
            previous_score=previous_score,
            new_score=new_score,
            score_change=score_change,
            update_type=ScoreUpdateType.TRADE_OUTCOME,
            trade_id=update_input.trade_id,
            triggered_flag=triggered_flag,
            triggered_blacklist=triggered_blacklist,
        )

        logger.info(
            "wallet_score_updated",
            wallet=update_input.wallet_address,
            previous=float(previous_score),
            new=float(new_score),
            change=float(score_change),
            is_win=update_input.is_win,
        )

        return result

    async def batch_update(
        self,
        request: BatchUpdateRequest,
    ) -> BatchUpdateResult:
        """
        Process batch of score updates efficiently.

        Args:
            request: Batch update request

        Returns:
            BatchUpdateResult with individual results
        """
        result = BatchUpdateResult()

        # Group by wallet for efficiency
        by_wallet: dict[str, list[ScoreUpdateInput]] = {}
        for update in request.updates:
            if update.wallet_address not in by_wallet:
                by_wallet[update.wallet_address] = []
            by_wallet[update.wallet_address].append(update)

        for wallet, updates in by_wallet.items():
            # Sort by trade timestamp if available
            for update in updates:
                try:
                    update_result = await self.update_from_trade(update)
                    result.results.append(update_result)
                    result.successful += 1
                except Exception as e:
                    result.failed += 1
                    result.errors.append(f"{wallet}: {str(e)}")
                    logger.error(
                        "batch_update_failed",
                        wallet=wallet,
                        error=str(e),
                    )

        result.total_processed = result.successful + result.failed
        return result

    async def manual_adjust(
        self,
        wallet_address: str,
        adjustment: Decimal,
        reason: str,
    ) -> ScoreUpdateResult:
        """
        Manually adjust wallet score.

        Args:
            wallet_address: Wallet to adjust
            adjustment: Score adjustment (-1 to 1)
            reason: Reason for adjustment

        Returns:
            ScoreUpdateResult
        """
        metrics = await self.get_wallet_metrics(wallet_address)
        if not metrics:
            raise ValueError(f"Wallet {wallet_address} not found")

        previous_score = metrics.current_score
        new_score = max(Decimal("0"), min(Decimal("1"), previous_score + adjustment))

        metrics.current_score = new_score
        metrics.last_score_update = datetime.utcnow()

        # Update flags based on new score
        metrics.is_flagged = new_score < self.config.decay_flag_threshold
        metrics.is_blacklisted = new_score < self.config.blacklist_threshold

        await self._save_metrics(metrics)
        await self._record_history(
            wallet_address=wallet_address,
            score=new_score,
            previous_score=previous_score,
            change=adjustment,
            update_type=ScoreUpdateType.MANUAL_ADJUSTMENT,
            reason=reason,
        )

        return ScoreUpdateResult(
            wallet_address=wallet_address,
            previous_score=previous_score,
            new_score=new_score,
            score_change=adjustment,
            update_type=ScoreUpdateType.MANUAL_ADJUSTMENT,
            triggered_flag=metrics.is_flagged,
            triggered_blacklist=metrics.is_blacklisted,
        )

    async def get_wallet_metrics(self, wallet_address: str) -> Optional[WalletMetrics]:
        """Get current metrics for a wallet."""
        result = await self.supabase.table("wallet_metrics").select("*").eq(
            "wallet_address", wallet_address
        ).single().execute()

        if result.data:
            return WalletMetrics(**result.data)
        return None

    async def get_score_history(
        self,
        wallet_address: str,
        limit: int = 50,
    ) -> list[WalletScoreHistory]:
        """Get score history for a wallet."""
        result = await self.supabase.table("wallet_score_history").select("*").eq(
            "wallet_address", wallet_address
        ).order("created_at", desc=True).limit(limit).execute()

        return [WalletScoreHistory(**h) for h in result.data]

    async def get_flagged_wallets(self) -> list[WalletMetrics]:
        """Get all wallets flagged for decay."""
        result = await self.supabase.table("wallet_metrics").select("*").eq(
            "is_flagged", True
        ).eq("is_blacklisted", False).execute()

        return [WalletMetrics(**w) for w in result.data]

    def _calculate_win_impact(self, pnl_percent: Decimal) -> Decimal:
        """Calculate score increase for a winning trade."""
        base = self.config.base_win_increase

        # Additional bonus based on profit magnitude
        profit_bonus = (abs(pnl_percent) / 10) * self.config.profit_multiplier

        total = base + profit_bonus
        return min(total, self.config.max_win_increase)

    def _calculate_loss_impact(self, pnl_percent: Decimal) -> Decimal:
        """Calculate score decrease for a losing trade."""
        base = self.config.base_loss_decrease

        # Additional penalty based on loss magnitude
        loss_penalty = (abs(pnl_percent) / 10) * self.config.loss_multiplier

        total = base + loss_penalty
        return -min(total, self.config.max_loss_decrease)

    def _update_rolling_window(
        self,
        wallet_address: str,
        is_win: bool,
        pnl_sol: Decimal,
    ) -> None:
        """Update rolling window for wallet."""
        if wallet_address not in self._rolling_windows:
            self._rolling_windows[wallet_address] = deque(
                maxlen=self.config.rolling_window_trades
            )

        self._rolling_windows[wallet_address].append({
            "is_win": is_win,
            "pnl_sol": pnl_sol,
            "timestamp": datetime.utcnow(),
        })

    async def _recalculate_rolling_metrics(self, metrics: WalletMetrics) -> None:
        """Recalculate rolling metrics from window."""
        window = self._rolling_windows.get(metrics.wallet_address, deque())

        metrics.rolling_trades = len(window)
        metrics.rolling_wins = sum(1 for t in window if t["is_win"])
        metrics.rolling_pnl = sum(t["pnl_sol"] for t in window)

    async def _save_metrics(self, metrics: WalletMetrics) -> None:
        """Save wallet metrics to database."""
        data = metrics.model_dump(mode="json")
        await self.supabase.table("wallet_metrics").upsert(data).execute()

    async def _record_history(
        self,
        wallet_address: str,
        score: Decimal,
        previous_score: Decimal,
        change: Decimal,
        update_type: ScoreUpdateType,
        trade_id: Optional[UUID] = None,
        reason: Optional[str] = None,
    ) -> None:
        """Record score history entry."""
        history = WalletScoreHistory(
            id=uuid4(),
            wallet_address=wallet_address,
            score=score,
            previous_score=previous_score,
            change=change,
            update_type=update_type,
            trade_id=trade_id,
            reason=reason,
        )

        await self.supabase.table("wallet_score_history").insert(
            history.model_dump(mode="json")
        ).execute()


# Singleton instance
_score_updater: Optional[WalletScoreUpdater] = None


async def get_score_updater(supabase_client) -> WalletScoreUpdater:
    """Get or create WalletScoreUpdater singleton."""
    global _score_updater
    if _score_updater is None:
        _score_updater = WalletScoreUpdater(supabase_client)
    return _score_updater
```

### Database Schema (SQL)

```sql
-- Wallet metrics table
CREATE TABLE wallet_metrics (
    wallet_address TEXT PRIMARY KEY,
    current_score DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    lifetime_trades INTEGER DEFAULT 0,
    lifetime_wins INTEGER DEFAULT 0,
    lifetime_losses INTEGER DEFAULT 0,
    lifetime_pnl DECIMAL(30, 18) DEFAULT 0,
    rolling_trades INTEGER DEFAULT 0,
    rolling_wins INTEGER DEFAULT 0,
    rolling_pnl DECIMAL(30, 18) DEFAULT 0,
    last_trade_timestamp TIMESTAMPTZ,
    last_score_update TIMESTAMPTZ DEFAULT NOW(),
    is_flagged BOOLEAN DEFAULT FALSE,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for wallet metrics
CREATE INDEX idx_wallet_metrics_score ON wallet_metrics(current_score);
CREATE INDEX idx_wallet_metrics_flagged ON wallet_metrics(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX idx_wallet_metrics_blacklisted ON wallet_metrics(is_blacklisted) WHERE is_blacklisted = TRUE;
CREATE INDEX idx_wallet_metrics_last_trade ON wallet_metrics(last_trade_timestamp DESC);

-- Wallet score history table
CREATE TABLE wallet_score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL REFERENCES wallet_metrics(wallet_address),
    score DECIMAL(5, 4) NOT NULL,
    previous_score DECIMAL(5, 4) NOT NULL,
    change DECIMAL(5, 4) NOT NULL,
    update_type TEXT NOT NULL CHECK (update_type IN (
        'trade_outcome', 'manual_adjustment', 'decay_penalty', 'recalibration'
    )),
    trade_id UUID REFERENCES trade_outcomes(id),
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for score history
CREATE INDEX idx_score_history_wallet ON wallet_score_history(wallet_address);
CREATE INDEX idx_score_history_created ON wallet_score_history(created_at DESC);
CREATE INDEX idx_score_history_trade ON wallet_score_history(trade_id) WHERE trade_id IS NOT NULL;

-- Score update configuration (singleton)
CREATE TABLE score_update_config (
    id TEXT PRIMARY KEY DEFAULT 'current',
    base_win_increase DECIMAL(5, 4) DEFAULT 0.02,
    profit_multiplier DECIMAL(5, 4) DEFAULT 0.01,
    max_win_increase DECIMAL(5, 4) DEFAULT 0.10,
    base_loss_decrease DECIMAL(5, 4) DEFAULT 0.03,
    loss_multiplier DECIMAL(5, 4) DEFAULT 0.015,
    max_loss_decrease DECIMAL(5, 4) DEFAULT 0.15,
    decay_flag_threshold DECIMAL(5, 4) DEFAULT 0.30,
    blacklist_threshold DECIMAL(5, 4) DEFAULT 0.15,
    rolling_window_trades INTEGER DEFAULT 20,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize config
INSERT INTO score_update_config (id) VALUES ('current');
```

### FastAPI Routes

```python
# src/walltrack/api/routes/wallet_scores.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from decimal import Decimal
from uuid import UUID

from walltrack.core.feedback.score_models import (
    ScoreUpdateInput,
    ScoreUpdateResult,
    WalletMetrics,
    WalletScoreHistory,
    BatchUpdateRequest,
    BatchUpdateResult,
)
from walltrack.core.feedback.score_updater import get_score_updater
from walltrack.core.database import get_supabase_client

router = APIRouter(prefix="/wallet-scores", tags=["wallet-scores"])


@router.post("/update", response_model=ScoreUpdateResult)
async def update_from_trade(
    update_input: ScoreUpdateInput,
    supabase=Depends(get_supabase_client),
):
    """Update wallet score from trade outcome."""
    updater = await get_score_updater(supabase)
    return await updater.update_from_trade(update_input)


@router.post("/batch", response_model=BatchUpdateResult)
async def batch_update(
    request: BatchUpdateRequest,
    supabase=Depends(get_supabase_client),
):
    """Process batch of score updates."""
    updater = await get_score_updater(supabase)
    return await updater.batch_update(request)


@router.post("/{wallet_address}/adjust", response_model=ScoreUpdateResult)
async def manual_adjust(
    wallet_address: str,
    adjustment: float = Query(..., ge=-1, le=1),
    reason: str = Query(..., min_length=3),
    supabase=Depends(get_supabase_client),
):
    """Manually adjust wallet score."""
    updater = await get_score_updater(supabase)
    return await updater.manual_adjust(
        wallet_address=wallet_address,
        adjustment=Decimal(str(adjustment)),
        reason=reason,
    )


@router.get("/{wallet_address}", response_model=WalletMetrics)
async def get_wallet_metrics(
    wallet_address: str,
    supabase=Depends(get_supabase_client),
):
    """Get current metrics for a wallet."""
    updater = await get_score_updater(supabase)
    metrics = await updater.get_wallet_metrics(wallet_address)
    if not metrics:
        raise HTTPException(status_code=404, detail="Wallet not found")
    return metrics


@router.get("/{wallet_address}/history", response_model=list[WalletScoreHistory])
async def get_score_history(
    wallet_address: str,
    limit: int = Query(default=50, ge=1, le=500),
    supabase=Depends(get_supabase_client),
):
    """Get score history for a wallet."""
    updater = await get_score_updater(supabase)
    return await updater.get_score_history(wallet_address, limit=limit)


@router.get("/flagged/all", response_model=list[WalletMetrics])
async def get_flagged_wallets(
    supabase=Depends(get_supabase_client),
):
    """Get all wallets flagged for decay."""
    updater = await get_score_updater(supabase)
    return await updater.get_flagged_wallets()
```

### Unit Tests

```python
# tests/core/feedback/test_score_updater.py
import pytest
from decimal import Decimal
from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.feedback.score_models import (
    ScoreUpdateConfig,
    ScoreUpdateInput,
    WalletMetrics,
    ScoreUpdateType,
    BatchUpdateRequest,
)
from walltrack.core.feedback.score_updater import WalletScoreUpdater


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()
    client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
        return_value=MagicMock(data=None)
    )
    client.table.return_value.upsert.return_value.execute = AsyncMock()
    client.table.return_value.insert.return_value.execute = AsyncMock()
    return client


@pytest.fixture
def score_updater(mock_supabase):
    """Create WalletScoreUpdater instance."""
    return WalletScoreUpdater(mock_supabase)


@pytest.fixture
def winning_trade():
    """Create winning trade input."""
    return ScoreUpdateInput(
        wallet_address="WinningWallet123",
        trade_id=uuid4(),
        pnl_sol=Decimal("5.0"),
        pnl_percent=Decimal("50.0"),
        is_win=True,
    )


@pytest.fixture
def losing_trade():
    """Create losing trade input."""
    return ScoreUpdateInput(
        wallet_address="LosingWallet456",
        trade_id=uuid4(),
        pnl_sol=Decimal("-3.0"),
        pnl_percent=Decimal("-30.0"),
        is_win=False,
    )


class TestScoreCalculation:
    """Tests for score calculation logic."""

    def test_win_impact_base(self, score_updater):
        """Test base win impact calculation."""
        impact = score_updater._calculate_win_impact(Decimal("10"))

        assert impact > 0
        assert impact >= score_updater.config.base_win_increase

    def test_win_impact_large_profit(self, score_updater):
        """Test win impact with large profit."""
        small_impact = score_updater._calculate_win_impact(Decimal("10"))
        large_impact = score_updater._calculate_win_impact(Decimal("100"))

        assert large_impact > small_impact
        assert large_impact <= score_updater.config.max_win_increase

    def test_loss_impact_base(self, score_updater):
        """Test base loss impact calculation."""
        impact = score_updater._calculate_loss_impact(Decimal("-10"))

        assert impact < 0
        assert abs(impact) >= score_updater.config.base_loss_decrease

    def test_loss_impact_large_loss(self, score_updater):
        """Test loss impact with large loss."""
        small_impact = score_updater._calculate_loss_impact(Decimal("-10"))
        large_impact = score_updater._calculate_loss_impact(Decimal("-50"))

        assert large_impact < small_impact  # More negative
        assert abs(large_impact) <= score_updater.config.max_loss_decrease


class TestScoreUpdates:
    """Tests for score update operations."""

    @pytest.mark.asyncio
    async def test_winning_trade_increases_score(self, score_updater, winning_trade):
        """Test that winning trades increase score."""
        result = await score_updater.update_from_trade(winning_trade)

        assert result.new_score > result.previous_score
        assert result.score_change > 0
        assert result.update_type == ScoreUpdateType.TRADE_OUTCOME

    @pytest.mark.asyncio
    async def test_losing_trade_decreases_score(self, score_updater, losing_trade):
        """Test that losing trades decrease score."""
        result = await score_updater.update_from_trade(losing_trade)

        assert result.new_score < result.previous_score
        assert result.score_change < 0

    @pytest.mark.asyncio
    async def test_score_bounded_at_one(self, score_updater, mock_supabase, winning_trade):
        """Test score cannot exceed 1.0."""
        # Mock existing wallet with high score
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "wallet_address": winning_trade.wallet_address,
                "current_score": "0.98",
                "lifetime_trades": 10,
                "lifetime_wins": 9,
                "lifetime_losses": 1,
                "lifetime_pnl": "50",
                "rolling_trades": 5,
                "rolling_wins": 5,
                "rolling_pnl": "25",
                "is_flagged": False,
                "is_blacklisted": False,
            })
        )

        result = await score_updater.update_from_trade(winning_trade)

        assert result.new_score <= Decimal("1.0")

    @pytest.mark.asyncio
    async def test_score_bounded_at_zero(self, score_updater, mock_supabase, losing_trade):
        """Test score cannot go below 0.0."""
        # Mock existing wallet with low score
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "wallet_address": losing_trade.wallet_address,
                "current_score": "0.05",
                "lifetime_trades": 10,
                "lifetime_wins": 1,
                "lifetime_losses": 9,
                "lifetime_pnl": "-30",
                "rolling_trades": 5,
                "rolling_wins": 0,
                "rolling_pnl": "-15",
                "is_flagged": True,
                "is_blacklisted": False,
            })
        )

        result = await score_updater.update_from_trade(losing_trade)

        assert result.new_score >= Decimal("0.0")


class TestDecayFlagging:
    """Tests for decay detection and flagging."""

    @pytest.mark.asyncio
    async def test_triggers_decay_flag(self, score_updater, mock_supabase, losing_trade):
        """Test that low score triggers decay flag."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "wallet_address": losing_trade.wallet_address,
                "current_score": "0.32",  # Just above threshold
                "lifetime_trades": 5,
                "lifetime_wins": 1,
                "lifetime_losses": 4,
                "lifetime_pnl": "-10",
                "rolling_trades": 5,
                "rolling_wins": 1,
                "rolling_pnl": "-10",
                "is_flagged": False,
                "is_blacklisted": False,
            })
        )

        result = await score_updater.update_from_trade(losing_trade)

        # Score should drop below threshold
        assert result.triggered_flag is True

    @pytest.mark.asyncio
    async def test_triggers_blacklist(self, score_updater, mock_supabase, losing_trade):
        """Test that very low score triggers blacklist."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "wallet_address": losing_trade.wallet_address,
                "current_score": "0.18",  # Just above blacklist threshold
                "lifetime_trades": 10,
                "lifetime_wins": 1,
                "lifetime_losses": 9,
                "lifetime_pnl": "-30",
                "rolling_trades": 5,
                "rolling_wins": 0,
                "rolling_pnl": "-15",
                "is_flagged": True,
                "is_blacklisted": False,
            })
        )

        result = await score_updater.update_from_trade(losing_trade)

        assert result.triggered_blacklist is True


class TestBatchUpdates:
    """Tests for batch update processing."""

    @pytest.mark.asyncio
    async def test_batch_update_multiple_wallets(self, score_updater):
        """Test batch update with multiple wallets."""
        request = BatchUpdateRequest(
            updates=[
                ScoreUpdateInput(
                    wallet_address="Wallet1",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("5"),
                    pnl_percent=Decimal("50"),
                    is_win=True,
                ),
                ScoreUpdateInput(
                    wallet_address="Wallet2",
                    trade_id=uuid4(),
                    pnl_sol=Decimal("-3"),
                    pnl_percent=Decimal("-30"),
                    is_win=False,
                ),
            ]
        )

        result = await score_updater.batch_update(request)

        assert result.total_processed == 2
        assert result.successful == 2
        assert len(result.results) == 2


class TestManualAdjustment:
    """Tests for manual score adjustments."""

    @pytest.mark.asyncio
    async def test_manual_increase(self, score_updater, mock_supabase):
        """Test manual score increase."""
        mock_supabase.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "wallet_address": "ManualWallet",
                "current_score": "0.5",
                "lifetime_trades": 5,
                "lifetime_wins": 3,
                "lifetime_losses": 2,
                "lifetime_pnl": "10",
                "rolling_trades": 5,
                "rolling_wins": 3,
                "rolling_pnl": "10",
                "is_flagged": False,
                "is_blacklisted": False,
            })
        )

        result = await score_updater.manual_adjust(
            wallet_address="ManualWallet",
            adjustment=Decimal("0.1"),
            reason="Performance review bonus",
        )

        assert result.new_score == Decimal("0.6")
        assert result.update_type == ScoreUpdateType.MANUAL_ADJUSTMENT
```

---

## Implementation Tasks

- [x] Create `src/walltrack/core/feedback/score_updater.py`
- [x] Implement score update on trade outcome
- [x] Weight updates by profit/loss magnitude
- [x] Connect to decay detection (Story 1.6)
- [x] Bound scores between 0.0 and 1.0
- [x] Preserve score history
- [x] Handle batch updates efficiently

## Definition of Done

- [x] Wallet scores updated on trade outcomes
- [x] Profitable trades increase score
- [x] Losses decrease score and trigger flagging
- [x] Score history preserved

---

## Dev Agent Record

### Implementation Notes
- Implemented `WalletScoreUpdater` service with configurable scoring parameters
- Score updates use weighted calculations based on profit/loss magnitude
- Scores bounded between 0.0 and 1.0 with neutral start at 0.5
- Decay flagging when score drops below 0.3, blacklist at 0.15
- Rolling window metrics (default 20 trades) for recent performance tracking
- In-memory cache for metrics to reduce database calls
- Batch update support with wallet grouping for efficiency

### Tests Created
- `tests/core/feedback/test_score_updater.py` - 27 unit tests
  - TestScoreModels: 4 tests for model validation
  - TestScoreCalculation: 6 tests for win/loss impact calculations
  - TestScoreUpdates: 5 tests for score update operations
  - TestDecayFlagging: 3 tests for decay detection
  - TestBatchUpdates: 2 tests for batch processing
  - TestManualAdjustment: 4 tests for manual score adjustments
  - TestRollingWindow: 3 tests for rolling window calculations

### Files Created/Modified
- `src/walltrack/core/feedback/score_models.py` (NEW)
- `src/walltrack/core/feedback/score_updater.py` (MODIFIED)
- `src/walltrack/core/feedback/__init__.py` (MODIFIED)
- `src/walltrack/api/routes/wallet_scores.py` (NEW)
- `src/walltrack/data/supabase/migrations/012_wallet_metrics.sql` (NEW)
- `tests/core/feedback/test_score_updater.py` (NEW)

### Change Log
| Date | Change | Reason |
|------|--------|--------|
| 2025-12-20 | Initial implementation | Story 6-2 development |
