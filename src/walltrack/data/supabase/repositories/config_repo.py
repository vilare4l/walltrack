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
