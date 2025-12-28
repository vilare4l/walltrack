"""Risk configuration and system health service."""

from datetime import datetime

import structlog

from walltrack.core.risk.config_models import (
    ComponentHealth,
    ConfigChangeLog,
    DashboardStatus,
    HealthStatus,
    RiskConfig,
    RiskConfigUpdate,
    SystemHealth,
)
from walltrack.data.supabase import SupabaseClient, get_supabase_client

logger = structlog.get_logger(__name__)


class RiskConfigService:
    """Manages risk configuration and system health monitoring."""

    def __init__(self) -> None:
        """Initialize the config service."""
        self._supabase: SupabaseClient | None = None
        self._config: RiskConfig | None = None

    async def _get_db(self) -> SupabaseClient:
        """Get database client."""
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load config from database on startup."""
        db = await self._get_db()

        result = (
            await db.table("system_config")
            .select("value")
            .eq("key", "risk_config")
            .single()
            .execute()
        )

        if result.data:
            self._config = RiskConfig(**result.data["value"])
        else:
            self._config = RiskConfig()
            await self._save_config()

        logger.info(
            "risk_config_initialized",
            drawdown_threshold=str(self._config.drawdown_threshold_percent),
            max_positions=self._config.max_concurrent_positions,
        )

    async def get_config(self) -> RiskConfig:
        """Get current risk configuration."""
        if self._config is None:
            await self.initialize()
        return self._config  # type: ignore[return-value]

    async def update_config(
        self,
        update: RiskConfigUpdate,
        operator_id: str,
    ) -> RiskConfig:
        """
        Update risk configuration.

        Args:
            update: Fields to update
            operator_id: ID of operator making change

        Returns:
            Updated configuration
        """
        db = await self._get_db()

        if self._config is None:
            await self.initialize()

        # Track changes
        changes: list[ConfigChangeLog] = []
        update_dict = update.model_dump(exclude_none=True)

        for field, new_value in update_dict.items():
            old_value = getattr(self._config, field)
            if old_value != new_value:
                changes.append(
                    ConfigChangeLog(
                        changed_by=operator_id,
                        field_name=field,
                        previous_value=str(old_value),
                        new_value=str(new_value),
                    )
                )
                setattr(self._config, field, new_value)

        # Persist config
        await self._save_config()

        # Log changes
        for change in changes:
            await (
                db.table("config_change_log")
                .insert(change.model_dump(exclude={"id"}, mode="json"))
                .execute()
            )

            logger.info(
                "risk_config_updated",
                field=change.field_name,
                old=change.previous_value,
                new=change.new_value,
                operator=operator_id,
            )

        return self._config  # type: ignore[return-value]

    async def _save_config(self) -> None:
        """Persist config to database."""
        db = await self._get_db()

        await (
            db.table("system_config")
            .upsert(
                {
                    "key": "risk_config",
                    "value": self._config.model_dump(mode="json"),  # type: ignore[union-attr]
                    "updated_at": datetime.utcnow().isoformat(),
                }
            )
            .execute()
        )

    async def _check_database_health(
        self,
        db: SupabaseClient,
    ) -> tuple[ComponentHealth, str | None]:
        """Check database connection health."""
        try:
            await db.table("system_config").select("key").limit(1).execute()
            return (
                ComponentHealth(
                    component="database",
                    status=HealthStatus.HEALTHY,
                    message="Database connection OK",
                ),
                None,
            )
        except Exception as e:
            return (
                ComponentHealth(
                    component="database",
                    status=HealthStatus.ERROR,
                    message=f"Database error: {e!s}",
                ),
                "Database connection failed",
            )

    async def _check_webhook_health(
        self,
        db: SupabaseClient,
    ) -> tuple[ComponentHealth, str | None]:
        """Check webhook endpoint health."""
        try:
            result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "webhook_status")
                .single()
                .execute()
            )

            if result.data and result.data["value"].get("healthy", False):
                return (
                    ComponentHealth(
                        component="webhook",
                        status=HealthStatus.HEALTHY,
                        message="Webhook endpoint active",
                    ),
                    None,
                )
            elif result.data:
                return (
                    ComponentHealth(
                        component="webhook",
                        status=HealthStatus.WARNING,
                        message="Webhook issues detected",
                    ),
                    "Webhook endpoint may have issues",
                )
            else:
                return (
                    ComponentHealth(
                        component="webhook",
                        status=HealthStatus.UNKNOWN,
                        message="Webhook status unknown",
                    ),
                    None,
                )
        except Exception:
            return (
                ComponentHealth(
                    component="webhook",
                    status=HealthStatus.UNKNOWN,
                    message="Webhook status unknown",
                ),
                None,
            )

    async def _check_signal_health(
        self,
        db: SupabaseClient,
        warning_hours: int,
    ) -> tuple[ComponentHealth, datetime | None, bool, str | None]:
        """Check signal reception health."""
        try:
            result = (
                await db.table("signals")
                .select("received_at")
                .order("received_at", desc=True)
                .limit(1)
                .execute()
            )

            if not result.data:
                return (
                    ComponentHealth(
                        component="signals",
                        status=HealthStatus.WARNING,
                        message="No signals received",
                    ),
                    None,
                    True,
                    "No signals have been received yet",
                )

            last_signal = datetime.fromisoformat(
                result.data[0]["received_at"].replace("Z", "+00:00")
            )
            hours_since = (
                datetime.utcnow() - last_signal.replace(tzinfo=None)
            ).total_seconds() / 3600

            if hours_since > warning_hours:
                return (
                    ComponentHealth(
                        component="signals",
                        status=HealthStatus.WARNING,
                        message=f"Last signal: {int(hours_since)}h ago",
                        details={"last_signal": last_signal.isoformat()},
                    ),
                    last_signal,
                    True,
                    f"No signals received for {int(hours_since)} hours",
                )
            else:
                return (
                    ComponentHealth(
                        component="signals",
                        status=HealthStatus.HEALTHY,
                        message=f"Last signal: {int(hours_since)}h ago",
                    ),
                    last_signal,
                    False,
                    None,
                )
        except Exception:
            return (
                ComponentHealth(
                    component="signals",
                    status=HealthStatus.UNKNOWN,
                    message="Signal status unknown",
                ),
                None,
                False,
                None,
            )

    async def check_system_health(self) -> SystemHealth:
        """Check health of all system components."""
        db = await self._get_db()

        if self._config is None:
            await self.initialize()

        components: list[ComponentHealth] = []
        warnings: list[str] = []
        errors: list[str] = []

        # Check database
        db_health, db_error = await self._check_database_health(db)
        components.append(db_health)
        if db_error:
            errors.append(db_error)

        # Check webhook
        webhook_health, webhook_warning = await self._check_webhook_health(db)
        components.append(webhook_health)
        if webhook_warning:
            warnings.append(webhook_warning)

        # Check signals
        signal_health, last_signal_time, no_signal_warning, signal_warning = (
            await self._check_signal_health(
                db, self._config.no_signal_warning_hours  # type: ignore[union-attr]
            )
        )
        components.append(signal_health)
        if signal_warning:
            warnings.append(signal_warning)

        # Determine overall status
        if errors:
            overall = HealthStatus.ERROR
        elif warnings:
            overall = HealthStatus.WARNING
        else:
            overall = HealthStatus.HEALTHY

        return SystemHealth(
            overall_status=overall,
            components=components,
            last_signal_time=last_signal_time,
            no_signal_warning=no_signal_warning,
            warnings=warnings,
            errors=errors,
        )

    async def get_dashboard_status(self) -> DashboardStatus:
        """Get complete dashboard status."""
        db = await self._get_db()

        # Get system status
        try:
            status_result = (
                await db.table("system_config")
                .select("value")
                .eq("key", "system_status")
                .single()
                .execute()
            )
            system_status = (
                status_result.data["value"] if status_result.data else "unknown"
            )
        except Exception:
            system_status = "unknown"

        # Get health
        health = await self.check_system_health()

        # Get config
        config = await self.get_config()

        # Get capital info
        capital_info: dict = {}
        try:
            capital_result = (
                await db.table("capital_snapshots")
                .select("capital, peak_capital, drawdown_percent")
                .order("timestamp", desc=True)
                .limit(1)
                .execute()
            )

            if capital_result.data:
                capital_info = {
                    "current_capital": capital_result.data[0]["capital"],
                    "peak_capital": capital_result.data[0]["peak_capital"],
                    "current_drawdown": capital_result.data[0]["drawdown_percent"],
                }
        except Exception:
            pass

        # Get alert count
        active_alerts = 0
        try:
            alerts_result = (
                await db.table("alerts")
                .select("id", count="exact")
                .in_("status", ["new", "acknowledged"])
                .execute()
            )
            active_alerts = alerts_result.count or 0
        except Exception:
            pass

        # Get position count
        open_positions = 0
        try:
            positions_result = (
                await db.table("positions")
                .select("id", count="exact")
                .eq("status", "open")
                .execute()
            )
            open_positions = positions_result.count or 0
        except Exception:
            pass

        return DashboardStatus(
            system_status=system_status,
            system_health=health,
            risk_config=config,
            capital_info=capital_info,
            active_alerts_count=active_alerts,
            open_positions_count=open_positions,
        )

    async def get_config_history(
        self,
        field_name: str | None = None,
        limit: int = 50,
    ) -> list[ConfigChangeLog]:
        """Get history of config changes."""
        db = await self._get_db()

        query = db.table("config_change_log").select("*")

        if field_name:
            query = query.eq("field_name", field_name)

        result = await query.order("changed_at", desc=True).limit(limit).execute()

        return [ConfigChangeLog(**row) for row in result.data]


# Singleton instance
_config_service: RiskConfigService | None = None


async def get_risk_config_service() -> RiskConfigService:
    """Get or create risk config service singleton."""
    global _config_service

    if _config_service is None:
        _config_service = RiskConfigService()
        await _config_service.initialize()

    return _config_service


def reset_risk_config_service() -> None:
    """Reset the singleton for testing."""
    global _config_service
    _config_service = None
