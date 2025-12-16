# Story 6.4: Signal Accuracy Tracking

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: Medium
- **FR**: FR37

## User Story

**As an** operator,
**I want** to track how accurate signals are over time,
**So that** I can assess system quality.

## Acceptance Criteria

### AC 1: Accuracy Calculation
**Given** signals that became trades
**When** accuracy is calculated
**Then** metrics include:
- Signal-to-win rate: % of signals that resulted in profitable trades
- Average score of winning signals vs losing signals
- Score threshold effectiveness (what threshold would maximize profit?)

### AC 2: Retrospective Analysis
**Given** signals that were NOT traded (below threshold)
**When** retrospective analysis runs (optional)
**Then** simulated outcome is estimated (what would have happened?)
**And** "missed opportunities" are identified
**And** "bullets dodged" are identified

### AC 3: Trend Analysis
**Given** accuracy tracking over time
**When** trend analysis runs
**Then** accuracy trend is calculated (improving, stable, declining)
**And** trend visualization is available in dashboard

### AC 4: Factor Breakdown
**Given** accuracy by factor
**When** breakdown is requested
**Then** accuracy contribution by each factor is shown
**And** which factors are predictive vs noise is identified

## Technical Notes

- FR37: Track signal accuracy over time
- Implement in `src/walltrack/core/feedback/accuracy_tracker.py`
- Store accuracy metrics in Supabase

---

## Technical Specification

### Pydantic Models

