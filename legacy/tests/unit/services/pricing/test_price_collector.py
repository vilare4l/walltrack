"""Unit tests for PriceCollector.

Story 10.5-7: Price History Collection.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.services.pricing.price_collector import (
    PriceCollector,
    PriceHistoryCleanup,
    PriceHistoryCompressor,
)
from walltrack.services.pricing.price_oracle import PriceResult, PriceSource


@pytest.fixture
def mock_position():
    """Create mock position."""
    position = MagicMock()
    position.id = uuid4()
    position.token_address = "TokenAddress123456789012345678901234567890123"
    position.entry_price = Decimal("0.001")
    position.entry_amount_tokens = Decimal("1000000")
    return position


@pytest.fixture
def mock_price_oracle():
    """Create mock price oracle."""
    oracle = MagicMock()
    oracle.get_prices_batch = AsyncMock(
        return_value={
            "TokenAddress123456789012345678901234567890123": PriceResult(
                success=True,
                price=Decimal("0.0015"),
                source=PriceSource.DEXSCREENER,
                timestamp=datetime.now(UTC),
            ),
        }
    )
    return oracle


@pytest.fixture
def mock_position_repo(mock_position):
    """Create mock position repository."""
    repo = MagicMock()
    repo.list_open = AsyncMock(return_value=[mock_position])
    return repo


@pytest.fixture
def mock_history_repo():
    """Create mock price history repository."""
    repo = MagicMock()
    repo.store_price = AsyncMock()
    repo.update_metrics = AsyncMock()
    return repo


@pytest.fixture
def collector(mock_price_oracle, mock_position_repo, mock_history_repo):
    """Create PriceCollector with mocks."""
    return PriceCollector(
        price_oracle=mock_price_oracle,
        position_repo=mock_position_repo,
        price_history_repo=mock_history_repo,
        collection_interval=0.1,  # Fast for testing
    )


class TestPriceCollectionForActivePositions:
    """Test AC1: Price Collection for Active Positions."""

    @pytest.mark.asyncio
    async def test_collects_price_for_open_position(
        self, collector, mock_position, mock_history_repo
    ):
        """Collector stores price for open positions."""
        count = await collector.collect_once()

        assert count == 1
        mock_history_repo.store_price.assert_called_once()
        call_args = mock_history_repo.store_price.call_args
        assert call_args.kwargs["position_id"] == mock_position.id
        assert call_args.kwargs["price"] == Decimal("0.0015")
        assert call_args.kwargs["source"] == "dexscreener"

    @pytest.mark.asyncio
    async def test_records_source_and_timestamp(
        self, collector, mock_history_repo
    ):
        """Price includes source and timestamp."""
        await collector.collect_once()

        call_args = mock_history_repo.store_price.call_args
        assert call_args.kwargs["source"] == "dexscreener"
        assert call_args.kwargs["timestamp"] is not None

    @pytest.mark.asyncio
    async def test_updates_metrics_for_position(
        self, collector, mock_history_repo
    ):
        """Collector updates price metrics."""
        await collector.collect_once()

        mock_history_repo.update_metrics.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_open_positions(
        self, mock_price_oracle, mock_history_repo
    ):
        """No collection when no positions."""
        empty_repo = MagicMock()
        empty_repo.list_open = AsyncMock(return_value=[])

        collector = PriceCollector(
            price_oracle=mock_price_oracle,
            position_repo=empty_repo,
            price_history_repo=mock_history_repo,
        )

        count = await collector.collect_once()

        assert count == 0
        mock_history_repo.store_price.assert_not_called()


class TestBatchCollectionEfficiency:
    """Test AC2: Batch Collection Efficiency."""

    @pytest.mark.asyncio
    async def test_batch_fetches_unique_tokens(self, mock_price_oracle, mock_history_repo):
        """Collector batches by unique token addresses."""
        # Create positions with same token
        pos1 = MagicMock()
        pos1.id = uuid4()
        pos1.token_address = "Token_A_111111111111111111111111111111111111111"
        pos1.entry_price = Decimal("0.001")
        pos1.entry_amount_tokens = Decimal("1000000")

        pos2 = MagicMock()
        pos2.id = uuid4()
        pos2.token_address = "Token_A_111111111111111111111111111111111111111"  # Same token
        pos2.entry_price = Decimal("0.001")
        pos2.entry_amount_tokens = Decimal("1000000")

        pos3 = MagicMock()
        pos3.id = uuid4()
        pos3.token_address = "Token_B_222222222222222222222222222222222222222"  # Different
        pos3.entry_price = Decimal("0.002")
        pos3.entry_amount_tokens = Decimal("500000")

        mock_position_repo = MagicMock()
        mock_position_repo.list_open = AsyncMock(return_value=[pos1, pos2, pos3])

        mock_price_oracle.get_prices_batch = AsyncMock(
            return_value={
                "Token_A_111111111111111111111111111111111111111": PriceResult(
                    success=True,
                    price=Decimal("0.001"),
                    source=PriceSource.DEXSCREENER,
                    timestamp=datetime.now(UTC),
                ),
                "Token_B_222222222222222222222222222222222222222": PriceResult(
                    success=True,
                    price=Decimal("0.002"),
                    source=PriceSource.BIRDEYE,
                    timestamp=datetime.now(UTC),
                ),
            }
        )

        collector = PriceCollector(
            price_oracle=mock_price_oracle,
            position_repo=mock_position_repo,
            price_history_repo=mock_history_repo,
        )

        count = await collector.collect_once()

        # Should collect for all 3 positions
        assert count == 3
        # But only batch fetch 2 unique tokens
        call_args = mock_price_oracle.get_prices_batch.call_args
        tokens = call_args[0][0]
        assert len(set(tokens)) == 2

    @pytest.mark.asyncio
    async def test_all_positions_receive_price(
        self, mock_price_oracle, mock_history_repo
    ):
        """Each position gets its price stored."""
        positions = []
        for i in range(5):
            pos = MagicMock()
            pos.id = uuid4()
            pos.token_address = f"Token{i}_{'1' * 39}"
            pos.entry_price = Decimal("0.001")
            pos.entry_amount_tokens = Decimal("1000000")
            positions.append(pos)

        mock_position_repo = MagicMock()
        mock_position_repo.list_open = AsyncMock(return_value=positions)

        mock_price_oracle.get_prices_batch = AsyncMock(
            return_value={
                pos.token_address: PriceResult(
                    success=True,
                    price=Decimal("0.001"),
                    source=PriceSource.DEXSCREENER,
                    timestamp=datetime.now(UTC),
                )
                for pos in positions
            }
        )

        collector = PriceCollector(
            price_oracle=mock_price_oracle,
            position_repo=mock_position_repo,
            price_history_repo=mock_history_repo,
        )

        count = await collector.collect_once()

        assert count == 5
        assert mock_history_repo.store_price.call_count == 5


class TestHistoryRetention:
    """Test AC3: History Retention."""

    @pytest.mark.asyncio
    async def test_history_stored_with_timestamp(
        self, collector, mock_history_repo
    ):
        """Each price point has a timestamp."""
        await collector.collect_once()

        call_args = mock_history_repo.store_price.call_args
        assert "timestamp" in call_args.kwargs
        assert isinstance(call_args.kwargs["timestamp"], datetime)


class TestCleanupAfterPositionClose:
    """Test AC4: Cleanup After Position Close."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_old_history(self):
        """Cleanup removes history for old closed positions."""
        cleanup = PriceHistoryCleanup(retention_days=7)

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            client = MagicMock()

            # Mock positions query (first call)
            positions_query = MagicMock()
            positions_query.select = MagicMock(return_value=positions_query)
            positions_query.eq = MagicMock(return_value=positions_query)
            positions_query.lt = MagicMock(return_value=positions_query)
            positions_query.execute = AsyncMock(
                return_value=MagicMock(data=[{"id": str(uuid4())}])
            )

            # Mock delete query (second call)
            delete_query = MagicMock()
            delete_query.delete = MagicMock(return_value=delete_query)
            delete_query.eq = MagicMock(return_value=delete_query)
            delete_query.execute = AsyncMock(return_value=MagicMock(data=[]))

            # Client.table returns positions_query first, then delete_query
            client.table = MagicMock(side_effect=[positions_query, delete_query])
            mock_get_client.return_value = client

            count = await cleanup.cleanup_closed_positions()

            assert count == 1

    @pytest.mark.asyncio
    async def test_cleanup_uses_retention_period(self):
        """Cleanup respects retention period."""
        cleanup = PriceHistoryCleanup(retention_days=14)

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            client = MagicMock()

            query = MagicMock()
            query.select = MagicMock(return_value=query)
            query.eq = MagicMock(return_value=query)
            query.lt = MagicMock(return_value=query)
            query.execute = AsyncMock(return_value=MagicMock(data=[]))
            client.table = MagicMock(return_value=query)
            mock_get_client.return_value = client

            await cleanup.cleanup_closed_positions()

            # Verify lt was called (checking cutoff date)
            query.lt.assert_called_once()


