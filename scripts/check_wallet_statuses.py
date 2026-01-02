"""Quick script to check wallet statuses in database."""

import asyncio

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


async def main():
    """Check wallet statuses."""
    client = await get_supabase_client()
    repo = WalletRepository(client=client)

    wallets = await repo.get_all(limit=100)
    print(f"\nTotal wallets: {len(wallets)}")

    # Group by status
    by_status = {}
    for wallet in wallets:
        status = wallet.status or "null"
        by_status[status] = by_status.get(status, 0) + 1

    print("\nWallets by status:")
    for status, count in sorted(by_status.items()):
        print(f"  {status}: {count}")

    # Show first 5 wallets
    print("\nFirst 5 wallets:")
    for wallet in wallets[:5]:
        print(f"  - {wallet.address[:8]}... status={wallet.status}")


if __name__ == "__main__":
    asyncio.run(main())
