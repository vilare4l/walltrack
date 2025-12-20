# Story 5.7: Dashboard - System Status and Risk Configuration

## Story Info
- **Epic**: Epic 5 - Risk Management & Capital Protection
- **Status**: Done
- **Priority**: High
- **FR**: FR39, FR40

## User Story

**As an** operator,
**I want** to view system status and configure risk parameters,
**So that** I can monitor and control risk settings.

## Acceptance Criteria

### AC 1: Status Panel
**Given** dashboard Status panel
**When** operator views status
**Then** current system state is displayed (running, paused_*, etc.)
**And** if paused, reason and timestamp are shown
**And** health indicators show: DB connections, webhook status, last signal time

### AC 2: Risk Config Panel
**Given** dashboard Risk Config panel
**When** operator views settings
**Then** all risk parameters are displayed:
- Drawdown threshold (%)
- Win rate threshold (%)
- Win rate window size (trades)
- Max concurrent positions
- Consecutive loss threshold
- Position size reduction factor

### AC 3: Risk Parameter Modification
**Given** operator modifies risk parameter
**When** change is saved
**Then** new value is validated (within acceptable ranges)
**And** change takes effect immediately
**And** change is logged with previous and new values

### AC 4: Health Warnings
**Given** system health check
**When** component is unhealthy
**Then** status indicator shows warning/error
**And** details are available on hover/click
**And** alert is raised if critical

### AC 5: No Signal Warning
**Given** last activity timestamps
**When** no signals for extended period (configurable, e.g., 48h)
**Then** "no_signals" warning is displayed
**And** system health check alert is raised

## Technical Notes

- FR39: Configure risk parameters
- FR40: View system status (running, paused, health indicators)
- Implement in `src/walltrack/ui/components/status.py` and `config_panel.py`
- NFR13: Health check endpoint and alerting

## Implementation Tasks

- [x] Create `src/walltrack/core/risk/config_service.py`
- [x] Display system state and health indicators
- [x] Create risk config models with all parameters
- [x] Implement parameter validation
- [x] Add health warning indicators
- [x] Implement no-signal warning
- [x] Log all config changes

## Definition of Done

- [x] System status displayed accurately
- [x] Risk parameters viewable and editable
- [x] Changes take effect immediately
- [x] Health warnings displayed

## Implementation Summary

**Completed:** 2024-12-20

**Files Created/Modified:**
- `src/walltrack/core/risk/config_models.py` - Models (HealthStatus, RiskConfig, RiskConfigUpdate, SystemHealth, DashboardStatus, ConfigChangeLog)
- `src/walltrack/core/risk/config_service.py` - RiskConfigService class with health checks
- `src/walltrack/api/routes/config.py` - API routes (GET/PUT /config/risk, /health, /dashboard, /history)
- `src/walltrack/data/supabase/migrations/010_risk_management.sql` - config_change_log table, risk_config defaults
- `tests/unit/risk/test_config_service.py` - 15 unit tests

**Test Coverage:** 15 tests passing

---

## Technical Specifications

### Pydantic Models

