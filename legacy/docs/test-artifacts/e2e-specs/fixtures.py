"""
E2E Test Fixtures for WallTrack

This file provides reusable fixtures for Playwright E2E tests.
Copy to tests/e2e/conftest.py and adapt as needed.
"""

import os
from uuid import uuid4
from typing import Generator

import pytest
from playwright.sync_api import Page, Browser, BrowserContext, expect

# =============================================================================
# ENVIRONMENT CONFIG
# =============================================================================

GRADIO_HOST = os.getenv("GRADIO_HOST", "localhost")
GRADIO_PORT = os.getenv("GRADIO_PORT", "7865")
GRADIO_BASE_URL = f"http://{GRADIO_HOST}:{GRADIO_PORT}"

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")

DEFAULT_TIMEOUT = 30_000
NAVIGATION_TIMEOUT = 60_000


# =============================================================================
# GRADIO LOCATORS HELPER
# =============================================================================

class GradioLocators:
    """Helper class for interacting with Gradio components."""

    def __init__(self, page: Page):
        self.page = page

    def click_tab(self, tab_name: str) -> None:
        """Click a main navigation tab."""
        tab_map = {
            "home": "Home",
            "explorer": "Explorer",
            "signals": "Signals",
            "positions": "Positions",
            "clusters": "Clusters",
            "config": "Config",
        }
        display_name = tab_map.get(tab_name.lower(), tab_name)
        tab = self.page.get_by_role("tab", name=display_name)
        tab.click()
        self.page.wait_for_timeout(500)

    def get_table(self, table_id: str) -> "Locator":
        """Get a table by elem_id."""
        return self.page.locator(f"#{table_id}")

    def get_button(self, button_id: str) -> "Locator":
        """Get a button by elem_id."""
        return self.page.locator(f"#{button_id}")

    def fill_input(self, input_id: str, value: str) -> None:
        """Fill a text input."""
        input_elem = self.page.locator(f"#{input_id}")
        input_elem.fill(value)

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
# BROWSER FIXTURES
# =============================================================================

@pytest.fixture(scope="session")
def browser_context_args():
    """Browser context arguments."""
    return {
        "viewport": {"width": 1920, "height": 1080},
        "ignore_https_errors": True,
    }


@pytest.fixture
def dashboard_page(page: Page) -> Generator[Page, None, None]:
    """Navigate to dashboard and wait for load."""
    page.set_default_timeout(DEFAULT_TIMEOUT)
    page.goto(GRADIO_BASE_URL, timeout=NAVIGATION_TIMEOUT)
    page.wait_for_load_state("networkidle")

    # Wait for Gradio to fully render
    page.wait_for_selector(".gradio-container", timeout=NAVIGATION_TIMEOUT)

    yield page


@pytest.fixture
def gradio_locators(dashboard_page: Page) -> GradioLocators:
    """Gradio locators helper."""
    return GradioLocators(dashboard_page)


# =============================================================================
# API CLIENT FIXTURES
# =============================================================================

@pytest.fixture
def api_client():
    """Async HTTP client for API calls."""
    import httpx
    return httpx.AsyncClient(base_url=API_BASE_URL, timeout=30.0)


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================

@pytest.fixture
def watchlisted_wallet() -> str:
    """A wallet address that exists in the watchlist."""
    # Replace with actual test wallet from your test database
    return "TestWatchlistedWallet123456789"


@pytest.fixture
def non_watchlisted_wallet() -> str:
    """A wallet address NOT in the watchlist."""
    return f"NonWatchlisted_{uuid4().hex[:16]}"


@pytest.fixture
def valid_token_mint() -> str:
    """A valid token mint that passes safety checks."""
    # Replace with actual test token from your test database
    return "ValidSafeTokenMint123456789"


@pytest.fixture
def honeypot_token_mint() -> str:
    """A token mint that fails safety checks (honeypot)."""
    return "HoneypotTokenMint_UNSAFE"


@pytest.fixture
def cluster_leader_wallet() -> str:
    """A wallet that is a cluster leader."""
    return "ClusterLeaderWallet123"


# =============================================================================
# WEBHOOK PAYLOAD FIXTURES
# =============================================================================

