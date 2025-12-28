"""Tests for the Orders UI page and components.

Story 10.5-13: Order list, filtering, details, and manual actions.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType
from walltrack.ui.components.orders import (
    format_order_for_table,
    format_order_summary,
    get_order_actions,
    get_status_color,
    get_status_emoji,
)


class TestStatusColor:
    """Tests for status color mapping."""

    def test_pending_is_orange(self) -> None:
        """Pending status should be orange."""
        assert get_status_color(OrderStatus.PENDING) == "orange"

    def test_submitted_is_blue(self) -> None:
        """Submitted status should be blue."""
        assert get_status_color(OrderStatus.SUBMITTED) == "blue"

    def test_confirming_is_purple(self) -> None:
        """Confirming status should be purple."""
        assert get_status_color(OrderStatus.CONFIRMING) == "purple"

    def test_filled_is_green(self) -> None:
        """Filled status should be green."""
        assert get_status_color(OrderStatus.FILLED) == "green"

    def test_failed_is_red(self) -> None:
        """Failed status should be red."""
        assert get_status_color(OrderStatus.FAILED) == "red"

    def test_cancelled_is_gray(self) -> None:
        """Cancelled status should be gray."""
        assert get_status_color(OrderStatus.CANCELLED) == "gray"

    def test_string_status_works(self) -> None:
        """String status should be converted to enum."""
        assert get_status_color("pending") == "orange"
        assert get_status_color("filled") == "green"

    def test_invalid_string_returns_gray(self) -> None:
        """Invalid string status should return gray."""
        assert get_status_color("invalid") == "gray"


class TestStatusEmoji:
    """Tests for status emoji mapping."""

    def test_all_statuses_have_emoji(self) -> None:
        """All statuses should have an emoji."""
        for status in OrderStatus:
            emoji = get_status_emoji(status)
            assert isinstance(emoji, str)

    def test_string_status_works(self) -> None:
        """String status should be converted to enum."""
        emoji = get_status_emoji("pending")
        assert isinstance(emoji, str)

    def test_invalid_string_returns_empty(self) -> None:
        """Invalid string status should return empty string."""
        assert get_status_emoji("invalid") == ""


class TestFormatOrderSummary:
    """Tests for order summary formatting."""

    def test_format_order_model(self) -> None:
        """Format Order model correctly."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddressHere12345",
            token_symbol="TEST",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
        )
        order.mark_submitted()

        summary = format_order_summary(order)
        assert "[SUBMITTED]" in summary
        assert "ENTRY" in summary
        assert "0.5000 SOL" in summary
        assert "TEST" in summary

    def test_format_order_dict(self) -> None:
        """Format order dict correctly."""
        order_dict = {
            "status": "filled",
            "order_type": "exit",
            "token_symbol": "MYTOKEN",
            "token_address": "SomeAddress",
            "amount_sol": 1.5,
        }

        summary = format_order_summary(order_dict)
        assert "[FILLED]" in summary
        assert "EXIT" in summary
        assert "1.5000 SOL" in summary
        assert "MYTOKEN" in summary

    def test_format_dict_without_symbol(self) -> None:
        """Format order dict without symbol uses truncated address."""
        order_dict = {
            "status": "pending",
            "order_type": "entry",
            "token_address": "LongTokenAddressHere",
            "amount_sol": 0.25,
        }

        summary = format_order_summary(order_dict)
        assert "LongToke" in summary  # First 8 chars


class TestFormatOrderForTable:
    """Tests for table row formatting."""

    def test_format_order_model_for_table(self) -> None:
        """Format Order model for table row."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddressHere12345",
            token_symbol="TEST",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
        )

        row = format_order_for_table(order)
        assert len(row) == 8
        assert row[0] == str(order.id)[:8]  # Truncated ID
        assert row[1] == "entry"  # Type
        assert row[2] == "TEST"  # Symbol
        assert row[3] == 0.5  # Amount
        assert row[4] == "pending"  # Status
        assert row[5] == 0  # Attempts

    def test_format_order_dict_for_table(self) -> None:
        """Format order dict for table row."""
        order_id = str(uuid4())
        order_dict = {
            "id": order_id,
            "order_type": "exit",
            "token_symbol": "MYTOKEN",
            "token_address": "SomeAddress",
            "amount_sol": 1.5,
            "status": "filled",
            "attempt_count": 2,
            "created_at": "2024-12-25T10:30:00Z",
            "updated_at": "2024-12-25T10:31:00Z",
        }

        row = format_order_for_table(order_dict)
        assert len(row) == 8
        assert row[0] == order_id[:8]
        assert row[1] == "exit"
        assert row[2] == "MYTOKEN"
        assert row[3] == 1.5
        assert row[4] == "filled"
        assert row[5] == 2


class TestGetOrderActions:
    """Tests for available order actions."""

    def test_pending_order_can_cancel_and_retry(self) -> None:
        """Pending order can be cancelled or retried."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddress",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
        )

        actions = get_order_actions(order)
        assert actions["can_cancel"] is True
        assert actions["can_retry"] is True

    def test_failed_order_can_cancel_and_retry(self) -> None:
        """Failed order can be cancelled or retried."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddress",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
        )
        order.mark_submitted()
        order.mark_failed(error="Test error")

        actions = get_order_actions(order)
        assert actions["can_cancel"] is True
        assert actions["can_retry"] is True

    def test_filled_order_cannot_cancel_or_retry(self) -> None:
        """Filled order cannot be cancelled or retried."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddress",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
        )
        # Transition through states to FILLED
        order.mark_submitted()
        order.mark_confirming(tx_signature="test_tx_sig")
        order.mark_filled(
            actual_price=Decimal("0.001"),
            amount_tokens=Decimal("500"),
        )

        actions = get_order_actions(order)
        assert actions["can_cancel"] is False
        assert actions["can_retry"] is False

    def test_max_attempts_reached_cannot_retry(self) -> None:
        """Order at max attempts cannot be retried."""
        order = Order(
            id=uuid4(),
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="TokenAddress",
            amount_sol=Decimal("0.5"),
            expected_price=Decimal("0.001"),
            max_attempts=3,
        )
        # Simulate 3 failed attempts
        order.mark_submitted()
        order.mark_failed(error="Fail 1")
        order.schedule_retry()
        order.mark_submitted()
        order.mark_failed(error="Fail 2")
        order.schedule_retry()
        order.mark_submitted()
        order.mark_failed(error="Fail 3")

        actions = get_order_actions(order)
        assert actions["can_cancel"] is True
        assert actions["can_retry"] is False

    def test_dict_order_actions(self) -> None:
        """Order dict actions work correctly."""
        order_dict = {
            "status": "pending",
            "attempt_count": 0,
            "max_attempts": 3,
        }

        actions = get_order_actions(order_dict)
        assert actions["can_cancel"] is True
        assert actions["can_retry"] is True

    def test_dict_invalid_status_returns_no_actions(self) -> None:
        """Dict with invalid status returns no actions."""
        order_dict = {
            "status": "invalid",
            "attempt_count": 0,
            "max_attempts": 3,
        }

        actions = get_order_actions(order_dict)
        assert actions["can_cancel"] is False
        assert actions["can_retry"] is False
