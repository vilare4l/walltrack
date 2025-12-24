"""
Backtest Simulation Script

Generates synthetic historical data and runs backtest scenarios to demonstrate
the full backtesting and comparison workflow.
"""

import asyncio
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from walltrack.core.backtest.comparison_service import ComparisonService
from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.parameters import (
    BacktestParameters,
    ExitStrategyParams,
    ScoringWeights,
)
from walltrack.core.backtest.results import BacktestMetrics, BacktestResult, BacktestTrade
from walltrack.core.backtest.scenario import PRESET_SCENARIOS


def generate_synthetic_backtest_result(
    scenario_name: str,
    score_threshold: Decimal,
    stop_loss_pct: Decimal,
    base_position: Decimal,
    num_days: int = 30,
) -> BacktestResult:
    """Generate a synthetic backtest result based on scenario parameters.

    Higher threshold = fewer trades but higher quality
    Lower stop loss = more risk management but potentially missed gains
    """
    random.seed(hash(scenario_name))  # Reproducible results per scenario

    # Simulate trades based on parameters
    trades = []
    now = datetime.now(UTC)
    start_time = now - timedelta(days=num_days)

    # Higher threshold = fewer signals pass
    base_signals_per_day = 10
    threshold_factor = float(1.0 - score_threshold)  # Lower threshold = more signals
    signals_per_day = int(base_signals_per_day * threshold_factor * 2)

    total_pnl = Decimal("0")
    winning_trades = 0
    losing_trades = 0
    max_drawdown = Decimal("0")
    peak = Decimal("0")

    for day in range(num_days):
        day_time = start_time + timedelta(days=day)
        num_signals = random.randint(max(1, signals_per_day - 3), signals_per_day + 3)

        for _ in range(num_signals):
            # Simulate trade outcome
            # Higher score threshold = better quality signals = higher win rate
            win_probability = 0.45 + float(score_threshold) * 0.3
            is_winner = random.random() < win_probability

            if is_winner:
                # Winners: 20% to 200% gain, occasionally moonshot
                if random.random() < 0.1:  # 10% moonshots
                    gain_pct = random.uniform(1.0, 5.0)
                else:
                    gain_pct = random.uniform(0.2, 1.0)
                pnl = base_position * Decimal(str(gain_pct))
                winning_trades += 1
            else:
                # Losers: limited by stop loss
                loss_pct = min(random.uniform(0.1, 0.8), float(stop_loss_pct))
                pnl = -base_position * Decimal(str(loss_pct))
                losing_trades += 1

            total_pnl += pnl
            peak = max(peak, total_pnl)
            drawdown = peak - total_pnl
            max_drawdown = max(max_drawdown, drawdown)

            trade = BacktestTrade(
                id=uuid4(),
                signal_id=uuid4(),
                token_address=f"Token{random.randint(1000, 9999)}",
                entry_time=day_time + timedelta(hours=random.randint(0, 23)),
                entry_price=Decimal(str(random.uniform(0.0001, 0.01))),
                position_size_sol=base_position,
                tokens_bought=Decimal("1000000"),
                realized_pnl=pnl,
                is_open=False,
            )
            trades.append(trade)

    total_trades = winning_trades + losing_trades
    win_rate = Decimal(str(winning_trades / total_trades)) if total_trades > 0 else Decimal("0")

    # Calculate profit factor
    total_wins = sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl > 0)
    total_losses = abs(sum(t.realized_pnl for t in trades if t.realized_pnl and t.realized_pnl < 0))
    profit_factor = total_wins / total_losses if total_losses > 0 else Decimal("999")

    max_dd_pct = (max_drawdown / peak * 100) if peak > 0 else Decimal("0")

    return BacktestResult(
        id=uuid4(),
        name=scenario_name,
        parameters={
            "score_threshold": str(score_threshold),
            "stop_loss_pct": str(stop_loss_pct),
            "base_position_sol": str(base_position),
        },
        started_at=start_time,
        completed_at=now,
        duration_seconds=num_days * 86400,
        trades=trades,
        metrics=BacktestMetrics(
            total_pnl=total_pnl,
            win_rate=win_rate,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
            profit_factor=min(profit_factor, Decimal("10")),
            max_drawdown_pct=max_dd_pct,
            avg_trade_pnl=total_pnl / total_trades if total_trades > 0 else Decimal("0"),
            avg_win=total_wins / winning_trades if winning_trades > 0 else Decimal("0"),
            avg_loss=total_losses / losing_trades if losing_trades > 0 else Decimal("0"),
        ),
    )


def print_separator(title: str = "") -> None:
    """Print a visual separator."""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


def print_result_summary(result: BacktestResult) -> None:
    """Print a summary of a backtest result."""
    m = result.metrics
    print(f"\n  {result.name}")
    print(f"  {'─' * 40}")
    print(f"  Total P&L:      {float(m.total_pnl):>10.2f} SOL")
    print(f"  Win Rate:       {float(m.win_rate) * 100:>10.1f}%")
    print(f"  Total Trades:   {m.total_trades:>10}")
    print(f"  Profit Factor:  {float(m.profit_factor):>10.2f}")
    print(f"  Max Drawdown:   {float(m.max_drawdown_pct):>10.1f}%")
    print(f"  Avg Trade P&L:  {float(m.avg_trade_pnl):>10.4f} SOL")


