# Story 6.5: Pattern Analysis and Insights

## Story Info
- **Epic**: Epic 6 - Feedback Loop & Performance Analytics
- **Status**: ready
- **Priority**: Medium
- **FR**: FR38

## User Story

**As an** operator,
**I want** the system to identify patterns in successful vs unsuccessful trades,
**So that** I can understand what works.

## Acceptance Criteria

### AC 1: Pattern Detection
**Given** trade history
**When** pattern analysis runs
**Then** patterns are identified across dimensions:
- Time of day patterns (best/worst hours)
- Day of week patterns
- Wallet patterns (which wallets perform best)
- Token characteristics (what token attributes correlate with success)
- Cluster patterns (cluster trades vs solo trades)

### AC 2: Significance Calculation
**Given** pattern is identified
**When** significance is calculated
**Then** statistical confidence is provided
**And** sample size is shown
**And** actionable insight is suggested

### AC 3: Pattern Display
**Given** dashboard Pattern Analysis view
**When** operator views patterns
**Then** top patterns are displayed with:
- Pattern description
- Win rate for pattern
- Sample size
- Suggested action

### AC 4: Negative Pattern Warnings
**Given** negative patterns identified
**When** displayed to operator
**Then** warning is highlighted
**And** suggestion to adjust strategy is provided
**And** (optional) auto-adjustment suggestion

## Technical Notes

- FR38: Identify patterns in successful vs unsuccessful trades
- Implement in `src/walltrack/core/feedback/pattern_analyzer.py`
- Run as periodic batch job (daily or on-demand)

---

## Technical Specification

### Pydantic Models