```python
# src/walltrack/core/risk/config_models.py
from pydantic import BaseModel, Field, computed_field
from enum import Enum
from decimal import Decimal
from datetime import datetime
from typing import Optional, Dict, Any


class HealthStatus(str, Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    ERROR = "error"
    UNKNOWN = "unknown"


class ComponentHealth(BaseModel):
    """Health status of a system component."""
    component: str
    status: HealthStatus
    message: str
    last_check: datetime = Field(default_factory=datetime.utcnow)
    details: Optional[Dict[str, Any]] = None


class RiskConfig(BaseModel):
    """Complete risk configuration."""
    # Drawdown settings
    drawdown_threshold_percent: Decimal = Field(
        default=Decimal("20.0"),
        ge=Decimal("5.0"),
        le=Decimal("50.0"),
        description="Drawdown threshold to trigger circuit breaker"
    )

    # Win rate settings
    win_rate_threshold_percent: Decimal = Field(
        default=Decimal("40.0"),
        ge=Decimal("10.0"),
        le=Decimal("60.0"),
        description="Win rate threshold to trigger circuit breaker"
    )
    win_rate_window_size: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of trades for win rate calculation"
    )

    # Consecutive loss settings
    consecutive_loss_threshold: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Consecutive losses before position reduction"
    )
    consecutive_loss_critical: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Consecutive losses before pause"
    )
    position_size_reduction: Decimal = Field(
        default=Decimal("0.5"),
        gt=Decimal("0"),
        lt=Decimal("1"),
        description="Position size reduction factor"
    )

    # Position limits
    max_concurrent_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent open positions"
    )

    # Signal monitoring
    no_signal_warning_hours: int = Field(
        default=48,
        ge=1,
        le=168,
        description="Hours without signals before warning"
    )

    class Config:
        json_encoders = {Decimal: str}


class RiskConfigUpdate(BaseModel):
    """Partial update for risk config."""
    drawdown_threshold_percent: Optional[Decimal] = None
    win_rate_threshold_percent: Optional[Decimal] = None
    win_rate_window_size: Optional[int] = None
    consecutive_loss_threshold: Optional[int] = None
    consecutive_loss_critical: Optional[int] = None
    position_size_reduction: Optional[Decimal] = None
    max_concurrent_positions: Optional[int] = None
    no_signal_warning_hours: Optional[int] = None


class ConfigChangeLog(BaseModel):
    """Record of config change."""
    id: Optional[str] = None
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str
    field_name: str
    previous_value: str
    new_value: str


class SystemHealth(BaseModel):
    """Overall system health status."""
    overall_status: HealthStatus
    components: list[ComponentHealth]
    last_signal_time: Optional[datetime]
    no_signal_warning: bool
    warnings: list[str]
    errors: list[str]

    @computed_field
    @property
    def has_issues(self) -> bool:
        """Whether any issues exist."""
        return len(self.warnings) > 0 or len(self.errors) > 0


class DashboardStatus(BaseModel):
    """Complete dashboard status."""
    system_status: str  # running, paused_*
    system_health: SystemHealth
    risk_config: RiskConfig
    capital_info: Dict[str, Any]
    active_alerts_count: int
    open_positions_count: int
```

### RiskConfigService

