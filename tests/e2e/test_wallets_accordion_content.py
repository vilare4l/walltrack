"""
Debug test to see what's inside the Wallets accordion after opening.

Run with: uv run pytest tests/e2e/test_wallets_accordion_content.py -v --headed -s
"""

from __future__ import annotations

import sys

# Fix Windows encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_wallets_accordion_content(page: Page, base_url: str) -> None:
    """See what's displayed inside Wallets accordion."""
    # Navigate to Explorer
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    explorer_link = page.get_by_text("Explorer", exact=True).first
    explorer_link.click()
    page.wait_for_timeout(2000)

    # Take "before" screenshot
    page.screenshot(path="test-results/before-wallets-open.png", full_page=True)

    # Click Wallets accordion using label-wrap
    wallets_accordion = page.locator(".label-wrap").filter(has_text="Wallets")
    wallets_accordion.click()
    page.wait_for_timeout(3000)  # Longer wait to ensure rendering

    # Take "after" screenshot
    page.screenshot(path="test-results/after-wallets-open.png", full_page=True)

    # Get all content
    body_text = page.locator("body").inner_text()

    print(f"\n{'='*60}")
    print("Checking for content markers:")
    print('='*60)

    # Check for empty state
    if "No wallets discovered yet" in body_text:
        print("✗ FOUND: Empty state message - No wallets")
        print("\n  This means:")
        print("  - Wallets accordion opened successfully")
        print("  - But _fetch_wallets() returned empty list")
        print("  - Need to check WalletRepository.get_all() in Supabase")

    # Check for wallets table headers
    if "Address" in body_text and "Status" in body_text:
        print("✓ FOUND: Wallets table headers (Address, Status)")

        # Count tables
        tables = page.locator("table")
        table_count = tables.count()
        print(f"\nTables on page: {table_count}")

        # Find the wallets table
        for i in range(table_count):
            table = tables.nth(i)
            headers = table.locator("thead th, thead td")
            if headers.count() > 0:
                first_header = headers.first.inner_text()
                print(f"  Table {i+1} first header: {first_header}")

                if first_header == "Address":
                    print(f"    → This is the Wallets table!")

                    # Count rows
                    rows = table.locator("tbody tr")
                    row_count = rows.count()
                    print(f"    → Rows: {row_count}")

                    if row_count > 0:
                        # Show first row
                        first_row = rows.first
                        cells = first_row.locator("td")
                        cell_count = cells.count()
                        print(f"    → First row cells: {cell_count}")

                        for j in range(min(3, cell_count)):  # First 3 cells
                            cell_text = cells.nth(j).inner_text()
                            print(f"        Cell {j}: {cell_text[:40]}...")

    # Check for filter dropdown (Story 3.5 feature)
    if "Filter by Status" in body_text:
        print("\n✓ FOUND: Status filter dropdown")

    # Check for analyze button (Story 3.2 feature)
    if "Analyze All Wallets" in body_text:
        print("✓ FOUND: Analyze All Wallets button")

    print(f"\nScreenshots saved to test-results/")
