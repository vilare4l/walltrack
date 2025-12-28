"""Comprehensive E2E tests for Settings Page workflows.

These tests verify actual functionality of all Settings tabs:
- Trading config
- Position sizing
- Exit rules
- Signal thresholds
- Risk management
- Notifications
- Discovery settings

Run with:
    uv run pytest tests/e2e/gradio/test_settings_workflow.py -m e2e -v --headed
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestSettingsPageLoading:
    """TC-SET-01: Verify Settings page loads correctly."""

    def test_settings_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Settings page should load with Configuration Management heading."""
        gradio_locators.click_tab("settings")
        expect(dashboard_page).to_have_url("http://localhost:7865/settings")

        heading = dashboard_page.get_by_text("Configuration Management")
        expect(heading).to_be_visible()

    def test_settings_description_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Settings description should be visible."""
        gradio_locators.click_tab("settings")
        desc = dashboard_page.get_by_text("Manage your trading configuration")
        expect(desc).to_be_visible()


class TestSettingsTabs:
    """TC-SET-02: Verify Settings tabs structure."""

    def test_settings_has_multiple_tabs(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Settings should have multiple configuration tabs."""
        gradio_locators.click_tab("settings")

        # Expected tabs in settings
        expected_tabs = [
            "Trading",
            "Position Sizing",
            "Exit Rules",
            "Thresholds",
            "Risk",
            "Notifications",
            "Discovery",
        ]
        for tab_name in expected_tabs:
            tab = dashboard_page.get_by_role("tab", name=tab_name)
            expect(tab).to_be_visible()

    def test_trading_tab_selected_by_default(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trading tab should be selected by default."""
        gradio_locators.click_tab("settings")
        trading_tab = dashboard_page.get_by_role("tab", name="Trading")
        expect(trading_tab).to_have_attribute("aria-selected", "true")


class TestTradingTab:
    """TC-SET-03: Verify Trading configuration tab."""

    def test_trading_mode_toggle(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trading mode toggle should be visible."""
        gradio_locators.click_tab("settings")

        mode_label = dashboard_page.get_by_text("Trading Mode")
        expect(mode_label).to_be_visible()

    def test_auto_trade_checkbox(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Auto Trade checkbox should be visible."""
        gradio_locators.click_tab("settings")

        auto_trade = dashboard_page.get_by_label("Auto Trade Enabled")
        expect(auto_trade).to_be_visible()

    def test_max_concurrent_positions(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Max concurrent positions input should be visible."""
        gradio_locators.click_tab("settings")

        max_positions = dashboard_page.get_by_label("Max Concurrent Positions")
        expect(max_positions).to_be_visible()


class TestPositionSizingTab:
    """TC-SET-04: Verify Position Sizing configuration tab."""

    def test_switch_to_position_sizing_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Position Sizing tab."""
        gradio_locators.click_tab("settings")
        sizing_tab = dashboard_page.get_by_role("tab", name="Position Sizing")
        sizing_tab.click()
        expect(sizing_tab).to_have_attribute("aria-selected", "true")

    def test_default_position_size(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Default position size input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Position Sizing").click()

        size_input = dashboard_page.get_by_label("Default Position Size (SOL)")
        expect(size_input).to_be_visible()

    def test_min_position_size(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Min position size input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Position Sizing").click()

        min_size = dashboard_page.get_by_label("Min Position Size (SOL)")
        expect(min_size).to_be_visible()

    def test_max_position_size(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Max position size input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Position Sizing").click()

        max_size = dashboard_page.get_by_label("Max Position Size (SOL)")
        expect(max_size).to_be_visible()


class TestExitRulesTab:
    """TC-SET-05: Verify Exit Rules configuration tab."""

    def test_switch_to_exit_rules_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Exit Rules tab."""
        gradio_locators.click_tab("settings")
        exit_tab = dashboard_page.get_by_role("tab", name="Exit Rules")
        exit_tab.click()
        expect(exit_tab).to_have_attribute("aria-selected", "true")

    def test_take_profit_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Take profit percentage input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Exit Rules").click()

        tp_input = dashboard_page.get_by_label("Take Profit %")
        expect(tp_input).to_be_visible()

    def test_stop_loss_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Stop loss percentage input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Exit Rules").click()

        sl_input = dashboard_page.get_by_label("Stop Loss %")
        expect(sl_input).to_be_visible()

    def test_trailing_stop_checkbox(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Trailing stop checkbox should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Exit Rules").click()

        trailing = dashboard_page.get_by_label("Enable Trailing Stop")
        expect(trailing).to_be_visible()


class TestThresholdsTab:
    """TC-SET-06: Verify Thresholds configuration tab."""

    def test_switch_to_thresholds_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Thresholds tab."""
        gradio_locators.click_tab("settings")
        thresholds_tab = dashboard_page.get_by_role("tab", name="Thresholds")
        thresholds_tab.click()
        expect(thresholds_tab).to_have_attribute("aria-selected", "true")

    def test_min_score_threshold(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Min score threshold input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Thresholds").click()

        min_score = dashboard_page.get_by_label("Min Signal Score")
        expect(min_score).to_be_visible()

    def test_min_wallet_score(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Min wallet score input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Thresholds").click()

        wallet_score = dashboard_page.get_by_label("Min Wallet Score")
        expect(wallet_score).to_be_visible()


class TestRiskTab:
    """TC-SET-07: Verify Risk configuration tab."""

    def test_switch_to_risk_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Risk tab."""
        gradio_locators.click_tab("settings")
        risk_tab = dashboard_page.get_by_role("tab", name="Risk")
        risk_tab.click()
        expect(risk_tab).to_have_attribute("aria-selected", "true")

    def test_max_daily_loss(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Max daily loss input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Risk").click()

        daily_loss = dashboard_page.get_by_label("Max Daily Loss (SOL)")
        expect(daily_loss).to_be_visible()

    def test_max_position_risk(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Max position risk input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Risk").click()

        position_risk = dashboard_page.get_by_label("Max Position Risk %")
        expect(position_risk).to_be_visible()


class TestNotificationsTab:
    """TC-SET-08: Verify Notifications configuration tab."""

    def test_switch_to_notifications_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Notifications tab."""
        gradio_locators.click_tab("settings")
        notif_tab = dashboard_page.get_by_role("tab", name="Notifications")
        notif_tab.click()
        expect(notif_tab).to_have_attribute("aria-selected", "true")

    def test_telegram_enabled_checkbox(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Telegram enabled checkbox should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Notifications").click()

        telegram = dashboard_page.get_by_label("Enable Telegram")
        expect(telegram).to_be_visible()

    def test_notification_types(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Notification type checkboxes should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Notifications").click()

        # Look for notification type options
        trade_notif = dashboard_page.get_by_label("Trade Notifications")
        expect(trade_notif).to_be_visible()


class TestDiscoveryTab:
    """TC-SET-09: Verify Discovery configuration tab."""

    def test_switch_to_discovery_tab(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch to Discovery tab."""
        gradio_locators.click_tab("settings")
        discovery_tab = dashboard_page.get_by_role("tab", name="Discovery")
        discovery_tab.click()
        expect(discovery_tab).to_have_attribute("aria-selected", "true")

    def test_discovery_enabled_checkbox(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discovery enabled checkbox should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Discovery").click()

        discovery = dashboard_page.get_by_label("Enable Discovery")
        expect(discovery).to_be_visible()

    def test_discovery_interval(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Discovery interval input should be visible."""
        gradio_locators.click_tab("settings")
        dashboard_page.get_by_role("tab", name="Discovery").click()

        interval = dashboard_page.get_by_label("Discovery Interval (min)")
        expect(interval).to_be_visible()


class TestSettingsActions:
    """TC-SET-10: Verify Settings action buttons."""

    def test_save_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Save button should be visible."""
        gradio_locators.click_tab("settings")
        save_btn = dashboard_page.get_by_role("button", name="Save")
        expect(save_btn).to_be_visible()

    def test_reset_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Reset button should be visible."""
        gradio_locators.click_tab("settings")
        reset_btn = dashboard_page.get_by_role("button", name="Reset")
        expect(reset_btn).to_be_visible()

    def test_save_button_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Save button should be clickable without crash."""
        gradio_locators.click_tab("settings")
        save_btn = dashboard_page.get_by_role("button", name="Save")
        save_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # Page should still be functional
        expect(save_btn).to_be_visible()


class TestSettingsTabSwitching:
    """TC-SET-11: Verify switching between Settings tabs."""

    def test_switch_between_all_tabs(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should switch between all tabs without errors."""
        gradio_locators.click_tab("settings")

        tabs_to_test = [
            "Position Sizing",
            "Exit Rules",
            "Thresholds",
            "Risk",
            "Notifications",
            "Discovery",
            "Trading",  # Back to first
        ]

        for tab_name in tabs_to_test:
            tab = dashboard_page.get_by_role("tab", name=tab_name)
            tab.click()
            expect(tab).to_have_attribute("aria-selected", "true")
            dashboard_page.wait_for_timeout(300)
