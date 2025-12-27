"""Simulate Helius webhooks for E2E testing.

This script sends realistic webhook payloads to the API to trigger
the full signal → position → order pipeline.
"""

import asyncio
import hashlib
import hmac
import json
import os
import random
import time
from datetime import UTC, datetime
from uuid import uuid4

import httpx

# Test configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
HMAC_SECRET = os.getenv("HELIUS_HMAC_SECRET", "test-secret-key")

# Wrapped SOL mint address
WRAPPED_SOL_MINT = "So11111111111111111111111111111111111111112"

# Sample tracked wallet (from a known profitable trader)
SAMPLE_WALLETS = [
    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",  # Example wallet
    "DYw8jCTfwHNRJhhmFcbXvVDTqWMEVFBX6ZKUmG5CNSKK",  # Another example
]

# Sample token addresses (memecoins)
SAMPLE_TOKENS = [
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (for testing)
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr",  # POPCAT
]


def generate_signature() -> str:
    """Generate a random Solana transaction signature."""
    return "".join(random.choices("123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz", k=88))


def create_swap_webhook_payload(
    wallet_address: str,
    token_address: str,
    direction: str = "buy",
    amount_sol: float = 0.5,
    amount_tokens: float = 1000000.0,
) -> dict:
    """
    Create a realistic Helius webhook payload for a swap.

    Args:
        wallet_address: Wallet making the swap
        token_address: Token being bought/sold
        direction: "buy" or "sell"
        amount_sol: SOL amount in the swap
        amount_tokens: Token amount in the swap

    Returns:
        Helius webhook payload dict
    """
    signature = generate_signature()
    timestamp = int(time.time())
    slot = 250000000 + random.randint(1, 1000000)

    # Build token transfers based on direction
    if direction == "buy":
        # Wallet sends SOL, receives tokens
        token_transfers = [
            {
                "fromUserAccount": wallet_address,
                "toUserAccount": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",  # Jupiter
                "mint": WRAPPED_SOL_MINT,
                "tokenAmount": amount_sol,
            },
            {
                "fromUserAccount": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
                "toUserAccount": wallet_address,
                "mint": token_address,
                "tokenAmount": amount_tokens,
            },
        ]
    else:
        # Wallet sends tokens, receives SOL
        token_transfers = [
            {
                "fromUserAccount": wallet_address,
                "toUserAccount": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
                "mint": token_address,
                "tokenAmount": amount_tokens,
            },
            {
                "fromUserAccount": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
                "toUserAccount": wallet_address,
                "mint": WRAPPED_SOL_MINT,
                "tokenAmount": amount_sol,
            },
        ]

    return {
        "webhookID": str(uuid4()),
        "type": "SWAP",
        "timestamp": timestamp,
        "signature": signature,
        "fee": 5000,  # 5000 lamports
        "feePayer": wallet_address,
        "slot": slot,
        "nativeTransfers": [],
        "tokenTransfers": token_transfers,
        "accountData": [
            {
                "account": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",
                "nativeBalanceChange": 0,
                "tokenBalanceChanges": [],
            }
        ],
        "source": "JUPITER",
        "description": f"Swap {amount_sol} SOL for {amount_tokens} tokens via Jupiter",
    }


def compute_hmac_signature(payload: bytes, secret: str) -> str:
    """Compute HMAC-SHA256 signature for payload."""
    return hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()


async def send_webhook(payload: dict, bypass_hmac: bool = True) -> dict:
    """
    Send webhook payload to API.

    Args:
        payload: Webhook payload dict
        bypass_hmac: If True, use test mode headers

    Returns:
        API response dict
    """
    payload_bytes = json.dumps(payload).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
    }

    if not bypass_hmac:
        signature = compute_hmac_signature(payload_bytes, HMAC_SECRET)
        headers["X-Helius-Signature"] = signature

    # For testing, we may need to bypass HMAC
    # The middleware should have a test mode
    headers["X-Test-Mode"] = "true"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_BASE_URL}/webhooks/helius",
            content=payload_bytes,
            headers=headers,
            timeout=30.0,
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text}")

        return {
            "status_code": response.status_code,
            "body": response.json() if response.status_code == 200 else response.text,
        }


