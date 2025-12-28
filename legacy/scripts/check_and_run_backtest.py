"""Check historical data availability and run real backtests.

This script:
1. Connects to Supabase
2. Checks for available historical data
3. Runs real backtests with preset scenarios if data exists
"""

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from walltrack.core.backtest.comparison_service import ComparisonService
from walltrack.core.backtest.engine import BacktestEngine
from walltrack.core.backtest.parameters import BacktestParameters, ExitStrategyParams, ScoringWeights
from walltrack.core.backtest.scenario import PRESET_SCENARIOS
from walltrack.data.supabase.client import get_supabase_client


async def check_historical_data() -> dict:
    """Check what historical data is available in Supabase."""
    supabase = await get_supabase_client()
    await supabase.connect()

    # Check signals count - direct query since select() method has issues
    signals_response = await supabase.table("historical_signals").select("*").limit(1000).execute()
    signals = signals_response.data if signals_response.data else []

    # Check prices count
    prices_response = await supabase.table("historical_prices").select("*").limit(1000).execute()
    prices = prices_response.data if prices_response.data else []

    # Get date ranges
    signal_dates = []
    if signals:
        signal_dates = sorted([s.get("timestamp") for s in signals if s.get("timestamp")])

    price_dates = []
    if prices:
        price_dates = sorted([p.get("timestamp") for p in prices if p.get("timestamp")])

    return {
        "signals_count": len(signals),
        "prices_count": len(prices),
        "signals_date_range": (signal_dates[0], signal_dates[-1]) if signal_dates else None,
        "prices_date_range": (price_dates[0], price_dates[-1]) if price_dates else None,
        "unique_tokens": len(set(s.get("token_address") for s in signals)) if signals else 0,
        "unique_wallets": len(set(s.get("wallet_address") for s in signals)) if signals else 0,
    }


async def run_real_backtest(
    name: str,
    start_date: datetime,
    end_date: datetime,
    score_threshold: Decimal,
    stop_loss_pct: Decimal,
    base_position_sol: Decimal,
    weights: ScoringWeights | None = None,
):
    """Run a real backtest with specified parameters."""
    params = BacktestParameters(
        start_date=start_date,
        end_date=end_date,
        score_threshold=score_threshold,
        base_position_sol=base_position_sol,
        scoring_weights=weights or ScoringWeights(),
        exit_strategy=ExitStrategyParams(stop_loss_pct=stop_loss_pct),
    )

    engine = BacktestEngine(params)
    result = await engine.run(name=name)
    return result


def print_separator(title: str = "") -> None:
    """Print a visual separator."""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


