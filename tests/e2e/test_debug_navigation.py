"""Debug test to find available navigation links."""

import sys
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pytest
from playwright.sync_api import Page


@pytest.mark.e2e
def test_find_navigation_links(page: Page, base_url: str) -> None:
    """Find all navigation links on dashboard."""
    page.goto(base_url, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # Get all links
    links = page.locator("a, button")
    link_count = links.count()

    print(f"\n{'='*60}")
    print(f"Found {link_count} links/buttons on page")
    print('='*60)

    # Show first 20 links
    for i in range(min(link_count, 20)):
        try:
            link = links.nth(i)
            text = link.inner_text()
            if text and text.strip():
                print(f"[{i}] {text[:50]}")
        except Exception:
            pass

    # Look specifically for navigation-related text
    body_text = page.locator("body").inner_text()
    print(f"\n{'='*60}")
    print("Looking for config/settings related text:")
    print('='*60)

    keywords = ["Config", "Settings", "Configuration", "Criteria", "Watchlist"]
    for keyword in keywords:
        if keyword in body_text:
            print(f"✓ Found: {keyword}")
        else:
            print(f"✗ Not found: {keyword}")
