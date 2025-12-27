"""Unit tests for EntryOrderService."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.order import Order, OrderStatus, OrderType, OrderSide
from walltrack.models.signal_log import SignalLogEntry, SignalStatus
from walltrack.services.order.entry_service import EntryOrderService
from walltrack.services.order.executor import OrderResult
from walltrack.services.pricing.price_oracle import PriceResult
from walltrack.services.risk.risk_manager import PositionSizeResult, RiskCheck


@pytest.fixture
def mock_order_repo():
    """Create a mock OrderRepository."""
    repo = AsyncMock()
    repo.create = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_signal_repo():
    """Create a mock SignalRepository."""
    repo = AsyncMock()
    repo.update_execution_status = AsyncMock()
    repo.get_by_id = AsyncMock(return_value=None)
    return repo


@pytest.fixture
def mock_position_service():
    """Create a mock PositionService."""
    service = AsyncMock()
    mock_position = MagicMock()
    mock_position.id = "pos-123"
    service.create_position = AsyncMock(return_value=mock_position)
    return service


@pytest.fixture
def mock_executor():
    """Create a mock OrderExecutor."""
    executor = AsyncMock()
    return executor


@pytest.fixture
def mock_risk_manager():
    """Create a mock RiskManager."""
    manager = AsyncMock()
    manager.check_entry_allowed = AsyncMock(
        return_value=RiskCheck(allowed=True)
    )
    manager.calculate_position_size = AsyncMock(
        return_value=PositionSizeResult(
            amount_sol=Decimal("0.5"),
            mode="full",
        )
    )
    return manager


@pytest.fixture
def mock_price_oracle():
    """Create a mock PriceOracle."""
    oracle = AsyncMock()
    oracle.get_price = AsyncMock(
        return_value=PriceResult(
            success=True,
            price=Decimal("0.001"),
            source="jupiter",
        )
    )
    return oracle


@pytest.fixture
def mock_order_factory():
    """Create a mock OrderFactory."""
    factory = MagicMock()

    def create_entry_order(**kwargs):
        return Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            signal_id=kwargs.get("signal_id"),
            token_address=kwargs.get("token_address"),
            amount_sol=kwargs.get("amount_sol"),
            expected_price=kwargs.get("expected_price"),
            max_slippage_bps=kwargs.get("max_slippage_bps", 100),
        )

    factory.create_entry_order = create_entry_order
    return factory


@pytest.fixture
def entry_service(
    mock_order_repo,
    mock_signal_repo,
    mock_position_service,
    mock_executor,
    mock_risk_manager,
    mock_price_oracle,
    mock_order_factory,
):
    """Create EntryOrderService with mocks."""
    return EntryOrderService(
        order_repo=mock_order_repo,
        signal_repo=mock_signal_repo,
        position_service=mock_position_service,
        executor=mock_executor,
        risk_manager=mock_risk_manager,
        price_oracle=mock_price_oracle,
        order_factory=mock_order_factory,
    )


@pytest.fixture
def sample_signal():
    """Create a sample signal for testing."""
    return SignalLogEntry(
        id="sig-123",
        tx_signature="tx_abc123",
        wallet_address="wallet_xyz",
        token_address="TokenMint123456789",
        direction="buy",
        final_score=0.85,
        timestamp=datetime.now(UTC),
        status=SignalStatus.TRADE_ELIGIBLE,
    )


class TestSignalToOrderConversion:
    """Test AC1: Signal to Order Conversion."""

    @pytest.mark.asyncio
    async def test_signal_creates_entry_order(
        self, entry_service, sample_signal, mock_order_repo, mock_executor
    ):
        """Signal creates ENTRY order with correct attributes."""
        # Track the order that was created
        created_order = None

        async def capture_order(order):
            nonlocal created_order
            created_order = order

        mock_order_repo.create = AsyncMock(side_effect=capture_order)

        # Setup executor to return success with the same order (modified)
        def execute_with_order(order):
            order.status = OrderStatus.FILLED
            order.actual_price = Decimal("0.001")
            order.amount_tokens = Decimal("500")
            return OrderResult(
                success=True,
                order=order,
                tx_signature="tx_sig_123",
                actual_price=Decimal("0.001"),
            )

        mock_executor.execute = AsyncMock(side_effect=execute_with_order)

        await entry_service.process_signal(sample_signal)

        # Verify the created order has correct attributes
        assert created_order is not None
        assert created_order.order_type == OrderType.ENTRY
        assert created_order.signal_id == "sig-123"
        assert created_order.token_address == "TokenMint123456789"
        mock_order_repo.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_order_has_pending_status_initially(
        self, entry_service, sample_signal, mock_order_repo, mock_executor
    ):
        """Order starts with PENDING status."""
        created_order = None

        async def capture_order(order):
            nonlocal created_order
            created_order = order

        mock_order_repo.create = AsyncMock(side_effect=capture_order)
        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=MagicMock(status=OrderStatus.FILLED),
                tx_signature="tx_123",
            )
        )

        await entry_service.process_signal(sample_signal)

        assert created_order is not None
        assert created_order.status == OrderStatus.PENDING


class TestRiskManagement:
    """Test AC5: Integration with Risk Manager."""

    @pytest.mark.asyncio
    async def test_risk_blocked_entry_returns_none(
        self, entry_service, sample_signal, mock_risk_manager, mock_signal_repo
    ):
        """Blocked entry returns None and updates signal status."""
        mock_risk_manager.check_entry_allowed = AsyncMock(
            return_value=RiskCheck(
                allowed=False,
                reason="Daily loss limit exceeded",
            )
        )

        result = await entry_service.process_signal(sample_signal)

        assert result is None
        mock_signal_repo.update_execution_status.assert_called_with(
            signal_id="sig-123",
            status="blocked",
            error="Daily loss limit exceeded",
        )

    @pytest.mark.asyncio
    async def test_price_fetch_failure_returns_none(
        self, entry_service, sample_signal, mock_price_oracle, mock_signal_repo
    ):
        """Price fetch failure returns None and updates signal status."""
        mock_price_oracle.get_price = AsyncMock(
            return_value=PriceResult(
                success=False,
                error="API timeout",
            )
        )

        result = await entry_service.process_signal(sample_signal)

        assert result is None
        mock_signal_repo.update_execution_status.assert_called_with(
            signal_id="sig-123",
            status="error",
            error="Price fetch failed",
        )


class TestPositionCreation:
    """Test AC3: Position Creation on Fill."""

    @pytest.mark.asyncio
    async def test_position_created_on_successful_order(
        self,
        entry_service,
        sample_signal,
        mock_executor,
        mock_position_service,
    ):
        """Position is created when order is FILLED."""
        filled_order = MagicMock()
        filled_order.status = OrderStatus.FILLED
        filled_order.actual_price = Decimal("0.001")
        filled_order.amount_tokens = Decimal("500")
        filled_order.amount_sol = Decimal("0.5")
        filled_order.token_address = "TokenMint123456789"
        filled_order.token_symbol = None

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_sig_123",
                actual_price=Decimal("0.001"),
            )
        )

        await entry_service.process_signal(sample_signal)

        mock_position_service.create_position.assert_called_once()
        call_kwargs = mock_position_service.create_position.call_args.kwargs
        assert call_kwargs["signal_id"] == "sig-123"
        assert call_kwargs["token_address"] == "TokenMint123456789"

    @pytest.mark.asyncio
    async def test_position_not_created_on_failed_order(
        self,
        entry_service,
        sample_signal,
        mock_executor,
        mock_position_service,
    ):
        """Position is NOT created when order fails."""
        failed_order = MagicMock()
        failed_order.status = OrderStatus.FAILED
        failed_order.can_retry = False
        failed_order.last_error = "Slippage exceeded"
        failed_order.attempt_count = 3
        failed_order.id = "order-123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=False,
                order=failed_order,
                error="Slippage exceeded",
            )
        )

        await entry_service.process_signal(sample_signal)

        mock_position_service.create_position.assert_not_called()


class TestFailureHandling:
    """Test AC4: Failure Handling."""

    @pytest.mark.asyncio
    async def test_failed_order_with_retry_available(
        self,
        entry_service,
        sample_signal,
        mock_executor,
        mock_signal_repo,
    ):
        """Failed order with retries available doesn't update signal as failed."""
        failed_order = MagicMock()
        failed_order.status = OrderStatus.FAILED
        failed_order.can_retry = True
        failed_order.attempt_count = 1
        failed_order.next_retry_at = datetime.now(UTC)

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=False,
                order=failed_order,
                error="Temporary error",
            )
        )

        result = await entry_service.process_signal(sample_signal)

        assert result is not None
        # Signal should NOT be marked as failed if retries available
        mock_signal_repo.update_execution_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_permanently_failed_order_updates_signal(
        self,
        entry_service,
        sample_signal,
        mock_executor,
        mock_signal_repo,
    ):
        """Permanently failed order updates signal status to failed."""
        failed_order = MagicMock()
        failed_order.status = OrderStatus.FAILED
        failed_order.can_retry = False
        failed_order.last_error = "Max retries exceeded"
        failed_order.attempt_count = 3
        failed_order.id = "order-123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=False,
                order=failed_order,
                error="Max retries exceeded",
            )
        )

        await entry_service.process_signal(sample_signal)

        mock_signal_repo.update_execution_status.assert_called_with(
            signal_id="sig-123",
            status="failed",
            error="Max retries exceeded",
        )


