"""Wallet configuration loaded securely from environment.

SECURITY: Private key is loaded as SecretStr to prevent logging.
NEVER log or expose the private key value.
"""

from functools import lru_cache

import structlog
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger()


class WalletSettings(BaseSettings):
    """Wallet configuration loaded securely from environment.

    SECURITY: Private key is loaded as SecretStr to prevent logging.
    NEVER log or expose the private key value.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Trading wallet (REQUIRED for execution)
    trading_wallet_private_key: SecretStr = Field(
        ...,
        description="Base58 private key for trading wallet",
    )

    # RPC configuration
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana RPC endpoint",
    )
    solana_rpc_ws_url: str | None = Field(
        default=None,
        description="Solana WebSocket endpoint for subscriptions",
    )

    # Connection settings
    rpc_commitment: str = Field(default="confirmed")
    rpc_timeout_seconds: int = Field(default=30, ge=5, le=120)
    rpc_max_retries: int = Field(default=3, ge=1, le=10)

    # Safety settings
    min_sol_balance: float = Field(
        default=0.05,
        ge=0.01,
        description="Minimum SOL to keep for fees",
    )
    auto_safe_mode_on_error: bool = Field(
        default=True,
        description="Automatically enter safe mode on connection errors",
    )
    balance_refresh_interval_seconds: int = Field(
        default=30,
        ge=10,
        le=300,
    )

    @field_validator("trading_wallet_private_key", mode="before")
    @classmethod
    def validate_private_key_format(cls, v: str | SecretStr) -> str | SecretStr:
        """Validate private key format without exposing value."""
        raw = v.get_secret_value() if isinstance(v, SecretStr) else str(v)

        # Basic format validation (don't log the actual key!)
        if len(raw) < 64:
            raise ValueError("Private key appears too short")

        # Log that key was loaded (not the key itself!)
        logger.info("wallet_private_key_loaded", key_length=len(raw))

        return v


@lru_cache
def get_wallet_settings() -> WalletSettings:
    """Get wallet settings singleton."""
    return WalletSettings()