```python
# src/walltrack/core/feedback/pattern_models.py
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, computed_field
from uuid import UUID


class PatternType(str, Enum):
    """Types of patterns analyzed."""
    TIME_OF_DAY = "time_of_day"
    DAY_OF_WEEK = "day_of_week"
    WALLET = "wallet"
    TOKEN_CHARACTERISTIC = "token_characteristic"
    CLUSTER_VS_SOLO = "cluster_vs_solo"
    ENTRY_SCORE_RANGE = "entry_score_range"
    POSITION_SIZE = "position_size"


class PatternSentiment(str, Enum):
    """Pattern sentiment classification."""
    POSITIVE = "positive"  # Correlated with success
    NEGATIVE = "negative"  # Correlated with failure
    NEUTRAL = "neutral"    # No significant correlation


class SignificanceLevel(str, Enum):
    """Statistical significance level."""
    HIGH = "high"      # p < 0.01
    MEDIUM = "medium"  # p < 0.05
    LOW = "low"        # p < 0.10
    NONE = "none"      # p >= 0.10


class Pattern(BaseModel):
    """Identified trading pattern."""
    id: UUID = Field(..., description="Pattern ID")
    pattern_type: PatternType = Field(..., description="Type of pattern")
    pattern_name: str = Field(..., description="Human-readable pattern name")
    description: str = Field(..., description="Pattern description")
    sentiment: PatternSentiment = Field(..., description="Positive or negative pattern")
    win_rate: Decimal = Field(..., ge=0, le=100, description="Win rate for this pattern %")
    baseline_win_rate: Decimal = Field(..., ge=0, le=100, description="Overall win rate for comparison")
    sample_size: int = Field(..., ge=0, description="Number of trades matching pattern")
    significance: SignificanceLevel = Field(..., description="Statistical significance")
    p_value: Optional[Decimal] = Field(default=None, description="P-value of correlation")
    suggested_action: str = Field(..., description="Actionable recommendation")
    discovered_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def win_rate_delta(self) -> Decimal:
        """Difference from baseline win rate."""
        return self.win_rate - self.baseline_win_rate

    @computed_field
    @property
    def is_actionable(self) -> bool:
        """Whether pattern has enough significance to act on."""
        return self.sample_size >= 20 and self.significance in [SignificanceLevel.HIGH, SignificanceLevel.MEDIUM]


class TimePattern(BaseModel):
    """Time-based pattern analysis."""
    hour: Optional[int] = Field(default=None, ge=0, le=23, description="Hour of day (UTC)")
    day_of_week: Optional[int] = Field(default=None, ge=0, le=6, description="Day of week (0=Monday)")
    trade_count: int = Field(default=0, description="Trades in this slot")
    win_count: int = Field(default=0, description="Wins in this slot")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate %")
    avg_pnl: Decimal = Field(default=Decimal("0"), description="Average PnL")
    total_pnl: Decimal = Field(default=Decimal("0"), description="Total PnL")


class WalletPattern(BaseModel):
    """Wallet-based performance pattern."""
    wallet_address: str = Field(..., description="Wallet address")
    wallet_score: Decimal = Field(..., description="Current wallet score")
    trade_count: int = Field(default=0, description="Total trades from wallet")
    win_count: int = Field(default=0, description="Wins from wallet")
    win_rate: Decimal = Field(default=Decimal("0"), description="Win rate %")
    avg_pnl: Decimal = Field(default=Decimal("0"), description="Average PnL")
    is_top_performer: bool = Field(default=False, description="Top 20% performer")
    is_underperformer: bool = Field(default=False, description="Bottom 20% performer")


class TokenPattern(BaseModel):
    """Token characteristic pattern."""
    characteristic: str = Field(..., description="Token characteristic name")
    characteristic_value: str = Field(..., description="Characteristic value/range")
    trade_count: int = Field(default=0)
    win_rate: Decimal = Field(default=Decimal("0"))
    avg_pnl: Decimal = Field(default=Decimal("0"))


class ClusterPattern(BaseModel):
    """Cluster vs solo trade pattern."""
    is_cluster_trade: bool = Field(..., description="Whether trade was cluster-based")
    trade_count: int = Field(default=0)
    win_count: int = Field(default=0)
    win_rate: Decimal = Field(default=Decimal("0"))
    avg_pnl: Decimal = Field(default=Decimal("0"))


class PatternAnalysisResult(BaseModel):
    """Complete pattern analysis results."""
    id: UUID = Field(..., description="Analysis ID")
    analyzed_at: datetime = Field(default_factory=datetime.utcnow)
    trade_count: int = Field(..., description="Total trades analyzed")
    baseline_win_rate: Decimal = Field(..., description="Overall win rate")
    patterns: list[Pattern] = Field(default_factory=list, description="Identified patterns")
    time_patterns: list[TimePattern] = Field(default_factory=list)
    wallet_patterns: list[WalletPattern] = Field(default_factory=list)
    token_patterns: list[TokenPattern] = Field(default_factory=list)
    cluster_pattern: Optional[ClusterPattern] = Field(default=None)
    top_positive_patterns: list[Pattern] = Field(default_factory=list)
    top_negative_patterns: list[Pattern] = Field(default_factory=list)


class PatternAlert(BaseModel):
    """Alert for significant pattern detection."""
    pattern_id: UUID = Field(..., description="Pattern ID")
    pattern_type: PatternType = Field(..., description="Pattern type")
    pattern_name: str = Field(..., description="Pattern name")
    sentiment: PatternSentiment = Field(..., description="Positive or negative")
    message: str = Field(..., description="Alert message")
    suggested_action: str = Field(..., description="Recommended action")
    created_at: datetime = Field(default_factory=datetime.utcnow)
```

### Service Implementation

