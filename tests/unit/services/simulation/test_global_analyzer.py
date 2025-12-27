"""Tests for global analyzer service."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.services.simulation.global_analyzer import (
    GlobalAnalysisResult,
    GlobalAnalyzer,
    StrategyStats,
    get_global_analyzer,
    reset_global_analyzer,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create mock Supabase client."""
    client = MagicMock()
    client.table = MagicMock(return_value=client)
    client.select = MagicMock(return_value=client)
    client.eq = MagicMock(return_value=client)
    client.gte = MagicMock(return_value=client)
    client.in_ = MagicMock(return_value=client)
    client.order = MagicMock(return_value=client)
    client.limit = MagicMock(return_value=client)
    client.execute = AsyncMock()
    return client


@pytest.fixture
def mock_engine() -> MagicMock:
    """Create mock simulation engine."""
    engine = MagicMock()
    engine.simulate_position = AsyncMock()
    return engine


@pytest.fixture
def mock_strategy_service() -> MagicMock:
    """Create mock strategy service."""
    service = MagicMock()
    service.get = AsyncMock()
    service.list_all = AsyncMock()
    return service


@pytest.fixture
def sample_position() -> dict:
    """Create sample position data."""
    return {
        "id": "position-123",
        "token_address": "token123",
        "entry_price": "1.0",
        "exit_price": "1.5",
        "entry_time": "2024-01-01T10:00:00+00:00",
        "exit_time": "2024-01-01T14:00:00+00:00",
        "size_sol": "10.0",
        "pnl_pct": "50.0",
    }


@pytest.fixture
def sample_strategy() -> MagicMock:
    """Create sample strategy."""
    strategy = MagicMock()
    strategy.id = "strategy-1"
    strategy.name = "Test Strategy"
    strategy.status = "active"
    strategy.rules = []
    return strategy


@pytest.fixture
def sample_sim_result() -> MagicMock:
    """Create sample simulation result."""
    result = MagicMock()
    result.final_pnl_pct = Decimal("60.0")
    result.final_pnl_sol = Decimal("6.0")
    result.hold_duration_hours = Decimal("4.0")
    return result


@pytest.fixture
def analyzer() -> GlobalAnalyzer:
    """Create analyzer instance."""
    reset_global_analyzer()
    return GlobalAnalyzer()


class TestStrategyStats:
    """Tests for StrategyStats dataclass."""

    def test_creates_stats(self) -> None:
        """StrategyStats initializes correctly."""
        stats = StrategyStats(
            strategy_id="s-1",
            strategy_name="Test",
            positions_analyzed=10,
            winning_positions=7,
            losing_positions=3,
            win_rate_pct=Decimal("70.0"),
            total_pnl_pct=Decimal("150.0"),
            total_pnl_sol=Decimal("15.0"),
            avg_pnl_pct=Decimal("15.0"),
            median_pnl_pct=Decimal("12.0"),
            max_gain_pct=Decimal("50.0"),
            max_loss_pct=Decimal("-10.0"),
            avg_hold_hours=Decimal("5.5"),
            best_for="standard",
        )

        assert stats.strategy_id == "s-1"
        assert stats.positions_analyzed == 10
        assert stats.win_rate_pct == Decimal("70.0")

    def test_default_values(self) -> None:
        """StrategyStats has correct default values."""
        stats = StrategyStats(
            strategy_id="s-1",
            strategy_name="Test",
            positions_analyzed=1,
            winning_positions=1,
            losing_positions=0,
            win_rate_pct=Decimal("100"),
            total_pnl_pct=Decimal("10"),
            total_pnl_sol=Decimal("1"),
            avg_pnl_pct=Decimal("10"),
            median_pnl_pct=Decimal("10"),
            max_gain_pct=Decimal("10"),
            max_loss_pct=Decimal("10"),
            avg_hold_hours=Decimal("1"),
            best_for="both",
        )

        assert stats.avg_improvement_pct == Decimal("0")
        assert stats.best_position_id == ""
        assert stats.worst_position_id == ""


class TestGlobalAnalysisResult:
    """Tests for GlobalAnalysisResult dataclass."""

    def test_creates_result(self) -> None:
        """GlobalAnalysisResult initializes correctly."""
        result = GlobalAnalysisResult(
            period_days=30,
            total_positions=50,
            strategies_compared=3,
            strategy_stats=[],
            recommended_strategy_id="s-1",
            recommended_strategy_name="Best",
            best_for_standard_id="s-2",
            best_for_high_conviction_id="s-3",
            analysis_duration_seconds=5.5,
        )

        assert result.period_days == 30
        assert result.total_positions == 50
        assert result.recommended_strategy_id == "s-1"


