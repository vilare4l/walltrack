"""Performance analytics component for dashboard."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import gradio as gr
import pandas as pd

from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.parameters import BacktestParameters, ExitStrategyParams, ScoringWeights


async def run_quick_backtest() -> dict[str, Any]:
    """Run a quick backtest with default parameters."""
    try:
        # Last 7 days
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=7)

        params = BacktestParameters(
            start_date=start_date,
            end_date=end_date,
            initial_capital=Decimal("10.0"),
            scoring_weights=ScoringWeights(),
            exit_strategy=ExitStrategyParams(),
        )

        engine = BacktestEngine(params)
        result = await engine.run(name="Dashboard Backtest")

        return {
            "success": True,
            "total_pnl": float(result.metrics.total_pnl),
            "win_rate": result.metrics.win_rate * 100,
            "total_trades": result.metrics.total_trades,
            "profit_factor": result.metrics.profit_factor,
            "max_drawdown": result.metrics.max_drawdown * 100,
            "winning_trades": result.metrics.winning_trades,
            "losing_trades": result.metrics.losing_trades,
            "avg_win": float(result.metrics.avg_win),
            "avg_loss": float(result.metrics.avg_loss),
            "trades": result.trades,
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def format_trades_table(trades: list) -> pd.DataFrame:
    """Format trades as DataFrame."""
    if not trades:
        return pd.DataFrame({"Message": ["No trades in backtest period"]})

    rows = []
    for t in trades:
        pnl = t.pnl or Decimal("0")
        rows.append({
            "Token": t.token_address[:8] + "...",
            "Entry": f"${float(t.entry_price):.8f}",
            "Exit": f"${float(t.exit_price):.8f}" if t.exit_price else "-",
            "P&L": f"{float(pnl):+.4f} SOL",
            "Exit Reason": t.exit_reason or "open",
            "Duration": str(t.exit_time - t.entry_time)[:8] if t.exit_time else "-",
        })

    return pd.DataFrame(rows)


def create_performance_tab() -> None:
    """Create the performance tab UI."""
    gr.Markdown("## Performance Analytics")
    gr.Markdown("Backtest results and trading performance metrics")

    with gr.Row():
        run_backtest_btn = gr.Button("🚀 Run Backtest (7 days)", variant="primary")

    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("### Summary")
            total_pnl = gr.Markdown("**Total P&L:** -")
            win_rate = gr.Markdown("**Win Rate:** -")
            total_trades = gr.Markdown("**Total Trades:** -")
            profit_factor = gr.Markdown("**Profit Factor:** -")

        with gr.Column(scale=1):
            gr.Markdown("### Risk Metrics")
            max_drawdown = gr.Markdown("**Max Drawdown:** -")
            avg_win = gr.Markdown("**Avg Win:** -")
            avg_loss = gr.Markdown("**Avg Loss:** -")
            win_loss = gr.Markdown("**Win/Loss:** -")

    gr.Markdown("### Trade History")
    trades_table = gr.Dataframe(
        headers=["Token", "Entry", "Exit", "P&L", "Exit Reason", "Duration"],
        label="Backtest Trades",
        interactive=False,
    )

    status_msg = gr.Markdown("")

    async def run_and_display():
        """Run backtest and display results."""
        result = await run_quick_backtest()

        if not result.get("success"):
            error = result.get("error", "Unknown error")
            return (
                "**Total P&L:** Error",
                "**Win Rate:** -",
                "**Total Trades:** -",
                "**Profit Factor:** -",
                "**Max Drawdown:** -",
                "**Avg Win:** -",
                "**Avg Loss:** -",
                "**Win/Loss:** -",
                pd.DataFrame({"Error": [error]}),
                f"❌ Backtest failed: {error}",
            )

        pnl = result["total_pnl"]
        pnl_color = "green" if pnl >= 0 else "red"

        trades_df = format_trades_table(result.get("trades", []))

        return (
            f"**Total P&L:** <span style='color:{pnl_color}'>{pnl:+.4f} SOL</span>",
            f"**Win Rate:** {result['win_rate']:.1f}%",
            f"**Total Trades:** {result['total_trades']}",
            f"**Profit Factor:** {result['profit_factor']:.2f}",
            f"**Max Drawdown:** {result['max_drawdown']:.1f}%",
            f"**Avg Win:** {result['avg_win']:+.4f} SOL",
            f"**Avg Loss:** {result['avg_loss']:+.4f} SOL",
            f"**Win/Loss:** {result['winning_trades']}/{result['losing_trades']}",
            trades_df,
            f"✅ Backtest completed - {result['total_trades']} trades analyzed",
        )

    run_backtest_btn.click(
        fn=run_and_display,
        outputs=[
            total_pnl, win_rate, total_trades, profit_factor,
            max_drawdown, avg_win, avg_loss, win_loss,
            trades_table, status_msg,
        ],
    )
