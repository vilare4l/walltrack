"""Collect historical data from real token pumps.

Finds tokens that pumped on Solana, identifies early/performer wallets,
and stores the data for backtesting.
"""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import httpx
from dotenv import load_dotenv

from walltrack.data.supabase.client import get_supabase_client

load_dotenv()

HELIUS_API_KEY = os.getenv("HELIUS_API_KEY")
HELIUS_RPC_URL = os.getenv("HELIUS_RPC_URL")
DEXSCREENER_API_URL = os.getenv("DEXSCREENER_API_URL", "https://api.dexscreener.com/latest")


async def get_trending_tokens() -> list[dict]:
    """Get trending/pumping tokens from DexScreener."""
    async with httpx.AsyncClient(timeout=30) as client:
        # Get Solana tokens sorted by price change
        response = await client.get(
            f"{DEXSCREENER_API_URL}/dex/tokens/solana",
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            print(f"DexScreener API error: {response.status_code}")
            return []

        data = response.json()
        return data.get("pairs", [])


async def search_pump_tokens(min_gain_pct: float = 100) -> list[dict]:
    """Search for tokens that have pumped significantly.

    Args:
        min_gain_pct: Minimum price gain percentage to consider a pump.

    Returns:
        List of token pairs that match criteria.
    """
    all_pumped = []

    async with httpx.AsyncClient(timeout=30) as client:
        # Try multiple search terms to find more tokens
        search_terms = ["pump", "moon", "pepe", "doge", "cat", "ai", "meme"]

        for term in search_terms:
            try:
                response = await client.get(
                    "https://api.dexscreener.com/latest/dex/search",
                    params={"q": term},
                    headers={"Accept": "application/json"},
                )

                if response.status_code != 200:
                    continue

                data = response.json()
                pairs = data.get("pairs", [])

                # Filter for Solana pairs with gains
                for pair in pairs:
                    if pair.get("chainId") != "solana":
                        continue

                    price_change = pair.get("priceChange", {})
                    h24_change = price_change.get("h24", 0) or 0

                    # Check if it pumped
                    if h24_change >= min_gain_pct:
                        # Avoid duplicates
                        token_addr = pair.get("baseToken", {}).get("address", "")
                        if not any(p.get("baseToken", {}).get("address") == token_addr for p in all_pumped):
                            all_pumped.append(pair)

                await asyncio.sleep(0.3)  # Rate limit
            except Exception as e:
                print(f"  Search error for '{term}': {e}")

        # Also try the boosted/trending tokens
        try:
            response = await client.get(
                "https://api.dexscreener.com/token-boosts/top/v1",
                headers={"Accept": "application/json"},
            )
            if response.status_code == 200:
                boosts = response.json()
                for boost in boosts[:20]:
                    if boost.get("chainId") == "solana":
                        token_addr = boost.get("tokenAddress", "")
                        # Get pair info
                        pair_response = await client.get(
                            f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}",
                        )
                        if pair_response.status_code == 200:
                            pair_data = pair_response.json()
                            pairs = pair_data.get("pairs", [])
                            if pairs:
                                pair = pairs[0]
                                h24_change = pair.get("priceChange", {}).get("h24", 0) or 0
                                if h24_change >= min_gain_pct / 2:  # Lower threshold for boosted
                                    if not any(p.get("baseToken", {}).get("address") == token_addr for p in all_pumped):
                                        all_pumped.append(pair)
                        await asyncio.sleep(0.2)
        except Exception as e:
            print(f"  Boost API error: {e}")

    return all_pumped


async def get_token_info(token_address: str) -> dict | None:
    """Get detailed token info from DexScreener."""
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"https://api.dexscreener.com/latest/dex/tokens/{token_address}",
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            return None

        data = response.json()
        pairs = data.get("pairs", [])
        return pairs[0] if pairs else None


async def get_token_transactions(token_address: str, limit: int = 100) -> list[dict]:
    """Get recent transactions for a token using Helius."""
    if not HELIUS_API_KEY:
        print("HELIUS_API_KEY not configured")
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        # Use Helius parsed transaction history
        response = await client.post(
            f"https://api.helius.xyz/v0/addresses/{token_address}/transactions",
            params={"api-key": HELIUS_API_KEY},
            json={"limit": limit},
        )

        if response.status_code != 200:
            print(f"Helius API error: {response.status_code} - {response.text[:200]}")
            return []

        return response.json()


async def get_token_holders(token_address: str) -> list[dict]:
    """Get token holders using Helius DAS API."""
    if not HELIUS_API_KEY:
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            f"https://mainnet.helius-rpc.com/?api-key={HELIUS_API_KEY}",
            json={
                "jsonrpc": "2.0",
                "id": "holders",
                "method": "getTokenAccounts",
                "params": {"mint": token_address, "limit": 100},
            },
        )

        if response.status_code != 200:
            return []

        data = response.json()
        return data.get("result", {}).get("token_accounts", [])


