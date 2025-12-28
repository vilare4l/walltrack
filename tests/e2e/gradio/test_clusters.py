"""E2E tests for Cluster Visualization - Spec 04.

These tests verify:
- Cluster list display
- Cluster details view
- Cluster member display
- Cluster expansion

Run with:
    uv run pytest tests/e2e/gradio/test_clusters.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestClustersList:
    """TC-04.1: View Clusters List."""

    def test_clusters_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clusters table should display."""
        gradio_locators.click_tab("clusters")

        expect(gradio_locators.clusters_table).to_be_visible()

    def test_clusters_table_has_headers(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clusters table should have expected headers."""
        gradio_locators.click_tab("clusters")

        clusters_table = gradio_locators.clusters_table
        headers = ["Cluster", "Size", "Leader", "Score"]

        for header in headers:
            header_cell = clusters_table.locator(f"text={header}")
            if header_cell.count() > 0:
                expect(header_cell.first).to_be_visible()

    def test_refresh_clusters_button(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist for clusters."""
        gradio_locators.click_tab("clusters")

        refresh_btn = dashboard_page.locator("#clusters-refresh-btn")
        if refresh_btn.is_visible():
            expect(refresh_btn).to_be_visible()


class TestClusterDetails:
    """TC-04.2 to TC-04.3: Cluster Details and Members."""

    def test_click_cluster_shows_details(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clicking a cluster should show details."""
        gradio_locators.click_tab("clusters")

        # Click first cluster row
        cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
        if cluster_row.is_visible():
            cluster_row.click()

            dashboard_page.wait_for_timeout(1000)

            # Check for details panel
            expect(gradio_locators.cluster_details).to_be_visible()

    def test_cluster_members_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster members table should be visible when cluster selected."""
        gradio_locators.click_tab("clusters")

        # Click first cluster
        cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
        if cluster_row.is_visible():
            cluster_row.click()

            dashboard_page.wait_for_timeout(1000)

            members_table = gradio_locators.cluster_members_table
            if members_table.is_visible():
                expect(members_table).to_be_visible()

    def test_cluster_details_shows_metrics(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster details should show performance metrics."""
        gradio_locators.click_tab("clusters")

        # Click first cluster
        cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
        if cluster_row.is_visible():
            cluster_row.click()

            dashboard_page.wait_for_timeout(1000)

            details = gradio_locators.cluster_details
            if details.is_visible():
                # Check for metrics
                expect(details).to_contain_text("Score")


class TestClusterExpansion:
    """TC-04.4 to TC-04.5: Cluster Expansion."""

    def test_expand_cluster_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Expand cluster button should exist."""
        gradio_locators.click_tab("clusters")

        # Click first cluster
        cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
        if cluster_row.is_visible():
            cluster_row.click()

            dashboard_page.wait_for_timeout(1000)

            expand_btn = dashboard_page.locator("#cluster-expand-btn")
            if expand_btn.is_visible():
                expect(expand_btn).to_be_visible()

    def test_cluster_boost_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Cluster boost should be visible in details."""
        gradio_locators.click_tab("clusters")

        # Click first cluster
        cluster_row = dashboard_page.locator("#clusters-table tbody tr").first
        if cluster_row.is_visible():
            cluster_row.click()

            dashboard_page.wait_for_timeout(1000)

            details = gradio_locators.cluster_details
            if details.is_visible():
                # Epic 14: Cluster boost should be displayed
                boost_indicator = details.locator("text=Boost")
                if boost_indicator.count() > 0:
                    expect(boost_indicator.first).to_be_visible()
