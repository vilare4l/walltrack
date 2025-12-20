"""Risk management Pydantic models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, computed_field


class CircuitBreakerType(str, Enum):
    """Type of circuit breaker."""

    DRAWDOWN = "drawdown"
    WIN_RATE = "win_rate"
    CONSECUTIVE_LOSS = "consecutive_loss"
    MANUAL = "manual"


class SystemStatus(str, Enum):
    """System trading status."""

    RUNNING = "running"
    PAUSED_DRAWDOWN = "paused_drawdown"
    PAUSED_WIN_RATE = "paused_win_rate"
    PAUSED_CONSECUTIVE_LOSS = "paused_consecutive_loss"
    PAUSED_MANUAL = "paused_manual"


class DrawdownConfig(BaseModel):
    """Configuration for drawdown circuit breaker."""

    threshold_percent: Decimal = Field(
        default=Decimal("20.0"),
        ge=Decimal("5.0"),
        le=Decimal("50.0"),
        description="Drawdown threshold to trigger circuit breaker",
    )
    initial_capital: Decimal = Field(
        ...,
        gt=Decimal("0"),
        description="Initial capital at system start",
    )

    model_config = {"json_encoders": {Decimal: str}}


class CapitalSnapshot(BaseModel):
    """Point-in-time capital snapshot."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    capital: Decimal = Field(..., description="Current capital value")
    peak_capital: Decimal = Field(..., description="Peak capital since start/reset")

    @computed_field
    @property
    def drawdown_amount(self) -> Decimal:
        """Absolute drawdown amount."""
        return self.peak_capital - self.capital

    @computed_field
    @property
    def drawdown_percent(self) -> Decimal:
        """Drawdown as percentage of peak."""
        if self.peak_capital == Decimal("0"):
            return Decimal("0")
        return (self.drawdown_amount / self.peak_capital) * Decimal("100")


class CircuitBreakerTrigger(BaseModel):
    """Record of circuit breaker trigger event."""

    id: str | None = None
    breaker_type: CircuitBreakerType
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    threshold_value: Decimal = Field(..., description="Threshold that was exceeded")
    actual_value: Decimal = Field(..., description="Actual value that triggered")
    capital_at_trigger: Decimal = Field(..., description="Capital when triggered")
    peak_capital_at_trigger: Decimal = Field(
        ..., description="Peak capital when triggered"
    )
    reset_at: datetime | None = None
    reset_by: str | None = None  # operator ID or "system"

    @computed_field
    @property
    def is_active(self) -> bool:
        """Whether this circuit breaker is still active."""
        return self.reset_at is None


class DrawdownCheckResult(BaseModel):
    """Result of drawdown check."""

    current_capital: Decimal
    peak_capital: Decimal
    drawdown_percent: Decimal
    threshold_percent: Decimal
    is_breached: bool
    trigger: CircuitBreakerTrigger | None = None


class BlockedSignal(BaseModel):
    """Record of a signal blocked by circuit breaker."""

    signal_id: str
    blocked_at: datetime = Field(default_factory=datetime.utcnow)
    breaker_type: CircuitBreakerType
    reason: str
    signal_data: dict = Field(default_factory=dict)


# Story 5-2: Consecutive Loss Position Reduction Models


class TradeOutcome(str, Enum):
    """Result of a completed trade."""

    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


class SizingMode(str, Enum):
    """Position sizing mode."""

    NORMAL = "normal"
    REDUCED = "reduced"
    CRITICAL = "critical"
    PAUSED = "paused"


class ConsecutiveLossConfig(BaseModel):
    """Configuration for consecutive loss position reduction."""

    reduction_threshold: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of consecutive losses before reduction",
    )
    reduction_factor: Decimal = Field(
        default=Decimal("0.5"),
        gt=Decimal("0"),
        lt=Decimal("1"),
        description="Factor to multiply position size (0.5 = 50% reduction)",
    )
    critical_threshold: int = Field(
        default=5,
        ge=2,
        le=15,
        description="Number of consecutive losses for critical mode",
    )
    critical_action: str = Field(
        default="pause",
        description="Action at critical threshold: 'pause' or 'further_reduce'",
    )
    further_reduction_factor: Decimal = Field(
        default=Decimal("0.25"),
        description="Factor for further reduction at critical threshold",
    )

    model_config = {"json_encoders": {Decimal: str}}


