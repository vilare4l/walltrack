"""Performance metrics calculator for wallet transaction analysis.

This module provides utilities to calculate wallet performance metrics
from transaction history, including win rate, PnL, and entry timing.
"""

from collections import defaultdict
from datetime import datetime

import structlog

from walltrack.data.models.transaction import SwapTransaction, Trade, TransactionType
from walltrack.data.models.wallet import PerformanceMetrics

log = structlog.get_logger(__name__)


class PerformanceCalculator:
    """Calculator for wallet performance metrics.

    Analyzes transaction history to compute:
    - Win rate (percentage of profitable trades)
    - Total PnL (sum of all trade profits/losses)
    - Entry delay (average time between token launch and first buy)
    - Total trades count
    - Confidence level based on trade volume

    Example:
        calculator = PerformanceCalculator()
        metrics = calculator.calculate_metrics(
            transactions=[...],
            token_launch_times={"token1": datetime(...), ...}
        )
    """

    def calculate_metrics(
        self,
        transactions: list[SwapTransaction],
        token_launch_times: dict[str, datetime] | None = None,
        min_profit_percent: float = 0.0,
    ) -> PerformanceMetrics:
        """Calculate performance metrics from transaction history.

        Args:
            transactions: List of swap transactions to analyze.
            token_launch_times: Dict mapping token_mint to launch datetime.
                               Used for entry_delay_seconds calculation.
                               If None, entry_delay_seconds will be 0.
            min_profit_percent: Minimum profit percentage to count as win (default: 0.0).
                               AC2: Default value is 10% for production use.
                               A trade is profitable if: exit_price >= entry_price * (1 + min_profit_percent/100)
                               Example: min_profit_percent=10 means 10% minimum profit required.

        Returns:
            PerformanceMetrics object with calculated values.

        Note:
            - Only completed trades (matched BUY/SELL pairs) count toward metrics
            - Open positions (BUY without SELL) are excluded
            - Uses FIFO matching (first BUY matches first SELL per token)

        Example:
            transactions = [
                SwapTransaction(tx_type=BUY, token_mint="token1", ...),
                SwapTransaction(tx_type=SELL, token_mint="token1", ...),
            ]
            token_launches = {"token1": datetime(2024, 1, 1)}
            metrics = calculator.calculate_metrics(transactions, token_launches)
        """
        if not transactions:
            log.debug("no_transactions_to_analyze")
            return PerformanceMetrics(
                win_rate=0.0,
                pnl_total=0.0,
                entry_delay_seconds=0,
                total_trades=0,
                confidence="unknown",
            )

        # Match BUY/SELL pairs to create trades
        trades = self._match_trades(transactions, min_profit_percent=min_profit_percent)

        if not trades:
            log.debug("no_completed_trades_found", transaction_count=len(transactions))
            return PerformanceMetrics(
                win_rate=0.0,
                pnl_total=0.0,
                entry_delay_seconds=0,
                total_trades=0,
                confidence="unknown",
            )

        # Calculate win rate
        profitable_count = sum(1 for t in trades if t.profitable)
        win_rate = (profitable_count / len(trades)) * 100.0

        # Calculate total PnL
        pnl_total = sum(t.pnl for t in trades)

        # Calculate entry delay
        entry_delay = self._calculate_entry_delay(transactions, token_launch_times or {})

        # Determine confidence
        confidence = PerformanceMetrics.calculate_confidence(len(trades))

        metrics = PerformanceMetrics(
            win_rate=win_rate,
            pnl_total=pnl_total,
            entry_delay_seconds=entry_delay,
            total_trades=len(trades),
            confidence=confidence,
        )

        log.info(
            "performance_metrics_calculated",
            total_trades=len(trades),
            win_rate=f"{win_rate:.1f}%",
            pnl_total=f"{pnl_total:.4f} SOL",
            confidence=confidence,
        )

        return metrics

    def _match_trades(
        self, transactions: list[SwapTransaction], min_profit_percent: float = 0.0
    ) -> list[Trade]:
        """Match BUY/SELL pairs to create completed trades.

        Uses FIFO matching: oldest BUY matches oldest SELL for each token.

        Args:
            transactions: List of swap transactions.
            min_profit_percent: Minimum profit percentage to count as win.
                               Default 0.0 means any positive profit is a win.

        Returns:
            List of Trade objects representing completed BUY/SELL pairs.

        Example:
            # Token1: BUY(1 SOL) -> SELL(1.5 SOL) = +0.5 SOL profit
            # Token2: BUY(2 SOL) -> SELL(1.8 SOL) = -0.2 SOL loss
            transactions = [buy1, sell1, buy2, sell2]
            trades = calculator._match_trades(transactions)
            # Returns: [Trade(pnl=0.5, profitable=True), Trade(pnl=-0.2, profitable=False)]
        """
        # Group transactions by token_mint
        by_token: dict[str, list[SwapTransaction]] = defaultdict(list)
        for tx in transactions:
            by_token[tx.token_mint].append(tx)

        trades: list[Trade] = []

        # Match BUY/SELL pairs for each token
        for token_mint, txs in by_token.items():
            # Separate BUYs and SELLs, sort by timestamp (FIFO)
            buys = sorted(
                [t for t in txs if t.tx_type == TransactionType.BUY],
                key=lambda t: t.timestamp,
            )
            sells = sorted(
                [t for t in txs if t.tx_type == TransactionType.SELL],
                key=lambda t: t.timestamp,
            )

            # Match oldest BUY with oldest SELL (FIFO)
            matched_count = min(len(buys), len(sells))

            for buy, sell in zip(buys, sells):
                pnl = sell.sol_amount - buy.sol_amount

                # Calculate profit percentage
                profit_percent = ((sell.sol_amount - buy.sol_amount) / buy.sol_amount) * 100.0

                # AC2: A trade is profitable if profit >= min_profit_percent
                # Example: min_profit_percent=10 means exit_price >= entry_price * 1.10
                profitable = profit_percent >= min_profit_percent

                trade = Trade(
                    token_mint=token_mint,
                    entry_time=buy.timestamp,
                    exit_time=sell.timestamp,
                    pnl=pnl,
                    profitable=profitable,
                )
                trades.append(trade)

                log.debug(
                    "trade_matched",
                    token_mint=token_mint[:8] + "...",
                    pnl=f"{pnl:+.4f} SOL",
                    profitable=profitable,
                )

            # Log unmatched open positions
            if len(buys) > matched_count:
                open_buys = len(buys) - matched_count
                log.info(
                    "open_positions_found",
                    token_mint=token_mint[:8] + "...",
                    open_buys=open_buys,
                    total_buys=len(buys),
                    total_sells=len(sells),
                )

            # Log orphaned sells (sells without corresponding buys - unusual)
            if len(sells) > matched_count:
                orphaned_sells = len(sells) - matched_count
                log.warning(
                    "orphaned_sells_found",
                    token_mint=token_mint[:8] + "...",
                    orphaned_sells=orphaned_sells,
                    total_buys=len(buys),
                    total_sells=len(sells),
                    message="More SELLs than BUYs - possible data inconsistency",
                )

        return trades

    def _calculate_entry_delay(
        self,
        transactions: list[SwapTransaction],
        token_launch_times: dict[str, datetime],
    ) -> int:
        """Calculate average entry delay across all tokens.

        Entry delay = time between token launch and wallet's first BUY.

        Args:
            transactions: List of swap transactions.
            token_launch_times: Dict mapping token_mint to launch datetime.

        Returns:
            Average entry delay in seconds (0 if no launch times available).

        Example:
            # Token launched at 12:00, wallet bought at 13:30 = 90 min delay
            transactions = [SwapTransaction(tx_type=BUY, timestamp=1703001800, ...)]
            launches = {"token_mint": datetime.fromtimestamp(1703001800 - 5400)}
            delay = calculator._calculate_entry_delay(transactions, launches)
            # Returns: 5400 (90 minutes in seconds)
        """
        if not token_launch_times:
            return 0

        delays: list[int] = []

        # Group BUYs by token
        buys_by_token: dict[str, list[SwapTransaction]] = defaultdict(list)
        for tx in transactions:
            if tx.tx_type == TransactionType.BUY:
                buys_by_token[tx.token_mint].append(tx)

        # Calculate delay for each token
        for token_mint, buys in buys_by_token.items():
            # Get launch time for this token
            launch_time = token_launch_times.get(token_mint)
            if not launch_time:
                log.debug(
                    "token_launch_time_missing",
                    token_mint=token_mint[:8] + "...",
                )
                continue

            # Find earliest BUY for this token
            first_buy = min(buys, key=lambda t: t.timestamp)
            first_buy_time = datetime.fromtimestamp(first_buy.timestamp)

            # Calculate delay in seconds
            delay = int((first_buy_time - launch_time).total_seconds())

            # Only include positive delays (buy after launch)
            if delay > 0:
                delays.append(delay)
                log.debug(
                    "entry_delay_calculated",
                    token_mint=token_mint[:8] + "...",
                    delay_seconds=delay,
                    delay_hours=f"{delay / 3600:.1f}h",
                )

        # Return average delay
        if delays:
            avg_delay = int(sum(delays) / len(delays))
            log.debug("average_entry_delay", seconds=avg_delay, hours=f"{avg_delay / 3600:.1f}h")
            return avg_delay
        else:
            return 0
