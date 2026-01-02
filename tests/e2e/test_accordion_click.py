"""
Debug test to find the correct selector for Wallets accordion.

Run with: uv run pytest tests/e2e/test_accordion_click.py -v --headed -s
"""

from __future__ import annotations

import sys

# Fix Windows encoding issue
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_find_wallets_accordion_selector(page: Page, base_url: str) -> None:
    """Try different strategies to open the Wallets accordion."""
    # Navigate to Explorer
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    explorer_link = page.get_by_text("Explorer", exact=True).first
    explorer_link.click()
    page.wait_for_timeout(2000)

    print(f"\n{'='*60}")
    print("Testing different selectors for Wallets accordion:")
    print('='*60)

    # Strategy 1: Text locator with different nth() values
    wallets_text_elements = page.get_by_text("Wallets", exact=False)
    count = wallets_text_elements.count()
    print(f"\n1. Text 'Wallets' found {count} times")

    for i in range(count):
        elem = wallets_text_elements.nth(i)
        tag = elem.evaluate("el => el.tagName")
        parent_tag = elem.evaluate("el => el.parentElement?.tagName")
        classes = elem.evaluate("el => el.className")
        print(f"   [{i}] Tag: {tag}, Parent: {parent_tag}, Classes: {classes[:50] if classes else 'none'}")

    # Strategy 2: Look for accordion wrapper
    print(f"\n2. Looking for accordion containers...")
    accordions = page.locator(".accordion, [data-accordion], .svelte-accordion")
    acc_count = accordions.count()
    print(f"   Found {acc_count} accordion containers")

    # Strategy 3: Look for clickable labels
    print(f"\n3. Looking for label elements...")
    labels = page.locator("label, .label, .label-wrap")
    label_count = labels.count()
    print(f"   Found {label_count} label elements")

    # Filter labels that contain "Wallets"
    for i in range(label_count):
        label = labels.nth(i)
        text = label.inner_text()
        if "Wallets" in text:
            classes = label.evaluate("el => el.className")
            print(f"   Label with 'Wallets': {text[:30]}, Classes: {classes[:50] if classes else 'none'}")

    # Strategy 4: Try clicking different Wallets elements and check result
    print(f"\n4. Testing click on different 'Wallets' elements...")

    for i in range(min(count, 5)):  # Test first 5 occurrences
        print(f"\n   Testing click on Wallets[{i}]...")

        # Take a "before" screenshot
        page.screenshot(path=f"test-results/before-click-{i}.png")

        # Click the element
        try:
            wallets_text_elements.nth(i).click(timeout=5000)
            page.wait_for_timeout(1000)

            # Take an "after" screenshot
            page.screenshot(path=f"test-results/after-click-{i}.png")

            # Check if wallets table is now visible
            wallets_table = page.locator("table").filter(has_text="Address")
            if wallets_table.count() > 0:
                print(f"   ✓ SUCCESS! Wallets table appeared after clicking element [{i}]")
                break
            else:
                # Check if any new table appeared
                all_tables = page.locator("table")
                table_count = all_tables.count()
                print(f"   Tables visible: {table_count}")

                if table_count > 2:  # More than the 2 Token tables
                    # Check what headers the new table has
                    for j in range(table_count):
                        headers = all_tables.nth(j).locator("thead th, thead td")
                        if headers.count() > 0:
                            first_header = headers.first.inner_text()
                            print(f"      Table {j} first header: {first_header}")

        except Exception as e:
            print(f"   ✗ Click failed: {e}")

    # Final screenshot
    page.screenshot(path="test-results/final-accordion-test.png", full_page=True)
    print(f"\nScreenshots saved to test-results/")