```python
# src/walltrack/core/risk/config_service.py
import structlog
from decimal import Decimal
from datetime import datetime, timedelta
from typing import Optional, List
from supabase import AsyncClient

from walltrack.core.risk.config_models import (
    HealthStatus,
    ComponentHealth,
    RiskConfig,
    RiskConfigUpdate,
    ConfigChangeLog,
    SystemHealth,
    DashboardStatus
)
from walltrack.db.supabase import get_supabase_client

logger = structlog.get_logger(__name__)


class RiskConfigService:
    """
    Manages risk configuration and system health monitoring.
    """

    def __init__(self):
        self._supabase: Optional[AsyncClient] = None
        self._config: Optional[RiskConfig] = None

    async def _get_db(self) -> AsyncClient:
        if self._supabase is None:
            self._supabase = await get_supabase_client()
        return self._supabase

    async def initialize(self) -> None:
        """Load config from database on startup."""
        db = await self._get_db()

        result = await db.table("system_config").select("value").eq(
            "key", "risk_config"
        ).single().execute()

        if result.data:
            self._config = RiskConfig(**result.data["value"])
        else:
            self._config = RiskConfig()
            await self._save_config("system")

        logger.info(
            "risk_config_initialized",
            drawdown_threshold=str(self._config.drawdown_threshold_percent),
            max_positions=self._config.max_concurrent_positions
        )

    async def get_config(self) -> RiskConfig:
        """Get current risk configuration."""
        if self._config is None:
            await self.initialize()
        return self._config

    async def update_config(
        self,
        update: RiskConfigUpdate,
        operator_id: str
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
        changes = []
        update_dict = update.model_dump(exclude_none=True)

        for field, new_value in update_dict.items():
            old_value = getattr(self._config, field)
            if old_value != new_value:
                changes.append(ConfigChangeLog(
                    changed_by=operator_id,
                    field_name=field,
                    previous_value=str(old_value),
                    new_value=str(new_value)
                ))
                setattr(self._config, field, new_value)

        # Persist config
        await self._save_config(operator_id)

        # Log changes
        for change in changes:
            await db.table("config_change_log").insert(
                change.model_dump(exclude={"id"}, mode="json")
            ).execute()

            logger.info(
                "risk_config_updated",
                field=change.field_name,
                old=change.previous_value,
                new=change.new_value,
                operator=operator_id
            )

        return self._config

    async def _save_config(self, operator_id: str) -> None:
        """Persist config to database."""
        db = await self._get_db()

        await db.table("system_config").upsert({
            "key": "risk_config",
            "value": self._config.model_dump(mode="json"),
            "updated_at": datetime.utcnow().isoformat()
        }).execute()

    async def check_system_health(self) -> SystemHealth:
        """Check health of all system components."""
        db = await self._get_db()

        components = []
        warnings = []
        errors = []

        # Check database connection
        try:
            await db.table("system_config").select("key").limit(1).execute()
            components.append(ComponentHealth(
                component="database",
                status=HealthStatus.HEALTHY,
                message="Database connection OK"
            ))
        except Exception as e:
            components.append(ComponentHealth(
                component="database",
                status=HealthStatus.ERROR,
                message=f"Database error: {str(e)}"
            ))
            errors.append("Database connection failed")

        # Check webhook status
        webhook_result = await db.table("system_config").select("value").eq(
            "key", "webhook_status"
        ).single().execute()

        if webhook_result.data:
            webhook_status = webhook_result.data["value"]
            if webhook_status.get("healthy", False):
                components.append(ComponentHealth(
                    component="webhook",
                    status=HealthStatus.HEALTHY,
                    message="Webhook endpoint active"
                ))
            else:
                components.append(ComponentHealth(
                    component="webhook",
                    status=HealthStatus.WARNING,
                    message="Webhook issues detected"
                ))
                warnings.append("Webhook endpoint may have issues")
        else:
            components.append(ComponentHealth(
                component="webhook",
                status=HealthStatus.UNKNOWN,
                message="Webhook status unknown"
            ))

        # Check last signal time
        signal_result = await db.table("signals").select(
            "received_at"
        ).order("received_at", desc=True).limit(1).execute()

        last_signal_time = None
        no_signal_warning = False

        if signal_result.data:
            last_signal_time = datetime.fromisoformat(
                signal_result.data[0]["received_at"]
            )
            hours_since = (datetime.utcnow() - last_signal_time).total_seconds() / 3600

            if hours_since > self._config.no_signal_warning_hours:
                no_signal_warning = True
                warnings.append(
                    f"No signals received for {int(hours_since)} hours"
                )
                components.append(ComponentHealth(
                    component="signals",
                    status=HealthStatus.WARNING,
                    message=f"Last signal: {int(hours_since)}h ago",
                    details={"last_signal": last_signal_time.isoformat()}
                ))
            else:
                components.append(ComponentHealth(
                    component="signals",
                    status=HealthStatus.HEALTHY,
                    message=f"Last signal: {int(hours_since)}h ago"
                ))
        else:
            no_signal_warning = True
            warnings.append("No signals have been received yet")
            components.append(ComponentHealth(
                component="signals",
                status=HealthStatus.WARNING,
                message="No signals received"
            ))

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
            errors=errors
        )

    async def get_dashboard_status(self) -> DashboardStatus:
        """Get complete dashboard status."""
        db = await self._get_db()

        # Get system status
        status_result = await db.table("system_config").select("value").eq(
            "key", "system_status"
        ).single().execute()
        system_status = status_result.data["value"] if status_result.data else "unknown"

        # Get health
        health = await self.check_system_health()

        # Get config
        config = await self.get_config()

        # Get capital info
        capital_result = await db.table("capital_snapshots").select(
            "capital, peak_capital, drawdown_percent"
        ).order("timestamp", desc=True).limit(1).execute()

        capital_info = {}
        if capital_result.data:
            capital_info = {
                "current_capital": capital_result.data[0]["capital"],
                "peak_capital": capital_result.data[0]["peak_capital"],
                "current_drawdown": capital_result.data[0]["drawdown_percent"]
            }

        # Get alert count
        alerts_result = await db.table("alerts").select(
            "id", count="exact"
        ).in_("status", ["new", "acknowledged"]).execute()
        active_alerts = alerts_result.count or 0

        # Get position count
        positions_result = await db.table("positions").select(
            "id", count="exact"
        ).eq("status", "open").execute()
        open_positions = positions_result.count or 0

        return DashboardStatus(
            system_status=system_status,
            system_health=health,
            risk_config=config,
            capital_info=capital_info,
            active_alerts_count=active_alerts,
            open_positions_count=open_positions
        )

    async def get_config_history(
        self,
        field_name: Optional[str] = None,
        limit: int = 50
    ) -> List[ConfigChangeLog]:
        """Get history of config changes."""
        db = await self._get_db()

        query = db.table("config_change_log").select("*")

        if field_name:
            query = query.eq("field_name", field_name)

        result = await query.order("changed_at", desc=True).limit(limit).execute()

        return [ConfigChangeLog(**row) for row in result.data]


# Singleton instance
_config_service: Optional[RiskConfigService] = None


async def get_risk_config_service() -> RiskConfigService:
    """Get or create risk config service singleton."""
    global _config_service

    if _config_service is None:
        _config_service = RiskConfigService()
        await _config_service.initialize()

    return _config_service
```

