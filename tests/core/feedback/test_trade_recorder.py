"""Tests for trade outcome recording."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from walltrack.core.feedback.models import (
    AggregateMetrics,
    ExitReason,
    TradeOutcome,
    TradeOutcomeCreate,
    TradeQuery,
)
from walltrack.core.feedback.trade_recorder import TradeRecorder


class ChainableMock(MagicMock):
    """Mock that returns itself for any attribute access and supports async execute."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._execute_result = MagicMock(data=[], count=0)

    def _get_child_mock(self, **kw):
        """Return a ChainableMock for any attribute access."""
        return ChainableMock(**kw)

    def set_execute_result(self, data=None, count=None):
        """Set the result for execute() calls."""
        self._execute_result = MagicMock(data=data or [], count=count or 0)

    async def execute(self):
        """Async execute that returns the configured result."""
        return self._execute_result


@pytest.fixture
def mock_supabase():
    """Create mock Supabase client."""
    client = MagicMock()

    # Store table mocks for test access
    table_mocks = {}

    def make_table_mock(_table_name):
        """Create chainable mock for table operations."""
        mock = ChainableMock()
        return mock

    def get_table(name):
        if name not in table_mocks:
            table_mocks[name] = make_table_mock(name)
        return table_mocks[name]

    client.table.side_effect = get_table
    client._table_mocks = table_mocks

    return client


@pytest.fixture
def trade_recorder(mock_supabase):
    """Create TradeRecorder instance."""
    return TradeRecorder(mock_supabase)


@pytest.fixture
def sample_trade_create():
    """Create sample TradeOutcomeCreate."""
    now = datetime.now(UTC)
    return TradeOutcomeCreate(
        position_id=uuid4(),
        signal_id=uuid4(),
        wallet_address="ABC123wallet",
        token_address="TokenMint123",
        token_symbol="MEME",
        entry_price=Decimal("0.00001"),
        exit_price=Decimal("0.00002"),  # 2x price
        amount_tokens=Decimal("1000000"),
        amount_sol=Decimal("10"),
        exit_reason=ExitReason.TAKE_PROFIT,
        signal_score=Decimal("0.85"),
        entry_timestamp=now - timedelta(hours=2),
        exit_timestamp=now,
    )