```python
# src/walltrack/core/feedback/pattern_analyzer.py
import structlog
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional
from uuid import UUID, uuid4
from collections import defaultdict
from scipy import stats

from .pattern_models import (
    PatternType,
    PatternSentiment,
    SignificanceLevel,
    Pattern,
    TimePattern,
    WalletPattern,
    TokenPattern,
    ClusterPattern,
    PatternAnalysisResult,
    PatternAlert,
)

logger = structlog.get_logger()


class PatternAnalyzer:
    """Analyzes trading patterns to identify success/failure correlations."""

    def __init__(self, supabase_client):
        self.supabase = supabase_client

    async def run_full_analysis(
        self,
        days: int = 30,
        min_sample_size: int = 10,
    ) -> PatternAnalysisResult:
        """
        Run comprehensive pattern analysis.

        Args:
            days: Number of days to analyze
            min_sample_size: Minimum trades for pattern to be considered

        Returns:
            PatternAnalysisResult with all identified patterns
        """
        analysis_id = uuid4()
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)

        # Load trade data
        trades = await self._load_trades(start_date, end_date)

        if len(trades) < min_sample_size:
            logger.warning("insufficient_trades_for_analysis", count=len(trades))
            return PatternAnalysisResult(
                id=analysis_id,
                trade_count=len(trades),
                baseline_win_rate=Decimal("0"),
            )

        # Calculate baseline
        wins = sum(1 for t in trades if t.get("is_win"))
        baseline_win_rate = Decimal(wins) / Decimal(len(trades)) * 100

        # Run all pattern analyses
        time_patterns = self._analyze_time_patterns(trades, baseline_win_rate)
        wallet_patterns = await self._analyze_wallet_patterns(trades, baseline_win_rate)
        token_patterns = self._analyze_token_patterns(trades, baseline_win_rate)
        cluster_pattern = self._analyze_cluster_patterns(trades)

        # Convert to Pattern objects
        all_patterns = []
        all_patterns.extend(self._time_to_patterns(time_patterns, baseline_win_rate))
        all_patterns.extend(self._wallet_to_patterns(wallet_patterns, baseline_win_rate))
        all_patterns.extend(self._token_to_patterns(token_patterns, baseline_win_rate))
        if cluster_pattern:
            all_patterns.extend(self._cluster_to_patterns(cluster_pattern, baseline_win_rate))

        # Filter by sample size and sort
        significant_patterns = [p for p in all_patterns if p.sample_size >= min_sample_size]
        significant_patterns.sort(key=lambda p: abs(p.win_rate_delta), reverse=True)

        # Separate positive and negative
        positive = [p for p in significant_patterns if p.sentiment == PatternSentiment.POSITIVE][:5]
        negative = [p for p in significant_patterns if p.sentiment == PatternSentiment.NEGATIVE][:5]

        result = PatternAnalysisResult(
            id=analysis_id,
            trade_count=len(trades),
            baseline_win_rate=baseline_win_rate,
            patterns=significant_patterns[:20],
            time_patterns=time_patterns,
            wallet_patterns=wallet_patterns[:20],
            token_patterns=token_patterns,
            cluster_pattern=cluster_pattern,
            top_positive_patterns=positive,
            top_negative_patterns=negative,
        )

        # Persist result
        await self._save_analysis(result)

        # Generate alerts for significant patterns
        await self._generate_alerts(significant_patterns)

        logger.info(
            "pattern_analysis_complete",
            analysis_id=str(analysis_id),
            trade_count=len(trades),
            patterns_found=len(significant_patterns),
            positive=len(positive),
            negative=len(negative),
        )

        return result

    def _analyze_time_patterns(
        self,
        trades: list[dict],
        baseline: Decimal,
    ) -> list[TimePattern]:
        """Analyze time-of-day and day-of-week patterns."""
        hour_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": Decimal("0")})
        day_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": Decimal("0")})

        for trade in trades:
            timestamp = datetime.fromisoformat(trade["entry_timestamp"])
            hour = timestamp.hour
            day = timestamp.weekday()
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))

            hour_stats[hour]["count"] += 1
            hour_stats[hour]["pnl"] += pnl
            if trade.get("is_win"):
                hour_stats[hour]["wins"] += 1

            day_stats[day]["count"] += 1
            day_stats[day]["pnl"] += pnl
            if trade.get("is_win"):
                day_stats[day]["wins"] += 1

        patterns = []

        for hour, stats in hour_stats.items():
            if stats["count"] > 0:
                patterns.append(TimePattern(
                    hour=hour,
                    trade_count=stats["count"],
                    win_count=stats["wins"],
                    win_rate=Decimal(stats["wins"]) / Decimal(stats["count"]) * 100,
                    avg_pnl=stats["pnl"] / stats["count"],
                    total_pnl=stats["pnl"],
                ))

        for day, stats in day_stats.items():
            if stats["count"] > 0:
                patterns.append(TimePattern(
                    day_of_week=day,
                    trade_count=stats["count"],
                    win_count=stats["wins"],
                    win_rate=Decimal(stats["wins"]) / Decimal(stats["count"]) * 100,
                    avg_pnl=stats["pnl"] / stats["count"],
                    total_pnl=stats["pnl"],
                ))

        return patterns

    async def _analyze_wallet_patterns(
        self,
        trades: list[dict],
        baseline: Decimal,
    ) -> list[WalletPattern]:
        """Analyze wallet performance patterns."""
        wallet_stats = defaultdict(lambda: {"count": 0, "wins": 0, "pnl": Decimal("0"), "score": Decimal("0")})

        for trade in trades:
            wallet = trade.get("wallet_address")
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            score = Decimal(str(trade.get("signal_score", 0.5)))

            wallet_stats[wallet]["count"] += 1
            wallet_stats[wallet]["pnl"] += pnl
            wallet_stats[wallet]["score"] = score
            if trade.get("is_win"):
                wallet_stats[wallet]["wins"] += 1

        patterns = []
        all_win_rates = []

        for wallet, stats in wallet_stats.items():
            if stats["count"] >= 3:
                win_rate = Decimal(stats["wins"]) / Decimal(stats["count"]) * 100
                all_win_rates.append(float(win_rate))
                patterns.append(WalletPattern(
                    wallet_address=wallet,
                    wallet_score=stats["score"],
                    trade_count=stats["count"],
                    win_count=stats["wins"],
                    win_rate=win_rate,
                    avg_pnl=stats["pnl"] / stats["count"],
                ))

        # Mark top/bottom performers
        if all_win_rates:
            top_threshold = sorted(all_win_rates, reverse=True)[int(len(all_win_rates) * 0.2)] if len(all_win_rates) > 5 else 100
            bottom_threshold = sorted(all_win_rates)[int(len(all_win_rates) * 0.2)] if len(all_win_rates) > 5 else 0

            for p in patterns:
                p.is_top_performer = float(p.win_rate) >= top_threshold
                p.is_underperformer = float(p.win_rate) <= bottom_threshold

        patterns.sort(key=lambda p: p.win_rate, reverse=True)
        return patterns

    def _analyze_token_patterns(
        self,
        trades: list[dict],
        baseline: Decimal,
    ) -> list[TokenPattern]:
        """Analyze token characteristic patterns."""
        patterns = []

        # Market cap patterns (if available)
        mcap_ranges = [
            ("micro_cap", 0, 100000),
            ("small_cap", 100000, 1000000),
            ("mid_cap", 1000000, 10000000),
            ("large_cap", 10000000, float("inf")),
        ]

        for name, min_mcap, max_mcap in mcap_ranges:
            matching = [t for t in trades if min_mcap <= float(t.get("market_cap", 0)) < max_mcap]
            if matching:
                wins = sum(1 for t in matching if t.get("is_win"))
                patterns.append(TokenPattern(
                    characteristic="market_cap",
                    characteristic_value=name,
                    trade_count=len(matching),
                    win_rate=Decimal(wins) / Decimal(len(matching)) * 100 if matching else Decimal("0"),
                    avg_pnl=sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in matching) / len(matching) if matching else Decimal("0"),
                ))

        # Token age patterns
        age_ranges = [
            ("new_token", 0, 1),      # < 1 day
            ("young_token", 1, 7),    # 1-7 days
            ("mature_token", 7, 30),  # 1-4 weeks
            ("old_token", 30, 365),   # 1+ month
        ]

        for name, min_days, max_days in age_ranges:
            matching = [t for t in trades if min_days <= float(t.get("token_age_days", 0)) < max_days]
            if matching:
                wins = sum(1 for t in matching if t.get("is_win"))
                patterns.append(TokenPattern(
                    characteristic="token_age",
                    characteristic_value=name,
                    trade_count=len(matching),
                    win_rate=Decimal(wins) / Decimal(len(matching)) * 100 if matching else Decimal("0"),
                    avg_pnl=sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in matching) / len(matching) if matching else Decimal("0"),
                ))

        return patterns

    def _analyze_cluster_patterns(self, trades: list[dict]) -> Optional[ClusterPattern]:
        """Analyze cluster vs solo trade patterns."""
        cluster_trades = [t for t in trades if t.get("is_cluster_trade")]
        solo_trades = [t for t in trades if not t.get("is_cluster_trade")]

        patterns = []

        if cluster_trades:
            wins = sum(1 for t in cluster_trades if t.get("is_win"))
            patterns.append(ClusterPattern(
                is_cluster_trade=True,
                trade_count=len(cluster_trades),
                win_count=wins,
                win_rate=Decimal(wins) / Decimal(len(cluster_trades)) * 100,
                avg_pnl=sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in cluster_trades) / len(cluster_trades),
            ))

        if solo_trades:
            wins = sum(1 for t in solo_trades if t.get("is_win"))
            patterns.append(ClusterPattern(
                is_cluster_trade=False,
                trade_count=len(solo_trades),
                win_count=wins,
                win_rate=Decimal(wins) / Decimal(len(solo_trades)) * 100,
                avg_pnl=sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in solo_trades) / len(solo_trades),
            ))

        return patterns[0] if patterns else None

    def _time_to_patterns(self, time_patterns: list[TimePattern], baseline: Decimal) -> list[Pattern]:
        """Convert time patterns to Pattern objects."""
        patterns = []
        for tp in time_patterns:
            if tp.hour is not None:
                name = f"Hour {tp.hour}:00 UTC"
                pattern_type = PatternType.TIME_OF_DAY
            elif tp.day_of_week is not None:
                days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                name = days[tp.day_of_week]
                pattern_type = PatternType.DAY_OF_WEEK
            else:
                continue

            delta = tp.win_rate - baseline
            sentiment = PatternSentiment.POSITIVE if delta > 5 else PatternSentiment.NEGATIVE if delta < -5 else PatternSentiment.NEUTRAL
            significance = self._calculate_significance(tp.trade_count, float(tp.win_rate), float(baseline))

            action = self._generate_action(pattern_type, name, sentiment, delta)

            patterns.append(Pattern(
                id=uuid4(),
                pattern_type=pattern_type,
                pattern_name=name,
                description=f"Win rate {tp.win_rate:.1f}% ({delta:+.1f}% vs baseline)",
                sentiment=sentiment,
                win_rate=tp.win_rate,
                baseline_win_rate=baseline,
                sample_size=tp.trade_count,
                significance=significance,
                suggested_action=action,
            ))

        return patterns

    def _wallet_to_patterns(self, wallet_patterns: list[WalletPattern], baseline: Decimal) -> list[Pattern]:
        """Convert wallet patterns to Pattern objects."""
        patterns = []
        for wp in wallet_patterns:
            if wp.trade_count < 5:
                continue

            delta = wp.win_rate - baseline
            sentiment = PatternSentiment.POSITIVE if delta > 10 else PatternSentiment.NEGATIVE if delta < -10 else PatternSentiment.NEUTRAL

            if sentiment == PatternSentiment.NEUTRAL:
                continue

            significance = self._calculate_significance(wp.trade_count, float(wp.win_rate), float(baseline))
            action = "Prioritize signals from this wallet" if sentiment == PatternSentiment.POSITIVE else "Review wallet score, consider reducing weight"

            patterns.append(Pattern(
                id=uuid4(),
                pattern_type=PatternType.WALLET,
                pattern_name=f"Wallet {wp.wallet_address[:8]}...",
                description=f"Win rate {wp.win_rate:.1f}% over {wp.trade_count} trades",
                sentiment=sentiment,
                win_rate=wp.win_rate,
                baseline_win_rate=baseline,
                sample_size=wp.trade_count,
                significance=significance,
                suggested_action=action,
            ))

        return patterns

    def _token_to_patterns(self, token_patterns: list[TokenPattern], baseline: Decimal) -> list[Pattern]:
        """Convert token patterns to Pattern objects."""
        patterns = []
        for tp in token_patterns:
            if tp.trade_count < 10:
                continue

            delta = tp.win_rate - baseline
            sentiment = PatternSentiment.POSITIVE if delta > 5 else PatternSentiment.NEGATIVE if delta < -5 else PatternSentiment.NEUTRAL

            significance = self._calculate_significance(tp.trade_count, float(tp.win_rate), float(baseline))
            action = f"Favor {tp.characteristic_value} tokens" if sentiment == PatternSentiment.POSITIVE else f"Avoid {tp.characteristic_value} tokens"

            patterns.append(Pattern(
                id=uuid4(),
                pattern_type=PatternType.TOKEN_CHARACTERISTIC,
                pattern_name=f"{tp.characteristic}: {tp.characteristic_value}",
                description=f"Win rate {tp.win_rate:.1f}% for {tp.characteristic_value}",
                sentiment=sentiment,
                win_rate=tp.win_rate,
                baseline_win_rate=baseline,
                sample_size=tp.trade_count,
                significance=significance,
                suggested_action=action,
            ))

        return patterns

    def _cluster_to_patterns(self, cluster_pattern: ClusterPattern, baseline: Decimal) -> list[Pattern]:
        """Convert cluster pattern to Pattern objects."""
        delta = cluster_pattern.win_rate - baseline
        sentiment = PatternSentiment.POSITIVE if delta > 5 else PatternSentiment.NEGATIVE if delta < -5 else PatternSentiment.NEUTRAL
        significance = self._calculate_significance(cluster_pattern.trade_count, float(cluster_pattern.win_rate), float(baseline))

        trade_type = "Cluster" if cluster_pattern.is_cluster_trade else "Solo"
        action = f"{'Prioritize' if sentiment == PatternSentiment.POSITIVE else 'Reduce weight for'} {trade_type.lower()} trades"

        return [Pattern(
            id=uuid4(),
            pattern_type=PatternType.CLUSTER_VS_SOLO,
            pattern_name=f"{trade_type} Trades",
            description=f"{trade_type} trades win rate: {cluster_pattern.win_rate:.1f}%",
            sentiment=sentiment,
            win_rate=cluster_pattern.win_rate,
            baseline_win_rate=baseline,
            sample_size=cluster_pattern.trade_count,
            significance=significance,
            suggested_action=action,
        )]

    def _calculate_significance(self, sample_size: int, win_rate: float, baseline: float) -> SignificanceLevel:
        """Calculate statistical significance using chi-square test."""
        if sample_size < 10:
            return SignificanceLevel.NONE

        # Expected vs observed
        expected_wins = sample_size * (baseline / 100)
        observed_wins = sample_size * (win_rate / 100)

        try:
            chi2, p_value = stats.chisquare([observed_wins, sample_size - observed_wins], [expected_wins, sample_size - expected_wins])
            if p_value < 0.01:
                return SignificanceLevel.HIGH
            elif p_value < 0.05:
                return SignificanceLevel.MEDIUM
            elif p_value < 0.10:
                return SignificanceLevel.LOW
        except Exception:
            pass

        return SignificanceLevel.NONE

    def _generate_action(self, pattern_type: PatternType, name: str, sentiment: PatternSentiment, delta: Decimal) -> str:
        """Generate actionable recommendation."""
        if sentiment == PatternSentiment.POSITIVE:
            if pattern_type == PatternType.TIME_OF_DAY:
                return f"Consider increasing position sizes during {name}"
            elif pattern_type == PatternType.DAY_OF_WEEK:
                return f"Favorable day: {name} shows +{delta:.1f}% win rate"
            return f"Pattern shows {delta:+.1f}% advantage"
        elif sentiment == PatternSentiment.NEGATIVE:
            if pattern_type == PatternType.TIME_OF_DAY:
                return f"Consider reducing activity during {name}"
            elif pattern_type == PatternType.DAY_OF_WEEK:
                return f"Caution on {name}: {delta:.1f}% below baseline"
            return f"Pattern shows {delta:.1f}% disadvantage"
        return "No significant deviation from baseline"

    async def _load_trades(self, start: datetime, end: datetime) -> list[dict]:
        """Load trade data for analysis."""
        result = await self.supabase.table("trade_outcomes").select(
            "*, signals(wallet_score, cluster_score, token_score, is_cluster_trade)"
        ).gte("entry_timestamp", start.isoformat()).lte("entry_timestamp", end.isoformat()).execute()
        return result.data

    async def _save_analysis(self, result: PatternAnalysisResult) -> None:
        """Persist analysis results."""
        await self.supabase.table("pattern_analyses").insert({
            "id": str(result.id),
            "analyzed_at": result.analyzed_at.isoformat(),
            "trade_count": result.trade_count,
            "baseline_win_rate": str(result.baseline_win_rate),
            "patterns": [p.model_dump(mode="json") for p in result.patterns],
        }).execute()

    async def _generate_alerts(self, patterns: list[Pattern]) -> None:
        """Generate alerts for significant patterns."""
        for pattern in patterns[:5]:
            if pattern.is_actionable and pattern.sentiment in [PatternSentiment.POSITIVE, PatternSentiment.NEGATIVE]:
                alert = PatternAlert(
                    pattern_id=pattern.id,
                    pattern_type=pattern.pattern_type,
                    pattern_name=pattern.pattern_name,
                    sentiment=pattern.sentiment,
                    message=pattern.description,
                    suggested_action=pattern.suggested_action,
                )
                await self.supabase.table("pattern_alerts").insert(
                    alert.model_dump(mode="json")
                ).execute()


_analyzer: Optional[PatternAnalyzer] = None


async def get_pattern_analyzer(supabase_client) -> PatternAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = PatternAnalyzer(supabase_client)
    return _analyzer
```

