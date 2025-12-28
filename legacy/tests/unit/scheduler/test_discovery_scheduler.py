"""Tests for DiscoveryScheduler."""

from datetime import datetime, timedelta, UTC
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.discovery.models import DiscoveryRunParams
from walltrack.scheduler.discovery_scheduler import (
    DiscoveryScheduler,
    get_discovery_scheduler,
    reset_scheduler,
)


@pytest.fixture
def mock_supabase() -> MagicMock:
    """Create mock Supabase client."""
    client = MagicMock()
    client.select = AsyncMock(return_value=[])
    client.update = AsyncMock()
    return client


@pytest.fixture
def scheduler() -> DiscoveryScheduler:
    """Create a fresh scheduler instance."""
    return DiscoveryScheduler()


class TestDiscoverySchedulerInit:
    """Tests for DiscoveryScheduler initialization."""

    def test_init_default_values(self, scheduler: DiscoveryScheduler) -> None:
        """Test that scheduler initializes with default values."""
        assert scheduler.enabled is True
        assert scheduler.schedule_hours == 6
        assert scheduler.next_run is None
        assert scheduler.last_run is None
        assert scheduler.is_running is False

    def test_init_default_params(self, scheduler: DiscoveryScheduler) -> None:
        """Test that scheduler initializes with default params."""
        params = scheduler.params
        assert params.min_price_change_pct == 100.0
        assert params.min_volume_usd == 50000.0
        assert params.max_tokens == 20


class TestLoadConfig:
    """Tests for load_config method."""

    async def test_load_config_from_database(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test loading config from database."""
        mock_supabase.select.side_effect = [
            # First call: discovery_config
            [
                {
                    "enabled": False,
                    "schedule_hours": 12,
                    "min_price_change_pct": 150.0,
                    "min_volume_usd": 75000.0,
                    "max_token_age_hours": 48,
                    "early_window_minutes": 20,
                    "min_profit_pct": 60.0,
                    "max_tokens": 30,
                }
            ],
            # Second call: last run
            [],
        ]

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.load_config()

        assert scheduler.enabled is False
        assert scheduler.schedule_hours == 12
        assert scheduler.params.min_price_change_pct == 150.0
        assert scheduler.params.max_tokens == 30

    async def test_load_config_uses_defaults_when_empty(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test loading config uses defaults when DB is empty."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.load_config()

        assert scheduler.enabled is True
        assert scheduler.schedule_hours == 6

    async def test_load_config_calculates_next_run(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that load_config calculates next run time."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.load_config()

        assert scheduler.next_run is not None
        # Next run should be approximately 6 hours from now
        expected = datetime.now(UTC) + timedelta(hours=6)
        assert abs((scheduler.next_run - expected).total_seconds()) < 10


class TestSaveConfig:
    """Tests for save_config method."""

    async def test_save_config_updates_database(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that save_config updates database."""
        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.save_config(
                enabled=False,
                schedule_hours=12,
                updated_by="test_user",
            )

        mock_supabase.update.assert_called_once()
        call_args = mock_supabase.update.call_args
        assert call_args[0][0] == "discovery_config"
        assert call_args[0][2]["enabled"] is False
        assert call_args[0][2]["schedule_hours"] == 12

    async def test_save_config_updates_scheduler_state(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that save_config updates scheduler state."""
        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.save_config(enabled=False, schedule_hours=8)

        assert scheduler.enabled is False
        assert scheduler.schedule_hours == 8

    async def test_save_config_with_params(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test saving config with custom params."""
        params = DiscoveryRunParams(max_tokens=50)

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.save_config(params=params)

        assert scheduler.params.max_tokens == 50


class TestCalculateNextRun:
    """Tests for _calculate_next_run method."""

    def test_next_run_disabled_returns_none(
        self,
        scheduler: DiscoveryScheduler,
    ) -> None:
        """Test that next_run is None when disabled."""
        scheduler._enabled = False
        scheduler._calculate_next_run()
        assert scheduler.next_run is None

    def test_next_run_from_last_run(
        self,
        scheduler: DiscoveryScheduler,
    ) -> None:
        """Test calculating next run from last run."""
        last_run = datetime.now(UTC) - timedelta(hours=2)
        scheduler._last_run = last_run
        scheduler._schedule_hours = 6
        scheduler._calculate_next_run()

        expected = last_run + timedelta(hours=6)
        assert scheduler.next_run == expected

    def test_next_run_in_past_schedules_future(
        self,
        scheduler: DiscoveryScheduler,
    ) -> None:
        """Test that past next_run is rescheduled to future."""
        # Set last run 10 hours ago (past the 6 hour interval)
        last_run = datetime.now(UTC) - timedelta(hours=10)
        scheduler._last_run = last_run
        scheduler._schedule_hours = 6
        scheduler._calculate_next_run()

        # Should be scheduled for 6 hours from now, not 4 hours ago
        assert scheduler.next_run is not None
        assert scheduler.next_run > datetime.now(UTC)


class TestStartStop:
    """Tests for start and stop methods."""

    async def test_start_loads_config(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that start loads config."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.start()

        assert scheduler.is_running is True
        await scheduler.stop()

    async def test_start_creates_task(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that start creates background task."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.start()

        assert scheduler._task is not None
        await scheduler.stop()

    async def test_stop_cancels_task(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that stop cancels the task."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.start()
            await scheduler.stop()

        assert scheduler.is_running is False

    async def test_start_twice_is_noop(
        self,
        scheduler: DiscoveryScheduler,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that starting twice doesn't create duplicate tasks."""
        mock_supabase.select.return_value = []

        with patch(
            "walltrack.scheduler.discovery_scheduler.get_supabase_client",
            return_value=mock_supabase,
        ):
            await scheduler.start()
            task = scheduler._task
            await scheduler.start()

        assert scheduler._task == task  # Same task
        await scheduler.stop()


class TestSingleton:
    """Tests for singleton pattern."""

    async def test_get_discovery_scheduler_returns_same_instance(self) -> None:
        """Test that get_discovery_scheduler returns same instance."""
        await reset_scheduler()

        scheduler1 = await get_discovery_scheduler()
        scheduler2 = await get_discovery_scheduler()

        assert scheduler1 is scheduler2
        await reset_scheduler()

    async def test_reset_scheduler_clears_instance(self) -> None:
        """Test that reset_scheduler clears the instance."""
        scheduler1 = await get_discovery_scheduler()
        await reset_scheduler()
        scheduler2 = await get_discovery_scheduler()

        assert scheduler1 is not scheduler2
        await reset_scheduler()


class TestProperties:
    """Tests for scheduler properties."""

    def test_enabled_property(self, scheduler: DiscoveryScheduler) -> None:
        """Test enabled property."""
        assert scheduler.enabled is True
        scheduler._enabled = False
        assert scheduler.enabled is False

    def test_schedule_hours_property(self, scheduler: DiscoveryScheduler) -> None:
        """Test schedule_hours property."""
        assert scheduler.schedule_hours == 6
        scheduler._schedule_hours = 12
        assert scheduler.schedule_hours == 12

    def test_params_property(self, scheduler: DiscoveryScheduler) -> None:
        """Test params property."""
        params = scheduler.params
        assert isinstance(params, DiscoveryRunParams)

    def test_is_running_property(self, scheduler: DiscoveryScheduler) -> None:
        """Test is_running property."""
        assert scheduler.is_running is False
        scheduler._running = True
        assert scheduler.is_running is True
