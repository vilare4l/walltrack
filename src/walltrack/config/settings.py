"""Application settings using pydantic-settings."""

from enum import Enum
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExecutionMode(str, Enum):
    """Trading execution mode."""

    LIVE = "live"
    SIMULATION = "simulation"


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    env: Literal["development", "staging", "production"] = "development"
    debug: bool = Field(default=False, description="Enable debug mode")

    # Execution Mode
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.SIMULATION,
        description="Trading execution mode (live/simulation)",
    )
    simulation_slippage_bps: int = Field(
        default=100,
        ge=0,
        le=500,
        description="Simulated slippage in basis points (100 = 1%)",
    )
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, ge=1, le=65535, description="Server port")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = Field(
        default="INFO", description="Logging level"
    )

    # Internal API URL (for dashboard to connect to API in Docker)
    api_base_url: str = Field(
        default="",
        description="Base URL for internal API calls. If empty, uses http://localhost:{port}",
    )

    # Neo4j
    neo4j_uri: str = Field(default="bolt://localhost:7687", description="Neo4j connection URI")
    neo4j_user: str = Field(default="neo4j", description="Neo4j username")
    neo4j_password: SecretStr = Field(
        default=SecretStr("neo4jpass"), description="Neo4j password"
    )
    neo4j_database: str = Field(
        default="walltrack",
        description="Neo4j database name (dedicated database for isolation)",
    )
    neo4j_max_connection_pool_size: int = Field(
        default=50, ge=1, le=100, description="Neo4j connection pool size"
    )

    # Supabase/PostgreSQL
    supabase_url: str = Field(
        default="http://localhost:54321", description="Supabase project URL"
    )
    supabase_key: SecretStr = Field(default=SecretStr(""), description="Supabase API key")
    supabase_service_key: SecretStr = Field(
        default=SecretStr(""), description="Supabase service role key"
    )
    postgres_schema: str = Field(
        default="walltrack",
        description="PostgreSQL schema name (dedicated schema for isolation)",
    )
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:54322/postgres",
        description="Direct PostgreSQL connection URL",
    )
    database_pool_min_size: int = Field(default=5, ge=1, le=20)
    database_pool_max_size: int = Field(default=20, ge=5, le=100)
    database_timeout_seconds: int = Field(default=60, ge=5, le=300)

    # Helius
    helius_api_key: SecretStr = Field(default=SecretStr(""), description="Helius API key")
    helius_webhook_secret: SecretStr = Field(
        default=SecretStr(""), description="Helius webhook HMAC secret"
    )
    helius_api_url: str = Field(
        default="https://api.helius.xyz/v0", description="Helius API base URL"
    )
    helius_rpc_url: str = Field(default="", description="Helius RPC URL")
    helius_webhook_url: str = Field(default="", description="Webhook callback URL")
    helius_webhook_id: str = Field(
        default="", description="Helius webhook ID (set after first registration)"
    )
    helius_auto_sync_webhook: bool = Field(
        default=True, description="Auto-sync webhook after discovery"
    )

    # Jupiter
    jupiter_api_url: str = Field(
        default="https://quote-api.jup.ag/v6", description="Jupiter API base URL"
    )
    jupiter_swap_api_url: str = Field(
        default="https://quote-api.jup.ag/v6/swap", description="Jupiter swap API URL"
    )
    jupiter_slippage_bps: int = Field(
        default=100, ge=1, le=1000, description="Default slippage in basis points (100 = 1%)"
    )
    jupiter_max_slippage_bps: int = Field(default=500, ge=100, le=5000)

    # DexScreener
    dexscreener_api_url: str = Field(
        default="https://api.dexscreener.com/latest", description="DexScreener API base URL"
    )

    birdeye_api_key: SecretStr = Field(
        default=SecretStr(""), description="Birdeye API key (optional fallback)"
    )
    birdeye_api_url: str = Field(
        default="https://public-api.birdeye.so", description="Birdeye API base URL"
    )

    # Solana
    solana_rpc_url: str = Field(
        default="https://api.mainnet-beta.solana.com", description="Solana RPC endpoint"
    )
    solana_fallback_rpcs: str = Field(default="", description="Fallback RPC endpoints")
    solana_rpc_timeout: int = Field(
        default=30, ge=5, le=120, description="Solana RPC timeout in seconds"
    )
    trading_wallet_private_key: SecretStr = Field(
        default=SecretStr(""), description="Trading wallet private key (base58)"
    )

    # Trading Configuration
    max_concurrent_positions: int = Field(
        default=5, ge=1, le=20, description="Maximum concurrent open positions"
    )
    base_position_size_sol: float = Field(default=0.1, ge=0.01, le=10.0)
    base_position_size_pct: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Base position size as % of capital"
    )
    max_position_size_sol: float = Field(default=0.5, ge=0.1, le=100.0)
    score_threshold: float = Field(
        default=0.70, ge=0.0, le=1.0, description="Minimum score for trade eligibility"
    )
    high_conviction_threshold: float = Field(
        default=0.85, ge=0.0, le=1.0, description="Score threshold for high conviction"
    )
    high_conviction_multiplier: float = Field(
        default=1.5, ge=1.0, le=3.0, description="Position size multiplier for high conviction"
    )
    standard_multiplier: float = Field(default=1.0, ge=0.5, le=2.0)

    # Risk Management
    max_drawdown_percent: float = Field(default=20.0, ge=5.0, le=50.0)
    drawdown_threshold_pct: float = Field(
        default=20.0, ge=5.0, le=50.0, description="Drawdown % to trigger circuit breaker"
    )
    min_win_rate_percent: float = Field(default=40.0, ge=20.0, le=60.0)
    win_rate_threshold_pct: float = Field(
        default=40.0, ge=20.0, le=60.0, description="Win rate % to trigger circuit breaker"
    )
    win_rate_trade_window: int = Field(default=50, ge=10, le=200)
    win_rate_window_size: int = Field(
        default=50, ge=10, le=200, description="Number of trades for win rate calculation"
    )
    max_consecutive_losses: int = Field(default=3, ge=2, le=10)
    consecutive_loss_threshold: int = Field(
        default=3, ge=2, le=10, description="Consecutive losses to reduce position size"
    )
    consecutive_loss_size_reduction: float = Field(default=0.5, ge=0.1, le=1.0)
    position_size_reduction_factor: float = Field(
        default=0.5, ge=0.1, le=1.0, description="Factor to reduce position size after losses"
    )
    max_daily_trades: int = Field(default=20, ge=1, le=100)
    max_position_hold_hours: int = Field(default=24, ge=1, le=168)

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

    # Exit Strategy
    default_stop_loss_percent: float = Field(default=50.0, ge=10.0, le=90.0)
    default_tp1_multiplier: float = Field(default=2.0, ge=1.1, le=10.0)
    default_tp1_sell_percent: float = Field(default=33.0, ge=10.0, le=100.0)
    default_tp2_multiplier: float = Field(default=3.0, ge=1.5, le=20.0)
    default_tp2_sell_percent: float = Field(default=33.0, ge=0.0, le=100.0)
    default_tp3_multiplier: float = Field(default=5.0, ge=2.0, le=50.0)
    default_tp3_sell_percent: float = Field(default=34.0, ge=0.0, le=100.0)
    trailing_stop_activation_multiplier: float = Field(default=2.0, ge=1.1, le=10.0)
    trailing_stop_distance_percent: float = Field(default=30.0, ge=5.0, le=50.0)
    default_moonbag_percent: float = Field(default=0.0, ge=0.0, le=50.0)

    # Discovery
    discovery_schedule: str = Field(default="0 */6 * * *")
    min_wallet_win_rate: float = Field(default=50.0, ge=30.0, le=80.0)
    min_wallet_total_trades: int = Field(default=10, ge=5, le=100)
    min_wallet_pnl_sol: float = Field(default=1.0, ge=0.1, le=100.0)
    decay_rolling_window: int = Field(default=20, ge=10, le=100)
    decay_win_rate_threshold: float = Field(default=40.0, ge=20.0, le=60.0)

    # Cluster Detection
    funding_min_amount_sol: float = Field(default=0.1, ge=0.01, le=10.0)
    sync_buy_window_minutes: int = Field(default=5, ge=1, le=60)
    cooccurrence_min_tokens: int = Field(default=3, ge=2, le=10)
    cooccurrence_time_window_hours: int = Field(default=24, ge=1, le=168)
    min_cluster_size: int = Field(default=3, ge=2, le=20)
    min_cluster_strength: float = Field(default=0.3, ge=0.1, le=1.0)

    # Signal Processing
    amplification_window_seconds: int = Field(default=600, ge=60, le=3600)
    min_active_members_for_amplification: int = Field(default=2, ge=2, le=10)
    base_amplification_factor: float = Field(default=1.2, ge=1.0, le=2.0)
    max_amplification_factor: float = Field(default=1.8, ge=1.2, le=3.0)
    min_token_age_seconds: int = Field(default=300, ge=0, le=3600)
    max_token_age_hours: int = Field(default=24, ge=1, le=168)
    min_liquidity_usd: float = Field(default=10000.0, ge=1000.0, le=1000000.0)
    max_market_cap_usd: float = Field(default=10000000.0, ge=100000.0, le=1000000000.0)

    # Gradio Dashboard
    ui_port: int = Field(default=7860, ge=1024, le=65535)
    ui_host: str = Field(default="0.0.0.0")
    ui_share: bool = Field(default=False)
    api_base_url: str = Field(
        default="",
        description="API base URL for dashboard (leave empty for localhost:port)",
    )

    # Optional Services
    discord_webhook_url: str = Field(default="")
    telegram_bot_token: str = Field(default="")
    telegram_chat_id: str = Field(default="")
    redis_host: str = Field(default="localhost")
    redis_port: int = Field(default=6379, ge=1, le=65535)
    redis_db: int = Field(default=0, ge=0, le=15)
    redis_password: str = Field(default="")
    storage_enabled: bool = Field(default=False)
    storage_endpoint: str = Field(default="http://localhost:9010")
    storage_user: str = Field(default="minio")
    storage_password: str = Field(default="miniopass")
    storage_bucket_name: str = Field(default="walltrack")

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
    return Settings()