async def get_swap_transactions(token_address: str) -> list[dict]:
    """Get swap transactions for a token (buys/sells)."""
    if not HELIUS_API_KEY:
        return []

    async with httpx.AsyncClient(timeout=60) as client:
        # Get parsed transactions for the token
        response = await client.get(
            f"https://api.helius.xyz/v0/addresses/{token_address}/transactions",
            params={
                "api-key": HELIUS_API_KEY,
                "limit": 100,
            },
        )

        if response.status_code != 200:
            print(f"Helius API error: {response.status_code} - {response.text[:100]}")
            return []

        txs = response.json()

        # Filter for swap-like transactions (those with token transfers)
        swaps = [tx for tx in txs if tx.get("tokenTransfers") and len(tx.get("tokenTransfers", [])) > 0]
        return swaps


async def analyze_early_buyers(token_address: str, token_info: dict) -> list[dict]:
    """Identify early buyers for a token.

    Returns list of wallets that bought early with their entry info.
    """
    # Get transaction history
    txs = await get_swap_transactions(token_address)

    if not txs:
        print(f"         No transactions found for {token_address[:8]}...")
        return []

    # Parse transactions to find buys
    buyers = {}

    for tx in txs:
        timestamp = tx.get("timestamp", 0)
        fee_payer = tx.get("feePayer", "")

        if not fee_payer or not timestamp:
            continue

        # Check tokenTransfers for buys (receiving the target token)
        token_transfers = tx.get("tokenTransfers", [])

        for transfer in token_transfers:
            mint = transfer.get("mint", "")
            to_user = transfer.get("toUserAccount", "")
            amount = float(transfer.get("tokenAmount", 0) or 0)

            # This is a buy if the wallet received the target token
            if mint == token_address and to_user and amount > 0:
                wallet = to_user

                if wallet not in buyers:
                    buyers[wallet] = {
                        "wallet": wallet,
                        "first_buy_time": timestamp,
                        "total_bought": amount,
                        "buy_count": 1,
                    }
                else:
                    buyers[wallet]["total_bought"] += amount
                    buyers[wallet]["buy_count"] += 1
                    if timestamp < buyers[wallet]["first_buy_time"]:
                        buyers[wallet]["first_buy_time"] = timestamp

    # Sort by earliest buy time
    early_buyers = sorted(buyers.values(), key=lambda x: x["first_buy_time"])

    return early_buyers[:50]  # Top 50 earliest buyers


async def store_historical_data(
    supabase,
    token_address: str,
    token_info: dict,
    early_buyers: list[dict],
) -> tuple[int, int]:
    """Store historical signals and prices in Supabase.

    Returns (signals_stored, prices_stored).
    """
    signals_stored = 0
    prices_stored = 0

    current_price = float(token_info.get("priceUsd", 0) or 0)
    market_cap = float(token_info.get("marketCap", 0) or 0)
    liquidity = float(token_info.get("liquidity", {}).get("usd", 0) or 0)

    # Get price changes to reconstruct historical prices
    price_change = token_info.get("priceChange", {})
    now = datetime.now(UTC)

    # Calculate historical prices from percentage changes
    # DexScreener gives: m5, h1, h6, h24 changes
    price_points = []

    # Current price
    price_points.append((now, current_price))

    # 5 minutes ago
    m5_change = float(price_change.get("m5", 0) or 0) / 100
    if m5_change != 0:
        price_5m_ago = current_price / (1 + m5_change)
        price_points.append((now - timedelta(minutes=5), price_5m_ago))

    # 1 hour ago
    h1_change = float(price_change.get("h1", 0) or 0) / 100
    if h1_change != 0:
        price_1h_ago = current_price / (1 + h1_change)
        price_points.append((now - timedelta(hours=1), price_1h_ago))

    # 6 hours ago
    h6_change = float(price_change.get("h6", 0) or 0) / 100
    if h6_change != 0:
        price_6h_ago = current_price / (1 + h6_change)
        price_points.append((now - timedelta(hours=6), price_6h_ago))

    # 24 hours ago
    h24_change = float(price_change.get("h24", 0) or 0) / 100
    if h24_change != 0:
        price_24h_ago = current_price / (1 + h24_change)
        price_points.append((now - timedelta(hours=24), price_24h_ago))

    # Store all price points
    for timestamp, price in price_points:
        price_data = {
            "id": str(uuid4()),
            "token_address": token_address,
            "timestamp": timestamp.isoformat(),
            "price_usd": price,
            "source": "dexscreener",
        }

        try:
            await supabase.table("historical_prices").insert(price_data).execute()
            prices_stored += 1
        except Exception as e:
            if "duplicate" not in str(e).lower():
                pass  # Ignore duplicate errors silently

    # Store signals for early buyers
    # Sort price points by time to find entry price
    price_points_sorted = sorted(price_points, key=lambda x: x[0])

    for buyer in early_buyers:
        entry_time = buyer.get("first_buy_time", 0)

        # Find the closest historical price to entry time
        if entry_time:
            entry_dt = datetime.fromtimestamp(entry_time, UTC)
            # Find price closest to entry time
            entry_price = current_price
            for ts, price in price_points_sorted:
                if ts <= entry_dt:
                    entry_price = price
                else:
                    break
        else:
            entry_dt = now
            entry_price = current_price

        # Calculate wallet score based on performance
        # If they bought early and price went up, higher score
        if entry_price > 0:
            gain_multiplier = current_price / entry_price
            # Score: 0.5 base + up to 0.4 based on gains
            wallet_score = min(0.95, 0.5 + min(gain_multiplier - 1, 4) * 0.1)
        else:
            wallet_score = 0.6

        # Boost score for multiple buys (conviction)
        wallet_score = min(0.95, wallet_score + (buyer.get("buy_count", 1) - 1) * 0.05)

        signal_data = {
            "id": str(uuid4()),
            "timestamp": entry_dt.isoformat(),
            "wallet_address": buyer["wallet"],
            "token_address": token_address,
            "wallet_score": round(wallet_score, 4),
            "cluster_id": None,
            "cluster_amplification": 1.0,
            "token_price_usd": entry_price,
            "token_market_cap": market_cap,
            "token_liquidity": liquidity,
            "token_age_minutes": None,
            "computed_score": round(wallet_score, 4),
            "score_breakdown": {
                "wallet": round(wallet_score, 4),
                "token": 0.6,
                "cluster": 0.5,
                "context": 0.5,
            },
            "trade_eligible": wallet_score >= 0.7,
        }

        try:
            await supabase.table("historical_signals").insert(signal_data).execute()
            signals_stored += 1
        except Exception as e:
            if "duplicate" not in str(e).lower():
                print(f"  Error storing signal: {e}")

    return signals_stored, prices_stored


