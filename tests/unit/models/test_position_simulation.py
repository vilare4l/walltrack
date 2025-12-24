"""Tests for Position model simulation support."""

import pytest
from datetime import datetime, UTC
from uuid import uuid4

from walltrack.models.position import Position, PositionStatus


class TestPositionSimulatedField:
    """Tests for Position simulated field."""

    def test_position_has_simulated_field(self) -> None:
        """Test that Position model has simulated field."""
        position = Position(
            signal_id=str(uuid4()),
            token_address="TestToken1111111111111111111111111111111111",
            entry_price=0.001,
            entry_amount_sol=1.0,
            entry_amount_tokens=100000.0,
            current_amount_tokens=100000.0,
            exit_strategy_id="default",
            conviction_tier="standard",
            simulated=True,
        )
        assert hasattr(position, "simulated")
        assert position.simulated is True

    def test_position_simulated_defaults_to_false(self) -> None:
        """Test that simulated field defaults to False."""
        position = Position(
            signal_id=str(uuid4()),
            token_address="TestToken1111111111111111111111111111111111",
            entry_price=0.001,
            entry_amount_sol=1.0,
            entry_amount_tokens=100000.0,
            current_amount_tokens=100000.0,
            exit_strategy_id="default",
            conviction_tier="standard",
        )
        assert position.simulated is False

    def test_position_is_simulated_property(self) -> None:
        """Test is_simulated computed property."""
        position = Position(
            signal_id=str(uuid4()),
            token_address="TestToken1111111111111111111111111111111111",
            entry_price=0.001,
            entry_amount_sol=1.0,
            entry_amount_tokens=100000.0,
            current_amount_tokens=100000.0,
            exit_strategy_id="default",
            conviction_tier="standard",
            simulated=True,
        )
        assert position.is_simulated is True

    def test_live_position_is_not_simulated(self) -> None:
        """Test that live position is_simulated returns False."""
        position = Position(
            signal_id=str(uuid4()),
            token_address="TestToken1111111111111111111111111111111111",
            entry_price=0.001,
            entry_amount_sol=1.0,
            entry_amount_tokens=100000.0,
            current_amount_tokens=100000.0,
            exit_strategy_id="default",
            conviction_tier="standard",
            simulated=False,
        )
        assert position.is_simulated is False