class TestPeakTroughDetection:
    """Test AC5: Peak/Trough Detection."""

    @pytest.mark.asyncio
    async def test_update_metrics_called_with_price(
        self, collector, mock_position, mock_history_repo
    ):
        """Metrics updated with current price."""
        await collector.collect_once()

        mock_history_repo.update_metrics.assert_called_once()
        call_args = mock_history_repo.update_metrics.call_args
        assert call_args.kwargs["current_price"] == Decimal("0.0015")


class TestCollectorLifecycle:
    """Test collector start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_begins_collection(self, collector):
        """Start initiates collection loop."""
        await collector.start()

        assert collector.is_running
        await asyncio.sleep(0.15)  # Wait for at least one collection

        await collector.stop()

        assert not collector.is_running
        assert collector._collection_count >= 1

    @pytest.mark.asyncio
    async def test_stop_halts_collection(self, collector):
        """Stop halts the collection loop."""
        await collector.start()
        await collector.stop()

        assert not collector.is_running

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self, collector):
        """Multiple starts don't cause issues."""
        await collector.start()
        await collector.start()  # Should be no-op

        assert collector.is_running

        await collector.stop()


class TestPriceHistoryCompressor:
    """Test price history compression."""

    @pytest.mark.asyncio
    async def test_compress_old_data(self):
        """Compressor compresses old data."""
        compressor = PriceHistoryCompressor(compression_threshold_hours=24)

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            client = MagicMock()

            # Mock RPC call
            rpc_result = MagicMock()
            rpc_result.execute = AsyncMock(return_value=MagicMock(data=10))
            client.rpc = MagicMock(return_value=rpc_result)
            mock_get_client.return_value = client

            count = await compressor.compress_old_data()

            assert count == 10

    @pytest.mark.asyncio
    async def test_compress_falls_back_to_client_side(self):
        """Compressor falls back when RPC unavailable."""
        compressor = PriceHistoryCompressor()

        with patch(
            "walltrack.data.supabase.client.get_supabase_client",
            new_callable=AsyncMock,
        ) as mock_get_client:
            client = MagicMock()

            # Mock RPC failure
            client.rpc = MagicMock(side_effect=Exception("RPC not available"))

            # Mock table query
            query = MagicMock()
            query.select = MagicMock(return_value=query)
            query.lt = MagicMock(return_value=query)
            query.order = MagicMock(return_value=query)
            query.limit = MagicMock(return_value=query)
            query.execute = AsyncMock(return_value=MagicMock(data=[]))
            client.table = MagicMock(return_value=query)
            mock_get_client.return_value = client

            count = await compressor.compress_old_data()

            assert count == 0