### Database Schema (SQL)

```sql
-- Pattern analyses table
CREATE TABLE pattern_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_count INTEGER NOT NULL,
    baseline_win_rate DECIMAL(10, 4) NOT NULL,
    patterns JSONB NOT NULL
);

CREATE INDEX idx_pattern_analyses_date ON pattern_analyses(analyzed_at DESC);

-- Pattern alerts table
CREATE TABLE pattern_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL,
    pattern_type TEXT NOT NULL,
    pattern_name TEXT NOT NULL,
    sentiment TEXT NOT NULL,
    message TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_pattern_alerts_created ON pattern_alerts(created_at DESC);
CREATE INDEX idx_pattern_alerts_unacked ON pattern_alerts(acknowledged) WHERE acknowledged = FALSE;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/patterns.py
from fastapi import APIRouter, Depends, Query
from uuid import UUID

from walltrack.core.feedback.pattern_models import PatternAnalysisResult, PatternAlert
from walltrack.core.feedback.pattern_analyzer import get_pattern_analyzer
from walltrack.core.database import get_supabase_client

router = APIRouter(prefix="/patterns", tags=["patterns"])


@router.post("/analyze", response_model=PatternAnalysisResult)
async def run_analysis(
    days: int = Query(default=30, ge=7, le=90),
    min_sample: int = Query(default=10, ge=5),
    supabase=Depends(get_supabase_client),
):
    """Run pattern analysis on trade history."""
    analyzer = await get_pattern_analyzer(supabase)
    return await analyzer.run_full_analysis(days=days, min_sample_size=min_sample)


@router.get("/alerts", response_model=list[PatternAlert])
async def get_alerts(
    unacknowledged_only: bool = Query(default=True),
    supabase=Depends(get_supabase_client),
):
    """Get pattern alerts."""
    query = supabase.table("pattern_alerts").select("*").order("created_at", desc=True)
    if unacknowledged_only:
        query = query.eq("acknowledged", False)
    result = await query.limit(50).execute()
    return [PatternAlert(**a) for a in result.data]


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: UUID,
    supabase=Depends(get_supabase_client),
):
    """Acknowledge a pattern alert."""
    await supabase.table("pattern_alerts").update({"acknowledged": True}).eq("id", str(alert_id)).execute()
    return {"status": "acknowledged"}
```

