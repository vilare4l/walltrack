"""Tests for risk configuration service."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.risk.config_models import (
    HealthStatus,
    RiskConfig,
    RiskConfigUpdate,
)
from walltrack.core.risk.config_service import (
    RiskConfigService,
    reset_risk_config_service,
)


@pytest.fixture
def service() -> RiskConfigService:
    """Create a fresh config service."""
    reset_risk_config_service()
    svc = RiskConfigService()
    svc._config = RiskConfig()
    return svc


class TestRiskConfig:
    """Test risk configuration model."""

    def test_default_config_values(self) -> None:
        """Default config has expected values."""
        config = RiskConfig()

        assert config.drawdown_threshold_percent == Decimal("20.0")
        assert config.win_rate_threshold_percent == Decimal("40.0")
        assert config.win_rate_window_size == 50
        assert config.consecutive_loss_threshold == 3
        assert config.consecutive_loss_critical == 5
        assert config.position_size_reduction == Decimal("0.5")
        assert config.max_concurrent_positions == 5
        assert config.no_signal_warning_hours == 48

    def test_config_validation(self) -> None:
        """Config validates field ranges."""
        # Valid config
        config = RiskConfig(
            drawdown_threshold_percent=Decimal("30.0"),
            max_concurrent_positions=10,
        )
        assert config.drawdown_threshold_percent == Decimal("30.0")

    def test_config_update_partial(self) -> None:
        """Update can be partial."""
        update = RiskConfigUpdate(
            drawdown_threshold_percent=Decimal("25.0"),
        )
        data = update.model_dump(exclude_none=True)

        assert "drawdown_threshold_percent" in data
        assert "win_rate_threshold_percent" not in data


class TestConfigUpdate:
    """Test config update functionality."""

    @pytest.mark.asyncio
    async def test_update_config(self, service: RiskConfigService) -> None:
        """Config updates are applied."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        update = RiskConfigUpdate(
            drawdown_threshold_percent=Decimal("25.0"),
            max_concurrent_positions=10,
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            config = await service.update_config(update, "operator-1")

            assert config.drawdown_threshold_percent == Decimal("25.0")
            assert config.max_concurrent_positions == 10

    @pytest.mark.asyncio
    async def test_update_config_logs_changes(
        self, service: RiskConfigService
    ) -> None:
        """Config updates are logged."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        update = RiskConfigUpdate(
            max_concurrent_positions=10,
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await service.update_config(update, "operator-1")

            # Verify changes were logged
            mock_db.table.assert_any_call("config_change_log")

    @pytest.mark.asyncio
    async def test_update_no_change(self, service: RiskConfigService) -> None:
        """Update with same values doesn't log changes."""
        mock_db = MagicMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        # Set initial value
        service._config.max_concurrent_positions = 10

        # Update with same value
        update = RiskConfigUpdate(max_concurrent_positions=10)

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await service.update_config(update, "operator-1")

            # config_change_log should not be called (no changes)
            calls = [
                call
                for call in mock_db.table.call_args_list
                if call.args[0] == "config_change_log"
            ]
            assert len(calls) == 0


class TestSystemHealth:
    """Test system health checks."""

    @pytest.mark.asyncio
    async def test_healthy_system(self, service: RiskConfigService) -> None:
        """Healthy system returns healthy status."""
        mock_db = MagicMock()

        # DB check passes
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock()
        )

        # Webhook healthy
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={"value": {"healthy": True}})
        )

        # Recent signal
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[{"received_at": datetime.utcnow().isoformat()}]
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            health = await service.check_system_health()

            assert health.overall_status == HealthStatus.HEALTHY
            assert len(health.errors) == 0
            assert len(health.warnings) == 0

    @pytest.mark.asyncio
    async def test_database_error(self, service: RiskConfigService) -> None:
        """Database error is reported."""
        mock_db = MagicMock()

        # DB check fails
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock(side_effect=Exception("DB connection failed"))
        )

        # Other checks return empty
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            health = await service.check_system_health()

            assert health.overall_status == HealthStatus.ERROR
            assert len(health.errors) > 0
            assert "Database connection failed" in health.errors[0]

    @pytest.mark.asyncio
    async def test_no_signals_warning(self, service: RiskConfigService) -> None:
        """No signals creates warning."""
        mock_db = MagicMock()

        # DB check passes
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock()
        )

        # Webhook healthy
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={"value": {"healthy": True}})
        )

        # Old signal (72 hours ago)
        old_time = datetime.utcnow() - timedelta(hours=72)
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[{"received_at": old_time.isoformat()}])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            health = await service.check_system_health()

            assert health.no_signal_warning is True
            assert len(health.warnings) > 0
            assert health.overall_status == HealthStatus.WARNING

    @pytest.mark.asyncio
    async def test_no_signals_ever(self, service: RiskConfigService) -> None:
        """No signals ever received creates warning."""
        mock_db = MagicMock()

        # DB check passes
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock()
        )

        # Webhook unknown
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data=None)
        )

        # No signals
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            health = await service.check_system_health()

            assert health.no_signal_warning is True
            assert "No signals have been received yet" in health.warnings


