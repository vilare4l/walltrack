"""E2E tests for Token Discovery - Spec 02.

NOTE: Discovery is currently not exposed in the UI.
The Discovery component exists but is not integrated into Explorer tabs.
These tests are skipped until Discovery is added to the UI.

Run with:
    uv run pytest tests/e2e/gradio/test_discovery.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skip(reason="Discovery tab not implemented in current UI. Explorer has: Signals, Wallets, Clusters only.")
]


class TestTokenDiscovery:
    """TC-02.1 to TC-02.3: Token Discovery Flow."""

    def test_discovery_tab_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discovery tab should load with input field."""
        gradio_locators.click_tab("discovery")
        expect(gradio_locators.discovery_token_input).to_be_visible()
        expect(gradio_locators.discovery_scan_btn).to_be_visible()

    def test_enter_token_address(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to enter a token address."""
        gradio_locators.click_tab("discovery")

        # Enter token address
        token_input = gradio_locators.discovery_token_input
        token_input.fill("TestTokenMintAddress123456789")

        # Verify input value
        expect(token_input).to_have_value("TestTokenMintAddress123456789")

    def test_scan_button_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Scan button should be clickable after entering token."""
        gradio_locators.click_tab("discovery")

        token_input = gradio_locators.discovery_token_input
        token_input.fill("TestTokenMintAddress123456789")

        scan_btn = gradio_locators.discovery_scan_btn
        expect(scan_btn).to_be_enabled()

    def test_invalid_token_shows_error(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Invalid token should show error message."""
        gradio_locators.click_tab("discovery")

        # Enter invalid token
        token_input = gradio_locators.discovery_token_input
        token_input.fill("INVALID_TOKEN_12345")

        scan_btn = gradio_locators.discovery_scan_btn
        scan_btn.click()

        # Wait for error message
        dashboard_page.wait_for_timeout(2000)


class TestWalletExtraction:
    """TC-02.4 to TC-02.5: Wallet Extraction from Discovery."""

    def test_discovery_results_container_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discovery results container should exist."""
        gradio_locators.click_tab("discovery")
        expect(gradio_locators.discovery_results).to_be_visible()

    def test_discovery_wallets_table_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discovered wallets table should be present."""
        gradio_locators.click_tab("discovery")

        # The wallets table may be empty initially
        wallets_table = gradio_locators.discovery_wallets_table
        expect(wallets_table).to_be_visible()

    def test_add_to_watchlist_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add to watchlist button should exist."""
        gradio_locators.click_tab("discovery")

        add_btn = dashboard_page.locator("#discovery-add-to-watchlist")
        if add_btn.is_visible():
            expect(add_btn).to_be_visible()


class TestDiscoveryFilters:
    """Tests for discovery filtering options."""

    def test_early_window_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Early window filter should be accessible."""
        gradio_locators.click_tab("discovery")

        early_window = dashboard_page.locator("#discovery-early-window")
        if early_window.is_visible():
            expect(early_window).to_be_visible()

    def test_min_profit_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Minimum profit filter should be accessible."""
        gradio_locators.click_tab("discovery")

        min_profit = dashboard_page.locator("#discovery-min-profit")
        if min_profit.is_visible():
            expect(min_profit).to_be_visible()
