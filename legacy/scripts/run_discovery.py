#!/usr/bin/env python3
"""
Script to run wallet discovery manually.

This script finds tokens that have pumped recently and discovers
the wallets that bought early and profited.

Usage:
    # Quick discovery (10 tokens, default parameters)
    uv run python scripts/run_discovery.py

    # Full discovery with custom parameters
    uv run python scripts/run_discovery.py --tokens 20 --min-change 100 --min-volume 50000

    # Discovery for a specific token
    uv run python scripts/run_discovery.py --token <MINT_ADDRESS>

    # Just find pumped tokens (no wallet discovery)
    uv run python scripts/run_discovery.py --find-pumps-only
"""

import argparse
import asyncio
import sys
from datetime import UTC, datetime

import structlog

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)

log = structlog.get_logger()


async def find_pumps_only(args: argparse.Namespace) -> None:
    """Find and display pumped tokens without running full discovery."""
    from walltrack.discovery.pump_finder import PumpFinder  # noqa: PLC0415

    print("\n" + "=" * 60)
    print("[SEARCH] Finding Pumped Tokens (DexScreener)")
    print("=" * 60 + "\n")

    finder = PumpFinder()
    try:
        tokens = await finder.find_pumped_tokens(
            min_price_change_pct=args.min_change,
            min_volume_usd=args.min_volume,
            max_age_hours=args.max_age,
            limit=args.tokens,
        )

        if not tokens:
            print("[ERROR] No pumped tokens found with current criteria")
            print(f"   Min change: {args.min_change}%")
            print(f"   Min volume: ${args.min_volume:,.0f}")
            print(f"   Max age: {args.max_age}h")
            return

        print(f"[OK] Found {len(tokens)} pumped tokens:\n")

        for i, token in enumerate(tokens, 1):
            now = datetime.now(UTC).replace(tzinfo=None)
            delta = now - token.launch_time.replace(tzinfo=None)
            age_hours = delta.total_seconds() / 3600
            print(f"{i:2}. {token.symbol or 'Unknown'}")
            print(f"    Mint: {token.mint}")
            print(f"    Volume 24h: ${token.volume_24h:,.0f}")
            print(f"    Market Cap: ${token.current_mcap:,.0f}")
            print(f"    Age: {age_hours:.1f}h")
            print()

    finally:
        await finder.close()


async def discover_for_token(token_mint: str, args: argparse.Namespace) -> None:
    """Run discovery for a specific token."""
    from walltrack.scheduler.tasks.discovery_task import (  # noqa: PLC0415
        run_discovery_for_token,
    )

    print("\n" + "=" * 60)
    print(f"[TARGET] Discovery for Token: {token_mint[:20]}...")
    print("=" * 60 + "\n")

    result = await run_discovery_for_token(
        token_mint=token_mint,
        early_window_minutes=args.early_window,
        min_profit_pct=args.min_profit,
    )

    print("\n" + "-" * 40)
    print("[RESULTS] Discovery Results:")
    print("-" * 40)
    print(f"  New wallets:     {result.new_wallets}")
    print(f"  Updated wallets: {result.updated_wallets}")
    print(f"  Duration:        {result.duration_seconds:.2f}s")

    if result.errors:
        print(f"  Errors:          {len(result.errors)}")
        for err in result.errors[:5]:
            print(f"    - {err}")


async def run_full_discovery(args: argparse.Namespace) -> None:
    """Run full discovery pipeline."""
    from walltrack.scheduler.tasks.discovery_task import run_discovery_task  # noqa: PLC0415

    print("\n" + "=" * 60)
    print("[RUN] Running Full Wallet Discovery Pipeline")
    print("=" * 60)
    print("\nParameters:")
    print(f"  Max tokens:       {args.tokens}")
    print(f"  Min price change: {args.min_change}%")
    print(f"  Min volume:       ${args.min_volume:,.0f}")
    print(f"  Max token age:    {args.max_age}h")
    print(f"  Early window:     {args.early_window}min")
    print(f"  Min profit:       {args.min_profit}%")
    print(f"  Profile wallets:  {not args.skip_profile}")
    print()

    result = await run_discovery_task(
        min_price_change_pct=args.min_change,
        min_volume_usd=args.min_volume,
        max_token_age_hours=args.max_age,
        early_window_minutes=args.early_window,
        min_profit_pct=args.min_profit,
        max_tokens=args.tokens,
        profile_immediately=not args.skip_profile,
    )

    print("\n" + "=" * 60)
    print("[COMPLETE] Discovery Complete!")
    print("=" * 60)
    print(f"  Tokens analyzed:   {result['tokens_analyzed']}")
    print(f"  New wallets:       {result['new_wallets']}")
    print(f"  Updated wallets:   {result['updated_wallets']}")
    print(f"  Profiled wallets:  {result.get('profiled_wallets', 'N/A')}")

    errors = result.get("errors", [])
    if errors:
        print(f"  Errors:            {len(errors)}")


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="WallTrack Wallet Discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick discovery with defaults
  uv run python scripts/run_discovery.py

  # Find more tokens with lower thresholds
  uv run python scripts/run_discovery.py --tokens 30 --min-change 50 --min-volume 20000

  # Discover wallets for a specific token
  uv run python scripts/run_discovery.py --token 7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr

  # Just find pumped tokens (no wallet discovery)
  uv run python scripts/run_discovery.py --find-pumps-only
        """,
    )

    parser.add_argument(
        "--tokens",
        type=int,
        default=10,
        help="Maximum number of pumped tokens to analyze (default: 10)",
    )
    parser.add_argument(
        "--min-change",
        type=float,
        default=100.0,
        help="Minimum 24h price change %% (default: 100)",
    )
    parser.add_argument(
        "--min-volume",
        type=float,
        default=50000.0,
        help="Minimum 24h volume in USD (default: 50000)",
    )
    parser.add_argument(
        "--max-age",
        type=int,
        default=72,
        help="Maximum token age in hours (default: 72)",
    )
    parser.add_argument(
        "--early-window",
        type=int,
        default=30,
        help="Early buyer window in minutes (default: 30)",
    )
    parser.add_argument(
        "--min-profit",
        type=float,
        default=50.0,
        help="Minimum profit %% for wallet qualification (default: 50)",
    )
    parser.add_argument(
        "--token",
        type=str,
        default=None,
        help="Specific token mint address to analyze",
    )
    parser.add_argument(
        "--find-pumps-only",
        action="store_true",
        help="Only find pumped tokens, don't run wallet discovery",
    )
    parser.add_argument(
        "--skip-profile",
        action="store_true",
        help="Skip profiling newly discovered wallets",
    )

    return parser.parse_args()


async def main() -> int:
    """Main entry point."""
    args = parse_args()

    try:
        if args.find_pumps_only:
            await find_pumps_only(args)
        elif args.token:
            await discover_for_token(args.token, args)
        else:
            await run_full_discovery(args)

        return 0

    except KeyboardInterrupt:
        print("\n[WARN] Interrupted by user")
        return 1
    except Exception as e:
        log.error("discovery_failed", error=str(e))
        print(f"\n[ERROR] Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
