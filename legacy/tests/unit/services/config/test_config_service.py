"""Tests for ConfigService."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.services.config import (
    ConfigService,
    TradingConfig,
    reset_config_service,
)


@pytest.fixture
def config_service():
    """Create a fresh config service for each test."""
    reset_config_service()
    return ConfigService(cache_ttl_seconds=60)


@pytest.fixture
def mock_supabase_client():
    """Create a mock Supabase client.

    Note: Use MagicMock for the client because table(), select(), eq(), single()
    are synchronous - only execute() is async.
    """
    client = MagicMock()
    return client


class TestConfigServiceGet:
    """Tests for ConfigService.get() method."""

    @pytest.mark.asyncio
    async def test_get_returns_value_from_db(self, config_service, mock_supabase_client):
        """Test that get() returns value from database."""
        # Setup mock
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "id": 1,
                "name": "Active Configuration",
                "status": "active",
                "version": 1,
                "score_threshold": "0.75",
                "base_position_size_pct": "2.0",
                "min_position_sol": "0.01",
                "max_position_sol": "1.0",
                "max_concurrent_positions": 5,
                "high_conviction_threshold": "0.85",
                "high_conviction_multiplier": "1.5",
                "min_token_age_seconds": 300,
                "max_token_age_hours": 24,
                "min_liquidity_usd": "10000.0",
                "max_market_cap_usd": "10000000.0",
                "max_position_hold_hours": 24,
                "max_daily_trades": 20,
            })
        )

        # Inject mock client directly
        config_service._client = mock_supabase_client
        value = await config_service.get("trading.score_threshold")

        assert value == Decimal("0.75")

    @pytest.mark.asyncio
    async def test_get_returns_default_for_invalid_key(self, config_service):
        """Test that get() returns default for invalid key format."""
        value = await config_service.get("invalid_key", default="fallback")
        assert value == "fallback"

    @pytest.mark.asyncio
    async def test_get_uses_cache(self, config_service, mock_supabase_client):
        """Test that get() uses cache for subsequent calls."""
        # Setup mock
        mock_execute = AsyncMock(return_value=MagicMock(data={
            "id": 1,
            "name": "Active Configuration",
            "status": "active",
            "version": 1,
            "score_threshold": "0.70",
            "base_position_size_pct": "2.0",
            "min_position_sol": "0.01",
            "max_position_sol": "1.0",
            "max_concurrent_positions": 5,
            "high_conviction_threshold": "0.85",
            "high_conviction_multiplier": "1.5",
            "min_token_age_seconds": 300,
            "max_token_age_hours": 24,
            "min_liquidity_usd": "10000.0",
            "max_market_cap_usd": "10000000.0",
            "max_position_hold_hours": 24,
            "max_daily_trades": 20,
        }))
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = mock_execute

        # Inject mock client directly
        config_service._client = mock_supabase_client

        # First call
        value1 = await config_service.get("trading.score_threshold")
        # Second call should use cache
        value2 = await config_service.get("trading.score_threshold")

        assert value1 == value2
        # Execute should only be called once (for block fetch)
        assert mock_execute.call_count == 1


class TestConfigServiceGetBlock:
    """Tests for ConfigService.get_block() method."""

    @pytest.mark.asyncio
    async def test_get_block_returns_typed_model(self, config_service, mock_supabase_client):
        """Test that get_block() returns correctly typed Pydantic model."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "id": 1,
                "name": "Active Configuration",
                "status": "active",
                "version": 1,
                "score_threshold": "0.70",
                "base_position_size_pct": "2.0",
                "min_position_sol": "0.01",
                "max_position_sol": "1.0",
                "max_concurrent_positions": 5,
                "high_conviction_threshold": "0.85",
                "high_conviction_multiplier": "1.5",
                "min_token_age_seconds": 300,
                "max_token_age_hours": 24,
                "min_liquidity_usd": "10000.0",
                "max_market_cap_usd": "10000000.0",
                "max_position_hold_hours": 24,
                "max_daily_trades": 20,
            })
        )

        config_service._client = mock_supabase_client
        block = await config_service.get_block("trading")

        assert isinstance(block, TradingConfig)
        assert block.score_threshold == Decimal("0.70")
        assert block.max_concurrent_positions == 5

    @pytest.mark.asyncio
    async def test_get_block_returns_fallback_on_error(self, config_service, mock_supabase_client):
        """Test that get_block() returns fallback on database error."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            side_effect=Exception("DB connection failed")
        )

        config_service._client = mock_supabase_client
        block = await config_service.get_block("trading")

        # Should return fallback
        assert isinstance(block, TradingConfig)
        assert block.name == "Fallback"

    @pytest.mark.asyncio
    async def test_get_block_returns_none_for_unknown_table(self, config_service):
        """Test that get_block() returns None for unknown table."""
        block = await config_service.get_block("unknown_table")
        assert block is None


class TestConfigServiceRefresh:
    """Tests for ConfigService.refresh() method."""

    @pytest.mark.asyncio
    async def test_refresh_clears_specific_table_cache(self, config_service, mock_supabase_client):
        """Test that refresh() clears cache for specific table."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "id": 1,
                "name": "Active Configuration",
                "status": "active",
                "version": 1,
                "score_threshold": "0.70",
                "base_position_size_pct": "2.0",
                "min_position_sol": "0.01",
                "max_position_sol": "1.0",
                "max_concurrent_positions": 5,
                "high_conviction_threshold": "0.85",
                "high_conviction_multiplier": "1.5",
                "min_token_age_seconds": 300,
                "max_token_age_hours": 24,
                "min_liquidity_usd": "10000.0",
                "max_market_cap_usd": "10000000.0",
                "max_position_hold_hours": 24,
                "max_daily_trades": 20,
            })
        )

        config_service._client = mock_supabase_client

        # Populate cache
        await config_service.get("trading.score_threshold")

        # Refresh
        await config_service.refresh("trading")

        # Cache should be empty for trading
        assert "block:trading" not in config_service._block_cache
        assert "trading.score_threshold" not in config_service._cache

    @pytest.mark.asyncio
    async def test_refresh_all_clears_all_caches(self, config_service):
        """Test that refresh() without table clears all caches."""
        # Add some items to cache
        config_service._cache["trading.value"] = 1
        config_service._cache["scoring.value"] = 2
        config_service._block_cache["block:trading"] = MagicMock()

        # Refresh all
        await config_service.refresh()

        assert len(config_service._cache) == 0
        assert len(config_service._block_cache) == 0