### Gradio Status and Config Panel

```python
# src/walltrack/ui/components/status_config.py
import gradio as gr
from decimal import Decimal
from datetime import datetime

from walltrack.core.risk.config_service import get_risk_config_service
from walltrack.core.risk.config_models import (
    HealthStatus,
    RiskConfig,
    RiskConfigUpdate
)


async def load_dashboard_status() -> tuple[str, str, str, str]:
    """Load complete dashboard status."""
    service = await get_risk_config_service()
    status = await service.get_dashboard_status()

    # System status badge
    status_badges = {
        "running": "🟢 RUNNING",
        "paused_manual": "🟡 PAUSED (Manual)",
        "paused_drawdown": "🔴 PAUSED (Drawdown)",
        "paused_win_rate": "🔴 PAUSED (Win Rate)",
        "paused_consecutive_loss": "🔴 PAUSED (Loss Streak)"
    }
    system_badge = status_badges.get(status.system_status, "❓ UNKNOWN")

    # Health display
    health_emoji = {
        HealthStatus.HEALTHY: "🟢",
        HealthStatus.WARNING: "🟡",
        HealthStatus.ERROR: "🔴",
        HealthStatus.UNKNOWN: "❓"
    }

    health_lines = [
        f"{health_emoji[c.status]} **{c.component}**: {c.message}"
        for c in status.system_health.components
    ]
    health_display = "\n".join(health_lines)

    if status.system_health.warnings:
        health_display += "\n\n**Warnings:**\n" + "\n".join(
            f"- {w}" for w in status.system_health.warnings
        )

    if status.system_health.errors:
        health_display += "\n\n**Errors:**\n" + "\n".join(
            f"- {e}" for e in status.system_health.errors
        )

    # Capital info
    capital = status.capital_info
    capital_display = f"""
**Current Capital:** {capital.get('current_capital', 'N/A')}
**Peak Capital:** {capital.get('peak_capital', 'N/A')}
**Current Drawdown:** {capital.get('current_drawdown', 'N/A')}%

**Active Alerts:** {status.active_alerts_count}
**Open Positions:** {status.open_positions_count}
"""

    return system_badge, health_display, capital_display, ""


async def load_risk_config() -> tuple:
    """Load current risk configuration."""
    service = await get_risk_config_service()
    config = await service.get_config()

    return (
        float(config.drawdown_threshold_percent),
        float(config.win_rate_threshold_percent),
        config.win_rate_window_size,
        config.consecutive_loss_threshold,
        config.consecutive_loss_critical,
        float(config.position_size_reduction * 100),  # Show as percentage
        config.max_concurrent_positions,
        config.no_signal_warning_hours
    )


async def save_risk_config(
    drawdown_threshold: float,
    win_rate_threshold: float,
    win_rate_window: int,
    loss_threshold: int,
    loss_critical: int,
    size_reduction: float,
    max_positions: int,
    no_signal_hours: int,
    operator_id: str
) -> str:
    """Save risk configuration."""
    if not operator_id:
        return "Error: Operator ID required"

    service = await get_risk_config_service()

    update = RiskConfigUpdate(
        drawdown_threshold_percent=Decimal(str(drawdown_threshold)),
        win_rate_threshold_percent=Decimal(str(win_rate_threshold)),
        win_rate_window_size=win_rate_window,
        consecutive_loss_threshold=loss_threshold,
        consecutive_loss_critical=loss_critical,
        position_size_reduction=Decimal(str(size_reduction / 100)),  # Convert from percentage
        max_concurrent_positions=max_positions,
        no_signal_warning_hours=no_signal_hours
    )

    try:
        await service.update_config(update, operator_id)
        return "Configuration saved successfully"
    except Exception as e:
        return f"Error: {str(e)}"


def create_status_config_panel() -> gr.Blocks:
    """Create the status and config panel for the dashboard."""

    with gr.Blocks() as panel:
        gr.Markdown("## System Status & Risk Configuration")

        with gr.Tabs():
            # Status Tab
            with gr.TabItem("System Status"):
                with gr.Row():
                    system_status = gr.Markdown("Loading...")

                with gr.Row():
                    with gr.Column():
                        gr.Markdown("### Health Indicators")
                        health_display = gr.Markdown("Loading...")

                    with gr.Column():
                        gr.Markdown("### Capital & Activity")
                        capital_display = gr.Markdown("Loading...")

                refresh_status_btn = gr.Button("🔄 Refresh Status")

            # Risk Config Tab
            with gr.TabItem("Risk Configuration"):
                gr.Markdown("### Circuit Breaker Thresholds")

                with gr.Row():
                    drawdown_input = gr.Slider(
                        minimum=5,
                        maximum=50,
                        step=1,
                        label="Drawdown Threshold (%)",
                        info="Pause trading when drawdown exceeds this"
                    )
                    win_rate_input = gr.Slider(
                        minimum=10,
                        maximum=60,
                        step=1,
                        label="Win Rate Threshold (%)",
                        info="Pause when win rate falls below this"
                    )

                with gr.Row():
                    win_rate_window_input = gr.Slider(
                        minimum=10,
                        maximum=200,
                        step=10,
                        label="Win Rate Window (trades)",
                        info="Number of trades for win rate calculation"
                    )

                gr.Markdown("### Consecutive Loss Settings")

                with gr.Row():
                    loss_threshold_input = gr.Slider(
                        minimum=1,
                        maximum=10,
                        step=1,
                        label="Reduction Threshold",
                        info="Reduce position size after N consecutive losses"
                    )
                    loss_critical_input = gr.Slider(
                        minimum=2,
                        maximum=15,
                        step=1,
                        label="Critical Threshold",
                        info="Pause trading after N consecutive losses"
                    )

                with gr.Row():
                    size_reduction_input = gr.Slider(
                        minimum=10,
                        maximum=90,
                        step=5,
                        label="Size Reduction (%)",
                        info="Reduce position size by this percentage"
                    )

                gr.Markdown("### Position Limits")

                with gr.Row():
                    max_positions_input = gr.Slider(
                        minimum=1,
                        maximum=20,
                        step=1,
                        label="Max Concurrent Positions",
                        info="Maximum open positions at once"
                    )

                gr.Markdown("### Monitoring")

                with gr.Row():
                    no_signal_input = gr.Slider(
                        minimum=1,
                        maximum=168,
                        step=1,
                        label="No Signal Warning (hours)",
                        info="Alert if no signals received for this long"
                    )

                gr.Markdown("---")

                with gr.Row():
                    config_operator = gr.Textbox(
                        label="Operator ID",
                        value="operator-1"
                    )

                with gr.Row():
                    load_config_btn = gr.Button("📥 Load Current Config")
                    save_config_btn = gr.Button("💾 Save Configuration", variant="primary")

                config_result = gr.Textbox(label="Result", interactive=False)

            # Config History Tab
            with gr.TabItem("Change History"):
                history_table = gr.Dataframe(
                    headers=["Time", "Field", "Previous", "New", "Changed By"],
                    datatype=["str", "str", "str", "str", "str"],
                    label="Recent Configuration Changes"
                )
                refresh_history_btn = gr.Button("🔄 Refresh History")

        # Hidden state for error messages
        error_display = gr.Textbox(visible=False)

        # Event handlers
        refresh_status_btn.click(
            fn=load_dashboard_status,
            outputs=[system_status, health_display, capital_display, error_display]
        )

        load_config_btn.click(
            fn=load_risk_config,
            outputs=[
                drawdown_input, win_rate_input, win_rate_window_input,
                loss_threshold_input, loss_critical_input, size_reduction_input,
                max_positions_input, no_signal_input
            ]
        )

        save_config_btn.click(
            fn=save_risk_config,
            inputs=[
                drawdown_input, win_rate_input, win_rate_window_input,
                loss_threshold_input, loss_critical_input, size_reduction_input,
                max_positions_input, no_signal_input, config_operator
            ],
            outputs=[config_result]
        )

        async def load_history():
            service = await get_risk_config_service()
            history = await service.get_config_history(limit=50)
            return [[
                h.changed_at.strftime("%Y-%m-%d %H:%M"),
                h.field_name,
                h.previous_value,
                h.new_value,
                h.changed_by
            ] for h in history]

        refresh_history_btn.click(
            fn=load_history,
            outputs=[history_table]
        )

        # Initial load
        panel.load(
            fn=load_dashboard_status,
            outputs=[system_status, health_display, capital_display, error_display]
        )

        panel.load(
            fn=load_risk_config,
            outputs=[
                drawdown_input, win_rate_input, win_rate_window_input,
                loss_threshold_input, loss_critical_input, size_reduction_input,
                max_positions_input, no_signal_input
            ]
        )

    return panel
```

