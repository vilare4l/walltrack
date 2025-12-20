"""Trade outcome recording service."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import structlog

from .models import (
    AggregateMetrics,
    ExitReason,
    TradeOutcome,
    TradeOutcomeCreate,
    TradeQuery,
    TradeQueryResult,
)

logger = structlog.get_logger()


class TradeRecorder:
    """Records and manages trade outcomes."""

    def __init__(self, supabase_client):
        """Initialize TradeRecorder.

        Args:
            supabase_client: Supabase client instance
        """
        self.supabase = supabase_client
        self._aggregate_cache: AggregateMetrics | None = None
        self._cache_timestamp: datetime | None = None

    async def record_trade(
        self,
        trade_create: TradeOutcomeCreate,
    ) -> TradeOutcome:
        """Record a trade outcome.

        Args:
            trade_create: Trade outcome data to record

        Returns:
            Recorded TradeOutcome with calculated metrics
        """
        trade_id = uuid4()

        trade = TradeOutcome(
            id=trade_id,
            position_id=trade_create.position_id,
            signal_id=trade_create.signal_id,
            wallet_address=trade_create.wallet_address,
            token_address=trade_create.token_address,
            token_symbol=trade_create.token_symbol,
            entry_price=trade_create.entry_price,
            exit_price=trade_create.exit_price,
            amount_tokens=trade_create.amount_tokens,
            amount_sol=trade_create.amount_sol,
            exit_reason=trade_create.exit_reason,
            signal_score=trade_create.signal_score,
            entry_timestamp=trade_create.entry_timestamp,
            exit_timestamp=trade_create.exit_timestamp,
            is_partial=trade_create.is_partial,
            parent_trade_id=trade_create.parent_trade_id,
        )

        # Persist to database
        await self._save_trade(trade)

        # Update aggregate metrics
        await self._update_aggregates(trade)

        # Invalidate cache
        self._aggregate_cache = None

        logger.info(
            "trade_recorded",
            trade_id=str(trade_id),
            position_id=str(trade.position_id),
            pnl_sol=float(trade.realized_pnl_sol),
            pnl_percent=float(trade.realized_pnl_percent),
            is_win=trade.is_win,
            exit_reason=trade.exit_reason.value,
        )

        return trade

    async def record_partial_exit(
        self,
        parent_trade_id: UUID,
        exit_price: Decimal,
        amount_tokens: Decimal,
        exit_reason: ExitReason = ExitReason.PARTIAL_TP,
    ) -> TradeOutcome:
        """Record a partial exit linked to a parent trade.

        Args:
            parent_trade_id: ID of the parent trade
            exit_price: Exit price for this partial
            amount_tokens: Token amount for this partial
            exit_reason: Reason for partial exit

        Returns:
            Recorded partial TradeOutcome
        """
        # Get parent trade details
        parent = await self.get_trade(parent_trade_id)
        if not parent:
            raise ValueError(f"Parent trade {parent_trade_id} not found")

        # Calculate proportional SOL amount
        proportion = amount_tokens / parent.amount_tokens
        amount_sol = parent.amount_sol * proportion

        partial_create = TradeOutcomeCreate(
            position_id=parent.position_id,
            signal_id=parent.signal_id,
            wallet_address=parent.wallet_address,
            token_address=parent.token_address,
            token_symbol=parent.token_symbol,
            entry_price=parent.entry_price,
            exit_price=exit_price,
            amount_tokens=amount_tokens,
            amount_sol=amount_sol,
            exit_reason=exit_reason,
            signal_score=parent.signal_score,
            entry_timestamp=parent.entry_timestamp,
            exit_timestamp=datetime.now(UTC),
            is_partial=True,
            parent_trade_id=parent_trade_id,
        )

        return await self.record_trade(partial_create)

    async def get_trade(self, trade_id: UUID) -> TradeOutcome | None:
        """Get a single trade by ID.

        Args:
            trade_id: Trade ID to retrieve

        Returns:
            TradeOutcome if found, None otherwise
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*")
            .eq("id", str(trade_id))
            .single()
            .execute()
        )

        if result.data:
            return self._deserialize_trade(result.data)
        return None

    async def query_trades(self, query: TradeQuery) -> TradeQueryResult:
        """Query trade history with filters.

        Args:
            query: Query parameters

        Returns:
            TradeQueryResult with trades and aggregates
        """
        db_query = self.supabase.table("trade_outcomes").select("*", count="exact")

        # Apply filters
        if query.start_date:
            db_query = db_query.gte("exit_timestamp", query.start_date.isoformat())
        if query.end_date:
            db_query = db_query.lte("exit_timestamp", query.end_date.isoformat())
        if query.wallet_address:
            db_query = db_query.eq("wallet_address", query.wallet_address)
        if query.token_address:
            db_query = db_query.eq("token_address", query.token_address)
        if query.exit_reason:
            db_query = db_query.eq("exit_reason", query.exit_reason.value)

        # Ordering and pagination
        db_query = db_query.order("exit_timestamp", desc=True)
        db_query = db_query.range(query.offset, query.offset + query.limit - 1)

        result = await db_query.execute()

        trades = [self._deserialize_trade(t) for t in result.data]

        # Filter by computed fields if needed
        if query.is_win is not None:
            trades = [t for t in trades if t.is_win == query.is_win]
        if query.min_pnl is not None:
            trades = [t for t in trades if t.realized_pnl_sol >= query.min_pnl]
        if query.max_pnl is not None:
            trades = [t for t in trades if t.realized_pnl_sol <= query.max_pnl]

        # Calculate aggregates for filtered trades
        aggregates = self._calculate_aggregates(trades)

        return TradeQueryResult(
            trades=trades,
            total_count=result.count or len(trades),
            aggregates=aggregates,
        )

    async def get_aggregates(self, force_refresh: bool = False) -> AggregateMetrics:
        """Get current aggregate metrics.

        Args:
            force_refresh: Force recalculation from database

        Returns:
            Current AggregateMetrics
        """
        # Check cache (5 minute expiry)
        if (
            not force_refresh
            and self._aggregate_cache
            and self._cache_timestamp
            and (datetime.now(UTC) - self._cache_timestamp).seconds < 300
        ):
            return self._aggregate_cache

        # Load from database
        result = (
            await self.supabase.table("aggregate_metrics").select("*").single().execute()
        )

        if result.data:
            self._aggregate_cache = AggregateMetrics(**result.data)
        else:
            self._aggregate_cache = AggregateMetrics()

        self._cache_timestamp = datetime.now(UTC)
        return self._aggregate_cache

    async def get_trades_for_position(self, position_id: UUID) -> list[TradeOutcome]:
        """Get all trades (including partials) for a position.

        Args:
            position_id: Position ID to get trades for

        Returns:
            List of TradeOutcome for the position
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*")
            .eq("position_id", str(position_id))
            .order("exit_timestamp")
            .execute()
        )

        return [self._deserialize_trade(t) for t in result.data]

    async def get_partial_trades(self, parent_trade_id: UUID) -> list[TradeOutcome]:
        """Get all partial trades linked to a parent trade.

        Args:
            parent_trade_id: Parent trade ID

        Returns:
            List of partial TradeOutcome
        """
        result = (
            await self.supabase.table("trade_outcomes")
            .select("*")
            .eq("parent_trade_id", str(parent_trade_id))
            .order("exit_timestamp")
            .execute()
        )

        return [self._deserialize_trade(t) for t in result.data]

    def _calculate_aggregates(self, trades: list[TradeOutcome]) -> AggregateMetrics:
        """Calculate aggregates for a list of trades.

        Args:
            trades: List of trades to aggregate

        Returns:
            Calculated AggregateMetrics
        """
        if not trades:
            return AggregateMetrics()

        wins = [t for t in trades if t.is_win]
        losses = [t for t in trades if not t.is_win]

        gross_profit = sum(t.realized_pnl_sol for t in wins)
        gross_loss = sum(t.realized_pnl_sol for t in losses)

        total_pnl_percent = (
            sum(t.realized_pnl_percent for t in trades) / len(trades)
            if trades
            else Decimal("0")
        )

        return AggregateMetrics(
            total_pnl_sol=sum(t.realized_pnl_sol for t in trades),
            total_pnl_percent=total_pnl_percent,
            win_count=len(wins),
            loss_count=len(losses),
            total_trades=len(trades),
            average_win_sol=gross_profit / len(wins) if wins else Decimal("0"),
            average_loss_sol=gross_loss / len(losses) if losses else Decimal("0"),
            largest_win_sol=max(
                (t.realized_pnl_sol for t in wins), default=Decimal("0")
            ),
            largest_loss_sol=min(
                (t.realized_pnl_sol for t in losses), default=Decimal("0")
            ),
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            total_volume_sol=sum(t.amount_sol for t in trades),
            last_updated=datetime.now(UTC),
        )

    def _deserialize_trade(self, data: dict) -> TradeOutcome:
        """Deserialize trade data from database.

        Args:
            data: Raw database record

        Returns:
            TradeOutcome instance
        """
        return TradeOutcome(
            id=UUID(data["id"]),
            position_id=UUID(data["position_id"]),
            signal_id=UUID(data["signal_id"]),
            wallet_address=data["wallet_address"],
            token_address=data["token_address"],
            token_symbol=data["token_symbol"],
            entry_price=Decimal(data["entry_price"]),
            exit_price=Decimal(data["exit_price"]),
            amount_tokens=Decimal(data["amount_tokens"]),
            amount_sol=Decimal(data["amount_sol"]),
            exit_reason=ExitReason(data["exit_reason"]),
            signal_score=Decimal(data["signal_score"]),
            entry_timestamp=datetime.fromisoformat(data["entry_timestamp"]),
            exit_timestamp=datetime.fromisoformat(data["exit_timestamp"]),
            is_partial=data.get("is_partial", False),
            parent_trade_id=UUID(data["parent_trade_id"])
            if data.get("parent_trade_id")
            else None,
            created_at=datetime.fromisoformat(data["created_at"]),
        )

    async def _save_trade(self, trade: TradeOutcome) -> None:
        """Persist trade to database.

        Args:
            trade: Trade to save
        """
        data = {
            "id": str(trade.id),
            "position_id": str(trade.position_id),
            "signal_id": str(trade.signal_id),
            "wallet_address": trade.wallet_address,
            "token_address": trade.token_address,
            "token_symbol": trade.token_symbol,
            "entry_price": str(trade.entry_price),
            "exit_price": str(trade.exit_price),
            "amount_tokens": str(trade.amount_tokens),
            "amount_sol": str(trade.amount_sol),
            "exit_reason": trade.exit_reason.value,
            "signal_score": str(trade.signal_score),
            "entry_timestamp": trade.entry_timestamp.isoformat(),
            "exit_timestamp": trade.exit_timestamp.isoformat(),
            "is_partial": trade.is_partial,
            "parent_trade_id": str(trade.parent_trade_id)
            if trade.parent_trade_id
            else None,
            "realized_pnl_sol": str(trade.realized_pnl_sol),
            "realized_pnl_percent": str(trade.realized_pnl_percent),
            "duration_seconds": trade.duration_seconds,
            "is_win": trade.is_win,
        }

        await self.supabase.table("trade_outcomes").insert(data).execute()

    async def _update_aggregates(self, trade: TradeOutcome) -> None:
        """Update aggregate metrics after recording a trade.

        Args:
            trade: Newly recorded trade
        """
        current = await self.get_aggregates(force_refresh=True)

        # Update running totals
        new_total_pnl = current.total_pnl_sol + trade.realized_pnl_sol
        new_win_count = current.win_count + (1 if trade.is_win else 0)
        new_loss_count = current.loss_count + (0 if trade.is_win else 1)
        new_total_trades = current.total_trades + 1
        new_gross_profit = current.gross_profit + (
            trade.realized_pnl_sol if trade.is_win else Decimal("0")
        )
        new_gross_loss = current.gross_loss + (
            trade.realized_pnl_sol if not trade.is_win else Decimal("0")
        )
        new_largest_win = max(
            current.largest_win_sol,
            trade.realized_pnl_sol if trade.is_win else Decimal("0"),
        )
        new_largest_loss = min(
            current.largest_loss_sol,
            trade.realized_pnl_sol if not trade.is_win else Decimal("0"),
        )
        new_total_volume = current.total_volume_sol + trade.amount_sol

        # Recalculate averages
        average_win = (
            new_gross_profit / Decimal(new_win_count)
            if new_win_count > 0
            else Decimal("0")
        )
        average_loss = (
            new_gross_loss / Decimal(new_loss_count)
            if new_loss_count > 0
            else Decimal("0")
        )

        # Persist
        await self.supabase.table("aggregate_metrics").upsert(
            {
                "id": "current",
                "total_pnl_sol": str(new_total_pnl),
                "win_count": new_win_count,
                "loss_count": new_loss_count,
                "total_trades": new_total_trades,
                "average_win_sol": str(average_win),
                "average_loss_sol": str(average_loss),
                "gross_profit": str(new_gross_profit),
                "gross_loss": str(new_gross_loss),
                "largest_win_sol": str(new_largest_win),
                "largest_loss_sol": str(new_largest_loss),
                "total_volume_sol": str(new_total_volume),
                "last_updated": datetime.now(UTC).isoformat(),
            }
        ).execute()


# Singleton instance
_trade_recorder: TradeRecorder | None = None


async def get_trade_recorder(supabase_client) -> TradeRecorder:
    """Get or create TradeRecorder singleton.

    Args:
        supabase_client: Supabase client instance

    Returns:
        TradeRecorder singleton instance
    """
    global _trade_recorder
    if _trade_recorder is None:
        _trade_recorder = TradeRecorder(supabase_client)
    return _trade_recorder
