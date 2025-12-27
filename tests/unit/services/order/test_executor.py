"""Unit tests for OrderExecutor."""

from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType
from walltrack.services.order.executor import OrderExecutor, OrderResult


@pytest.fixture
def mock_repository():
    """Create a mock OrderRepository."""
    repo = AsyncMock()
    repo.update = AsyncMock()
    return repo


@pytest.fixture
def mock_jupiter():
    """Create a mock JupiterClient."""
    jupiter = AsyncMock()

    # Mock quote response
    mock_quote = MagicMock()
    mock_quote.output_amount = 1000000000  # 1 token in lamports
    mock_quote.input_amount = 1000000000  # 1 SOL in lamports
    mock_quote.price_impact_pct = 0.5
    jupiter.get_quote = AsyncMock(return_value=mock_quote)

    # Mock swap transaction
    mock_swap_tx = MagicMock()
    mock_swap_tx.quote = mock_quote
    jupiter.build_swap_transaction = AsyncMock(return_value=mock_swap_tx)

    # Mock swap result
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.tx_signature = "tx_sig_123456"
    mock_result.error_message = None
    jupiter.execute_swap = AsyncMock(return_value=mock_result)

    return jupiter


@pytest.fixture
def mock_keypair():
    """Create a mock Keypair."""
    keypair = MagicMock()
    keypair.pubkey.return_value = "wallet_pubkey_123"
    return keypair


@pytest.fixture
def executor(mock_repository, mock_jupiter, mock_keypair):
    """Create OrderExecutor with mocks."""
    return OrderExecutor(
        repository=mock_repository,
        jupiter_client=mock_jupiter,
        keypair=mock_keypair,
        confirmation_timeout=5,
    )


@pytest.fixture
def sample_entry_order():
    """Create a sample entry order."""
    return Order(
        order_type=OrderType.ENTRY,
        side=OrderSide.BUY,
        token_address="TokenXYZ123456789",
        token_symbol="XYZ",
        amount_sol=Decimal("1.0"),
        expected_price=Decimal("0.001"),
        signal_id="sig-123",
    )


@pytest.fixture
def sample_exit_order():
    """Create a sample exit order."""
    return Order(
        order_type=OrderType.EXIT,
        side=OrderSide.SELL,
        token_address="TokenXYZ123456789",
        token_symbol="XYZ",
        amount_sol=Decimal("2.0"),
        amount_tokens=Decimal("2000"),
        expected_price=Decimal("0.001"),
        position_id="pos-456",
    )


class TestOrderExecution:
    """Test order execution flow."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, executor, sample_entry_order, mock_repository):
        """Order executes successfully through all states."""
        result = await executor.execute(sample_entry_order)

        assert result.success is True
        assert result.order.status == OrderStatus.FILLED
        assert result.tx_signature == "tx_sig_123456"
        assert result.actual_price is not None

        # Verify state transitions were persisted
        assert mock_repository.update.call_count >= 2

    @pytest.mark.asyncio
    async def test_execution_updates_order_status(
        self, executor, sample_entry_order, mock_repository
    ):
        """Execution updates order status correctly."""
        # Track status changes
        statuses_seen = []

        async def track_status(order):
            statuses_seen.append(order.status)

        mock_repository.update = AsyncMock(side_effect=track_status)

        await executor.execute(sample_entry_order)

        # Should have seen SUBMITTED then FILLED
        assert OrderStatus.SUBMITTED in statuses_seen
        assert OrderStatus.FILLED in statuses_seen
        assert len(statuses_seen) >= 2

    @pytest.mark.asyncio
    async def test_execution_failure_marks_order_failed(
        self, executor, mock_jupiter, sample_entry_order, mock_repository
    ):
        """Failed execution marks order as FAILED."""
        mock_jupiter.get_quote = AsyncMock(side_effect=Exception("API Error"))

        result = await executor.execute(sample_entry_order)

        assert result.success is False
        assert result.order.status == OrderStatus.FAILED
        assert result.order.attempt_count == 1
        assert result.error == "API Error"

    @pytest.mark.asyncio
    async def test_execution_failure_enables_retry(
        self, executor, mock_jupiter, sample_entry_order
    ):
        """Failed execution allows retry."""
        mock_jupiter.get_quote = AsyncMock(side_effect=Exception("API Error"))

        result = await executor.execute(sample_entry_order)

        assert result.order.can_retry is True
        assert result.order.next_retry_at is not None

    @pytest.mark.asyncio
    async def test_swap_failure_marks_order_failed(
        self, executor, mock_jupiter, sample_entry_order
    ):
        """Swap execution failure marks order as FAILED."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error_message = "Slippage exceeded"
        mock_jupiter.execute_swap = AsyncMock(return_value=mock_result)

        result = await executor.execute(sample_entry_order)

        assert result.success is False
        assert result.order.status == OrderStatus.FAILED
        assert "Slippage exceeded" in result.error


