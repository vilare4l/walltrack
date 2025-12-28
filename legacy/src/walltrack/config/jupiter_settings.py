"""Jupiter API configuration."""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class JupiterSettings(BaseSettings):
    """Jupiter API configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API endpoints
    jupiter_api_url: str = Field(
        default="https://quote-api.jup.ag/v6",
        description="Jupiter V6 API base URL",
    )
    jupiter_swap_api_url: str = Field(
        default="https://quote-api.jup.ag/v6/swap",
        description="Jupiter swap endpoint",
    )

    # Raydium fallback
    raydium_api_url: str = Field(
        default="https://api.raydium.io/v2",
        description="Raydium API for fallback",
    )
    enable_raydium_fallback: bool = Field(
        default=True,
        description="Enable Raydium as fallback DEX",
    )

    # Trading parameters
    default_slippage_bps: int = Field(
        default=100,  # 1%
        ge=10,
        le=5000,
        description="Default slippage in basis points",
    )
    max_slippage_bps: int = Field(
        default=500,  # 5%
        ge=100,
        le=5000,
        description="Maximum allowed slippage",
    )
    priority_fee_lamports: int = Field(
        default=10000,
        ge=0,
        description="Priority fee for faster inclusion",
    )

    # Timeouts and retries
    quote_timeout_seconds: int = Field(default=5, ge=1, le=30)
    swap_timeout_seconds: int = Field(default=30, ge=10, le=120)
    confirmation_timeout_seconds: int = Field(default=60, ge=30, le=180)
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_delay_seconds: float = Field(default=1.0, ge=0.5, le=10)

    # Safety limits
    max_trade_sol: float = Field(
        default=1.0,
        gt=0,
        description="Maximum SOL per trade",
    )
    min_trade_sol: float = Field(
        default=0.01,
        gt=0,
        description="Minimum SOL per trade",
    )

    @field_validator("max_slippage_bps")
    @classmethod
    def validate_max_slippage(cls, v: int, info: dict) -> int:
        """Validate max slippage is >= default slippage."""
        default = info.data.get("default_slippage_bps", 100)
        if v < default:
            raise ValueError("max_slippage must be >= default_slippage")
        return v


@lru_cache
def get_jupiter_settings() -> JupiterSettings:
    """Get Jupiter settings singleton."""
    return JupiterSettings()
