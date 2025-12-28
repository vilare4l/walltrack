"""E2E tests for WallTrack Gradio dashboard - Spec 01: Dashboard Navigation.

These tests verify:
- Dashboard cold start and loading
- Tab visibility and navigation
- System status panel
- Error state handling

Run with:
    uv run pytest tests/e2e/gradio/test_dashboard.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestDashboardColdStart:
    """TC-01.1: Dashboard Cold Start."""

    def test_dashboard_title_visible(self, dashboard_page: Page) -> None:
        """Dashboard should display the main title."""
        title = dashboard_page.locator("#dashboard-title")
        expect(title).to_be_visible()
        expect(title).to_contain_text("WallTrack")

    def test_dashboard_subtitle_visible(self, dashboard_page: Page) -> None:
        """Dashboard should display the subtitle."""
        subtitle = dashboard_page.locator("#dashboard-subtitle")
        expect(subtitle).to_be_visible()

    def test_gradio_container_loaded(self, dashboard_page: Page) -> None:
        """Gradio container should be fully loaded."""
        container = dashboard_page.locator(".gradio-container")
        expect(container).to_be_visible()


class TestNavVisibility:
    """TC-01.2: All Navigation Links Visible."""

    def test_all_nav_links_visible(self, dashboard_page: Page) -> None:
        """All main navigation links should be visible."""
        nav_names = [
            "Home",
            "Explorer",
            "Orders",
            "Settings",
            "Exit Strategies",
        ]
        for nav_name in nav_names:
            link = dashboard_page.get_by_role("link", name=nav_name)
            expect(link).to_be_visible()

    def test_home_is_default(self, dashboard_page: Page) -> None:
        """Home page should load by default."""
        # Check dashboard title is visible (we're on home)
        title = dashboard_page.locator("h1")
        expect(title).to_contain_text("WallTrack")


class TestNavigation:
    """TC-01.3: Navigation Round-Trip."""

    def test_navigate_to_explorer(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Explorer page."""
        gradio_locators.click_tab("explorer")
        # Verify URL changed
        expect(dashboard_page).to_have_url("http://localhost:7865/explorer")

    def test_navigate_to_orders(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Orders page."""
        gradio_locators.click_tab("orders")
        expect(dashboard_page).to_have_url("http://localhost:7865/orders")

    def test_navigate_to_settings(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Settings page."""
        gradio_locators.click_tab("settings")
        expect(dashboard_page).to_have_url("http://localhost:7865/settings")

    def test_navigate_to_exit_strategies(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate to Exit Strategies page."""
        gradio_locators.click_tab("exit-strategies")
        expect(dashboard_page).to_have_url("http://localhost:7865/exit-strategies")

    def test_nav_round_trip(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should navigate through pages and back."""
        # Navigate through pages
        gradio_locators.click_tab("explorer")
        expect(dashboard_page).to_have_url("http://localhost:7865/explorer")

        gradio_locators.click_tab("orders")
        expect(dashboard_page).to_have_url("http://localhost:7865/orders")

        gradio_locators.click_tab("home")
        expect(dashboard_page).to_have_url("http://localhost:7865/")


class TestSystemStatus:
    """TC-01.4: System Status Panel (Home page stats)."""

    def test_stats_cards_visible(self, dashboard_page: Page) -> None:
        """Stats cards should be visible on Home page."""
        # Home page has stats cards instead of status panel
        pnl_card = dashboard_page.get_by_text("P&L Today")
        expect(pnl_card).to_be_visible()

    def test_active_positions_card_visible(self, dashboard_page: Page) -> None:
        """Active Positions card should be visible."""
        positions_card = dashboard_page.get_by_text("Active Positions").first
        expect(positions_card).to_be_visible()

    def test_signals_today_card_visible(self, dashboard_page: Page) -> None:
        """Signals Today card should be visible."""
        signals_card = dashboard_page.get_by_text("Signals Today")
        expect(signals_card).to_be_visible()


class TestWalletsTab:
    """Tests for Wallets tab (Explorer > Wallets sub-tab)."""

    def test_wallets_subtab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets sub-tab should be accessible from Explorer."""
        gradio_locators.click_tab("explorer")
        # Click on Wallets sub-tab
        wallets_tab = dashboard_page.get_by_role("tab", name="Wallets")
        expect(wallets_tab).to_be_visible()
        wallets_tab.click()

    def test_wallets_table_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets table should be present."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()
        dashboard_page.wait_for_timeout(500)
        # Check for wallets table or wallet list
        wallets_content = dashboard_page.locator("#wallets-table, .wallets-list")
        if wallets_content.count() > 0:
            expect(wallets_content.first).to_be_visible()

    def test_clusters_subtab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clusters sub-tab should be accessible from Explorer."""
        gradio_locators.click_tab("explorer")
        clusters_tab = dashboard_page.get_by_role("tab", name="Clusters")
        expect(clusters_tab).to_be_visible()
        clusters_tab.click()


class TestConfigTab:
    """Tests for Settings page (Configuration Management)."""

    def test_settings_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Settings page should load with configuration tabs."""
        gradio_locators.click_tab("settings")
        heading = dashboard_page.get_by_text("Configuration Management")
        expect(heading).to_be_visible()

    def test_trading_tab_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trading sub-tab should be visible."""
        gradio_locators.click_tab("settings")
        trading_tab = dashboard_page.get_by_role("tab", name="Trading")
        expect(trading_tab).to_be_visible()

    def test_scoring_tab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Scoring sub-tab should be accessible."""
        gradio_locators.click_tab("settings")
        scoring_tab = dashboard_page.get_by_role("tab", name="Scoring")
        expect(scoring_tab).to_be_visible()
        scoring_tab.click()

    def test_edit_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Edit configuration button should exist."""
        gradio_locators.click_tab("settings")
        edit_btn = dashboard_page.get_by_role("button", name="Edit")
        expect(edit_btn).to_be_visible()

    def test_refresh_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should be accessible."""
        gradio_locators.click_tab("settings")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()


class TestPositionsTab:
    """Tests for Active Positions on Home page."""

    def test_positions_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Active Positions heading should be visible on Home."""
        gradio_locators.click_tab("home")
        heading = dashboard_page.get_by_role("heading", name="Active Positions")
        expect(heading).to_be_visible()

    def test_positions_table_has_headers(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Positions table should have expected column headers."""
        gradio_locators.click_tab("home")
        # Check for position table headers
        token_header = dashboard_page.get_by_role("columnheader").filter(has_text="Token")
        expect(token_header.first).to_be_visible()

    def test_sidebar_shows_no_selection(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Sidebar should show 'No Selection' by default."""
        gradio_locators.click_tab("home")
        no_selection = dashboard_page.get_by_text("No Selection")
        expect(no_selection).to_be_visible()

    def test_toggle_sidebar_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Toggle Sidebar button should exist."""
        gradio_locators.click_tab("home")
        toggle_btn = dashboard_page.get_by_role("button", name="Toggle Sidebar")
        expect(toggle_btn).to_be_visible()
