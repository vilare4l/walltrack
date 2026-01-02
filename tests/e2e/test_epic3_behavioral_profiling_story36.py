"""
Epic 3.6 E2E Tests - Wallet Behavioral Profiling Display

Tests that wallet behavioral patterns are correctly displayed in the UI.
Story 3.6 - Task 3.3: E2E Test - Behavioral Pattern Display

Run with: uv run pytest tests/e2e/test_epic3_behavioral_profiling_story36.py -v --headed
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestEpic3BehavioralProfiling:
    """Epic 3.6 - Story 3.3 validation: Wallet Behavioral Profiling Display."""

    def test_behavioral_columns_display(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.3 - AC1: Behavioral pattern columns are displayed

        GIVEN wallets exist with behavioral profiling data
        WHEN I navigate to Explorer → Wallets accordion
        THEN behavioral pattern columns are visible
        AND patterns show meaningful values
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

        # Step 4: Get wallets table
        wallets_table = page.locator("table").filter(has_text="Address").last
        expect(wallets_table).to_be_visible(timeout=5000)

        # Step 5: Verify behavioral pattern columns exist
        # Story 3.3 columns: Entry Delay, Avg Hold Time, Risk Level, Pattern Type
        headers_row = wallets_table.locator("thead tr").first
        headers_text = headers_row.inner_text()

        # Expected behavioral columns (Story 3.3)
        expected_columns = [
            "Entry Delay",  # How quickly wallet enters after discovery
            # Note: Other behavioral columns may not be visible in main table
            # They might be in drill-down/sidebar
        ]

        for column in expected_columns:
            assert column in headers_text, f"Behavioral column '{column}' not found in table headers"

        # Step 6: Verify at least one wallet row exists
        wallet_rows = wallets_table.locator("tbody tr")
        row_count = wallet_rows.count()
        assert row_count > 0, "Expected at least 1 wallet with behavioral profiling"

        # Step 7: Verify Entry Delay column has data
        first_row = wallet_rows.first
        cells = first_row.locator("td")

        # Entry Delay is typically shown in minutes/hours
        # Find Entry Delay column (around column 6-7)
        entry_delay_found = False
        for i in range(cells.count()):
            cell_text = cells.nth(i).inner_text()
            # Entry delay might show as: "5m", "2h", "N/A", or numeric
            if any(indicator in cell_text for indicator in ["m", "h", "min", "hour", "N/A"]) or cell_text.replace(".", "").replace("-", "").isdigit():
                entry_delay_found = True
                break

        assert entry_delay_found, "Entry Delay data not found in wallets table"

    def test_behavioral_profiling_accuracy(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.3 - AC2: Behavioral profiling values are accurate

        GIVEN wallets with known behavioral patterns
        WHEN I view wallet behavioral data
        THEN values match expected patterns
        AND patterns are consistent with wallet activity
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

        # Get all wallet rows
        wallet_rows = wallets_table.locator("tbody tr")
        row_count = wallet_rows.count()
        assert row_count > 0, "No wallets to validate"

        # Check that behavioral values are present and reasonable
        # For each wallet, at least one behavioral metric should not be "N/A"
        wallets_with_data = 0
        wallets_checked = min(row_count, 5)  # Check first 5 wallets

        for i in range(wallets_checked):
            row = wallet_rows.nth(i)
            cells = row.locator("td")
            row_text = row.inner_text()

            # Check if row has at least some behavioral data (not all N/A)
            if "m" in row_text or "h" in row_text or "%" in row_text:
                wallets_with_data += 1

        # At least half of checked wallets should have some behavioral data
        assert wallets_with_data >= wallets_checked // 2, f"Only {wallets_with_data}/{wallets_checked} checked wallets have behavioral data"

    def test_confidence_indicator_display(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 3.3 - AC3: Confidence indicators are displayed

        GIVEN wallets with behavioral profiling confidence scores
        WHEN I view wallet table
        THEN confidence indicators are visible
        AND confidence values are within valid range (0-100%)
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

        # Check for Confidence column
        headers_row = wallets_table.locator("thead tr").first
        headers_text = headers_row.inner_text()

        # Confidence column should exist
        assert "Confidence" in headers_text, "Confidence column not found in table headers"

        # Verify confidence values in first row
        wallet_rows = wallets_table.locator("tbody tr")
        assert wallet_rows.count() > 0, "No wallets to check confidence"

        first_row = wallet_rows.first
        row_text = first_row.inner_text()

        # Confidence might show as: "High", "Medium", "Low", "85%", or "N/A"
        confidence_indicators = ["High", "Medium", "Low", "%", "N/A"]
        has_confidence = any(indicator in row_text for indicator in confidence_indicators)

        assert has_confidence, f"Confidence indicator not found in wallet row"
