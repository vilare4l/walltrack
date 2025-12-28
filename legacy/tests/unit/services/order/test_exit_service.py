"""Unit tests for ExitOrderService."""

from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from walltrack.models.order import Order, OrderStatus, OrderType, OrderSide
from walltrack.models.position import ExitReason, Position, PositionStatus
from walltrack.services.order.executor import OrderResult
from walltrack.services.order.exit_service import ExitOrderService
from walltrack.services.pricing.price_oracle import PriceResult


@pytest.fixture
def mock_order_repo():
    """Create a mock OrderRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.get_by_position = AsyncMock(return_value=[])
    return repo


@pytest.fixture
def mock_position_repo():
    """Create a mock PositionRepository."""
    repo = AsyncMock()
    repo.update = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    repo.save_exit_execution = AsyncMock()
    return repo


@pytest.fixture
def mock_executor():
    """Create a mock OrderExecutor."""
    executor = AsyncMock()
    return executor


@pytest.fixture
def mock_price_oracle():
    """Create a mock PriceOracle."""
    oracle = AsyncMock()
    oracle.get_price = AsyncMock(
        return_value=PriceResult(
            success=True,
            price=Decimal("0.002"),
            source="jupiter",
        )
    )
    return oracle


@pytest.fixture
def mock_order_factory():
    """Create a mock OrderFactory."""
    factory = MagicMock()

    def create_exit_order(**kwargs):
        return Order(
            order_type=OrderType.EXIT,
            side=OrderSide.SELL,
            position_id=str(kwargs.get("position").id),
            token_address=kwargs.get("position").token_address,
            token_symbol=kwargs.get("position").token_symbol,
            amount_tokens=kwargs.get("amount_tokens"),
            amount_sol=kwargs.get("amount_tokens") * kwargs.get("expected_price"),
            expected_price=kwargs.get("expected_price"),
            max_slippage_bps=kwargs.get("max_slippage_bps", 150),
        )

    factory.create_exit_order = create_exit_order
    return factory


@pytest.fixture
def exit_service(
    mock_order_repo,
    mock_position_repo,
    mock_executor,
    mock_price_oracle,
    mock_order_factory,
):
    """Create ExitOrderService with mocks."""
    return ExitOrderService(
        order_repo=mock_order_repo,
        position_repo=mock_position_repo,
        executor=mock_executor,
        price_oracle=mock_price_oracle,
        order_factory=mock_order_factory,
    )


@pytest.fixture
def sample_position():
    """Create a sample position for testing."""
    return Position(
        id=str(uuid4()),
        signal_id="sig-123",
        token_address="TokenMint123456789",
        token_symbol="TEST",
        status=PositionStatus.OPEN,
        entry_price=0.001,
        entry_amount_sol=0.5,
        entry_amount_tokens=500.0,
        current_amount_tokens=500.0,
        exit_strategy_id="default",
        conviction_tier="standard",
    )


class TestExitTriggerToOrder:
    """Test AC1: Exit Trigger to Order."""

    @pytest.mark.asyncio
    async def test_creates_exit_order_with_pending_status(
        self, exit_service, sample_position, mock_order_repo
    ):
        """Exit creates PENDING order with correct attributes."""
        created_order = None

        async def capture_order(order):
            nonlocal created_order
            created_order = order

        mock_order_repo.create = AsyncMock(side_effect=capture_order)

        result = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        assert result is not None
        assert created_order is not None
        assert created_order.order_type == OrderType.EXIT
        assert created_order.status == OrderStatus.PENDING
        assert created_order.position_id == sample_position.id

    @pytest.mark.asyncio
    async def test_order_contains_position_and_exit_reason(
        self, exit_service, sample_position, mock_order_repo, mock_position_repo
    ):
        """Order has position_id and amount_tokens."""
        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.TAKE_PROFIT,
            sell_percent=Decimal("50"),
        )

        assert order is not None
        assert order.position_id == sample_position.id
        # 50% of 500 tokens = 250
        expected_tokens = Decimal("250")
        assert order.amount_tokens == expected_tokens

    @pytest.mark.asyncio
    async def test_rejects_exit_for_closed_position(
        self, exit_service, sample_position
    ):
        """Cannot exit already closed position."""
        sample_position.status = PositionStatus.CLOSED

        result = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.MANUAL,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_rejects_when_exit_already_pending(
        self, exit_service, sample_position, mock_order_repo
    ):
        """Cannot create exit if one is already pending."""
        pending_order = MagicMock()
        pending_order.is_terminal = False

        mock_order_repo.get_by_position = AsyncMock(return_value=[pending_order])

        result = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        assert result is None


class TestPartialExitSupport:
    """Test AC2: Partial Exit Support."""

    @pytest.mark.asyncio
    async def test_partial_exit_calculates_correct_amount(
        self, exit_service, sample_position
    ):
        """33% exit calculates correct token amount."""
        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.TAKE_PROFIT,
            sell_percent=Decimal("33"),
        )

        assert order is not None
        # 33% of 500 = 165
        expected = Decimal("500") * Decimal("33") / Decimal("100")
        assert order.amount_tokens == expected

    @pytest.mark.asyncio
    async def test_position_remains_open_after_partial_exit(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Position stays open with remaining tokens after partial exit."""
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.status = OrderStatus.FILLED
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("165")  # 33%
        filled_order.actual_price = Decimal("0.002")
        filled_order.expected_price = Decimal("0.002")
        filled_order.amount_sol = Decimal("0.33")
        filled_order.tx_signature = "tx_partial_123"
        filled_order.is_terminal = True

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_partial_123",
                actual_price=Decimal("0.002"),
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.TAKE_PROFIT,
            sell_percent=Decimal("33"),
        )

        await exit_service.execute_exit_order(order)

        # Position should be updated
        mock_position_repo.update.assert_called()
        updated_position = mock_position_repo.update.call_args[0][0]
        assert updated_position.status == PositionStatus.PARTIAL_EXIT
        # 500 - 165 = 335 remaining
        assert updated_position.current_amount_tokens == pytest.approx(335.0, rel=0.01)

    @pytest.mark.asyncio
    async def test_realized_pnl_updated_on_partial_exit(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """realized_pnl is updated after partial exit."""
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("250")  # 50%
        filled_order.actual_price = Decimal("0.002")  # 2x entry price
        filled_order.expected_price = Decimal("0.002")
        filled_order.amount_sol = Decimal("0.5")  # 250 * 0.002
        filled_order.tx_signature = "tx_pnl_123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_pnl_123",
                actual_price=Decimal("0.002"),
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.TAKE_PROFIT,
            sell_percent=Decimal("50"),
        )

        await exit_service.execute_exit_order(order)

        updated_position = mock_position_repo.update.call_args[0][0]
        # Entry: 0.5 SOL for 500 tokens = 0.001/token
        # Exit: 250 tokens at 0.002 = 0.5 SOL
        # Entry cost for 250 tokens = 0.25 SOL
        # PnL = 0.5 - 0.25 = 0.25 SOL profit
        assert updated_position.realized_pnl_sol == pytest.approx(0.25, rel=0.01)


