"""Pydantic models for centralized configuration.

These models match the database schema from V8__config_centralization.sql
with lifecycle columns added by V13__config_lifecycle.sql.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class ConfigBase(BaseModel):
    """Base model for all config tables with lifecycle columns."""

    id: int
    name: str
    status: str  # 'default', 'draft', 'active', 'archived'
    version: int = 1
    description: str | None = None
    created_at: datetime | None = None
    created_by: str | None = None
    updated_at: datetime | None = None
    updated_by: str | None = None

    class Config:
        from_attributes = True


class TradingConfig(ConfigBase):
    """Trading configuration model matching trading_config table."""

    # Position Sizing
    base_position_size_pct: Decimal = Field(default=Decimal("2.0"))
    min_position_sol: Decimal = Field(default=Decimal("0.01"))
    max_position_sol: Decimal = Field(default=Decimal("1.0"))
    max_concurrent_positions: int = Field(default=5)

    # Thresholds
    score_threshold: Decimal = Field(default=Decimal("0.70"))
    high_conviction_threshold: Decimal = Field(default=Decimal("0.85"))
    high_conviction_multiplier: Decimal = Field(default=Decimal("1.5"))

    # Token Filters
    min_token_age_seconds: int = Field(default=300)
    max_token_age_hours: int = Field(default=24)
    min_liquidity_usd: Decimal = Field(default=Decimal("10000.0"))
    max_market_cap_usd: Decimal = Field(default=Decimal("10000000.0"))

    # Timing
    max_position_hold_hours: int = Field(default=24)
    max_daily_trades: int = Field(default=20)


class ScoringConfig(ConfigBase):
    """Scoring configuration model matching scoring_config table."""

    # Main Weights
    wallet_weight: Decimal = Field(default=Decimal("0.30"))
    cluster_weight: Decimal = Field(default=Decimal("0.25"))
    token_weight: Decimal = Field(default=Decimal("0.25"))
    context_weight: Decimal = Field(default=Decimal("0.20"))

    # Wallet Score Sub-Weights
    wallet_win_rate_weight: Decimal = Field(default=Decimal("0.35"))
    wallet_pnl_weight: Decimal = Field(default=Decimal("0.25"))
    wallet_timing_weight: Decimal = Field(default=Decimal("0.25"))
    wallet_consistency_weight: Decimal = Field(default=Decimal("0.15"))
    wallet_leader_bonus: Decimal = Field(default=Decimal("0.15"))
    wallet_max_decay_penalty: Decimal = Field(default=Decimal("0.30"))

    # Token Score Sub-Weights
    token_liquidity_weight: Decimal = Field(default=Decimal("0.30"))
    token_mcap_weight: Decimal = Field(default=Decimal("0.25"))
    token_holder_dist_weight: Decimal = Field(default=Decimal("0.20"))
    token_volume_weight: Decimal = Field(default=Decimal("0.25"))

    # Token Thresholds
    token_min_liquidity_usd: Decimal = Field(default=Decimal("1000.0"))
    token_optimal_liquidity_usd: Decimal = Field(default=Decimal("50000.0"))
    token_min_mcap_usd: Decimal = Field(default=Decimal("10000.0"))
    token_optimal_mcap_usd: Decimal = Field(default=Decimal("500000.0"))

    # Context Score
    peak_trading_hours_utc: list[int] = Field(default=[14, 15, 16, 17, 18])
    high_volatility_threshold: Decimal = Field(default=Decimal("0.10"))

    # Cluster Score
    solo_signal_base: Decimal = Field(default=Decimal("0.50"))
    min_participation_rate: Decimal = Field(default=Decimal("0.30"))

    # New Token Penalty
    new_token_penalty_minutes: int = Field(default=5)
    max_new_token_penalty: Decimal = Field(default=Decimal("0.30"))


class DiscoveryConfig(ConfigBase):
    """Discovery configuration model matching discovery_config table."""

    # Schedule
    discovery_cron: str = Field(default="0 */6 * * *")

    # Pump Token Criteria
    pump_min_gain_pct: Decimal = Field(default=Decimal("100.0"))
    pump_min_liquidity_usd: Decimal = Field(default=Decimal("10000.0"))
    pump_max_market_cap_usd: Decimal = Field(default=Decimal("5000000.0"))
    pump_min_age_minutes: int = Field(default=30)
    pump_max_age_hours: int = Field(default=24)
    pump_max_tokens_per_run: int = Field(default=20)

    # Early Buyer Filtering
    buyer_min_amount_sol: Decimal = Field(default=Decimal("0.1"))
    buyer_max_amount_sol: Decimal = Field(default=Decimal("10.0"))
    buyer_max_per_token: int = Field(default=100)

    # Wallet Profiling Thresholds
    profile_min_total_trades: int = Field(default=10)
    profile_min_win_rate_pct: Decimal = Field(default=Decimal("50.0"))
    profile_min_pnl_sol: Decimal = Field(default=Decimal("1.0"))
    profile_lookback_days: int = Field(default=90)

    # Decay Detection
    decay_rolling_window: int = Field(default=20)
    decay_win_rate_threshold: Decimal = Field(default=Decimal("40.0"))
    decay_recovery_threshold: Decimal = Field(default=Decimal("50.0"))
    decay_consecutive_loss_threshold: int = Field(default=3)
    decay_score_downgrade_factor: Decimal = Field(default=Decimal("0.80"))


class ClusterConfig(ConfigBase):
    """Cluster configuration model matching cluster_config table."""

    # Cluster Detection
    min_cluster_size: int = Field(default=3)
    min_cluster_strength: Decimal = Field(default=Decimal("0.30"))
    min_cluster_edges: int = Field(default=2)
    max_analysis_depth: int = Field(default=3)

    # Sync Buy Detection
    sync_buy_window_minutes: int = Field(default=5)
    sync_buy_lookback_days: int = Field(default=30)

    # Co-occurrence Analysis
    cooccurrence_min_tokens: int = Field(default=3)
    cooccurrence_time_window_hours: int = Field(default=24)
    cooccurrence_min_jaccard: Decimal = Field(default=Decimal("0.20"))
    cooccurrence_min_count: int = Field(default=2)

    # Funding Analysis
    funding_min_amount_sol: Decimal = Field(default=Decimal("0.1"))
    funding_strength_cap_sol: Decimal = Field(default=Decimal("10.0"))
    funding_max_depth: int = Field(default=3)

    # Leader Detection
    leader_min_score: Decimal = Field(default=Decimal("0.30"))
    leader_funding_weight: Decimal = Field(default=Decimal("0.30"))
    leader_timing_weight: Decimal = Field(default=Decimal("0.25"))
    leader_centrality_weight: Decimal = Field(default=Decimal("0.25"))
    leader_performance_weight: Decimal = Field(default=Decimal("0.20"))
    leader_pnl_cap_usd: Decimal = Field(default=Decimal("10000.0"))

    # Signal Amplification
    amplification_window_seconds: int = Field(default=600)
    min_active_members_for_amp: int = Field(default=2)
    base_amplification_factor: Decimal = Field(default=Decimal("1.20"))
    max_amplification_factor: Decimal = Field(default=Decimal("1.80"))
    min_amplification_multiplier: Decimal = Field(default=Decimal("1.00"))
    max_amplification_multiplier: Decimal = Field(default=Decimal("3.00"))
    cohesion_threshold: Decimal = Field(default=Decimal("0.30"))


class RiskConfig(ConfigBase):
    """Risk configuration model matching risk_config table."""

    # Risk-Based Position Sizing
    risk_per_trade_pct: Decimal = Field(default=Decimal("1.0"))
    sizing_mode: str = Field(default="risk_based")

    # Daily Loss Limit
    daily_loss_limit_pct: Decimal = Field(default=Decimal("5.0"))
    daily_loss_limit_enabled: bool = Field(default=True)

    # Concentration Limits
    max_concentration_token_pct: Decimal = Field(default=Decimal("25.0"))
    max_concentration_cluster_pct: Decimal = Field(default=Decimal("50.0"))
    max_positions_per_cluster: int = Field(default=3)

    # Capital Protection (Drawdown)
    max_drawdown_pct: Decimal = Field(default=Decimal("20.0"))
    drawdown_warning_pct: Decimal = Field(default=Decimal("15.0"))

    # Drawdown-Based Size Reduction Tiers
    drawdown_reduction_tiers: list[dict] = Field(
        default=[
            {"threshold_pct": 5, "size_reduction_pct": 0},
            {"threshold_pct": 10, "size_reduction_pct": 25},
            {"threshold_pct": 15, "size_reduction_pct": 50},
            {"threshold_pct": 20, "size_reduction_pct": 100},
        ]
    )

    # Win Rate Circuit Breaker
    win_rate_threshold_pct: Decimal = Field(default=Decimal("40.0"))
    win_rate_window_size: int = Field(default=50)
    win_rate_min_trades: int = Field(default=10)

    # Consecutive Loss Circuit Breaker
    consecutive_loss_threshold: int = Field(default=3)
    consecutive_loss_critical: int = Field(default=5)
    position_size_reduction_factor: Decimal = Field(default=Decimal("0.50"))

    # Circuit Breaker Behavior
    circuit_breaker_threshold: int = Field(default=5)
    circuit_breaker_cooldown_seconds: int = Field(default=30)
    auto_resume_enabled: bool = Field(default=True)

    # No Signal Warning
    no_signal_warning_hours: int = Field(default=48)


class ExitConfig(ConfigBase):
    """Exit configuration model matching exit_config table."""

    # Default Stop Loss
    default_stop_loss_pct: Decimal = Field(default=Decimal("50.0"))

    # Default Take Profits
    default_tp1_multiplier: Decimal = Field(default=Decimal("2.0"))
    default_tp1_sell_pct: Decimal = Field(default=Decimal("33.0"))
    default_tp2_multiplier: Decimal = Field(default=Decimal("3.0"))
    default_tp2_sell_pct: Decimal = Field(default=Decimal("33.0"))
    default_tp3_multiplier: Decimal = Field(default=Decimal("5.0"))
    default_tp3_sell_pct: Decimal = Field(default=Decimal("34.0"))

    # Trailing Stop Defaults
    trailing_stop_enabled: bool = Field(default=True)
    trailing_stop_activation_multiplier: Decimal = Field(default=Decimal("2.0"))
    trailing_stop_distance_pct: Decimal = Field(default=Decimal("30.0"))

    # Moonbag Defaults
    moonbag_enabled: bool = Field(default=False)
    moonbag_percent: Decimal = Field(default=Decimal("0.0"))
    moonbag_stop_loss_pct: Decimal = Field(default=Decimal("20.0"))

    # Time Limits
    default_max_hold_hours: int = Field(default=168)
    stagnation_exit_enabled: bool = Field(default=False)
    stagnation_threshold_pct: Decimal = Field(default=Decimal("5.0"))
    stagnation_hours: int = Field(default=6)

    # Default Strategy IDs for Conviction Tiers
    default_strategy_standard_id: str | None = Field(default=None)
    default_strategy_high_conviction_id: str | None = Field(default=None)


class ApiConfig(ConfigBase):
    """API configuration model matching api_config table."""

    # General API Settings
    default_timeout_seconds: int = Field(default=30)
    max_retries: int = Field(default=3)
    retry_base_delay_seconds: Decimal = Field(default=Decimal("1.0"))

    # DexScreener
    dexscreener_timeout_seconds: int = Field(default=5)
    dexscreener_rate_limit_per_minute: int = Field(default=300)

    # Birdeye
    birdeye_timeout_seconds: int = Field(default=5)
    birdeye_rate_limit_per_minute: int = Field(default=100)

    # Jupiter
    jupiter_quote_timeout_seconds: int = Field(default=5)
    jupiter_swap_timeout_seconds: int = Field(default=30)
    jupiter_confirmation_timeout_seconds: int = Field(default=60)
    jupiter_default_slippage_bps: int = Field(default=100)
    jupiter_max_slippage_bps: int = Field(default=500)
    jupiter_priority_fee_lamports: int = Field(default=10000)

    # Cache TTLs
    token_cache_ttl_seconds: int = Field(default=300)
    wallet_cache_ttl_seconds: int = Field(default=60)
    config_cache_ttl_seconds: int = Field(default=60)

    # Cache Sizes
    token_cache_max_size: int = Field(default=5000)
    wallet_cache_max_size: int = Field(default=10000)


# Mapping table names to Pydantic models
CONFIG_MODELS: dict[str, type[ConfigBase]] = {
    "trading": TradingConfig,
    "scoring": ScoringConfig,
    "discovery": DiscoveryConfig,
    "cluster": ClusterConfig,
    "risk": RiskConfig,
    "exit": ExitConfig,
    "api": ApiConfig,
}