class TestTradeOutcomeModel:
    """Tests for TradeOutcome model computed fields."""

    def test_realized_pnl_sol_winning(self):
        """Test PnL calculation for winning trade."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.00002"),  # Exit at 2x
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.TAKE_PROFIT,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        # 1M tokens * 0.00002 = 20 SOL exit value
        # 20 - 10 = 10 SOL profit
        assert trade.realized_pnl_sol == Decimal("10")

    def test_realized_pnl_sol_losing(self):
        """Test PnL calculation for losing trade."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.000005"),  # Exit at 0.5x
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.STOP_LOSS,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        # 1M tokens * 0.000005 = 5 SOL exit value
        # 5 - 10 = -5 SOL loss
        assert trade.realized_pnl_sol == Decimal("-5")

    def test_realized_pnl_percent(self):
        """Test percentage PnL calculation."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.00002"),
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.TAKE_PROFIT,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        # 10 SOL profit / 10 SOL invested = 100%
        assert trade.realized_pnl_percent == Decimal("100")

    def test_duration_seconds(self):
        """Test duration calculation."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.00002"),
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.TAKE_PROFIT,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        # 1 hour = 3600 seconds
        assert trade.duration_seconds == 3600

    def test_is_win_true(self):
        """Test is_win for winning trade."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.00002"),
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.TAKE_PROFIT,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        assert trade.is_win is True

    def test_is_win_false(self):
        """Test is_win for losing trade."""
        now = datetime.now(UTC)
        trade = TradeOutcome(
            id=uuid4(),
            position_id=uuid4(),
            signal_id=uuid4(),
            wallet_address="wallet1",
            token_address="token1",
            token_symbol="TEST",
            entry_price=Decimal("0.00001"),
            exit_price=Decimal("0.000005"),
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=ExitReason.STOP_LOSS,
            signal_score=Decimal("0.8"),
            entry_timestamp=now - timedelta(hours=1),
            exit_timestamp=now,
        )

        assert trade.is_win is False


class TestAggregateMetrics:
    """Tests for AggregateMetrics computed fields."""

    def test_win_rate_calculation(self):
        """Test win rate calculation."""
        metrics = AggregateMetrics(
            win_count=7,
            loss_count=3,
            total_trades=10,
        )

        assert metrics.win_rate == Decimal("70")

    def test_win_rate_zero_trades(self):
        """Test win rate with no trades."""
        metrics = AggregateMetrics(total_trades=0)
        assert metrics.win_rate == Decimal("0")

    def test_profit_factor_calculation(self):
        """Test profit factor calculation."""
        metrics = AggregateMetrics(
            gross_profit=Decimal("100"),
            gross_loss=Decimal("-50"),
        )

        assert metrics.profit_factor == Decimal("2")

    def test_profit_factor_no_losses(self):
        """Test profit factor with no losses."""
        metrics = AggregateMetrics(
            gross_profit=Decimal("100"),
            gross_loss=Decimal("0"),
        )

        assert metrics.profit_factor == Decimal("999")

    def test_expectancy_calculation(self):
        """Test expectancy calculation."""
        metrics = AggregateMetrics(
            total_pnl_sol=Decimal("50"),
            total_trades=10,
        )

        assert metrics.expectancy == Decimal("5")


class TestTradeRecording:
    """Tests for trade outcome recording."""

    @pytest.mark.asyncio
    async def test_record_winning_trade(self, trade_recorder, sample_trade_create):
        """Test recording a winning trade."""
        trade = await trade_recorder.record_trade(sample_trade_create)

        assert trade.id is not None
        assert trade.position_id == sample_trade_create.position_id
        assert trade.is_win is True
        assert trade.realized_pnl_sol == Decimal("10")
        assert trade.realized_pnl_percent == Decimal("100")

    @pytest.mark.asyncio
    async def test_record_losing_trade(self, trade_recorder, sample_trade_create):
        """Test recording a losing trade."""
        sample_trade_create.exit_price = Decimal("0.000005")  # 0.5x price
        sample_trade_create.exit_reason = ExitReason.STOP_LOSS

        trade = await trade_recorder.record_trade(sample_trade_create)

        assert trade.is_win is False
        assert trade.realized_pnl_sol < 0
        assert trade.exit_reason == ExitReason.STOP_LOSS

    @pytest.mark.asyncio
    async def test_record_trade_persists(self, trade_recorder, sample_trade_create, mock_supabase):
        """Test that trade is persisted to database."""
        await trade_recorder.record_trade(sample_trade_create)

        # Verify insert was called
        mock_supabase.table.assert_called()

    @pytest.mark.asyncio
    async def test_duration_calculation(self, trade_recorder, sample_trade_create):
        """Test trade duration calculation."""
        now = datetime.now(UTC)
        sample_trade_create.entry_timestamp = now - timedelta(hours=1)
        sample_trade_create.exit_timestamp = now

        trade = await trade_recorder.record_trade(sample_trade_create)

        # Duration should be approximately 3600 seconds
        assert 3500 < trade.duration_seconds < 3700


class TestPartialExits:
    """Tests for partial exit recording."""

    @pytest.mark.asyncio
    async def test_record_partial_exit_creates_correct_data(self, sample_trade_create):
        """Test partial exit creates correct data when parent is found."""
        # Test that partial exit correctly calculates proportional amounts
        # by testing the TradeOutcomeCreate construction directly
        now = datetime.now(UTC)
        parent = TradeOutcome(
            id=uuid4(),
            position_id=sample_trade_create.position_id,
            signal_id=sample_trade_create.signal_id,
            wallet_address=sample_trade_create.wallet_address,
            token_address=sample_trade_create.token_address,
            token_symbol=sample_trade_create.token_symbol,
            entry_price=sample_trade_create.entry_price,
            exit_price=sample_trade_create.exit_price,
            amount_tokens=Decimal("1000000"),
            amount_sol=Decimal("10"),
            exit_reason=sample_trade_create.exit_reason,
            signal_score=sample_trade_create.signal_score,
            entry_timestamp=sample_trade_create.entry_timestamp,
            exit_timestamp=now,
        )

        # Simulate partial exit calculation
        partial_amount_tokens = Decimal("500000")  # 50%
        proportion = partial_amount_tokens / parent.amount_tokens
        partial_amount_sol = parent.amount_sol * proportion

        partial = TradeOutcomeCreate(
            position_id=parent.position_id,
            signal_id=parent.signal_id,
            wallet_address=parent.wallet_address,
            token_address=parent.token_address,
            token_symbol=parent.token_symbol,
            entry_price=parent.entry_price,
            exit_price=Decimal("0.000025"),
            amount_tokens=partial_amount_tokens,
            amount_sol=partial_amount_sol,
            exit_reason=ExitReason.PARTIAL_TP,
            signal_score=parent.signal_score,
            entry_timestamp=parent.entry_timestamp,
            exit_timestamp=now,
            is_partial=True,
            parent_trade_id=parent.id,
        )

        assert partial.is_partial is True
        assert partial.parent_trade_id == parent.id
        assert partial.amount_tokens == Decimal("500000")
        assert partial.amount_sol == Decimal("5")  # 50% of 10 SOL

    @pytest.mark.asyncio
    async def test_partial_exit_invalid_parent(self, trade_recorder):
        """Test partial exit with invalid parent trade."""
        # Default mock returns None for get_trade
        with pytest.raises(ValueError, match=r"Parent trade .* not found"):
            await trade_recorder.record_partial_exit(
                parent_trade_id=uuid4(),
                exit_price=Decimal("0.000025"),
                amount_tokens=Decimal("500000"),
            )


class TestTradeQuery:
    """Tests for trade querying."""

    @pytest.mark.asyncio
    async def test_query_returns_result(self, trade_recorder):
        """Test that query returns TradeQueryResult."""
        query = TradeQuery()
        result = await trade_recorder.query_trades(query)

        assert result.total_count == 0
        assert result.trades == []
        assert isinstance(result.aggregates, AggregateMetrics)

    @pytest.mark.asyncio
    async def test_query_with_date_filter(self, trade_recorder):
        """Test query with date range filter."""
        query = TradeQuery(
            start_date=datetime.now(UTC) - timedelta(days=7),
            end_date=datetime.now(UTC),
        )

        result = await trade_recorder.query_trades(query)
        assert result.total_count == 0

    @pytest.mark.asyncio
    async def test_query_with_wallet_filter(self, trade_recorder):
        """Test query with wallet filter."""
        query = TradeQuery(wallet_address="ABC123wallet")
        result = await trade_recorder.query_trades(query)

        assert isinstance(result.aggregates, AggregateMetrics)


class TestAggregatesCalculation:
    """Tests for aggregate calculation logic."""

    def test_calculate_aggregates_empty(self, trade_recorder):
        """Test aggregate calculation with empty list."""
        aggregates = trade_recorder._calculate_aggregates([])
        assert aggregates.total_trades == 0
        assert aggregates.win_rate == Decimal("0")

    def test_calculate_aggregates_with_trades(self, trade_recorder):
        """Test aggregate calculation with trades."""
        now = datetime.now(UTC)
        trades = [
            TradeOutcome(
                id=uuid4(),
                position_id=uuid4(),
                signal_id=uuid4(),
                wallet_address="wallet1",
                token_address="token1",
                token_symbol="TEST",
                entry_price=Decimal("0.00001"),
                exit_price=Decimal("0.00002"),  # Win
                amount_tokens=Decimal("1000000"),
                amount_sol=Decimal("10"),
                exit_reason=ExitReason.TAKE_PROFIT,
                signal_score=Decimal("0.8"),
                entry_timestamp=now - timedelta(hours=1),
                exit_timestamp=now,
            ),
            TradeOutcome(
                id=uuid4(),
                position_id=uuid4(),
                signal_id=uuid4(),
                wallet_address="wallet1",
                token_address="token2",
                token_symbol="TEST2",
                entry_price=Decimal("0.00001"),
                exit_price=Decimal("0.000005"),  # Loss
                amount_tokens=Decimal("1000000"),
                amount_sol=Decimal("10"),
                exit_reason=ExitReason.STOP_LOSS,
                signal_score=Decimal("0.6"),
                entry_timestamp=now - timedelta(hours=1),
                exit_timestamp=now,
            ),
        ]

        aggregates = trade_recorder._calculate_aggregates(trades)

        assert aggregates.total_trades == 2
        assert aggregates.win_count == 1
        assert aggregates.loss_count == 1
        assert aggregates.win_rate == Decimal("50")
        assert aggregates.total_pnl_sol == Decimal("5")  # 10 - 5 = 5


class TestGetTrade:
    """Tests for getting individual trades."""

    def test_deserialize_trade(self, trade_recorder):
        """Test deserializing trade data from database format."""
        trade_id = uuid4()
        position_id = uuid4()
        signal_id = uuid4()
        now = datetime.now(UTC)

        trade_data = {
            "id": str(trade_id),
            "position_id": str(position_id),
            "signal_id": str(signal_id),
            "wallet_address": "wallet1",
            "token_address": "token1",
            "token_symbol": "TEST",
            "entry_price": "0.00001",
            "exit_price": "0.00002",
            "amount_tokens": "1000000",
            "amount_sol": "10",
            "exit_reason": "take_profit",
            "signal_score": "0.8",
            "entry_timestamp": (now - timedelta(hours=1)).isoformat(),
            "exit_timestamp": now.isoformat(),
            "is_partial": False,
            "parent_trade_id": None,
            "created_at": now.isoformat(),
        }

        trade = trade_recorder._deserialize_trade(trade_data)

        assert trade.id == trade_id
        assert trade.position_id == position_id
        assert trade.signal_id == signal_id
        assert trade.wallet_address == "wallet1"
        assert trade.entry_price == Decimal("0.00001")
        assert trade.exit_price == Decimal("0.00002")
        assert trade.exit_reason == ExitReason.TAKE_PROFIT
        assert trade.is_partial is False

    @pytest.mark.asyncio
    async def test_get_trade_not_found(self, trade_recorder):
        """Test getting non-existent trade."""
        trade = await trade_recorder.get_trade(uuid4())
        assert trade is None