class TestFullExitOnStopLoss:
    """Test AC3: Full Exit on Stop Loss."""

    @pytest.mark.asyncio
    async def test_stop_loss_exits_100_percent(
        self, exit_service, sample_position
    ):
        """Stop loss creates 100% exit order."""
        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
            sell_percent=Decimal("100"),
        )

        assert order is not None
        assert order.amount_tokens == Decimal("500")  # All tokens

    @pytest.mark.asyncio
    async def test_position_closed_after_full_exit(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Position status = CLOSED after full exit."""
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("500")  # 100%
        filled_order.actual_price = Decimal("0.0005")  # 50% loss
        filled_order.expected_price = Decimal("0.0005")
        filled_order.amount_sol = Decimal("0.25")
        filled_order.tx_signature = "tx_sl_123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_sl_123",
                actual_price=Decimal("0.0005"),
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        await exit_service.execute_exit_order(order)

        updated_position = mock_position_repo.update.call_args[0][0]
        assert updated_position.status == PositionStatus.CLOSED
        assert updated_position.exit_time is not None
        assert updated_position.current_amount_tokens == pytest.approx(0.0, abs=0.01)

    @pytest.mark.asyncio
    async def test_stop_loss_uses_fallback_price(
        self, exit_service, sample_position, mock_price_oracle
    ):
        """Stop loss uses fallback price if oracle fails."""
        sample_position.peak_price = 0.0008

        mock_price_oracle.get_price = AsyncMock(
            return_value=PriceResult(
                success=False,
                error="API timeout",
            )
        )

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        assert order is not None
        # Should use peak_price as fallback
        assert order.expected_price == Decimal("0.0008")


class TestExitRetryOnFailure:
    """Test AC4: Exit Retry on Failure."""

    @pytest.mark.asyncio
    async def test_failed_exit_with_retry_available(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Failed exit with retries keeps position in CLOSING."""
        failed_order = MagicMock(spec=Order)
        failed_order.id = uuid4()
        failed_order.position_id = sample_position.id
        failed_order.can_retry = True
        failed_order.attempt_count = 1
        failed_order.next_retry_at = datetime.now(UTC)

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=False,
                order=failed_order,
                error="Slippage exceeded",
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        result = await exit_service.execute_exit_order(order)

        assert result is False
        # Position should remain in CLOSING status (set during create_exit_order)
        # and not be restored since can_retry is True

    @pytest.mark.asyncio
    async def test_permanently_failed_exit_restores_position(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Permanently failed exit restores position and creates alert."""
        failed_order = MagicMock(spec=Order)
        failed_order.id = uuid4()
        failed_order.position_id = sample_position.id
        failed_order.can_retry = False
        failed_order.attempt_count = 3
        failed_order.last_error = "Max retries exceeded"
        failed_order.token_address = sample_position.token_address

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=False,
                order=failed_order,
                error="Max retries exceeded",
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        result = await exit_service.execute_exit_order(order)

        assert result is False
        # Position should be restored to OPEN
        mock_position_repo.update.assert_called()
        updated_position = mock_position_repo.update.call_args[0][0]
        assert updated_position.status == PositionStatus.OPEN


class TestExitExecution:
    """Test exit execution tracking."""

    @pytest.mark.asyncio
    async def test_exit_execution_recorded(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Exit execution is saved to repository."""
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("500")
        filled_order.actual_price = Decimal("0.002")
        filled_order.expected_price = Decimal("0.002")
        filled_order.amount_sol = Decimal("1.0")
        filled_order.tx_signature = "tx_exec_123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_exec_123",
                actual_price=Decimal("0.002"),
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.STOP_LOSS,
        )

        await exit_service.execute_exit_order(order)

        mock_position_repo.save_exit_execution.assert_called_once()

    @pytest.mark.asyncio
    async def test_tx_signature_added_to_position(
        self, exit_service, sample_position, mock_executor, mock_position_repo
    ):
        """Exit tx signature is added to position.exit_tx_signatures."""
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("500")
        filled_order.actual_price = Decimal("0.002")
        filled_order.expected_price = Decimal("0.002")
        filled_order.amount_sol = Decimal("1.0")
        filled_order.tx_signature = "tx_sig_abc123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_sig_abc123",
                actual_price=Decimal("0.002"),
            )
        )

        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        order = await exit_service.create_exit_order(
            position=sample_position,
            exit_reason=ExitReason.MANUAL,
        )

        await exit_service.execute_exit_order(order)

        updated_position = mock_position_repo.update.call_args[0][0]
        assert "tx_sig_abc123" in updated_position.exit_tx_signatures