class TradeResult(BaseModel):
    """Record of a trade result for tracking."""

    trade_id: str
    closed_at: datetime = Field(default_factory=datetime.utcnow)
    outcome: TradeOutcome
    pnl_percent: Decimal
    pnl_absolute: Decimal
    entry_price: Decimal
    exit_price: Decimal
    token_address: str


class ConsecutiveLossState(BaseModel):
    """Current state of consecutive loss tracking."""

    consecutive_loss_count: int = Field(default=0, ge=0)
    sizing_mode: SizingMode = Field(default=SizingMode.NORMAL)
    current_size_factor: Decimal = Field(default=Decimal("1.0"))
    last_trade_outcome: TradeOutcome | None = None
    streak_started_at: datetime | None = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def is_reduced(self) -> bool:
        """Whether position sizing is currently reduced."""
        return self.sizing_mode != SizingMode.NORMAL

    @computed_field
    @property
    def reduction_percent(self) -> Decimal:
        """Current reduction as percentage."""
        return (Decimal("1") - self.current_size_factor) * Decimal("100")


class SizeAdjustmentResult(BaseModel):
    """Result of a position size adjustment."""

    original_size: Decimal
    adjusted_size: Decimal
    size_factor: Decimal
    sizing_mode: SizingMode
    consecutive_losses: int
    reason: str


class LossStreakEvent(BaseModel):
    """Event record for loss streak changes."""

    id: str | None = None
    event_type: str  # "reduction_triggered", "critical_triggered", "recovery"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    consecutive_losses: int
    previous_mode: SizingMode
    new_mode: SizingMode
    previous_factor: Decimal
    new_factor: Decimal
    triggering_trade_id: str | None = None


# Story 5-3: Win Rate Circuit Breaker Models


class WinRateConfig(BaseModel):
    """Configuration for win rate circuit breaker."""

    threshold_percent: Decimal = Field(
        default=Decimal("40.0"),
        ge=Decimal("10.0"),
        le=Decimal("60.0"),
        description="Win rate threshold below which circuit breaker triggers",
    )
    window_size: int = Field(
        default=50,
        ge=10,
        le=200,
        description="Number of trades in rolling window",
    )
    minimum_trades: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Minimum trades required before circuit breaker applies",
    )
    enable_caution_flag: bool = Field(
        default=True,
        description="Show caution flag when below minimum trades",
    )

    model_config = {"json_encoders": {Decimal: str}}


class TradeRecord(BaseModel):
    """Minimal trade record for win rate calculation."""

    trade_id: str
    closed_at: datetime
    is_win: bool
    pnl_percent: Decimal


class WinRateSnapshot(BaseModel):
    """Point-in-time win rate calculation."""

    calculated_at: datetime = Field(default_factory=datetime.utcnow)
    window_size: int
    trades_in_window: int
    winning_trades: int
    losing_trades: int

    @computed_field
    @property
    def win_rate_percent(self) -> Decimal:
        """Win rate as percentage."""
        if self.trades_in_window == 0:
            return Decimal("0")
        return (
            Decimal(self.winning_trades) / Decimal(self.trades_in_window)
        ) * Decimal("100")

    @computed_field
    @property
    def has_sufficient_history(self) -> bool:
        """Whether enough trades exist for reliable calculation."""
        return self.trades_in_window >= 20  # Will be checked against config

    @computed_field
    @property
    def loss_rate_percent(self) -> Decimal:
        """Loss rate as percentage."""
        return Decimal("100") - self.win_rate_percent


class WinRateCheckResult(BaseModel):
    """Result of win rate circuit breaker check."""

    snapshot: WinRateSnapshot
    threshold_percent: Decimal
    is_breached: bool
    is_caution: bool  # True if below minimum trades
    trigger: CircuitBreakerTrigger | None = None
    message: str


class WinRateAnalysis(BaseModel):
    """Detailed analysis of recent trades for investigation."""

    snapshot: WinRateSnapshot
    recent_trades: list[TradeRecord]
    losing_streak_current: int
    winning_streak_current: int
    avg_win_pnl_percent: Decimal
    avg_loss_pnl_percent: Decimal
    profit_factor: Decimal  # total_wins / total_losses
    largest_win_percent: Decimal
    largest_loss_percent: Decimal


