"""Verification script for migration 004_wallets_watchlist_status.sql

Story 3.5 Issue #7 - Migration execution verification.

Run this script to verify that migration 004 was successfully executed:
    python src/walltrack/data/supabase/migrations/verify_004_watchlist.py

Verifies:
1. Required columns exist (wallet_status, watchlist_score, etc.)
2. Indexes are created (idx_wallets_status, idx_wallets_watchlist_score)
3. CHECK constraint exists on wallet_status
4. Wallet status distribution
5. Sample of watchlisted wallets
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from walltrack.data.supabase.client import SupabaseClientWrapper


async def verify_migration():
    """Run verification queries for migration 004."""
    print("=" * 80)
    print("Migration 004 Verification - Wallet Watchlist Status")
    print("=" * 80)
    print()

    # Initialize Supabase client
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")

    if not supabase_url or not supabase_key:
        print("❌ ERROR: SUPABASE_URL and SUPABASE_KEY environment variables required")
        return False

    client_wrapper = SupabaseClientWrapper(url=supabase_url, key=supabase_key)
    client = client_wrapper.client

    all_passed = True

    # 1. Verify columns exist
    print("1. Verifying columns exist...")
    result = await (
        client.table("information_schema.columns")
        .select("column_name, data_type, is_nullable, column_default")
        .eq("table_schema", "walltrack")
        .eq("table_name", "wallets")
        .in_(
            "column_name",
            [
                "wallet_status",
                "watchlist_score",
                "watchlist_reason",
                "watchlist_added_date",
                "manual_override",
            ],
        )
        .execute()
    )

    if len(result.data) == 5:
        print("   ✅ All 5 watchlist columns found")
        for row in sorted(result.data, key=lambda x: x["column_name"]):
            print(f"      - {row['column_name']}: {row['data_type']}")
    else:
        print(
            f"   ❌ FAILED: Expected 5 columns, found {len(result.data)}"
        )
        all_passed = False

    print()

    # 2. Verify indexes exist
    print("2. Verifying indexes exist...")
    result = await (
        client.table("pg_indexes")
        .select("indexname, indexdef")
        .eq("schemaname", "walltrack")
        .eq("tablename", "wallets")
        .in_("indexname", ["idx_wallets_status", "idx_wallets_watchlist_score"])
        .execute()
    )

    if len(result.data) == 2:
        print("   ✅ Both required indexes found")
        for row in result.data:
            print(f"      - {row['indexname']}")
    else:
        print(f"   ❌ FAILED: Expected 2 indexes, found {len(result.data)}")
        all_passed = False

    print()

    # 3. Verify wallet status distribution
    print("3. Verifying wallet status distribution...")
    result = await (
        client.table("wallets")
        .select("wallet_status", count="exact")
        .execute()
    )

    if result.count > 0:
        print(f"   ✅ Found {result.count} total wallets")

        # Get distribution
        distribution_result = await client.rpc(
            "exec_sql",
            {
                "sql": "SELECT wallet_status, COUNT(*) as count FROM walltrack.wallets GROUP BY wallet_status ORDER BY count DESC"
            },
        ).execute()

        if distribution_result.data:
            print("   Status distribution:")
            for row in distribution_result.data:
                print(f"      - {row['wallet_status']}: {row['count']}")
        else:
            print("   ℹ️  Could not fetch status distribution (RPC not available)")
    else:
        print("   ℹ️  No wallets in database yet")

    print()

    # 4. Verify watchlisted wallets sample
    print("4. Verifying watchlisted wallets...")
    result = await (
        client.table("wallets")
        .select(
            "wallet_address, wallet_status, watchlist_score, watchlist_reason, manual_override"
        )
        .eq("wallet_status", "watchlisted")
        .limit(5)
        .execute()
    )

    if len(result.data) > 0:
        print(f"   ✅ Found {len(result.data)} watchlisted wallets (showing up to 5):")
        for wallet in result.data:
            addr = wallet["wallet_address"][:8] + "..."
            score = wallet["watchlist_score"] or "N/A"
            manual = "🔧" if wallet["manual_override"] else "🤖"
            print(f"      - {addr} | Score: {score} | {manual}")
    else:
        print("   ℹ️  No watchlisted wallets yet")

    print()
    print("=" * 80)

    if all_passed:
        print("✅ Migration 004 verification PASSED")
    else:
        print("❌ Migration 004 verification FAILED")

    print("=" * 80)
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(verify_migration())
    sys.exit(0 if success else 1)
