"""Historical data collector for backtesting."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from walltrack.core.backtest.models import HistoricalPrice, HistoricalSignal
from walltrack.data.supabase.client import get_supabase_client

log = structlog.get_logger()


class HistoricalDataCollector:
    """Collects and stores historical data for backtesting.

    Stores signal snapshots and price data for later replay
    in backtest scenarios.
    """

    def __init__(self, price_track_hours: int = 24) -> None:
        """Initialize the collector.

        Args:
            price_track_hours: How long to track prices after a signal.
        """
        self._price_track_hours = price_track_hours
        self._tracked_tokens: set[str] = set()

    async def store_signal(
        self,
        wallet_address: str,
        token_address: str,
        token_price: float,
        wallet_score: float,
        computed_score: float,
        score_breakdown: dict,
        trade_eligible: bool,
        cluster_id: str | None = None,
        cluster_amplification: float = 1.0,
        token_market_cap: float | None = None,
        token_liquidity: float | None = None,
        token_age_minutes: int | None = None,
    ) -> HistoricalSignal:
        """Store a signal snapshot for backtesting.

        Args:
            wallet_address: The wallet that generated the signal.
            token_address: Token mint address.
            token_price: Price at signal time.
            wallet_score: Wallet's score at signal time.
            computed_score: Final computed signal score.
            score_breakdown: Score component breakdown.
            trade_eligible: Whether the signal passed threshold.
            cluster_id: Optional cluster ID.
            cluster_amplification: Cluster amplification factor.
            token_market_cap: Optional market cap.
            token_liquidity: Optional liquidity.
            token_age_minutes: Optional token age.

        Returns:
            The stored HistoricalSignal.
        """
        signal = HistoricalSignal(
            id=uuid4(),
            timestamp=datetime.now(UTC),
            wallet_address=wallet_address,
            token_address=token_address,
            wallet_score=Decimal(str(wallet_score)),
            cluster_id=cluster_id,
            cluster_amplification=Decimal(str(cluster_amplification)),
            token_price_usd=Decimal(str(token_price)),
            token_market_cap=Decimal(str(token_market_cap)) if token_market_cap else None,
            token_liquidity=Decimal(str(token_liquidity)) if token_liquidity else None,
            token_age_minutes=token_age_minutes,
            computed_score=Decimal(str(computed_score)),
            score_breakdown=score_breakdown,
            trade_eligible=trade_eligible,
        )

        supabase = await get_supabase_client()
        await supabase.insert("historical_signals", signal.model_dump(mode="json"))

        # Start tracking price for this token
        self._tracked_tokens.add(token_address)

        log.info(
            "historical_signal_stored",
            signal_id=str(signal.id),
            token=token_address[:8] if len(token_address) > 8 else token_address,
            score=float(computed_score),
        )

        return signal

    async def record_price(
        self,
        token_address: str,
        price_usd: float,
        source: str = "dexscreener",
    ) -> HistoricalPrice:
        """Record a price point for a token.

        Args:
            token_address: Token mint address.
            price_usd: Current price in USD.
            source: Price data source.

        Returns:
            The stored HistoricalPrice.
        """
        price = HistoricalPrice(
            id=uuid4(),
            token_address=token_address,
            timestamp=datetime.now(UTC),
            price_usd=Decimal(str(price_usd)),
            source=source,
        )

        supabase = await get_supabase_client()
        await supabase.insert("historical_prices", price.model_dump(mode="json"))

        return price

    async def get_signals_for_range(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list[HistoricalSignal]:
        """Get historical signals for a date range.

        Args:
            start_date: Start of the range.
            end_date: End of the range.

        Returns:
            List of HistoricalSignal objects.
        """
        supabase = await get_supabase_client()

        # Use direct query to avoid retry decorator issues
        response = await (
            supabase.table("historical_signals")
            .select("*")
            .gte("timestamp", start_date.isoformat())
            .lte("timestamp", end_date.isoformat())
            .order("timestamp")
            .execute()
        )

        records = response.data if response.data else []
        return [HistoricalSignal(**r) for r in records]

    async def get_price_timeline(
        self,
        token_address: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[HistoricalPrice]:
        """Get price history for a token.

        Args:
            token_address: Token mint address.
            start_time: Start of timeline.
            end_time: End of timeline.

        Returns:
            List of HistoricalPrice objects.
        """
        supabase = await get_supabase_client()

        # Use direct query to avoid retry decorator issues
        response = await (
            supabase.table("historical_prices")
            .select("*")
            .eq("token_address", token_address)
            .gte("timestamp", start_time.isoformat())
            .lte("timestamp", end_time.isoformat())
            .order("timestamp")
            .execute()
        )

        records = response.data if response.data else []
        return [HistoricalPrice(**r) for r in records]


# Singleton
_collector: HistoricalDataCollector | None = None


async def get_historical_collector() -> HistoricalDataCollector:
    """Get historical data collector singleton.

    Returns:
        The HistoricalDataCollector singleton instance.
    """
    global _collector
    if _collector is None:
        _collector = HistoricalDataCollector()
    return _collector
