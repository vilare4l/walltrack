"""Playwright E2E test fixtures for WallTrack Gradio dashboard.

This module provides fixtures for:
- Browser and page setup with Gradio-specific configuration
- Dashboard navigation helpers
- Element selectors using elem_id convention
- Screenshot capture on failure

Usage:
    @pytest.mark.e2e
    def test_dashboard_loads(dashboard_page):
        assert dashboard_page.locator("#dashboard-title").is_visible()
"""

import os
import subprocess
import time
from collections.abc import Generator
from typing import Any

import pytest
from playwright.sync_api import Page, expect

# =============================================================================
# Configuration
# =============================================================================

GRADIO_HOST = os.environ.get("GRADIO_HOST", "localhost")
GRADIO_PORT = int(os.environ.get("GRADIO_PORT", "7865"))  # Match UI_PORT in .env
GRADIO_BASE_URL = f"http://{GRADIO_HOST}:{GRADIO_PORT}"

# Timeouts (in milliseconds)
DEFAULT_TIMEOUT = 30_000  # 30 seconds for Gradio to load
ACTION_TIMEOUT = 15_000  # 15 seconds for actions
NAVIGATION_TIMEOUT = 60_000  # 60 seconds for initial load


# =============================================================================
# Gradio Dashboard Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def browser_context_args(browser_context_args: dict[str, Any]) -> dict[str, Any]:
    """Configure browser context for Gradio testing."""
    return {
        **browser_context_args,
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


@pytest.fixture
def dashboard_page(page: Page) -> Generator[Page, None, None]:
    """Navigate to dashboard and wait for Gradio to load.

    This fixture:
    1. Navigates to the Gradio dashboard URL
    2. Waits for the dashboard title to appear
    3. Yields the page for testing
    4. Takes a screenshot on failure

    Usage:
        def test_something(dashboard_page):
            dashboard_page.locator("#tab-wallets").click()
    """
    # Configure timeouts
    page.set_default_timeout(DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

    # Navigate to dashboard
    page.goto(GRADIO_BASE_URL)

    # Wait for Gradio to fully load (dashboard title appears)
    page.wait_for_selector("#dashboard-title", state="visible", timeout=NAVIGATION_TIMEOUT)

    yield page


@pytest.fixture
def gradio_locators(dashboard_page: Page) -> "GradioLocators":
    """Provide helper class for common Gradio element locators.

    Usage:
        def test_navigation(dashboard_page, gradio_locators):
            gradio_locators.click_tab("wallets")
            assert gradio_locators.is_tab_active("wallets")
    """
    return GradioLocators(dashboard_page)


# =============================================================================
# Gradio Locator Helpers
# =============================================================================


class GradioLocators:
    """Helper class for interacting with Gradio dashboard elements.

    All locators use the elem_id convention: {section}-{component}-{action}
    """

    def __init__(self, page: Page) -> None:
        self.page = page

    # -------------------------------------------------------------------------
    # Navigation
    # -------------------------------------------------------------------------

    def click_tab(self, tab_name: str) -> None:
        """Click a main navigation tab.

        Args:
            tab_name: One of: status, wallets, clusters, signals, positions, performance, config
        """
        # Map tab names to display text
        tab_display_names = {
            "status": "Status",
            "wallets": "Wallets",
            "clusters": "Clusters",
            "signals": "Signals",
            "positions": "Positions",
            "performance": "Performance",
            "config": "Config",
        }
        display_name = tab_display_names.get(tab_name, tab_name.capitalize())
        
        # Use role-based selector for Gradio tabs (rendered as tab buttons)
        self.page.get_by_role("tab", name=display_name).click()
        # Wait for tab content to load
        time.sleep(0.5)  # Gradio needs time to render tab content  # Gradio needs time to render tab content

    def is_tab_active(self, tab_name: str) -> bool:
        """Check if a tab is currently active."""
        tab = self.page.locator(f"#tab-{tab_name}")
        return "selected" in (tab.get_attribute("class") or "")

    # -------------------------------------------------------------------------
    # Wallets Tab
    # -------------------------------------------------------------------------

    @property
    def wallets_table(self):
        """Get the wallets table element."""
        return self.page.locator("#wallets-table")

    @property
    def wallets_refresh_btn(self):
        """Get the wallets refresh button."""
        return self.page.locator("#wallets-refresh-btn")

    @property
    def wallets_status_filter(self):
        """Get the wallets status filter dropdown."""
        return self.page.locator("#wallets-status-filter")

    @property
    def wallets_add_address_input(self):
        """Get the new wallet address input."""
        return self.page.locator("#wallets-new-address")

    @property
    def wallets_add_btn(self):
        """Get the add wallet button."""
        return self.page.locator("#wallets-add-btn")

    def add_wallet(self, address: str) -> None:
        """Add a wallet to the watchlist.

        Args:
            address: Solana wallet address
        """
        self.wallets_add_address_input.fill(address)
        self.wallets_add_btn.click()

    # -------------------------------------------------------------------------
    # Config Tab
    # -------------------------------------------------------------------------

    @property
    def config_wallet_weight(self):
        """Get the wallet weight slider."""
        return self.page.locator("#config-wallet-weight")

    @property
    def config_apply_weights_btn(self):
        """Get the apply weights button."""
        return self.page.locator("#config-apply-weights-btn")

    @property
    def config_normalize_btn(self):
        """Get the normalize button."""
        return self.page.locator("#config-normalize-btn")

    @property
    def config_reset_btn(self):
        """Get the reset to defaults button."""
        return self.page.locator("#config-reset-btn")

    @property
    def config_status(self):
        """Get the config status message."""
        return self.page.locator("#config-status")

    # -------------------------------------------------------------------------
    # Positions Tab
    # -------------------------------------------------------------------------

    @property
    def positions_table(self):
        """Get the positions table."""
        return self.page.locator("#positions-table")

    @property
    def positions_refresh_btn(self):
        """Get the positions refresh button."""
        return self.page.locator("#positions-refresh-btn")

    @property
    def history_table(self):
        """Get the trade history table."""
        return self.page.locator("#history-table")


# =============================================================================
# Utility Fixtures
# =============================================================================


@pytest.fixture
def gradio_server() -> Generator[str, None, None]:
    """Start Gradio server for testing and yield base URL.

    This fixture starts the Gradio dashboard in a subprocess,
    waits for it to be ready, runs tests, then stops it.

    Note: Only use this if you need to start the server.
    In most cases, the server should already be running.
    """
    import socket

    # Check if server is already running
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex((GRADIO_HOST, GRADIO_PORT))
    sock.close()

    if result == 0:
        # Server already running
        yield GRADIO_BASE_URL
        return

    # Start server
    process = subprocess.Popen(
        ["uv", "run", "python", "-m", "walltrack.ui.dashboard"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # Wait for server to start
    max_retries = 30
    for _ in range(max_retries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex((GRADIO_HOST, GRADIO_PORT))
        sock.close()
        if result == 0:
            break
        time.sleep(1)
    else:
        process.terminate()
        raise RuntimeError("Gradio server failed to start")

    yield GRADIO_BASE_URL

    # Cleanup
    process.terminate()
    process.wait(timeout=10)


# =============================================================================
# pytest-playwright Configuration
# =============================================================================


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args: dict[str, Any]) -> dict[str, Any]:
    """Configure browser launch arguments."""
    return {
        **browser_type_launch_args,
        "headless": os.environ.get("HEADED", "0") != "1",
        "slow_mo": int(os.environ.get("SLOW_MO", "0")),
    }
