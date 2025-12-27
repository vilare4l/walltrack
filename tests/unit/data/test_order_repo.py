"""Unit tests for OrderRepository."""

from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.data.supabase.repositories.order_repo import OrderRepository
from walltrack.models.order import Order, OrderSide, OrderStatus, OrderType


@pytest.fixture
def mock_client():
    """Create a mock Supabase client."""
    client = MagicMock()
    client.client = MagicMock()
    return client


@pytest.fixture
def repo(mock_client):
    """Create OrderRepository with mock client."""
    return OrderRepository(mock_client)


@pytest.fixture
def sample_order():
    """Create a sample order for testing."""
    return Order(
        order_type=OrderType.ENTRY,
        side=OrderSide.BUY,
        token_address="So11111111111111111111111111111111111111112",
        token_symbol="TEST",
        amount_sol=Decimal("1.5"),
        expected_price=Decimal("0.001"),
        signal_id="sig-123",
    )


@pytest.fixture
def sample_order_data():
    """Sample order data from database."""
    return {
        "id": str(uuid4()),
        "order_type": "entry",
        "side": "buy",
        "signal_id": "sig-123",
        "position_id": None,
        "token_address": "So11111111111111111111111111111111111111112",
        "token_symbol": "TEST",
        "amount_sol": 1.5,
        "amount_tokens": None,
        "expected_price": 0.001,
        "actual_price": None,
        "max_slippage_bps": 100,
        "status": "pending",
        "tx_signature": None,
        "filled_at": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "last_error": None,
        "next_retry_at": None,
        "is_simulated": False,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }


class TestOrderRepositoryCreate:
    """Test OrderRepository.create()."""

    @pytest.mark.asyncio
    async def test_create_order(self, repo, mock_client, sample_order):
        """Create inserts order into database."""
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[{}]))

        mock_client.client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute = mock_execute

        result = await repo.create(sample_order)

        assert result == sample_order
        mock_client.client.table.assert_called_with("orders")
        mock_table.insert.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_serializes_correctly(self, repo, mock_client, sample_order):
        """Create serializes order fields correctly."""
        mock_table = MagicMock()
        mock_insert = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[{}]))

        mock_client.client.table.return_value = mock_table
        mock_table.insert.return_value = mock_insert
        mock_insert.execute = mock_execute

        await repo.create(sample_order)

        call_args = mock_table.insert.call_args[0][0]
        assert call_args["order_type"] == "entry"
        assert call_args["side"] == "buy"
        assert call_args["token_address"] == sample_order.token_address
        assert call_args["amount_sol"] == 1.5
        assert call_args["expected_price"] == 0.001


class TestOrderRepositoryUpdate:
    """Test OrderRepository.update()."""

    @pytest.mark.asyncio
    async def test_update_order(self, repo, mock_client, sample_order):
        """Update modifies order in database."""
        mock_table = MagicMock()
        mock_update = MagicMock()
        mock_eq = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[{}]))

        mock_client.client.table.return_value = mock_table
        mock_table.update.return_value = mock_update
        mock_update.eq.return_value = mock_eq
        mock_eq.execute = mock_execute

        sample_order.status = OrderStatus.SUBMITTED
        result = await repo.update(sample_order)

        assert result == sample_order
        mock_update.eq.assert_called_with("id", str(sample_order.id))


class TestOrderRepositoryGetById:
    """Test OrderRepository.get_by_id()."""

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, repo, mock_client, sample_order_data):
        """get_by_id returns order when found."""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_single = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=sample_order_data))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.maybe_single.return_value = mock_single
        mock_single.execute = mock_execute

        result = await repo.get_by_id(sample_order_data["id"])

        assert result is not None
        assert str(result.id) == sample_order_data["id"]
        assert result.order_type == OrderType.ENTRY

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, repo, mock_client):
        """get_by_id returns None when not found."""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_single = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=None))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.maybe_single.return_value = mock_single
        mock_single.execute = mock_execute

        result = await repo.get_by_id(str(uuid4()))

        assert result is None


