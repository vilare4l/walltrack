"""Historical data models for backtesting."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class HistoricalSignal(BaseModel):
    """Stored signal for backtesting."""

    id: UUID
    timestamp: datetime
    wallet_address: str
    token_address: str

    # Signal context snapshot
    wallet_score: Decimal
    cluster_id: str | None = None
    cluster_amplification: Decimal = Decimal("1.0")

    # Token data at signal time
    token_price_usd: Decimal
    token_market_cap: Decimal | None = None
    token_liquidity: Decimal | None = None
    token_age_minutes: int | None = None

    # Scoring context
    computed_score: Decimal
    score_breakdown: dict = Field(default_factory=dict)

    # Decision
    trade_eligible: bool
    actual_traded: bool = False

    model_config = {"json_encoders": {Decimal: str}}


class HistoricalPrice(BaseModel):
    """Price point for backtesting."""

    id: UUID
    token_address: str
    timestamp: datetime
    price_usd: Decimal
    source: str = "dexscreener"

    # Optional OHLCV data
    open: Decimal | None = None
    high: Decimal | None = None
    low: Decimal | None = None
    close: Decimal | None = None
    volume: Decimal | None = None


class PriceTimeline(BaseModel):
    """Price history for a token."""

    token_address: str
    prices: list[HistoricalPrice]
    start_time: datetime
    end_time: datetime

    def price_at(self, timestamp: datetime) -> Decimal | None:
        """Get price closest to timestamp.

        Args:
            timestamp: The timestamp to find the closest price for.

        Returns:
            The price closest to the timestamp, or None if no prices exist.
        """
        if not self.prices:
            return None

        closest = min(
            self.prices,
            key=lambda p: abs((p.timestamp - timestamp).total_seconds()),
        )
        return closest.price_usd
