"""Pattern analysis service for identifying trading patterns."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import structlog
from scipy import stats

from .pattern_models import (
    ClusterPattern,
    Pattern,
    PatternAlert,
    PatternAnalysisResult,
    PatternSentiment,
    PatternType,
    SignificanceLevel,
    TimePattern,
    TokenPattern,
    WalletPattern,
)

logger = structlog.get_logger()


class PatternAnalyzer:
    """Analyzes trading patterns to identify success/failure correlations."""

    # Configuration
    MIN_SAMPLE_SIZE = 10
    HIGH_P_VALUE = 0.01
    MEDIUM_P_VALUE = 0.05
    LOW_P_VALUE = 0.10
    POSITIVE_DELTA_THRESHOLD = Decimal("5")
    NEGATIVE_DELTA_THRESHOLD = Decimal("-5")

    def __init__(self, supabase_client):
        """Initialize analyzer.

        Args:
            supabase_client: Supabase client instance
        """
        self.supabase = supabase_client
        self._trades_cache: list[dict] | None = None

    async def run_full_analysis(
        self,
        days: int = 30,
        min_sample_size: int = 10,
    ) -> PatternAnalysisResult:
        """Run comprehensive pattern analysis.

        Args:
            days: Number of days to analyze
            min_sample_size: Minimum trades for pattern to be considered

        Returns:
            PatternAnalysisResult with all identified patterns
        """
        analysis_id = uuid4()
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=days)

        # Load trade data (use cache if available for testing)
        if self._trades_cache is not None:
            trades = self._trades_cache
        else:
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
        cluster_patterns = self._analyze_cluster_patterns(trades)

        # Convert to Pattern objects
        all_patterns: list[Pattern] = []
        all_patterns.extend(self._time_to_patterns(time_patterns, baseline_win_rate))
        all_patterns.extend(self._wallet_to_patterns(wallet_patterns, baseline_win_rate))
        all_patterns.extend(self._token_to_patterns(token_patterns, baseline_win_rate))
        all_patterns.extend(self._cluster_to_patterns(cluster_patterns, baseline_win_rate))

        # Filter by sample size and sort
        significant_patterns = [p for p in all_patterns if p.sample_size >= min_sample_size]
        significant_patterns.sort(key=lambda p: abs(p.win_rate_delta), reverse=True)

        # Separate positive and negative
        positive = [p for p in significant_patterns if p.sentiment == PatternSentiment.POSITIVE][
            :5
        ]
        negative = [p for p in significant_patterns if p.sentiment == PatternSentiment.NEGATIVE][
            :5
        ]

        result = PatternAnalysisResult(
            id=analysis_id,
            trade_count=len(trades),
            baseline_win_rate=baseline_win_rate,
            patterns=significant_patterns[:20],
            time_patterns=time_patterns,
            wallet_patterns=wallet_patterns[:20],
            token_patterns=token_patterns,
            cluster_patterns=cluster_patterns,
            top_positive_patterns=positive,
            top_negative_patterns=negative,
        )

        # Persist result (skip if cache is set - testing mode)
        if self._trades_cache is None:
            await self._save_analysis(result)
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
        _baseline: Decimal,
    ) -> list[TimePattern]:
        """Analyze time-of-day and day-of-week patterns.

        Args:
            trades: List of trade dicts
            _baseline: Baseline win rate (unused, for interface consistency)

        Returns:
            List of TimePattern objects
        """
        hour_stats: dict[int, dict] = defaultdict(
            lambda: {"count": 0, "wins": 0, "pnl": Decimal("0")}
        )
        day_stats: dict[int, dict] = defaultdict(
            lambda: {"count": 0, "wins": 0, "pnl": Decimal("0")}
        )

        for trade in trades:
            timestamp_str = trade.get("entry_timestamp", "")
            if not timestamp_str:
                continue

            try:
                if isinstance(timestamp_str, str):
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                else:
                    timestamp = timestamp_str
            except (ValueError, TypeError):
                continue

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

        for hour, stat in hour_stats.items():
            if stat["count"] > 0:
                patterns.append(
                    TimePattern(
                        hour=hour,
                        trade_count=stat["count"],
                        win_count=stat["wins"],
                        win_rate=Decimal(stat["wins"]) / Decimal(stat["count"]) * 100,
                        avg_pnl=stat["pnl"] / stat["count"],
                        total_pnl=stat["pnl"],
                    )
                )

        for day, stat in day_stats.items():
            if stat["count"] > 0:
                patterns.append(
                    TimePattern(
                        day_of_week=day,
                        trade_count=stat["count"],
                        win_count=stat["wins"],
                        win_rate=Decimal(stat["wins"]) / Decimal(stat["count"]) * 100,
                        avg_pnl=stat["pnl"] / stat["count"],
                        total_pnl=stat["pnl"],
                    )
                )

        return patterns

    async def _analyze_wallet_patterns(
        self,
        trades: list[dict],
        _baseline: Decimal,
    ) -> list[WalletPattern]:
        """Analyze wallet performance patterns.

        Args:
            trades: List of trade dicts
            _baseline: Baseline win rate (unused, for interface consistency)

        Returns:
            List of WalletPattern objects
        """
        wallet_stats: dict[str, dict] = defaultdict(
            lambda: {"count": 0, "wins": 0, "pnl": Decimal("0"), "score": Decimal("0.5")}
        )

        for trade in trades:
            wallet = trade.get("wallet_address", "unknown")
            pnl = Decimal(str(trade.get("realized_pnl_sol", 0)))
            score = Decimal(str(trade.get("signal_score", 0.5)))

            wallet_stats[wallet]["count"] += 1
            wallet_stats[wallet]["pnl"] += pnl
            wallet_stats[wallet]["score"] = score
            if trade.get("is_win"):
                wallet_stats[wallet]["wins"] += 1

        patterns = []
        all_win_rates: list[float] = []

        for wallet, stat in wallet_stats.items():
            if stat["count"] >= 3:
                win_rate = Decimal(stat["wins"]) / Decimal(stat["count"]) * 100
                all_win_rates.append(float(win_rate))
                patterns.append(
                    WalletPattern(
                        wallet_address=wallet,
                        wallet_score=stat["score"],
                        trade_count=stat["count"],
                        win_count=stat["wins"],
                        win_rate=win_rate,
                        avg_pnl=stat["pnl"] / stat["count"],
                    )
                )

        # Mark top/bottom performers
        if len(all_win_rates) > 5:
            sorted_rates = sorted(all_win_rates, reverse=True)
            top_idx = int(len(sorted_rates) * 0.2)
            bottom_idx = int(len(sorted_rates) * 0.8)
            top_threshold = sorted_rates[top_idx] if top_idx < len(sorted_rates) else 100.0
            bottom_threshold = sorted_rates[bottom_idx] if bottom_idx < len(sorted_rates) else 0.0

            for p in patterns:
                p.is_top_performer = float(p.win_rate) >= top_threshold
                p.is_underperformer = float(p.win_rate) <= bottom_threshold

        patterns.sort(key=lambda p: p.win_rate, reverse=True)
        return patterns

    def _analyze_token_patterns(
        self,
        trades: list[dict],
        _baseline: Decimal,
    ) -> list[TokenPattern]:
        """Analyze token characteristic patterns.

        Args:
            trades: List of trade dicts
            _baseline: Baseline win rate (unused, for interface consistency)

        Returns:
            List of TokenPattern objects
        """
        patterns = []

        # Market cap patterns
        mcap_ranges = [
            ("micro_cap", 0, 100000),
            ("small_cap", 100000, 1000000),
            ("mid_cap", 1000000, 10000000),
            ("large_cap", 10000000, float("inf")),
        ]

        for name, min_mcap, max_mcap in mcap_ranges:
            matching = [
                t for t in trades if min_mcap <= float(t.get("market_cap", 0) or 0) < max_mcap
            ]
            if matching:
                wins = sum(1 for t in matching if t.get("is_win"))
                total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in matching)
                patterns.append(
                    TokenPattern(
                        characteristic="market_cap",
                        characteristic_value=name,
                        trade_count=len(matching),
                        win_rate=(
                            Decimal(wins) / Decimal(len(matching)) * 100
                            if matching
                            else Decimal("0")
                        ),
                        avg_pnl=total_pnl / len(matching) if matching else Decimal("0"),
                    )
                )

        # Token age patterns
        age_ranges = [
            ("new_token", 0, 1),
            ("young_token", 1, 7),
            ("mature_token", 7, 30),
            ("old_token", 30, 365),
        ]

        for name, min_days, max_days in age_ranges:
            matching = [
                t
                for t in trades
                if min_days <= float(t.get("token_age_days", 0) or 0) < max_days
            ]
            if matching:
                wins = sum(1 for t in matching if t.get("is_win"))
                total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in matching)
                patterns.append(
                    TokenPattern(
                        characteristic="token_age",
                        characteristic_value=name,
                        trade_count=len(matching),
                        win_rate=(
                            Decimal(wins) / Decimal(len(matching)) * 100
                            if matching
                            else Decimal("0")
                        ),
                        avg_pnl=total_pnl / len(matching) if matching else Decimal("0"),
                    )
                )

        return patterns

    def _analyze_cluster_patterns(self, trades: list[dict]) -> list[ClusterPattern]:
        """Analyze cluster vs solo trade patterns.

        Args:
            trades: List of trade dicts

        Returns:
            List of ClusterPattern objects (cluster and solo)
        """
        cluster_trades = [t for t in trades if t.get("is_cluster_trade")]
        solo_trades = [t for t in trades if not t.get("is_cluster_trade")]

        patterns = []

        if cluster_trades:
            wins = sum(1 for t in cluster_trades if t.get("is_win"))
            total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in cluster_trades)
            patterns.append(
                ClusterPattern(
                    is_cluster_trade=True,
                    trade_count=len(cluster_trades),
                    win_count=wins,
                    win_rate=Decimal(wins) / Decimal(len(cluster_trades)) * 100,
                    avg_pnl=total_pnl / len(cluster_trades),
                )
            )

        if solo_trades:
            wins = sum(1 for t in solo_trades if t.get("is_win"))
            total_pnl = sum(Decimal(str(t.get("realized_pnl_sol", 0))) for t in solo_trades)
            patterns.append(
                ClusterPattern(
                    is_cluster_trade=False,
                    trade_count=len(solo_trades),
                    win_count=wins,
                    win_rate=Decimal(wins) / Decimal(len(solo_trades)) * 100,
                    avg_pnl=total_pnl / len(solo_trades),
                )
            )

        return patterns

    def _time_to_patterns(
        self, time_patterns: list[TimePattern], baseline: Decimal
    ) -> list[Pattern]:
        """Convert time patterns to Pattern objects.

        Args:
            time_patterns: List of TimePattern objects
            baseline: Baseline win rate

        Returns:
            List of Pattern objects
        """
        patterns = []
        days_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

        for tp in time_patterns:
            if tp.hour is not None:
                name = f"Hour {tp.hour}:00 UTC"
                pattern_type = PatternType.TIME_OF_DAY
            elif tp.day_of_week is not None:
                name = days_names[tp.day_of_week]
                pattern_type = PatternType.DAY_OF_WEEK
            else:
                continue

            delta = tp.win_rate - baseline
            sentiment = self._classify_sentiment(delta)
            significance = self._calculate_significance(
                tp.trade_count, float(tp.win_rate), float(baseline)
            )
            action = self._generate_action(pattern_type, name, sentiment, delta)

            patterns.append(
                Pattern(
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
                )
            )

        return patterns

    def _wallet_to_patterns(
        self, wallet_patterns: list[WalletPattern], baseline: Decimal
    ) -> list[Pattern]:
        """Convert wallet patterns to Pattern objects.

        Args:
            wallet_patterns: List of WalletPattern objects
            baseline: Baseline win rate

        Returns:
            List of Pattern objects
        """
        patterns = []

        for wp in wallet_patterns:
            if wp.trade_count < 5:
                continue

            delta = wp.win_rate - baseline

            # Only include significantly different wallets
            if abs(delta) <= 10:
                continue

            sentiment = self._classify_sentiment(delta)
            significance = self._calculate_significance(
                wp.trade_count, float(wp.win_rate), float(baseline)
            )

            if sentiment == PatternSentiment.POSITIVE:
                action = "Prioritize signals from this wallet"
            else:
                action = "Review wallet score, consider reducing weight"

            patterns.append(
                Pattern(
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
                )
            )

        return patterns

    def _token_to_patterns(
        self, token_patterns: list[TokenPattern], baseline: Decimal
    ) -> list[Pattern]:
        """Convert token patterns to Pattern objects.

        Args:
            token_patterns: List of TokenPattern objects
            baseline: Baseline win rate

        Returns:
            List of Pattern objects
        """
        patterns = []

        for tp in token_patterns:
            if tp.trade_count < 10:
                continue

            delta = tp.win_rate - baseline
            sentiment = self._classify_sentiment(delta)
            significance = self._calculate_significance(
                tp.trade_count, float(tp.win_rate), float(baseline)
            )

            if sentiment == PatternSentiment.POSITIVE:
                action = f"Favor {tp.characteristic_value} tokens"
            elif sentiment == PatternSentiment.NEGATIVE:
                action = f"Avoid {tp.characteristic_value} tokens"
            else:
                action = "No significant edge"

            patterns.append(
                Pattern(
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
                )
            )

        return patterns

    def _cluster_to_patterns(
        self, cluster_patterns: list[ClusterPattern], baseline: Decimal
    ) -> list[Pattern]:
        """Convert cluster patterns to Pattern objects.

        Args:
            cluster_patterns: List of ClusterPattern objects
            baseline: Baseline win rate

        Returns:
            List of Pattern objects
        """
        patterns = []

        for cp in cluster_patterns:
            delta = cp.win_rate - baseline
            sentiment = self._classify_sentiment(delta)
            significance = self._calculate_significance(
                cp.trade_count, float(cp.win_rate), float(baseline)
            )

            trade_type = "Cluster" if cp.is_cluster_trade else "Solo"
            if sentiment == PatternSentiment.POSITIVE:
                action = f"Prioritize {trade_type.lower()} trades"
            elif sentiment == PatternSentiment.NEGATIVE:
                action = f"Reduce weight for {trade_type.lower()} trades"
            else:
                action = "No significant edge"

            patterns.append(
                Pattern(
                    id=uuid4(),
                    pattern_type=PatternType.CLUSTER_VS_SOLO,
                    pattern_name=f"{trade_type} Trades",
                    description=f"{trade_type} trades win rate: {cp.win_rate:.1f}%",
                    sentiment=sentiment,
                    win_rate=cp.win_rate,
                    baseline_win_rate=baseline,
                    sample_size=cp.trade_count,
                    significance=significance,
                    suggested_action=action,
                )
            )

        return patterns

    def _classify_sentiment(self, delta: Decimal) -> PatternSentiment:
        """Classify pattern sentiment based on delta.

        Args:
            delta: Win rate delta from baseline

        Returns:
            PatternSentiment classification
        """
        if delta > self.POSITIVE_DELTA_THRESHOLD:
            return PatternSentiment.POSITIVE
        elif delta < self.NEGATIVE_DELTA_THRESHOLD:
            return PatternSentiment.NEGATIVE
        return PatternSentiment.NEUTRAL

    def _calculate_significance(
        self, sample_size: int, win_rate: float, baseline: float
    ) -> SignificanceLevel:
        """Calculate statistical significance using chi-square test.

        Args:
            sample_size: Number of trades in pattern
            win_rate: Win rate for pattern (%)
            baseline: Baseline win rate (%)

        Returns:
            SignificanceLevel classification
        """
        if sample_size < self.MIN_SAMPLE_SIZE:
            return SignificanceLevel.NONE

        # Expected vs observed counts
        expected_wins = sample_size * (baseline / 100)
        expected_losses = sample_size - expected_wins
        observed_wins = sample_size * (win_rate / 100)
        observed_losses = sample_size - observed_wins

        # Avoid division by zero
        if expected_wins <= 0 or expected_losses <= 0:
            return SignificanceLevel.NONE

        try:
            # Chi-square test
            _, p_value = stats.chisquare(
                [observed_wins, observed_losses], [expected_wins, expected_losses]
            )

            if p_value < self.HIGH_P_VALUE:
                return SignificanceLevel.HIGH
            elif p_value < self.MEDIUM_P_VALUE:
                return SignificanceLevel.MEDIUM
            elif p_value < self.LOW_P_VALUE:
                return SignificanceLevel.LOW
        except (ValueError, ZeroDivisionError):
            pass

        return SignificanceLevel.NONE

    def _generate_action(
        self,
        pattern_type: PatternType,
        name: str,
        sentiment: PatternSentiment,
        delta: Decimal,
    ) -> str:
        """Generate actionable recommendation.

        Args:
            pattern_type: Type of pattern
            name: Pattern name
            sentiment: Pattern sentiment
            delta: Win rate delta

        Returns:
            Action recommendation string
        """
        if sentiment == PatternSentiment.NEUTRAL:
            return "No significant deviation from baseline"

        # Build action based on sentiment and pattern type
        is_positive = sentiment == PatternSentiment.POSITIVE

        action_templates = {
            (True, PatternType.TIME_OF_DAY): f"Consider increasing position sizes during {name}",
            (True, PatternType.DAY_OF_WEEK): f"Favorable day: {name} shows +{delta:.1f}% win rate",
            (False, PatternType.TIME_OF_DAY): f"Consider reducing activity during {name}",
            (False, PatternType.DAY_OF_WEEK): f"Caution on {name}: {delta:.1f}% below baseline",
        }

        key = (is_positive, pattern_type)
        if key in action_templates:
            return action_templates[key]

        # Default actions for other pattern types
        if is_positive:
            return f"Pattern shows {delta:+.1f}% advantage"
        return f"Pattern shows {delta:.1f}% disadvantage"

    async def _load_trades(self, start: datetime, end: datetime) -> list[dict]:
        """Load trade data for analysis.

        Args:
            start: Start date
            end: End date

        Returns:
            List of trade dicts
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*, signals(wallet_score, cluster_score, token_score, is_cluster_trade)")
            .gte("entry_timestamp", start.isoformat())
            .lte("entry_timestamp", end.isoformat())
            .execute()
        )
        return result.data

    async def _save_analysis(self, result: PatternAnalysisResult) -> None:
        """Persist analysis results.

        Args:
            result: Analysis result to save
        """
        await self.supabase.table("pattern_analyses").insert(
            {
                "id": str(result.id),
                "analyzed_at": result.analyzed_at.isoformat(),
                "trade_count": result.trade_count,
                "baseline_win_rate": str(result.baseline_win_rate),
                "patterns": [p.model_dump(mode="json") for p in result.patterns],
            }
        ).execute()

    async def _generate_alerts(self, patterns: list[Pattern]) -> None:
        """Generate alerts for significant patterns.

        Args:
            patterns: List of significant patterns
        """
        for pattern in patterns[:5]:
            if pattern.is_actionable and pattern.sentiment in [
                PatternSentiment.POSITIVE,
                PatternSentiment.NEGATIVE,
            ]:
                alert = PatternAlert(
                    id=uuid4(),
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

    async def get_alerts(
        self,
        unacknowledged_only: bool = True,
        limit: int = 20,
    ) -> list[PatternAlert]:
        """Get pattern alerts.

        Args:
            unacknowledged_only: Only return unacknowledged alerts
            limit: Maximum number of alerts to return

        Returns:
            List of pattern alerts
        """
        query = self.supabase.table("pattern_alerts").select("*")

        if unacknowledged_only:
            query = query.eq("acknowledged", False)

        query = query.order("created_at", desc=True).limit(limit)
        result = await query.execute()

        return [PatternAlert(**row) for row in result.data]

    async def acknowledge_alert(self, alert_id: str) -> None:
        """Acknowledge a pattern alert.

        Args:
            alert_id: ID of the alert to acknowledge
        """
        await (
            self.supabase.table("pattern_alerts")
            .update({"acknowledged": True})
            .eq("id", alert_id)
            .execute()
        )


# Singleton instance
_analyzer: PatternAnalyzer | None = None


def get_pattern_analyzer(supabase_client) -> PatternAnalyzer:
    """Get or create singleton PatternAnalyzer instance.

    Args:
        supabase_client: Supabase client instance

    Returns:
        PatternAnalyzer instance
    """
    global _analyzer
    if _analyzer is None:
        _analyzer = PatternAnalyzer(supabase_client)
    return _analyzer
