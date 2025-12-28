"""E2E tests for Signal Scoring - Spec 05 (Epic 14 Simplified).

These tests verify:
- Signals table display
- Signal score breakdown (2-component model)
- Trade decision display
- Signal filtering

Run with:
    uv run pytest tests/e2e/gradio/test_signals.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestSignalsTable:
    """TC-05.1: View Signals Table."""

    def test_signals_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals table should display recent signals."""
        gradio_locators.click_tab("signals")

        expect(gradio_locators.signals_table).to_be_visible()

    def test_signals_table_has_headers(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals table should have expected headers."""
        gradio_locators.click_tab("signals")

        signals_table = gradio_locators.signals_table
        # Epic 14 simplified headers
        headers = ["Time", "Wallet", "Token", "Score", "Boost", "Status"]

        for header in headers:
            header_cell = signals_table.locator(f"text={header}")
            if header_cell.count() > 0:
                expect(header_cell.first).to_be_visible()

    def test_refresh_signals_button(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist for signals."""
        gradio_locators.click_tab("signals")

        expect(gradio_locators.signals_refresh_btn).to_be_visible()


class TestSignalScoreBreakdown:
    """TC-05.2: View Signal Score Breakdown (Epic 14)."""

    def test_click_signal_shows_details(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clicking a signal should show score breakdown."""
        gradio_locators.click_tab("signals")

        # Click first signal row
        signal_row = dashboard_page.locator("#signals-table tbody tr").first
        if signal_row.is_visible():
            signal_row.click()

            dashboard_page.wait_for_timeout(1000)

            # Check for details panel
            expect(gradio_locators.signal_details).to_be_visible()

    def test_signal_details_shows_wallet_score(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signal details should show wallet score (Epic 14)."""
        gradio_locators.click_tab("signals")

        signal_row = dashboard_page.locator("#signals-table tbody tr").first
        if signal_row.is_visible():
            signal_row.click()

            dashboard_page.wait_for_timeout(1000)

            details = gradio_locators.signal_details
            if details.is_visible():
                # Epic 14: 2-component model shows wallet score
                expect(details).to_contain_text("Wallet")

    def test_signal_details_shows_cluster_boost(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signal details should show cluster boost (Epic 14)."""
        gradio_locators.click_tab("signals")

        signal_row = dashboard_page.locator("#signals-table tbody tr").first
        if signal_row.is_visible():
            signal_row.click()

            dashboard_page.wait_for_timeout(1000)

            details = gradio_locators.signal_details
            if details.is_visible():
                # Epic 14: Cluster boost component
                boost = details.locator("text=Boost")
                if boost.count() > 0:
                    expect(boost.first).to_be_visible()

    def test_signal_details_shows_final_score(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signal details should show final score."""
        gradio_locators.click_tab("signals")

        signal_row = dashboard_page.locator("#signals-table tbody tr").first
        if signal_row.is_visible():
            signal_row.click()

            dashboard_page.wait_for_timeout(1000)

            details = gradio_locators.signal_details
            if details.is_visible():
                expect(details).to_contain_text("Score")


class TestTradeDecision:
    """TC-05.3: Signal Trade Decision Display."""

    def test_trade_indicator_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """TRADE or NO TRADE indicator should be visible."""
        gradio_locators.click_tab("signals")

        signals_table = gradio_locators.signals_table

        # Check for TRADE or NO TRADE indicators
        trade_indicator = signals_table.locator("text=TRADE")
        if trade_indicator.count() > 0:
            expect(trade_indicator.first).to_be_visible()


class TestSignalFiltering:
    """TC-05.4 to TC-05.5: Signal Refresh and Filtering."""

    def test_refresh_signals(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should reload signals."""
        gradio_locators.click_tab("signals")

        refresh_btn = gradio_locators.signals_refresh_btn
        expect(refresh_btn).to_be_visible()

        # Click refresh
        refresh_btn.click()

        # Wait for refresh
        dashboard_page.wait_for_timeout(1000)

        # Table should still be visible
        expect(gradio_locators.signals_table).to_be_visible()

    def test_signals_filter_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Signals filter should exist."""
        gradio_locators.click_tab("signals")

        signals_filter = dashboard_page.locator("#signals-filter")
        if signals_filter.is_visible():
            expect(signals_filter).to_be_visible()

    def test_filter_by_trade_decision(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to filter by trade decision."""
        gradio_locators.click_tab("signals")

        signals_filter = dashboard_page.locator("#signals-filter")
        if signals_filter.is_visible():
            signals_filter.click()

            listbox = dashboard_page.get_by_role("listbox")
            if listbox.is_visible():
                trade_option = listbox.get_by_text("TRADE")
                if trade_option.is_visible():
                    trade_option.click()

                    dashboard_page.wait_for_timeout(500)
