"""
Debug test to inspect Explorer page structure.

Run with: uv run pytest tests/e2e/test_explorer_navigation.py -v --headed -s
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_explore_page_structure(page: Page, base_url: str) -> None:
    """Debug test to see what's on the Explorer page."""
    # Try different URL patterns
    urls_to_try = [
        base_url,  # /dashboard
        base_url + "/explorer",  # /dashboard/explorer
        base_url.replace("/dashboard", "/explorer"),  # /explorer
    ]

    for url in urls_to_try:
        print(f"\n{'='*60}")
        print(f"Trying URL: {url}")
        print('='*60)

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=10000)
            page.wait_for_timeout(3000)

            # Get page title
            title = page.title()
            print(f"Page title: {title}")

            # Get page HTML structure
            body = page.locator("body")
            html = body.inner_html()

            # Check for key markers
            print(f"\nContent markers:")
            print(f"  - Contains 'Explorer': {'Explorer' in html}")
            print(f"  - Contains 'Tokens': {'Tokens' in html}")
            print(f"  - Contains 'Wallets': {'Wallets' in html}")
            print(f"  - Contains 'accordion': {'accordion' in html.lower()}")

            # Try to find Wallets text
            wallets_text = page.get_by_text("Wallets", exact=False)
            if wallets_text.count() > 0:
                print(f"\n  Found {wallets_text.count()} element(s) containing 'Wallets'")

                # Print first occurrence details
                first = wallets_text.first
                print(f"  First match tag: {first.evaluate('el => el.tagName')}")
                print(f"  First match role: {first.evaluate('el => el.getAttribute(\"role\")')}")
                print(f"  First match class: {first.evaluate('el => el.className')}")

        except Exception as e:
            print(f"  ✗ Failed: {e}")


@pytest.mark.e2e
def test_find_wallets_accordion(page: Page, base_url: str) -> None:
    """Try different selectors to find Wallets accordion."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)

    selectors_to_try = [
        ('text="Wallets"', 'Simple text match'),
        ('button:has-text("Wallets")', 'Button with text'),
        ('[role="button"]:has-text("Wallets")', 'Button role with text'),
        ('//button[contains(text(), "Wallets")]', 'XPath button'),
        ('.label-wrap:has-text("Wallets")', 'Label wrap class'),
    ]

    print(f"\n{'='*60}")
    print("Testing selectors:")
    print('='*60)

    for selector, description in selectors_to_try:
        try:
            element = page.locator(selector)
            count = element.count()
            print(f"\n{description}")
            print(f"  Selector: {selector}")
            print(f"  Found: {count} element(s)")

            if count > 0:
                first = element.first
                is_visible = first.is_visible()
                print(f"  Visible: {is_visible}")
                if is_visible:
                    print(f"  ✓ SUCCESS - This selector works!")
        except Exception as e:
            print(f"  ✗ Failed: {e}")