class TestGlobalAnalyzer:
    """Tests for GlobalAnalyzer class."""

    @pytest.mark.asyncio
    async def test_get_positions_for_analysis(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        sample_position: dict,
    ) -> None:
        """get_positions_for_analysis returns closed positions."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])

        with patch.object(analyzer, "_get_client", return_value=mock_client):
            positions = await analyzer.get_positions_for_analysis(days_back=30)

        assert len(positions) == 1
        assert positions[0]["id"] == "position-123"
        mock_client.eq.assert_called_with("status", "closed")

    @pytest.mark.asyncio
    async def test_analyze_returns_none_no_positions(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
    ) -> None:
        """analyze returns None when no positions found."""
        mock_client.execute.return_value = MagicMock(data=[])

        with patch.object(analyzer, "_get_client", return_value=mock_client):
            result = await analyzer.analyze(days_back=30)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_returns_none_no_strategies(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
    ) -> None:
        """analyze returns None when no strategies found."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = []

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result = await analyzer.analyze(days_back=30)

        assert result is None

    @pytest.mark.asyncio
    async def test_analyze_full_flow(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze runs full analysis and returns result."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result = await analyzer.analyze(days_back=30, use_cache=False)

        assert result is not None
        assert result.total_positions == 1
        assert result.strategies_compared == 1
        assert len(result.strategy_stats) == 1

    @pytest.mark.asyncio
    async def test_analyze_with_specific_positions(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze with specific position_ids queries by ID."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result = await analyzer.analyze(
                position_ids=["position-123"],
                use_cache=False,
            )

        assert result is not None
        mock_client.in_.assert_called_with("id", ["position-123"])

    @pytest.mark.asyncio
    async def test_analyze_with_specific_strategies(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze with specific strategy_ids fetches by ID."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.get.return_value = sample_strategy
        mock_engine.simulate_position.return_value = sample_sim_result

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result = await analyzer.analyze(
                strategy_ids=["strategy-1"],
                use_cache=False,
            )

        assert result is not None
        mock_strategy_service.get.assert_called_with("strategy-1")

    @pytest.mark.asyncio
    async def test_analyze_progress_callback(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze calls progress callback."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        progress_calls = []

        def on_progress(current: int, total: int) -> None:
            progress_calls.append((current, total))

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            await analyzer.analyze(
                days_back=30,
                on_progress=on_progress,
                use_cache=False,
            )

        assert len(progress_calls) == 1
        assert progress_calls[0] == (1, 1)


class TestGlobalAnalyzerCache:
    """Tests for caching functionality."""

    @pytest.mark.asyncio
    async def test_uses_cache(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze uses cached result on second call."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result1 = await analyzer.analyze(days_back=30, use_cache=True)
            result2 = await analyzer.analyze(days_back=30, use_cache=True)

        assert result1 is result2
        # Engine should only be called once
        assert mock_engine.simulate_position.call_count == 1

    @pytest.mark.asyncio
    async def test_bypasses_cache(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze bypasses cache when use_cache=False."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            await analyzer.analyze(days_back=30, use_cache=False)
            await analyzer.analyze(days_back=30, use_cache=False)

        # Engine should be called twice
        assert mock_engine.simulate_position.call_count == 2

    def test_clear_cache(self, analyzer: GlobalAnalyzer) -> None:
        """clear_cache removes all cached results."""
        # Manually add cache entries
        analyzer._cache["key1"] = MagicMock()
        analyzer._cache_timestamps["key1"] = datetime.now(UTC)

        analyzer.clear_cache()

        assert len(analyzer._cache) == 0
        assert len(analyzer._cache_timestamps) == 0

    @pytest.mark.asyncio
    async def test_expired_cache(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
        sample_sim_result: MagicMock,
    ) -> None:
        """analyze ignores expired cache."""
        mock_client.execute.return_value = MagicMock(data=[sample_position])
        mock_strategy_service.list_all.return_value = [sample_strategy]
        mock_engine.simulate_position.return_value = sample_sim_result

        # Pre-populate cache with expired entry
        cache_key = "30:all:active"
        analyzer._cache[cache_key] = MagicMock()
        analyzer._cache_timestamps[cache_key] = datetime.now(UTC) - timedelta(hours=2)

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            await analyzer.analyze(days_back=30, use_cache=True)

        # Should fetch fresh data
        mock_engine.simulate_position.assert_called_once()


class TestGlobalAnalyzerCancellation:
    """Tests for cancellation functionality."""

    def test_cancel(self, analyzer: GlobalAnalyzer) -> None:
        """cancel sets cancelled flag."""
        analyzer.cancel()
        assert analyzer._cancelled is True

    @pytest.mark.asyncio
    async def test_analyze_respects_cancellation(
        self,
        analyzer: GlobalAnalyzer,
        mock_client: MagicMock,
        mock_engine: MagicMock,
        mock_strategy_service: MagicMock,
        sample_position: dict,
        sample_strategy: MagicMock,
    ) -> None:
        """analyze returns None when cancelled."""
        # Set up mocks
        positions = [
            {**sample_position, "id": f"pos-{i}"}
            for i in range(5)
        ]
        mock_client.execute.return_value = MagicMock(data=positions)
        mock_strategy_service.list_all.return_value = [sample_strategy]

        # Cancel after first simulation
        sim_count = 0

        async def slow_sim(**kwargs):
            nonlocal sim_count
            sim_count += 1
            if sim_count >= 2:
                analyzer.cancel()
            result = MagicMock()
            result.final_pnl_pct = Decimal("10.0")
            result.final_pnl_sol = Decimal("1.0")
            result.hold_duration_hours = Decimal("1.0")
            return result

        mock_engine.simulate_position = slow_sim

        with (
            patch.object(analyzer, "_get_client", return_value=mock_client),
            patch.object(analyzer, "_get_engine", return_value=mock_engine),
            patch.object(
                analyzer, "_get_strategy_service", return_value=mock_strategy_service
            ),
        ):
            result = await analyzer.analyze(days_back=30, use_cache=False)

        assert result is None


class TestDetermineBestFor:
    """Tests for _determine_best_for heuristic."""

    def test_standard_strategy(self, analyzer: GlobalAnalyzer) -> None:
        """Strategy without wide stops or high TPs is standard."""
        strategy = MagicMock()
        strategy.rules = [
            MagicMock(rule_type="stop_loss", trigger_pct=Decimal("-5")),
            MagicMock(rule_type="take_profit", trigger_pct=Decimal("20")),
        ]

        result = analyzer._determine_best_for(strategy)
        assert result == "standard"

    def test_high_conviction_strategy(self, analyzer: GlobalAnalyzer) -> None:
        """Strategy with wide stops and high TPs is high conviction."""
        strategy = MagicMock()
        strategy.rules = [
            MagicMock(rule_type="stop_loss", trigger_pct=Decimal("-15")),
            MagicMock(rule_type="take_profit", trigger_pct=Decimal("50")),
        ]

        result = analyzer._determine_best_for(strategy)
        assert result == "high"

    def test_both_strategy(self, analyzer: GlobalAnalyzer) -> None:
        """Strategy with mixed characteristics is both."""
        strategy = MagicMock()
        strategy.rules = [
            MagicMock(rule_type="stop_loss", trigger_pct=Decimal("-15")),
            MagicMock(rule_type="take_profit", trigger_pct=Decimal("20")),
        ]

        result = analyzer._determine_best_for(strategy)
        assert result == "both"


class TestCalculateMedian:
    """Tests for _calculate_median helper."""

    def test_empty_list(self, analyzer: GlobalAnalyzer) -> None:
        """Returns 0 for empty list."""
        assert analyzer._calculate_median([], 0) == Decimal("0")

    def test_odd_count(self, analyzer: GlobalAnalyzer) -> None:
        """Returns middle element for odd count."""
        values = [Decimal("1"), Decimal("2"), Decimal("3")]
        assert analyzer._calculate_median(values, 1) == Decimal("2")

    def test_even_count(self, analyzer: GlobalAnalyzer) -> None:
        """Returns average of middle two for even count."""
        values = [Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")]
        assert analyzer._calculate_median(values, 2) == Decimal("2.5")


class TestSingleton:
    """Tests for singleton pattern."""

    @pytest.mark.asyncio
    async def test_get_global_analyzer(self) -> None:
        """get_global_analyzer returns singleton."""
        reset_global_analyzer()
        a1 = await get_global_analyzer()
        a2 = await get_global_analyzer()
        assert a1 is a2

    def test_reset_global_analyzer(self) -> None:
        """reset_global_analyzer clears singleton."""
        reset_global_analyzer()
        # Verify no error is raised
        reset_global_analyzer()
