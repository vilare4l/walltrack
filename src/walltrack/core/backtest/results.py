"""Backtest result models."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, computed_field


class BacktestTrade(BaseModel):
    """A simulated trade in backtest.

    Tracks entry, exit, and P&L for each trade.
    """

    id: UUID
    signal_id: UUID
    token_address: str

    # Entry
    entry_time: datetime
    entry_price: Decimal
    position_size_sol: Decimal
    tokens_bought: Decimal

    # Exit
    exit_time: datetime | None = None
    exit_price: Decimal | None = None
    exit_reason: str | None = None

    # Partial exits
    partial_exits: list[dict] = Field(default_factory=list)

    # P&L
    realized_pnl: Decimal | None = None
    realized_pnl_pct: Decimal | None = None

    # Status
    is_open: bool = True

    @computed_field
    @property
    def is_winner(self) -> bool | None:
        """Check if trade was profitable.

        Returns:
            True if profitable, False if loss, None if still open.
        """
        if self.realized_pnl is None:
            return None
        return self.realized_pnl > 0


class BacktestMetrics(BaseModel):
    """Aggregate metrics from backtest.

    Contains all performance statistics calculated from trades.
    """

    # Trade counts
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    open_trades: int = 0

    # P&L metrics
    total_pnl: Decimal = Decimal("0")
    total_pnl_pct: Decimal = Decimal("0")
    average_win: Decimal = Decimal("0")
    average_loss: Decimal = Decimal("0")
    largest_win: Decimal = Decimal("0")
    largest_loss: Decimal = Decimal("0")

    # Risk metrics
    max_drawdown: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    profit_factor: Decimal = Decimal("0")

    # Ratios
    win_rate: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None
    sortino_ratio: Decimal | None = None

    # Timing
    average_hold_time_hours: Decimal = Decimal("0")

    # Signal metrics
    signals_processed: int = 0
    signals_traded: int = 0
    signals_skipped: int = 0

    def calculate_from_trades(self, trades: list[BacktestTrade]) -> None:
        """Calculate metrics from trade list.

        Args:
            trades: List of completed trades to analyze.
        """
        self.total_trades = len(trades)

        closed_trades = [t for t in trades if not t.is_open]
        self.open_trades = len([t for t in trades if t.is_open])

        winners = [t for t in closed_trades if t.is_winner]
        losers = [t for t in closed_trades if t.is_winner is False]

        self.winning_trades = len(winners)
        self.losing_trades = len(losers)

        if self.total_trades > 0:
            self.win_rate = Decimal(str(self.winning_trades / self.total_trades))

        # P&L calculations
        self.total_pnl = sum(
            (t.realized_pnl for t in closed_trades if t.realized_pnl),
            Decimal("0"),
        )

        if winners:
            winner_pnls = [t.realized_pnl for t in winners if t.realized_pnl]
            if winner_pnls:
                self.average_win = sum(winner_pnls, Decimal("0")) / len(winner_pnls)
                self.largest_win = max(winner_pnls)

        if losers:
            loser_pnls = [t.realized_pnl for t in losers if t.realized_pnl]
            if loser_pnls:
                self.average_loss = sum(loser_pnls, Decimal("0")) / len(loser_pnls)
                self.largest_loss = min(loser_pnls)

        # Profit factor
        gross_profit = sum(
            (t.realized_pnl for t in winners if t.realized_pnl),
            Decimal("0"),
        )
        gross_loss = abs(
            sum(
                (t.realized_pnl for t in losers if t.realized_pnl),
                Decimal("0"),
            )
        )
        if gross_loss > 0:
            self.profit_factor = gross_profit / gross_loss
        else:
            self.profit_factor = gross_profit


class BacktestResult(BaseModel):
    """Complete backtest result.

    Contains all trades, metrics, and configuration used.
    """

    id: UUID
    name: str
    parameters: dict

    # Timing
    started_at: datetime
    completed_at: datetime
    duration_seconds: float

    # Results
    trades: list[BacktestTrade]
    metrics: BacktestMetrics

    # Equity curve
    equity_curve: list[dict] = Field(default_factory=list)

    # Comparison to actual (if available)
    actual_pnl: Decimal | None = None
    actual_trades: int | None = None
    pnl_difference: Decimal | None = None
