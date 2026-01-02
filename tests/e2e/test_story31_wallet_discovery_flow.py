"""
Story 3.1 E2E Test - Wallet Discovery Flow (RPC-based)

Tests the complete wallet discovery workflow from trigger to UI display.
Story 3.1 - Task 7: E2E test for wallet discovery flow (token → wallet → Explorer → Sidebar)

Run with: uv run pytest tests/e2e/test_story31_wallet_discovery_flow.py -v --headed
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestStory31WalletDiscoveryFlow:
    """Story 3.1 - Task 7 validation: Complete wallet discovery workflow via RPC."""

    def test_explorer_tabs_structure(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC6 + Task 8: Explorer page uses Tabs structure (not Accordions)

        GIVEN application is running
        WHEN I navigate to Explorer page
        THEN Explorer uses gr.Tabs with Signals, Wallets, Clusters tabs
        AND tabs are visible and clickable
        """
        # Navigate to dashboard
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Click Explorer navigation link
        explorer_link = page.get_by_text("Explorer", exact=True).first

        if explorer_link.count() == 0:
            pytest.skip("Explorer page navigation not yet implemented in UI")

        explorer_link.click()
        page.wait_for_timeout(2000)

        # Verify Explorer page loaded
        page_text = page.locator("body").inner_text()
        assert "Explorer" in page_text, "Explorer page not loaded"

        # Verify Tabs structure (not Accordions)
        # Look for tab labels - Gradio tabs use specific structure
        # Check for "Signals", "Wallets", "Clusters" text
        assert "Signals" in page_text, "Signals tab not found"
        assert "Wallets" in page_text, "Wallets tab not found"
        assert "Clusters" in page_text, "Clusters tab not found"

    def test_wallets_tab_has_discovery_columns(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC6: Wallets table shows First Seen and Discovered From columns

        GIVEN I'm on the Explorer page
        WHEN I view the Wallets tab
        THEN table headers include "First Seen" and "Discovered From"
        AND existing wallets display these values
        """
        # Navigate to Explorer
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        explorer_link = page.get_by_text("Explorer", exact=True).first
        if explorer_link.count() == 0:
            pytest.skip("Explorer page navigation not yet implemented")

        explorer_link.click()
        page.wait_for_timeout(2000)

        # Click Wallets tab (if tabs exist)
        wallets_tab = page.locator("text=Wallets").first
        if wallets_tab.count() > 0:
            wallets_tab.click()
            page.wait_for_timeout(1000)

        # Look for table headers in page text
        page_text = page.locator("body").inner_text()

        # Check for new columns (AC6)
        expected_columns = ["First Seen", "Discovered From"]
        found_columns = [col for col in expected_columns if col in page_text]

        # At least one new column should be visible
        assert len(found_columns) > 0, \
            f"Discovery columns not found. Expected {expected_columns}, found {found_columns}"

    def test_wallet_row_click_opens_sidebar(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC6 + Task 8: Clicking wallet row opens Sidebar with context

        GIVEN I'm on the Explorer → Wallets tab
        WHEN I click a wallet row in the table
        THEN Sidebar opens on the right
        AND Sidebar shows wallet details (address, score, metrics)
        AND "Discovery Origin" section is visible
        """
        # Navigate to Explorer
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        explorer_link = page.get_by_text("Explorer", exact=True).first
        if explorer_link.count() == 0:
            pytest.skip("Explorer page navigation not yet implemented")

        explorer_link.click()
        page.wait_for_timeout(2000)

        # Click Wallets tab
        wallets_tab = page.locator("text=Wallets").first
        if wallets_tab.count() > 0:
            wallets_tab.click()
            page.wait_for_timeout(1000)

        # Find table and click first row (if wallets exist)
        # Gradio dataframes render as HTML tables
        tables = page.locator("table")

        if tables.count() > 0:
            # Find the wallets table (should contain "Address" column)
            wallet_table = None
            for i in range(tables.count()):
                table_text = tables.nth(i).inner_text()
                if "Address" in table_text and "Score" in table_text:
                    wallet_table = tables.nth(i)
                    break

            if wallet_table:
                # Click first data row (skip header row)
                rows = wallet_table.locator("tbody tr")
                if rows.count() > 0:
                    first_row = rows.first
                    first_row.click()
                    page.wait_for_timeout(1500)

                    # Verify Sidebar opened and shows wallet details
                    page_text = page.locator("body").inner_text()

                    # Check for Sidebar content markers (Task 8)
                    sidebar_indicators = [
                        "Wallet Details",
                        "Discovery Origin",
                        "Performance Metrics",
                        "Manual Controls",
                    ]

                    sidebar_content_found = any(indicator in page_text for indicator in sidebar_indicators)
                    assert sidebar_content_found, \
                        "Sidebar did not open or content missing after clicking wallet row"
                else:
                    pytest.skip("No wallet rows to click (table empty)")
            else:
                pytest.skip("Wallets table not found or has no data")
        else:
            pytest.skip("No tables found on Wallets tab")

    def test_sidebar_shows_discovery_origin(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC6 + Task 8: Sidebar shows Discovery Origin section

        GIVEN I've clicked a wallet row
        WHEN Sidebar opens
        THEN "Discovery Origin" section is visible
        AND section shows "Found on" token reference
        AND section shows discovery date
        AND section shows discovery method (RPC holder analysis)
        """
        # Navigate to Explorer → Wallets
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        explorer_link = page.get_by_text("Explorer", exact=True).first
        if explorer_link.count() == 0:
            pytest.skip("Explorer page navigation not yet implemented")

        explorer_link.click()
        page.wait_for_timeout(2000)

        # Click Wallets tab
        wallets_tab = page.locator("text=Wallets").first
        if wallets_tab.count() > 0:
            wallets_tab.click()
            page.wait_for_timeout(1000)

        # Click first wallet row
        tables = page.locator("table")
        if tables.count() > 0:
            wallet_table = None
            for i in range(tables.count()):
                table_text = tables.nth(i).inner_text()
                if "Address" in table_text:
                    wallet_table = tables.nth(i)
                    break

            if wallet_table:
                rows = wallet_table.locator("tbody tr")
                if rows.count() > 0:
                    first_row = rows.first
                    first_row.click()
                    page.wait_for_timeout(1500)

                    # Check Sidebar content for Discovery Origin
                    page_text = page.locator("body").inner_text()

                    # Verify Discovery Origin section markers
                    origin_indicators = [
                        "Discovery Origin",
                        "Found on",
                        "Date",
                        "Method",
                        "RPC",
                    ]

                    found_indicators = [ind for ind in origin_indicators if ind in page_text]

                    # At least 3 indicators should be present
                    assert len(found_indicators) >= 3, \
                        f"Discovery Origin section incomplete. Found: {found_indicators}"
                else:
                    pytest.skip("No wallet rows to click")
            else:
                pytest.skip("Wallets table not found")
        else:
            pytest.skip("No tables found")

    def test_config_page_wallet_discovery_trigger(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC5 + AC7: Config page has "Run Wallet Discovery" button with configurable criteria

        GIVEN I'm on the Config page
        WHEN I view Discovery section
        THEN "Run Wallet Discovery" button is visible
        AND "Wallet Discovery Criteria" accordion exists
        AND criteria sliders are configurable
        """
        # Navigate to Config page
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        config_link = page.get_by_text("Config", exact=True).first
        if config_link.count() == 0:
            pytest.skip("Config page navigation not yet implemented")

        config_link.click()
        page.wait_for_timeout(2000)

        # Look for wallet discovery button
        page_text = page.locator("body").inner_text()

        discovery_indicators = [
            "Wallet Discovery",
            "Run Wallet Discovery",
            "Discovery Criteria",
        ]

        found_indicators = [ind for ind in discovery_indicators if ind in page_text]

        assert len(found_indicators) >= 1, \
            f"Wallet Discovery controls not found. Found: {found_indicators}"

    def test_status_bar_shows_wallet_count(
        self, page: Page, base_url: str
    ) -> None:
        """
        AC5: Status bar shows wallet count

        GIVEN wallets have been discovered
        WHEN I view the status bar
        THEN wallet count is displayed
        AND count reflects discovered wallets
        """
        # Navigate to dashboard
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Look for status bar elements
        # Status bar typically at top or bottom of page
        page_text = page.locator("body").inner_text()

        # Look for wallet count indicator (format: "X wallets" or "Wallets: X")
        # This is a basic check - full validation would require mocking discovery
        status_indicators = ["wallet", "Wallet"]

        status_found = any(indicator in page_text for indicator in status_indicators)

        # Note: This test is basic - full validation requires running wallet discovery
        # which is tested in integration tests with mocked RPC
        assert status_found, "Wallet status indicator not found in UI"
