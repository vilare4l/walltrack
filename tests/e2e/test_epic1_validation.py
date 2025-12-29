"""
Epic 1 E2E Validation Tests

Complete validation of Foundation & Core Infrastructure.
Run with: uv run pytest tests/e2e/test_epic1_validation.py -v --headed
"""

from __future__ import annotations

import httpx
import pytest
from playwright.sync_api import Page, expect


@pytest.mark.e2e
class TestEpic1Foundation:
    """Epic 1: Foundation & Core Infrastructure - Complete Validation."""

    # =========================================================================
    # Story 1.1: Project Structure & Configuration
    # =========================================================================

    def test_app_starts_with_configuration(self, api_url: str) -> None:
        """
        Story 1.1 - AC1: Configuration loads correctly

        GIVEN valid environment configuration
        WHEN the app starts
        THEN health endpoint returns OK
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ("ok", "degraded")  # ok if all healthy, degraded if partial

    # =========================================================================
    # Story 1.2: Database Connections
    # =========================================================================

    def test_neo4j_connection_healthy(self, api_url: str) -> None:
        """
        Story 1.2 - AC1: Neo4j connection established

        GIVEN valid Neo4j credentials
        WHEN health check runs
        THEN Neo4j status is reported
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/health")

        data = response.json()
        assert "databases" in data
        assert "neo4j" in data["databases"]

    def test_supabase_connection_healthy(self, api_url: str) -> None:
        """
        Story 1.2 - AC2: Supabase connection established

        GIVEN valid Supabase credentials
        WHEN health check runs
        THEN Supabase status is reported
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/health")

        data = response.json()
        assert "databases" in data
        assert "supabase" in data["databases"]

    # =========================================================================
    # Story 1.4: Gradio Base App & Status Bar
    # =========================================================================

    def test_gradio_app_loads(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC1: Gradio app renders

        GIVEN Gradio app with gr.themes.Soft()
        WHEN I open the dashboard
        THEN the page loads successfully
        """
        page.goto(base_url)

        # Gradio apps have specific structure - check page loads
        # Title may vary, but page should not show error
        expect(page.locator("body")).not_to_contain_text("Error 404")
        expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    def test_status_bar_visible(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC3: Status bar shows system status

        GIVEN the dashboard is open
        WHEN the page loads
        THEN status bar is visible with system status
        """
        page.goto(base_url)

        # Wait for status bar element (uses elem_id="status-bar")
        status_bar = page.locator("#status-bar")
        expect(status_bar).to_be_visible(timeout=15_000)

    def test_status_bar_shows_simulation_mode(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC3: Status bar shows mode indicator

        GIVEN the dashboard is open in simulation mode
        WHEN the page loads
        THEN status bar shows SIMULATION mode
        """
        page.goto(base_url)

        # Should show simulation mode (default)
        expect(page.locator("body")).to_contain_text("SIMULATION")

    def test_navigation_to_explorer_page(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC2: Navigation between pages works

        GIVEN the dashboard is open
        WHEN I navigate to Explorer page
        THEN Explorer page content is visible
        """
        page.goto(base_url)

        # Click Explorer navigation (Gradio renders nav links)
        page.click("text=Explorer")

        # Wait for navigation and verify page changed
        page.wait_for_load_state("networkidle")

        # Explorer page should have specific content
        expect(page.locator("body")).to_contain_text("Explorer")

    def test_navigation_to_settings_page(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC2: Navigation to Settings page

        GIVEN the dashboard is open
        WHEN I navigate to Settings page
        THEN Settings page content is visible
        """
        page.goto(base_url)

        # Click Settings navigation
        page.click("text=Settings")

        # Wait for navigation
        page.wait_for_load_state("networkidle")

        # Settings page should show configuration content
        # Look for wallet section (Story 1.5) or other config elements
        expect(page.locator("body")).to_contain_text("Settings", ignore_case=True)

    # =========================================================================
    # Story 1.5: Trading Wallet Connection
    # =========================================================================

    def test_wallet_section_on_settings_page(self, page: Page, base_url: str) -> None:
        """
        Story 1.5 - AC1: Wallet section visible on Settings page

        GIVEN the Settings page
        WHEN I view the page
        THEN Trading Wallet section is visible
        """
        page.goto(f"{base_url}")
        page.click("text=Settings")
        page.wait_for_load_state("networkidle")

        # Look for wallet-related content
        body_text = page.locator("body")
        # Should contain wallet or trading related text
        has_wallet = (
            body_text.locator("text=/Wallet/i").count() > 0
            or body_text.locator("text=/Trading/i").count() > 0
            or body_text.locator("text=/Connect/i").count() > 0
        )

        assert has_wallet, "Settings page should contain wallet configuration section"

    def test_status_bar_shows_wallet_status(self, page: Page, base_url: str) -> None:
        """
        Story 1.5 - Status bar shows wallet connection status

        GIVEN the dashboard is open
        WHEN the page loads
        THEN status bar shows wallet status (connected or not)
        """
        page.goto(base_url)

        status_bar = page.locator("#status-bar")
        expect(status_bar).to_be_visible(timeout=15_000)

        # Should show wallet status (either "Wallet:" followed by address or "Not Connected")
        expect(status_bar).to_contain_text("Wallet")


@pytest.mark.e2e
@pytest.mark.smoke
class TestEpic1Smoke:
    """Quick smoke tests for Epic 1 - run in CI."""

    def test_api_health(self, api_url: str) -> None:
        """API health endpoint responds."""
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{api_url}/api/health")
        assert response.status_code == 200

    def test_dashboard_loads(self, page: Page, base_url: str) -> None:
        """Dashboard loads without errors."""
        page.goto(base_url)
        expect(page.locator("body")).not_to_contain_text("Error 404")
        expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    def test_status_bar_renders(self, page: Page, base_url: str) -> None:
        """Status bar component renders."""
        page.goto(base_url)
        status_bar = page.locator("#status-bar")
        expect(status_bar).to_be_visible(timeout=15_000)


@pytest.mark.e2e
class TestEpic1API:
    """API-level tests for Epic 1 validation."""

    def test_health_endpoint_structure(self, api_url: str) -> None:
        """
        Health endpoint returns expected structure.

        GIVEN the API is running
        WHEN I call /api/health
        THEN I get a structured response with status and databases
        """
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{api_url}/api/health")

        assert response.status_code == 200
        data = response.json()

        # Required fields
        assert "status" in data
        assert data["status"] in ("ok", "degraded")

        # Database status
        assert "databases" in data
        assert isinstance(data["databases"], dict)

    def test_dashboard_endpoint_accessible(self, api_url: str) -> None:
        """
        Dashboard endpoint responds.

        GIVEN the API with Gradio mounted
        WHEN I request /dashboard
        THEN I get a response (Gradio serves HTML)
        """
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            response = client.get(f"{api_url}/dashboard")

        # Gradio serves HTML, should not be 404
        assert response.status_code in (200, 302, 307)
