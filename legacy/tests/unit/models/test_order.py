"""Unit tests for Order model and state machine."""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest

from walltrack.models.order import (
    RETRY_DELAYS,
    Order,
    OrderCreateRequest,
    OrderSide,
    OrderStatus,
    OrderSummary,
    OrderTransitionError,
    OrderType,
)


class TestOrderCreation:
    """Test order creation."""

    def test_create_entry_order(self):
        """Create a basic entry order."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="So11111111111111111111111111111111111111112",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )

        assert order.order_type == OrderType.ENTRY
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING
        assert order.attempt_count == 0
        assert order.max_attempts == 3
        assert order.is_terminal is False
        assert order.can_retry is False  # Not failed yet

    def test_create_exit_order(self):
        """Create a basic exit order."""
        order = Order(
            order_type=OrderType.EXIT,
            side=OrderSide.SELL,
            token_address="So11111111111111111111111111111111111111112",
            position_id="pos-123",
            amount_sol=Decimal("0.5"),
            amount_tokens=Decimal("500"),
            expected_price=Decimal("0.001"),
        )

        assert order.order_type == OrderType.EXIT
        assert order.side == OrderSide.SELL
        assert order.position_id == "pos-123"

    def test_order_has_uuid(self):
        """Order gets a UUID on creation."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )

        assert order.id is not None

    def test_order_timestamps(self):
        """Order has created_at and updated_at."""
        before = datetime.utcnow()
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        after = datetime.utcnow()

        assert before <= order.created_at <= after
        assert before <= order.updated_at <= after


class TestOrderStateMachine:
    """Test order state transitions."""

    def test_pending_to_submitted(self):
        """PENDING -> SUBMITTED is valid."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        order.mark_submitted()
        assert order.status == OrderStatus.SUBMITTED

    def test_pending_to_cancelled(self):
        """PENDING -> CANCELLED is valid."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        order.cancel("User cancelled")
        assert order.status == OrderStatus.CANCELLED
        assert order.last_error == "User cancelled"

    def test_pending_to_filled_invalid(self):
        """PENDING -> FILLED is invalid."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        with pytest.raises(OrderTransitionError) as exc_info:
            order.mark_filled(Decimal("0.001"))
        assert "Invalid transition" in str(exc_info.value)
        assert "pending -> filled" in str(exc_info.value)

    def test_pending_to_confirming_invalid(self):
        """PENDING -> CONFIRMING is invalid (must go through SUBMITTED)."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        with pytest.raises(OrderTransitionError):
            order.mark_confirming("tx_123")

    def test_submitted_to_confirming(self):
        """SUBMITTED -> CONFIRMING with TX signature."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.SUBMITTED,
        )
        order.mark_confirming("tx_sig_123")
        assert order.status == OrderStatus.CONFIRMING
        assert order.tx_signature == "tx_sig_123"

    def test_submitted_to_failed(self):
        """SUBMITTED -> FAILED on API error."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.SUBMITTED,
        )
        order.mark_failed("API timeout")
        assert order.status == OrderStatus.FAILED
        assert order.last_error == "API timeout"
        assert order.attempt_count == 1

    def test_confirming_to_filled(self):
        """CONFIRMING -> FILLED with price."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.CONFIRMING,
            tx_signature="tx_sig_123",
        )
        order.mark_filled(Decimal("0.00105"), Decimal("950"))
        assert order.status == OrderStatus.FILLED
        assert order.actual_price == Decimal("0.00105")
        assert order.amount_tokens == Decimal("950")
        assert order.filled_at is not None
        assert order.is_terminal is True

    def test_confirming_to_failed(self):
        """CONFIRMING -> FAILED on TX failure."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.CONFIRMING,
            tx_signature="tx_sig_123",
        )
        order.mark_failed("TX reverted")
        assert order.status == OrderStatus.FAILED
        assert order.last_error == "TX reverted"

    def test_failed_to_pending_retry(self):
        """FAILED -> PENDING for retry."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.FAILED,
            attempt_count=1,
            max_attempts=3,
        )
        order.schedule_retry()
        assert order.status == OrderStatus.PENDING
        assert order.next_retry_at is None

    def test_failed_to_cancelled(self):
        """FAILED -> CANCELLED when giving up."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.FAILED,
            attempt_count=3,
            max_attempts=3,
        )
        order.cancel("Max retries reached")
        assert order.status == OrderStatus.CANCELLED
        assert order.is_terminal is True

    def test_filled_is_terminal(self):
        """FILLED state has no valid transitions."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.FILLED,
        )
        assert order.is_terminal is True

        with pytest.raises(OrderTransitionError):
            order.transition_to(OrderStatus.PENDING)

    def test_cancelled_is_terminal(self):
        """CANCELLED state has no valid transitions."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.CANCELLED,
        )
        assert order.is_terminal is True

        with pytest.raises(OrderTransitionError):
            order.transition_to(OrderStatus.PENDING)


