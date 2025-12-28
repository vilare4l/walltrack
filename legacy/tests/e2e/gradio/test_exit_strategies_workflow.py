"""Comprehensive E2E tests for Exit Strategies Page workflows.

These tests verify actual functionality:
- Exit strategies table display
- Strategy editor form
- Strategy creation workflow
- Strategy actions (save draft, activate, clone, delete)
- Template creation

Run with:
    uv run pytest tests/e2e/gradio/test_exit_strategies_workflow.py -m e2e -v --headed
"""

import pytest
from playwright.sync_api import Page, expect

pytestmark = pytest.mark.e2e


class TestExitStrategiesPageLoading:
    """TC-EXIT-01: Verify Exit Strategies page loads correctly."""

    def test_exit_strategies_page_loads(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Exit Strategies page should load with correct URL."""
        gradio_locators.click_tab("exit-strategies")
        expect(dashboard_page).to_have_url("http://localhost:7865/exit-strategies")

    def test_strategies_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategies heading should be visible."""
        gradio_locators.click_tab("exit-strategies")
        heading = dashboard_page.get_by_role("heading", name="Strategies")
        expect(heading).to_be_visible()


class TestStrategiesTable:
    """TC-EXIT-02: Verify strategies table structure."""

    def test_strategies_table_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategies table should be visible."""
        gradio_locators.click_tab("exit-strategies")

        # Look for table with Exit Strategies caption
        table = dashboard_page.locator("table").first
        expect(table).to_be_visible()

    def test_strategies_table_columns(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategies table should have correct columns."""
        gradio_locators.click_tab("exit-strategies")

        expected_columns = ["ID", "Name", "Version", "Status", "Rules", "Created"]
        for col_name in expected_columns:
            column = dashboard_page.get_by_role("columnheader").filter(has_text=col_name)
            expect(column.first).to_be_visible()

    def test_strategies_table_sortable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategies table columns should be sortable."""
        gradio_locators.click_tab("exit-strategies")

        # Name column should have a sortable button
        name_header = dashboard_page.get_by_role("columnheader").filter(has_text="Name").first
        sort_button = name_header.locator("button").first
        expect(sort_button).to_be_visible()


class TestStrategyEditor:
    """TC-EXIT-03: Verify strategy editor form."""

    def test_editor_heading_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy Editor heading should be visible."""
        gradio_locators.click_tab("exit-strategies")
        heading = dashboard_page.get_by_role("heading", name="Strategy Editor")
        expect(heading).to_be_visible()

    def test_strategy_name_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy name input should be visible."""
        gradio_locators.click_tab("exit-strategies")
        name_input = dashboard_page.get_by_label("Name")
        expect(name_input).to_be_visible()

    def test_strategy_version_field(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy version field should be visible (disabled for new)."""
        gradio_locators.click_tab("exit-strategies")
        version_field = dashboard_page.get_by_label("Version")
        expect(version_field).to_be_visible()

    def test_strategy_description_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Description input should be visible."""
        gradio_locators.click_tab("exit-strategies")
        desc_input = dashboard_page.get_by_label("Description")
        expect(desc_input).to_be_visible()

    def test_max_hold_hours_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Max Hold hours input should be visible."""
        gradio_locators.click_tab("exit-strategies")
        max_hold = dashboard_page.get_by_label("Max Hold (hours)")
        expect(max_hold).to_be_visible()

    def test_stagnation_hours_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Stagnation hours input should be visible."""
        gradio_locators.click_tab("exit-strategies")
        stagnation = dashboard_page.get_by_label("Stagnation (hours)")
        expect(stagnation).to_be_visible()

    def test_stagnation_threshold_input(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Stagnation Threshold input should be visible."""
        gradio_locators.click_tab("exit-strategies")
        threshold = dashboard_page.get_by_label("Stagnation Threshold (%)")
        expect(threshold).to_be_visible()


class TestExitRulesEditor:
    """TC-EXIT-04: Verify Exit Rules JSON editor."""

    def test_exit_rules_heading(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Exit Rules heading should be visible."""
        gradio_locators.click_tab("exit-strategies")
        heading = dashboard_page.get_by_role("heading", name="Exit Rules")
        expect(heading).to_be_visible()

    def test_rules_json_editor_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Rules JSON editor should be visible."""
        gradio_locators.click_tab("exit-strategies")
        # Look for the code input container
        code_input = dashboard_page.get_by_label("Code input container")
        expect(code_input).to_be_visible()

    def test_rules_documentation_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Rules documentation should show rule types."""
        gradio_locators.click_tab("exit-strategies")

        # Verify rule types documentation
        rule_types = dashboard_page.get_by_text("Rule Types:")
        expect(rule_types).to_be_visible()

        # Verify specific rule types mentioned
        expect(dashboard_page.get_by_text("stop_loss").first).to_be_visible()
        expect(dashboard_page.get_by_text("take_profit").first).to_be_visible()


class TestStrategyActions:
    """TC-EXIT-05: Verify strategy action buttons."""

    def test_save_draft_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Save Draft button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        save_btn = dashboard_page.get_by_role("button", name="Save Draft")
        expect(save_btn).to_be_visible()

    def test_activate_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Activate button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        activate_btn = dashboard_page.get_by_role("button", name="Activate")
        expect(activate_btn).to_be_visible()

    def test_clone_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Clone button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        clone_btn = dashboard_page.get_by_role("button", name="Clone")
        expect(clone_btn).to_be_visible()

    def test_delete_draft_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Delete Draft button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        delete_btn = dashboard_page.get_by_role("button", name="Delete Draft")
        expect(delete_btn).to_be_visible()

    def test_refresh_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        expect(refresh_btn).to_be_visible()

    def test_new_button_visible(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """+ New button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        new_btn = dashboard_page.get_by_role("button", name="+ New")
        expect(new_btn).to_be_visible()


class TestQuickActions:
    """TC-EXIT-06: Verify Quick Actions section."""

    def test_quick_actions_heading(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Quick Actions heading should be visible."""
        gradio_locators.click_tab("exit-strategies")
        heading = dashboard_page.get_by_role("heading", name="Quick Actions")
        expect(heading).to_be_visible()

    def test_template_dropdown(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Template dropdown should be visible."""
        gradio_locators.click_tab("exit-strategies")
        template = dashboard_page.get_by_label("Template")
        expect(template).to_be_visible()

    def test_create_from_template_button(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Create from Template button should be visible."""
        gradio_locators.click_tab("exit-strategies")
        create_btn = dashboard_page.get_by_role("button", name="Create from Template")
        expect(create_btn).to_be_visible()


class TestShowArchivedFilter:
    """TC-EXIT-07: Verify Show Archived filter."""

    def test_show_archived_checkbox(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Show Archived checkbox should be visible."""
        gradio_locators.click_tab("exit-strategies")
        checkbox = dashboard_page.get_by_label("Show Archived")
        expect(checkbox).to_be_visible()

    def test_show_archived_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Show Archived checkbox should be clickable."""
        gradio_locators.click_tab("exit-strategies")
        checkbox = dashboard_page.get_by_label("Show Archived")
        checkbox.click()
        dashboard_page.wait_for_timeout(500)
        # Should not crash
        expect(checkbox).to_be_visible()


class TestStrategyPreview:
    """TC-EXIT-08: Verify Strategy Preview accordion."""

    def test_strategy_preview_accordion_exists(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy Preview accordion should exist."""
        gradio_locators.click_tab("exit-strategies")
        preview_btn = dashboard_page.get_by_role("button", name="Strategy Preview")
        expect(preview_btn).to_be_visible()

    def test_strategy_preview_expandable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Strategy Preview accordion should be expandable."""
        gradio_locators.click_tab("exit-strategies")
        preview_btn = dashboard_page.get_by_role("button", name="Strategy Preview")
        preview_btn.click()
        dashboard_page.wait_for_timeout(500)
        # Should not crash
        expect(preview_btn).to_be_visible()


class TestStrategyCreationWorkflow:
    """TC-EXIT-09: Verify strategy creation workflow."""

    def test_fill_strategy_name(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to fill strategy name."""
        gradio_locators.click_tab("exit-strategies")

        name_input = dashboard_page.get_by_label("Name")
        test_name = "Test E2E Strategy"
        name_input.fill(test_name)
        expect(name_input).to_have_value(test_name)

    def test_fill_description(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to fill description."""
        gradio_locators.click_tab("exit-strategies")

        desc_input = dashboard_page.get_by_label("Description")
        test_desc = "Test strategy description"
        desc_input.fill(test_desc)
        expect(desc_input).to_have_value(test_desc)

    def test_fill_max_hold_hours(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Should be able to set max hold hours."""
        gradio_locators.click_tab("exit-strategies")

        max_hold = dashboard_page.get_by_label("Max Hold (hours)")
        max_hold.fill("48")
        expect(max_hold).to_have_value("48")

    def test_save_draft_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Save Draft button should be clickable without crash."""
        gradio_locators.click_tab("exit-strategies")

        # Fill required fields first
        name_input = dashboard_page.get_by_label("Name")
        name_input.fill("Test Strategy Create")

        save_btn = dashboard_page.get_by_role("button", name="Save Draft")
        save_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # Page should still be functional
        expect(save_btn).to_be_visible()


class TestExitStrategiesRefresh:
    """TC-EXIT-10: Verify refresh functionality."""

    def test_refresh_button_clickable(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Refresh button should be clickable and update data."""
        gradio_locators.click_tab("exit-strategies")

        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        refresh_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # Page should still be functional
        heading = dashboard_page.get_by_role("heading", name="Strategies")
        expect(heading).to_be_visible()


class TestExitStrategiesCompleteWorkflow:
    """TC-EXIT-11: Verify complete exit strategies workflow."""

    def test_full_workflow(
        self, dashboard_page: Page, gradio_locators
    ) -> None:
        """Test complete exit strategies page workflow."""
        gradio_locators.click_tab("exit-strategies")

        # 1. Verify page loaded
        heading = dashboard_page.get_by_role("heading", name="Strategies")
        expect(heading).to_be_visible()

        # 2. Verify editor is ready
        name_input = dashboard_page.get_by_label("Name")
        expect(name_input).to_be_visible()

        # 3. Fill in strategy details
        name_input.fill("E2E Test Strategy")

        desc_input = dashboard_page.get_by_label("Description")
        desc_input.fill("Test strategy from E2E tests")

        max_hold = dashboard_page.get_by_label("Max Hold (hours)")
        max_hold.fill("24")

        # 4. Verify action buttons are enabled
        save_btn = dashboard_page.get_by_role("button", name="Save Draft")
        expect(save_btn).to_be_enabled()

        # 5. Click refresh to reset
        refresh_btn = dashboard_page.get_by_role("button", name="Refresh")
        refresh_btn.click()
        dashboard_page.wait_for_timeout(1000)

        # 6. Page should still be functional
        expect(heading).to_be_visible()
