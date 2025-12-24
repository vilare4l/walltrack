"""Tests for historical data collector."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest


class TestHistoricalDataCollector:
    """Tests for HistoricalDataCollector class."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create mock Supabase client."""
        mock = MagicMock()
        mock.insert = AsyncMock(return_value={})
        mock.select = AsyncMock(return_value=[])
        return mock


class TestStoreSignal(TestHistoricalDataCollector):
    """Tests for store_signal method."""

    async def test_store_signal_creates_record(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that store_signal creates a database record."""
        with patch(
            "walltrack.core.backtest.collector.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.collector import HistoricalDataCollector

            collector = HistoricalDataCollector()
            signal = await collector.store_signal(
                wallet_address="WalletTest111",
                token_address="TokenTest111",
                token_price=0.001234,
                wallet_score=0.85,
                computed_score=0.78,
                score_breakdown={"wallet": 0.85},
                trade_eligible=True,
            )

            mock_supabase.insert.assert_called_once()
            call_args = mock_supabase.insert.call_args
            assert call_args[0][0] == "historical_signals"
            assert signal.wallet_address == "WalletTest111"
            assert signal.token_price_usd == Decimal("0.001234")

    async def test_store_signal_adds_token_to_tracking(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that storing a signal adds the token to tracking."""
        with patch(
            "walltrack.core.backtest.collector.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.collector import HistoricalDataCollector

            collector = HistoricalDataCollector()
            await collector.store_signal(
                wallet_address="Wallet111",
                token_address="TokenToTrack",
                token_price=0.001,
                wallet_score=0.80,
                computed_score=0.75,
                score_breakdown={},
                trade_eligible=True,
            )

            assert "TokenToTrack" in collector._tracked_tokens


class TestRecordPrice(TestHistoricalDataCollector):
    """Tests for record_price method."""

    async def test_record_price_creates_record(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that record_price creates a database record."""
        with patch(
            "walltrack.core.backtest.collector.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.collector import HistoricalDataCollector

            collector = HistoricalDataCollector()
            price = await collector.record_price(
                token_address="TokenTest111",
                price_usd=0.001234,
                source="dexscreener",
            )

            mock_supabase.insert.assert_called_once()
            call_args = mock_supabase.insert.call_args
            assert call_args[0][0] == "historical_prices"
            assert price.price_usd == Decimal("0.001234")
            assert price.source == "dexscreener"


class TestGetSignalsForRange(TestHistoricalDataCollector):
    """Tests for get_signals_for_range method."""

    async def test_get_signals_for_range_returns_signals(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test retrieving signals for a date range."""
        now = datetime.now(UTC)
        mock_signals = [
            {
                "id": str(uuid4()),
                "timestamp": now.isoformat(),
                "wallet_address": "Wallet111",
                "token_address": "Token111",
                "wallet_score": "0.85",
                "cluster_id": None,
                "cluster_amplification": "1.0",
                "token_price_usd": "0.001",
                "token_market_cap": None,
                "token_liquidity": None,
                "token_age_minutes": None,
                "computed_score": "0.78",
                "score_breakdown": {},
                "trade_eligible": True,
                "actual_traded": False,
            }
        ]
        mock_supabase.select = AsyncMock(return_value=mock_signals)

        with patch(
            "walltrack.core.backtest.collector.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.collector import HistoricalDataCollector

            collector = HistoricalDataCollector()
            signals = await collector.get_signals_for_range(
                start_date=now - timedelta(days=1),
                end_date=now,
            )

            assert len(signals) == 1
            assert signals[0].wallet_address == "Wallet111"


class TestGetPriceTimeline(TestHistoricalDataCollector):
    """Tests for get_price_timeline method."""

    async def test_get_price_timeline_returns_prices(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test retrieving price timeline for a token."""
        now = datetime.now(UTC)
        mock_prices = [
            {
                "id": str(uuid4()),
                "token_address": "Token111",
                "timestamp": now.isoformat(),
                "price_usd": "0.001",
                "source": "dexscreener",
                "open": None,
                "high": None,
                "low": None,
                "close": None,
                "volume": None,
            }
        ]
        mock_supabase.select = AsyncMock(return_value=mock_prices)

        with patch(
            "walltrack.core.backtest.collector.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.backtest.collector import HistoricalDataCollector

            collector = HistoricalDataCollector()
            prices = await collector.get_price_timeline(
                token_address="Token111",
                start_time=now - timedelta(hours=1),
                end_time=now,
            )

            assert len(prices) == 1
            assert prices[0].token_address == "Token111"


class TestGetHistoricalCollector:
    """Tests for get_historical_collector singleton."""

    async def test_returns_singleton_instance(self) -> None:
        """Test that get_historical_collector returns the same instance."""
        from walltrack.core.backtest.collector import (
            HistoricalDataCollector,
            get_historical_collector,
        )

        # Reset singleton
        import walltrack.core.backtest.collector as module

        module._collector = None

        collector1 = await get_historical_collector()
        collector2 = await get_historical_collector()

        assert collector1 is collector2
        assert isinstance(collector1, HistoricalDataCollector)
