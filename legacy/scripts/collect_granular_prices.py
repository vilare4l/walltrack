"""Collect granular historical prices for tokens.

Uses Birdeye API to get 10-minute interval price data for tokens
already in the database, enabling realistic backtesting.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from walltrack.data.supabase.client import get_supabase_client

load_dotenv()

BIRDEYE_API_KEY = os.getenv("BIRDEYE_API_KEY", "")
BIRDEYE_API_URL = "https://public-api.birdeye.so"


async def get_tokens_from_db(supabase) -> list[str]:
    """Get unique token addresses from historical signals."""
    response = await (
        supabase.table("historical_signals")
        .select("token_address")
        .limit(1000)
        .execute()
    )

    tokens = set()
    for row in response.data or []:
        tokens.add(row["token_address"])

    return list(tokens)


async def get_birdeye_ohlcv(
    token_address: str,
    time_from: int,
    time_to: int,
    interval: str = "15m",
) -> list[dict]:
    """Get OHLCV data from Birdeye API.

    Args:
        token_address: Solana token mint address.
        time_from: Unix timestamp start.
        time_to: Unix timestamp end.
        interval: Candle interval (1m, 5m, 15m, 30m, 1H, etc.)

    Returns:
        List of OHLCV candles.
    """
    if not BIRDEYE_API_KEY:
        return []

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(
                f"{BIRDEYE_API_URL}/defi/ohlcv",
                params={
                    "address": token_address,
                    "type": interval,
                    "time_from": time_from,
                    "time_to": time_to,
                },
                headers={
                    "X-API-KEY": BIRDEYE_API_KEY,
                    "Accept": "application/json",
                },
            )

            if response.status_code != 200:
                print(f"         Birdeye error: {response.status_code}", flush=True)
                return []

            data = response.json()
            return data.get("data", {}).get("items", [])
    except httpx.TimeoutException:
        print("         Birdeye timeout", flush=True)
        return []
    except Exception as e:
        print(f"         Birdeye error: {e}", flush=True)
        return []


async def get_dexscreener_chart(token_address: str) -> list[dict]:
    """Fallback: Get price data from DexScreener pair info.

    DexScreener doesn't have a public candle API, so we use
    the pair info and interpolate prices.
    """
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            return []

        data = response.json()
        pairs = data.get("pairs", [])

        if not pairs:
            return []

        pair = pairs[0]
        current_price = float(pair.get("priceUsd", 0) or 0)
        price_change = pair.get("priceChange", {})

        if current_price == 0:
            return []

        # Build price points from percentage changes
        now = datetime.now(UTC)
        prices = []

        # Current
        prices.append({"timestamp": int(now.timestamp()), "price": current_price})

        # 5 minutes ago
        m5 = float(price_change.get("m5", 0) or 0) / 100
        if m5 != 0:
            price_5m = current_price / (1 + m5)
            prices.append({
                "timestamp": int((now - timedelta(minutes=5)).timestamp()),
                "price": price_5m,
            })

        # 1 hour ago
        h1 = float(price_change.get("h1", 0) or 0) / 100
        if h1 != 0:
            price_1h = current_price / (1 + h1)
            prices.append({
                "timestamp": int((now - timedelta(hours=1)).timestamp()),
                "price": price_1h,
            })

        # 6 hours ago
        h6 = float(price_change.get("h6", 0) or 0) / 100
        if h6 != 0:
            price_6h = current_price / (1 + h6)
            prices.append({
                "timestamp": int((now - timedelta(hours=6)).timestamp()),
                "price": price_6h,
            })

        # 24 hours ago
        h24 = float(price_change.get("h24", 0) or 0) / 100
        if h24 != 0:
            price_24h = current_price / (1 + h24)
            prices.append({
                "timestamp": int((now - timedelta(hours=24)).timestamp()),
                "price": price_24h,
            })

        # Interpolate to create 10-minute intervals
        prices.sort(key=lambda x: x["timestamp"])
        interpolated = interpolate_prices(prices, interval_minutes=10)

        return interpolated


def interpolate_prices(
    price_points: list[dict],
    interval_minutes: int = 10,
) -> list[dict]:
    """Interpolate between price points to create regular intervals.

    Args:
        price_points: List of {"timestamp": int, "price": float}.
        interval_minutes: Desired interval in minutes.

    Returns:
        List of interpolated price points.
    """
    if len(price_points) < 2:
        return price_points

    result = []
    interval_secs = interval_minutes * 60

    for i in range(len(price_points) - 1):
        p1 = price_points[i]
        p2 = price_points[i + 1]

        t1, price1 = p1["timestamp"], p1["price"]
        t2, price2 = p2["timestamp"], p2["price"]

        # Add the starting point
        result.append({"timestamp": t1, "price": price1})

        # Interpolate between p1 and p2
        current_t = t1 + interval_secs
        while current_t < t2:
            # Linear interpolation
            ratio = (current_t - t1) / (t2 - t1)
            interp_price = price1 + (price2 - price1) * ratio
            result.append({"timestamp": current_t, "price": interp_price})
            current_t += interval_secs

    # Add the last point
    result.append(price_points[-1])

    return result


async def store_prices(
    supabase,
    token_address: str,
    prices: list[dict],
) -> int:
    """Store price points in the database.

    Args:
        supabase: Supabase client.
        token_address: Token mint address.
        prices: List of price points.

    Returns:
        Number of prices stored.
    """
    stored = 0

    for price_point in prices:
        timestamp = price_point.get("timestamp") or price_point.get("unixTime")
        price = price_point.get("price") or price_point.get("c") or price_point.get("close")

        if not timestamp or not price:
            continue

        # Convert timestamp to datetime
        if isinstance(timestamp, int):
            dt = datetime.fromtimestamp(timestamp, UTC)
        else:
            dt = timestamp

        price_data = {
            "id": str(uuid4()),
            "token_address": token_address,
            "timestamp": dt.isoformat(),
            "price_usd": float(price),
            "source": "birdeye" if BIRDEYE_API_KEY else "interpolated",
        }

        try:
            await supabase.table("historical_prices").insert(price_data).execute()
            stored += 1
        except Exception as e:
            if "duplicate" not in str(e).lower():
                pass  # Ignore duplicates

    return stored


def print_separator(title: str = "") -> None:
    """Print a visual separator."""
    print("\n" + "=" * 70, flush=True)
    if title:
        print(f"  {title}", flush=True)
        print("=" * 70, flush=True)


async def main():
    """Main collection workflow."""
    print_separator("COLLECTING GRANULAR PRICE DATA")

    # Connect to Supabase first
    print("\n  Connecting to Supabase...", flush=True)
    supabase = await get_supabase_client()
    await supabase.connect()
    print("  Connected!", flush=True)

    # Get tokens from database
    print("  Fetching tokens from database...", flush=True)
    tokens = await get_tokens_from_db(supabase)
    print(f"  Found {len(tokens)} tokens", flush=True)

    if not tokens:
        print("\n  No tokens found. Run collect_historical_pumps.py first.")
        return

    # Time range: last 24 hours
    now = datetime.now(UTC)
    time_to = int(now.timestamp())
    time_from = int((now - timedelta(hours=24)).timestamp())

    print(f"\n  Time range: {now - timedelta(hours=24)} to {now}", flush=True)
    print(f"  Interval: 10-15 minutes", flush=True)

    if BIRDEYE_API_KEY:
        print(f"  Data source: Birdeye API (with DexScreener fallback)", flush=True)
    else:
        print(f"  Data source: DexScreener + Interpolation", flush=True)

    print_separator("COLLECTING PRICES")

    total_prices = 0

    for i, token in enumerate(tokens):
        print(f"\n  [{i+1}/{len(tokens)}] {token[:8]}...", flush=True)

        # Try Birdeye first (with quick timeout)
        prices = []
        if BIRDEYE_API_KEY:
            prices = await get_birdeye_ohlcv(
                token_address=token,
                time_from=time_from,
                time_to=time_to,
                interval="15m",  # 15-minute candles
            )

        # Fallback to DexScreener interpolation
        if not prices:
            print("         Using DexScreener fallback...", flush=True)
            prices = await get_dexscreener_chart(token)

        if prices:
            stored = await store_prices(supabase, token, prices)
            total_prices += stored
            print(f"         Stored {stored} price points", flush=True)
        else:
            print("         No price data available", flush=True)

        # Rate limiting
        await asyncio.sleep(0.3)

    print_separator("COLLECTION COMPLETE")

    print(f"\n  Total price points stored: {total_prices}", flush=True)
    print(f"  Tokens processed: {len(tokens)}", flush=True)

    if total_prices > 0:
        avg_per_token = total_prices / len(tokens)
        print(f"  Average per token: {avg_per_token:.1f} points")
        print("\n  You can now run backtests with granular data!")
        print("  Run: uv run python scripts/check_and_run_backtest.py")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