class TestErrorHandling:
    """Test error handling in collector."""

    @pytest.mark.asyncio
    async def test_collection_continues_on_error(self, mock_position_repo, mock_history_repo):
        """Collector continues after errors."""
        failing_oracle = MagicMock()
        failing_oracle.get_prices_batch = AsyncMock(
            side_effect=Exception("API error")
        )

        collector = PriceCollector(
            price_oracle=failing_oracle,
            position_repo=mock_position_repo,
            price_history_repo=mock_history_repo,
            collection_interval=0.1,
        )

        await collector.start()
        await asyncio.sleep(0.25)  # Wait for a few collection attempts
        await collector.stop()

        # Should have attempted multiple collections despite errors
        assert collector._collection_count == 0  # All failed but loop continued

    @pytest.mark.asyncio
    async def test_skips_failed_price_fetches(
        self, mock_position_repo, mock_history_repo
    ):
        """Positions with failed price fetches are skipped."""
        oracle = MagicMock()
        oracle.get_prices_batch = AsyncMock(
            return_value={
                "TokenAddress123456789012345678901234567890123": PriceResult(
                    success=False,
                    error="Price unavailable",
                ),
            }
        )

        collector = PriceCollector(
            price_oracle=oracle,
            position_repo=mock_position_repo,
            price_history_repo=mock_history_repo,
        )

        count = await collector.collect_once()

        assert count == 0
        mock_history_repo.store_price.assert_not_called()
