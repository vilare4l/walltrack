"""Comprehensive E2E tests for Orders Page workflows.

These tests verify actual functionality:
- Orders table display and sorting
- Status/Type/Time filters
- Order statistics cards
- Order details accordion
- Refresh functionality

Run with:
    uv run pytest tests/e2e/gradio/test_orders_workflow.py -m e2e -v --headed
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestOrdersPageLoading:
    """TC-ORD-01: Verify Orders page loads correctly."""

    def test_orders_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders page should load with Orders Management heading."""
        gradio_locators.click_tab("orders")
        expect(dashboard_page).to_have_url("http://localhost:7865/orders")

        heading = dashboard_page.get_by_text("Orders Management")
        expect(heading).to_be_visible()


class TestOrderFilters:
    """TC-ORD-02: Verify order filtering controls."""

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

    def test_status_filter_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status filter dropdown should be clickable."""
        gradio_locators.click_tab("orders")
        status_filter = dashboard_page.get_by_label("Status")
        expect(status_filter).to_be_enabled()
        status_filter.click()
        dashboard_page.wait_for_timeout(300)

    def test_time_range_filter_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Time Range filter dropdown should be clickable."""
        gradio_locators.click_tab("orders")
        time_filter = dashboard_page.get_by_label("Time Range")
        expect(time_filter).to_be_enabled()
        time_filter.click()
        dashboard_page.wait_for_timeout(300)


class TestOrderStatistics:
    """TC-ORD-03: Verify order statistics cards."""

    def test_pending_stat_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Pending orders stat should be visible."""
        gradio_locators.click_tab("orders")
        pending_label = dashboard_page.get_by_text("Pending")
        expect(pending_label.first).to_be_visible()

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

    def test_failed_cancelled_stat_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Failed/Cancelled orders stat should be visible."""
        gradio_locators.click_tab("orders")
        failed = dashboard_page.get_by_text("Failed/Cancelled")
        expect(failed).to_be_visible()


class TestOrdersTable:
    """TC-ORD-04: Verify orders table structure."""

    def test_orders_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders table should be visible."""
        gradio_locators.click_tab("orders")
        orders_caption = dashboard_page.get_by_text("Orders").first
        expect(orders_caption).to_be_visible()

    def test_orders_table_columns(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders table should have correct columns."""
        gradio_locators.click_tab("orders")

        expected_columns = ["ID", "Type", "Token", "Amount (SOL)", "Status", "Attempts", "Created", "Updated"]
        for col_name in expected_columns:
            column = dashboard_page.get_by_role("columnheader").filter(has_text=col_name)
            expect(column.first).to_be_visible()

    def test_orders_table_sortable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Orders table columns should be sortable."""
        gradio_locators.click_tab("orders")

        # ID column should have a sortable button
        id_header = dashboard_page.get_by_role("columnheader").filter(has_text="ID").first
        sort_button = id_header.locator("button.header-button").first
        expect(sort_button).to_be_visible()


class TestOrderActions:
    """TC-ORD-05: Verify order action buttons."""

    def test_refresh_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist."""
        gradio_locators.click_tab("orders")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()

    def test_refresh_button_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should be clickable."""
        gradio_locators.click_tab("orders")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")

        # Click and verify no crash
        refresh_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # Page should still be functional
        expect(refresh_btn).to_be_visible()


class TestOrderDetails:
    """TC-ORD-06: Verify order details accordion."""

    def test_order_details_accordion_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Order Details accordion should exist."""
        gradio_locators.click_tab("orders")
        details_accordion = dashboard_page.get_by_role("button", name="Order Details")
        expect(details_accordion).to_be_visible()

    def test_order_details_accordion_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Order Details accordion should be expandable."""
        gradio_locators.click_tab("orders")
        details_accordion = dashboard_page.get_by_role("button", name="Order Details")

        # Click to expand
        details_accordion.click()
        dashboard_page.wait_for_timeout(500)

        # Should not crash
        expect(details_accordion).to_be_visible()


class TestOrdersSidebar:
    """TC-ORD-07: Verify orders sidebar."""

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
        no_selection = dashboard_page.get_by_role("heading", name="No Selection")
        expect(no_selection).to_be_visible()

    def test_sidebar_instruction(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Sidebar should show instruction text."""
        gradio_locators.click_tab("orders")
        instruction = dashboard_page.get_by_text("Click on any order to view details")
        expect(instruction).to_be_visible()


class TestOrdersWorkflow:
    """TC-ORD-08: Verify complete orders workflow."""

    def test_filter_refresh_cycle(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Test filter and refresh workflow."""
        gradio_locators.click_tab("orders")

        # Verify initial state
        status_filter = dashboard_page.get_by_label("Status")
        expect(status_filter).to_be_visible()

        # Click refresh
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        refresh_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # Page should still be functional
        expect(status_filter).to_be_visible()
        expect(refresh_btn).to_be_visible()