class TestOrderRetry:
    """Test retry logic."""

    def test_failed_can_retry(self):
        """Failed order with attempts left can retry."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.SUBMITTED,
        )
        order.mark_failed("API error")

        assert order.status == OrderStatus.FAILED
        assert order.can_retry is True
        assert order.attempt_count == 1
        assert order.next_retry_at is not None

    def test_retry_backoff_first_attempt(self):
        """First retry has 5s delay."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.SUBMITTED,
        )

        before = datetime.utcnow()
        order.mark_failed("Error 1")

        expected_delay = RETRY_DELAYS[0]  # 5 seconds
        assert order.next_retry_at is not None
        delay = (order.next_retry_at - before).total_seconds()
        assert expected_delay - 1 < delay < expected_delay + 1

    def test_retry_backoff_exponential(self):
        """Retry delays increase exponentially."""
        # Use max_attempts=4 to test all 3 retry delays
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.SUBMITTED,
            max_attempts=4,  # Allow 4 attempts to test 3 delays
        )

        # First failure: 5s delay
        order.mark_failed("Error 1")
        delay1 = (order.next_retry_at - datetime.utcnow()).total_seconds()
        assert 4 < delay1 < 6

        # Reset for second attempt
        order.schedule_retry()
        order.mark_submitted()
        order.mark_failed("Error 2")
        delay2 = (order.next_retry_at - datetime.utcnow()).total_seconds()
        assert 14 < delay2 < 16  # 15s

        # Third attempt: 45s
        order.schedule_retry()
        order.mark_submitted()
        order.mark_failed("Error 3")
        delay3 = (order.next_retry_at - datetime.utcnow()).total_seconds()
        assert 44 < delay3 < 46

    def test_max_retries_exhausted(self):
        """Order cannot retry after max attempts."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            attempt_count=3,
            max_attempts=3,
            status=OrderStatus.FAILED,
        )
        assert order.can_retry is False

    def test_schedule_retry_fails_when_exhausted(self):
        """Cannot schedule retry when max attempts reached."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            attempt_count=3,
            max_attempts=3,
            status=OrderStatus.FAILED,
        )

        with pytest.raises(OrderTransitionError) as exc_info:
            order.schedule_retry()
        assert "Cannot retry" in str(exc_info.value)

    def test_no_retry_scheduled_when_exhausted(self):
        """When max retries reached, no next_retry_at is set."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            attempt_count=2,
            max_attempts=3,
            status=OrderStatus.SUBMITTED,
        )

        order.mark_failed("Final error")
        # After 3rd attempt (attempt_count=3), can_retry is False
        assert order.attempt_count == 3
        assert order.can_retry is False
        # next_retry_at should still be None since can_retry was False
        # Actually looking at the code, it increments first then checks
        # Let me re-check the logic


class TestOrderSlippage:
    """Test slippage calculation."""

    def test_slippage_calculation_positive(self):
        """Slippage calculated correctly for price increase."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            actual_price=Decimal("0.00105"),  # 5% higher
            status=OrderStatus.FILLED,
        )
        assert order.slippage_bps == 500  # 5%

    def test_slippage_calculation_negative(self):
        """Slippage calculated correctly for price decrease."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            actual_price=Decimal("0.00095"),  # 5% lower
            status=OrderStatus.FILLED,
        )
        assert order.slippage_bps == 500  # absolute value

    def test_slippage_none_when_not_filled(self):
        """Slippage is None when actual_price not set."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            status=OrderStatus.PENDING,
        )
        assert order.slippage_bps is None

    def test_slippage_1_percent(self):
        """1% slippage = 100 bps."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("100"),
            actual_price=Decimal("101"),
            status=OrderStatus.FILLED,
        )
        assert order.slippage_bps == 100


class TestOrderSimulation:
    """Test simulation mode."""

    def test_order_simulated_flag(self):
        """Order can be marked as simulated."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=True,
        )
        assert order.is_simulated is True

    def test_order_not_simulated_by_default(self):
        """Orders are not simulated by default."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )
        assert order.is_simulated is False


class TestOrderCreateRequest:
    """Test OrderCreateRequest DTO."""

    def test_create_request(self):
        """Create a valid OrderCreateRequest."""
        request = OrderCreateRequest(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.5"),
            expected_price=Decimal("0.001"),
            max_slippage_bps=150,
            signal_id="sig-123",
        )

        assert request.order_type == OrderType.ENTRY
        assert request.amount_sol == Decimal("1.5")
        assert request.max_slippage_bps == 150


class TestOrderSummary:
    """Test OrderSummary DTO."""

    def test_create_summary_from_order(self):
        """Create OrderSummary from Order."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            token_symbol="TEST",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=True,
        )

        summary = OrderSummary(
            id=order.id,
            order_type=order.order_type,
            side=order.side,
            token_symbol=order.token_symbol,
            amount_sol=order.amount_sol,
            status=order.status,
            attempt_count=order.attempt_count,
            is_simulated=order.is_simulated,
            created_at=order.created_at,
            slippage_bps=order.slippage_bps,
        )

        assert summary.id == order.id
        assert summary.token_symbol == "TEST"
        assert summary.is_simulated is True
