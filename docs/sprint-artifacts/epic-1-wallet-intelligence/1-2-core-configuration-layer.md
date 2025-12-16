# Story 1.2: Core Configuration Layer

## Story Info
- **Epic**: Epic 1 - Wallet Intelligence & Discovery
- **Status**: ready
- **Priority**: Critical (Foundation)
- **FR**: Foundation for all FRs
- **NFR**: NFR6, NFR10

## User Story

**As a** developer,
**I want** centralized configuration management using pydantic-settings,
**So that** all settings are validated, typed, and secure.

## Acceptance Criteria

### AC 1: Environment Loading
**Given** a .env file with configuration
**When** the application starts
**Then** all settings are loaded via pydantic-settings
**And** missing required fields raise clear errors
**And** validation runs on all values

### AC 2: Secret Protection
**Given** sensitive values (API keys, private keys)
**When** settings are logged or serialized
**Then** secrets are NEVER exposed (NFR6)
**And** SecretStr type is used for all secrets

### AC 3: Type Safety
**Given** configuration values
**When** accessed in code
**Then** full type hints are available
**And** mypy validates all usages

## Technical Specifications

### Settings Model

**src/walltrack/config/settings.py:**
```python
"""Application settings using pydantic-settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    debug: bool = Field(default=False, description="Enable debug mode")
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    # Neo4j
    neo4j_uri: str = Field(..., description="Neo4j connection URI")
    neo4j_user: str = Field(..., description="Neo4j username")
    neo4j_password: SecretStr = Field(..., description="Neo4j password")
    neo4j_database: str = Field(
        default="walltrack",
        description="Neo4j database name (dedicated database for isolation)",
    )
    neo4j_max_connection_pool_size: int = Field(
        default=50, ge=1, le=100, description="Neo4j connection pool size"
    )

    # Supabase/PostgreSQL
    supabase_url: str = Field(..., description="Supabase project URL")
    supabase_key: SecretStr = Field(..., description="Supabase API key")
    postgres_schema: str = Field(
        default="walltrack",
        description="PostgreSQL schema name (dedicated schema for isolation)",
    )

    # Helius
    helius_api_key: SecretStr = Field(..., description="Helius API key")
    helius_webhook_secret: SecretStr = Field(..., description="Helius webhook HMAC secret")
    helius_api_url: str = Field(
        default="https://api.helius.xyz/v0", description="Helius API base URL"
    )

    # Jupiter
    jupiter_api_url: str = Field(
        default="https://quote-api.jup.ag/v6", description="Jupiter API base URL"
    )
    jupiter_slippage_bps: int = Field(
        default=100, ge=1, le=1000, description="Default slippage in basis points (100 = 1%)"
    )

    # DexScreener
    dexscreener_api_url: str = Field(
        default="https://api.dexscreener.com/latest", description="DexScreener API base URL"
    )

    # Birdeye (fallback)
    birdeye_api_key: SecretStr | None = Field(
        default=None, description="Birdeye API key (optional fallback)"
    )
    birdeye_api_url: str = Field(
        default="https://public-api.birdeye.so", description="Birdeye API base URL"
    )

    # Solana
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com", description="Solana RPC endpoint"
    )
    solana_rpc_timeout: int = Field(
        default=30, ge=5, le=120, description="Solana RPC timeout in seconds"
    )
    trading_wallet_private_key: SecretStr = Field(
        ..., description="Trading wallet private key (base58)"
    )

    # Trading Configuration (defaults, can be overridden in Supabase)
    max_concurrent_positions: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent open positions"
    )
    base_position_size_pct: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Base position size as % of capital"
    )
    score_threshold: float = Field(
        default=0.70, ge=0.0, le=1.0, description="Minimum score for trade eligibility"
    )
    high_conviction_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Score threshold for high conviction"
    )
    high_conviction_multiplier: float = Field(
        default=1.5, ge=1.0, le=3.0, description="Position size multiplier for high conviction"
    )

    # Risk Management (defaults)
    drawdown_threshold_pct: float = Field(
        default=20.0, ge=5.0, le=50.0, description="Drawdown % to trigger circuit breaker"
    )
    win_rate_threshold_pct: float = Field(
        default=40.0, ge=20.0, le=60.0, description="Win rate % to trigger circuit breaker"
    )
    win_rate_window_size: int = Field(
        default=50, ge=10, le=200, description="Number of trades for win rate calculation"
    )
    consecutive_loss_threshold: int = Field(
        default=3, ge=2, le=10, description="Consecutive losses to reduce position size"
    )
    position_size_reduction_factor: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Factor to reduce position size after losses"
    )

    # Retry Configuration
    max_retries: int = Field(default=3, ge=1, le=10, description="Maximum API retry attempts")
    retry_base_delay: float = Field(
        default=1.0, ge=0.1, le=5.0, description="Base delay between retries in seconds"
    )
    circuit_breaker_threshold: int = Field(
        default=5, ge=3, le=20, description="Failures before circuit breaker opens"
    )
    circuit_breaker_cooldown: int = Field(
        default=30, ge=10, le=300, description="Circuit breaker cooldown in seconds"
    )

    # Cache Configuration
    token_cache_ttl: int = Field(
        default=300, ge=60, le=3600, description="Token data cache TTL in seconds"
    )
    wallet_cache_ttl: int = Field(
        default=60, ge=10, le=300, description="Wallet lookup cache TTL in seconds"
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
        if not v.startswith("https://"):
            raise ValueError("Supabase URL must use HTTPS")
        return v


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
```

