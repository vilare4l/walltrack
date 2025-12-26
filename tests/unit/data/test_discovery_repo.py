"""Tests for DiscoveryRepository."""

from datetime import datetime, UTC
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from walltrack.data.supabase.client import SupabaseClient
from walltrack.data.supabase.repositories.discovery_repo import DiscoveryRepository
from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunParams,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a mock SupabaseClient."""
    client = MagicMock(spec=SupabaseClient)
    client.insert = AsyncMock()
    client.select = AsyncMock()
    client.update = AsyncMock()
    return client


@pytest.fixture
def repo(mock_client: MagicMock) -> DiscoveryRepository:
    """Create a DiscoveryRepository with mocked client."""
    return DiscoveryRepository(mock_client)


class TestDiscoveryRepositoryInit:
    """Tests for DiscoveryRepository initialization."""

    def test_init_sets_client(self, mock_client: MagicMock) -> None:
        """Test that client is set on init."""
        repo = DiscoveryRepository(mock_client)
        assert repo.client == mock_client

    def test_init_sets_table_names(self, mock_client: MagicMock) -> None:
        """Test that table names are set correctly."""
        repo = DiscoveryRepository(mock_client)
        assert repo.runs_table == "discovery_runs"
        assert repo.wallets_table == "discovery_run_wallets"


class TestCreateRun:
    """Tests for create_run method."""

    async def test_create_run_inserts_data(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that create_run inserts data to database."""
        params = {
            "min_price_change_pct": 100.0,
            "min_volume_usd": 50000.0,
        }

        await repo.create_run(
            trigger_type=TriggerType.MANUAL,
            params=params,
            triggered_by="test_user",
        )

        mock_client.insert.assert_called_once()
        call_args = mock_client.insert.call_args
        assert call_args[0][0] == "discovery_runs"

    async def test_create_run_returns_discovery_run(
        self,
        repo: DiscoveryRepository,
    ) -> None:
        """Test that create_run returns a DiscoveryRun object."""
        result = await repo.create_run(
            trigger_type=TriggerType.SCHEDULED,
            params={},
            triggered_by="scheduler",
        )

        assert isinstance(result, DiscoveryRun)
        assert result.trigger_type == TriggerType.SCHEDULED
        assert result.triggered_by == "scheduler"
        assert result.status == RunStatus.RUNNING

    async def test_create_run_generates_uuid(
        self,
        repo: DiscoveryRepository,
    ) -> None:
        """Test that create_run generates a valid UUID."""
        result = await repo.create_run(
            trigger_type=TriggerType.API,
            params={},
        )

        assert result.id is not None
        # Should be a valid UUID (no exception)
        str(result.id)


