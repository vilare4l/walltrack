"""Tests for backtest models."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest


class TestHistoricalSignal:
    """Tests for HistoricalSignal model."""

    def test_historical_signal_creation(self) -> None:
        """Test creating a historical signal."""
        from walltrack.core.backtest.models import HistoricalSignal

        signal = HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address="WalletTest1111111111111111111111111111111111",
            token_address="TokenTest11111111111111111111111111111111111",
            wallet_score=Decimal("0.85"),
            token_price_usd=Decimal("0.001234"),
            computed_score=Decimal("0.78"),
            score_breakdown={"wallet": 0.85, "token": 0.70},
            trade_eligible=True,
        )

        assert signal.wallet_address == "WalletTest1111111111111111111111111111111111"
        assert signal.wallet_score == Decimal("0.85")
        assert signal.trade_eligible is True

    def test_historical_signal_with_cluster(self) -> None:
        """Test historical signal with cluster data."""
        from walltrack.core.backtest.models import HistoricalSignal

        signal = HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address="WalletTest1111111111111111111111111111111111",
            token_address="TokenTest11111111111111111111111111111111111",
            wallet_score=Decimal("0.80"),
            cluster_id="cluster-123",
            cluster_amplification=Decimal("1.25"),
            token_price_usd=Decimal("0.001"),
            computed_score=Decimal("0.90"),
            trade_eligible=True,
        )

        assert signal.cluster_id == "cluster-123"
        assert signal.cluster_amplification == Decimal("1.25")

    def test_historical_signal_optional_token_data(self) -> None:
        """Test that token data fields are optional."""
        from walltrack.core.backtest.models import HistoricalSignal

        signal = HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address="WalletTest1111111111111111111111111111111111",
            token_address="TokenTest11111111111111111111111111111111111",
            wallet_score=Decimal("0.75"),
            token_price_usd=Decimal("0.01"),
            computed_score=Decimal("0.75"),
            trade_eligible=False,
        )

        assert signal.token_market_cap is None
        assert signal.token_liquidity is None
        assert signal.token_age_minutes is None


class TestHistoricalPrice:
    """Tests for HistoricalPrice model."""

    def test_historical_price_creation(self) -> None:
        """Test creating a historical price."""
        from walltrack.core.backtest.models import HistoricalPrice

        price = HistoricalPrice(
            id=uuid4(),
            token_address="TokenTest11111111111111111111111111111111111",
            timestamp=datetime.now(UTC),
            price_usd=Decimal("0.001234"),
            source="dexscreener",
        )

        assert price.price_usd == Decimal("0.001234")
        assert price.source == "dexscreener"

    def test_historical_price_with_ohlcv(self) -> None:
        """Test historical price with OHLCV data."""
        from walltrack.core.backtest.models import HistoricalPrice

        price = HistoricalPrice(
            id=uuid4(),
            token_address="TokenTest11111111111111111111111111111111111",
            timestamp=datetime.now(UTC),
            price_usd=Decimal("0.001234"),
            open=Decimal("0.001200"),
            high=Decimal("0.001300"),
            low=Decimal("0.001100"),
            close=Decimal("0.001234"),
            volume=Decimal("100000.00"),
        )

        assert price.open == Decimal("0.001200")
        assert price.high == Decimal("0.001300")
        assert price.volume == Decimal("100000.00")


class TestPriceTimeline:
    """Tests for PriceTimeline model."""

    def test_price_timeline_creation(self) -> None:
        """Test creating a price timeline."""
        from walltrack.core.backtest.models import HistoricalPrice, PriceTimeline

        now = datetime.now(UTC)
        prices = [
            HistoricalPrice(
                id=uuid4(),
                token_address="Token111",
                timestamp=now,
                price_usd=Decimal("0.001"),
            ),
            HistoricalPrice(
                id=uuid4(),
                token_address="Token111",
                timestamp=now,
                price_usd=Decimal("0.002"),
            ),
        ]

        timeline = PriceTimeline(
            token_address="Token111",
            prices=prices,
            start_time=now,
            end_time=now,
        )

        assert len(timeline.prices) == 2
        assert timeline.token_address == "Token111"

    def test_price_at_returns_closest_price(self) -> None:
        """Test price_at returns the closest price to timestamp."""
        from datetime import timedelta

        from walltrack.core.backtest.models import HistoricalPrice, PriceTimeline

        base_time = datetime.now(UTC)
        prices = [
            HistoricalPrice(
                id=uuid4(),
                token_address="Token111",
                timestamp=base_time,
                price_usd=Decimal("0.001"),
            ),
            HistoricalPrice(
                id=uuid4(),
                token_address="Token111",
                timestamp=base_time + timedelta(hours=1),
                price_usd=Decimal("0.002"),
            ),
            HistoricalPrice(
                id=uuid4(),
                token_address="Token111",
                timestamp=base_time + timedelta(hours=2),
                price_usd=Decimal("0.003"),
            ),
        ]

        timeline = PriceTimeline(
            token_address="Token111",
            prices=prices,
            start_time=base_time,
            end_time=base_time + timedelta(hours=2),
        )

        # Should return 0.002 (closest to 50 minutes from start)
        result = timeline.price_at(base_time + timedelta(minutes=50))
        assert result == Decimal("0.002")

    def test_price_at_empty_timeline(self) -> None:
        """Test price_at with empty timeline."""
        from walltrack.core.backtest.models import PriceTimeline

        now = datetime.now(UTC)
        timeline = PriceTimeline(
            token_address="Token111",
            prices=[],
            start_time=now,
            end_time=now,
        )

        result = timeline.price_at(now)
        assert result is None
