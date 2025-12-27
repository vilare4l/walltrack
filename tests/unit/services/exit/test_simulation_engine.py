"""Tests for ExitSimulationEngine."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyRule,
)
from walltrack.services.exit.simulation_engine import (
    ExitSimulationEngine,
    PricePoint,
    SimulationResult,
    reset_simulation_engine,
)


@pytest.fixture
def sample_strategy() -> ExitStrategy:
    """Create a sample exit strategy for testing."""
    return ExitStrategy(
        id="test-strategy-1",
        name="Test Strategy",
        description="Test description",
        version=1,
        status="active",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-10"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("20"),
                exit_pct=Decimal("50"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("50"),
                exit_pct=Decimal("100"),
                priority=2,
            ),
        ],
        max_hold_hours=24,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("2.0"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def trailing_stop_strategy() -> ExitStrategy:
    """Create a strategy with trailing stop."""
    return ExitStrategy(
        id="trailing-strategy-1",
        name="Trailing Strategy",
        description="With trailing stop",
        version=1,
        status="active",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-15"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="trailing_stop",
                trigger_pct=Decimal("-5"),
                exit_pct=Decimal("100"),
                priority=1,
                params={"activation_pct": 10},
            ),
        ],
        max_hold_hours=48,
        stagnation_hours=12,
        stagnation_threshold_pct=Decimal("3.0"),
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def engine() -> ExitSimulationEngine:
    """Create simulation engine for testing."""
    reset_simulation_engine()
    return ExitSimulationEngine()


@pytest.fixture
def base_time() -> datetime:
    """Base time for price history."""
    return datetime(2024, 1, 1, 12, 0, 0, tzinfo=UTC)


class TestPricePoint:
    """Tests for PricePoint dataclass."""

    def test_create_price_point(self, base_time: datetime) -> None:
        """Test creating a price point."""
        pp = PricePoint(
            timestamp=base_time,
            price=Decimal("1.5"),
            high=Decimal("1.6"),
            low=Decimal("1.4"),
        )

        assert pp.price == Decimal("1.5")
        assert pp.high == Decimal("1.6")
        assert pp.low == Decimal("1.4")

    def test_price_point_without_ohlc(self, base_time: datetime) -> None:
        """Test price point without high/low."""
        pp = PricePoint(timestamp=base_time, price=Decimal("1.5"))

        assert pp.high is None
        assert pp.low is None


class TestExitSimulationEngine:
    """Tests for ExitSimulationEngine."""

    def test_check_take_profit_rule(
        self, engine: ExitSimulationEngine, sample_strategy: ExitStrategy
    ) -> None:
        """Test take profit rule detection."""
        rule = sample_strategy.rules[1]  # 20% TP

        # Not triggered at 15%
        assert not engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("15"),
            current_price=Decimal("1.15"),
            trailing_high_price=Decimal("1.15"),
            hold_hours=1.0,
        )

        # Triggered at 20%
        assert engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("20"),
            current_price=Decimal("1.20"),
            trailing_high_price=Decimal("1.20"),
            hold_hours=1.0,
        )

        # Triggered above 20%
        assert engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("25"),
            current_price=Decimal("1.25"),
            trailing_high_price=Decimal("1.25"),
            hold_hours=1.0,
        )

    def test_check_stop_loss_rule(
        self, engine: ExitSimulationEngine, sample_strategy: ExitStrategy
    ) -> None:
        """Test stop loss rule detection."""
        rule = sample_strategy.rules[0]  # -10% SL

        # Not triggered at -5%
        assert not engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("-5"),
            current_price=Decimal("0.95"),
            trailing_high_price=Decimal("1.0"),
            hold_hours=1.0,
        )

        # Triggered at -10%
        assert engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("-10"),
            current_price=Decimal("0.90"),
            trailing_high_price=Decimal("1.0"),
            hold_hours=1.0,
        )

        # Triggered below -10%
        assert engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("-15"),
            current_price=Decimal("0.85"),
            trailing_high_price=Decimal("1.0"),
            hold_hours=1.0,
        )

    def test_check_trailing_stop_rule(
        self, engine: ExitSimulationEngine, trailing_stop_strategy: ExitStrategy
    ) -> None:
        """Test trailing stop rule detection."""
        rule = trailing_stop_strategy.rules[1]  # -5% trailing, 10% activation

        # Not triggered if not activated (pnl < 10%)
        assert not engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("8"),
            current_price=Decimal("1.08"),
            trailing_high_price=Decimal("1.10"),
            hold_hours=1.0,
        )

        # Activated but not triggered (drop < 5%)
        assert not engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("12"),
            current_price=Decimal("1.12"),
            trailing_high_price=Decimal("1.15"),  # 2.6% drop
            hold_hours=1.0,
        )

        # Triggered (activated + 5% drop from high)
        # High: 1.20, current: 1.14, drop = 5%
        assert engine._check_rule(
            rule=rule,
            pnl_pct=Decimal("14"),
            current_price=Decimal("1.14"),
            trailing_high_price=Decimal("1.20"),  # 5% drop
            hold_hours=1.0,
        )

    def test_simulate_on_prices_stop_loss(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulation with stop loss trigger."""
        prices = [
            PricePoint(timestamp=base_time + timedelta(hours=i), price=Decimal(str(p)))
            for i, p in enumerate([1.0, 0.98, 0.95, 0.89])  # -11% at end
        ]

        result = engine._simulate_on_prices(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            prices=prices,
        )

        assert len(result.triggers) == 1
        assert result.triggers[0].rule_type == "stop_loss"
        assert result.final_pnl_pct < Decimal("0")

    def test_simulate_on_prices_take_profit(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulation with take profit trigger."""
        prices = [
            PricePoint(timestamp=base_time + timedelta(hours=i), price=Decimal(str(p)))
            for i, p in enumerate([1.0, 1.10, 1.20, 1.25])  # +25% at end
        ]

        result = engine._simulate_on_prices(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            prices=prices,
        )

        # Should trigger first TP at 20%
        assert len(result.triggers) >= 1
        assert result.triggers[0].rule_type == "take_profit"
        assert result.final_pnl_pct > Decimal("0")

    def test_simulate_on_prices_max_hold(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulation with max hold time trigger."""
        # Create 25 hours of flat price (exceeds 24h max hold)
        prices = [
            PricePoint(
                timestamp=base_time + timedelta(hours=i), price=Decimal("1.0")
            )
            for i in range(26)
        ]

        result = engine._simulate_on_prices(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            prices=prices,
        )

        assert any(t.rule_type in ["max_hold_time", "stagnation"] for t in result.triggers)

    def test_simulate_on_prices_no_trigger(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulation with no exit trigger."""
        # Only 2 hours of mild price movement
        prices = [
            PricePoint(timestamp=base_time + timedelta(hours=i), price=Decimal(str(p)))
            for i, p in enumerate([1.0, 1.05])
        ]

        result = engine._simulate_on_prices(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            prices=prices,
        )

        assert len(result.triggers) == 0
        assert result.final_exit_price == Decimal("1.05")

    def test_calculate_aggregate_stats_empty(
        self, engine: ExitSimulationEngine
    ) -> None:
        """Test aggregate stats with no results."""
        stats = engine._calculate_aggregate_stats([])

        assert stats.total_positions == 0
        assert stats.win_rate == Decimal("0")
        assert stats.avg_pnl_pct == Decimal("0")

    def test_calculate_aggregate_stats(
        self, engine: ExitSimulationEngine, base_time: datetime
    ) -> None:
        """Test aggregate stats calculation."""
        results = [
            SimulationResult(
                strategy_id="test",
                strategy_name="Test",
                position_id="pos1",
                entry_price=Decimal("1.0"),
                entry_time=base_time,
                triggers=[],
                final_exit_price=Decimal("1.20"),
                final_exit_time=base_time + timedelta(hours=5),
                final_pnl_pct=Decimal("20"),
                final_pnl_sol=Decimal("2"),
                hold_duration_hours=Decimal("5"),
            ),
            SimulationResult(
                strategy_id="test",
                strategy_name="Test",
                position_id="pos2",
                entry_price=Decimal("1.0"),
                entry_time=base_time,
                triggers=[],
                final_exit_price=Decimal("0.90"),
                final_exit_time=base_time + timedelta(hours=3),
                final_pnl_pct=Decimal("-10"),
                final_pnl_sol=Decimal("-1"),
                hold_duration_hours=Decimal("3"),
            ),
            SimulationResult(
                strategy_id="test",
                strategy_name="Test",
                position_id="pos3",
                entry_price=Decimal("1.0"),
                entry_time=base_time,
                triggers=[],
                final_exit_price=Decimal("1.10"),
                final_exit_time=base_time + timedelta(hours=4),
                final_pnl_pct=Decimal("10"),
                final_pnl_sol=Decimal("1"),
                hold_duration_hours=Decimal("4"),
            ),
        ]

        stats = engine._calculate_aggregate_stats(results)

        assert stats.total_positions == 3
        assert stats.winning_positions == 2
        assert stats.losing_positions == 1
        # Win rate should be 66.67%
        assert stats.win_rate > Decimal("66")
        assert stats.win_rate < Decimal("67")
        # Avg PnL = (20 - 10 + 10) / 3 = 6.67%
        assert stats.avg_pnl_pct > Decimal("6")
        assert stats.avg_pnl_pct < Decimal("7")
        # Max gain = 20%
        assert stats.max_gain_pct == Decimal("20")
        # Max loss = -10%
        assert stats.max_loss_pct == Decimal("-10")

    @pytest.mark.asyncio
    async def test_simulate_position_with_price_history(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulating with provided price history."""
        price_history = [
            {"timestamp": base_time + timedelta(hours=i), "price": p}
            for i, p in enumerate([1.0, 1.10, 1.21, 1.25])  # +25% at end
        ]

        result = await engine.simulate_position(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            price_history=price_history,
        )

        assert result.strategy_id == sample_strategy.id
        assert len(result.triggers) >= 1
        assert result.final_pnl_pct > Decimal("0")

    @pytest.mark.asyncio
    async def test_simulate_position_with_actual_exit(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test simulation with actual exit comparison."""
        price_history = [
            {"timestamp": base_time + timedelta(hours=i), "price": p}
            for i, p in enumerate([1.0, 1.10, 1.21, 1.25])
        ]

        actual_exit = (Decimal("1.15"), base_time + timedelta(hours=2))

        result = await engine.simulate_position(
            strategy=sample_strategy,
            position_id="test-pos",
            entry_price=Decimal("1.0"),
            entry_time=base_time,
            position_size_sol=Decimal("10"),
            price_history=price_history,
            actual_exit=actual_exit,
        )

        assert result.actual_exit_price == Decimal("1.15")
        assert result.actual_pnl_pct == Decimal("15")
        assert result.pnl_difference is not None

    @pytest.mark.asyncio
    async def test_batch_simulate(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test batch simulation."""
        positions = [
            {
                "id": "pos1",
                "entry_price": "1.0",
                "entry_time": base_time,
                "size_sol": "10",
                "price_history": [
                    {"timestamp": base_time + timedelta(hours=i), "price": p}
                    for i, p in enumerate([1.0, 1.10, 1.21])
                ],
            },
            {
                "id": "pos2",
                "entry_price": "1.0",
                "entry_time": base_time,
                "size_sol": "10",
                "price_history": [
                    {"timestamp": base_time + timedelta(hours=i), "price": p}
                    for i, p in enumerate([1.0, 0.95, 0.89])
                ],
            },
        ]

        results, stats = await engine.batch_simulate(sample_strategy, positions)

        assert len(results) == 2
        assert stats.total_positions == 2
        assert stats.winning_positions == 1
        assert stats.losing_positions == 1

    @pytest.mark.asyncio
    async def test_compare_strategies(
        self,
        engine: ExitSimulationEngine,
        sample_strategy: ExitStrategy,
        trailing_stop_strategy: ExitStrategy,
        base_time: datetime,
    ) -> None:
        """Test strategy comparison."""
        positions = [
            {
                "id": "pos1",
                "entry_price": "1.0",
                "entry_time": base_time,
                "size_sol": "10",
                "price_history": [
                    {"timestamp": base_time + timedelta(hours=i), "price": p}
                    for i, p in enumerate([1.0, 1.15, 1.25, 1.20])
                ],
            },
        ]

        comparison = await engine.compare_strategies(
            strategies=[sample_strategy, trailing_stop_strategy],
            positions=positions,
        )

        assert len(comparison.strategies) == 2
        assert len(comparison.results) == 2
        assert comparison.best_strategy_id in comparison.strategies
        assert "win_rate" in comparison.best_by_metric
        assert "total_pnl" in comparison.best_by_metric
