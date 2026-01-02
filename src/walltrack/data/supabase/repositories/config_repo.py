"""Configuration repository for Supabase.

This module provides a repository pattern for accessing the config table
in Supabase, storing key-value configuration pairs.

Table schema expected:
    config (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMPTZ DEFAULT NOW()
    )
"""

from datetime import datetime, timedelta

import structlog

from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger(__name__)


class ConfigRepository:
    """Repository for accessing config table in Supabase.

    Provides CRUD operations for configuration key-value pairs,
    with specialized methods for trading wallet address.

    Attributes:
        _client: SupabaseClient instance for database operations.
        _cache: In-memory cache for config values with timestamps (Story 3.5).

    Example:
        client = await get_supabase_client()
        repo = ConfigRepository(client)
        await repo.set_trading_wallet("9WzDX...")
        wallet = await repo.get_trading_wallet()
    """

    TABLE_NAME = "config"
    CACHE_TTL_MINUTES = 5  # Story 3.5: Cache watchlist criteria for 5 minutes

    # Class-level cache shared across all instances (Story 3.5)
    _cache: dict[str, tuple[dict, datetime]] = {}

    def __init__(self, client: SupabaseClient) -> None:
        """Initialize repository with Supabase client.

        Args:
            client: Connected SupabaseClient instance.
        """
        self._client = client

    async def get_value(self, key: str) -> str | None:
        """Get configuration value by key.

        Args:
            key: Configuration key to retrieve.

        Returns:
            Configuration value if exists, None otherwise.
        """
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("value")
                .eq("key", key)
                .single()
                .execute()
            )

            if result.data:
                return result.data.get("value")
            return None

        except Exception as e:
            log.warning("config_get_value_failed", key=key, error=str(e))
            return None

    async def set_value(self, key: str, value: str) -> None:
        """Set configuration value by key (upsert).

        Args:
            key: Configuration key to set.
            value: Configuration value to store.
        """
        try:
            await (
                self._client.client.table(self.TABLE_NAME)
                .upsert({"key": key, "value": value}, on_conflict="key")
                .execute()
            )
            log.info("config_value_set", key=key)

        except Exception as e:
            log.error("config_set_value_failed", key=key, error=str(e))
            raise

    async def delete_value(self, key: str) -> None:
        """Delete configuration value by key.

        Args:
            key: Configuration key to delete.
        """
        try:
            await (
                self._client.client.table(self.TABLE_NAME)
                .delete()
                .eq("key", key)
                .execute()
            )
            log.info("config_value_deleted", key=key)

        except Exception as e:
            log.warning("config_delete_value_failed", key=key, error=str(e))

    # Wallet-specific methods

    async def get_trading_wallet(self) -> str | None:
        """Get stored trading wallet address.

        Returns:
            Wallet address if configured, None otherwise.
        """
        return await self.get_value("trading_wallet_address")

    async def set_trading_wallet(self, address: str) -> None:
        """Store trading wallet address.

        Args:
            address: Solana wallet address to store.
        """
        await self.set_value("trading_wallet_address", address)

    async def clear_trading_wallet(self) -> None:
        """Remove stored trading wallet address."""
        await self.delete_value("trading_wallet_address")

    # Behavioral profiling parameters (Story 3.3)

    async def get_behavioral_min_trades(self) -> int:
        """Get minimum trades required for behavioral profiling.

        Returns:
            Minimum trade count threshold (default: 10).
        """
        value = await self.get_value("behavioral_min_trades")
        return int(value) if value else 10

    async def get_behavioral_confidence_high(self) -> int:
        """Get high confidence threshold for behavioral profiling.

        Returns:
            Trade count for high confidence (default: 50).
        """
        value = await self.get_value("behavioral_confidence_high")
        return int(value) if value else 50

    async def get_behavioral_confidence_medium(self) -> int:
        """Get medium confidence threshold for behavioral profiling.

        Returns:
            Trade count for medium confidence (default: 10).
        """
        value = await self.get_value("behavioral_confidence_medium")
        return int(value) if value else 10

    async def get_position_size_small_max(self) -> float:
        """Get maximum SOL amount for 'small' position size classification.

        Returns:
            SOL threshold for small positions (default: 0.5).
        """
        value = await self.get_value("position_size_small_max")
        return float(value) if value else 0.5

    async def get_position_size_medium_max(self) -> float:
        """Get maximum SOL amount for 'medium' position size classification.

        Returns:
            SOL threshold for medium positions (default: 2.0).
        """
        value = await self.get_value("position_size_medium_max")
        return float(value) if value else 2.0

    async def get_hold_duration_scalper_max(self) -> int:
        """Get maximum seconds for 'scalper' hold duration classification.

        Returns:
            Seconds threshold for scalper (default: 3600 = 1 hour).
        """
        value = await self.get_value("hold_duration_scalper_max")
        return int(value) if value else 3600

    async def get_hold_duration_day_trader_max(self) -> int:
        """Get maximum seconds for 'day_trader' hold duration classification.

        Returns:
            Seconds threshold for day trader (default: 86400 = 24 hours).
        """
        value = await self.get_value("hold_duration_day_trader_max")
        return int(value) if value else 86400

    async def get_hold_duration_swing_trader_max(self) -> int:
        """Get maximum seconds for 'swing_trader' hold duration classification.

        Returns:
            Seconds threshold for swing trader (default: 604800 = 7 days).
        """
        value = await self.get_value("hold_duration_swing_trader_max")
        return int(value) if value else 604800

    async def get_behavioral_criteria(self) -> dict[str, float]:
        """Get all behavioral profiling criteria with 5-minute cache.

        Fetches behavioral configuration parameters from config table:
        - position_size_small_max: Threshold for small position size (default: 0.5 SOL)
        - position_size_large_min: Threshold for large position size (default: 2.0 SOL)
        - hold_duration_scalper_max: Scalper threshold in seconds (default: 3600)
        - hold_duration_day_trader_max: Day trader threshold in seconds (default: 86400)
        - hold_duration_swing_trader_max: Swing trader threshold in seconds (default: 604800)
        - confidence_high_min: High confidence min trades (default: 20)
        - confidence_medium_min: Medium confidence min trades (default: 10)
        - confidence_low_min: Low confidence min trades (default: 5)

        Cache reduces DB queries when profiling multiple wallets.
        Cache is cleared when config is updated via clear_cache().

        Returns:
            Dictionary with criteria keys and float values.

        Example:
            criteria = await repo.get_behavioral_criteria()
            # {'position_size_small_max': 0.5, 'position_size_large_min': 2.0, ...}
        """
        cache_key = "behavioral_criteria"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            cache_age = datetime.utcnow() - timestamp
            if cache_age < timedelta(minutes=self.CACHE_TTL_MINUTES):
                log.debug(
                    "behavioral_criteria_cache_hit",
                    cache_age_seconds=int(cache_age.total_seconds()),
                )
                return data

        # Fetch from database
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("key, value")
                .like("key", "behavioral.%")
                .execute()
            )

            if not result.data:
                log.warning("behavioral_criteria_not_found_using_defaults")
                criteria = {
                    "position_size_small_max": 0.5,
                    "position_size_large_min": 2.0,
                    "hold_duration_scalper_max": 3600.0,
                    "hold_duration_day_trader_max": 86400.0,
                    "hold_duration_swing_trader_max": 604800.0,
                    "confidence_high_min": 20.0,
                    "confidence_medium_min": 10.0,
                    "confidence_low_min": 5.0,
                }
            else:
                # Parse config rows into dict (key = "behavioral.position_size_small_max" → "position_size_small_max")
                criteria = {}
                for row in result.data:
                    key = row["key"].replace("behavioral.", "")  # Remove prefix
                    value = float(row["value"])
                    criteria[key] = value

                # Validate all required keys present
                required_keys = {
                    "position_size_small_max",
                    "position_size_large_min",
                    "hold_duration_scalper_max",
                    "hold_duration_day_trader_max",
                    "hold_duration_swing_trader_max",
                    "confidence_high_min",
                    "confidence_medium_min",
                    "confidence_low_min",
                }
                if not required_keys.issubset(criteria.keys()):
                    missing = required_keys - criteria.keys()
                    log.warning(
                        "behavioral_criteria_missing_keys_using_defaults", missing=list(missing)
                    )
                    # Fill missing with defaults
                    defaults = {
                        "position_size_small_max": 0.5,
                        "position_size_large_min": 2.0,
                        "hold_duration_scalper_max": 3600.0,
                        "hold_duration_day_trader_max": 86400.0,
                        "hold_duration_swing_trader_max": 604800.0,
                        "confidence_high_min": 20.0,
                        "confidence_medium_min": 10.0,
                        "confidence_low_min": 5.0,
                    }
                    for key in missing:
                        criteria[key] = defaults[key]

            # Update cache
            self._cache[cache_key] = (criteria, datetime.utcnow())
            log.info("behavioral_criteria_loaded", criteria=criteria)
            return criteria

        except Exception as e:
            log.error("behavioral_criteria_fetch_failed_using_defaults", error=str(e))
            # Return defaults on error
            return {
                "position_size_small_max": 0.5,
                "position_size_large_min": 2.0,
                "hold_duration_scalper_max": 3600.0,
                "hold_duration_day_trader_max": 86400.0,
                "hold_duration_swing_trader_max": 604800.0,
                "confidence_high_min": 20.0,
                "confidence_medium_min": 10.0,
                "confidence_low_min": 5.0,
            }

    # Decay detection parameters (Story 3.4)

    async def get_decay_rolling_window_size(self) -> int:
        """Get rolling window size for decay detection.

        Returns:
            Number of recent trades to analyze (default: 20).
        """
        value = await self.get_value("decay_rolling_window_size")
        return int(value) if value else 20

    async def get_decay_min_trades(self) -> int:
        """Get minimum trades required for decay detection.

        Returns:
            Minimum completed trades threshold (default: 20).
        """
        value = await self.get_value("decay_min_trades")
        return int(value) if value else 20

    async def get_decay_threshold(self) -> float:
        """Get rolling win rate threshold for flagging wallet as decayed.

        Returns:
            Win rate threshold (default: 0.40 = 40%).
        """
        value = await self.get_value("decay_threshold")
        return float(value) if value else 0.40

    async def get_decay_recovery_threshold(self) -> float:
        """Get rolling win rate threshold for recovery from flagged status.

        Returns:
            Recovery threshold (default: 0.50 = 50%).
        """
        value = await self.get_value("decay_recovery_threshold")
        return float(value) if value else 0.50

    async def get_decay_consecutive_loss_threshold(self) -> int:
        """Get consecutive loss count threshold for downgraded status.

        Returns:
            Consecutive losses threshold (default: 3).
        """
        value = await self.get_value("decay_consecutive_loss_threshold")
        return int(value) if value else 3

    async def get_decay_dormancy_days(self) -> int:
        """Get days without activity threshold for dormancy.

        Returns:
            Days threshold for dormancy (default: 30).
        """
        value = await self.get_value("decay_dormancy_days")
        return int(value) if value else 30

    async def get_decay_score_downgrade_decay(self) -> float:
        """Get score multiplier for decay detected event.

        Returns:
            Score multiplier (default: 0.80 = 20% reduction).
        """
        value = await self.get_value("decay_score_downgrade_decay")
        return float(value) if value else 0.80

    async def get_decay_score_downgrade_loss(self) -> float:
        """Get score multiplier per consecutive loss beyond threshold.

        Returns:
            Score multiplier per loss (default: 0.95 = 5% reduction).
        """
        value = await self.get_value("decay_score_downgrade_loss")
        return float(value) if value else 0.95

    async def get_decay_score_recovery_boost(self) -> float:
        """Get score multiplier for recovery event.

        Returns:
            Score multiplier (default: 1.10 = 10% increase).
        """
        value = await self.get_value("decay_score_recovery_boost")
        return float(value) if value else 1.10

    # Discovery criteria parameters (Story 3.1)

    async def get_discovery_criteria(self) -> dict[str, float]:
        """Get wallet discovery criteria with 5-minute cache.

        Fetches discovery configuration parameters from config table:
        - early_entry_minutes: Maximum minutes after token launch (default: 30)
        - min_profit_percent: Minimum profit percentage for profitable exit (default: 50)

        Cache reduces DB queries when discovering wallets from multiple tokens.
        Cache is cleared when config is updated via clear_cache().

        Returns:
            Dictionary with criteria keys and float values.

        Example:
            criteria = await repo.get_discovery_criteria()
            # {'early_entry_minutes': 30.0, 'min_profit_percent': 50.0}
        """
        cache_key = "discovery_criteria"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            cache_age = datetime.utcnow() - timestamp
            if cache_age < timedelta(minutes=self.CACHE_TTL_MINUTES):
                log.debug(
                    "discovery_criteria_cache_hit",
                    cache_age_seconds=int(cache_age.total_seconds()),
                )
                return data

        # Fetch from database
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("key, value")
                .like("key", "discovery.%")
                .execute()
            )

            if not result.data:
                log.warning("discovery_criteria_not_found_using_defaults")
                criteria = {
                    "early_entry_minutes": 30.0,
                    "min_profit_percent": 50.0,
                }
            else:
                # Parse config rows into dict (key = "discovery.early_entry_minutes" → "early_entry_minutes")
                criteria = {}
                for row in result.data:
                    key = row["key"].replace("discovery.", "")  # Remove prefix
                    value = float(row["value"])
                    criteria[key] = value

                # Validate all required keys present
                required_keys = {"early_entry_minutes", "min_profit_percent"}
                if not required_keys.issubset(criteria.keys()):
                    missing = required_keys - criteria.keys()
                    log.warning(
                        "discovery_criteria_missing_keys_using_defaults", missing=list(missing)
                    )
                    # Fill missing with defaults
                    defaults = {
                        "early_entry_minutes": 30.0,
                        "min_profit_percent": 50.0,
                    }
                    for key in missing:
                        criteria[key] = defaults[key]

            # Update cache
            self._cache[cache_key] = (criteria, datetime.utcnow())
            log.info("discovery_criteria_loaded", criteria=criteria)
            return criteria

        except Exception as e:
            log.error("discovery_criteria_fetch_failed_using_defaults", error=str(e))
            # Return defaults on error
            return {
                "early_entry_minutes": 30.0,
                "min_profit_percent": 50.0,
            }

    # Watchlist criteria parameters (Story 3.5)

    async def get_watchlist_criteria(self) -> dict[str, float]:
        """Get watchlist evaluation criteria with 5-minute cache.

        Fetches watchlist configuration parameters from config table:
        - min_winrate: Minimum win rate to qualify (0.0-1.0)
        - min_pnl: Minimum total PnL in SOL
        - min_trades: Minimum number of trades
        - max_decay_score: Maximum decay score allowed (0.0-1.0)

        Cache reduces DB queries when evaluating multiple wallets.
        Cache is cleared when config is updated via clear_cache().

        Returns:
            Dictionary with criteria keys and float values.

        Example:
            criteria = await repo.get_watchlist_criteria()
            # {'min_winrate': 0.70, 'min_pnl': 5.0, 'min_trades': 10.0, 'max_decay_score': 0.3}
        """
        cache_key = "watchlist_criteria"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            cache_age = datetime.utcnow() - timestamp
            if cache_age < timedelta(minutes=self.CACHE_TTL_MINUTES):
                log.debug(
                    "watchlist_criteria_cache_hit",
                    cache_age_seconds=int(cache_age.total_seconds()),
                )
                return data

        # Fetch from database
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("key, value")
                .like("key", "watchlist.%")
                .execute()
            )

            if not result.data:
                log.warning("watchlist_criteria_not_found_using_defaults")
                criteria = {
                    "min_winrate": 0.70,
                    "min_pnl": 5.0,
                    "min_trades": 10.0,
                    "max_decay_score": 0.3,
                }
            else:
                # Parse config rows into dict (key = "watchlist.min_winrate" → "min_winrate")
                criteria = {}
                for row in result.data:
                    key = row["key"].replace("watchlist.", "")  # Remove prefix
                    value = float(row["value"])
                    criteria[key] = value

                # Validate all required keys present
                required_keys = {"min_winrate", "min_pnl", "min_trades", "max_decay_score"}
                if not required_keys.issubset(criteria.keys()):
                    missing = required_keys - criteria.keys()
                    log.warning(
                        "watchlist_criteria_missing_keys_using_defaults", missing=list(missing)
                    )
                    # Fill missing with defaults
                    defaults = {
                        "min_winrate": 0.70,
                        "min_pnl": 5.0,
                        "min_trades": 10.0,
                        "max_decay_score": 0.3,
                    }
                    for key in missing:
                        criteria[key] = defaults[key]

            # Update cache
            self._cache[cache_key] = (criteria, datetime.utcnow())
            log.info("watchlist_criteria_loaded", criteria=criteria)
            return criteria

        except Exception as e:
            log.error("watchlist_criteria_fetch_failed_using_defaults", error=str(e))
            # Return defaults on error
            return {
                "min_winrate": 0.70,
                "min_pnl": 5.0,
                "min_trades": 10.0,
                "max_decay_score": 0.3,
            }


    # Performance analysis criteria (Story 3.2)

    async def get_performance_criteria(self) -> dict[str, float]:
        """Get performance analysis criteria with 5-minute cache (AC7).

        Fetches performance configuration parameters from config table:
        - min_profit_percent: Minimum profit percentage for win rate calculation (default: 10.0)
                             AC2: Profitable trade defined as exit_price > entry_price * 1.1

        Cache reduces DB queries when analyzing performance for multiple wallets.
        Cache is cleared when config is updated via clear_cache().

        Returns:
            Dictionary with criteria keys and float values.

        Example:
            criteria = await repo.get_performance_criteria()
            # {'min_profit_percent': 10.0}
        """
        cache_key = "performance_criteria"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            cache_age = datetime.utcnow() - timestamp
            if cache_age < timedelta(minutes=self.CACHE_TTL_MINUTES):
                log.debug(
                    "performance_criteria_cache_hit",
                    cache_age_seconds=int(cache_age.total_seconds()),
                )
                return data

        # Fetch from database
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("key, value")
                .like("key", "performance.%")
                .execute()
            )

            if not result.data:
                log.warning("performance_criteria_not_found_using_defaults")
                criteria = {
                    "min_profit_percent": 10.0,
                }
            else:
                # Parse config rows into dict (key = "performance.min_profit_percent" → "min_profit_percent")
                criteria = {}
                for row in result.data:
                    key = row["key"].replace("performance.", "")  # Remove prefix
                    value = float(row["value"])
                    criteria[key] = value

                # Validate all required keys present
                required_keys = {"min_profit_percent"}
                if not required_keys.issubset(criteria.keys()):
                    missing = required_keys - criteria.keys()
                    log.warning(
                        "performance_criteria_missing_keys_using_defaults", missing=list(missing)
                    )
                    # Fill missing with defaults
                    defaults = {
                        "min_profit_percent": 10.0,
                    }
                    for key in missing:
                        criteria[key] = defaults[key]

            # Update cache
            self._cache[cache_key] = (criteria, datetime.utcnow())
            log.info("performance_criteria_loaded", criteria=criteria)
            return criteria

        except Exception as e:
            log.error("performance_criteria_fetch_failed_using_defaults", error=str(e))
            # Return defaults on error
            return {
                "min_profit_percent": 10.0,
            }

    async def get_scoring_weights(self) -> dict[str, float]:
        """Get watchlist scoring weights with 5-minute cache.

        Story 3.5 Issue #5 fix - Make scoring weights configurable instead of hardcoded.

        Fetches scoring weight configuration parameters from config table:
        - weight_win_rate: Win rate component weight (default: 0.40)
        - weight_pnl: PnL component weight (default: 0.30)
        - weight_trades: Trades component weight (default: 0.20)
        - weight_decay: Decay component weight (default: 0.10)

        Weights must sum to 1.0 for proper scoring normalization.
        Cache reduces DB queries when evaluating multiple wallets.

        Returns:
            Dictionary with weight keys and float values.

        Example:
            weights = await repo.get_scoring_weights()
            # {'weight_win_rate': 0.40, 'weight_pnl': 0.30, 'weight_trades': 0.20, 'weight_decay': 0.10}
        """
        cache_key = "scoring_weights"

        # Check cache
        if cache_key in self._cache:
            data, timestamp = self._cache[cache_key]
            cache_age = datetime.utcnow() - timestamp
            if cache_age < timedelta(minutes=self.CACHE_TTL_MINUTES):
                log.debug(
                    "scoring_weights_cache_hit",
                    cache_age_seconds=int(cache_age.total_seconds()),
                )
                return data

        # Fetch from database
        try:
            result = await (
                self._client.client.table(self.TABLE_NAME)
                .select("key, value")
                .like("key", "scoring.%")
                .execute()
            )

            if not result.data:
                log.warning("scoring_weights_not_found_using_defaults")
                weights = {
                    "weight_win_rate": 0.40,
                    "weight_pnl": 0.30,
                    "weight_trades": 0.20,
                    "weight_decay": 0.10,
                }
            else:
                # Parse config rows into dict (key = "scoring.weight_win_rate" → "weight_win_rate")
                weights = {}
                for row in result.data:
                    key = row["key"].replace("scoring.", "")  # Remove prefix
                    value = float(row["value"])
                    weights[key] = value

                # Validate all required keys present
                required_keys = {"weight_win_rate", "weight_pnl", "weight_trades", "weight_decay"}
                if not required_keys.issubset(weights.keys()):
                    missing = required_keys - weights.keys()
                    log.warning(
                        "scoring_weights_missing_keys_using_defaults", missing=list(missing)
                    )
                    # Fill missing with defaults
                    defaults = {
                        "weight_win_rate": 0.40,
                        "weight_pnl": 0.30,
                        "weight_trades": 0.20,
                        "weight_decay": 0.10,
                    }
                    for key in missing:
                        weights[key] = defaults[key]

                # Validate weights sum to 1.0 (with small tolerance for float precision)
                total = sum(weights.values())
                if abs(total - 1.0) > 0.01:
                    log.warning(
                        "scoring_weights_invalid_sum_using_defaults",
                        total=total,
                        expected=1.0,
                    )
                    # Use defaults if weights don't sum to 1.0
                    weights = {
                        "weight_win_rate": 0.40,
                        "weight_pnl": 0.30,
                        "weight_trades": 0.20,
                        "weight_decay": 0.10,
                    }

            # Update cache
            self._cache[cache_key] = (weights, datetime.utcnow())
            log.info("scoring_weights_loaded", weights=weights)
            return weights

        except Exception as e:
            log.error("scoring_weights_fetch_failed_using_defaults", error=str(e))
            # Return defaults on error
            return {
                "weight_win_rate": 0.40,
                "weight_pnl": 0.30,
                "weight_trades": 0.20,
                "weight_decay": 0.10,
            }

    def clear_cache(self) -> None:
        """Clear config cache (call after updating watchlist criteria).

        Forces reload from database on next get_watchlist_criteria() call.
        Should be called after UI config update to ensure fresh values.

        Example:
            await repo.set_value("watchlist.min_winrate", "0.80")
            repo.clear_cache()  # Force reload
        """
        self._cache.clear()
        log.info("config_cache_cleared")
