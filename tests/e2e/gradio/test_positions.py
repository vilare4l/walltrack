"""E2E tests for Position Management - Spec 06.

These tests verify:
- Active positions table on Home page
- Position table columns
- Sidebar for position details
- Refresh functionality

Run with:
    uv run pytest tests/e2e/gradio/test_positions.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestPositionsTable:
    """TC-06.1: View Active Positions Table."""

    def test_active_positions_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Active Positions heading should be visible on Home."""
        gradio_locators.click_tab("home")
        heading = dashboard_page.get_by_role("heading", name="Active Positions")
        expect(heading).to_be_visible()

    def test_positions_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Positions table should be visible."""
        gradio_locators.click_tab("home")
        # Check for table by column header
        token_header = dashboard_page.get_by_role("columnheader").filter(has_text="Token")
        expect(token_header.first).to_be_visible()


class TestPositionsTableColumns:
    """TC-06.2: Positions Table has correct columns."""

    def test_token_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Token column should exist."""
        gradio_locators.click_tab("home")
        token_header = dashboard_page.get_by_role("columnheader").filter(has_text="Token")
        expect(token_header.first).to_be_visible()

    def test_entry_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Entry column should exist."""
        gradio_locators.click_tab("home")
        entry_header = dashboard_page.get_by_role("columnheader").filter(has_text="Entry")
        expect(entry_header.first).to_be_visible()

    def test_current_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Current column should exist."""
        gradio_locators.click_tab("home")
        current_header = dashboard_page.get_by_role("columnheader").filter(has_text="Current")
        expect(current_header.first).to_be_visible()

    def test_pnl_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """P&L % column should exist."""
        gradio_locators.click_tab("home")
        pnl_header = dashboard_page.get_by_role("columnheader").filter(has_text="P&L")
        expect(pnl_header.first).to_be_visible()

    def test_strategy_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy column should exist."""
        gradio_locators.click_tab("home")
        strategy_header = dashboard_page.get_by_role("columnheader").filter(has_text="Strategy")
        expect(strategy_header.first).to_be_visible()


class TestPositionsSidebar:
    """TC-06.3: Positions Sidebar."""

    def test_toggle_sidebar_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Toggle Sidebar button should exist."""
        gradio_locators.click_tab("home")
        toggle_btn = dashboard_page.get_by_role("button", name="Toggle Sidebar")
        expect(toggle_btn).to_be_visible()

    def test_sidebar_shows_no_selection(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Sidebar should show 'No Selection' by default."""
        gradio_locators.click_tab("home")
        no_selection = dashboard_page.get_by_text("No Selection")
        expect(no_selection).to_be_visible()

    def test_sidebar_instruction_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Sidebar instruction should be visible."""
        gradio_locators.click_tab("home")
        instruction = dashboard_page.get_by_text("Click on any row to view details")
        expect(instruction).to_be_visible()


class TestHomePageStats:
    """TC-06.4: Home Page Statistics Cards."""

    def test_pnl_today_card_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """P&L Today card should be visible."""
        gradio_locators.click_tab("home")
        pnl_card = dashboard_page.get_by_text("P&L Today")
        expect(pnl_card).to_be_visible()

    def test_active_positions_card_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Active Positions stat card should be visible."""
        gradio_locators.click_tab("home")
        positions_card = dashboard_page.get_by_text("Active Positions").first
        expect(positions_card).to_be_visible()

    def test_signals_today_card_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals Today card should be visible."""
        gradio_locators.click_tab("home")
        signals_card = dashboard_page.get_by_text("Signals Today")
        expect(signals_card).to_be_visible()

    def test_trades_today_card_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trades Today card should be visible."""
        gradio_locators.click_tab("home")
        trades_card = dashboard_page.get_by_text("Trades Today")
        expect(trades_card).to_be_visible()


class TestHomePageActions:
    """TC-06.5: Home Page Actions."""

    def test_refresh_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist on Home page."""
        gradio_locators.click_tab("home")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()


class TestRecentAlerts:
    """TC-06.6: Recent Alerts Section."""

    def test_recent_alerts_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Recent Alerts heading should be visible."""
        gradio_locators.click_tab("home")
        heading = dashboard_page.get_by_role("heading", name="Recent Alerts")
        expect(heading).to_be_visible()
