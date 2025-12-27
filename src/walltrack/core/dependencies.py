"""Dependency injection setup for services.

Provides a centralized ServiceContainer for managing service instances
and their dependencies throughout the application lifecycle.
"""

from typing import Optional

import structlog

from walltrack.services.config.config_service import ConfigService, get_config_service

logger = structlog.get_logger(__name__)


class ServiceContainer:
    """Container for dependency injection.

    Provides lazy initialization and caching of service instances.
    Use this to ensure consistent service instances across the application.

    Usage:
        container = await ServiceContainer.get_instance()
        config = container.config
    """

    _instance: Optional["ServiceContainer"] = None
    _config_service: Optional[ConfigService] = None
    _initialized: bool = False

    @classmethod
    async def get_instance(cls) -> "ServiceContainer":
        """Get or create service container."""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._initialize()
        return cls._instance

    async def _initialize(self) -> None:
        """Initialize all services."""
        if self._initialized:
            return

        self._config_service = await get_config_service()
        self._initialized = True

        logger.info("service_container_initialized")

    @property
    def config(self) -> ConfigService:
        """Get config service."""
        if self._config_service is None:
            raise RuntimeError("ServiceContainer not initialized. Call get_instance() first.")
        return self._config_service

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None
        cls._config_service = None


async def get_config() -> ConfigService:
    """Get config service via container.

    Convenience function for quick access to ConfigService.

    Usage:
        config = await get_config()
        threshold = await config.get("trading.score_threshold")
    """
    container = await ServiceContainer.get_instance()
    return container.config