### Unit Tests

```python
# tests/core/feedback/test_pattern_analyzer.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.feedback.pattern_models import PatternSentiment, SignificanceLevel
from walltrack.core.feedback.pattern_analyzer import PatternAnalyzer


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    client.table.return_value.select.return_value.gte.return_value.lte.return_value.execute = AsyncMock(
        return_value=MagicMock(data=[])
    )
    client.table.return_value.insert.return_value.execute = AsyncMock()
    return client


@pytest.fixture
def analyzer(mock_supabase):
    return PatternAnalyzer(mock_supabase)


@pytest.fixture
def sample_trades():
    """Generate sample trade data."""
    trades = []
    for i in range(100):
        trades.append({
            "id": f"trade_{i}",
            "wallet_address": f"wallet_{i % 10}",
            "entry_timestamp": (datetime.utcnow() - timedelta(hours=i)).isoformat(),
            "is_win": i % 3 != 0,  # ~67% win rate
            "realized_pnl_sol": "10" if i % 3 != 0 else "-5",
            "is_cluster_trade": i % 2 == 0,
        })
    return trades


class TestTimePatterns:
    def test_hourly_pattern_detection(self, analyzer, sample_trades):
        patterns = analyzer._analyze_time_patterns(sample_trades, Decimal("67"))
        hour_patterns = [p for p in patterns if p.hour is not None]
        assert len(hour_patterns) > 0

    def test_day_of_week_patterns(self, analyzer, sample_trades):
        patterns = analyzer._analyze_time_patterns(sample_trades, Decimal("67"))
        day_patterns = [p for p in patterns if p.day_of_week is not None]
        assert len(day_patterns) > 0


class TestSignificanceCalculation:
    def test_high_significance(self, analyzer):
        sig = analyzer._calculate_significance(100, 80, 50)
        assert sig in [SignificanceLevel.HIGH, SignificanceLevel.MEDIUM]

    def test_low_significance(self, analyzer):
        sig = analyzer._calculate_significance(10, 52, 50)
        assert sig in [SignificanceLevel.LOW, SignificanceLevel.NONE]
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/feedback/pattern_analyzer.py`
- [ ] Analyze time of day patterns
- [ ] Analyze wallet performance patterns
- [ ] Analyze token characteristic patterns
- [ ] Analyze cluster vs solo trade patterns
- [ ] Calculate statistical significance
- [ ] Generate actionable insights
- [ ] Schedule periodic analysis