async def main():
    """Main entry point."""
    print_separator("CHECKING HISTORICAL DATA IN SUPABASE")

    try:
        data_info = await check_historical_data()
    except Exception as e:
        print(f"\n  ERROR: Could not connect to Supabase: {e}")
        print("\n  Please ensure:")
        print("    1. SUPABASE_URL is set in .env")
        print("    2. SUPABASE_KEY is set in .env")
        print("    3. The database is accessible")
        return

    print(f"\n  Historical Signals: {data_info['signals_count']}")
    print(f"  Historical Prices:  {data_info['prices_count']}")
    print(f"  Unique Tokens:      {data_info['unique_tokens']}")
    print(f"  Unique Wallets:     {data_info['unique_wallets']}")

    if data_info["signals_date_range"]:
        print(f"\n  Signal Date Range: {data_info['signals_date_range'][0]} to {data_info['signals_date_range'][1]}")

    if data_info["prices_date_range"]:
        print(f"  Price Date Range:  {data_info['prices_date_range'][0]} to {data_info['prices_date_range'][1]}")

    # Check if we have enough data for backtesting
    if data_info["signals_count"] == 0:
        print_separator("NO HISTORICAL DATA FOUND")
        print("""
  To run real backtests, you need historical data in Supabase.

  Historical data is collected automatically when:
  1. The system processes wallet signals (stores to historical_signals)
  2. Price tracking runs (stores to historical_prices)

  Options to get historical data:

  1. RUN THE LIVE SYSTEM: Let the system run in paper trading mode
     for a few days to collect real signals and prices.

  2. IMPORT HISTORICAL DATA: If you have historical data exports,
     import them into the historical_signals and historical_prices tables.

  3. USE EXTERNAL DATA SOURCES: Connect to historical data APIs
     and populate the tables with past data.

  Required tables in Supabase:
  - historical_signals: Wallet signal snapshots with scores
  - historical_prices: Token price history for P&L calculation
""")
        return

    # We have data - run real backtests!
    print_separator("RUNNING REAL BACKTESTS")

    # Determine date range from actual data
    if data_info["signals_date_range"]:
        start_str = data_info["signals_date_range"][0]
        end_str = data_info["signals_date_range"][1]

        # Parse dates
        if isinstance(start_str, str):
            start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end_date = datetime.fromisoformat(end_str.replace("Z", "+00:00"))
        else:
            start_date = start_str
            end_date = end_str
    else:
        # Default: last 30 days
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=30)

    print(f"\n  Backtest Period: {start_date.date()} to {end_date.date()}")
    print(f"  Signals Available: {data_info['signals_count']}")

    # Define scenarios to test (adjusted thresholds based on actual signal scores)
    scenarios = [
        {
            "name": "High Conviction",
            "threshold": Decimal("0.70"),
            "stop_loss": Decimal("0.25"),
            "position": Decimal("0.05"),
        },
        {
            "name": "Balanced",
            "threshold": Decimal("0.65"),
            "stop_loss": Decimal("0.35"),
            "position": Decimal("0.08"),
        },
        {
            "name": "Active Trader",
            "threshold": Decimal("0.60"),
            "stop_loss": Decimal("0.40"),
            "position": Decimal("0.10"),
        },
        {
            "name": "YOLO",
            "threshold": Decimal("0.55"),
            "stop_loss": Decimal("0.50"),
            "position": Decimal("0.15"),
        },
    ]

    results = []
    for scenario in scenarios:
        print(f"\n  Running: {scenario['name']}...")
        try:
            result = await run_real_backtest(
                name=scenario["name"],
                start_date=start_date,
                end_date=end_date,
                score_threshold=scenario["threshold"],
                stop_loss_pct=scenario["stop_loss"],
                base_position_sol=scenario["position"],
            )
            results.append(result)
            print(f"    Trades: {result.metrics.total_trades}, P&L: {float(result.metrics.total_pnl):.4f} SOL")
        except Exception as e:
            import traceback
            print(f"    ERROR: {e}")
            traceback.print_exc()

    if not results:
        print("\n  No backtests completed successfully.")
        return

    # Compare results
    print_separator("RESULTS COMPARISON")

    if len(results) < 2:
        print("\n  Only 1 result - showing individual metrics:")
        r = results[0]
        print(f"\n  {r.name}")
        print(f"    Trades: {r.metrics.total_trades}")
        print(f"    P&L: {float(r.metrics.total_pnl):.4f} SOL")
        print(f"    Win Rate: {float(r.metrics.win_rate) * 100:.1f}%")
        return

    comparison_service = ComparisonService()
    comparison = comparison_service.compare_scenarios(results)

    print("\n  Rank | Scenario       | P&L       | Win Rate | Trades | Profit Factor")
    print("  " + "-" * 65)

    sorted_scenarios = sorted(comparison.scenarios, key=lambda s: s.overall_rank)
    for s in sorted_scenarios:
        print(
            f"  #{s.overall_rank}   | {s.scenario_name:<14} | "
            f"{float(s.metrics.total_pnl):>8.4f} | "
            f"{float(s.metrics.win_rate) * 100:>6.1f}% | "
            f"{s.metrics.total_trades:>6} | "
            f"{float(s.metrics.profit_factor):>6.2f}"
        )

    print_separator("BEST CONFIGURATION")

    best = comparison.best_scenario_name
    best_result = next(r for r in results if r.name == best)

    print(f"\n  Winner: {best}")
    print(f"\n  Parameters:")
    for key, value in best_result.parameters.items():
        if key not in ["start_date", "end_date"]:
            print(f"    {key}: {value}")

    print(f"\n  Performance:")
    print(f"    Total P&L:     {float(best_result.metrics.total_pnl):.4f} SOL")
    print(f"    Win Rate:      {float(best_result.metrics.win_rate) * 100:.1f}%")
    print(f"    Total Trades:  {best_result.metrics.total_trades}")
    print(f"    Profit Factor: {float(best_result.metrics.profit_factor):.2f}")
    print(f"    Max Drawdown:  {float(best_result.metrics.max_drawdown_pct):.1f}%")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