class TestTypedHelpers:
    """Tests for typed helper methods."""

    @pytest.mark.asyncio
    async def test_get_trading_config_returns_typed(self, config_service, mock_supabase_client):
        """Test get_trading_config() returns TradingConfig."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={
                "id": 1,
                "name": "Active Configuration",
                "status": "active",
                "version": 1,
                "score_threshold": "0.70",
                "base_position_size_pct": "2.0",
                "min_position_sol": "0.01",
                "max_position_sol": "1.0",
                "max_concurrent_positions": 5,
                "high_conviction_threshold": "0.85",
                "high_conviction_multiplier": "1.5",
                "min_token_age_seconds": 300,
                "max_token_age_hours": 24,
                "min_liquidity_usd": "10000.0",
                "max_market_cap_usd": "10000000.0",
                "max_position_hold_hours": 24,
                "max_daily_trades": 20,
            })
        )

        config_service._client = mock_supabase_client
        config = await config_service.get_trading_config()

        assert isinstance(config, TradingConfig)

    @pytest.mark.asyncio
    async def test_get_trading_config_returns_fallback_on_none(self, config_service, mock_supabase_client):
        """Test get_trading_config() returns fallback when DB returns None."""
        mock_supabase_client.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        config_service._client = mock_supabase_client
        config = await config_service.get_trading_config()

        assert isinstance(config, TradingConfig)
        assert config.name == "Fallback"
