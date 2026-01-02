"""Test script to measure Solana RPC rate limits and optimal parameters.

This script helps determine:
1. Real RPC rate limit (requests/second)
2. Circuit breaker behavior
3. Optimal delays between requests
4. Time to analyze 1 wallet
"""

import asyncio
import time
from datetime import datetime

import structlog

from walltrack.services.solana.rpc_client import SolanaRPCClient

log = structlog.get_logger(__name__)


async def test_burst_limit(client: SolanaRPCClient, test_wallet: str):
    """Test how many rapid requests we can make before getting rate limited.

    Args:
        client: RPC client to test
        test_wallet: A valid wallet address to query
    """
    print("\n" + "=" * 60)
    print("TEST 1: Burst Rate Limit")
    print("=" * 60)
    print("Sending requests as fast as possible until rate limited...\n")

    success_count = 0
    error_count = 0
    start_time = time.time()

    for i in range(50):  # Try 50 rapid requests
        try:
            await client.getSignaturesForAddress(test_wallet, limit=1)
            success_count += 1
            elapsed = time.time() - start_time
            print(f"[OK] Request {i+1}: SUCCESS (elapsed: {elapsed:.2f}s)")
        except Exception as e:
            error_count += 1
            elapsed = time.time() - start_time
            error_msg = str(e)
            if "429" in error_msg:
                print(f"[ERROR] Request {i+1}: RATE LIMITED at {elapsed:.2f}s")
                break
            elif "Circuit breaker" in error_msg:
                print(f"[WARN]  Request {i+1}: CIRCUIT BREAKER at {elapsed:.2f}s")
                break
            else:
                print(f"[ERROR] Request {i+1}: ERROR - {error_msg[:50]}")

    elapsed_total = time.time() - start_time

    print(f"\n[STATS] Results:")
    print(f"   Success: {success_count} requests")
    print(f"   Errors: {error_count} requests")
    print(f"   Time: {elapsed_total:.2f}s")
    print(f"   Rate: {success_count / elapsed_total:.2f} req/s")


async def test_sustained_rate(client: SolanaRPCClient, test_wallet: str, delay_ms: int):
    """Test sustained request rate with fixed delay.

    Args:
        client: RPC client to test
        test_wallet: A valid wallet address to query
        delay_ms: Delay in milliseconds between requests
    """
    print("\n" + "=" * 60)
    print(f"TEST 2: Sustained Rate ({delay_ms}ms delay)")
    print("=" * 60)
    print(f"Sending 20 requests with {delay_ms}ms delay between each...\n")

    success_count = 0
    error_count = 0
    start_time = time.time()

    for i in range(20):
        try:
            await client.getSignaturesForAddress(test_wallet, limit=1)
            success_count += 1
            elapsed = time.time() - start_time
            print(f"[OK] Request {i+1}: SUCCESS (total time: {elapsed:.2f}s)")
        except Exception as e:
            error_count += 1
            error_msg = str(e)
            if "429" in error_msg:
                print(f"[ERROR] Request {i+1}: RATE LIMITED")
            elif "Circuit breaker" in error_msg:
                print(f"[WARN]  Request {i+1}: CIRCUIT BREAKER")
            else:
                print(f"[ERROR] Request {i+1}: ERROR - {error_msg[:50]}")

        # Add delay
        await asyncio.sleep(delay_ms / 1000.0)

    elapsed_total = time.time() - start_time

    print(f"\n[STATS] Results:")
    print(f"   Success: {success_count}/20 requests")
    print(f"   Errors: {error_count}/20 requests")
    print(f"   Time: {elapsed_total:.2f}s")
    if success_count > 0:
        print(f"   Average rate: {success_count / elapsed_total:.2f} req/s")


async def test_wallet_analysis_time(client: SolanaRPCClient, test_wallet: str):
    """Measure time to fetch data for 1 wallet analysis.

    Args:
        client: RPC client to test
        test_wallet: A valid wallet address to query
    """
    print("\n" + "=" * 60)
    print("TEST 3: Single Wallet Analysis Time")
    print("=" * 60)
    print("Simulating full wallet analysis (signatures + sample transactions)...\n")

    start_time = time.time()

    try:
        # Step 1: Get signatures
        print("[INFO] Fetching signatures (limit=100)...")
        step1_start = time.time()
        signatures = await client.getSignaturesForAddress(test_wallet, limit=100)
        step1_time = time.time() - step1_start
        sig_count = len(signatures) if signatures else 0
        print(f"   [OK] Got {sig_count} signatures in {step1_time:.2f}s")

        # Step 2: Fetch sample transactions (first 10)
        if signatures:
            sample_size = min(10, len(signatures))
            print(f"\n[FETCH] Fetching {sample_size} transactions...")
            step2_start = time.time()

            tx_success = 0
            tx_errors = 0

            for i, sig_obj in enumerate(signatures[:sample_size]):
                try:
                    sig = sig_obj.get("signature") if isinstance(sig_obj, dict) else sig_obj
                    await client.getTransaction(sig)
                    tx_success += 1
                    print(f"   [OK] Transaction {i+1}/{sample_size}")
                except Exception as e:
                    tx_errors += 1
                    error_msg = str(e)
                    if "429" in error_msg:
                        print(f"   [ERROR] Transaction {i+1}/{sample_size}: RATE LIMITED")
                        break
                    elif "Circuit breaker" in error_msg:
                        print(f"   [WARN]  Transaction {i+1}/{sample_size}: CIRCUIT BREAKER")
                        break
                    else:
                        print(f"   [ERROR] Transaction {i+1}/{sample_size}: {error_msg[:40]}")

                # Small delay between transactions
                await asyncio.sleep(0.5)

            step2_time = time.time() - step2_start
            print(f"\n   [STATS] Transactions: {tx_success} success, {tx_errors} errors in {step2_time:.2f}s")

        total_time = time.time() - start_time

        print(f"\n[STATS] Total Wallet Analysis Time: {total_time:.2f}s")
        print(f"   To analyze 52 wallets: ~{total_time * 52 / 60:.1f} minutes")

    except Exception as e:
        print(f"[ERROR] Analysis failed: {e}")


