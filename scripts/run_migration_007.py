"""Run migration 007 - RPC Rate Limiting Configuration."""

import asyncio
from pathlib import Path

from walltrack.data.supabase.client import get_supabase_client
from walltrack.data.supabase.repositories.config_repo import ConfigRepository


async def main():
    """Execute migration 007."""
    print("Executing migration 007: RPC Rate Limiting Configuration")

    supabase_client = await get_supabase_client()
    config_repo = ConfigRepository(supabase_client)

    # Direct access to table for full control (category + description)
    table = supabase_client._client.table('config')

    configs = [
        {'key': 'profiling_signatures_limit', 'value': '20'},
        {'key': 'profiling_transactions_limit', 'value': '20'},
        {'key': 'profiling_rpc_delay_ms', 'value': '1000'},
        {'key': 'profiling_wallet_delay_seconds', 'value': '10'},
        {'key': 'profiling_batch_size', 'value': '10'},
    ]

    print("\nInserting RPC rate limiting configs...")
    for cfg in configs:
        try:
            await table.upsert(cfg, on_conflict='key').execute()
            print(f"   [OK] {cfg['key']}: {cfg['value']}")
        except Exception as e:
            print(f"   [ERROR] {cfg['key']}: {e}")

    # Verify
    print("\nVerifying configs...")
    result = await table.select('key, value').in_('key', [c['key'] for c in configs]).execute()
    print(f"\n[OK] Migration complete: {len(result.data)} configs created")
    for row in result.data:
        print(f"   - {row['key']}: {row['value']}")


if __name__ == "__main__":
    asyncio.run(main())
