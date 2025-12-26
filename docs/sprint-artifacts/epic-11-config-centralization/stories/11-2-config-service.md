# Story 11.2: ConfigService with Cache and Hot-Reload

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 5
- **Depends on**: Story 11-1 (Schema Migration)

## User Story

**As a** developer,
**I want** un service centralisé pour accéder aux configurations,
**So that** je n'ai plus de constantes hardcodées et les changements sont hot-reloadés.

## Acceptance Criteria

### AC 1: Get Configuration Value
**Given** le ConfigService est initialisé
**When** j'appelle `config.get("trading.score_threshold")`
**Then** je reçois la valeur de la config `active`
**And** le format est `{table}.{field}`

### AC 2: TTL Cache
**Given** une valeur est récupérée
**When** je rappelle la même clé dans les 60 secondes
**Then** la valeur cachée est retournée
**And** aucun appel DB n'est fait

### AC 3: Hot-Reload
**Given** une config est modifiée en DB
**When** le cache expire (60s)
**Then** la nouvelle valeur est automatiquement chargée
**And** aucun restart n'est nécessaire

### AC 4: Fallback on Error
**Given** la DB est indisponible
**When** j'appelle `config.get()`
**Then** je reçois la valeur default hardcodée (fallback)
**And** un warning est loggé

### AC 5: Get Full Block
**Given** je veux tous les paramètres d'un domaine
**When** j'appelle `config.get_block("trading")`
**Then** je reçois un dict complet du trading_config actif
**And** le résultat est typé via Pydantic

### AC 6: Force Refresh
**Given** une modification urgente est faite
**When** j'appelle `config.refresh("trading")`
**Then** le cache est invalidé immédiatement
**And** la prochaine lecture fetch depuis la DB

## Technical Specifications

### ConfigService

