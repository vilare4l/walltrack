"""Playwright E2E test fixtures for WallTrack Gradio dashboard.

This module provides fixtures for:
- Browser and page setup with Gradio-specific configuration
- Dashboard navigation helpers
- Element selectors using elem_id convention
- Test data fixtures for wallets, positions, orders, signals
- Webhook payload fixtures for integration tests

Usage:
    @pytest.mark.e2e
    def test_dashboard_loads(dashboard_page):
        assert dashboard_page.locator("#dashboard-title").is_visible()
"""

import os
import subprocess
import time
from collections.abc import Generator
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from playwright.sync_api import Browser

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


@pytest.fixture(scope="class")
def dashboard_page(browser: Any, browser_context_args: dict[str, Any]) -> Generator[Page, None, None]:
    """Navigate to dashboard and wait for Gradio to load.

    This fixture is class-scoped to reduce browser resource usage.
    Tests within the same class share a single page instance.

    This fixture:
    1. Creates a new browser context and page
    2. Navigates to the Gradio dashboard URL with retry logic
    3. Waits for the dashboard title to appear
    4. Yields the page for testing
    5. Closes the context when the class is done

    Usage:
        def test_something(dashboard_page):
            dashboard_page.locator("#tab-wallets").click()
    """
    # Create context with configured args
    context = browser.new_context(**browser_context_args)
    page = context.new_page()

    # Configure timeouts
    page.set_default_timeout(DEFAULT_TIMEOUT)
    page.set_default_navigation_timeout(NAVIGATION_TIMEOUT)

    # Navigate to dashboard with retry logic
    max_retries = 3
    retry_delay = 5  # seconds
    last_error = None

    for attempt in range(max_retries):
        try:
            page.goto(GRADIO_BASE_URL)
            # Wait for Gradio to fully load (dashboard title appears)
            page.wait_for_selector("#dashboard-title", state="visible", timeout=NAVIGATION_TIMEOUT)
            break  # Success
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                # Try refreshing the page
                try:
                    page.reload()
                except Exception:
                    pass
    else:
        # All retries exhausted
        context.close()
        if last_error:
            raise last_error
        raise RuntimeError("Failed to connect to dashboard after retries")

    yield page

    # Cleanup
    context.close()


