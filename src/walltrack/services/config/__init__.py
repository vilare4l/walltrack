"""Centralized configuration service.

This module provides:
- ConfigService: Cached configuration access with hot-reload
- Pydantic models for each config domain

Usage:
    from walltrack.services.config import get_config_service

    service = await get_config_service()
    trading_config = await service.get_trading_config()
    score_threshold = await service.get("trading.score_threshold")
"""

from .config_service import (
    ConfigService,
    get_config_service,
    reset_config_service,
)
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

__all__ = [
    # Service
    "ConfigService",
    "get_config_service",
    "reset_config_service",
    # Models
    "ConfigBase",
    "TradingConfig",
    "ScoringConfig",
    "DiscoveryConfig",
    "ClusterConfig",
    "RiskConfig",
    "ExitConfig",
    "ApiConfig",
    "CONFIG_MODELS",
]
