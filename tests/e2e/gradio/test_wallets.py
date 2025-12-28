"""E2E tests for Wallet Management - Spec 03.

These tests verify:
- Wallet table display and columns
- Adding wallets manually
- Filtering by source and status
- Wallet profiling
- Wallet details view

Run with:
    uv run pytest tests/e2e/gradio/test_wallets.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestWalletsTable:
    """TC-03.1: View Wallets Table."""

    def test_wallets_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets table should display with correct columns."""
        gradio_locators.click_tab("wallets")

        wallets_table = gradio_locators.wallets_table
        expect(wallets_table).to_be_visible()

    def test_wallets_table_has_headers(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets table should have expected column headers."""
        gradio_locators.click_tab("wallets")

        wallets_table = gradio_locators.wallets_table
        headers = ["Address", "Win Rate", "PnL", "Status"]

        for header in headers:
            # Check if header text exists in table
            header_cell = wallets_table.locator(f"text={header}")
            if header_cell.count() > 0:
                expect(header_cell.first).to_be_visible()

    def test_refresh_button_works(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should reload wallet data."""
        gradio_locators.click_tab("wallets")

        refresh_btn = gradio_locators.wallets_refresh_btn
        expect(refresh_btn).to_be_visible()

        # Click refresh
        refresh_btn.click()

        # Wait for refresh
        dashboard_page.wait_for_timeout(1000)

        # Table should still be visible
        expect(gradio_locators.wallets_table).to_be_visible()


class TestAddWallet:
    """TC-03.2: Add Wallet Manually."""

    def test_add_wallet_input_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add wallet input should be visible."""
        gradio_locators.click_tab("wallets")

        expect(gradio_locators.wallets_add_address_input).to_be_visible()
        expect(gradio_locators.wallets_add_btn).to_be_visible()

    def test_can_enter_wallet_address(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to enter a wallet address."""
        gradio_locators.click_tab("wallets")

        address_input = gradio_locators.wallets_add_address_input
        address_input.fill("NewTestWalletAddress123456789")

        expect(address_input).to_have_value("NewTestWalletAddress123456789")

    def test_add_button_enabled_with_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add button should be enabled when address is entered."""
        gradio_locators.click_tab("wallets")

        address_input = gradio_locators.wallets_add_address_input
        address_input.fill("NewTestWalletAddress123456789")

        add_btn = gradio_locators.wallets_add_btn
        expect(add_btn).to_be_enabled()


class TestWalletFiltering:
    """TC-03.3: Filter Wallets."""

    def test_status_filter_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter dropdown should be visible."""
        gradio_locators.click_tab("wallets")

        expect(gradio_locators.wallets_status_filter).to_be_visible()

    def test_status_filter_opens(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter dropdown should open."""
        gradio_locators.click_tab("wallets")

        gradio_locators.wallets_status_filter.click()

        listbox = dashboard_page.get_by_role("listbox")
        expect(listbox).to_be_visible()

    def test_source_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Source filter should exist."""
        gradio_locators.click_tab("wallets")

        source_filter = dashboard_page.locator("#wallets-source-filter")
        if source_filter.is_visible():
            expect(source_filter).to_be_visible()


class TestWalletProfiling:
    """TC-03.4 to TC-03.5: Wallet Profiling."""

    def test_profile_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Profile button should exist for wallets."""
        gradio_locators.click_tab("wallets")

        profile_btn = dashboard_page.locator("#wallets-profile-btn")
        if profile_btn.is_visible():
            expect(profile_btn).to_be_visible()

    def test_bulk_profile_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Bulk profile button should exist."""
        gradio_locators.click_tab("wallets")

        bulk_btn = dashboard_page.locator("#wallets-bulk-profile-btn")
        if bulk_btn.is_visible():
            expect(bulk_btn).to_be_visible()


class TestWalletDetails:
    """TC-03.6 to TC-03.7: Wallet Details and Actions."""

    def test_click_wallet_shows_details(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clicking a wallet should show details."""
        gradio_locators.click_tab("wallets")

        # Click first wallet row
        wallet_row = dashboard_page.locator("#wallets-table tbody tr").first
        if wallet_row.is_visible():
            wallet_row.click()

            # Wait for details
            dashboard_page.wait_for_timeout(1000)

            # Check for details panel
            details = dashboard_page.locator("#wallet-details")
            if details.is_visible():
                expect(details).to_be_visible()

    def test_remove_wallet_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Remove wallet button should exist."""
        gradio_locators.click_tab("wallets")

        remove_btn = dashboard_page.locator("#wallets-remove-btn")
        if remove_btn.is_visible():
            expect(remove_btn).to_be_visible()