def print_separator(title: str = "") -> None:
    """Print a visual separator."""
    print("\n" + "=" * 70)
    if title:
        print(f"  {title}")
        print("=" * 70)


async def main():
    """Main collection workflow."""
    print_separator("COLLECTING HISTORICAL PUMP DATA")

    print("\n  Searching for tokens that pumped recently...")

    # Get pumped tokens
    pumped_tokens = await search_pump_tokens(min_gain_pct=50)

    print(f"\n  Found {len(pumped_tokens)} tokens with 50%+ gains in 24h")

    if not pumped_tokens:
        # Try getting any trending Solana tokens
        print("  Trying trending tokens instead...")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://api.dexscreener.com/latest/dex/search",
                params={"q": "SOL"},
            )
            if response.status_code == 200:
                data = response.json()
                pumped_tokens = [
                    p for p in data.get("pairs", [])
                    if p.get("chainId") == "solana"
                ][:20]

    if not pumped_tokens:
        print("\n  No tokens found. Check API connectivity.")
        return

    # Connect to Supabase
    supabase = await get_supabase_client()
    await supabase.connect()

    print_separator("ANALYZING TOKENS")

    total_signals = 0
    total_prices = 0

    # Process top tokens
    for i, token in enumerate(pumped_tokens[:10]):  # Limit to 10 tokens
        token_address = token.get("baseToken", {}).get("address", "")
        token_name = token.get("baseToken", {}).get("symbol", "Unknown")
        price_change = token.get("priceChange", {}).get("h24", 0) or 0

        if not token_address:
            continue

        print(f"\n  [{i+1}/10] {token_name} ({token_address[:8]}...)")
        print(f"         24h Change: {price_change:+.1f}%")

        # Get detailed info
        token_info = await get_token_info(token_address)
        if not token_info:
            print("         Skipping - no info available")
            continue

        # Find early buyers
        print("         Analyzing early buyers...")
        early_buyers = await analyze_early_buyers(token_address, token_info)
        print(f"         Found {len(early_buyers)} early buyers")

        if early_buyers:
            # Store data
            signals, prices = await store_historical_data(
                supabase, token_address, token_info, early_buyers
            )
            total_signals += signals
            total_prices += prices
            print(f"         Stored: {signals} signals, {prices} prices")

        # Rate limiting
        await asyncio.sleep(0.5)

    print_separator("COLLECTION COMPLETE")

    print(f"\n  Total Signals Stored: {total_signals}")
    print(f"  Total Prices Stored:  {total_prices}")

    if total_signals > 0:
        print("\n  You can now run backtests with real data!")
        print("  Run: uv run python scripts/check_and_run_backtest.py")
    else:
        print("\n  No data collected. This may be due to:")
        print("    - API rate limits")
        print("    - No swap transactions found")
        print("    - Helius API key issues")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