```python
# src/walltrack/core/feedback/accuracy_models.py
from enum import Enum
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from uuid import UUID


class AccuracyTrend(str, Enum):
    """Accuracy trend direction."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"


class RetrospectiveOutcome(str, Enum):
    """Outcome classification for non-traded signals."""
    MISSED_OPPORTUNITY = "missed_opportunity"  # Would have been profitable
    BULLET_DODGED = "bullet_dodged"  # Would have been a loss
    UNCERTAIN = "uncertain"  # Not enough data


class SignalAccuracyMetrics(BaseModel):
    """Accuracy metrics for signals."""
    period_start: datetime = Field(..., description="Start of measurement period")
    period_end: datetime = Field(..., description="End of measurement period")
    total_signals: int = Field(default=0, description="Total signals generated")
    traded_signals: int = Field(default=0, description="Signals that became trades")
    winning_trades: int = Field(default=0, description="Trades that were profitable")
    losing_trades: int = Field(default=0, description="Trades that were losses")
    avg_score_winners: Decimal = Field(default=Decimal("0"), description="Average score of winning signals")
    avg_score_losers: Decimal = Field(default=Decimal("0"), description="Average score of losing signals")
    optimal_threshold: Decimal = Field(default=Decimal("0.6"), description="Threshold that would maximize profit")

    @computed_field
    @property
    def signal_to_trade_rate(self) -> Decimal:
        """Percentage of signals that became trades."""
        if self.total_signals == 0:
            return Decimal("0")
        return (Decimal(self.traded_signals) / Decimal(self.total_signals)) * 100

    @computed_field
    @property
    def signal_to_win_rate(self) -> Decimal:
        """Percentage of traded signals that won."""
        if self.traded_signals == 0:
            return Decimal("0")
        return (Decimal(self.winning_trades) / Decimal(self.traded_signals)) * 100

    @computed_field
    @property
    def score_differential(self) -> Decimal:
        """Difference between winner and loser average scores."""
        return self.avg_score_winners - self.avg_score_losers


class ThresholdAnalysis(BaseModel):
    """Analysis of different threshold effectiveness."""
    threshold: Decimal = Field(..., description="Score threshold")
    would_trade_count: int = Field(default=0, description="Signals above threshold")
    would_win_count: int = Field(default=0, description="Would-be wins")
    would_lose_count: int = Field(default=0, description="Would-be losses")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at threshold")
    total_pnl: Decimal = Field(default=Decimal("0"), description="Total PnL at threshold")
    profit_factor: Decimal = Field(default=Decimal("0"), description="Profit factor at threshold")


class RetrospectiveSignal(BaseModel):
    """Signal that was not traded with retrospective analysis."""
    signal_id: UUID = Field(..., description="Signal ID")
    signal_score: Decimal = Field(..., description="Signal score")
    token_address: str = Field(..., description="Token address")
    wallet_address: str = Field(..., description="Originating wallet")
    signal_timestamp: datetime = Field(..., description="When signal was generated")
    threshold_at_time: Decimal = Field(..., description="Trading threshold at signal time")
    outcome: RetrospectiveOutcome = Field(..., description="Retrospective classification")
    estimated_pnl: Optional[Decimal] = Field(default=None, description="Estimated PnL if traded")
    price_at_signal: Optional[Decimal] = Field(default=None, description="Token price at signal")
    peak_price_after: Optional[Decimal] = Field(default=None, description="Peak price in window")
    min_price_after: Optional[Decimal] = Field(default=None, description="Min price in window")


class RetrospectiveAnalysis(BaseModel):
    """Summary of retrospective analysis."""
    period_start: datetime = Field(..., description="Analysis period start")
    period_end: datetime = Field(..., description="Analysis period end")
    total_non_traded: int = Field(default=0, description="Total non-traded signals")
    missed_opportunities: int = Field(default=0, description="Signals that would have won")
    bullets_dodged: int = Field(default=0, description="Signals that would have lost")
    uncertain: int = Field(default=0, description="Uncertain outcomes")
    total_missed_pnl: Decimal = Field(default=Decimal("0"), description="PnL from missed opportunities")
    total_avoided_loss: Decimal = Field(default=Decimal("0"), description="Loss avoided by not trading")
    signals: list[RetrospectiveSignal] = Field(default_factory=list)


class AccuracySnapshot(BaseModel):
    """Point-in-time accuracy snapshot for trend analysis."""
    id: UUID = Field(..., description="Snapshot ID")
    snapshot_date: datetime = Field(..., description="Date of snapshot")
    signal_to_win_rate: Decimal = Field(..., description="Win rate at snapshot")
    sample_size: int = Field(..., description="Number of trades in sample")
    avg_signal_score: Decimal = Field(..., description="Average signal score")
    score_differential: Decimal = Field(..., description="Winner vs loser score diff")


class AccuracyTrendAnalysis(BaseModel):
    """Accuracy trend over time."""
    period_start: datetime = Field(..., description="Trend analysis start")
    period_end: datetime = Field(..., description="Trend analysis end")
    snapshots: list[AccuracySnapshot] = Field(default_factory=list)
    trend: AccuracyTrend = Field(..., description="Overall trend direction")
    trend_slope: Decimal = Field(default=Decimal("0"), description="Trend slope (% change per week)")
    start_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at start")
    end_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate at end")
    confidence: Decimal = Field(default=Decimal("0"), description="Trend confidence 0-1")


class FactorAccuracyBreakdown(BaseModel):
    """Accuracy broken down by scoring factor."""
    factor_name: str = Field(..., description="Factor name")
    high_score_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate when factor score high")
    low_score_win_rate: Decimal = Field(default=Decimal("0"), description="Win rate when factor score low")
    is_predictive: bool = Field(default=False, description="Whether factor is predictive")
    correlation_with_outcome: Decimal = Field(default=Decimal("0"), description="Correlation with trade outcome")
    recommended_weight_adjustment: str = Field(default="none", description="Weight adjustment recommendation")
```

### Service Implementation

