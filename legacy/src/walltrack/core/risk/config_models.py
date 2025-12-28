"""Risk configuration and health monitoring models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, computed_field


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
    details: dict[str, Any] | None = None


class RiskConfig(BaseModel):
    """Complete risk configuration."""

    # Drawdown settings
    drawdown_threshold_percent: Decimal = Field(
        default=Decimal("20.0"),
        ge=Decimal("5.0"),
        le=Decimal("50.0"),
        description="Drawdown threshold to trigger circuit breaker",
    )

    # Win rate settings
    win_rate_threshold_percent: Decimal = Field(
        default=Decimal("40.0"),
        ge=Decimal("10.0"),
        le=Decimal("60.0"),
        description="Win rate threshold to trigger circuit breaker",
    )
    win_rate_window_size: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of trades for win rate calculation",
    )

    # Consecutive loss settings
    consecutive_loss_threshold: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Consecutive losses before position reduction",
    )
    consecutive_loss_critical: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Consecutive losses before pause",
    )
    position_size_reduction: Decimal = Field(
        default=Decimal("0.5"),
        gt=Decimal("0"),
        lt=Decimal("1"),
        description="Position size reduction factor",
    )

    # Position limits
    max_concurrent_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum concurrent open positions",
    )

    # Signal monitoring
    no_signal_warning_hours: int = Field(
        default=48,
        ge=1,
        le=168,
        description="Hours without signals before warning",
    )

    model_config = {"json_encoders": {Decimal: str}}


class RiskConfigUpdate(BaseModel):
    """Partial update for risk config."""

    drawdown_threshold_percent: Decimal | None = None
    win_rate_threshold_percent: Decimal | None = None
    win_rate_window_size: int | None = None
    consecutive_loss_threshold: int | None = None
    consecutive_loss_critical: int | None = None
    position_size_reduction: Decimal | None = None
    max_concurrent_positions: int | None = None
    no_signal_warning_hours: int | None = None


class ConfigChangeLog(BaseModel):
    """Record of config change."""

    id: str | None = None
    changed_at: datetime = Field(default_factory=datetime.utcnow)
    changed_by: str
    field_name: str
    previous_value: str
    new_value: str


class SystemHealth(BaseModel):
    """Overall system health status."""

    overall_status: HealthStatus
    components: list[ComponentHealth]
    last_signal_time: datetime | None
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
    capital_info: dict[str, Any]
    active_alerts_count: int
    open_positions_count: int