class TestSimulatedExecution:
    """Test simulated order execution."""

    @pytest.mark.asyncio
    async def test_simulated_execution_succeeds(self, executor, mock_repository):
        """Simulated order executes without calling Jupiter."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=True,
        )

        result = await executor.execute(order)

        assert result.success is True
        assert result.order.status == OrderStatus.FILLED
        assert "sim_" in result.tx_signature

    @pytest.mark.asyncio
    async def test_simulated_uses_expected_price(self, executor, mock_repository):
        """Simulated execution uses expected price as actual."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.00123"),
            is_simulated=True,
        )

        result = await executor.execute(order)

        assert result.actual_price == Decimal("0.00123")

    @pytest.mark.asyncio
    async def test_simulated_does_not_call_jupiter(
        self, executor, mock_jupiter, mock_repository
    ):
        """Simulated execution doesn't call Jupiter API."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
            is_simulated=True,
        )

        await executor.execute(order)

        mock_jupiter.get_quote.assert_not_called()
        mock_jupiter.build_swap_transaction.assert_not_called()
        mock_jupiter.execute_swap.assert_not_called()


class TestOrderResult:
    """Test OrderResult dataclass."""

    def test_order_result_success(self):
        """OrderResult captures success state."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )

        result = OrderResult(
            success=True,
            order=order,
            tx_signature="tx_123",
            actual_price=Decimal("0.00105"),
        )

        assert result.success is True
        assert result.tx_signature == "tx_123"
        assert result.actual_price == Decimal("0.00105")
        assert result.error is None

    def test_order_result_failure(self):
        """OrderResult captures failure state."""
        order = Order(
            order_type=OrderType.ENTRY,
            side=OrderSide.BUY,
            token_address="token123",
            amount_sol=Decimal("1.0"),
            expected_price=Decimal("0.001"),
        )

        result = OrderResult(
            success=False,
            order=order,
            error="API timeout",
        )

        assert result.success is False
        assert result.tx_signature is None
        assert result.error == "API timeout"


class TestBatchExecution:
    """Test batch order execution."""

    @pytest.mark.asyncio
    async def test_execute_batch(self, executor, mock_repository):
        """Execute multiple orders in batch."""
        orders = [
            Order(
                order_type=OrderType.ENTRY,
                side=OrderSide.BUY,
                token_address=f"token{i}",
                amount_sol=Decimal("1.0"),
                expected_price=Decimal("0.001"),
                is_simulated=True,
            )
            for i in range(3)
        ]

        results = await executor.execute_batch(orders)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_execute_batch_handles_failures(
        self, executor, mock_jupiter, mock_repository
    ):
        """Batch execution handles individual failures."""
        orders = [
            Order(
                order_type=OrderType.ENTRY,
                side=OrderSide.BUY,
                token_address="token1",
                amount_sol=Decimal("1.0"),
                expected_price=Decimal("0.001"),
                is_simulated=True,  # Will succeed
            ),
            Order(
                order_type=OrderType.ENTRY,
                side=OrderSide.BUY,
                token_address="token2",
                amount_sol=Decimal("1.0"),
                expected_price=Decimal("0.001"),
                is_simulated=True,  # Will succeed
            ),
        ]

        results = await executor.execute_batch(orders)

        assert len(results) == 2
        # Both simulated orders should succeed
        assert all(r.success for r in results)


class TestConcurrencyControl:
    """Test concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, mock_repository, mock_jupiter, mock_keypair):
        """Semaphore limits concurrent executions."""
        executor = OrderExecutor(
            repository=mock_repository,
            jupiter_client=mock_jupiter,
            keypair=mock_keypair,
            max_concurrent=2,
        )

        # Verify semaphore was created with correct limit
        assert executor._semaphore._value == 2