### Usage Examples

**Loading settings in application:**
```python
from walltrack.config.settings import get_settings

settings = get_settings()

# Access typed values
port: int = settings.port
debug: bool = settings.debug

# Access secrets (returns SecretStr)
neo4j_password: str = settings.neo4j_password.get_secret_value()
```

**Using in dependency injection (FastAPI):**
```python
# src/walltrack/api/dependencies.py
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from walltrack.config.settings import Settings, get_settings


@lru_cache
def get_settings_dependency() -> Settings:
    return get_settings()


SettingsDep = Annotated[Settings, Depends(get_settings_dependency)]


# Usage in route
@router.get("/health")
async def health(settings: SettingsDep):
    return {"debug": settings.debug}
```

**Safe logging (never expose secrets):**
```python
import structlog

log = structlog.get_logger()

settings = get_settings()

# ✅ Safe - logs "SecretStr('**********')"
log.info("config_loaded", neo4j_uri=settings.neo4j_uri)

# ❌ NEVER DO THIS - exposes secret
# log.info("config", password=settings.neo4j_password.get_secret_value())
```

### Structlog Configuration

**src/walltrack/config/logging.py:**
```python
"""Logging configuration using structlog."""

import logging
import sys

import structlog
from walltrack.config.settings import get_settings


def configure_logging() -> None:
    """Configure structlog for the application."""
    settings = get_settings()

    # Set log level
    log_level = getattr(logging, settings.log_level)

    # Configure structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            # Use JSON in production, pretty print in debug
            structlog.dev.ConsoleRenderer()
            if settings.debug
            else structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging for third-party libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
```

### Dynamic Configuration from Supabase

**src/walltrack/data/models/config.py:**
```python
"""Configuration models."""

from pydantic import BaseModel, Field


class ScoringWeights(BaseModel):
    """Scoring factor weights."""

    wallet: float = Field(default=0.30, ge=0.0, le=1.0)
    cluster: float = Field(default=0.25, ge=0.0, le=1.0)
    token: float = Field(default=0.25, ge=0.0, le=1.0)
    context: float = Field(default=0.20, ge=0.0, le=1.0)

    def validate_sum(self) -> bool:
        """Validate weights sum to 1.0."""
        return abs(self.wallet + self.cluster + self.token + self.context - 1.0) < 0.01


class DynamicConfig(BaseModel):
    """Dynamic configuration stored in Supabase."""

    scoring_weights: ScoringWeights = Field(default_factory=ScoringWeights)
    score_threshold: float = Field(default=0.70, ge=0.0, le=1.0)
    high_conviction_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    drawdown_threshold_pct: float = Field(default=20.0, ge=5.0, le=50.0)
    win_rate_threshold_pct: float = Field(default=40.0, ge=20.0, le=60.0)
    max_concurrent_positions: int = Field(default=5, ge=1, le=20)
```