class TestConvictionTier:
    """Test conviction tier determination."""

    @pytest.mark.asyncio
    async def test_high_score_gets_high_conviction(
        self,
        entry_service,
        mock_executor,
        mock_position_service,
    ):
        """Signal with score >= 0.85 gets 'high' conviction tier."""
        high_score_signal = SignalLogEntry(
            id="sig-high",
            tx_signature="tx_high",
            wallet_address="wallet",
            token_address="TokenMint",
            direction="buy",
            final_score=0.90,
            timestamp=datetime.now(UTC),
            status=SignalStatus.TRADE_ELIGIBLE,
        )

        filled_order = MagicMock()
        filled_order.status = OrderStatus.FILLED
        filled_order.actual_price = Decimal("0.001")
        filled_order.amount_tokens = Decimal("500")
        filled_order.amount_sol = Decimal("0.5")
        filled_order.token_address = "TokenMint"
        filled_order.token_symbol = None

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_123",
            )
        )

        await entry_service.process_signal(high_score_signal)

        call_kwargs = mock_position_service.create_position.call_args.kwargs
        assert call_kwargs["conviction_tier"] == "high"

    @pytest.mark.asyncio
    async def test_standard_score_gets_standard_conviction(
        self,
        entry_service,
        mock_executor,
        mock_position_service,
    ):
        """Signal with score < 0.85 gets 'standard' conviction tier."""
        standard_signal = SignalLogEntry(
            id="sig-std",
            tx_signature="tx_std",
            wallet_address="wallet",
            token_address="TokenMint",
            direction="buy",
            final_score=0.75,
            timestamp=datetime.now(UTC),
            status=SignalStatus.TRADE_ELIGIBLE,
        )

        filled_order = MagicMock()
        filled_order.status = OrderStatus.FILLED
        filled_order.actual_price = Decimal("0.001")
        filled_order.amount_tokens = Decimal("500")
        filled_order.amount_sol = Decimal("0.5")
        filled_order.token_address = "TokenMint"
        filled_order.token_symbol = None

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=filled_order,
                tx_signature="tx_123",
            )
        )

        await entry_service.process_signal(standard_signal)

        call_kwargs = mock_position_service.create_position.call_args.kwargs
        assert call_kwargs["conviction_tier"] == "standard"