async def calculate_optimal_parameters():
    """Calculate and display optimal configuration parameters."""
    print("\n" + "=" * 60)
    print("OPTIMAL PARAMETERS CALCULATION")
    print("=" * 60)

    # Known constraints (source: https://solana.com/docs/references/clusters)
    rpc_limit_total = 100  # 100 req / 10 seconds per IP (all endpoints)
    rpc_limit_per_endpoint = 40  # 40 req / 10 seconds per IP per single RPC
    rpc_limit_per_sec = 4  # = 40 / 10 = 4 req/sec per endpoint (conservative)

    print(f"\n[LIST] Official Solana Limits (api.mainnet-beta.solana.com):")
    print(f"   Total: {rpc_limit_total} req / 10s = {rpc_limit_total / 10:.0f} req/sec (all endpoints)")
    print(f"   Per endpoint: {rpc_limit_per_endpoint} req / 10s = {rpc_limit_per_sec:.0f} req/sec")
    print(f"   Conservative target: 2-3 req/sec (safety margin)")

    # Scenarios
    scenarios = [
        {
            "name": "Conservative (100 tx/wallet)",
            "signatures_limit": 100,
            "tx_to_fetch": 100,
            "requests_per_wallet": 101,  # 1 sig call + 100 tx calls
        },
        {
            "name": "Moderate (50 tx/wallet)",
            "signatures_limit": 50,
            "tx_to_fetch": 50,
            "requests_per_wallet": 51,
        },
        {
            "name": "Light (20 tx/wallet)",
            "signatures_limit": 20,
            "tx_to_fetch": 20,
            "requests_per_wallet": 21,
        },
        {
            "name": "Minimal (10 tx/wallet)",
            "signatures_limit": 10,
            "tx_to_fetch": 10,
            "requests_per_wallet": 11,
        },
    ]

    wallets_to_analyze = 52

    print(f"\n[STATS] Scenarios (for {wallets_to_analyze} wallets):\n")

    for scenario in scenarios:
        total_requests = scenario["requests_per_wallet"] * wallets_to_analyze
        time_at_4rps = total_requests / 4  # seconds
        time_at_2rps = total_requests / 2  # seconds (conservative)

        print(f"   {scenario['name']}:")
        print(f"      • Requests/wallet: {scenario['requests_per_wallet']}")
        print(f"      • Total requests: {total_requests}")
        print(f"      • Time at 4 req/s: {time_at_4rps / 60:.1f} min")
        print(f"      • Time at 2 req/s: {time_at_2rps / 60:.1f} min (safe)")
        print(f"      • Delay/request: 500ms (2 req/s)")
        print(f"      • Delay/wallet: {scenario['requests_per_wallet'] * 0.5:.1f}s automatic")
        print()

    print("[TIP] Recommendations:")
    print("   • Start with 'Light' scenario (20 tx/wallet)")
    print("   • Use 500ms delay between RPC calls (already implemented)")
    print("   • Add 5s delay between wallets (extra safety)")
    print("   • Process max 10 wallets per batch")
    print("   • Store ALL in config table for easy tuning")


async def main():
    """Run all RPC limit tests."""
    print("\n" + "=" * 60)
    print("SOLANA RPC RATE LIMIT TESTING")
    print("=" * 60)
    print(f"Start time: {datetime.now().isoformat()}\n")

    # Test wallet - using a known active wallet from our DB
    test_wallet = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    # Create RPC client
    client = SolanaRPCClient()

    try:
        # Test 1: Burst limit
        await test_burst_limit(client, test_wallet)

        # Wait for circuit breaker to reset
        print("\n[WAIT] Waiting 35s for circuit breaker reset...")
        await asyncio.sleep(35)

        # Test 2: Sustained rate with 500ms delay
        await test_sustained_rate(client, test_wallet, delay_ms=500)

        # Wait for circuit breaker to reset
        print("\n[WAIT] Waiting 35s for circuit breaker reset...")
        await asyncio.sleep(35)

        # Test 3: Full wallet analysis
        await test_wallet_analysis_time(client, test_wallet)

        # Calculate optimal parameters
        await calculate_optimal_parameters()

    finally:
        await client.close()

    print("\n" + "=" * 60)
    print("[OK] TESTING COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
