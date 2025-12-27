"""Tests for WhatIfCalculator."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategy,
    ExitStrategyRule,
)
from walltrack.services.exit.what_if_calculator import (
    WhatIfCalculator,
    WhatIfScenario,
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
def calculator() -> WhatIfCalculator:
    """Create calculator instance."""
    return WhatIfCalculator()


@pytest.fixture
def entry_time() -> datetime:
    """Entry time for tests."""
    return datetime.now(UTC) - timedelta(hours=2)


class TestWhatIfScenario:
    """Tests for WhatIfScenario dataclass."""

    def test_create_scenario(self) -> None:
        """Test creating a scenario."""
        scenario = WhatIfScenario(
            price=Decimal("1.20"),
            pnl_pct=Decimal("20"),
            pnl_sol=Decimal("2.0"),
            triggered_rules=["take_profit"],
            action="partial_exit",
            exit_pct=Decimal("50"),
        )

        assert scenario.price == Decimal("1.20")
        assert scenario.action == "partial_exit"
        assert "take_profit" in scenario.triggered_rules


class TestWhatIfCalculator:
    """Tests for WhatIfCalculator."""

    def test_analyze_basic(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test basic analysis."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.05"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
            position_id="test-pos",
        )

        assert analysis.position_id == "test-pos"
        assert analysis.entry_price == Decimal("1.0")
        assert analysis.current_price == Decimal("1.05")
        assert analysis.strategy_name == "Test Strategy"
        assert len(analysis.scenarios) > 0

    def test_key_levels_calculation(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test key price level calculation."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        # Stop loss at -10% of 1.0 = 0.90
        assert analysis.stop_loss_price == Decimal("0.90")

        # First TP at +20% of 1.0 = 1.20
        assert analysis.first_tp_price == Decimal("1.20")

        # Breakeven at entry price
        assert analysis.breakeven_price == Decimal("1.0")

    def test_current_pnl_calculation(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test current P&L calculation."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.10"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        # Expect gain of 10 percent
        assert analysis.current_pnl_pct == Decimal("10")
        # Expect profit of 1 SOL (10 SOL position times 10 percent)
        assert analysis.current_pnl_sol == Decimal("1.0")

    def test_generate_price_levels(
        self, calculator: WhatIfCalculator
    ) -> None:
        """Test price level generation."""
        levels = calculator._generate_price_levels(
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.05"),
            stop_loss_price=Decimal("0.90"),
            first_tp_price=Decimal("1.20"),
        )

        # Should include entry, current, SL, TP
        assert Decimal("1.0") in levels
        assert Decimal("1.05") in levels
        assert Decimal("0.90") in levels
        assert Decimal("1.20") in levels

        # Should include percentage steps
        assert Decimal("0.80") in levels  # -20%
        assert Decimal("1.50") in levels  # +50%
        assert Decimal("2.0") in levels  # +100%

    def test_calculate_scenario_hold(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Test scenario calculation when holding."""
        scenario = calculator._calculate_scenario(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            test_price=Decimal("1.05"),  # +5%, no triggers
            position_size_sol=Decimal("10"),
        )

        assert scenario.action == "hold"
        assert scenario.exit_pct == Decimal("0")
        assert len(scenario.triggered_rules) == 0

    def test_calculate_scenario_partial_exit(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Test scenario calculation for partial exit."""
        scenario = calculator._calculate_scenario(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            test_price=Decimal("1.20"),  # +20%, first TP
            position_size_sol=Decimal("10"),
        )

        assert scenario.action == "partial_exit"
        assert scenario.exit_pct == Decimal("50")
        assert "take_profit" in scenario.triggered_rules

    def test_calculate_scenario_full_exit(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Test scenario calculation for full exit."""
        scenario = calculator._calculate_scenario(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            test_price=Decimal("0.89"),  # -11%, stop loss
            position_size_sol=Decimal("10"),
        )

        assert scenario.action == "full_exit"
        assert scenario.exit_pct == Decimal("100")
        assert "stop_loss" in scenario.triggered_rules

    def test_find_breakeven_scenarios(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test finding breakeven scenarios."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        breakeven_scenarios = calculator.find_breakeven_scenarios(analysis)

        # Should find scenarios within 1% of breakeven
        assert len(breakeven_scenarios) > 0
        for s in breakeven_scenarios:
            assert abs(s.pnl_pct) < Decimal("1.0")

    def test_find_exit_scenarios(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test finding exit scenarios."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        exit_scenarios = calculator.find_exit_scenarios(analysis)

        # Should find scenarios that trigger exits
        assert len(exit_scenarios) > 0
        for s in exit_scenarios:
            assert s.action in ["partial_exit", "full_exit"]
            assert s.exit_pct > Decimal("0")

    def test_calculate_risk_reward(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test risk/reward calculation."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        rr = calculator.calculate_risk_reward(analysis)

        # Risk = 10% (stop loss)
        assert rr["risk_pct"] == Decimal("10")

        # Reward = 20% (first TP)
        assert rr["reward_pct"] == Decimal("20")

        # RR ratio = 20/10 = 2.0
        assert rr["risk_reward_ratio"] == Decimal("2")

    def test_calculate_risk_reward_no_levels(
        self,
        calculator: WhatIfCalculator,
        entry_time: datetime,
    ) -> None:
        """Test risk/reward with no defined levels."""
        # Strategy with no SL or TP
        no_sl_strategy = ExitStrategy(
            id="no-sl",
            name="No SL",
            description="No stop loss",
            version=1,
            status="active",
            rules=[],
            max_hold_hours=24,
            stagnation_hours=6,
            stagnation_threshold_pct=Decimal("2.0"),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        analysis = calculator.analyze(
            strategy=no_sl_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        rr = calculator.calculate_risk_reward(analysis)

        assert rr["risk_pct"] == Decimal("0")
        assert rr["reward_pct"] == Decimal("0")
        assert rr["risk_reward_ratio"] == Decimal("0")

    def test_analysis_with_losing_position(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
        entry_time: datetime,
    ) -> None:
        """Test analysis on a position that is currently losing."""
        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("0.92"),  # -8%
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        # Current should show negative
        assert analysis.current_pnl_pct == Decimal("-8")
        assert analysis.current_pnl_sol == Decimal("-0.8")

        # Stop loss should be close
        distance_to_sl = (
            (analysis.current_price - analysis.stop_loss_price)
            / analysis.current_price
            * 100
        )
        # 0.92 to 0.90 is about 2%
        assert distance_to_sl > Decimal("0")
        assert distance_to_sl < Decimal("5")

    def test_time_held_calculation(
        self,
        calculator: WhatIfCalculator,
        sample_strategy: ExitStrategy,
    ) -> None:
        """Test time held calculation."""
        # 5 hours ago
        entry_time = datetime.now(UTC) - timedelta(hours=5)

        analysis = calculator.analyze(
            strategy=sample_strategy,
            entry_price=Decimal("1.0"),
            current_price=Decimal("1.0"),
            position_size_sol=Decimal("10"),
            entry_time=entry_time,
        )

        # Should be approximately 5 hours
        assert analysis.time_held_hours >= Decimal("4.9")
        assert analysis.time_held_hours <= Decimal("5.1")
