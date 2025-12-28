"""Default exit strategy presets.

Five built-in strategies for different risk profiles:
- Conservative: Safe, early exits
- Balanced: Middle ground with trailing stop
- Moonbag Aggressive: High moonbag, ride to zero
- Quick Flip: Fast exit, scalping
- Diamond Hands: Long hold, high targets
"""

from walltrack.models.exit_strategy import (
    ExitStrategy,
    MoonbagConfig,
    StrategyPreset,
    TakeProfitLevel,
    TimeRulesConfig,
    TrailingStopConfig,
)

# ============================================================================
# CONSERVATIVE: Safe, early exits, no trailing, no moonbag
# Best for: Risk-averse operators, volatile markets
# ============================================================================
CONSERVATIVE_STRATEGY = ExitStrategy(
    id="preset-conservative",
    name="Conservative",
    description="Safe strategy: sell 50% at 2x, remaining 50% at 3x. No trailing or moonbag.",
    preset=StrategyPreset.CONSERVATIVE,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
    ],
    stop_loss=0.5,
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(max_hold_hours=72),
    moonbag=MoonbagConfig(percentage=0),
)


# ============================================================================
# BALANCED: Middle ground with trailing stop and small moonbag
# Best for: Most operators, default recommendation
# ============================================================================
BALANCED_STRATEGY = ExitStrategy(
    id="preset-balanced",
    name="Balanced",
    description="Balanced approach: 33% at 2x, 33% at 3x, trailing at 2x (30%), 34% moonbag.",
    preset=StrategyPreset.BALANCED,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=33),
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=50),
    ],
    stop_loss=0.5,
    trailing_stop=TrailingStopConfig(
        enabled=True,
        activation_multiplier=2.0,
        distance_percentage=30,
    ),
    time_rules=TimeRulesConfig(max_hold_hours=168),
    moonbag=MoonbagConfig(percentage=34, stop_loss=0.3),
)


# ============================================================================
# MOONBAG AGGRESSIVE: High moonbag, ride to zero strategy
# Best for: High conviction plays, meme coins with moonshot potential
# ============================================================================
MOONBAG_AGGRESSIVE_STRATEGY = ExitStrategy(
    id="preset-moonbag-aggressive",
    name="Moonbag Aggressive",
    description="High moonbag: 25% at 2x, 25% at 3x, 50% moonbag rides to zero.",
    preset=StrategyPreset.MOONBAG_AGGRESSIVE,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=2.0, sell_percentage=50),
        TakeProfitLevel(trigger_multiplier=3.0, sell_percentage=100),
    ],
    stop_loss=0.5,
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(),
    moonbag=MoonbagConfig(percentage=50, stop_loss=None),
)


# ============================================================================
# QUICK FLIP: Fast exit, take profit early
# Best for: Scalping, quick trades, high volume tokens
# ============================================================================
QUICK_FLIP_STRATEGY = ExitStrategy(
    id="preset-quick-flip",
    name="Quick Flip",
    description="Fast exit: sell 100% at 1.5x. Tight stop loss, no moonbag.",
    preset=StrategyPreset.QUICK_FLIP,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=1.5, sell_percentage=100),
    ],
    stop_loss=0.3,
    trailing_stop=TrailingStopConfig(enabled=False),
    time_rules=TimeRulesConfig(
        max_hold_hours=24,
        stagnation_exit_enabled=True,
        stagnation_threshold_pct=5,
        stagnation_hours=6,
    ),
    moonbag=MoonbagConfig(percentage=0),
)


# ============================================================================
# DIAMOND HANDS: Long hold, high targets
# Best for: Strong conviction, low volume positions
# ============================================================================
DIAMOND_HANDS_STRATEGY = ExitStrategy(
    id="preset-diamond-hands",
    name="Diamond Hands",
    description="Long hold: 25% at 5x, 25% at 10x, trailing at 3x (40%), 50% moonbag.",
    preset=StrategyPreset.DIAMOND_HANDS,
    is_default=True,
    take_profit_levels=[
        TakeProfitLevel(trigger_multiplier=5.0, sell_percentage=50),
        TakeProfitLevel(trigger_multiplier=10.0, sell_percentage=100),
    ],
    stop_loss=0.6,
    trailing_stop=TrailingStopConfig(
        enabled=True,
        activation_multiplier=3.0,
        distance_percentage=40,
    ),
    time_rules=TimeRulesConfig(),
    moonbag=MoonbagConfig(percentage=50, stop_loss=0.2),
)


# All default presets
DEFAULT_PRESETS: list[ExitStrategy] = [
    CONSERVATIVE_STRATEGY,
    BALANCED_STRATEGY,
    MOONBAG_AGGRESSIVE_STRATEGY,
    QUICK_FLIP_STRATEGY,
    DIAMOND_HANDS_STRATEGY,
]


def get_preset_by_name(name: str) -> ExitStrategy | None:
    """Get preset strategy by name (case-insensitive).

    Args:
        name: Strategy name to look up

    Returns:
        ExitStrategy if found, None otherwise
    """
    for preset in DEFAULT_PRESETS:
        if preset.name.lower() == name.lower():
            return preset
    return None


def get_preset_by_type(preset_type: StrategyPreset) -> ExitStrategy | None:
    """Get preset strategy by type.

    Args:
        preset_type: StrategyPreset enum value

    Returns:
        ExitStrategy if found, None otherwise
    """
    for preset in DEFAULT_PRESETS:
        if preset.preset == preset_type:
            return preset
    return None