class TestDashboardStatus:
    """Test dashboard status."""

    @pytest.mark.asyncio
    async def test_dashboard_includes_all_info(
        self, service: RiskConfigService
    ) -> None:
        """Dashboard includes all required info."""
        mock_db = MagicMock()

        # System status
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            return_value=MagicMock(data={"value": "running"})
        )

        # Capital snapshot
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "capital": "1000",
                        "peak_capital": "1200",
                        "drawdown_percent": "16.67",
                    }
                ]
            )
        )

        # DB health check
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock()
        )

        # Alerts count
        mock_db.table.return_value.select.return_value.in_.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=3))
        )

        # Positions count
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(return_value=MagicMock(count=2))
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            with patch.object(service, "check_system_health") as mock_health:
                from walltrack.core.risk.config_models import SystemHealth

                mock_health.return_value = SystemHealth(
                    overall_status=HealthStatus.HEALTHY,
                    components=[],
                    last_signal_time=datetime.utcnow(),
                    no_signal_warning=False,
                    warnings=[],
                    errors=[],
                )

                status = await service.get_dashboard_status()

                assert status.system_status == "running"
                assert status.active_alerts_count == 3
                assert status.open_positions_count == 2
                assert status.capital_info["current_capital"] == "1000"

    @pytest.mark.asyncio
    async def test_dashboard_handles_missing_data(
        self, service: RiskConfigService
    ) -> None:
        """Dashboard handles missing data gracefully."""
        mock_db = MagicMock()

        # Everything fails or returns empty
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute = AsyncMock(
            side_effect=Exception("Not found")
        )
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )
        mock_db.table.return_value.select.return_value.limit.return_value.execute = (
            AsyncMock()
        )
        mock_db.table.return_value.select.return_value.in_.return_value.execute = (
            AsyncMock(side_effect=Exception("Error"))
        )
        mock_db.table.return_value.select.return_value.eq.return_value.execute = (
            AsyncMock(side_effect=Exception("Error"))
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            with patch.object(service, "check_system_health") as mock_health:
                from walltrack.core.risk.config_models import SystemHealth

                mock_health.return_value = SystemHealth(
                    overall_status=HealthStatus.UNKNOWN,
                    components=[],
                    last_signal_time=None,
                    no_signal_warning=False,
                    warnings=[],
                    errors=[],
                )

                status = await service.get_dashboard_status()

                assert status.system_status == "unknown"
                assert status.active_alerts_count == 0
                assert status.open_positions_count == 0
                assert status.capital_info == {}


class TestConfigHistory:
    """Test configuration change history."""

    @pytest.mark.asyncio
    async def test_get_history(self, service: RiskConfigService) -> None:
        """History returns change records."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(
                data=[
                    {
                        "id": "1",
                        "changed_at": datetime.utcnow().isoformat(),
                        "changed_by": "operator-1",
                        "field_name": "max_concurrent_positions",
                        "previous_value": "5",
                        "new_value": "10",
                    }
                ]
            )
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            history = await service.get_config_history()

            assert len(history) == 1
            assert history[0].field_name == "max_concurrent_positions"
            assert history[0].previous_value == "5"
            assert history[0].new_value == "10"

    @pytest.mark.asyncio
    async def test_filter_history_by_field(
        self, service: RiskConfigService
    ) -> None:
        """History can be filtered by field."""
        mock_db = MagicMock()
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute = AsyncMock(
            return_value=MagicMock(data=[])
        )

        with patch.object(
            service, "_get_db", new_callable=AsyncMock, return_value=mock_db
        ):
            await service.get_config_history(field_name="drawdown_threshold_percent")

            mock_db.table.return_value.select.return_value.eq.assert_called_once()


class TestSingletonManagement:
    """Test singleton management."""

    def test_reset_singleton(self) -> None:
        """Reset clears the singleton."""
        reset_risk_config_service()
        # No error means success
