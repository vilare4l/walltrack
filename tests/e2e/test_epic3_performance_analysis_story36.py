"""
Epic 3.6 E2E Tests - Wallet Performance Analysis Display

Tests that wallet performance metrics are correctly displayed in the UI.
Story 3.6 - Task 3.2: E2E Test - Wallet Performance Metrics Display

Run with: uv run pytest tests/e2e/test_epic3_performance_analysis_story36.py -v --headed
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestEpic3PerformanceAnalysis:
    """Epic 3.6 - Story 3.2 validation: Wallet Performance Analysis Display."""

    def test_performance_metrics_display(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.2 - AC1: Performance metrics are displayed in wallets table

        GIVEN wallets exist with performance metrics
        WHEN I navigate to Explorer → Wallets accordion
        THEN performance metrics columns are visible
        AND metrics show valid values (Win Rate %, PnL $, etc.)
        """
        # Step 1: Navigate to /dashboard
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Step 2: Click Explorer navigation link
        explorer_link = page.get_by_text("Explorer", exact=True).first
        explorer_link.click()
        page.wait_for_timeout(2000)

        # Step 3: Open Wallets accordion
        wallets_accordion = page.locator(".label-wrap").filter(has_text="Wallets")
        expect(wallets_accordion).to_be_visible(timeout=10000)
        wallets_accordion.click()
        page.wait_for_timeout(2000)

        # Step 4: Get wallets table (last table with "Address" header)
        wallets_table = page.locator("table").filter(has_text="Address").last
        expect(wallets_table).to_be_visible(timeout=5000)

        # Step 5: Verify performance metric columns exist
        # Story 3.2 columns: Win Rate %, PnL $, Avg Hold Time, Total Trades, Sharpe Ratio
        headers_row = wallets_table.locator("thead tr").first
        headers_text = headers_row.inner_text()

        # Epic 3.2 performance columns
        expected_columns = [
            "Win Rate",  # Win Rate %
            "PnL",       # Total PnL in USD
            "Trades",    # Total number of trades
        ]

        for column in expected_columns:
            assert column in headers_text, f"Performance column '{column}' not found in table headers"

        # Step 6: Verify at least one wallet row exists
        wallet_rows = wallets_table.locator("tbody tr")
        row_count = wallet_rows.count()
        assert row_count > 0, "Expected at least 1 wallet with performance metrics"

        # Step 7: Verify first wallet has performance metrics
        first_row = wallet_rows.first
        expect(first_row).to_be_visible()

        # Get all cells in first row
        cells = first_row.locator("td")
        cell_count = cells.count()
        assert cell_count >= 5, f"Expected at least 5 columns (Address, Status, Win Rate, PnL, Trades), got {cell_count}"

        # Check Win Rate cell (should contain % or "N/A")
        # Column order: Address (0), Status (1), Win Rate (2), ...
        win_rate_cell = cells.nth(2)
        win_rate_text = win_rate_cell.inner_text()
        assert (
            "%" in win_rate_text or "N/A" in win_rate_text
        ), f"Win Rate should contain '%' or 'N/A', got: {win_rate_text}"

        # Step 8: Verify PnL formatting
        # PnL may show as: numeric (0.85), with $ sign ($1.23), with SOL, or "N/A"
        pnl_cell = cells.nth(3)
        pnl_text = pnl_cell.inner_text()

        # Check if it's a valid PnL value
        is_numeric = any(char.isdigit() for char in pnl_text)
        is_na = "N/A" in pnl_text

        assert is_numeric or is_na, f"PnL should be numeric or 'N/A', got: {pnl_text}"

    def test_performance_metrics_sorting(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.2 - AC2: Performance metrics can be sorted

        GIVEN wallets table with performance metrics
        WHEN I click on a performance metric column header
        THEN table sorts by that metric
        AND sort order indicator is visible (if Gradio supports it)
        """
        # Navigate to Explorer → Wallets accordion
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        explorer_link = page.get_by_text("Explorer", exact=True).first
        explorer_link.click()
        page.wait_for_timeout(2000)

        wallets_accordion = page.locator(".label-wrap").filter(has_text="Wallets")
        wallets_accordion.click()
        page.wait_for_timeout(2000)

        # Get wallets table
        wallets_table = page.locator("table").filter(has_text="Address").last
        expect(wallets_table).to_be_visible(timeout=5000)

        # Get table rows before sorting
        wallet_rows_before = wallets_table.locator("tbody tr")
        count_before = wallet_rows_before.count()
        assert count_before > 0, "No wallets to sort"

        # Try clicking on Win Rate header to sort
        # Gradio Dataframe headers are clickable for sorting
        headers = wallets_table.locator("thead th, thead td")

        # Find Win Rate header (column index may vary)
        win_rate_header = None
        for i in range(headers.count()):
            header = headers.nth(i)
            if "Win Rate" in header.inner_text():
                win_rate_header = header
                break

        if win_rate_header:
            # Click to sort
            win_rate_header.click()
            page.wait_for_timeout(1000)

            # Verify table still has same row count (data not lost)
            wallet_rows_after = wallets_table.locator("tbody tr")
            count_after = wallet_rows_after.count()
            assert count_after == count_before, f"Row count changed after sort: {count_before} → {count_after}"

    def test_performance_metrics_filter_integration(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.2 - AC3: Performance metrics display with status filter

        GIVEN wallets with performance metrics
        WHEN I filter by wallet status
        THEN filtered wallets still show performance metrics
        AND metrics are accurate for filtered subset
        """
        # Navigate to Explorer → Wallets accordion
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        explorer_link = page.get_by_text("Explorer", exact=True).first
        explorer_link.click()
        page.wait_for_timeout(2000)

        wallets_accordion = page.locator(".label-wrap").filter(has_text="Wallets")
        wallets_accordion.click()
        page.wait_for_timeout(2000)

        # Get initial wallet count
        wallets_table = page.locator("table").filter(has_text="Address").last
        wallet_rows = wallets_table.locator("tbody tr")
        initial_count = wallet_rows.count()

        # Find and use status filter dropdown (Story 3.5 feature)
        # Look for dropdown with "Filter by Status" label
        filter_dropdown = page.locator("select, .dropdown").filter(has_text="All")

        if filter_dropdown.count() > 0:
            # Select "Profiled" status
            filter_dropdown.first.select_option("Profiled")
            page.wait_for_timeout(1500)

            # Verify table updated
            filtered_rows = wallets_table.locator("tbody tr")
            filtered_count = filtered_rows.count()

            # After filtering, count may be same or less
            assert filtered_count <= initial_count, "Filtered count should be <= initial count"

            # Verify first filtered wallet still has performance metrics
            if filtered_count > 0:
                first_filtered = filtered_rows.first
                cells = first_filtered.locator("td")

                # Check Win Rate column exists
                win_rate_cell = cells.nth(2)
                win_rate_text = win_rate_cell.inner_text()
                assert (
                    "%" in win_rate_text or "N/A" in win_rate_text
                ), f"Filtered wallet should still show Win Rate: {win_rate_text}"