@pytest.fixture(scope="class")
def gradio_locators(dashboard_page: Page) -> "GradioLocators":
    """Provide helper class for common Gradio element locators.

    Class-scoped to match dashboard_page fixture.

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
        """Click a main navigation link.

        Args:
            tab_name: One of: home, explorer, orders, settings, exit-strategies
        """
        # Map tab names to display text (actual navigation links)
        tab_display_names = {
            "home": "Home",
            "explorer": "Explorer",
            "orders": "Orders",
            "settings": "Settings",
            "exit-strategies": "Exit Strategies",
            # Legacy mappings for backward compatibility
            "wallets": "Explorer",
            "positions": "Home",
            "config": "Settings",
            "signals": "Home",
            "clusters": "Explorer",
            "discovery": "Explorer",
        }
        display_name = tab_display_names.get(tab_name.lower(), tab_name.capitalize())

        # Use link-based navigation (actual UI structure)
        link = self.page.get_by_role("link", name=display_name)
        link.click()
        # Wait for navigation to complete
        time.sleep(1.5)
        # Verify page is responsive (not crashed)
        self.page.wait_for_load_state("domcontentloaded", timeout=10000)

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

    # -------------------------------------------------------------------------
    # Discovery Tab (Epic 14)
    # -------------------------------------------------------------------------

    @property
    def discovery_token_input(self):
        """Get the token address input."""
        return self.page.locator("#discovery-token-input")

    @property
    def discovery_scan_btn(self):
        """Get the scan button."""
        return self.page.locator("#discovery-scan-btn")

    @property
    def discovery_results(self):
        """Get the discovery results container."""
        return self.page.locator("#discovery-results")

    @property
    def discovery_wallets_table(self):
        """Get the discovered wallets table."""
        return self.page.locator("#discovery-wallets-table")

    # -------------------------------------------------------------------------
    # Clusters Tab (Epic 14)
    # -------------------------------------------------------------------------

    @property
    def clusters_table(self):
        """Get the clusters list table."""
        return self.page.locator("#clusters-table")

    @property
    def cluster_details(self):
        """Get the cluster details panel."""
        return self.page.locator("#cluster-details")

    @property
    def cluster_members_table(self):
        """Get the cluster members table."""
        return self.page.locator("#cluster-members-table")

    # -------------------------------------------------------------------------
    # Signals Tab (Epic 14)
    # -------------------------------------------------------------------------

    @property
    def signals_table(self):
        """Get the signals table."""
        return self.page.locator("#signals-table")

    @property
    def signals_refresh_btn(self):
        """Get the signals refresh button."""
        return self.page.locator("#signals-refresh-btn")

    @property
    def signal_details(self):
        """Get the signal details panel."""
        return self.page.locator("#signal-details")

    # -------------------------------------------------------------------------
    # Position Details Sidebar (Epic 14)
    # -------------------------------------------------------------------------

    @property
    def position_details_sidebar(self):
        """Get the position details sidebar."""
        return self.page.locator("#position-details-sidebar")

    @property
    def sidebar_close_btn(self):
        """Get the sidebar close button."""
        return self.page.locator("#sidebar-close-btn")

    @property
    def sidebar_strategy_btn(self):
        """Get the change strategy button."""
        return self.page.locator("#sidebar-strategy-btn")

    # -------------------------------------------------------------------------
    # Orders Tab (Epic 14)
    # -------------------------------------------------------------------------

    @property
    def orders_table(self):
        """Get the orders table."""
        return self.page.locator("#orders-table")

    @property
    def orders_status_filter(self):
        """Get the orders status filter."""
        return self.page.locator("#orders-status-filter")

    @property
    def order_details(self):
        """Get the order details panel."""
        return self.page.locator("#order-details")

    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------

    def fill_input(self, input_id: str, value: str) -> None:
        """Fill a text input by elem_id."""
        self.page.locator(f"#{input_id}").fill(value)

    def set_slider(self, slider_id: str, value: float) -> None:
        """Set a slider value."""
        slider = self.page.locator(f"#{slider_id}")
        slider_input = slider.locator("input[type='range']")
        if slider_input.is_visible():
            slider_input.fill(str(value))

    def select_dropdown(self, dropdown_id: str, option_text: str) -> None:
        """Select an option from a dropdown."""
        dropdown = self.page.locator(f"#{dropdown_id}")
        dropdown.click()
        listbox = self.page.get_by_role("listbox")
        listbox.get_by_text(option_text).click()


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def watchlisted_wallet() -> str:
    """A wallet address that exists in the watchlist."""
    return "TestWatchlistedWallet123456789"


@pytest.fixture
def valid_token_mint() -> str:
    """A valid token mint that passes safety checks."""
    return "ValidSafeTokenMint123456789"


@pytest.fixture
def webhook_payload(watchlisted_wallet: str, valid_token_mint: str) -> dict:
    """Valid Helius webhook payload for BUY transaction."""
    return {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"test_sig_{uuid4().hex[:8]}",
            "type": "SWAP",
            "feePayer": watchlisted_wallet,
            "timestamp": 1703721600,
            "tokenTransfers": [{
                "mint": valid_token_mint,
                "fromUserAccount": "",
                "toUserAccount": watchlisted_wallet,
                "tokenAmount": 1000000,
                "tokenStandard": "Fungible",
            }],
            "nativeTransfers": [{
                "fromUserAccount": watchlisted_wallet,
                "toUserAccount": "DEX_POOL_ADDRESS",
                "amount": 100000000,
            }],
        }]
    }


@pytest.fixture
def default_scoring_config() -> dict:
    """Epic 14 default scoring configuration."""
    return {
        "trade_threshold": 0.65,
        "win_rate_weight": 0.60,
        "pnl_weight": 0.40,
        "leader_bonus": 1.15,
        "pnl_normalize_min": -50,
        "pnl_normalize_max": 200,
        "min_cluster_boost": 1.0,
        "max_cluster_boost": 1.8,
    }


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