# Story 5-4: Maximum Concurrent Position Limits Models


class PositionLimitConfig(BaseModel):
    """Configuration for maximum concurrent positions."""

    max_positions: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of concurrent open positions",
    )
    enable_queue: bool = Field(
        default=True,
        description="Queue blocked signals for later execution",
    )
    max_queue_size: int = Field(
        default=10,
        ge=0,
        le=50,
        description="Maximum signals to queue (0 = unlimited)",
    )
    queue_expiry_minutes: int = Field(
        default=60,
        ge=5,
        le=1440,
        description="Minutes after which queued signals expire",
    )


class QueuedSignal(BaseModel):
    """Signal queued for later execution."""

    id: str | None = None
    signal_id: str
    queued_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    signal_data: dict
    priority: int = Field(default=0)  # Higher = more priority
    status: str = Field(default="pending")  # pending, executed, expired, cancelled

    @computed_field
    @property
    def is_expired(self) -> bool:
        """Check if signal has expired."""
        return datetime.utcnow() > self.expires_at

    @computed_field
    @property
    def time_remaining_seconds(self) -> int:
        """Seconds until expiry."""
        delta = self.expires_at - datetime.utcnow()
        return max(0, int(delta.total_seconds()))


class PositionLimitCheckResult(BaseModel):
    """Result of position limit check."""

    current_positions: int
    max_positions: int
    can_open: bool
    slots_available: int
    queued_signals_count: int
    message: str


class PositionSlotEvent(BaseModel):
    """Event when position slot becomes available."""

    id: str | None = None
    event_type: str  # "slot_freed", "signal_executed", "signal_expired"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    position_id: str | None = None  # Position that closed
    signal_id: str | None = None  # Signal that was processed
    queue_length_before: int
    queue_length_after: int


class BlockedTradeResponse(BaseModel):
    """Response when trade is blocked due to position limit."""

    blocked: bool = True
    reason: str
    current_positions: int
    max_positions: int
    queued: bool = False
    queue_position: int | None = None
    signal_id: str


# Story 5-6: Manual Pause/Resume Controls Models


class PauseReason(str, Enum):
    """Reason for manual pause."""

    MAINTENANCE = "maintenance"
    INVESTIGATION = "investigation"
    MARKET_CONDITIONS = "market_conditions"
    SYSTEM_ISSUE = "system_issue"
    OTHER = "other"


class SystemState(BaseModel):
    """Current system state."""

    status: SystemStatus = Field(default=SystemStatus.RUNNING)
    paused_at: datetime | None = None
    paused_by: str | None = None
    pause_reason: PauseReason | None = None
    pause_note: str | None = None
    resumed_at: datetime | None = None
    resumed_by: str | None = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def is_paused(self) -> bool:
        """Whether system is currently paused."""
        return self.status != SystemStatus.RUNNING

    @computed_field
    @property
    def is_circuit_breaker_pause(self) -> bool:
        """Whether pause is due to circuit breaker."""
        return self.status in [
            SystemStatus.PAUSED_DRAWDOWN,
            SystemStatus.PAUSED_WIN_RATE,
            SystemStatus.PAUSED_CONSECUTIVE_LOSS,
        ]

    @computed_field
    @property
    def pause_duration_seconds(self) -> int | None:
        """Duration of current pause in seconds."""
        if self.paused_at and self.is_paused:
            return int((datetime.utcnow() - self.paused_at).total_seconds())
        return None


class PauseRequest(BaseModel):
    """Request to pause the system."""

    operator_id: str
    reason: PauseReason
    note: str | None = None


class ResumeRequest(BaseModel):
    """Request to resume the system."""

    operator_id: str
    acknowledge_warning: bool = False  # Required if resuming from circuit breaker


class PauseResumeEvent(BaseModel):
    """Historical record of pause/resume event."""

    id: str | None = None
    event_type: str  # "pause" or "resume"
    occurred_at: datetime = Field(default_factory=datetime.utcnow)
    operator_id: str
    previous_status: SystemStatus
    new_status: SystemStatus
    reason: PauseReason | None = None
    note: str | None = None


class SystemStateResponse(BaseModel):
    """API response for system state."""

    state: SystemState
    can_trade: bool
    can_exit: bool  # Always True - exits work during pause
    active_circuit_breakers: list[str]
    recent_events: list[PauseResumeEvent]