## Definition of Done

- [x] Patterns identified across multiple dimensions
- [x] Statistical significance calculated
- [x] Patterns displayed with insights
- [x] Negative patterns highlighted with warnings

---

## Implementation Summary

### Files Created/Modified

1. **`src/walltrack/core/feedback/pattern_models.py`** - Pydantic models
   - `PatternType`, `PatternSentiment`, `SignificanceLevel` enums
   - `Pattern` model with `@computed_field` for `win_rate_delta` and `is_actionable`
   - `TimePattern`, `WalletPattern`, `TokenPattern`, `ClusterPattern` models
   - `PatternAnalysisResult` model with all pattern lists
   - `PatternAlert` model for notifications

2. **`src/walltrack/core/feedback/pattern_analyzer.py`** - Core service
   - `PatternAnalyzer` class with comprehensive analysis methods
   - `run_full_analysis()` - Main entry point for pattern analysis
   - `_analyze_time_patterns()` - Hour and day of week analysis
   - `_analyze_wallet_patterns()` - Wallet performance analysis with top/bottom marking
   - `_analyze_token_patterns()` - Market cap and token age analysis
   - `_analyze_cluster_patterns()` - Cluster vs solo trade comparison
   - `_calculate_significance()` - Chi-square statistical significance
   - `get_alerts()`, `acknowledge_alert()` - Alert management
   - Singleton pattern with `get_pattern_analyzer()`