### Database Schema (Supabase)

```sql
-- Config change log for audit trail
CREATE TABLE config_change_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(100) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    previous_value TEXT NOT NULL,
    new_value TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_config_change_log_date ON config_change_log(changed_at DESC);
CREATE INDEX idx_config_change_log_field ON config_change_log(field_name);

-- Insert default risk config
INSERT INTO system_config (key, value) VALUES
('risk_config', '{
    "drawdown_threshold_percent": "20.0",
    "win_rate_threshold_percent": "40.0",
    "win_rate_window_size": 50,
    "consecutive_loss_threshold": 3,
    "consecutive_loss_critical": 5,
    "position_size_reduction": "0.5",
    "max_concurrent_positions": 5,
    "no_signal_warning_hours": 48
}'),
('webhook_status', '{"healthy": true, "last_check": null}')
ON CONFLICT (key) DO NOTHING;
```

### FastAPI Routes

```python
# src/walltrack/api/routes/config.py
from fastapi import APIRouter, Depends
from typing import List

from walltrack.core.risk.config_service import (
    get_risk_config_service,
    RiskConfigService
)
from walltrack.core.risk.config_models import (
    RiskConfig,
    RiskConfigUpdate,
    SystemHealth,
    DashboardStatus,
    ConfigChangeLog
)

router = APIRouter(prefix="/config", tags=["config"])


class ConfigUpdateRequest(BaseModel):
    update: RiskConfigUpdate
    operator_id: str


@router.get("/risk", response_model=RiskConfig)
async def get_risk_config(
    service: RiskConfigService = Depends(get_risk_config_service)
):
    """Get current risk configuration."""
    return await service.get_config()


@router.put("/risk", response_model=RiskConfig)
async def update_risk_config(
    request: ConfigUpdateRequest,
    service: RiskConfigService = Depends(get_risk_config_service)
):
    """Update risk configuration."""
    return await service.update_config(request.update, request.operator_id)


@router.get("/health", response_model=SystemHealth)
async def get_system_health(
    service: RiskConfigService = Depends(get_risk_config_service)
):
    """Get system health status."""
    return await service.check_system_health()


@router.get("/dashboard", response_model=DashboardStatus)
async def get_dashboard_status(
    service: RiskConfigService = Depends(get_risk_config_service)
):
    """Get complete dashboard status."""
    return await service.get_dashboard_status()


@router.get("/history", response_model=List[ConfigChangeLog])
async def get_config_history(
    field_name: str | None = None,
    limit: int = 50,
    service: RiskConfigService = Depends(get_risk_config_service)
):
    """Get configuration change history."""
    return await service.get_config_history(field_name, limit)
```