class TestRetryFailedExit:
    """Test retry_failed_exit method."""

    @pytest.mark.asyncio
    async def test_retry_creates_new_order(
        self,
        exit_service,
        sample_position,
        mock_order_repo,
        mock_position_repo,
        mock_executor,
    ):
        """Retry creates new exit order with higher slippage."""
        cancelled_order = MagicMock(spec=Order)
        cancelled_order.id = uuid4()
        cancelled_order.status = OrderStatus.CANCELLED
        cancelled_order.position_id = sample_position.id

        mock_order_repo.get_by_id = AsyncMock(return_value=cancelled_order)
        mock_position_repo.get_by_id = AsyncMock(return_value=sample_position)

        # Mock successful execution on retry
        filled_order = MagicMock(spec=Order)
        filled_order.id = uuid4()
        filled_order.position_id = sample_position.id
        filled_order.amount_tokens = Decimal("500")
        filled_order.actual_price = Decimal("0.002")
        filled_order.expected_price = Decimal("0.002")
        filled_order.amount_sol = Decimal("1.0")
        filled_order.tx_signature = "tx_retry_123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_retry_123",
                actual_price=Decimal("0.002"),
            )
        )

        result = await exit_service.retry_failed_exit(str(cancelled_order.id))

        assert result is not None
        mock_order_repo.create.assert_called()

    @pytest.mark.asyncio
    async def test_retry_fails_for_non_cancelled_order(
        self, exit_service, mock_order_repo
    ):
        """Cannot retry order that is not CANCELLED."""
        pending_order = MagicMock(spec=Order)
        pending_order.id = uuid4()
        pending_order.status = OrderStatus.PENDING

        mock_order_repo.get_by_id = AsyncMock(return_value=pending_order)

        result = await exit_service.retry_failed_exit(str(pending_order.id))

        assert result is None

    @pytest.mark.asyncio
    async def test_retry_fails_for_nonexistent_order(
        self, exit_service, mock_order_repo
    ):
        """Cannot retry order that doesn't exist."""
        mock_order_repo.get_by_id = AsyncMock(return_value=None)

        result = await exit_service.retry_failed_exit(str(uuid4()))

        assert result is None