@pytest.fixture
def webhook_payload(watchlisted_wallet: str, valid_token_mint: str) -> dict:
    """Valid Helius webhook payload."""
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
                "amount": 100000000,  # 0.1 SOL
            }],
        }]
    }


@pytest.fixture
def sell_webhook_payload(watchlisted_wallet: str, valid_token_mint: str) -> dict:
    """Webhook payload for a SELL transaction."""
    return {
        "type": "TRANSACTION",
        "transactions": [{
            "signature": f"sell_sig_{uuid4().hex[:8]}",
            "type": "SWAP",
            "feePayer": watchlisted_wallet,
            "timestamp": 1703721700,
            "tokenTransfers": [{
                "mint": valid_token_mint,
                "fromUserAccount": watchlisted_wallet,
                "toUserAccount": "DEX_POOL_ADDRESS",
                "tokenAmount": 500000,
                "tokenStandard": "Fungible",
            }],
            "nativeTransfers": [{
                "fromUserAccount": "DEX_POOL_ADDRESS",
                "toUserAccount": watchlisted_wallet,
                "amount": 150000000,  # 0.15 SOL (profit)
            }],
        }]
    }


# =============================================================================
# DISCOVERY FIXTURES
# =============================================================================

@pytest.fixture
def discovery_token_address() -> str:
    """A token address for discovery testing."""
    return "DiscoveryTestToken123456789"


@pytest.fixture
def discovery_params() -> dict:
    """Default discovery parameters."""
    return {
        "early_window_minutes": 30,
        "min_profit_percent": 50.0,
        "min_wallets": 5,
    }


# =============================================================================
# POSITION FIXTURES
# =============================================================================

@pytest.fixture
def active_position_id() -> str:
    """ID of an active position in test database."""
    return "active-position-test-001"


@pytest.fixture
def closed_position_id() -> str:
    """ID of a closed position in test database."""
    return "closed-position-test-001"


# =============================================================================
# ORDER FIXTURES
# =============================================================================

@pytest.fixture
def pending_order_id() -> str:
    """ID of a pending order in test database."""
    return "pending-order-test-001"


@pytest.fixture
def failed_order_id() -> str:
    """ID of a failed order in test database."""
    return "failed-order-test-001"


# =============================================================================
# SCORING FIXTURES
# =============================================================================

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


@pytest.fixture
def high_score_wallet_metrics() -> dict:
    """Wallet metrics that should produce TRADE decision."""
    return {
        "win_rate": 0.75,
        "pnl_percent": 150.0,
        "is_leader": True,
        "cluster_size": 5,
    }


@pytest.fixture
def low_score_wallet_metrics() -> dict:
    """Wallet metrics that should produce NO TRADE decision."""
    return {
        "win_rate": 0.30,
        "pnl_percent": -20.0,
        "is_leader": False,
        "cluster_size": 1,
    }


# =============================================================================
# CLUSTER FIXTURES
# =============================================================================

@pytest.fixture
def test_cluster_id() -> str:
    """ID of a test cluster in Neo4j."""
    return "cluster-test-001"


@pytest.fixture
def cluster_members() -> list[str]:
    """Member wallet addresses for test cluster."""
    return [
        "ClusterMember1Wallet",
        "ClusterMember2Wallet",
        "ClusterMember3Wallet",
        "ClusterLeaderWallet123",
    ]


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def assert_table_has_rows(page: Page, table_id: str, min_rows: int = 1) -> None:
    """Assert that a table has at least min_rows rows."""
    table = page.locator(f"#{table_id}")
    rows = table.locator("tbody tr")
    assert rows.count() >= min_rows, f"Expected at least {min_rows} rows in {table_id}"


def assert_element_contains_any(page: Page, selector: str, texts: list[str]) -> None:
    """Assert element contains any of the given texts."""
    element = page.locator(selector)
    content = element.inner_text()
    assert any(text in content for text in texts), \
        f"Expected one of {texts} in element content: {content}"


def wait_for_api_response(page: Page, url_pattern: str, timeout: int = 10000) -> None:
    """Wait for a specific API response."""
    page.wait_for_response(
        lambda response: url_pattern in response.url,
        timeout=timeout
    )


# =============================================================================
# MARKERS
# =============================================================================

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as end-to-end test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "api: mark test as API integration test"
    )
