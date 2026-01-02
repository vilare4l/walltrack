"""Test if a specific wallet has transactions via RPC."""

import asyncio

from walltrack.services.solana.rpc_client import SolanaRPCClient
from walltrack.services.solana.transaction_parser import TransactionParser


async def test_wallet():
    """Test wallet transaction fetching."""
    client = SolanaRPCClient()
    parser = TransactionParser()
    wallet = "9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin"

    print(f"\n[TEST] Testing wallet: {wallet[:8]}...")

    # Fetch signatures
    sigs = await client.getSignaturesForAddress(wallet, limit=20)
    print(f"[OK] Signatures found: {len(sigs)}")

    if sigs:
        # Fetch first 3 transactions
        swap_count = 0
        for i, sig_info in enumerate(sigs[:3]):
            sig = sig_info.get("signature")
            if not sig:
                continue

            print(f"\n[TEST] Fetching transaction {i+1}/3: {sig[:8]}...")

            tx = await client.getTransaction(sig)
            if tx:
                print(f"[OK] Transaction fetched")

                # Try parsing
                parsed = parser.parse(tx)
                if parsed:
                    print(f"[OK] Parsed as {parsed.tx_type}: {parsed.amount_sol} SOL")
                    swap_count += 1
                else:
                    print(f"[WARN] Not a swap transaction")
            else:
                print(f"[ERROR] Transaction not found")

            # Rate limit
            await asyncio.sleep(1)

        print(f"\n[SUMMARY] Total swaps found: {swap_count}/{len(sigs[:3])}")
    else:
        print("[ERROR] No signatures found for this wallet")

    await client.close()


if __name__ == "__main__":
    asyncio.run(test_wallet())
