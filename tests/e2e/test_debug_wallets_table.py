"""
Debug test to inspect Wallets table structure.

Run with: uv run pytest tests/e2e/test_debug_wallets_table.py -v --headed -s
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_inspect_wallets_table(page: Page, base_url: str) -> None:
    """Debug test to see what's in the Wallets table."""
    # Navigate to /dashboard
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # Click Explorer navigation link
    explorer_link = page.get_by_text("Explorer", exact=True).first
    explorer_link.click()
    page.wait_for_timeout(2000)

    # Find and click Wallets accordion
    wallets_accordion = page.get_by_text("Wallets").nth(1)
    wallets_accordion.click()
    page.wait_for_timeout(2000)

    # Get full page content to inspect
    page_content = page.locator("body").inner_text()

    # Check for empty state message
    if "No wallets discovered yet" in page_content:
        print(f"\n{'='*60}")
        print("WARNING: Empty state detected - No wallets UI message")
        print('='*60)

    # Find all tables on the page
    tables = page.locator("table")
    table_count = tables.count()
    print(f"\n{'='*60}")
    print(f"Found {table_count} table(s) on the page")
    print('='*60)

    # Inspect each table
    for i in range(table_count):
        table = tables.nth(i)
        print(f"\nTable {i+1}:")
        print("-" * 60)

        # Get table HTML for inspection
        table_html = table.inner_html()

        # Check for headers
        headers = table.locator("thead th, thead td")
        header_count = headers.count()
        if header_count > 0:
            print(f"  Headers ({header_count}):")
            for j in range(header_count):
                header_text = headers.nth(j).inner_text()
                print(f"    [{j}] {header_text}")
        else:
            print("  No headers found")

        # Check for rows
        rows = table.locator("tbody tr")
        row_count = rows.count()
        print(f"\n  Rows: {row_count}")

        if row_count > 0:
            # Inspect first row in detail
            first_row = rows.first
            cells = first_row.locator("td")
            cell_count = cells.count()
            print(f"  First row cells ({cell_count}):")
            for k in range(cell_count):
                cell_text = cells.nth(k).inner_text()
                print(f"    [{k}] {cell_text[:50]}...")  # First 50 chars

        print()

    # Take a screenshot for visual reference
    page.screenshot(path="test-results/debug-wallets-table.png", full_page=True)
    print(f"\nScreenshot saved: test-results/debug-wallets-table.png")