```python
# src/walltrack/core/feedback/accuracy_tracker.py
import structlog
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
from statistics import linear_regression

from .accuracy_models import (
    AccuracyTrend,
    RetrospectiveOutcome,
    SignalAccuracyMetrics,
    ThresholdAnalysis,
    RetrospectiveSignal,
    RetrospectiveAnalysis,
    AccuracySnapshot,
    AccuracyTrendAnalysis,
    FactorAccuracyBreakdown,
)

logger = structlog.get_logger()


class AccuracyTracker:
    """Tracks signal accuracy and provides analysis."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def calculate_accuracy_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> SignalAccuracyMetrics:
        """
        Calculate accuracy metrics for a period.

        Args:
            start_date: Period start (default: 30 days ago)
            end_date: Period end (default: now)

        Returns:
            SignalAccuracyMetrics
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Load signals and trades
        signals = await self._load_signals(start_date, end_date)
        trades = await self._load_trades_for_signals([s["id"] for s in signals])

        traded_signal_ids = {t["signal_id"] for t in trades}
        winning_trades = [t for t in trades if t.get("is_win")]
        losing_trades = [t for t in trades if not t.get("is_win")]

        # Calculate average scores
        avg_winners = (
            sum(Decimal(str(s["score"])) for s in signals if s["id"] in {t["signal_id"] for t in winning_trades})
            / len(winning_trades) if winning_trades else Decimal("0")
        )
        avg_losers = (
            sum(Decimal(str(s["score"])) for s in signals if s["id"] in {t["signal_id"] for t in losing_trades})
            / len(losing_trades) if losing_trades else Decimal("0")
        )

        # Find optimal threshold
        optimal_threshold = await self._find_optimal_threshold(signals, trades)

        metrics = SignalAccuracyMetrics(
            period_start=start_date,
            period_end=end_date,
            total_signals=len(signals),
            traded_signals=len(traded_signal_ids),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            avg_score_winners=avg_winners,
            avg_score_losers=avg_losers,
            optimal_threshold=optimal_threshold,
        )

        # Persist snapshot
        await self._save_snapshot(metrics)

        logger.info(
            "accuracy_metrics_calculated",
            period=f"{start_date.date()} to {end_date.date()}",
            win_rate=float(metrics.signal_to_win_rate),
            score_diff=float(metrics.score_differential),
        )

        return metrics

    async def analyze_thresholds(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> list[ThresholdAnalysis]:
        """
        Analyze different threshold effectiveness.

        Returns:
            List of ThresholdAnalysis for each threshold
        """
        if not end_date:
            end_date = datetime.utcnow()
        if not start_date:
            start_date = end_date - timedelta(days=30)

        signals = await self._load_signals(start_date, end_date)
        trades = await self._load_trades_for_signals([s["id"] for s in signals])

        trade_map = {t["signal_id"]: t for t in trades}

        analyses = []
        for threshold in [Decimal(str(t / 100)) for t in range(40, 90, 5)]:
            above_threshold = [s for s in signals if Decimal(str(s["score"])) >= threshold]

            wins = 0
            losses = 0
            total_pnl = Decimal("0")

            for signal in above_threshold:
                trade = trade_map.get(signal["id"])
                if trade:
                    if trade.get("is_win"):
                        wins += 1
                    else:
                        losses += 1
                    total_pnl += Decimal(str(trade.get("realized_pnl_sol", 0)))

            win_rate = Decimal(wins) / Decimal(wins + losses) * 100 if (wins + losses) > 0 else Decimal("0")
            gross_loss = sum(Decimal(str(trade_map.get(s["id"], {}).get("realized_pnl_sol", 0))) for s in above_threshold if trade_map.get(s["id"], {}).get("is_win") is False)
            profit_factor = abs(total_pnl - gross_loss) / abs(gross_loss) if gross_loss != 0 else Decimal("999")

            analyses.append(ThresholdAnalysis(
                threshold=threshold,
                would_trade_count=len(above_threshold),
                would_win_count=wins,
                would_lose_count=losses,
                win_rate=win_rate,
                total_pnl=total_pnl,
                profit_factor=profit_factor,
            ))

        return analyses

    async def run_retrospective_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        price_window_hours: int = 24,
    ) -> RetrospectiveAnalysis:
        """
        Analyze signals that were not traded.

        Args:
            start_date: Period start
            end_date: Period end
            price_window_hours: Hours to look forward for price

        Returns:
            RetrospectiveAnalysis
        """
        if not end_date:
            end_date = datetime.utcnow() - timedelta(hours=price_window_hours)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        signals = await self._load_signals(start_date, end_date)
        trades = await self._load_trades_for_signals([s["id"] for s in signals])

        traded_ids = {t["signal_id"] for t in trades}
        non_traded = [s for s in signals if s["id"] not in traded_ids]

        retrospective_signals = []
        missed_count = 0
        dodged_count = 0
        uncertain_count = 0
        total_missed_pnl = Decimal("0")
        total_avoided_loss = Decimal("0")

        for signal in non_traded:
            # Get price data
            price_data = await self._get_price_data(
                signal["token_address"],
                signal["created_at"],
                price_window_hours,
            )

            if not price_data:
                outcome = RetrospectiveOutcome.UNCERTAIN
                uncertain_count += 1
                estimated_pnl = None
            else:
                price_at_signal = price_data.get("price_at_signal")
                peak_price = price_data.get("peak_price")
                min_price = price_data.get("min_price")

                # Simulate trade with basic exit logic
                estimated_pnl = self._estimate_trade_pnl(
                    price_at_signal, peak_price, min_price
                )

                if estimated_pnl > 0:
                    outcome = RetrospectiveOutcome.MISSED_OPPORTUNITY
                    missed_count += 1
                    total_missed_pnl += estimated_pnl
                else:
                    outcome = RetrospectiveOutcome.BULLET_DODGED
                    dodged_count += 1
                    total_avoided_loss += abs(estimated_pnl)

            retrospective_signals.append(RetrospectiveSignal(
                signal_id=UUID(signal["id"]),
                signal_score=Decimal(str(signal["score"])),
                token_address=signal["token_address"],
                wallet_address=signal["wallet_address"],
                signal_timestamp=datetime.fromisoformat(signal["created_at"]),
                threshold_at_time=Decimal(str(signal.get("threshold", 0.6))),
                outcome=outcome,
                estimated_pnl=estimated_pnl,
                price_at_signal=price_data.get("price_at_signal") if price_data else None,
                peak_price_after=price_data.get("peak_price") if price_data else None,
                min_price_after=price_data.get("min_price") if price_data else None,
            ))

        analysis = RetrospectiveAnalysis(
            period_start=start_date,
            period_end=end_date,
            total_non_traded=len(non_traded),
            missed_opportunities=missed_count,
            bullets_dodged=dodged_count,
            uncertain=uncertain_count,
            total_missed_pnl=total_missed_pnl,
            total_avoided_loss=total_avoided_loss,
            signals=retrospective_signals[:100],  # Limit response size
        )

        logger.info(
            "retrospective_analysis_complete",
            non_traded=len(non_traded),
            missed=missed_count,
            dodged=dodged_count,
            missed_pnl=float(total_missed_pnl),
        )

        return analysis

    async def analyze_trend(
        self,
        weeks: int = 8,
    ) -> AccuracyTrendAnalysis:
        """
        Analyze accuracy trend over time.

        Args:
            weeks: Number of weeks to analyze

        Returns:
            AccuracyTrendAnalysis
        """
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(weeks=weeks)

        # Load historical snapshots
        result = await self.supabase.table("accuracy_snapshots").select("*").gte(
            "snapshot_date", start_date.isoformat()
        ).order("snapshot_date").execute()

        snapshots = [AccuracySnapshot(**s) for s in result.data]

        if len(snapshots) < 3:
            return AccuracyTrendAnalysis(
                period_start=start_date,
                period_end=end_date,
                snapshots=snapshots,
                trend=AccuracyTrend.STABLE,
                confidence=Decimal("0"),
            )

        # Calculate trend using linear regression
        x_values = [(s.snapshot_date - start_date).days for s in snapshots]
        y_values = [float(s.signal_to_win_rate) for s in snapshots]

        slope, intercept = linear_regression(x_values, y_values)

        # Classify trend
        weekly_change = slope * 7
        if weekly_change > 1:
            trend = AccuracyTrend.IMPROVING
        elif weekly_change < -1:
            trend = AccuracyTrend.DECLINING
        else:
            trend = AccuracyTrend.STABLE

        return AccuracyTrendAnalysis(
            period_start=start_date,
            period_end=end_date,
            snapshots=snapshots,
            trend=trend,
            trend_slope=Decimal(str(weekly_change)).quantize(Decimal("0.01")),
            start_win_rate=snapshots[0].signal_to_win_rate if snapshots else Decimal("0"),
            end_win_rate=snapshots[-1].signal_to_win_rate if snapshots else Decimal("0"),
            confidence=Decimal("0.8") if len(snapshots) >= 5 else Decimal("0.5"),
        )

    async def breakdown_by_factor(self) -> list[FactorAccuracyBreakdown]:
        """
        Break down accuracy by scoring factor.

        Returns:
            List of FactorAccuracyBreakdown
        """
        factors = ["wallet_score", "cluster_score", "token_score", "context_score"]
        breakdowns = []

        for factor in factors:
            # Load signals with factor scores and outcomes
            trades = await self._load_trades_with_factor_scores()

            high_threshold = Decimal("0.7")
            high_score_trades = [t for t in trades if Decimal(str(t.get(factor, 0))) >= high_threshold]
            low_score_trades = [t for t in trades if Decimal(str(t.get(factor, 0))) < high_threshold]

            high_win_rate = (
                sum(1 for t in high_score_trades if t.get("is_win")) / len(high_score_trades) * 100
                if high_score_trades else 0
            )
            low_win_rate = (
                sum(1 for t in low_score_trades if t.get("is_win")) / len(low_score_trades) * 100
                if low_score_trades else 0
            )

            is_predictive = high_win_rate > low_win_rate + 5

            if is_predictive and high_win_rate - low_win_rate > 10:
                recommendation = "increase"
            elif not is_predictive:
                recommendation = "decrease"
            else:
                recommendation = "none"

            breakdowns.append(FactorAccuracyBreakdown(
                factor_name=factor,
                high_score_win_rate=Decimal(str(high_win_rate)),
                low_score_win_rate=Decimal(str(low_win_rate)),
                is_predictive=is_predictive,
                correlation_with_outcome=Decimal(str((high_win_rate - low_win_rate) / 100)),
                recommended_weight_adjustment=recommendation,
            ))

        return breakdowns

    async def _find_optimal_threshold(self, signals: list, trades: list) -> Decimal:
        """Find threshold that maximizes profit."""
        trade_map = {t["signal_id"]: t for t in trades}
        best_threshold = Decimal("0.6")
        best_pnl = Decimal("-999999")

        for threshold in [Decimal(str(t / 100)) for t in range(40, 90, 5)]:
            pnl = Decimal("0")
            for signal in signals:
                if Decimal(str(signal["score"])) >= threshold:
                    trade = trade_map.get(signal["id"])
                    if trade:
                        pnl += Decimal(str(trade.get("realized_pnl_sol", 0)))

            if pnl > best_pnl:
                best_pnl = pnl
                best_threshold = threshold

        return best_threshold

    def _estimate_trade_pnl(
        self,
        entry_price: Decimal,
        peak_price: Decimal,
        min_price: Decimal,
    ) -> Decimal:
        """Estimate trade PnL based on price movement."""
        if not entry_price or entry_price == 0:
            return Decimal("0")

        # Simple model: assume 20% take profit or -10% stop loss
        peak_gain = (peak_price - entry_price) / entry_price
        max_loss = (min_price - entry_price) / entry_price

        if peak_gain >= Decimal("0.2"):
            return Decimal("0.2")  # Would have hit TP
        elif max_loss <= Decimal("-0.1"):
            return Decimal("-0.1")  # Would have hit SL
        else:
            return (peak_price - entry_price) / entry_price

    async def _load_signals(self, start: datetime, end: datetime) -> list:
        """Load signals for period."""
        result = await self.supabase.table("signals").select("*").gte(
            "created_at", start.isoformat()
        ).lte("created_at", end.isoformat()).execute()
        return result.data

    async def _load_trades_for_signals(self, signal_ids: list) -> list:
        """Load trades for given signals."""
        if not signal_ids:
            return []
        result = await self.supabase.table("trade_outcomes").select("*").in_(
            "signal_id", [str(s) for s in signal_ids]
        ).execute()
        return result.data

    async def _load_trades_with_factor_scores(self) -> list:
        """Load trades with factor scores."""
        result = await self.supabase.table("trade_outcomes").select(
            "*, signals(wallet_score, cluster_score, token_score, context_score)"
        ).limit(1000).execute()
        return result.data

    async def _get_price_data(self, token: str, signal_time: str, window_hours: int) -> Optional[dict]:
        """Get price data for retrospective analysis."""
        # Simplified - would call price API
        return None

    async def _save_snapshot(self, metrics: SignalAccuracyMetrics) -> None:
        """Save accuracy snapshot."""
        snapshot = AccuracySnapshot(
            id=uuid4(),
            snapshot_date=datetime.utcnow(),
            signal_to_win_rate=metrics.signal_to_win_rate,
            sample_size=metrics.traded_signals,
            avg_signal_score=(metrics.avg_score_winners + metrics.avg_score_losers) / 2,
            score_differential=metrics.score_differential,
        )
        await self.supabase.table("accuracy_snapshots").insert(
            snapshot.model_dump(mode="json")
        ).execute()


_tracker: Optional[AccuracyTracker] = None


async def get_accuracy_tracker(supabase_client) -> AccuracyTracker:
    global _tracker
    if _tracker is None:
        _tracker = AccuracyTracker(supabase_client)
    return _tracker
```