async def main():
    """Run backtest simulation and analysis."""

    print_separator("BACKTEST SIMULATION")
    print("\nGenerating synthetic backtest data for preset scenarios...")
    print("(30 days of simulated trading)")

    # Define scenarios to test
    scenarios = [
        {
            "name": "Conservative",
            "threshold": Decimal("0.80"),
            "stop_loss": Decimal("0.30"),
            "position": Decimal("0.05"),
        },
        {
            "name": "Balanced",
            "threshold": Decimal("0.70"),
            "stop_loss": Decimal("0.50"),
            "position": Decimal("0.10"),
        },
        {
            "name": "Aggressive",
            "threshold": Decimal("0.60"),
            "stop_loss": Decimal("0.60"),
            "position": Decimal("0.15"),
        },
        {
            "name": "High Conviction Only",
            "threshold": Decimal("0.85"),
            "stop_loss": Decimal("0.40"),
            "position": Decimal("0.20"),
        },
        {
            "name": "Volume Hunter",
            "threshold": Decimal("0.65"),
            "stop_loss": Decimal("0.50"),
            "position": Decimal("0.08"),
        },
    ]

    # Generate results for each scenario
    results = []
    for scenario in scenarios:
        result = generate_synthetic_backtest_result(
            scenario_name=scenario["name"],
            score_threshold=scenario["threshold"],
            stop_loss_pct=scenario["stop_loss"],
            base_position=scenario["position"],
        )
        results.append(result)

    print_separator("INDIVIDUAL RESULTS")

    for result in results:
        print_result_summary(result)

    print_separator("SCENARIO COMPARISON")

    # Compare scenarios
    comparison_service = ComparisonService()
    comparison = comparison_service.compare_scenarios(results)

    print("\n  Ranking by Metric:")
    print("  " + "─" * 60)

    for metric in comparison.metric_comparisons:
        rankings_str = ", ".join(
            f"{name}(#{rank})"
            for name, rank in sorted(metric.rankings.items(), key=lambda x: x[1])
        )
        print(f"\n  {metric.display_name}:")
        print(f"    Best: {metric.best_scenario} ({float(metric.best_value):.2f})")
        print(f"    Rankings: {rankings_str}")

    print_separator("OVERALL RANKINGS")

    sorted_scenarios = sorted(comparison.scenarios, key=lambda s: s.overall_rank)

    print("\n  Rank | Scenario             | Score  | P&L      | Win Rate")
    print("  " + "─" * 60)

    for s in sorted_scenarios:
        rank_icon = "🥇" if s.overall_rank == 1 else "🥈" if s.overall_rank == 2 else "🥉" if s.overall_rank == 3 else "  "
        print(
            f"  {rank_icon} {s.overall_rank}  | {s.scenario_name:<20} | "
            f"{float(s.weighted_score):.3f} | {float(s.metrics.total_pnl):>8.2f} | "
            f"{float(s.metrics.win_rate) * 100:.1f}%"
        )

    print_separator("BEST SCENARIO ANALYSIS")

    best = comparison.best_scenario_name
    best_result = next(r for r in results if r.name == best)

    print(f"\n  Winner: {best}")
    print(f"\n  Configuration:")
    for key, value in best_result.parameters.items():
        print(f"    {key}: {value}")

    print(f"\n  Performance:")
    print(f"    Total P&L:     {float(best_result.metrics.total_pnl):.2f} SOL")
    print(f"    Win Rate:      {float(best_result.metrics.win_rate) * 100:.1f}%")
    print(f"    Trades:        {best_result.metrics.total_trades}")
    print(f"    Profit Factor: {float(best_result.metrics.profit_factor):.2f}")

    # Detailed comparison between top 2
    if len(sorted_scenarios) >= 2:
        print_separator("DETAILED COMPARISON: #1 vs #2")

        first = next(r for r in results if r.name == sorted_scenarios[0].scenario_name)
        second = next(r for r in results if r.name == sorted_scenarios[1].scenario_name)

        detailed = comparison_service.compare_pair_detailed(first, second)

        print(f"\n  {first.name} vs {second.name}")
        print(f"\n  Trade Analysis:")
        print(f"    Only in {first.name}: {detailed.trades_only_a} trades")
        print(f"    Only in {second.name}: {detailed.trades_only_b} trades")
        print(f"    P&L Difference: {float(detailed.pnl_difference):.2f} SOL")
        print(f"    Statistically Significant: {'Yes' if detailed.pnl_difference_significant else 'No'}")

    # Export CSV
    print_separator("CSV EXPORT")

    csv_output = comparison_service.export_comparison_csv(comparison)
    print("\n" + csv_output)

    print_separator("RECOMMENDATION")

    print(f"""
  Based on this 30-day simulation:

  Recommended Strategy: {best}

  Key Insights:
  - Score Threshold: {best_result.parameters.get('score_threshold', 'N/A')}
  - Stop Loss: {best_result.parameters.get('stop_loss_pct', 'N/A')}
  - Position Size: {best_result.parameters.get('base_position_sol', 'N/A')} SOL

  This configuration achieved:
  - {float(best_result.metrics.total_pnl):.2f} SOL profit
  - {float(best_result.metrics.win_rate) * 100:.1f}% win rate
  - {float(best_result.metrics.profit_factor):.2f}x profit factor

  Note: These are simulated results. Real performance may vary.
""")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
