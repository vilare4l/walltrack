"""Order model with state machine.

Models for tracking trade orders from creation to execution,
with retry logic and state machine validation.

Story 10.5-12: Added locking fields for retry worker.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, computed_field


class OrderType(str, Enum):
    """Type of order."""

    ENTRY = "entry"
    EXIT = "exit"


class OrderSide(str, Enum):
    """Order side."""

    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    """Order status with valid transitions."""

    PENDING = "pending"  # Waiting to be submitted
    SUBMITTED = "submitted"  # Sent to Jupiter API
    CONFIRMING = "confirming"  # TX sent, waiting for confirmation
    FILLED = "filled"  # Successfully executed
    FAILED = "failed"  # Execution failed (may retry)
    CANCELLED = "cancelled"  # Permanently cancelled


# Valid state transitions
ORDER_TRANSITIONS: dict[OrderStatus, list[OrderStatus]] = {
    OrderStatus.PENDING: [OrderStatus.SUBMITTED, OrderStatus.CANCELLED],
    OrderStatus.SUBMITTED: [OrderStatus.CONFIRMING, OrderStatus.FAILED],
    OrderStatus.CONFIRMING: [OrderStatus.FILLED, OrderStatus.FAILED],
    OrderStatus.FAILED: [OrderStatus.PENDING, OrderStatus.CANCELLED],
    OrderStatus.FILLED: [],  # Terminal state
    OrderStatus.CANCELLED: [],  # Terminal state
}

# Retry backoff delays (seconds)
RETRY_DELAYS = [5, 15, 45]  # Exponential backoff


class OrderTransitionError(Exception):
    """Invalid order state transition."""

    pass


class Order(BaseModel):
    """
    Order model representing a trade request.

    Tracks the full lifecycle from creation to execution.
    """

    id: UUID = Field(default_factory=uuid4)

    # Type and direction
    order_type: OrderType
    side: OrderSide

    # References
    signal_id: Optional[str] = None  # For ENTRY orders
    position_id: Optional[str] = None  # For EXIT orders
    exit_reason: Optional[str] = None  # For EXIT orders (e.g., "stop_loss", "take_profit")

    # Token info
    token_address: str
    token_symbol: Optional[str] = None

    # Amounts
    amount_sol: Decimal
    amount_tokens: Optional[Decimal] = None  # Filled after execution

    # Pricing
    expected_price: Decimal
    actual_price: Optional[Decimal] = None
    max_slippage_bps: int = 100  # 1% default

    # Status
    status: OrderStatus = OrderStatus.PENDING

    # Execution details
    tx_signature: Optional[str] = None
    filled_at: Optional[datetime] = None

    # Retry management
    attempt_count: int = 0
    max_attempts: int = 3
    last_error: Optional[str] = None
    next_retry_at: Optional[datetime] = None

    # Simulation
    is_simulated: bool = False

    # Locking (for retry worker concurrency control)
    locked_until: Optional[datetime] = None
    locked_by: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @computed_field
    @property
    def slippage_bps(self) -> Optional[int]:
        """Calculate actual slippage in basis points."""
        if self.actual_price is None or self.expected_price == 0:
            return None
        diff = abs(self.actual_price - self.expected_price) / self.expected_price
        return int(diff * 10000)

    @computed_field
    @property
    def can_retry(self) -> bool:
        """Check if order can be retried."""
        return self.status == OrderStatus.FAILED and self.attempt_count < self.max_attempts

    @computed_field
    @property
    def is_terminal(self) -> bool:
        """Check if order is in terminal state."""
        return self.status in [OrderStatus.FILLED, OrderStatus.CANCELLED]

    def transition_to(self, new_status: OrderStatus) -> None:
        """
        Transition to new status with validation.

        Raises:
            OrderTransitionError: If transition is invalid
        """
        valid_next = ORDER_TRANSITIONS.get(self.status, [])

        if new_status not in valid_next:
            raise OrderTransitionError(
                f"Invalid transition: {self.status.value} -> {new_status.value}. "
                f"Valid transitions: {[s.value for s in valid_next]}"
            )

        self.status = new_status
        self.updated_at = datetime.utcnow()

    def mark_submitted(self) -> None:
        """Mark order as submitted to Jupiter."""
        self.transition_to(OrderStatus.SUBMITTED)

    def mark_confirming(self, tx_signature: str) -> None:
        """Mark order as confirming with TX signature."""
        self.tx_signature = tx_signature
        self.transition_to(OrderStatus.CONFIRMING)

    def mark_filled(
        self,
        actual_price: Decimal,
        amount_tokens: Optional[Decimal] = None,
    ) -> None:
        """Mark order as successfully filled."""
        self.actual_price = actual_price
        self.amount_tokens = amount_tokens
        self.filled_at = datetime.utcnow()
        self.transition_to(OrderStatus.FILLED)

    def mark_failed(self, error: str) -> None:
        """Mark order as failed and schedule retry if possible."""
        self.last_error = error
        self.attempt_count += 1
        self.transition_to(OrderStatus.FAILED)

        if self.can_retry:
            delay_index = min(self.attempt_count - 1, len(RETRY_DELAYS) - 1)
            delay = RETRY_DELAYS[delay_index]
            self.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)

    def schedule_retry(self) -> None:
        """Move failed order back to pending for retry."""
        if not self.can_retry:
            raise OrderTransitionError(
                f"Cannot retry: attempts={self.attempt_count}/{self.max_attempts}"
            )
        self.transition_to(OrderStatus.PENDING)
        self.next_retry_at = None

    def cancel(self, reason: str = "Manually cancelled") -> None:
        """Cancel the order permanently."""
        self.last_error = reason
        self.transition_to(OrderStatus.CANCELLED)


class OrderCreateRequest(BaseModel):
    """Request to create a new order."""

    order_type: OrderType
    side: OrderSide
    token_address: str
    token_symbol: Optional[str] = None
    amount_sol: Decimal
    expected_price: Decimal
    max_slippage_bps: int = 100
    signal_id: Optional[str] = None
    position_id: Optional[str] = None
    is_simulated: bool = False


class OrderSummary(BaseModel):
    """Summary view of an order for UI."""

    id: UUID
    order_type: OrderType
    side: OrderSide
    token_symbol: Optional[str]
    amount_sol: Decimal
    status: OrderStatus
    attempt_count: int
    is_simulated: bool
    created_at: datetime
    slippage_bps: Optional[int] = None