### Database Schema (SQL)

```sql
-- Accuracy snapshots table
CREATE TABLE accuracy_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_to_win_rate DECIMAL(10, 4) NOT NULL,
    sample_size INTEGER NOT NULL,
    avg_signal_score DECIMAL(5, 4) NOT NULL,
    score_differential DECIMAL(5, 4) NOT NULL
);

CREATE INDEX idx_accuracy_snapshots_date ON accuracy_snapshots(snapshot_date DESC);

-- Retrospective analysis results
CREATE TABLE retrospective_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    total_non_traded INTEGER NOT NULL,
    missed_opportunities INTEGER DEFAULT 0,
    bullets_dodged INTEGER DEFAULT 0,
    uncertain INTEGER DEFAULT 0,
    total_missed_pnl DECIMAL(30, 18) DEFAULT 0,
    total_avoided_loss DECIMAL(30, 18) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_retrospective_date ON retrospective_analyses(created_at DESC);
```

### FastAPI Routes

```python
# src/walltrack/api/routes/accuracy.py
from fastapi import APIRouter, Depends, Query
from typing import Optional
from datetime import datetime

from walltrack.core.feedback.accuracy_models import (
    SignalAccuracyMetrics,
    ThresholdAnalysis,
    RetrospectiveAnalysis,
    AccuracyTrendAnalysis,
    FactorAccuracyBreakdown,
)
from walltrack.core.feedback.accuracy_tracker import get_accuracy_tracker
from walltrack.core.database import get_supabase_client

router = APIRouter(prefix="/accuracy", tags=["accuracy"])


@router.get("/metrics", response_model=SignalAccuracyMetrics)
async def get_accuracy_metrics(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    supabase=Depends(get_supabase_client),
):
    """Get signal accuracy metrics."""
    tracker = await get_accuracy_tracker(supabase)
    return await tracker.calculate_accuracy_metrics(start_date, end_date)


@router.get("/thresholds", response_model=list[ThresholdAnalysis])
async def analyze_thresholds(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    supabase=Depends(get_supabase_client),
):
    """Analyze different threshold effectiveness."""
    tracker = await get_accuracy_tracker(supabase)
    return await tracker.analyze_thresholds(start_date, end_date)


@router.get("/retrospective", response_model=RetrospectiveAnalysis)
async def get_retrospective(
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    supabase=Depends(get_supabase_client),
):
    """Analyze non-traded signals."""
    tracker = await get_accuracy_tracker(supabase)
    return await tracker.run_retrospective_analysis(start_date, end_date)


@router.get("/trend", response_model=AccuracyTrendAnalysis)
async def get_trend(
    weeks: int = Query(default=8, ge=2, le=52),
    supabase=Depends(get_supabase_client),
):
    """Get accuracy trend over time."""
    tracker = await get_accuracy_tracker(supabase)
    return await tracker.analyze_trend(weeks)


@router.get("/breakdown", response_model=list[FactorAccuracyBreakdown])
async def get_factor_breakdown(
    supabase=Depends(get_supabase_client),
):
    """Get accuracy breakdown by factor."""
    tracker = await get_accuracy_tracker(supabase)
    return await tracker.breakdown_by_factor()
```

