"""Core backtest engine for signal replay."""

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import structlog

from walltrack.core.backtest.collector import get_historical_collector
from walltrack.core.backtest.models import HistoricalPrice, HistoricalSignal
from walltrack.core.backtest.parameters import BacktestParameters
from walltrack.core.backtest.results import (
    BacktestMetrics,
    BacktestResult,
    BacktestTrade,
)

log = structlog.get_logger()


class BacktestEngine:
    """Engine for replaying historical signals with different parameters.

    Processes historical signals chronologically, applying configurable
    scoring weights and trading parameters to simulate performance.
    """

    def __init__(self, parameters: BacktestParameters) -> None:
        """Initialize the backtest engine.

        Args:
            parameters: Configuration for the backtest run.
        """
        self._params = parameters
        self._trades: list[BacktestTrade] = []
        self._equity_curve: list[dict] = []
        self._current_capital = Decimal("1.0")  # Normalized
        self._peak_capital = Decimal("1.0")
        self._open_positions: dict[str, BacktestTrade] = {}
        # Price cache: token_address -> list of (timestamp, price)
        self._price_cache: dict[str, list[HistoricalPrice]] = {}

    async def run(self, name: str = "Backtest") -> BacktestResult:
        """Run the backtest.

        Args:
            name: Name for this backtest run.

        Returns:
            BacktestResult with all trades and metrics.
        """
        started_at = datetime.now(UTC)

        collector = await get_historical_collector()

        # Get historical signals for date range
        signals = await collector.get_signals_for_range(
            start_date=self._params.start_date,
            end_date=self._params.end_date,
        )

        log.info(
            "backtest_started",
            name=name,
            signals=len(signals),
            start=self._params.start_date.isoformat(),
            end=self._params.end_date.isoformat(),
        )

        # Preload all prices upfront to avoid per-signal DB queries
        await self._preload_prices(signals, collector)

        signals_traded = 0
        signals_skipped = 0

        # Process signals chronologically
        for signal in sorted(signals, key=lambda s: s.timestamp):
            # Rescore with backtest parameters
            new_score = self._rescore_signal(signal)

            # Check trade eligibility
            if new_score >= self._params.score_threshold:
                if self._can_open_position():
                    await self._open_trade(signal, new_score)
                    signals_traded += 1
                else:
                    signals_skipped += 1
            else:
                signals_skipped += 1

            # Update open positions (check exits)
            await self._update_positions(signal.timestamp)

            # Record equity curve point
            self._record_equity(signal.timestamp)

        # Close remaining open positions at end
        await self._close_all_positions(self._params.end_date)

        completed_at = datetime.now(UTC)

        # Calculate metrics
        metrics = BacktestMetrics()
        metrics.signals_processed = len(signals)
        metrics.signals_traded = signals_traded
        metrics.signals_skipped = signals_skipped
        metrics.calculate_from_trades(self._trades)

        # Calculate max drawdown
        metrics.max_drawdown_pct = self._calculate_max_drawdown()

        return BacktestResult(
            id=uuid4(),
            name=name,
            parameters=self._params.model_dump(mode="json"),
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=(completed_at - started_at).total_seconds(),
            trades=self._trades,
            metrics=metrics,
            equity_curve=self._equity_curve,
        )

    async def _preload_prices(
        self,
        signals: list[HistoricalSignal],
        collector: "HistoricalDataCollector",
    ) -> None:
        """Preload all price data for tokens in signals.

        Args:
            signals: List of signals to preload prices for.
            collector: Historical data collector instance.
        """
        # Get unique tokens
        tokens = set(s.token_address for s in signals)

        log.info("preloading_prices", tokens=len(tokens))

        for token in tokens:
            prices = await collector.get_price_timeline(
                token_address=token,
                start_time=self._params.start_date,
                end_time=self._params.end_date,
            )
            self._price_cache[token] = prices

        log.info(
            "prices_preloaded",
            tokens=len(tokens),
            total_prices=sum(len(p) for p in self._price_cache.values()),
        )

    def _get_cached_prices(
        self,
        token_address: str,
        start_time: datetime,
        end_time: datetime,
    ) -> list[HistoricalPrice]:
        """Get prices from cache for a token and time range.

        Args:
            token_address: Token to get prices for.
            start_time: Start of time range.
            end_time: End of time range.

        Returns:
            List of prices in the range.
        """
        all_prices = self._price_cache.get(token_address, [])
        return [
            p for p in all_prices
            if start_time <= p.timestamp <= end_time
        ]

    def _rescore_signal(self, signal: HistoricalSignal) -> Decimal:
        """Rescore a signal with backtest parameters.

        Args:
            signal: Historical signal to rescore.

        Returns:
            New computed score.
        """
        weights = self._params.scoring_weights

        # Use stored score breakdown if available
        breakdown = signal.score_breakdown

        wallet_score = Decimal(str(breakdown.get("wallet", signal.wallet_score)))
        cluster_score = (
            Decimal(str(breakdown.get("cluster", 0.5))) * signal.cluster_amplification
        )
        token_score = Decimal(str(breakdown.get("token", 0.5)))
        context_score = Decimal(str(breakdown.get("context", 0.5)))

        new_score = (
            wallet_score * weights.wallet_weight
            + cluster_score * weights.cluster_weight
            + token_score * weights.token_weight
            + context_score * weights.context_weight
        )

        return min(max(new_score, Decimal("0")), Decimal("1"))

    def _can_open_position(self) -> bool:
        """Check if we can open a new position.

        Returns:
            True if under position limit.
        """
        return len(self._open_positions) < self._params.max_concurrent_positions

    async def _open_trade(
        self,
        signal: HistoricalSignal,
        score: Decimal,
    ) -> BacktestTrade:
        """Open a simulated trade.

        Args:
            signal: Signal triggering the trade.
            score: Computed score for position sizing.

        Returns:
            The opened BacktestTrade.
        """
        # Calculate position size
        position_size = self._params.base_position_sol
        if score >= self._params.high_conviction_threshold:
            position_size *= self._params.high_conviction_multiplier

        # Apply slippage to entry
        slippage = Decimal(str(self._params.slippage_bps)) / Decimal("10000")
        entry_price = signal.token_price_usd * (Decimal("1") + slippage)

        # Calculate tokens
        sol_price = Decimal("100")  # Simplified, should use historical
        usd_amount = position_size * sol_price
        tokens_bought = usd_amount / entry_price

        trade = BacktestTrade(
            id=uuid4(),
            signal_id=signal.id,
            token_address=signal.token_address,
            entry_time=signal.timestamp,
            entry_price=entry_price,
            position_size_sol=position_size,
            tokens_bought=tokens_bought,
        )

        self._trades.append(trade)
        self._open_positions[signal.token_address] = trade

        token_display = (
            signal.token_address[:8]
            if len(signal.token_address) > 8
            else signal.token_address
        )
        log.debug(
            "backtest_trade_opened",
            token=token_display,
            entry_price=float(entry_price),
            score=float(score),
        )

        return trade

    async def _update_positions(self, current_time: datetime) -> None:
        """Check and update open positions for exits.

        Args:
            current_time: Current simulation time.
        """
        for token, trade in list(self._open_positions.items()):
            # Get current price from cache
            prices = self._get_cached_prices(
                token_address=token,
                start_time=trade.entry_time,
                end_time=current_time,
            )

            if not prices:
                continue

            current_price = prices[-1].price_usd

            # Check stop-loss
            stop_price = trade.entry_price * (
                Decimal("1") - self._params.exit_strategy.stop_loss_pct
            )
            if current_price <= stop_price:
                await self._close_trade(trade, current_price, "stop_loss", current_time)
                continue

            # Check take-profit levels
            for level in self._params.exit_strategy.take_profit_levels:
                target_price = trade.entry_price * Decimal(str(level["multiplier"]))
                if current_price >= target_price:
                    # Simplified: close full position at first TP hit
                    await self._close_trade(
                        trade, current_price, "take_profit", current_time
                    )
                    break

    async def _close_trade(
        self,
        trade: BacktestTrade,
        exit_price: Decimal,
        exit_reason: str,
        exit_time: datetime,
    ) -> None:
        """Close a trade and calculate P&L.

        Args:
            trade: Trade to close.
            exit_price: Price at exit.
            exit_reason: Reason for exit.
            exit_time: Time of exit.
        """
        # Apply slippage to exit
        slippage = Decimal(str(self._params.slippage_bps)) / Decimal("10000")
        actual_exit = exit_price * (Decimal("1") - slippage)

        # Calculate P&L
        entry_value = trade.entry_price * trade.tokens_bought
        exit_value = actual_exit * trade.tokens_bought
        pnl = exit_value - entry_value
        pnl_pct = (pnl / entry_value) * 100

        trade.exit_time = exit_time
        trade.exit_price = actual_exit
        trade.exit_reason = exit_reason
        trade.realized_pnl = pnl
        trade.realized_pnl_pct = pnl_pct
        trade.is_open = False

        # Update capital
        self._current_capital += pnl / (Decimal("100") * trade.position_size_sol)
        self._peak_capital = max(self._peak_capital, self._current_capital)

        # Remove from open positions
        if trade.token_address in self._open_positions:
            del self._open_positions[trade.token_address]

        log.debug(
            "backtest_trade_closed",
            token=trade.token_address[:8] if len(trade.token_address) > 8 else trade.token_address,
            pnl=float(pnl),
            reason=exit_reason,
        )

    async def _close_all_positions(self, end_time: datetime) -> None:
        """Close all remaining positions at backtest end.

        Args:
            end_time: End time of the backtest.
        """
        for token, trade in list(self._open_positions.items()):
            # Get prices from cache
            prices = self._get_cached_prices(
                token_address=token,
                start_time=trade.entry_time,
                end_time=end_time,
            )

            # Use last price or entry price if no data
            exit_price = prices[-1].price_usd if prices else trade.entry_price

            await self._close_trade(trade, exit_price, "backtest_end", end_time)

    def _record_equity(self, timestamp: datetime) -> None:
        """Record equity curve point.

        Args:
            timestamp: Current timestamp.
        """
        self._equity_curve.append(
            {
                "timestamp": timestamp.isoformat(),
                "equity": float(self._current_capital),
                "open_positions": len(self._open_positions),
            }
        )

    def _calculate_max_drawdown(self) -> Decimal:
        """Calculate maximum drawdown from equity curve.

        Returns:
            Maximum drawdown as percentage.
        """
        if not self._equity_curve:
            return Decimal("0")

        peak = Decimal("0")
        max_dd = Decimal("0")

        for point in self._equity_curve:
            equity = Decimal(str(point["equity"]))
            peak = max(peak, equity)
            drawdown = (peak - equity) / peak if peak > 0 else Decimal("0")
            max_dd = max(max_dd, drawdown)

        return max_dd * 100  # Return as percentage