async def scenario_1_buy_signal():
    """
    Scenario 1: Tracked wallet buys a memecoin.

    Expected flow:
    1. Webhook received
    2. Signal created (if wallet is tracked and passes filters)
    3. Position created (if signal score >= threshold)
    4. Entry order created
    """
    print("\n" + "=" * 60)
    print("SCENARIO 1: Buy Signal from Tracked Wallet")
    print("=" * 60)

    wallet = SAMPLE_WALLETS[0]
    token = SAMPLE_TOKENS[1]  # BONK

    payload = create_swap_webhook_payload(
        wallet_address=wallet,
        token_address=token,
        direction="buy",
        amount_sol=1.5,
        amount_tokens=5000000.0,
    )

    print(f"\nSending BUY webhook:")
    print(f"  Wallet: {wallet[:16]}...")
    print(f"  Token: {token[:16]}...")
    print(f"  Amount: 1.5 SOL")
    print(f"  Direction: BUY")

    result = await send_webhook(payload)
    return result


async def scenario_2_sell_signal():
    """
    Scenario 2: Tracked wallet sells a memecoin.

    Expected flow:
    1. Webhook received
    2. If we have a position in this token, may trigger exit
    """
    print("\n" + "=" * 60)
    print("SCENARIO 2: Sell Signal (Potential Exit Trigger)")
    print("=" * 60)

    wallet = SAMPLE_WALLETS[0]
    token = SAMPLE_TOKENS[1]

    payload = create_swap_webhook_payload(
        wallet_address=wallet,
        token_address=token,
        direction="sell",
        amount_sol=2.0,
        amount_tokens=5000000.0,
    )

    print(f"\nSending SELL webhook:")
    print(f"  Wallet: {wallet[:16]}...")
    print(f"  Token: {token[:16]}...")
    print(f"  Amount: 2.0 SOL received")
    print(f"  Direction: SELL")

    result = await send_webhook(payload)
    return result


async def scenario_3_batch_webhooks():
    """
    Scenario 3: Multiple webhooks in batch (like real Helius behavior).

    Tests system's ability to handle batch processing.
    """
    print("\n" + "=" * 60)
    print("SCENARIO 3: Batch Webhooks (3 transactions)")
    print("=" * 60)

    batch = []
    for i in range(3):
        payload = create_swap_webhook_payload(
            wallet_address=SAMPLE_WALLETS[i % len(SAMPLE_WALLETS)],
            token_address=SAMPLE_TOKENS[i % len(SAMPLE_TOKENS)],
            direction="buy" if i % 2 == 0 else "sell",
            amount_sol=0.5 + (i * 0.25),
            amount_tokens=1000000.0 * (i + 1),
        )
        batch.append(payload)

    print(f"\nSending batch of {len(batch)} webhooks...")

    result = await send_webhook(batch)
    return result


async def main():
    """Run all E2E scenarios."""
    print("\n" + "#" * 60)
    print("# WallTrack E2E Test - Webhook Simulation")
    print("#" * 60)
    print(f"\nAPI URL: {API_BASE_URL}")
    print(f"Time: {datetime.now(UTC).isoformat()}")

    # Check API health first
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            print(f"\nAPI Health: {response.status_code}")
        except Exception as e:
            print(f"\nERROR: Cannot connect to API: {e}")
            print("Please start the API server first:")
            print("  uv run python -m walltrack.main")
            return

    # Run scenarios
    results = {}

    results["scenario_1"] = await scenario_1_buy_signal()
    await asyncio.sleep(2)  # Allow processing

    results["scenario_2"] = await scenario_2_sell_signal()
    await asyncio.sleep(2)

    results["scenario_3"] = await scenario_3_batch_webhooks()

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for name, result in results.items():
        status = "OK" if result.get("status_code") == 200 else "FAILED"
        print(f"  {name}: {status}")


if __name__ == "__main__":
    asyncio.run(main())
