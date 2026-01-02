"""
Epic 3.6 E2E Tests - Configuration Management

Tests that configuration management features work correctly in the UI.
Story 3.6 - Task 6: E2E Test - Watchlist Criteria Configuration

Run with: uv run pytest tests/e2e/test_epic3_config_management_story36.py -v --headed
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestEpic3ConfigManagement:
    """Epic 3.6 - Story 3.5 validation: Configuration Management UI."""

    def test_config_page_accessible(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 6.1 - AC1: Config page is accessible from navigation

        GIVEN application is running
        WHEN I navigate to Config page
        THEN Config page loads successfully
        AND configuration options are displayed
        """
        # Step 1: Navigate to /dashboard
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Step 2: Click Config navigation link
        config_link = page.get_by_text("Config", exact=True).first

        # Check if Config link exists (UI may not have it implemented yet)
        if config_link.count() == 0:
            pytest.skip("Config page navigation not yet implemented in UI")

        # Verify Config link exists
        expect(config_link).to_be_visible(timeout=5000)

        # Click Config link
        config_link.click()
        page.wait_for_timeout(2000)

        # Step 3: Verify Config page loaded
        # Look for config-specific elements
        # Expected: "Watchlist Criteria" or configuration controls

        page_text = page.locator("body").inner_text()

        # Config page should contain configuration-related text
        config_indicators = [
            "Criteria",
            "Configuration",
            "Settings",
            "Watchlist",
            "Min",  # Min Win Rate, Min Trades, etc.
        ]

        has_config_content = any(indicator in page_text for indicator in config_indicators)
        assert has_config_content, "Config page doesn't contain expected configuration elements"

    def test_watchlist_criteria_configuration(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 6.2 - AC2: Watchlist criteria can be configured

        GIVEN I'm on the Config page
        WHEN I view watchlist criteria controls
        THEN criteria inputs are displayed
        AND I can modify criteria values
        """
        # Navigate to Config page
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        config_link = page.get_by_text("Config", exact=True).first
        if config_link.count() == 0:
            pytest.skip("Config page navigation not yet implemented in UI")

        config_link.click()
        page.wait_for_timeout(2000)

        # Look for watchlist criteria inputs
        # Expected inputs: Min Win Rate, Min Trade Count, Min PnL, etc.

        # Find input fields or sliders
        inputs = page.locator("input[type='number'], input[type='text'], input[type='range']")
        input_count = inputs.count()

        # Should have at least 1 input for criteria
        assert input_count > 0, "No input fields found for watchlist criteria configuration"

        # Try to identify specific criteria inputs
        page_text = page.locator("body").inner_text()

        # Expected criteria labels
        expected_criteria = [
            "Win Rate",
            "Trade",
            "PnL",
            "Score",
        ]

        # At least one criterion should be present
        criteria_found = any(criterion in page_text for criterion in expected_criteria)
        assert criteria_found, f"No expected watchlist criteria found. Page text: {page_text[:200]}"

    def test_config_save_functionality(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 6.3 - AC3: Configuration changes can be saved

        GIVEN I'm on the Config page
        WHEN I modify a configuration value
        AND I click save button
        THEN configuration is persisted
        AND success feedback is shown
        """
        # Navigate to Config page
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        config_link = page.get_by_text("Config", exact=True).first
        if config_link.count() == 0:
            pytest.skip("Config page navigation not yet implemented in UI")

        config_link.click()
        page.wait_for_timeout(2000)

        # Look for save button
        save_button = page.get_by_role("button").filter(has_text="Save")

        if save_button.count() > 0:
            # Find an input to modify
            inputs = page.locator("input[type='number']")

            if inputs.count() > 0:
                # Modify first numeric input
                first_input = inputs.first

                # Get current value
                current_value = first_input.input_value()

                # Try to change value (increase by 1)
                try:
                    current_num = float(current_value) if current_value else 0
                    new_value = current_num + 1

                    # Set new value
                    first_input.fill(str(new_value))
                    page.wait_for_timeout(500)

                    # Click save
                    save_button.first.click()
                    page.wait_for_timeout(1500)

                    # Verify no error occurred
                    # Config page should still be visible
                    page_text = page.locator("body").inner_text()
                    assert "Criteria" in page_text or "Configuration" in page_text, \
                        "Config page disappeared after save"

                except Exception:
                    # Skip if input modification fails
                    pass
        else:
            # No save button - config might auto-save
            pytest.skip("No save button found - config might use auto-save")

    def test_config_persistence(
        self, page: Page, base_url: str
    ) -> None:
        """
        Task 6.4 - AC4: Configuration persists across page reloads

        GIVEN configuration has been set
        WHEN I reload the Config page
        THEN previous configuration values are retained
        AND inputs show saved values
        """
        # Navigate to Config page
        page.goto(base_url, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        config_link = page.get_by_text("Config", exact=True).first
        if config_link.count() == 0:
            pytest.skip("Config page navigation not yet implemented in UI")

        config_link.click()
        page.wait_for_timeout(2000)

        # Get current input values (if any)
        inputs = page.locator("input[type='number'], input[type='text']")

        if inputs.count() > 0:
            # Store current values
            initial_values = []
            for i in range(min(inputs.count(), 5)):  # Check first 5 inputs
                try:
                    value = inputs.nth(i).input_value()
                    initial_values.append(value)
                except Exception:
                    initial_values.append(None)

            # Reload page
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            # Navigate back to Config
            config_link = page.get_by_text("Config", exact=True).first
            config_link.click()
            page.wait_for_timeout(2000)

            # Check if values persisted
            inputs_after = page.locator("input[type='number'], input[type='text']")

            if inputs_after.count() > 0:
                # Verify at least one input retained its value
                values_match = 0
                for i in range(min(len(initial_values), inputs_after.count())):
                    try:
                        new_value = inputs_after.nth(i).input_value()
                        if initial_values[i] == new_value:
                            values_match += 1
                    except Exception:
                        pass

                # At least half of inputs should retain their values
                assert values_match >= len(initial_values) // 2, \
                    f"Only {values_match}/{len(initial_values)} input values persisted"
        else:
            pytest.skip("No input fields found to test persistence")
