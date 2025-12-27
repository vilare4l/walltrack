"""What-if analysis for exit strategies on open positions."""

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from walltrack.services.exit.exit_strategy_service import ExitStrategy


@dataclass
class WhatIfScenario:
    """Projected outcome at a given price."""

    price: Decimal
    pnl_pct: Decimal
    pnl_sol: Decimal
    triggered_rules: list[str]
    action: str  # "hold", "partial_exit", "full_exit"
    exit_pct: Decimal


@dataclass
class WhatIfAnalysis:
    """Complete what-if analysis for a position."""

    position_id: str
    entry_price: Decimal
    current_price: Decimal
    position_size_sol: Decimal
    strategy_name: str

    # Key levels
    breakeven_price: Decimal
    stop_loss_price: Decimal | None
    first_tp_price: Decimal | None

    # Scenarios
    scenarios: list[WhatIfScenario]

    # Current state
    current_pnl_pct: Decimal
    current_pnl_sol: Decimal
    time_held_hours: Decimal


class WhatIfCalculator:
    """Calculate what-if scenarios for open positions."""

    def analyze(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        current_price: Decimal,
        position_size_sol: Decimal,
        entry_time: datetime,
        position_id: str = "current",
    ) -> WhatIfAnalysis:
        """Analyze what-if scenarios for a position.

        Generates scenarios at key price levels.
        """
        # Calculate key levels
        stop_loss_price: Decimal | None = None
        first_tp_price: Decimal | None = None

        for rule in strategy.rules:
            if rule.rule_type == "stop_loss" and rule.trigger_pct:
                stop_loss_price = entry_price * (1 + rule.trigger_pct / 100)
            elif (
                rule.rule_type == "take_profit"
                and rule.trigger_pct
                and first_tp_price is None
            ):
                first_tp_price = entry_price * (1 + rule.trigger_pct / 100)

        # Generate scenarios at different price points
        scenarios: list[WhatIfScenario] = []

        # Key price levels to analyze
        price_levels = self._generate_price_levels(
            entry_price=entry_price,
            current_price=current_price,
            stop_loss_price=stop_loss_price,
            first_tp_price=first_tp_price,
        )

        for price in price_levels:
            scenario = self._calculate_scenario(
                strategy=strategy,
                entry_price=entry_price,
                test_price=price,
                position_size_sol=position_size_sol,
            )
            scenarios.append(scenario)

        # Current state
        current_pnl_pct = ((current_price - entry_price) / entry_price) * 100
        current_pnl_sol = position_size_sol * (current_pnl_pct / 100)
        time_held = Decimal(
            str((datetime.now(UTC) - entry_time).total_seconds() / 3600)
        )

        return WhatIfAnalysis(
            position_id=position_id,
            entry_price=entry_price,
            current_price=current_price,
            position_size_sol=position_size_sol,
            strategy_name=strategy.name,
            breakeven_price=entry_price,
            stop_loss_price=stop_loss_price,
            first_tp_price=first_tp_price,
            scenarios=scenarios,
            current_pnl_pct=current_pnl_pct,
            current_pnl_sol=current_pnl_sol,
            time_held_hours=time_held,
        )

    def _generate_price_levels(
        self,
        entry_price: Decimal,
        current_price: Decimal,
        stop_loss_price: Decimal | None,
        first_tp_price: Decimal | None,
    ) -> list[Decimal]:
        """Generate price levels to analyze."""
        levels: set[Decimal] = set()

        # Add entry and current
        levels.add(entry_price)
        levels.add(current_price)

        # Add stop loss and TP if defined
        if stop_loss_price:
            levels.add(stop_loss_price)
        if first_tp_price:
            levels.add(first_tp_price)

        # Add percentage steps
        for pct in [-20, -15, -10, -5, 0, 5, 10, 15, 20, 30, 50, 100]:
            price = entry_price * (1 + Decimal(pct) / 100)
            levels.add(price.quantize(Decimal("0.000001")))

        return sorted(levels)

    def _calculate_scenario(
        self,
        strategy: ExitStrategy,
        entry_price: Decimal,
        test_price: Decimal,
        position_size_sol: Decimal,
    ) -> WhatIfScenario:
        """Calculate scenario at a specific price."""
        pnl_pct = ((test_price - entry_price) / entry_price) * 100
        pnl_sol = position_size_sol * (pnl_pct / 100)

        # Check which rules would trigger
        triggered_rules: list[str] = []
        total_exit_pct = Decimal("0")

        for rule in strategy.rules:
            if not rule.enabled:
                continue

            triggered = False

            if rule.rule_type == "take_profit" and rule.trigger_pct:
                triggered = pnl_pct >= rule.trigger_pct

            elif rule.rule_type == "stop_loss" and rule.trigger_pct:
                triggered = pnl_pct <= rule.trigger_pct

            if triggered:
                triggered_rules.append(rule.rule_type)
                total_exit_pct = min(total_exit_pct + rule.exit_pct, Decimal("100"))

        # Determine action
        if total_exit_pct >= 100:
            action = "full_exit"
        elif total_exit_pct > 0:
            action = "partial_exit"
        else:
            action = "hold"

        return WhatIfScenario(
            price=test_price,
            pnl_pct=pnl_pct,
            pnl_sol=pnl_sol,
            triggered_rules=triggered_rules,
            action=action,
            exit_pct=total_exit_pct,
        )

    def find_breakeven_scenarios(
        self,
        analysis: WhatIfAnalysis,
    ) -> list[WhatIfScenario]:
        """Find scenarios near breakeven point."""
        return [
            s
            for s in analysis.scenarios
            if abs(s.pnl_pct) < Decimal("1.0")  # Within 1% of breakeven
        ]

    def find_exit_scenarios(
        self,
        analysis: WhatIfAnalysis,
    ) -> list[WhatIfScenario]:
        """Find scenarios that would trigger an exit."""
        return [s for s in analysis.scenarios if s.action != "hold"]

    def calculate_risk_reward(
        self,
        analysis: WhatIfAnalysis,
    ) -> dict[str, Decimal]:
        """Calculate risk/reward metrics from scenarios."""
        if not analysis.stop_loss_price or not analysis.first_tp_price:
            return {
                "risk_pct": Decimal("0"),
                "reward_pct": Decimal("0"),
                "risk_reward_ratio": Decimal("0"),
            }

        risk_pct = (
            (analysis.entry_price - analysis.stop_loss_price)
            / analysis.entry_price
            * 100
        )
        reward_pct = (
            (analysis.first_tp_price - analysis.entry_price)
            / analysis.entry_price
            * 100
        )

        risk_reward_ratio = (
            abs(reward_pct / risk_pct) if risk_pct != 0 else Decimal("0")
        )

        return {
            "risk_pct": abs(risk_pct),
            "reward_pct": reward_pct,
            "risk_reward_ratio": risk_reward_ratio,
        }