### Unit Tests

```python
# tests/core/feedback/test_accuracy_tracker.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.feedback.accuracy_models import (
    SignalAccuracyMetrics,
    RetrospectiveOutcome,
    AccuracyTrend,
)
from walltrack.core.feedback.accuracy_tracker import AccuracyTracker


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    client.table.return_value.select.return_value.gte.return_value.lte.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    client.table.return_value.insert.return_value.execute = AsyncMock()
    return client


@pytest.fixture
def tracker(mock_supabase):
    return AccuracyTracker(mock_supabase)


class TestAccuracyMetrics:
    def test_signal_to_win_rate_calculation(self):
        metrics = SignalAccuracyMetrics(
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            total_signals=100,
            traded_signals=50,
            winning_trades=35,
            losing_trades=15,
        )
        assert metrics.signal_to_win_rate == Decimal("70")
        assert metrics.signal_to_trade_rate == Decimal("50")

    def test_score_differential(self):
        metrics = SignalAccuracyMetrics(
            period_start=datetime.utcnow() - timedelta(days=30),
            period_end=datetime.utcnow(),
            avg_score_winners=Decimal("0.75"),
            avg_score_losers=Decimal("0.55"),
        )
        assert metrics.score_differential == Decimal("0.20")


class TestRetrospective:
    def test_pnl_estimation(self, tracker):
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0.001"),
            peak_price=Decimal("0.0012"),
            min_price=Decimal("0.00095"),
        )
        assert pnl == Decimal("0.2")  # Hit 20% TP

    def test_stop_loss_hit(self, tracker):
        pnl = tracker._estimate_trade_pnl(
            entry_price=Decimal("0.001"),
            peak_price=Decimal("0.00105"),
            min_price=Decimal("0.00085"),
        )
        assert pnl == Decimal("-0.1")  # Hit 10% SL
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/feedback/accuracy_tracker.py`
- [ ] Calculate signal-to-win rate
- [ ] Compare scores of winning vs losing signals
- [ ] Implement retrospective analysis for non-traded signals
- [ ] Calculate accuracy trend over time
- [ ] Break down accuracy by factor

## Definition of Done

- [ ] Signal accuracy calculated correctly
- [ ] Retrospective analysis identifies opportunities/bullets
- [ ] Accuracy trend visualizable
- [ ] Factor breakdown shows effectiveness
