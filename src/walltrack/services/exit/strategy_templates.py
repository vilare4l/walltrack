"""Pre-defined exit strategy templates."""

from decimal import Decimal

from walltrack.services.exit.exit_strategy_service import (
    ExitStrategyCreate,
    ExitStrategyRule,
)


def get_standard_template() -> ExitStrategyCreate:
    """Standard balanced exit strategy."""
    return ExitStrategyCreate(
        name="Standard",
        description="Balanced exit with 15% TP, 10% SL",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-10"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("15"),
                exit_pct=Decimal("50"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("30"),
                exit_pct=Decimal("100"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="trailing_stop",
                trigger_pct=Decimal("-5"),
                exit_pct=Decimal("100"),
                priority=3,
                params={"activation_pct": 10},
            ),
        ],
        max_hold_hours=24,
        stagnation_hours=6,
        stagnation_threshold_pct=Decimal("2.0"),
    )


def get_aggressive_template() -> ExitStrategyCreate:
    """Aggressive high-conviction template."""
    return ExitStrategyCreate(
        name="High Conviction",
        description="Let winners run with wide stops",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-15"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("25"),
                exit_pct=Decimal("30"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("50"),
                exit_pct=Decimal("50"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("100"),
                exit_pct=Decimal("100"),
                priority=3,
            ),
            ExitStrategyRule(
                rule_type="trailing_stop",
                trigger_pct=Decimal("-8"),
                exit_pct=Decimal("100"),
                priority=4,
                params={"activation_pct": 20},
            ),
        ],
        max_hold_hours=48,
        stagnation_hours=12,
        stagnation_threshold_pct=Decimal("3.0"),
    )


def get_conservative_template() -> ExitStrategyCreate:
    """Conservative quick exit template."""
    return ExitStrategyCreate(
        name="Conservative",
        description="Tight stops, quick profits",
        rules=[
            ExitStrategyRule(
                rule_type="stop_loss",
                trigger_pct=Decimal("-5"),
                exit_pct=Decimal("100"),
                priority=0,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("10"),
                exit_pct=Decimal("75"),
                priority=1,
            ),
            ExitStrategyRule(
                rule_type="take_profit",
                trigger_pct=Decimal("20"),
                exit_pct=Decimal("100"),
                priority=2,
            ),
            ExitStrategyRule(
                rule_type="time_based",
                trigger_pct=None,
                exit_pct=Decimal("100"),
                priority=5,
                params={"max_hours": 12},
            ),
        ],
        max_hold_hours=12,
        stagnation_hours=4,
        stagnation_threshold_pct=Decimal("1.5"),
    )


TEMPLATES: dict[str, type] = {
    "standard": get_standard_template,
    "aggressive": get_aggressive_template,
    "conservative": get_conservative_template,
}


def get_template(name: str) -> ExitStrategyCreate:
    """Get a template by name."""
    factory = TEMPLATES.get(name.lower())
    if not factory:
        raise ValueError(f"Unknown template: {name}. Available: {list(TEMPLATES.keys())}")
    return factory()


def list_templates() -> list[str]:
    """List available template names."""
    return list(TEMPLATES.keys())
