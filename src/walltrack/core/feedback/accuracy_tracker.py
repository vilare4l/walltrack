"""Signal accuracy tracking service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from statistics import linear_regression
from uuid import uuid4

import structlog

from .accuracy_models import (
    AccuracySnapshot,
    AccuracyTrend,
    AccuracyTrendAnalysis,
    FactorAccuracyBreakdown,
    RetrospectiveAnalysis,
    RetrospectiveOutcome,
    RetrospectiveSignal,
    SignalAccuracyMetrics,
    ThresholdAnalysis,
)

logger = structlog.get_logger()


class AccuracyTracker:
    """Tracks signal accuracy and provides analysis."""

    # Default thresholds for analysis
    THRESHOLD_RANGE_START = 40
    THRESHOLD_RANGE_END = 90
    THRESHOLD_STEP = 5

    # Trade simulation parameters
    TAKE_PROFIT_PCT = Decimal("0.2")  # 20%
    STOP_LOSS_PCT = Decimal("-0.1")  # -10%

    # Factor threshold for high/low classification
    FACTOR_HIGH_THRESHOLD = Decimal("0.7")

    def __init__(self, supabase_client):
        """Initialize AccuracyTracker.

        Args:
            supabase_client: Supabase async client
        """
        self.supabase = supabase_client
        # Caches for testing
        self._signals_cache: list[dict] | None = None
        self._trades_cache: dict[str, dict | None] | None = None
        self._snapshots_cache: list[dict] | None = None

    async def calculate_accuracy_metrics(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> SignalAccuracyMetrics:
        """Calculate accuracy metrics for a period.

        Args:
            start_date: Period start (default: 30 days ago)
            end_date: Period end (default: now)

        Returns:
            SignalAccuracyMetrics
        """
        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        # Load signals and trades
        signals = await self._load_signals(start_date, end_date)
        trades = await self._load_trades_for_signals([s["id"] for s in signals])

        trade_map = {t["signal_id"]: t for t in trades}
        traded_signal_ids = set(trade_map.keys())

        winning_trades = [t for t in trades if t.get("is_win")]
        losing_trades = [t for t in trades if not t.get("is_win")]

        # Calculate average scores
        winner_signal_ids = {t["signal_id"] for t in winning_trades}
        loser_signal_ids = {t["signal_id"] for t in losing_trades}

        winner_scores = [
            Decimal(str(s.get("score", 0)))
            for s in signals
            if s["id"] in winner_signal_ids
        ]
        loser_scores = [
            Decimal(str(s.get("score", 0)))
            for s in signals
            if s["id"] in loser_signal_ids
        ]

        avg_winners = (
            sum(winner_scores) / len(winner_scores) if winner_scores else Decimal("0")
        )
        avg_losers = (
            sum(loser_scores) / len(loser_scores) if loser_scores else Decimal("0")
        )

        # Find optimal threshold
        optimal_threshold = self._find_optimal_threshold(signals, trades)

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
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[ThresholdAnalysis]:
        """Analyze different threshold effectiveness.

        Args:
            start_date: Period start (default: 30 days ago)
            end_date: Period end (default: now)

        Returns:
            List of ThresholdAnalysis for each threshold
        """
        if not end_date:
            end_date = datetime.now(UTC)
        if not start_date:
            start_date = end_date - timedelta(days=30)

        signals = await self._load_signals(start_date, end_date)
        trades = await self._load_trades_for_signals([s["id"] for s in signals])

        trade_map = {t["signal_id"]: t for t in trades}

        analyses = []
        for threshold_pct in range(
            self.THRESHOLD_RANGE_START,
            self.THRESHOLD_RANGE_END,
            self.THRESHOLD_STEP,
        ):
            threshold = Decimal(str(threshold_pct / 100))
            above_threshold = [
                s for s in signals if Decimal(str(s.get("score", 0))) >= threshold
            ]

            wins = 0
            losses = 0
            total_pnl = Decimal("0")
            gross_profit = Decimal("0")
            gross_loss = Decimal("0")

            for signal in above_threshold:
                trade = trade_map.get(signal["id"])
                if trade:
                    pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
                    if trade.get("is_win"):
                        wins += 1
                        gross_profit += pnl
                    else:
                        losses += 1
                        gross_loss += abs(pnl)
                    total_pnl += pnl

            total_trades = wins + losses
            win_rate = (
                Decimal(wins) / Decimal(total_trades) * 100
                if total_trades > 0
                else Decimal("0")
            )
            profit_factor = (
                gross_profit / gross_loss
                if gross_loss > 0
                else Decimal("999")
            )

            analyses.append(
                ThresholdAnalysis(
                    threshold=threshold,
                    would_trade_count=len(above_threshold),
                    would_win_count=wins,
                    would_lose_count=losses,
                    win_rate=win_rate,
                    total_pnl=total_pnl,
                    profit_factor=profit_factor,
                )
            )

        return analyses

    async def run_retrospective_analysis(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        price_window_hours: int = 24,
    ) -> RetrospectiveAnalysis:
        """Analyze signals that were not traded.

        Args:
            start_date: Period start
            end_date: Period end
            price_window_hours: Hours to look forward for price

        Returns:
            RetrospectiveAnalysis
        """
        if not end_date:
            end_date = datetime.now(UTC) - timedelta(hours=price_window_hours)
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
                signal.get("token_address", ""),
                signal.get("created_at", ""),
                price_window_hours,
            )

            if not price_data:
                outcome = RetrospectiveOutcome.UNCERTAIN
                uncertain_count += 1
                estimated_pnl = None
            else:
                price_at_signal = Decimal(str(price_data.get("price_at_signal", 0)))
                peak_price = Decimal(str(price_data.get("peak_price", 0)))
                min_price = Decimal(str(price_data.get("min_price", 0)))

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

            signal_timestamp = signal.get("created_at", "")
            if isinstance(signal_timestamp, str) and signal_timestamp:
                signal_timestamp = datetime.fromisoformat(
                    signal_timestamp.replace("Z", "+00:00")
                )
            else:
                signal_timestamp = datetime.now(UTC)

            retrospective_signals.append(
                RetrospectiveSignal(
                    signal_id=uuid4(),  # Use signal ID if available
                    signal_score=Decimal(str(signal.get("score", 0))),
                    token_address=signal.get("token_address", ""),
                    wallet_address=signal.get("wallet_address", ""),
                    signal_timestamp=signal_timestamp,
                    threshold_at_time=Decimal(str(signal.get("threshold", 0.6))),
                    outcome=outcome,
                    estimated_pnl=estimated_pnl,
                    price_at_signal=price_data.get("price_at_signal")
                    if price_data
                    else None,
                    peak_price_after=price_data.get("peak_price") if price_data else None,
                    min_price_after=price_data.get("min_price") if price_data else None,
                )
            )

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
        """Analyze accuracy trend over time.

        Args:
            weeks: Number of weeks to analyze

        Returns:
            AccuracyTrendAnalysis
        """
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(weeks=weeks)

        # Load historical snapshots
        snapshots_data = await self._load_snapshots(start_date)

        snapshots = [
            AccuracySnapshot(
                id=s.get("id", uuid4()),
                snapshot_date=datetime.fromisoformat(
                    s["snapshot_date"].replace("Z", "+00:00")
                )
                if isinstance(s.get("snapshot_date"), str)
                else s.get("snapshot_date", datetime.now(UTC)),
                signal_to_win_rate=Decimal(str(s.get("signal_to_win_rate", 0))),
                sample_size=s.get("sample_size", 0),
                avg_signal_score=Decimal(str(s.get("avg_signal_score", 0))),
                score_differential=Decimal(str(s.get("score_differential", 0))),
            )
            for s in snapshots_data
        ]

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

        slope, _ = linear_regression(x_values, y_values)

        # Classify trend - weekly change
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
            trend_slope=Decimal(str(round(weekly_change, 2))),
            start_win_rate=snapshots[0].signal_to_win_rate if snapshots else Decimal("0"),
            end_win_rate=snapshots[-1].signal_to_win_rate if snapshots else Decimal("0"),
            confidence=Decimal("0.8") if len(snapshots) >= 5 else Decimal("0.5"),
        )

    async def breakdown_by_factor(self) -> list[FactorAccuracyBreakdown]:
        """Break down accuracy by scoring factor.

        Returns:
            List of FactorAccuracyBreakdown
        """
        factors = ["wallet_score", "cluster_score", "token_score", "context_score"]
        breakdowns = []

        trades = await self._load_trades_with_factor_scores()

        for factor in factors:
            high_score_trades = [
                t
                for t in trades
                if Decimal(str(t.get(factor, 0))) >= self.FACTOR_HIGH_THRESHOLD
            ]
            low_score_trades = [
                t
                for t in trades
                if Decimal(str(t.get(factor, 0))) < self.FACTOR_HIGH_THRESHOLD
            ]

            high_win_rate = (
                sum(1 for t in high_score_trades if t.get("is_win"))
                / len(high_score_trades)
                * 100
                if high_score_trades
                else 0
            )
            low_win_rate = (
                sum(1 for t in low_score_trades if t.get("is_win"))
                / len(low_score_trades)
                * 100
                if low_score_trades
                else 0
            )

            is_predictive = high_win_rate > low_win_rate + 5

            if is_predictive and high_win_rate - low_win_rate > 10:
                recommendation = "increase"
            elif not is_predictive:
                recommendation = "decrease"
            else:
                recommendation = "none"

            breakdowns.append(
                FactorAccuracyBreakdown(
                    factor_name=factor,
                    high_score_win_rate=Decimal(str(round(high_win_rate, 2))),
                    low_score_win_rate=Decimal(str(round(low_win_rate, 2))),
                    is_predictive=is_predictive,
                    correlation_with_outcome=Decimal(
                        str(round((high_win_rate - low_win_rate) / 100, 4))
                    ),
                    recommended_weight_adjustment=recommendation,
                )
            )

        return breakdowns

    def _find_optimal_threshold(
        self, signals: list[dict], trades: list[dict]
    ) -> Decimal:
        """Find threshold that maximizes profit.

        Args:
            signals: List of signals
            trades: List of trades

        Returns:
            Optimal threshold decimal
        """
        if not signals or not trades:
            return Decimal("0.6")

        trade_map = {t["signal_id"]: t for t in trades}
        best_threshold = Decimal("0.6")
        best_pnl = Decimal("-999999")

        for threshold_pct in range(
            self.THRESHOLD_RANGE_START,
            self.THRESHOLD_RANGE_END,
            self.THRESHOLD_STEP,
        ):
            threshold = Decimal(str(threshold_pct / 100))
            pnl = Decimal("0")

            for signal in signals:
                if Decimal(str(signal.get("score", 0))) >= threshold:
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
        """Estimate trade PnL based on price movement.

        Args:
            entry_price: Entry price
            peak_price: Peak price in window
            min_price: Minimum price in window

        Returns:
            Estimated PnL as decimal
        """
        if not entry_price or entry_price == 0:
            return Decimal("0")

        # Calculate percentage changes
        peak_gain = (peak_price - entry_price) / entry_price
        max_loss = (min_price - entry_price) / entry_price

        if peak_gain >= self.TAKE_PROFIT_PCT:
            return self.TAKE_PROFIT_PCT
        elif max_loss <= self.STOP_LOSS_PCT:
            return self.STOP_LOSS_PCT
        else:
            return peak_gain

    async def _load_signals(
        self, start: datetime, end: datetime
    ) -> list[dict]:
        """Load signals for period.

        Args:
            start: Start datetime
            end: End datetime

        Returns:
            List of signal dicts
        """
        # Use cache if available (for testing)
        if self._signals_cache is not None:
            return self._signals_cache

        result = (
            await self.supabase.table("signals")
            .select("*")
            .gte("created_at", start.isoformat())
            .lte("created_at", end.isoformat())
            .execute()
        )
        return result.data if result.data else []

    async def _load_trades_for_signals(self, signal_ids: list[str]) -> list[dict]:
        """Load trades for given signals.

        Args:
            signal_ids: List of signal IDs

        Returns:
            List of trade dicts
        """
        # Use cache if available (for testing)
        if self._trades_cache is not None:
            return [
                t for t in self._trades_cache.values()
                if t is not None
            ]

        if not signal_ids:
            return []

        result = (
            await self.supabase.table("trade_outcomes")
            .select("*")
            .in_("signal_id", [str(s) for s in signal_ids])
            .execute()
        )
        return result.data if result.data else []

    async def _load_trades_with_factor_scores(self) -> list[dict]:
        """Load trades with factor scores.

        Returns:
            List of trade dicts with factor scores
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*, signals(wallet_score, cluster_score, token_score, context_score)")
            .limit(1000)
            .execute()
        )
        return result.data if result.data else []

    async def _load_snapshots(self, start_date: datetime) -> list[dict]:
        """Load accuracy snapshots since start date.

        Args:
            start_date: Start date

        Returns:
            List of snapshot dicts
        """
        # Use cache if available (for testing)
        if self._snapshots_cache is not None:
            return self._snapshots_cache

        result = (
            await self.supabase.table("accuracy_snapshots")
            .select("*")
            .gte("snapshot_date", start_date.isoformat())
            .order("snapshot_date")
            .execute()
        )
        return result.data if result.data else []

    async def _get_price_data(
        self, _token: str, _signal_time: str, _window_hours: int
    ) -> dict | None:
        """Get price data for retrospective analysis.

        Args:
            _token: Token address
            _signal_time: Signal timestamp
            _window_hours: Hours to look forward

        Returns:
            Price data dict or None
        """
        # Stub - production implementation calls price API (Birdeye/DexScreener)
        return None

    async def _save_snapshot(self, metrics: SignalAccuracyMetrics) -> None:
        """Save accuracy snapshot.

        Args:
            metrics: Accuracy metrics to save
        """
        snapshot_data = {
            "id": str(uuid4()),
            "snapshot_date": datetime.now(UTC).isoformat(),
            "signal_to_win_rate": str(metrics.signal_to_win_rate),
            "sample_size": metrics.traded_signals,
            "avg_signal_score": str(
                (metrics.avg_score_winners + metrics.avg_score_losers) / 2
            ),
            "score_differential": str(metrics.score_differential),
        }

        await self.supabase.table("accuracy_snapshots").insert(snapshot_data).execute()


# Singleton instance
_tracker: AccuracyTracker | None = None


def get_accuracy_tracker(supabase_client) -> AccuracyTracker:
    """Get or create AccuracyTracker singleton.

    Args:
        supabase_client: Supabase client

    Returns:
        AccuracyTracker instance
    """
    global _tracker
    if _tracker is None:
        _tracker = AccuracyTracker(supabase_client)
    return _tracker
