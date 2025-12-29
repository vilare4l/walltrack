"""Application settings using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """WallTrack V2 configuration from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore extra env vars
    )

    # Application
    app_name: str = Field(default="WallTrack", description="Application name")
    app_version: str = Field(default="2.0.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")

    # Server
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")

    # Database - Supabase
    supabase_url: str = Field(description="Supabase project URL")
    supabase_key: SecretStr = Field(description="Supabase API key")
    postgres_schema: str = Field(
        default="walltrack", description="PostgreSQL schema for WallTrack tables"
    )

    # Database - Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: SecretStr = Field(description="Neo4j password")

    # External APIs (minimal for Story 1.1)
    helius_api_key: SecretStr = Field(default=SecretStr(""), description="Helius API key")

    # Solana RPC (Story 1.5)
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com",
        description="Solana RPC endpoint URL",
    )

    # Trading mode (to be used in later stories)
    trading_mode: Literal["simulation", "live"] = Field(
        default="simulation", description="Trading mode: simulation or live"
    )

    # Circuit Breaker
    circuit_breaker_threshold: int = Field(
        default=5, ge=1, description="Failures before circuit opens"
    )
    circuit_breaker_cooldown: int = Field(
        default=30, ge=1, description="Seconds before half-open"
    )

    # Discovery Scheduler (Story 2.2)
    discovery_scheduler_enabled: bool = Field(
        default=True, description="Enable automatic token discovery scheduler"
    )
    discovery_schedule_hours: int = Field(
        default=4, ge=1, le=24, description="Hours between discovery runs"
    )

    @field_validator("neo4j_uri")
    @classmethod
    def validate_neo4j_uri(cls, v: str) -> str:
        """Validate Neo4j URI format."""
        if not v.startswith(("bolt://", "neo4j://", "neo4j+s://")):
            raise ValueError("Neo4j URI must start with bolt://, neo4j://, or neo4j+s://")
        return v

    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Validate Supabase URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Supabase URL must start with http:// or https://")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()  # type: ignore[call-arg]  # Values from env


# Note: For safe import, use get_settings() to get the settings instance
# The module-level 'settings' is available after explicit get_settings() call
