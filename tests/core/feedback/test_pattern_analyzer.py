"""Tests for pattern analysis and insights."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from walltrack.core.feedback.pattern_models import (
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
from walltrack.core.feedback.pattern_analyzer import PatternAnalyzer


class ChainableMock:
    """Mock that supports method chaining for Supabase client."""

    def __init__(self, data=None, count=None):
        self._data = data if data is not None else []
        self._count = count

    def __getattr__(self, name):
        return lambda *args, **kwargs: self

    async def execute(self):
        return MagicMock(data=self._data, count=self._count)


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()
    client.table.return_value = ChainableMock()
    return client


@pytest.fixture
def analyzer(mock_supabase):
    """Create PatternAnalyzer instance."""
    return PatternAnalyzer(mock_supabase)


@pytest.fixture
def sample_trades():
    """Generate sample trade data with varied patterns."""
    trades = []
    now = datetime.now(UTC)

    for i in range(100):
        # Create trades with patterns:
        # - Morning hours (6-12) have higher win rate
        # - Weekend trades (5,6) have lower win rate
        # - Cluster trades have higher win rate
        hour = 6 + (i % 18)  # Hours 6-23
        day = i % 7

        # Create predictable patterns
        is_morning = 6 <= hour < 12
        is_weekend = day >= 5
        is_cluster = i % 2 == 0

        # Win probability based on patterns
        win_prob = 0.5
        if is_morning:
            win_prob += 0.2
        if is_weekend:
            win_prob -= 0.15
        if is_cluster:
            win_prob += 0.1

        is_win = (i % 100) / 100 < win_prob

        trades.append(
            {
                "id": str(uuid4()),
                "wallet_address": f"wallet_{i % 10}",
                "entry_timestamp": (now - timedelta(hours=i * 6)).replace(hour=hour).isoformat(),
                "is_win": is_win,
                "realized_pnl_sol": "0.5" if is_win else "-0.3",
                "is_cluster_trade": is_cluster,
                "market_cap": 500000 * (1 + i % 5),
                "token_age_days": i % 30,
                "signal_score": 0.6 + (i % 4) * 0.1,
            }
        )
    return trades


class TestPatternModels:
    """Tests for pattern models."""

    def test_pattern_win_rate_delta(self):
        """Test win rate delta calculation."""
        pattern = Pattern(
            id=uuid4(),
            pattern_type=PatternType.TIME_OF_DAY,
            pattern_name="Test",
            description="Test pattern",
            sentiment=PatternSentiment.POSITIVE,
            win_rate=Decimal("75"),
            baseline_win_rate=Decimal("60"),
            sample_size=50,
            significance=SignificanceLevel.HIGH,
            suggested_action="Test action",
        )
        assert pattern.win_rate_delta == Decimal("15")

    def test_pattern_is_actionable_true(self):
        """Test pattern is actionable with high significance."""
        pattern = Pattern(
            id=uuid4(),
            pattern_type=PatternType.WALLET,
            pattern_name="Test",
            description="Test",
            sentiment=PatternSentiment.POSITIVE,
            win_rate=Decimal("80"),
            baseline_win_rate=Decimal("55"),
            sample_size=30,
            significance=SignificanceLevel.HIGH,
            suggested_action="Act",
        )
        assert pattern.is_actionable is True

    def test_pattern_is_actionable_false_low_sample(self):
        """Test pattern not actionable with low sample."""
        pattern = Pattern(
            id=uuid4(),
            pattern_type=PatternType.WALLET,
            pattern_name="Test",
            description="Test",
            sentiment=PatternSentiment.POSITIVE,
            win_rate=Decimal("80"),
            baseline_win_rate=Decimal("55"),
            sample_size=10,  # Below threshold
            significance=SignificanceLevel.HIGH,
            suggested_action="Act",
        )
        assert pattern.is_actionable is False

    def test_pattern_is_actionable_false_low_significance(self):
        """Test pattern not actionable with low significance."""
        pattern = Pattern(
            id=uuid4(),
            pattern_type=PatternType.WALLET,
            pattern_name="Test",
            description="Test",
            sentiment=PatternSentiment.POSITIVE,
            win_rate=Decimal("80"),
            baseline_win_rate=Decimal("55"),
            sample_size=50,
            significance=SignificanceLevel.NONE,  # Low significance
            suggested_action="Act",
        )
        assert pattern.is_actionable is False

    def test_time_pattern_model(self):
        """Test TimePattern model."""
        pattern = TimePattern(
            hour=10,
            trade_count=25,
            win_count=18,
            win_rate=Decimal("72"),
            avg_pnl=Decimal("0.5"),
            total_pnl=Decimal("12.5"),
        )
        assert pattern.hour == 10
        assert pattern.win_rate == Decimal("72")

    def test_wallet_pattern_model(self):
        """Test WalletPattern model."""
        pattern = WalletPattern(
            wallet_address="abc123",
            wallet_score=Decimal("0.85"),
            trade_count=15,
            win_count=12,
            win_rate=Decimal("80"),
            avg_pnl=Decimal("0.3"),
            is_top_performer=True,
        )
        assert pattern.is_top_performer is True
        assert pattern.wallet_score == Decimal("0.85")


class TestTimePatternAnalysis:
    """Tests for time pattern analysis."""

    def test_hourly_pattern_detection(self, analyzer, sample_trades):
        """Test hourly patterns are detected."""
        patterns = analyzer._analyze_time_patterns(sample_trades, Decimal("50"))
        hour_patterns = [p for p in patterns if p.hour is not None]
        assert len(hour_patterns) > 0

    def test_day_of_week_patterns(self, analyzer, sample_trades):
        """Test day of week patterns are detected."""
        patterns = analyzer._analyze_time_patterns(sample_trades, Decimal("50"))
        day_patterns = [p for p in patterns if p.day_of_week is not None]
        assert len(day_patterns) > 0

    def test_time_pattern_win_rate_calculated(self, analyzer, sample_trades):
        """Test win rate is calculated for time patterns."""
        patterns = analyzer._analyze_time_patterns(sample_trades, Decimal("50"))
        for pattern in patterns:
            if pattern.trade_count > 0:
                expected_rate = Decimal(pattern.win_count) / Decimal(pattern.trade_count) * 100
                assert pattern.win_rate == expected_rate


class TestWalletPatternAnalysis:
    """Tests for wallet pattern analysis."""

    @pytest.mark.asyncio
    async def test_wallet_patterns_detected(self, analyzer, sample_trades):
        """Test wallet patterns are detected."""
        patterns = await analyzer._analyze_wallet_patterns(sample_trades, Decimal("50"))
        assert len(patterns) > 0

    @pytest.mark.asyncio
    async def test_wallet_top_performers_marked(self, analyzer, sample_trades):
        """Test top performers are marked."""
        patterns = await analyzer._analyze_wallet_patterns(sample_trades, Decimal("50"))
        top_performers = [p for p in patterns if p.is_top_performer]
        # At least some should be marked as top performers
        if len(patterns) > 5:
            assert len(top_performers) > 0


class TestTokenPatternAnalysis:
    """Tests for token pattern analysis."""

    def test_market_cap_patterns(self, analyzer, sample_trades):
        """Test market cap patterns are analyzed."""
        patterns = analyzer._analyze_token_patterns(sample_trades, Decimal("50"))
        mcap_patterns = [p for p in patterns if p.characteristic == "market_cap"]
        assert len(mcap_patterns) > 0

    def test_token_age_patterns(self, analyzer, sample_trades):
        """Test token age patterns are analyzed."""
        patterns = analyzer._analyze_token_patterns(sample_trades, Decimal("50"))
        age_patterns = [p for p in patterns if p.characteristic == "token_age"]
        assert len(age_patterns) > 0


class TestClusterPatternAnalysis:
    """Tests for cluster pattern analysis."""

    def test_cluster_patterns_detected(self, analyzer, sample_trades):
        """Test cluster vs solo patterns are detected."""
        patterns = analyzer._analyze_cluster_patterns(sample_trades)
        assert len(patterns) == 2  # Both cluster and solo

    def test_cluster_pattern_win_rate(self, analyzer, sample_trades):
        """Test cluster pattern win rates are calculated."""
        patterns = analyzer._analyze_cluster_patterns(sample_trades)
        for pattern in patterns:
            if pattern.trade_count > 0:
                expected_rate = Decimal(pattern.win_count) / Decimal(pattern.trade_count) * 100
                assert pattern.win_rate == expected_rate


class TestSignificanceCalculation:
    """Tests for statistical significance calculation."""

    def test_high_significance_detection(self, analyzer):
        """Test high significance is detected for strong patterns."""
        sig = analyzer._calculate_significance(100, 80.0, 50.0)
        assert sig in [SignificanceLevel.HIGH, SignificanceLevel.MEDIUM]

    def test_low_significance_detection(self, analyzer):
        """Test low/none significance for weak patterns."""
        sig = analyzer._calculate_significance(15, 52.0, 50.0)
        assert sig in [SignificanceLevel.LOW, SignificanceLevel.NONE]

    def test_small_sample_returns_none(self, analyzer):
        """Test small samples return NONE significance."""
        sig = analyzer._calculate_significance(5, 80.0, 50.0)
        assert sig == SignificanceLevel.NONE


class TestPatternConversion:
    """Tests for pattern conversion to Pattern objects."""

    def test_time_to_patterns_conversion(self, analyzer):
        """Test time patterns convert to Pattern objects."""
        time_patterns = [
            TimePattern(hour=10, trade_count=30, win_count=24, win_rate=Decimal("80")),
        ]
        patterns = analyzer._time_to_patterns(time_patterns, Decimal("50"))
        assert len(patterns) == 1
        assert patterns[0].pattern_type == PatternType.TIME_OF_DAY
        assert patterns[0].sentiment == PatternSentiment.POSITIVE

    def test_day_of_week_conversion(self, analyzer):
        """Test day of week patterns convert correctly."""
        time_patterns = [
            TimePattern(day_of_week=0, trade_count=25, win_count=20, win_rate=Decimal("80")),
        ]
        patterns = analyzer._time_to_patterns(time_patterns, Decimal("50"))
        assert patterns[0].pattern_type == PatternType.DAY_OF_WEEK
        assert "Monday" in patterns[0].pattern_name

    def test_negative_pattern_detection(self, analyzer):
        """Test negative patterns are correctly classified."""
        time_patterns = [
            TimePattern(hour=3, trade_count=25, win_count=8, win_rate=Decimal("32")),
        ]
        patterns = analyzer._time_to_patterns(time_patterns, Decimal("50"))
        assert patterns[0].sentiment == PatternSentiment.NEGATIVE


class TestActionGeneration:
    """Tests for action generation."""

    def test_positive_time_action(self, analyzer):
        """Test positive time of day action generation."""
        action = analyzer._generate_action(
            PatternType.TIME_OF_DAY, "Hour 10:00", PatternSentiment.POSITIVE, Decimal("15")
        )
        assert "10:00" in action
        assert "increase" in action.lower() or "position" in action.lower()

    def test_negative_day_action(self, analyzer):
        """Test negative day of week action generation."""
        action = analyzer._generate_action(
            PatternType.DAY_OF_WEEK, "Saturday", PatternSentiment.NEGATIVE, Decimal("-12")
        )
        assert "Saturday" in action
        assert "caution" in action.lower() or "reduce" in action.lower()


class TestFullAnalysis:
    """Tests for full analysis workflow."""

    @pytest.mark.asyncio
    async def test_full_analysis_with_data(self, analyzer, mock_supabase, sample_trades):
        """Test full analysis returns result."""
        mock_supabase.table.return_value = ChainableMock(data=sample_trades)
        analyzer._trades_cache = sample_trades

        result = await analyzer.run_full_analysis(days=30)

        assert isinstance(result, PatternAnalysisResult)
        assert result.trade_count == len(sample_trades)

    @pytest.mark.asyncio
    async def test_full_analysis_empty_data(self, analyzer, mock_supabase):
        """Test full analysis with no data returns empty result."""
        mock_supabase.table.return_value = ChainableMock(data=[])

        result = await analyzer.run_full_analysis(days=30)

        assert result.trade_count == 0
        assert result.baseline_win_rate == Decimal("0")

    @pytest.mark.asyncio
    async def test_analysis_identifies_top_patterns(self, analyzer, sample_trades):
        """Test top positive and negative patterns are identified."""
        analyzer._trades_cache = sample_trades

        result = await analyzer.run_full_analysis(days=30)

        # Should identify both positive and negative patterns
        assert isinstance(result.top_positive_patterns, list)
        assert isinstance(result.top_negative_patterns, list)


class TestPatternAlerts:
    """Tests for pattern alert generation."""

    def test_pattern_alert_model(self):
        """Test PatternAlert model."""
        alert = PatternAlert(
            id=uuid4(),
            pattern_id=uuid4(),
            pattern_type=PatternType.TIME_OF_DAY,
            pattern_name="Morning trades",
            sentiment=PatternSentiment.POSITIVE,
            message="High win rate in morning",
            suggested_action="Increase morning activity",
        )
        assert alert.acknowledged is False
        assert alert.sentiment == PatternSentiment.POSITIVE
