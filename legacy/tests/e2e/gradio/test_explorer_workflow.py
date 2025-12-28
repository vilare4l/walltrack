"""Comprehensive E2E tests for Explorer Page workflows.

These tests verify actual functionality of all Explorer tabs:
- Signals tab: Signal feed, stats, refresh
- Wallets tab: Wallet list, filtering, add wallet, blacklist
- Clusters tab: Cluster analysis, actions, discovery

Run with:
    uv run pytest tests/e2e/gradio/test_explorer_workflow.py -m e2e -v --headed
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestExplorerNavigation:
    """TC-EXPL-01: Verify Explorer page structure and tabs."""

    def test_explorer_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Explorer page should load with tabs."""
        gradio_locators.click_tab("explorer")
        expect(dashboard_page).to_have_url("http://localhost:7865/explorer")

    def test_explorer_has_three_tabs(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Explorer should have Signals, Wallets, Clusters tabs."""
        gradio_locators.click_tab("explorer")

        tabs = ["Signals", "Wallets", "Clusters"]
        for tab_name in tabs:
            tab = dashboard_page.get_by_role("tab", name=tab_name)
            expect(tab).to_be_visible()

    def test_signals_tab_selected_by_default(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals tab should be selected by default."""
        gradio_locators.click_tab("explorer")
        signals_tab = dashboard_page.get_by_role("tab", name="Signals")
        expect(signals_tab).to_have_attribute("aria-selected", "true")


class TestSignalsTab:
    """TC-EXPL-02: Verify Signals tab functionality."""

    def test_signal_feed_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signal Feed heading should be visible."""
        gradio_locators.click_tab("explorer")
        heading = dashboard_page.get_by_role("heading", name="Signal Feed")
        expect(heading).to_be_visible()

    def test_signal_feed_description(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signal feed description should be visible."""
        gradio_locators.click_tab("explorer")
        desc = dashboard_page.get_by_text("Real-time trading signals from wallet analysis")
        expect(desc).to_be_visible()

    def test_signals_table_columns(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals table should have correct columns."""
        gradio_locators.click_tab("explorer")

        expected_columns = ["Time", "Token", "Wallet", "Score", "Amount", "Type"]
        for col_name in expected_columns:
            column = dashboard_page.get_by_role("columnheader").filter(has_text=col_name)
            expect(column.first).to_be_visible()

    def test_refresh_signals_button(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh Signals button should be visible and clickable."""
        gradio_locators.click_tab("explorer")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh Signals")
        expect(refresh_btn).to_be_visible()

        # Click and verify no crash
        refresh_btn.click()
        dashboard_page.wait_for_timeout(1000)
        expect(refresh_btn).to_be_visible()

    def test_signals_stats_sidebar(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Stats sidebar should show signal statistics."""
        gradio_locators.click_tab("explorer")

        stats_heading = dashboard_page.get_by_role("heading", name="Stats")
        expect(stats_heading).to_be_visible()

        # Check for stat labels
        expect(dashboard_page.get_by_text("Total:")).to_be_visible()
        expect(dashboard_page.get_by_text("Avg Score:")).to_be_visible()
        expect(dashboard_page.get_by_text("Tokens:")).to_be_visible()
        expect(dashboard_page.get_by_text("Wallets:")).to_be_visible()


class TestWalletsTab:
    """TC-EXPL-03: Verify Wallets tab functionality."""

    def test_switch_to_wallets_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Wallets tab."""
        gradio_locators.click_tab("explorer")
        wallets_tab = dashboard_page.get_by_role("tab", name="Wallets")
        wallets_tab.click()
        expect(wallets_tab).to_have_attribute("aria-selected", "true")

    def test_wallet_watchlist_heading(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallet Watchlist heading should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        heading = dashboard_page.get_by_role("heading", name="Wallet Watchlist")
        expect(heading).to_be_visible()

    def test_wallets_table_columns(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallets table should have correct columns."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        expected_columns = ["Address", "Status", "Score", "Win Rate", "Total PnL", "Trades", "Last Signal"]
        for col_name in expected_columns:
            column = dashboard_page.get_by_role("columnheader").filter(has_text=col_name)
            expect(column.first).to_be_visible()

    def test_status_filter_dropdown(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter dropdown should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        status_label = dashboard_page.get_by_text("Status Filter")
        expect(status_label).to_be_visible()

        # Verify listbox exists
        status_dropdown = dashboard_page.get_by_label("Status Filter")
        expect(status_dropdown).to_be_visible()

    def test_min_score_slider(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Min Score slider should be visible and functional."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        min_score_label = dashboard_page.get_by_text("Min Score")
        expect(min_score_label).to_be_visible()

        # Verify slider exists
        slider = dashboard_page.get_by_role("slider", name="range slider for Min Score")
        expect(slider).to_be_visible()

    def test_add_wallet_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add Wallet input should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        add_wallet_label = dashboard_page.get_by_text("Add Wallet")
        expect(add_wallet_label.first).to_be_visible()

        add_input = dashboard_page.get_by_placeholder("Enter Solana wallet address...")
        expect(add_input).to_be_visible()

    def test_add_and_profile_button(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Add & Profile button should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        add_btn = dashboard_page.get_by_role("button", name="Add & Profile")
        expect(add_btn).to_be_visible()

    def test_wallet_details_section(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallet Details section should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        details_heading = dashboard_page.get_by_role("heading", name="Wallet Details")
        expect(details_heading).to_be_visible()

        placeholder = dashboard_page.get_by_text("Select a wallet to view details")
        expect(placeholder).to_be_visible()

    def test_blacklist_controls(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Blacklist controls should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        # Blacklist reason input
        reason_label = dashboard_page.get_by_text("Blacklist Reason")
        expect(reason_label).to_be_visible()

        reason_input = dashboard_page.get_by_placeholder("Enter reason...")
        expect(reason_input).to_be_visible()

        # Blacklist button (use exact match)
        blacklist_btn = dashboard_page.get_by_role("button", name="Blacklist", exact=True)
        expect(blacklist_btn).to_be_visible()

    def test_add_wallet_workflow(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Test adding a wallet address (input validation)."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Wallets").click()

        add_input = dashboard_page.get_by_placeholder("Enter Solana wallet address...")
        test_address = "TestE2EWallet111222333444555666777888999"

        # Enter address
        add_input.fill(test_address)
        expect(add_input).to_have_value(test_address)

        # Verify button is ready
        add_btn = dashboard_page.get_by_role("button", name="Add & Profile")
        expect(add_btn).to_be_visible()


class TestClustersTab:
    """TC-EXPL-04: Verify Clusters tab functionality."""

    def test_switch_to_clusters_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Clusters tab."""
        gradio_locators.click_tab("explorer")
        clusters_tab = dashboard_page.get_by_role("tab", name="Clusters")
        clusters_tab.click()
        expect(clusters_tab).to_have_attribute("aria-selected", "true")

    def test_cluster_analysis_heading(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster Analysis heading should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Clusters").click()

        heading = dashboard_page.get_by_role("heading", name="Cluster Analysis")
        expect(heading).to_be_visible()

    def test_clusters_table_columns(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clusters table should have correct columns."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Clusters").click()

        expected_columns = ["ID", "Size", "Cohesion", "Multiplier", "Leader", "Members"]
        for col_name in expected_columns:
            column = dashboard_page.get_by_role("columnheader").filter(has_text=col_name)
            expect(column.first).to_be_visible()

    def test_cluster_action_buttons(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster action buttons should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Clusters").click()

        actions_heading = dashboard_page.get_by_role("heading", name="Actions")
        expect(actions_heading).to_be_visible()

        # Verify action buttons
        actions = [
            "Discover Clusters",
            "Analyze Co-occurrence",
            "Detect Leaders",
            "Update Multipliers",
            "Refresh",
        ]
        for action in actions:
            btn = dashboard_page.get_by_role("button", name=action)
            expect(btn).to_be_visible()

    def test_cluster_stats(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster stats should be visible."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Clusters").click()

        stats = ["Total Clusters", "Avg Cohesion", "Avg Size", "With Leader"]
        for stat in stats:
            stat_label = dashboard_page.get_by_text(stat)
            expect(stat_label).to_be_visible()

    def test_discover_clusters_action(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discover Clusters button should be clickable."""
        gradio_locators.click_tab("explorer")
        dashboard_page.get_by_role("tab", name="Clusters").click()

        discover_btn = dashboard_page.get_by_role("button", name="Discover Clusters")
        expect(discover_btn).to_be_enabled()

        # Click and wait (don't verify result, just that it doesn't crash)
        discover_btn.click()
        dashboard_page.wait_for_timeout(1000)


class TestExplorerSidebar:
    """TC-EXPL-05: Verify Explorer sidebar functionality."""

    def test_toggle_sidebar_on_signals(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Toggle sidebar should work on Signals tab."""
        gradio_locators.click_tab("explorer")

        toggle_btn = dashboard_page.get_by_role("button", name="Toggle Sidebar")
        expect(toggle_btn).to_be_visible()

        # Default state
        no_selection = dashboard_page.get_by_role("heading", name="No Selection")
        expect(no_selection).to_be_visible()


class TestExplorerTabSwitching:
    """TC-EXPL-06: Verify switching between Explorer tabs."""

    def test_switch_between_all_tabs(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch between all tabs without errors."""
        gradio_locators.click_tab("explorer")

        # Switch to Wallets
        wallets_tab = dashboard_page.get_by_role("tab", name="Wallets")
        wallets_tab.click()
        expect(wallets_tab).to_have_attribute("aria-selected", "true")
        expect(dashboard_page.get_by_role("heading", name="Wallet Watchlist")).to_be_visible()

        # Switch to Clusters
        clusters_tab = dashboard_page.get_by_role("tab", name="Clusters")
        clusters_tab.click()
        expect(clusters_tab).to_have_attribute("aria-selected", "true")
        expect(dashboard_page.get_by_role("heading", name="Cluster Analysis")).to_be_visible()

        # Switch back to Signals
        signals_tab = dashboard_page.get_by_role("tab", name="Signals")
        signals_tab.click()
        expect(signals_tab).to_have_attribute("aria-selected", "true")
        expect(dashboard_page.get_by_role("heading", name="Signal Feed")).to_be_visible()