class TestRetryFailedOrder:
    """Test retry_failed_order method."""

    @pytest.mark.asyncio
    async def test_retry_order_that_cannot_retry(
        self, entry_service, mock_order_repo
    ):
        """Order that cannot retry returns None."""
        # Create a mock order where can_retry is False
        order = MagicMock(spec=Order)
        order.can_retry = False
        order.id = "order-123"
        order.attempt_count = 3
        order.max_attempts = 3

        result = await entry_service.retry_failed_order(order)

        assert result is None
        mock_order_repo.update.assert_not_called()

    @pytest.mark.asyncio
    async def test_retry_order_that_can_retry(
        self,
        entry_service,
        mock_order_repo,
        mock_executor,
        mock_signal_repo,
        mock_position_service,
    ):
        """Order that can retry executes and succeeds."""
        # Create a mock order that can retry with all needed attributes
        order = MagicMock(spec=Order)
        order.can_retry = True
        order.id = "order-456"
        order.signal_id = "sig-retry"
        order.status = OrderStatus.FAILED
        order.token_address = "TokenMint123"
        order.token_symbol = "TEST"
        order.amount_sol = Decimal("0.5")
        order.expected_price = Decimal("0.001")
        order.actual_price = None
        order.amount_tokens = None

        # Mock signal lookup
        mock_signal = MagicMock()
        mock_signal.id = "sig-retry"
        mock_signal.final_score = 0.80
        mock_signal_repo.get_by_id = AsyncMock(return_value=mock_signal)

        # Mock successful execution after retry
        successful_order = MagicMock()
        successful_order.status = OrderStatus.FILLED
        successful_order.actual_price = Decimal("0.001")
        successful_order.amount_tokens = Decimal("500")
        successful_order.amount_sol = Decimal("0.5")
        successful_order.token_address = "TokenMint123"
        successful_order.token_symbol = "TEST"
        successful_order.id = "pos-123"

        mock_executor.execute = AsyncMock(
            return_value=OrderResult(
                success=True,
                order=successful_order,
                tx_signature="tx_retry_123",
            )
        )

        result = await entry_service.retry_failed_order(order)

        assert result is not None
        mock_order_repo.update.assert_called_once()  # Status reset to PENDING
        mock_executor.execute.assert_called_once()
        mock_position_service.create_position.assert_called_once()
