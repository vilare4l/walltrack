"""Position sizing settings from environment."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings


class PositionSettings(BaseSettings):
    """Position sizing settings from environment."""

    # Default values (can be overridden in DB)
    default_base_position_pct: float = Field(default=2.0)
    default_min_position_sol: float = Field(default=0.01)
    default_max_position_sol: float = Field(default=1.0)
    default_max_concurrent_positions: int = Field(default=5)

    # Cache settings
    config_cache_ttl_seconds: int = Field(default=60)

    model_config = {
        "env_prefix": "POSITION_",
        "env_file": ".env",
        "extra": "ignore",
    }


@lru_cache
def get_position_settings() -> PositionSettings:
    """Get position settings singleton."""
    return PositionSettings()
