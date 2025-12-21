"""E2E tests for WallTrack Gradio dashboard.

These tests verify the dashboard loads correctly and basic navigation works.
They require the Gradio server to be running on localhost:7860.

Run with:
    uv run pytest tests/e2e -m e2e --headed  # Visual mode
    uv run pytest tests/e2e -m e2e           # Headless mode
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestDashboardLoads:
    """Test that the dashboard loads and displays correctly."""

    def test_dashboard_title_visible(self, dashboard_page: Page) -> None:
        """Dashboard should display the main title."""
        title = dashboard_page.locator("#dashboard-title")
        expect(title).to_be_visible()
        expect(title).to_contain_text("WallTrack Dashboard")

    def test_dashboard_subtitle_visible(self, dashboard_page: Page) -> None:
        """Dashboard should display the subtitle."""
        subtitle = dashboard_page.locator("#dashboard-subtitle")
        expect(subtitle).to_be_visible()
        expect(subtitle).to_contain_text("Solana Memecoin")

    def test_main_tabs_visible(self, dashboard_page: Page) -> None:
        """All main navigation tabs should be visible."""
        tab_names = [
            "Status",
            "Wallets",
            "Clusters",
            "Signals",
            "Positions",
            "Performance",
            "Config",
        ]
        for tab_name in tab_names:
            tab = dashboard_page.get_by_role("tab", name=tab_name)
            expect(tab).to_be_visible()


class TestTabNavigation:
    """Test navigation between dashboard tabs."""

    def test_navigate_to_wallets_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Wallets tab and show wallet components."""
        gradio_locators.click_tab("wallets")

        # Verify wallet components are visible
        expect(gradio_locators.wallets_refresh_btn).to_be_visible()
        expect(gradio_locators.wallets_status_filter).to_be_visible()

    def test_navigate_to_config_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Config tab and show config components."""
        gradio_locators.click_tab("config")

        # Verify config components are visible
        expect(gradio_locators.config_apply_weights_btn).to_be_visible()
        expect(gradio_locators.config_normalize_btn).to_be_visible()

    def test_navigate_to_positions_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Positions tab and show positions components."""
        gradio_locators.click_tab("positions")

        # Verify positions components are visible
        expect(gradio_locators.positions_refresh_btn).to_be_visible()

    def test_tab_round_trip(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate through multiple tabs and back."""
        # Start at status (default)
        gradio_locators.click_tab("wallets")
        expect(gradio_locators.wallets_refresh_btn).to_be_visible()

        gradio_locators.click_tab("config")
        expect(gradio_locators.config_apply_weights_btn).to_be_visible()

        gradio_locators.click_tab("positions")
        expect(gradio_locators.positions_refresh_btn).to_be_visible()

        # Back to wallets
        gradio_locators.click_tab("wallets")
        expect(gradio_locators.wallets_refresh_btn).to_be_visible()


class TestWalletsTab:
    """Test Wallets tab functionality."""

    def test_wallets_table_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets table should be present."""
        gradio_locators.click_tab("wallets")
        expect(gradio_locators.wallets_table).to_be_visible()

    def test_wallets_filter_options(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter should have correct options."""
        gradio_locators.click_tab("wallets")

        # Verify the filter dropdown is visible and clickable
        expect(gradio_locators.wallets_status_filter).to_be_visible()

        # Click to open dropdown - Gradio renders options as listbox items
        gradio_locators.wallets_status_filter.click()

        # Check that a listbox appears with options (Gradio dropdown behavior)
        listbox = dashboard_page.get_by_role("listbox")
        expect(listbox).to_be_visible()

    def test_add_wallet_input_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add wallet input and button should exist."""
        gradio_locators.click_tab("wallets")

        expect(gradio_locators.wallets_add_address_input).to_be_visible()
        expect(gradio_locators.wallets_add_btn).to_be_visible()


class TestConfigTab:
    """Test Config tab functionality."""

    def test_weight_sliders_exist(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """All weight sliders should be present."""
        gradio_locators.click_tab("config")

        sliders = [
            "#config-wallet-weight",
            "#config-cluster-weight",
            "#config-token-weight",
            "#config-context-weight",
        ]
        for slider_id in sliders:
            expect(dashboard_page.locator(slider_id)).to_be_visible()

    def test_threshold_sliders_exist(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Threshold sliders should be accessible."""
        gradio_locators.click_tab("config")

        # Navigate to Trade Threshold sub-tab (use role for unique selection)
        dashboard_page.get_by_role("tab", name="Trade Threshold").click()

        expect(dashboard_page.locator("#config-trade-threshold")).to_be_visible()
        expect(dashboard_page.locator("#config-high-conviction")).to_be_visible()

    def test_reset_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Reset button should be accessible."""
        gradio_locators.click_tab("config")

        # Navigate to Trade Threshold sub-tab where reset button is
        dashboard_page.get_by_role("tab", name="Trade Threshold").click()

        expect(gradio_locators.config_reset_btn).to_be_visible()


class TestPositionsTab:
    """Test Positions tab functionality."""

    def test_positions_table_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Positions table should be present."""
        gradio_locators.click_tab("positions")
        expect(gradio_locators.positions_table).to_be_visible()

    def test_trade_history_tab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trade History sub-tab should be accessible."""
        gradio_locators.click_tab("positions")

        # Click Trade History sub-tab (use role for unique selection)
        dashboard_page.get_by_role("tab", name="Trade History").click()

        expect(gradio_locators.history_table).to_be_visible()

    def test_history_filters_exist(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """History filters should be present."""
        gradio_locators.click_tab("positions")
        dashboard_page.get_by_role("tab", name="Trade History").click()

        expect(dashboard_page.locator("#history-date-from")).to_be_visible()
        expect(dashboard_page.locator("#history-date-to")).to_be_visible()
        expect(dashboard_page.locator("#history-pnl-filter")).to_be_visible()
        expect(dashboard_page.locator("#history-search-btn")).to_be_visible()
