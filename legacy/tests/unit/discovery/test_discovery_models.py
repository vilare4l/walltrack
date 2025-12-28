"""Unit tests for discovery models."""

from datetime import datetime, UTC
from uuid import uuid4

import pytest

from walltrack.discovery.models import (
    DiscoveryRun,
    DiscoveryRunCreate,
    DiscoveryRunParams,
    DiscoveryRunUpdate,
    DiscoveryRunWallet,
    DiscoveryStats,
    RunStatus,
    TriggerType,
)


class TestRunStatus:
    """Tests for RunStatus enum."""

    def test_running_value(self) -> None:
        """Test RUNNING status value."""
        assert RunStatus.RUNNING.value == "running"

    def test_completed_value(self) -> None:
        """Test COMPLETED status value."""
        assert RunStatus.COMPLETED.value == "completed"

    def test_failed_value(self) -> None:
        """Test FAILED status value."""
        assert RunStatus.FAILED.value == "failed"

    def test_cancelled_value(self) -> None:
        """Test CANCELLED status value."""
        assert RunStatus.CANCELLED.value == "cancelled"

    def test_from_string(self) -> None:
        """Test creating status from string."""
        status = RunStatus("running")
        assert status == RunStatus.RUNNING


class TestTriggerType:
    """Tests for TriggerType enum."""

    def test_manual_value(self) -> None:
        """Test MANUAL trigger value."""
        assert TriggerType.MANUAL.value == "manual"

    def test_scheduled_value(self) -> None:
        """Test SCHEDULED trigger value."""
        assert TriggerType.SCHEDULED.value == "scheduled"

    def test_api_value(self) -> None:
        """Test API trigger value."""
        assert TriggerType.API.value == "api"


class TestDiscoveryRunParams:
    """Tests for DiscoveryRunParams model."""

    def test_default_values(self) -> None:
        """Test default parameter values."""
        params = DiscoveryRunParams()

        assert params.min_price_change_pct == 100.0
        assert params.min_volume_usd == 50000.0
        assert params.max_token_age_hours == 72
        assert params.early_window_minutes == 30
        assert params.min_profit_pct == 50.0
        assert params.max_tokens == 20

    def test_custom_values(self) -> None:
        """Test custom parameter values."""
        params = DiscoveryRunParams(
            min_price_change_pct=200.0,
            min_volume_usd=100000.0,
            max_token_age_hours=48,
            early_window_minutes=15,
            min_profit_pct=75.0,
            max_tokens=10,
        )

        assert params.min_price_change_pct == 200.0
        assert params.min_volume_usd == 100000.0
        assert params.max_token_age_hours == 48
        assert params.early_window_minutes == 15
        assert params.min_profit_pct == 75.0
        assert params.max_tokens == 10

    def test_model_dump(self) -> None:
        """Test model can be dumped to dict."""
        params = DiscoveryRunParams()
        data = params.model_dump()

        assert isinstance(data, dict)
        assert "min_price_change_pct" in data
        assert "max_tokens" in data


class TestDiscoveryRun:
    """Tests for DiscoveryRun model."""

    def test_minimal_creation(self) -> None:
        """Test creating run with minimal required fields."""
        run_id = uuid4()
        now = datetime.now(UTC)

        run = DiscoveryRun(
            id=run_id,
            started_at=now,
            trigger_type=TriggerType.MANUAL,
        )

        assert run.id == run_id
        assert run.started_at == now
        assert run.completed_at is None
        assert run.status == RunStatus.RUNNING
        assert run.trigger_type == TriggerType.MANUAL
        assert run.triggered_by is None
        assert run.tokens_analyzed == 0
        assert run.new_wallets == 0
        assert run.errors == []

    def test_full_creation(self) -> None:
        """Test creating run with all fields."""
        run_id = uuid4()
        now = datetime.now(UTC)
        params = DiscoveryRunParams(min_price_change_pct=150.0)

        run = DiscoveryRun(
            id=run_id,
            started_at=now,
            completed_at=now,
            status=RunStatus.COMPLETED,
            trigger_type=TriggerType.SCHEDULED,
            triggered_by="scheduler",
            params=params,
            tokens_analyzed=10,
            new_wallets=25,
            updated_wallets=5,
            profiled_wallets=20,
            duration_seconds=120.5,
            errors=["error1", "error2"],
        )

        assert run.status == RunStatus.COMPLETED
        assert run.triggered_by == "scheduler"
        assert run.params.min_price_change_pct == 150.0
        assert run.tokens_analyzed == 10
        assert run.new_wallets == 25
        assert run.duration_seconds == 120.5
        assert len(run.errors) == 2


