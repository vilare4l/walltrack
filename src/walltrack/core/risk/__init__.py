"""Risk management module."""

from walltrack.core.risk.circuit_breaker import (
    DrawdownCircuitBreaker,
    get_drawdown_circuit_breaker,
    reset_drawdown_circuit_breaker,
)
from walltrack.core.risk.config_models import (
    ComponentHealth,
    ConfigChangeLog,
    DashboardStatus,
    HealthStatus,
    RiskConfig,
    RiskConfigUpdate,
    SystemHealth,
)
from walltrack.core.risk.config_service import (
    RiskConfigService,
    get_risk_config_service,
    reset_risk_config_service,
)
from walltrack.core.risk.consecutive_loss import (
    ConsecutiveLossManager,
    get_consecutive_loss_manager,
    reset_consecutive_loss_manager,
)
from walltrack.core.risk.position_limits import (
    PositionLimitManager,
    get_position_limit_manager,
    reset_position_limit_manager,
)
from walltrack.core.risk.system_state import (
    SystemStateManager,
    get_system_state_manager,
    reset_system_state_manager,
)
from walltrack.core.risk.win_rate_breaker import (
    WinRateCircuitBreaker,
    get_win_rate_circuit_breaker,
    reset_win_rate_circuit_breaker,
)

__all__ = [
    "ComponentHealth",
    "ConfigChangeLog",
    "ConsecutiveLossManager",
    "DashboardStatus",
    "DrawdownCircuitBreaker",
    "HealthStatus",
    "PositionLimitManager",
    "RiskConfig",
    "RiskConfigService",
    "RiskConfigUpdate",
    "SystemHealth",
    "SystemStateManager",
    "WinRateCircuitBreaker",
    "get_consecutive_loss_manager",
    "get_drawdown_circuit_breaker",
    "get_position_limit_manager",
    "get_risk_config_service",
    "get_system_state_manager",
    "get_win_rate_circuit_breaker",
    "reset_consecutive_loss_manager",
    "reset_drawdown_circuit_breaker",
    "reset_position_limit_manager",
    "reset_risk_config_service",
    "reset_system_state_manager",
    "reset_win_rate_circuit_breaker",
]
