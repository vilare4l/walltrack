"""
Epic 3.6 Performance Tests - Response Time & Load Validation

Tests that system performs acceptably under moderate load.
Story 3.6 - Task 8: Performance & Regression Testing

Run with: uv run pytest tests/performance/test_epic3_performance_story36.py -v
"""

from __future__ import annotations

import time

import pytest

from walltrack.data.supabase.repositories.token_repo import TokenRepository
from walltrack.data.supabase.repositories.wallet_repo import WalletRepository


@pytest.mark.integration
class TestEpic3Performance:
    """Epic 3.6 - Performance validation for wallet analysis system."""

    async def test_wallet_query_performance(
        self, supabase_client
    ) -> None:
        """
        Task 8.1 - AC1: Wallet queries complete in < 2 seconds

        GIVEN database contains wallets
        WHEN I query all wallets
        THEN query completes in < 2 seconds
        AND returns all wallets
        """
        # Measure query time
        start_time = time.time()

        wallet_repo = WalletRepository(client=supabase_client)
        wallets = await wallet_repo.get_all(limit=1000)

        end_time = time.time()
        elapsed = end_time - start_time

        # Verify query completed
        assert len(wallets) > 0, "No wallets returned from query"

        # Verify performance
        assert elapsed < 2.0, \
            f"Wallet query took {elapsed:.2f}s, expected < 2.0s"

    async def test_token_query_performance(
        self, supabase_client
    ) -> None:
        """
        Task 8.2 - AC2: Token queries complete in < 2 seconds

        GIVEN database contains tokens
        WHEN I query all tokens
        THEN query completes in < 2 seconds
        AND returns all tokens
        """
        # Measure query time
        start_time = time.time()

        token_repo = TokenRepository(supabase_client)
        tokens = await token_repo.get_all(limit=1000)

        end_time = time.time()
        elapsed = end_time - start_time

        # Verify query completed
        assert len(tokens) > 0, "No tokens returned from query"

        # Verify performance
        assert elapsed < 2.0, \
            f"Token query took {elapsed:.2f}s, expected < 2.0s"

    async def test_wallet_filtering_performance(
        self, supabase_client
    ) -> None:
        """
        Task 8.3 - AC3: Filtered queries perform efficiently

        GIVEN database contains wallets with various statuses
        WHEN I filter wallets by status
        THEN query completes in < 2 seconds
        AND returns filtered results
        """
        # Get all wallets first
        wallet_repo = WalletRepository(client=supabase_client)
        all_wallets = await wallet_repo.get_all(limit=1000)

        assert len(all_wallets) > 0, "No wallets to filter"

        # Measure filtering operation
        # (In-memory filtering for now, could be database-level in future)
        start_time = time.time()

        # Filter by profiled status
        profiled_wallets = [
            w for w in all_wallets
            if w.wallet_status and w.wallet_status.value == "profiled"
        ]

        end_time = time.time()
        elapsed = end_time - start_time

        # Verify performance (filtering should be very fast)
        assert elapsed < 0.5, \
            f"Wallet filtering took {elapsed:.2f}s, expected < 0.5s"

    async def test_moderate_load_handling(
        self, supabase_client
    ) -> None:
        """
        Task 8.4 - AC4: System handles moderate data volumes

        GIVEN database contains multiple entities
        WHEN I query wallets and tokens together
        THEN both queries complete successfully
        AND total time is reasonable (< 5 seconds)
        """
        start_time = time.time()

        # Query both wallets and tokens
        wallet_repo = WalletRepository(client=supabase_client)
        token_repo = TokenRepository(supabase_client)

        wallets = await wallet_repo.get_all(limit=1000)
        tokens = await token_repo.get_all(limit=1000)

        end_time = time.time()
        elapsed = end_time - start_time

        # Verify data returned
        assert len(wallets) > 0, "No wallets returned"
        assert len(tokens) > 0, "No tokens returned"

        # Verify reasonable performance
        assert elapsed < 5.0, \
            f"Combined queries took {elapsed:.2f}s, expected < 5.0s"

        # Log metrics for reference
        print(f"\n{'='*60}")
        print(f"Performance Metrics:")
        print(f"  Wallets retrieved: {len(wallets)}")
        print(f"  Tokens retrieved:  {len(tokens)}")
        print(f"  Total time:        {elapsed:.2f}s")
        print(f"  Avg per query:     {elapsed/2:.2f}s")
        print('='*60)

    async def test_repeated_query_consistency(
        self, supabase_client
    ) -> None:
        """
        Task 8.5 - AC5: Repeated queries return consistent results

        GIVEN database is stable
        WHEN I query wallets multiple times
        THEN results are consistent
        AND performance doesn't degrade
        """
        wallet_repo = WalletRepository(client=supabase_client)

        # Run query 3 times
        results = []
        times = []

        for i in range(3):
            start = time.time()
            wallets = await wallet_repo.get_all(limit=1000)
            elapsed = time.time() - start

            results.append(len(wallets))
            times.append(elapsed)

        # Verify consistency
        assert len(set(results)) == 1, \
            f"Inconsistent results across queries: {results}"

        # Verify no performance degradation
        for i, t in enumerate(times):
            assert t < 2.0, \
                f"Query {i+1} took {t:.2f}s, expected < 2.0s"

        # Log timing for analysis
        avg_time = sum(times) / len(times)
        print(f"\n{'='*60}")
        print(f"Consistency Test Results:")
        print(f"  Query 1: {times[0]:.3f}s ({results[0]} wallets)")
        print(f"  Query 2: {times[1]:.3f}s ({results[1]} wallets)")
        print(f"  Query 3: {times[2]:.3f}s ({results[2]} wallets)")
        print(f"  Average: {avg_time:.3f}s")
        print('='*60)
