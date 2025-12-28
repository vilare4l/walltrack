"""Repository for dynamic configuration stored in Supabase."""

from typing import Any

import structlog
from supabase import Client

from walltrack.data.models.config import DynamicConfig, ScoringWeights

log = structlog.get_logger()


class ConfigRepository:
    """Repository for runtime configuration."""

    def __init__(self, client: Client, schema: str = "walltrack") -> None:
        """Initialize the config repository.

        Args:
            client: Supabase client instance.
            schema: Database schema name.
        """
        self.client = client
        self.schema = schema
        self.table = "config"

    def _table(self) -> Any:
        """Get table reference with schema."""
        return self.client.schema(self.schema).table(self.table)

    async def get_config(self, key: str) -> Any | None:
        """Get a configuration value by key.

        Args:
            key: Configuration key to retrieve.

        Returns:
            Configuration value or None if not found.
        """
        response = self._table().select("value").eq("key", key).single().execute()
        return response.data.get("value") if response.data else None

    async def set_config(self, key: str, value: Any) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key.
            value: Configuration value (will be stored as JSONB).
        """
        self._table().upsert({"key": key, "value": value}).execute()
        log.info("config_updated", key=key)

    async def get_scoring_weights(self) -> ScoringWeights:
        """Get current scoring weights.

        Returns:
            ScoringWeights instance with current values.
        """
        weights = await self.get_config("scoring_weights")
        return ScoringWeights(**(weights or {}))

    async def set_scoring_weights(self, weights: ScoringWeights) -> None:
        """Set scoring weights.

        Args:
            weights: New scoring weights to save.

        Raises:
            ValueError: If weights don't sum to 1.0.
        """
        if not weights.validate_sum():
            raise ValueError("Scoring weights must sum to 1.0")
        await self.set_config("scoring_weights", weights.model_dump())

    async def get_score_threshold(self) -> float:
        """Get current score threshold.

        Returns:
            Score threshold value.
        """
        threshold = await self.get_config("score_threshold")
        return float(threshold) if threshold else 0.70

    async def get_all_config(self) -> DynamicConfig:
        """Get all dynamic configuration.

        Returns:
            DynamicConfig instance with all values.
        """
        response = self._table().select("*").execute()
        config_dict = {row["key"]: row["value"] for row in response.data}
        return DynamicConfig(**config_dict)
