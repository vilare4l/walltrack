"""Unit tests for OrderFactory."""

from decimal import Decimal

import pytest

from walltrack.models.order import OrderSide, OrderStatus, OrderType
from walltrack.models.position import Position, PositionLevels, PositionStatus
from walltrack.services.order.order_factory import OrderFactory


class TestOrderFactoryCreation:
    """Test OrderFactory initialization."""

    def test_factory_default_mode(self):
        """Factory defaults to non-simulation mode."""
        factory = OrderFactory()
        assert factory.is_simulation_mode is False

    def test_factory_simulation_mode(self):
        """Factory can be set to simulation mode."""
        factory = OrderFactory(is_simulation_mode=True)
        assert factory.is_simulation_mode is True


class TestCreateEntryOrder:
    """Test entry order creation."""

    def test_create_entry_order_basic(self):
        """Create a basic entry order."""
        factory = OrderFactory()
        order = factory.create_entry_order(
            signal_id="sig-123",
            token_address="token-abc",
            amount_sol=Decimal("1.5"),
            expected_price=Decimal("0.001"),
        )

        assert order.order_type == OrderType.ENTRY
        assert order.side == OrderSide.BUY
        assert order.signal_id == "sig-123"
        assert order.token_address == "token-abc"
        assert order.amount_sol == Decimal("1.5")
        assert order.expected_price == Decimal("0.001")
        assert order.status == OrderStatus.PENDING
        assert order.is_simulated is False

    def test_create_entry_order_with_symbol(self):
        """Create entry order with token symbol."""
        factory = OrderFactory()
        order = factory.create_entry_order(
            signal_id="sig-123",
            token_address="token-abc",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            token_symbol="TEST",
        )

        assert order.token_symbol == "TEST"

    def test_create_entry_order_custom_slippage(self):
        """Create entry order with custom slippage."""
        factory = OrderFactory()
        order = factory.create_entry_order(
            signal_id="sig-123",
            token_address="token-abc",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            max_slippage_bps=200,
        )

        assert order.max_slippage_bps == 200

    def test_create_entry_order_simulation_mode(self):
        """Entry orders inherit simulation mode from factory."""
        factory = OrderFactory(is_simulation_mode=True)
        order = factory.create_entry_order(
            signal_id="sig-123",
            token_address="token-abc",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )

        assert order.is_simulated is True


class TestCreateExitOrder:
    """Test exit order creation."""

    @pytest.fixture
    def sample_position(self) -> Position:
        """Create a sample position for testing."""
        return Position(
            id="pos-123",
            signal_id="sig-456",
            token_address="token-xyz",
            token_symbol="XYZ",
            status=PositionStatus.OPEN,
            entry_price=0.001,
            entry_amount_sol=1.0,
            entry_amount_tokens=1000.0,
            current_amount_tokens=1000.0,
            exit_strategy_id="strat-1",
            conviction_tier="high",
            levels=PositionLevels(
                entry_price=0.001,
                stop_loss_price=0.0005,
                take_profit_levels=[],
            ),
            simulated=False,
        )

    def test_create_exit_order_basic(self, sample_position: Position):
        """Create a basic exit order."""
        factory = OrderFactory()
        order = factory.create_exit_order(
            position=sample_position,
            amount_tokens=Decimal("500"),
            expected_price=Decimal("0.002"),
            exit_reason="take_profit",
        )

        assert order.order_type == OrderType.EXIT
        assert order.side == OrderSide.SELL
        assert order.position_id == "pos-123"
        assert order.token_address == "token-xyz"
        assert order.token_symbol == "XYZ"
        assert order.amount_tokens == Decimal("500")
        assert order.expected_price == Decimal("0.002")
        # amount_sol = 500 * 0.002 = 1.0
        assert order.amount_sol == Decimal("1.0")
        assert order.status == OrderStatus.PENDING

    def test_create_exit_order_inherits_simulation(self, sample_position: Position):
        """Exit order inherits simulation from position."""
        sample_position.simulated = True
        factory = OrderFactory()
        order = factory.create_exit_order(
            position=sample_position,
            amount_tokens=Decimal("500"),
            expected_price=Decimal("0.002"),
            exit_reason="stop_loss",
        )

        assert order.is_simulated is True

    def test_create_exit_order_factory_simulation_mode(self, sample_position: Position):
        """Exit order uses factory simulation mode."""
        factory = OrderFactory(is_simulation_mode=True)
        order = factory.create_exit_order(
            position=sample_position,
            amount_tokens=Decimal("500"),
            expected_price=Decimal("0.002"),
            exit_reason="stop_loss",
        )

        assert order.is_simulated is True


class TestFromRequest:
    """Test order creation from API request."""

    def test_from_request_entry(self):
        """Create order from entry request."""
        from walltrack.models.order import OrderCreateRequest

        factory = OrderFactory()
        request = OrderCreateRequest(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token-123",
            token_symbol="TOK",
            amount_sol=Decimal("2.5"),
            expected_price=Decimal("0.0015"),
            max_slippage_bps=150,
            signal_id="sig-999",
        )

        order = factory.from_request(request)

        assert order.order_type == OrderType.ENTRY
        assert order.side == OrderSide.BUY
        assert order.token_address == "token-123"
        assert order.token_symbol == "TOK"
        assert order.amount_sol == Decimal("2.5")
        assert order.signal_id == "sig-999"
        assert order.max_slippage_bps == 150

    def test_from_request_simulation_in_request(self):
        """Request simulation flag is respected."""
        from walltrack.models.order import OrderCreateRequest

        factory = OrderFactory()
        request = OrderCreateRequest(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token-123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=True,
        )

        order = factory.from_request(request)
        assert order.is_simulated is True

    def test_from_request_factory_simulation_override(self):
        """Factory simulation mode overrides request."""
        from walltrack.models.order import OrderCreateRequest

        factory = OrderFactory(is_simulation_mode=True)
        request = OrderCreateRequest(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token-123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=False,  # Request says not simulated
        )

        order = factory.from_request(request)
        # But factory is in simulation mode, so it's simulated
        assert order.is_simulated is True
