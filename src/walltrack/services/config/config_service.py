"""Centralized configuration service with caching and hot-reload.

Provides cached access to database configurations with automatic
hot-reload (via TTL expiry) and fallback to defaults when DB unavailable.
"""

from decimal import Decimal
from typing import Any, Optional

import structlog
from cachetools import TTLCache

from .models import (
    CONFIG_MODELS,
    ApiConfig,
    ClusterConfig,
    ConfigBase,
    DiscoveryConfig,
    ExitConfig,
    RiskConfig,
    ScoringConfig,
    TradingConfig,
)

logger = structlog.get_logger(__name__)


class ConfigService:
    """
    Centralized configuration service.

    Provides cached access to database configurations
    with automatic hot-reload and fallback to defaults.

    Usage:
        service = await get_config_service()

        # Get individual value
        threshold = await service.get("trading.score_threshold")

        # Get full config block
        trading_config = await service.get_trading_config()

        # Force refresh after changes
        await service.refresh("trading")
    """

    def __init__(
        self,
        cache_ttl_seconds: int = 60,
        cache_max_size: int = 500,
    ):
        """
        Initialize the config service.

        Args:
            cache_ttl_seconds: Time-to-live for cached values (default 60s)
            cache_max_size: Maximum number of individual values to cache
        """
        self._cache: TTLCache = TTLCache(
            maxsize=cache_max_size,
            ttl=cache_ttl_seconds
        )
        self._block_cache: TTLCache = TTLCache(
            maxsize=50,
            ttl=cache_ttl_seconds
        )
        self._cache_ttl = cache_ttl_seconds
        self._client = None

    async def _get_client(self):
        """Get Supabase client lazily."""
        if self._client is None:
            from walltrack.data.supabase.client import get_supabase_client
            self._client = await get_supabase_client()
        return self._client

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
                return default

            # Get field value
            value = getattr(block, field, None)
            if value is None:
                return default

            # Cache the individual value
            self._cache[key] = value

            return value

        except Exception as e:
            logger.warning(
                "config_fetch_error",
                key=key,
                error=str(e)
            )
            return default

    async def get_block(self, table: str) -> Optional[ConfigBase]:
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
            client = await self._get_client()
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

            logger.debug("config_block_loaded", table=table, version=block.version)
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
            return self._create_default_trading_config()
        return block  # type: ignore

    async def get_scoring_config(self) -> ScoringConfig:
        """Get scoring configuration (typed helper)."""
        block = await self.get_block("scoring")
        if block is None:
            return self._create_default_scoring_config()
        return block  # type: ignore

    async def get_discovery_config(self) -> DiscoveryConfig:
        """Get discovery configuration (typed helper)."""
        block = await self.get_block("discovery")
        if block is None:
            return self._create_default_discovery_config()
        return block  # type: ignore

    async def get_cluster_config(self) -> ClusterConfig:
        """Get cluster configuration (typed helper)."""
        block = await self.get_block("cluster")
        if block is None:
            return self._create_default_cluster_config()
        return block  # type: ignore

    async def get_risk_config(self) -> RiskConfig:
        """Get risk configuration (typed helper)."""
        block = await self.get_block("risk")
        if block is None:
            return self._create_default_risk_config()
        return block  # type: ignore

    async def get_exit_config(self) -> ExitConfig:
        """Get exit configuration (typed helper)."""
        block = await self.get_block("exit")
        if block is None:
            return self._create_default_exit_config()
        return block  # type: ignore

    async def get_api_config(self) -> ApiConfig:
        """Get API configuration (typed helper)."""
        block = await self.get_block("api")
        if block is None:
            return self._create_default_api_config()
        return block  # type: ignore

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

    def _get_fallback_block(self, table: str) -> Optional[ConfigBase]:
        """Get fallback block with default values."""
        match table:
            case "trading":
                return self._create_default_trading_config()
            case "scoring":
                return self._create_default_scoring_config()
            case "discovery":
                return self._create_default_discovery_config()
            case "cluster":
                return self._create_default_cluster_config()
            case "risk":
                return self._create_default_risk_config()
            case "exit":
                return self._create_default_exit_config()
            case "api":
                return self._create_default_api_config()
            case _:
                return None

    def _create_default_trading_config(self) -> TradingConfig:
        """Create trading config with default values."""
        return TradingConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
            base_position_size_pct=Decimal("2.0"),
            min_position_sol=Decimal("0.01"),
            max_position_sol=Decimal("1.0"),
            max_concurrent_positions=5,
            score_threshold=Decimal("0.70"),
            high_conviction_threshold=Decimal("0.85"),
            high_conviction_multiplier=Decimal("1.5"),
            min_token_age_seconds=300,
            max_token_age_hours=24,
            min_liquidity_usd=Decimal("10000.0"),
            max_market_cap_usd=Decimal("10000000.0"),
            max_position_hold_hours=24,
            max_daily_trades=20,
        )

    def _create_default_scoring_config(self) -> ScoringConfig:
        """Create scoring config with default values."""
        return ScoringConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
            wallet_weight=Decimal("0.30"),
            cluster_weight=Decimal("0.25"),
            token_weight=Decimal("0.25"),
            context_weight=Decimal("0.20"),
            wallet_win_rate_weight=Decimal("0.35"),
            wallet_pnl_weight=Decimal("0.25"),
            wallet_timing_weight=Decimal("0.25"),
            wallet_consistency_weight=Decimal("0.15"),
            wallet_leader_bonus=Decimal("0.15"),
            wallet_max_decay_penalty=Decimal("0.30"),
            token_liquidity_weight=Decimal("0.30"),
            token_mcap_weight=Decimal("0.25"),
            token_holder_dist_weight=Decimal("0.20"),
            token_volume_weight=Decimal("0.25"),
            token_min_liquidity_usd=Decimal("1000.0"),
            token_optimal_liquidity_usd=Decimal("50000.0"),
            token_min_mcap_usd=Decimal("10000.0"),
            token_optimal_mcap_usd=Decimal("500000.0"),
            peak_trading_hours_utc=[14, 15, 16, 17, 18],
            high_volatility_threshold=Decimal("0.10"),
            solo_signal_base=Decimal("0.50"),
            min_participation_rate=Decimal("0.30"),
            new_token_penalty_minutes=5,
            max_new_token_penalty=Decimal("0.30"),
        )

    def _create_default_discovery_config(self) -> DiscoveryConfig:
        """Create discovery config with default values."""
        return DiscoveryConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
        )

    def _create_default_cluster_config(self) -> ClusterConfig:
        """Create cluster config with default values."""
        return ClusterConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
        )

    def _create_default_risk_config(self) -> RiskConfig:
        """Create risk config with default values."""
        return RiskConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
            risk_per_trade_pct=Decimal("1.0"),
            sizing_mode="risk_based",
            daily_loss_limit_pct=Decimal("5.0"),
            daily_loss_limit_enabled=True,
            max_concentration_token_pct=Decimal("25.0"),
            max_concentration_cluster_pct=Decimal("50.0"),
            max_positions_per_cluster=3,
            max_drawdown_pct=Decimal("20.0"),
            drawdown_warning_pct=Decimal("15.0"),
            drawdown_reduction_tiers=[
                {"threshold_pct": 5, "size_reduction_pct": 0},
                {"threshold_pct": 10, "size_reduction_pct": 25},
                {"threshold_pct": 15, "size_reduction_pct": 50},
                {"threshold_pct": 20, "size_reduction_pct": 100},
            ],
            win_rate_threshold_pct=Decimal("40.0"),
            win_rate_window_size=50,
            win_rate_min_trades=10,
            consecutive_loss_threshold=3,
            consecutive_loss_critical=5,
            position_size_reduction_factor=Decimal("0.50"),
            circuit_breaker_threshold=5,
            circuit_breaker_cooldown_seconds=30,
            auto_resume_enabled=True,
            no_signal_warning_hours=48,
        )

    def _create_default_exit_config(self) -> ExitConfig:
        """Create exit config with default values."""
        return ExitConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
        )

    def _create_default_api_config(self) -> ApiConfig:
        """Create API config with default values."""
        return ApiConfig(
            id=0,
            name="Fallback",
            status="default",
            version=0,
        )


# Singleton
_config_service: Optional[ConfigService] = None


async def get_config_service() -> ConfigService:
    """Get or create config service singleton."""
    global _config_service

    if _config_service is None:
        _config_service = ConfigService()

    return _config_service


def reset_config_service() -> None:
    """Reset the singleton (for testing)."""
    global _config_service
    _config_service = None
