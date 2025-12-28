"""E2E tests for Order Management - Spec 07.

These tests verify:
- Orders page display
- Order filtering by status and type
- Order table with correct columns
- Refresh functionality
- Order details sidebar

Run with:
    uv run pytest tests/e2e/gradio/test_orders.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestOrdersPage:
    """TC-07.1: View Orders Page."""

    def test_orders_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders page should load with Orders Management heading."""
        gradio_locators.click_tab("orders")
        heading = dashboard_page.get_by_text("Orders Management")
        expect(heading).to_be_visible()

    def test_orders_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders table should be visible."""
        gradio_locators.click_tab("orders")
        # Look for the Orders table caption
        orders_table = dashboard_page.get_by_text("Orders").first
        expect(orders_table).to_be_visible()


class TestOrdersTableColumns:
    """TC-07.2: Orders Table has correct columns."""

    def test_id_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """ID column should exist."""
        gradio_locators.click_tab("orders")
        id_header = dashboard_page.get_by_role("columnheader").filter(has_text="ID")
        expect(id_header.first).to_be_visible()

    def test_type_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Type column should exist."""
        gradio_locators.click_tab("orders")
        type_header = dashboard_page.get_by_role("columnheader").filter(has_text="Type")
        expect(type_header.first).to_be_visible()

    def test_token_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Token column should exist."""
        gradio_locators.click_tab("orders")
        token_header = dashboard_page.get_by_role("columnheader").filter(has_text="Token")
        expect(token_header.first).to_be_visible()

    def test_status_column_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status column should exist."""
        gradio_locators.click_tab("orders")
        status_header = dashboard_page.get_by_role("columnheader").filter(has_text="Status")
        expect(status_header.first).to_be_visible()


class TestOrderFiltering:
    """TC-07.3: Order Filtering."""

    def test_status_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter dropdown should exist."""
        gradio_locators.click_tab("orders")
        status_filter = dashboard_page.get_by_label("Status")
        expect(status_filter).to_be_visible()

    def test_type_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Type filter dropdown should exist."""
        gradio_locators.click_tab("orders")
        type_filter = dashboard_page.get_by_label("Type")
        expect(type_filter).to_be_visible()

    def test_time_range_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Time Range filter dropdown should exist."""
        gradio_locators.click_tab("orders")
        time_filter = dashboard_page.get_by_label("Time Range")
        expect(time_filter).to_be_visible()


class TestOrderStats:
    """TC-07.4: Order Statistics."""

    def test_pending_stat_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Pending orders stat should be visible."""
        gradio_locators.click_tab("orders")
        pending = dashboard_page.get_by_text("Pending")
        expect(pending.first).to_be_visible()

    def test_submitted_stat_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Submitted orders stat should be visible."""
        gradio_locators.click_tab("orders")
        submitted = dashboard_page.get_by_text("Submitted")
        expect(submitted).to_be_visible()

    def test_filled_stat_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Filled orders stat should be visible."""
        gradio_locators.click_tab("orders")
        filled = dashboard_page.get_by_text("Filled")
        expect(filled).to_be_visible()


class TestOrderActions:
    """TC-07.5: Order Actions."""

    def test_refresh_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist."""
        gradio_locators.click_tab("orders")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()

    def test_order_details_accordion_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Order Details accordion should exist."""
        gradio_locators.click_tab("orders")
        details = dashboard_page.get_by_text("Order Details")
        expect(details).to_be_visible()


class TestOrdersSidebar:
    """TC-07.6: Orders Sidebar."""

    def test_toggle_sidebar_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Toggle Sidebar button should exist."""
        gradio_locators.click_tab("orders")
        toggle_btn = dashboard_page.get_by_role("button", name="Toggle Sidebar")
        expect(toggle_btn).to_be_visible()

    def test_sidebar_shows_no_selection(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Sidebar should show 'No Selection' by default."""
        gradio_locators.click_tab("orders")
        no_selection = dashboard_page.get_by_text("No Selection")
        expect(no_selection).to_be_visible()