class TestOrderRepositoryGetBySignal:
    """Test OrderRepository.get_by_signal()."""

    @pytest.mark.asyncio
    async def test_get_by_signal_found(self, repo, mock_client, sample_order_data):
        """get_by_signal returns order when found."""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_eq = MagicMock()
        mock_single = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=sample_order_data))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.eq.return_value = mock_eq
        mock_eq.maybe_single.return_value = mock_single
        mock_single.execute = mock_execute

        result = await repo.get_by_signal("sig-123")

        assert result is not None
        assert result.signal_id == "sig-123"


class TestOrderRepositoryGetPendingRetries:
    """Test OrderRepository.get_pending_retries()."""

    @pytest.mark.asyncio
    async def test_get_pending_retries(self, repo, mock_client, sample_order_data):
        """get_pending_retries returns orders ready for retry."""
        # Set up order that can be retried
        sample_order_data["status"] = "failed"
        sample_order_data["attempt_count"] = 1
        sample_order_data["next_retry_at"] = (
            datetime.utcnow() - timedelta(minutes=1)
        ).isoformat()

        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_in = MagicMock()
        mock_lte = MagicMock()
        mock_or = MagicMock()
        mock_order1 = MagicMock()
        mock_order2 = MagicMock()
        mock_limit = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_order_data]))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.in_.return_value = mock_in
        mock_in.lte.return_value = mock_lte
        mock_lte.or_.return_value = mock_or
        mock_or.order.return_value = mock_order1
        mock_order1.order.return_value = mock_order2
        mock_order2.limit.return_value = mock_limit
        mock_limit.execute = mock_execute

        result = await repo.get_pending_retries()

        assert len(result) == 1
        assert result[0].status == OrderStatus.FAILED
        assert result[0].can_retry is True


class TestOrderRepositoryGetActiveOrders:
    """Test OrderRepository.get_active_orders()."""

    @pytest.mark.asyncio
    async def test_get_active_orders(self, repo, mock_client, sample_order_data):
        """get_active_orders returns non-terminal orders."""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_not = MagicMock()
        mock_in = MagicMock()
        mock_order = MagicMock()
        mock_limit = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_order_data]))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.not_ = mock_not
        mock_not.in_.return_value = mock_in
        mock_in.order.return_value = mock_order
        mock_order.limit.return_value = mock_limit
        mock_limit.execute = mock_execute

        result = await repo.get_active_orders()

        assert len(result) == 1


class TestOrderRepositoryGetHistory:
    """Test OrderRepository.get_history()."""

    @pytest.mark.asyncio
    async def test_get_history_no_filters(self, repo, mock_client, sample_order_data):
        """get_history returns all orders without filters."""
        mock_table = MagicMock()
        mock_select = MagicMock()
        mock_order = MagicMock()
        mock_range = MagicMock()
        mock_execute = AsyncMock(return_value=MagicMock(data=[sample_order_data]))

        mock_client.client.table.return_value = mock_table
        mock_table.select.return_value = mock_select
        mock_select.order.return_value = mock_order
        mock_order.range.return_value = mock_range
        mock_range.execute = mock_execute

        result = await repo.get_history()

        assert len(result) == 1


class TestOrderRepositorySerialization:
    """Test order serialization/deserialization."""

    def test_serialize_order(self, repo, sample_order):
        """Serialize converts Order to dict."""
        data = repo._serialize_order(sample_order)

        assert data["id"] == str(sample_order.id)
        assert data["order_type"] == "entry"
        assert data["side"] == "buy"
        assert data["amount_sol"] == 1.5
        assert data["status"] == "pending"

    def test_deserialize_order(self, repo, sample_order_data):
        """Deserialize converts dict to Order."""
        order = repo._deserialize_order(sample_order_data)

        assert order.order_type == OrderType.ENTRY
        assert order.side == OrderSide.BUY
        assert order.status == OrderStatus.PENDING
        assert order.amount_sol == Decimal("1.5")
        assert order.token_address == sample_order_data["token_address"]

    def test_deserialize_filled_order(self, repo, sample_order_data):
        """Deserialize handles filled order with actual_price."""
        sample_order_data["status"] = "filled"
        sample_order_data["actual_price"] = 0.00105
        sample_order_data["filled_at"] = datetime.utcnow().isoformat()
        sample_order_data["tx_signature"] = "tx_123"

        order = repo._deserialize_order(sample_order_data)

        assert order.status == OrderStatus.FILLED
        assert order.actual_price == Decimal("0.00105")
        assert order.tx_signature == "tx_123"
        assert order.filled_at is not None