class TestDiscoveryRunWallet:
    """Tests for DiscoveryRunWallet model."""

    def test_creation(self) -> None:
        """Test creating wallet record."""
        wallet_id = uuid4()
        run_id = uuid4()

        wallet = DiscoveryRunWallet(
            id=wallet_id,
            run_id=run_id,
            wallet_address="ABC123",
            source_token="TOKEN123",
            is_new=True,
            initial_score=0.85,
        )

        assert wallet.id == wallet_id
        assert wallet.run_id == run_id
        assert wallet.wallet_address == "ABC123"
        assert wallet.source_token == "TOKEN123"
        assert wallet.is_new is True
        assert wallet.initial_score == 0.85

    def test_default_values(self) -> None:
        """Test default values for optional fields."""
        wallet = DiscoveryRunWallet(
            id=uuid4(),
            run_id=uuid4(),
            wallet_address="ABC",
            source_token="TOKEN",
        )

        assert wallet.is_new is True
        assert wallet.initial_score is None
        assert wallet.created_at is None


class TestDiscoveryStats:
    """Tests for DiscoveryStats model."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = DiscoveryStats()

        assert stats.total_runs == 0
        assert stats.successful_runs == 0
        assert stats.failed_runs == 0
        assert stats.total_wallets_discovered == 0
        assert stats.avg_wallets_per_run == 0.0
        assert stats.last_run_at is None

    def test_custom_values(self) -> None:
        """Test custom statistics values."""
        now = datetime.now(UTC)

        stats = DiscoveryStats(
            total_runs=100,
            successful_runs=95,
            failed_runs=5,
            total_wallets_discovered=1000,
            total_wallets_updated=200,
            avg_wallets_per_run=10.0,
            avg_duration_seconds=60.0,
            last_run_at=now,
        )

        assert stats.total_runs == 100
        assert stats.successful_runs == 95
        assert stats.total_wallets_discovered == 1000
        assert stats.last_run_at == now


class TestDiscoveryRunCreate:
    """Tests for DiscoveryRunCreate model."""

    def test_minimal_creation(self) -> None:
        """Test creating with minimal fields."""
        create = DiscoveryRunCreate(trigger_type=TriggerType.MANUAL)

        assert create.trigger_type == TriggerType.MANUAL
        assert create.triggered_by is None
        assert create.params.min_price_change_pct == 100.0

    def test_with_all_fields(self) -> None:
        """Test creating with all fields."""
        params = DiscoveryRunParams(max_tokens=5)
        create = DiscoveryRunCreate(
            trigger_type=TriggerType.API,
            triggered_by="api_user",
            params=params,
        )

        assert create.trigger_type == TriggerType.API
        assert create.triggered_by == "api_user"
        assert create.params.max_tokens == 5


class TestDiscoveryRunUpdate:
    """Tests for DiscoveryRunUpdate model."""

    def test_partial_update(self) -> None:
        """Test partial update with only some fields."""
        update = DiscoveryRunUpdate(
            status=RunStatus.COMPLETED,
            new_wallets=10,
        )

        assert update.status == RunStatus.COMPLETED
        assert update.new_wallets == 10
        assert update.completed_at is None
        assert update.tokens_analyzed is None

    def test_full_update(self) -> None:
        """Test update with all fields."""
        now = datetime.now(UTC)

        update = DiscoveryRunUpdate(
            status=RunStatus.COMPLETED,
            completed_at=now,
            tokens_analyzed=5,
            new_wallets=20,
            updated_wallets=3,
            profiled_wallets=15,
            duration_seconds=45.5,
            errors=["minor error"],
        )

        assert update.completed_at == now
        assert update.duration_seconds == 45.5
        assert update.errors == ["minor error"]