**src/walltrack/data/supabase/repositories/config_repo.py:**
```python
"""Repository for dynamic configuration stored in Supabase."""

from typing import Any

import structlog
from supabase import AsyncClient

from walltrack.data.models.config import DynamicConfig, ScoringWeights

log = structlog.get_logger()


class ConfigRepository:
    """Repository for runtime configuration."""

    def __init__(self, client: AsyncClient) -> None:
        self.client = client
        self.table = "config"

    async def get_config(self, key: str) -> Any | None:
        """Get a configuration value by key."""
        response = await self.client.table(self.table).select("value").eq("key", key).single().execute()
        return response.data.get("value") if response.data else None

    async def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value."""
        await self.client.table(self.table).upsert(
            {"key": key, "value": value, "updated_at": "now()"}
        ).execute()
        log.info("config_updated", key=key)

    async def get_scoring_weights(self) -> ScoringWeights:
        """Get current scoring weights."""
        weights = await self.get_config("scoring_weights")
        return ScoringWeights(**(weights or {}))

    async def set_scoring_weights(self, weights: ScoringWeights) -> None:
        """Set scoring weights."""
        if not weights.validate_sum():
            raise ValueError("Scoring weights must sum to 1.0")
        await self.set_config("scoring_weights", weights.model_dump())

    async def get_score_threshold(self) -> float:
        """Get current score threshold."""
        threshold = await self.get_config("score_threshold")
        return float(threshold) if threshold else 0.70

    async def get_all_config(self) -> DynamicConfig:
        """Get all dynamic configuration."""
        response = await self.client.table(self.table).select("*").execute()
        config_dict = {row["key"]: row["value"] for row in response.data}
        return DynamicConfig(**config_dict)
```

### Supabase Config Table Schema

```sql
-- migrations/001_initial.sql (config table portion)

CREATE TABLE IF NOT EXISTS config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Trigger for auto-updating updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_config_updated_at
    BEFORE UPDATE ON config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Default configuration values
INSERT INTO config (key, value, description) VALUES
    ('scoring_weights', '{"wallet": 0.30, "cluster": 0.25, "token": 0.25, "context": 0.20}', 'Signal scoring factor weights'),
    ('score_threshold', '0.70', 'Minimum score for trade eligibility'),
    ('high_conviction_threshold', '0.85', 'Score threshold for high conviction trades'),
    ('drawdown_threshold_pct', '20.0', 'Drawdown % to trigger circuit breaker'),
    ('win_rate_threshold_pct', '40.0', 'Win rate % to trigger circuit breaker'),
    ('max_concurrent_positions', '5', 'Maximum concurrent open positions')
ON CONFLICT (key) DO NOTHING;

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_config_updated_at ON config(updated_at);
```

## Implementation Tasks

- [ ] Create `src/walltrack/config/settings.py` with full Settings model
- [ ] Create `src/walltrack/config/logging.py` with structlog configuration
- [ ] Create `src/walltrack/config/__init__.py` with exports
- [ ] Create `src/walltrack/api/dependencies.py` with settings dependency
- [ ] Update `.env.example` with all variables
- [ ] Create `src/walltrack/data/models/config.py` for DynamicConfig model
- [ ] Create `src/walltrack/data/supabase/repositories/config_repo.py`
- [ ] Add config table to Supabase migration
- [ ] Write unit tests for settings validation
- [ ] Verify secrets are never logged

## Definition of Done

- [ ] Settings load correctly from .env
- [ ] Missing required fields raise ValidationError
- [ ] SecretStr values never appear in logs or repr
- [ ] mypy passes for all settings usage
- [ ] Dynamic config can be loaded from Supabase
- [ ] Unit tests cover validation edge cases