3. **`src/walltrack/api/routes/patterns.py`** - FastAPI routes
   - `POST /patterns/analyze` - Run full pattern analysis
   - `GET /patterns/alerts` - Get pattern alerts
   - `POST /patterns/alerts/{alert_id}/acknowledge` - Acknowledge alert
   - `GET /patterns/top-patterns` - Get top positive/negative patterns

4. **`src/walltrack/data/supabase/migrations/015_pattern_analysis.sql`** - Database
   - `pattern_analyses` table for storing analysis results
   - `pattern_alerts` table for notifications
   - Indexes for efficient querying
   - RLS policies and cleanup functions
   - Trigger for setting `acknowledged_at`

5. **`src/walltrack/core/feedback/__init__.py`** - Updated exports
   - Added all pattern models and `PatternAnalyzer`
   - Added `get_pattern_analyzer` singleton accessor

6. **`tests/core/feedback/test_pattern_analyzer.py`** - 27 comprehensive tests
   - Pattern model tests (win_rate_delta, is_actionable)
   - Time pattern analysis tests
   - Wallet pattern analysis tests
   - Token pattern analysis tests
   - Cluster pattern analysis tests
   - Significance calculation tests
   - Pattern conversion tests
   - Action generation tests
   - Full analysis workflow tests
   - Pattern alert tests

### Key Implementation Details

- **Statistical Significance**: Uses scipy.stats chi-square test with p-value thresholds
  - HIGH: p < 0.01
  - MEDIUM: p < 0.05
  - LOW: p < 0.10
  - NONE: p >= 0.10

- **Pattern Dimensions**:
  - Time of day (24 hours UTC)
  - Day of week (Monday-Sunday)
  - Wallet performance (top/bottom 20% performers)
  - Token characteristics (market cap ranges, token age ranges)
  - Cluster vs solo trades

- **Actionable Patterns**: Requires sample_size >= 20 AND significance HIGH or MEDIUM

### Test Results

All 27 tests passing:
- 6 pattern model tests
- 3 time pattern analysis tests
- 2 wallet pattern analysis tests
- 2 token pattern analysis tests
- 2 cluster pattern analysis tests
- 3 significance calculation tests
- 3 pattern conversion tests
- 2 action generation tests
- 3 full analysis tests
- 1 pattern alert test