**src/walltrack/services/config/config_service.py:**
```python
"""Centralized configuration service with caching and hot-reload."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Optional, TypeVar, Type
from pydantic import BaseModel

import structlog
from cachetools import TTLCache

logger = structlog.get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class TradingConfig(BaseModel):
    """Trading configuration model."""
    base_position_pct: Decimal
    max_position_sol: Decimal
    min_position_sol: Decimal
    high_conviction_multiplier: Decimal
    sizing_mode: str
    risk_per_trade_pct: Decimal
    max_concurrent_positions: int
    daily_loss_limit_pct: Decimal
    daily_loss_limit_enabled: bool
    max_concentration_token_pct: Decimal
    max_concentration_cluster_pct: Decimal
    max_positions_per_cluster: int
    drawdown_reduction_tiers: list[dict]
    score_threshold: Decimal
    high_conviction_threshold: Decimal
    max_slippage_entry_bps: int
    max_slippage_exit_bps: int


class ScoringConfig(BaseModel):
    """Scoring configuration model."""
    wallet_score_weight: Decimal
    timing_score_weight: Decimal
    market_score_weight: Decimal
    cluster_score_weight: Decimal
    wallet_win_rate_weight: Decimal
    wallet_avg_pnl_weight: Decimal
    wallet_consistency_weight: Decimal
    timing_decay_hours: int
    timing_freshness_bonus: Decimal
    market_liquidity_threshold: Decimal
    market_volume_threshold: Decimal
    cluster_min_sync_ratio: Decimal
    cluster_amplification_factor: Decimal


class DiscoveryConfig(BaseModel):
    """Discovery configuration model."""
    run_interval_minutes: int
    max_wallets_per_run: int
    min_wallet_age_days: int
    min_win_rate: Decimal
    min_trades: int
    min_avg_pnl_pct: Decimal
    max_avg_loss_pct: Decimal
    decay_lookback_days: int
    decay_threshold: Decimal
    decay_check_interval_hours: int
    pump_volume_spike_threshold: Decimal
    pump_price_spike_threshold: Decimal


class ClusterConfig(BaseModel):
    """Cluster configuration model."""
    min_cluster_size: int
    max_cluster_size: int
    similarity_threshold: Decimal
    sync_time_window_minutes: int
    sync_token_overlap_threshold: Decimal
    leader_min_followers: int
    leader_time_advantage_minutes: int
    enable_cluster_amplification: bool
    amplification_max_boost: Decimal


class RiskConfig(BaseModel):
    """Risk configuration model."""
    circuit_breaker_enabled: bool
    circuit_breaker_loss_threshold: Decimal
    circuit_breaker_cooldown_minutes: int
    max_drawdown_pct: Decimal
    drawdown_lookback_days: int
    max_order_attempts: int
    retry_delay_base_seconds: int
    retry_delay_multiplier: Decimal
    emergency_exit_threshold_pct: Decimal


class ExitConfig(BaseModel):
    """Exit configuration model."""
    default_strategy_standard_id: Optional[str]
    default_strategy_high_conviction_id: Optional[str]
    default_max_hold_hours: int
    stagnation_hours: int
    stagnation_threshold_pct: Decimal
    price_collection_interval_seconds: int
    price_history_retention_days: int


class ApiConfig(BaseModel):
    """API configuration model."""
    dexscreener_requests_per_minute: int
    birdeye_requests_per_minute: int
    jupiter_requests_per_minute: int
    helius_requests_per_minute: int
    api_timeout_seconds: int
    rpc_timeout_seconds: int
    api_retry_count: int
    api_retry_backoff_seconds: int
    price_cache_ttl_seconds: int
    token_info_cache_ttl_seconds: int


# Mapping table names to Pydantic models
CONFIG_MODELS: dict[str, Type[BaseModel]] = {
    "trading": TradingConfig,
    "scoring": ScoringConfig,
    "discovery": DiscoveryConfig,
    "cluster": ClusterConfig,
    "risk": RiskConfig,
    "exit": ExitConfig,
    "api": ApiConfig,
}

# Hardcoded fallback defaults (used when DB unavailable)
FALLBACK_DEFAULTS: dict[str, dict] = {
    "trading": {
        "base_position_pct": Decimal("2.0"),
        "max_position_sol": Decimal("1.0"),
        "min_position_sol": Decimal("0.05"),
        "score_threshold": Decimal("0.70"),
        "high_conviction_threshold": Decimal("0.85"),
        "max_concurrent_positions": 5,
        "sizing_mode": "risk_based",
        "risk_per_trade_pct": Decimal("1.0"),
        "daily_loss_limit_pct": Decimal("5.0"),
        "daily_loss_limit_enabled": True,
        "max_concentration_token_pct": Decimal("25.0"),
        "max_concentration_cluster_pct": Decimal("50.0"),
        "max_positions_per_cluster": 3,
        "high_conviction_multiplier": Decimal("1.5"),
        "drawdown_reduction_tiers": [
            {"threshold_pct": 5, "size_reduction_pct": 0},
            {"threshold_pct": 10, "size_reduction_pct": 25},
            {"threshold_pct": 15, "size_reduction_pct": 50},
            {"threshold_pct": 20, "size_reduction_pct": 100},
        ],
        "max_slippage_entry_bps": 100,
        "max_slippage_exit_bps": 150,
    },
    "scoring": {
        "wallet_score_weight": Decimal("0.30"),
        "timing_score_weight": Decimal("0.25"),
        "market_score_weight": Decimal("0.20"),
        "cluster_score_weight": Decimal("0.25"),
        "wallet_win_rate_weight": Decimal("0.40"),
        "wallet_avg_pnl_weight": Decimal("0.30"),
        "wallet_consistency_weight": Decimal("0.30"),
        "timing_decay_hours": 4,
        "timing_freshness_bonus": Decimal("0.2"),
        "market_liquidity_threshold": Decimal("10000"),
        "market_volume_threshold": Decimal("5000"),
        "cluster_min_sync_ratio": Decimal("0.3"),
        "cluster_amplification_factor": Decimal("1.2"),
    },
    # Add other tables...
}


class ConfigService:
    """
    Centralized configuration service.

    Provides cached access to database configurations
    with automatic hot-reload and fallback to defaults.
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 60,
        cache_max_size: int = 500,
    ):
        self._cache: TTLCache = TTLCache(
            maxsize=cache_max_size,
            ttl=cache_ttl_seconds
        )
        self._block_cache: TTLCache = TTLCache(
            maxsize=50,
            ttl=cache_ttl_seconds
        )
        self._cache_ttl = cache_ttl_seconds
        self._initialized = False

    async def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value by key.

        Key format: "{table}.{field}" e.g., "trading.score_threshold"

        Args:
            key: Configuration key in format "table.field"
            default: Default value if not found

        Returns:
            Configuration value or default
        """
        # Check cache first
        if key in self._cache:
            return self._cache[key]

        # Parse key
        parts = key.split(".", 1)
        if len(parts) != 2:
            logger.warning("invalid_config_key", key=key)
            return default

        table, field = parts

        try:
            # Get full block (which will be cached)
            block = await self.get_block(table)

            if block is None:
                return self._get_fallback_value(table, field, default)

            # Get field value
            value = getattr(block, field, None)
            if value is None:
                value = self._get_fallback_value(table, field, default)

            # Cache the individual value
            self._cache[key] = value

            return value

        except Exception as e:
            logger.warning(
                "config_fetch_error",
                key=key,
                error=str(e)
            )
            return self._get_fallback_value(table, field, default)

    async def get_block(self, table: str) -> Optional[BaseModel]:
        """
        Get full configuration block for a table.

        Args:
            table: Table name (e.g., "trading", "scoring")

        Returns:
            Pydantic model with all config values or None
        """
        cache_key = f"block:{table}"

        # Check cache
        if cache_key in self._block_cache:
            return self._block_cache[cache_key]

        model_class = CONFIG_MODELS.get(table)
        if model_class is None:
            logger.warning("unknown_config_table", table=table)
            return None

        try:
            from walltrack.data.supabase.client import get_supabase_client

            client = await get_supabase_client()
            db_table = f"{table}_config"

            result = await client.table(db_table) \
                .select("*") \
                .eq("status", "active") \
                .single() \
                .execute()

            if not result.data:
                logger.warning("no_active_config", table=table)
                return self._get_fallback_block(table)

            # Convert to Pydantic model
            block = model_class(**result.data)

            # Cache it
            self._block_cache[cache_key] = block

            logger.debug("config_block_loaded", table=table)
            return block

        except Exception as e:
            logger.error(
                "config_block_fetch_error",
                table=table,
                error=str(e)
            )
            return self._get_fallback_block(table)

    async def get_trading_config(self) -> TradingConfig:
        """Get trading configuration (typed helper)."""
        block = await self.get_block("trading")
        if block is None:
            return TradingConfig(**FALLBACK_DEFAULTS["trading"])
        return block

    async def get_scoring_config(self) -> ScoringConfig:
        """Get scoring configuration (typed helper)."""
        block = await self.get_block("scoring")
        if block is None:
            return ScoringConfig(**FALLBACK_DEFAULTS["scoring"])
        return block

    async def get_risk_config(self) -> RiskConfig:
        """Get risk configuration (typed helper)."""
        block = await self.get_block("risk")
        if block is None:
            # Create minimal fallback
            return RiskConfig(
                circuit_breaker_enabled=True,
                circuit_breaker_loss_threshold=Decimal("10.0"),
                circuit_breaker_cooldown_minutes=60,
                max_drawdown_pct=Decimal("20.0"),
                drawdown_lookback_days=30,
                max_order_attempts=3,
                retry_delay_base_seconds=5,
                retry_delay_multiplier=Decimal("3.0"),
                emergency_exit_threshold_pct=Decimal("50.0"),
            )
        return block

    async def refresh(self, table: Optional[str] = None) -> None:
        """
        Force refresh of cached configuration.

        Args:
            table: Specific table to refresh, or None for all
        """
        if table:
            # Clear specific table cache
            cache_key = f"block:{table}"
            self._block_cache.pop(cache_key, None)

            # Clear individual keys for this table
            keys_to_remove = [k for k in self._cache if k.startswith(f"{table}.")]
            for key in keys_to_remove:
                self._cache.pop(key, None)

            logger.info("config_refreshed", table=table)
        else:
            # Clear all caches
            self._cache.clear()
            self._block_cache.clear()
            logger.info("all_configs_refreshed")

    def _get_fallback_value(
        self,
        table: str,
        field: str,
        default: Any
    ) -> Any:
        """Get fallback value from hardcoded defaults."""
        fallbacks = FALLBACK_DEFAULTS.get(table, {})
        return fallbacks.get(field, default)

    def _get_fallback_block(self, table: str) -> Optional[BaseModel]:
        """Get fallback block from hardcoded defaults."""
        model_class = CONFIG_MODELS.get(table)
        fallbacks = FALLBACK_DEFAULTS.get(table)

        if model_class and fallbacks:
            try:
                return model_class(**fallbacks)
            except Exception as e:
                logger.error("fallback_block_error", table=table, error=str(e))

        return None


# Singleton
_config_service: Optional[ConfigService] = None


async def get_config_service() -> ConfigService:
    """Get or create config service singleton."""
    global _config_service

    if _config_service is None:
        _config_service = ConfigService()

    return _config_service
```

## Implementation Tasks

- [ ] Create ConfigService class
- [ ] Implement TTL cache with cachetools
- [ ] Create Pydantic models for each config table
- [ ] Implement get() with key parsing
- [ ] Implement get_block() for full table fetch
- [ ] Add fallback defaults for all tables
- [ ] Implement refresh() for cache invalidation
- [ ] Add typed helper methods (get_trading_config, etc.)
- [ ] Create singleton pattern
- [ ] Write unit tests with mocked DB
- [ ] Write integration tests

## Definition of Done

- [ ] All config tables accessible via service
- [ ] Cache working with 60s TTL
- [ ] Fallback to defaults when DB unavailable
- [ ] Force refresh works
- [ ] Pydantic models validate data
- [ ] Full test coverage

## File List

### New Files
- `src/walltrack/services/config/__init__.py` - Package init
- `src/walltrack/services/config/config_service.py` - Main service
- `src/walltrack/services/config/models.py` - Pydantic config models
- `tests/unit/services/config/test_config_service.py` - Tests

### Modified Files
- `src/walltrack/services/__init__.py` - Export config module