class TestCompleteRun:
    """Tests for complete_run method."""

    async def test_complete_run_updates_database(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that complete_run updates the database."""
        run_id = uuid4()

        await repo.complete_run(
            run_id=run_id,
            tokens_analyzed=10,
            new_wallets=25,
            updated_wallets=5,
            profiled_wallets=20,
            duration_seconds=120.5,
            errors=[],
        )

        mock_client.update.assert_called_once()
        call_args = mock_client.update.call_args
        assert call_args[0][0] == "discovery_runs"
        assert call_args[0][1] == {"id": str(run_id)}

    async def test_complete_run_sets_completed_status(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that complete_run sets status to COMPLETED."""
        run_id = uuid4()

        await repo.complete_run(
            run_id=run_id,
            tokens_analyzed=0,
            new_wallets=0,
            updated_wallets=0,
            profiled_wallets=0,
            duration_seconds=1.0,
            errors=[],
        )

        call_args = mock_client.update.call_args
        update_data = call_args[0][2]
        assert update_data["status"] == "completed"


class TestFailRun:
    """Tests for fail_run method."""

    async def test_fail_run_updates_database(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that fail_run updates the database."""
        run_id = uuid4()

        await repo.fail_run(run_id, "Test error")

        mock_client.update.assert_called_once()
        call_args = mock_client.update.call_args
        update_data = call_args[0][2]
        assert update_data["status"] == "failed"
        assert update_data["errors"] == ["Test error"]


class TestCancelRun:
    """Tests for cancel_run method."""

    async def test_cancel_run_updates_database(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that cancel_run updates the database."""
        run_id = uuid4()

        await repo.cancel_run(run_id)

        mock_client.update.assert_called_once()
        call_args = mock_client.update.call_args
        update_data = call_args[0][2]
        assert update_data["status"] == "cancelled"


class TestGetRun:
    """Tests for get_run method."""

    async def test_get_run_returns_none_when_not_found(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_run returns None when run not found."""
        mock_client.select.return_value = []

        result = await repo.get_run(uuid4())

        assert result is None

    async def test_get_run_returns_discovery_run_when_found(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_run returns DiscoveryRun when found."""
        run_id = uuid4()
        mock_client.select.return_value = [
            {
                "id": str(run_id),
                "started_at": "2024-01-01T12:00:00+00:00",
                "completed_at": None,
                "status": "running",
                "trigger_type": "manual",
                "triggered_by": "test",
                "min_price_change_pct": 100.0,
                "min_volume_usd": 50000.0,
                "max_token_age_hours": 72,
                "early_window_minutes": 30,
                "min_profit_pct": 50.0,
                "max_tokens": 20,
                "tokens_analyzed": 5,
                "new_wallets": 10,
                "updated_wallets": 2,
                "profiled_wallets": 8,
                "duration_seconds": 60.0,
                "errors": [],
            }
        ]

        result = await repo.get_run(run_id)

        assert result is not None
        assert isinstance(result, DiscoveryRun)
        assert result.id == run_id
        assert result.status == RunStatus.RUNNING
        assert result.new_wallets == 10


class TestGetRuns:
    """Tests for get_runs method."""

    async def test_get_runs_returns_empty_list_when_none(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_runs returns empty list when no runs."""
        mock_client.select.return_value = []

        result = await repo.get_runs()

        assert result == []

    async def test_get_runs_filters_by_status(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_runs can filter by status."""
        mock_client.select.return_value = []

        await repo.get_runs(status=RunStatus.COMPLETED)

        call_args = mock_client.select.call_args
        assert call_args[1]["filters"] == {"status": "completed"}


class TestGetStats:
    """Tests for get_stats method."""

    async def test_get_stats_returns_empty_when_no_runs(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_stats returns empty stats when no runs."""
        mock_client.select.return_value = []

        result = await repo.get_stats()

        assert isinstance(result, DiscoveryStats)
        assert result.total_runs == 0
        assert result.successful_runs == 0

    async def test_get_stats_calculates_correctly(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_stats calculates statistics correctly."""
        run1_id = uuid4()
        run2_id = uuid4()
        mock_client.select.return_value = [
            {
                "id": str(run1_id),
                "started_at": "2024-01-02T12:00:00+00:00",
                "completed_at": "2024-01-02T12:01:00+00:00",
                "status": "completed",
                "trigger_type": "manual",
                "triggered_by": None,
                "min_price_change_pct": 100.0,
                "min_volume_usd": 50000.0,
                "max_token_age_hours": 72,
                "early_window_minutes": 30,
                "min_profit_pct": 50.0,
                "max_tokens": 20,
                "tokens_analyzed": 10,
                "new_wallets": 20,
                "updated_wallets": 5,
                "profiled_wallets": 15,
                "duration_seconds": 60.0,
                "errors": [],
            },
            {
                "id": str(run2_id),
                "started_at": "2024-01-01T12:00:00+00:00",
                "completed_at": "2024-01-01T12:02:00+00:00",
                "status": "failed",
                "trigger_type": "scheduled",
                "triggered_by": "scheduler",
                "min_price_change_pct": 100.0,
                "min_volume_usd": 50000.0,
                "max_token_age_hours": 72,
                "early_window_minutes": 30,
                "min_profit_pct": 50.0,
                "max_tokens": 20,
                "tokens_analyzed": 5,
                "new_wallets": 10,
                "updated_wallets": 2,
                "profiled_wallets": 0,
                "duration_seconds": 120.0,
                "errors": ["error"],
            },
        ]

        result = await repo.get_stats()

        assert result.total_runs == 2
        assert result.successful_runs == 1
        assert result.failed_runs == 1
        assert result.total_wallets_discovered == 30  # 20 + 10
        assert result.total_wallets_updated == 7  # 5 + 2
        assert result.avg_wallets_per_run == 15.0  # 30 / 2


class TestAddWalletToRun:
    """Tests for add_wallet_to_run method."""

    async def test_add_wallet_inserts_data(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that add_wallet_to_run inserts data."""
        run_id = uuid4()

        await repo.add_wallet_to_run(
            run_id=run_id,
            wallet_address="ABC123",
            source_token="TOKEN456",
            is_new=True,
            initial_score=0.85,
        )

        mock_client.insert.assert_called_once()
        call_args = mock_client.insert.call_args
        assert call_args[0][0] == "discovery_run_wallets"
        data = call_args[0][1]
        assert data["run_id"] == str(run_id)
        assert data["wallet_address"] == "ABC123"
        assert data["source_token"] == "TOKEN456"
        assert data["is_new"] is True
        assert data["initial_score"] == 0.85


class TestGetRunWallets:
    """Tests for get_run_wallets method."""

    async def test_get_run_wallets_returns_empty_when_none(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_run_wallets returns empty list when none."""
        mock_client.select.return_value = []

        result = await repo.get_run_wallets(uuid4())

        assert result == []

    async def test_get_run_wallets_returns_wallets(
        self,
        repo: DiscoveryRepository,
        mock_client: MagicMock,
    ) -> None:
        """Test that get_run_wallets returns wallet records."""
        run_id = uuid4()
        wallet_id = uuid4()
        mock_client.select.return_value = [
            {
                "id": str(wallet_id),
                "run_id": str(run_id),
                "wallet_address": "ABC123",
                "source_token": "TOKEN456",
                "is_new": True,
                "initial_score": 0.9,
                "created_at": "2024-01-01T12:00:00+00:00",
            }
        ]

        result = await repo.get_run_wallets(run_id)

        assert len(result) == 1
        assert result[0].wallet_address == "ABC123"
        assert result[0].initial_score == 0.9


class TestRowToRun:
    """Tests for _row_to_run helper method."""

    def test_row_to_run_parses_correctly(
        self,
        repo: DiscoveryRepository,
    ) -> None:
        """Test that _row_to_run converts database row correctly."""
        run_id = uuid4()
        row = {
            "id": str(run_id),
            "started_at": "2024-01-01T12:00:00Z",
            "completed_at": "2024-01-01T12:05:00Z",
            "status": "completed",
            "trigger_type": "api",
            "triggered_by": "api_user",
            "min_price_change_pct": 150.0,
            "min_volume_usd": 75000.0,
            "max_token_age_hours": 48,
            "early_window_minutes": 15,
            "min_profit_pct": 60.0,
            "max_tokens": 10,
            "tokens_analyzed": 8,
            "new_wallets": 15,
            "updated_wallets": 3,
            "profiled_wallets": 12,
            "duration_seconds": 300.5,
            "errors": ["err1"],
        }

        result = repo._row_to_run(row)

        assert result.id == run_id
        assert result.status == RunStatus.COMPLETED
        assert result.trigger_type == TriggerType.API
        assert result.triggered_by == "api_user"
        assert result.params.min_price_change_pct == 150.0
        assert result.params.max_tokens == 10
        assert result.new_wallets == 15
        assert result.duration_seconds == 300.5
        assert result.errors == ["err1"]