### Unit Tests

```python
# tests/unit/risk/test_config_service.py
import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from walltrack.core.risk.config_models import (
    HealthStatus,
    RiskConfig,
    RiskConfigUpdate
)
from walltrack.core.risk.config_service import RiskConfigService


@pytest.fixture
def service():
    svc = RiskConfigService()
    svc._config = RiskConfig()
    return svc


class TestRiskConfig:
    """Test risk configuration."""

    def test_default_config_values(self):
        """Default config has expected values."""
        config = RiskConfig()

        assert config.drawdown_threshold_percent == Decimal("20.0")
        assert config.win_rate_threshold_percent == Decimal("40.0")
        assert config.consecutive_loss_threshold == 3
        assert config.max_concurrent_positions == 5

    @pytest.mark.asyncio
    async def test_update_config(self, service):
        """Config updates are applied and logged."""
        mock_db = AsyncMock()
        mock_db.table.return_value.upsert.return_value.execute = AsyncMock()
        mock_db.table.return_value.insert.return_value.execute = AsyncMock()

        update = RiskConfigUpdate(
            drawdown_threshold_percent=Decimal("25.0"),
            max_concurrent_positions=10
        )

        with patch.object(service, '_get_db', return_value=mock_db):
            config = await service.update_config(update, "operator-1")

            assert config.drawdown_threshold_percent == Decimal("25.0")
            assert config.max_concurrent_positions == 10

            # Verify changes were logged
            mock_db.table.assert_any_call("config_change_log")


class TestSystemHealth:
    """Test system health checks."""

    @pytest.mark.asyncio
    async def test_healthy_system(self, service):
        """Healthy system returns healthy status."""
        mock_db = AsyncMock()

        # DB check passes
        mock_db.table.return_value.select.return_value.limit.return_value.execute = AsyncMock()

        # Webhook healthy
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "value": {"healthy": True}
        }

        # Recent signal
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{
            "received_at": datetime.utcnow().isoformat()
        }]

        with patch.object(service, '_get_db', return_value=mock_db):
            health = await service.check_system_health()

            assert health.overall_status == HealthStatus.HEALTHY
            assert len(health.errors) == 0

    @pytest.mark.asyncio
    async def test_no_signals_warning(self, service):
        """No signals creates warning."""
        mock_db = AsyncMock()

        # DB check passes
        mock_db.table.return_value.select.return_value.limit.return_value.execute = AsyncMock()

        # Webhook healthy
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "value": {"healthy": True}
        }

        # Old signal (72 hours ago)
        old_time = datetime.utcnow() - timedelta(hours=72)
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{
            "received_at": old_time.isoformat()
        }]

        with patch.object(service, '_get_db', return_value=mock_db):
            health = await service.check_system_health()

            assert health.no_signal_warning is True
            assert len(health.warnings) > 0
            assert health.overall_status == HealthStatus.WARNING


class TestDashboardStatus:
    """Test dashboard status."""

    @pytest.mark.asyncio
    async def test_dashboard_includes_all_info(self, service):
        """Dashboard includes all required info."""
        mock_db = AsyncMock()

        # System status
        mock_db.table.return_value.select.return_value.eq.return_value.single.return_value.execute.return_value.data = {
            "value": "running"
        }

        # Capital snapshot
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [{
            "capital": "1000",
            "peak_capital": "1200",
            "drawdown_percent": "16.67"
        }]

        # Alerts count
        mock_db.table.return_value.select.return_value.in_.return_value.execute.return_value.count = 3

        # Positions count
        mock_db.table.return_value.select.return_value.eq.return_value.execute.return_value.count = 2

        with patch.object(service, '_get_db', return_value=mock_db):
            with patch.object(service, 'check_system_health') as mock_health:
                from walltrack.core.risk.config_models import SystemHealth
                mock_health.return_value = SystemHealth(
                    overall_status=HealthStatus.HEALTHY,
                    components=[],
                    last_signal_time=datetime.utcnow(),
                    no_signal_warning=False,
                    warnings=[],
                    errors=[]
                )

                status = await service.get_dashboard_status()

                assert status.system_status == "running"
                assert status.active_alerts_count == 3
                assert status.open_positions_count == 2


class TestConfigHistory:
    """Test configuration change history."""

    @pytest.mark.asyncio
    async def test_get_history(self, service):
        """History returns change records."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.order.return_value.limit.return_value.execute.return_value.data = [
            {
                "id": "1",
                "changed_at": datetime.utcnow().isoformat(),
                "changed_by": "operator-1",
                "field_name": "max_concurrent_positions",
                "previous_value": "5",
                "new_value": "10"
            }
        ]

        with patch.object(service, '_get_db', return_value=mock_db):
            history = await service.get_config_history()

            assert len(history) == 1
            assert history[0].field_name == "max_concurrent_positions"

    @pytest.mark.asyncio
    async def test_filter_history_by_field(self, service):
        """History can be filtered by field."""
        mock_db = AsyncMock()
        mock_db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value.execute.return_value.data = []

        with patch.object(service, '_get_db', return_value=mock_db):
            await service.get_config_history(field_name="drawdown_threshold_percent")

            mock_db.table.return_value.select.return_value.eq.assert_called()
```
