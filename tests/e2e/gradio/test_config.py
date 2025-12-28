"""E2E tests for Configuration Panel - Spec 08 (Epic 14 Simplified).

These tests verify:
- Settings page with multiple configuration tabs
- Trading, Scoring, Discovery, Cluster, Risk, Exit, API configuration
- Edit and Refresh functionality
- Version control status display

Run with:
    uv run pytest tests/e2e/gradio/test_config.py -m e2e -v
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestSettingsPage:
    """TC-08.1: View Settings Page."""

    def test_settings_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Settings page should load with Configuration Management heading."""
        gradio_locators.click_tab("settings")
        heading = dashboard_page.get_by_text("Configuration Management")
        expect(heading).to_be_visible()

    def test_all_config_tabs_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """All configuration tabs should be visible."""
        gradio_locators.click_tab("settings")
        tabs = ["Trading", "Scoring", "Discovery", "Cluster", "Risk", "Exit", "API"]
        for tab_name in tabs:
            tab = dashboard_page.get_by_role("tab", name=tab_name)
            expect(tab).to_be_visible()


class TestTradingConfig:
    """TC-08.2: Trading Configuration Tab."""

    def test_trading_tab_selected_by_default(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trading tab should be selected by default."""
        gradio_locators.click_tab("settings")
        trading_tab = dashboard_page.get_by_role("tab", name="Trading")
        expect(trading_tab).to_have_attribute("aria-selected", "true")

    def test_position_sizing_section_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Position Sizing section should be visible."""
        gradio_locators.click_tab("settings")
        heading = dashboard_page.get_by_role("heading", name="Position Sizing")
        expect(heading).to_be_visible()

    def test_thresholds_section_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Thresholds section should be visible."""
        gradio_locators.click_tab("settings")
        heading = dashboard_page.get_by_role("heading", name="Thresholds")
        expect(heading).to_be_visible()

    def test_limits_section_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Limits section should be visible."""
        gradio_locators.click_tab("settings")
        heading = dashboard_page.get_by_role("heading", name="Limits", exact=True)
        expect(heading).to_be_visible()


class TestScoringConfig:
    """TC-08.3: Scoring Configuration Tab."""

    def test_scoring_tab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Scoring tab should be accessible."""
        gradio_locators.click_tab("settings")
        scoring_tab = dashboard_page.get_by_role("tab", name="Scoring")
        scoring_tab.click()
        expect(scoring_tab).to_have_attribute("aria-selected", "true")

    def test_score_weights_section_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Score Weights section should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Scoring").click()
        heading = dashboard_page.get_by_role("heading", name="Score Weights")
        expect(heading).to_be_visible()

    def test_wallet_scoring_section_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Wallet Scoring section should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Scoring").click()
        heading = dashboard_page.get_by_role("heading", name="Wallet Scoring")
        expect(heading).to_be_visible()

    def test_scoring_weights_fields_exist(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Scoring weight fields should exist."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Scoring").click()

        # Check for weight labels
        wallet_weight = dashboard_page.get_by_text("Wallet Weight")
        cluster_weight = dashboard_page.get_by_text("Cluster Weight")
        expect(wallet_weight).to_be_visible()
        expect(cluster_weight).to_be_visible()


class TestConfigActions:
    """TC-08.4: Edit and Refresh Configuration."""

    def test_edit_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Edit button should exist."""
        gradio_locators.click_tab("settings")
        edit_btn = dashboard_page.get_by_role("button", name="Edit")
        expect(edit_btn).to_be_visible()

    def test_refresh_button_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should exist."""
        gradio_locators.click_tab("settings")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()

    def test_status_field_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Status field should exist showing config state."""
        gradio_locators.click_tab("settings")
        status_label = dashboard_page.get_by_text("Status")
        expect(status_label.first).to_be_visible()

    def test_version_field_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Version field should exist."""
        gradio_locators.click_tab("settings")
        version_label = dashboard_page.get_by_text("Version", exact=True)
        expect(version_label).to_be_visible()


class TestHistoryTab:
    """TC-08.5: Configuration History Tab."""

    def test_history_tab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """History tab should be accessible."""
        gradio_locators.click_tab("settings")
        history_tab = dashboard_page.get_by_role("tab", name="History")
        expect(history_tab).to_be_visible()
        history_tab.click()


class TestAuditLogTab:
    """TC-08.6: Audit Log Tab."""

    def test_audit_log_tab_accessible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Audit Log tab should be accessible."""
        gradio_locators.click_tab("settings")
        audit_tab = dashboard_page.get_by_role("tab", name="Audit Log")
        expect(audit_tab).to_be_visible()
        audit_tab.click()
