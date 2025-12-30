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

import structlog

from walltrack.data.supabase.client import SupabaseClient

log = structlog.get_logger(__name__)


class ConfigRepository:
    """Repository for accessing config table in Supabase.

    Provides CRUD operations for configuration key-value pairs,
    with specialized methods for trading wallet address.

    Attributes:
        _client: SupabaseClient instance for database operations.

    Example:
        client = await get_supabase_client()
        repo = ConfigRepository(client)
        await repo.set_trading_wallet("9WzDX...")
        wallet = await repo.get_trading_wallet()
    """

    TABLE_NAME = "config"

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
            SOL threshold for small positions (default: 1.0).
        """
        value = await self.get_value("position_size_small_max")
        return float(value) if value else 1.0

    async def get_position_size_medium_max(self) -> float:
        """Get maximum SOL amount for 'medium' position size classification.

        Returns:
            SOL threshold for medium positions (default: 5.0).
        """
        value = await self.get_value("position_size_medium_max")
        return float(value) if value else 5.0

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
