"""
WallTrack Test Configuration - Main conftest.py

This file configures pytest and Playwright fixtures for the entire test suite.
Follows the fixture-architecture pattern: pure functions -> fixtures -> composition.

Timeout Standards:
- Action timeout: 15s (click, fill, etc.)
- Navigation timeout: 30s (page.goto)
- Expect timeout: 10s (assertions)
- Test timeout: 60s (overall test)
"""

from __future__ import annotations

import os
from collections.abc import Generator
from typing import TYPE_CHECKING

import pytest
from playwright.sync_api import Page, expect

if TYPE_CHECKING:
    from playwright.sync_api import Playwright

# =============================================================================
# Environment Configuration
# =============================================================================

# Load test environment from TEST_ENV variable (default: local)
TEST_ENV = os.getenv("TEST_ENV", "local")

# Environment-specific base URLs
# Note: Gradio dashboard is mounted at /dashboard on the FastAPI server
# Docker compose maps internal port 8000 to external port 8080
ENV_CONFIG = {
    "local": {
        "base_url": os.getenv("BASE_URL", "http://localhost:8080/dashboard"),
        "api_url": os.getenv("API_URL", "http://localhost:8080"),
    },
    "staging": {
        "base_url": os.getenv("BASE_URL", "https://staging.walltrack.example.com/dashboard"),
        "api_url": os.getenv("API_URL", "https://staging-api.walltrack.example.com"),
    },
}

# Fail-fast if invalid environment
if TEST_ENV not in ENV_CONFIG:
    available = ", ".join(ENV_CONFIG.keys())
    raise ValueError(f"Invalid TEST_ENV='{TEST_ENV}'. Available: {available}")


def get_config(key: str) -> str:
    """Get configuration value for current environment."""
    return ENV_CONFIG[TEST_ENV][key]


# =============================================================================
# Pytest Configuration
# =============================================================================


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers and settings."""
    # Register custom markers
    config.addinivalue_line("markers", "e2e: End-to-end tests using Playwright")
    config.addinivalue_line("markers", "smoke: Quick smoke tests for CI")
    config.addinivalue_line("markers", "slow: Slow tests that may be skipped")


# =============================================================================
# Database Singleton Reset (CRITICAL for test isolation)
# =============================================================================


@pytest.fixture(autouse=True)
def reset_database_singletons() -> Generator[None, None, None]:
    """
    Reset all database singletons before and after each test.

    This prevents test pollution when running the full test suite.
    Without this, TestClient's event loop can conflict with pytest-asyncio.
    """
    import walltrack.data.neo4j.client as neo4j_module
    import walltrack.data.supabase.client as supabase_module

    # Clear before test
    neo4j_module._neo4j_client = None
    supabase_module._supabase_client = None

    yield

    # Clear after test
    neo4j_module._neo4j_client = None
    supabase_module._supabase_client = None


# =============================================================================
# Playwright Fixtures
# =============================================================================


@pytest.fixture(scope="session")
def browser_context_args() -> dict:
    """
    Browser context arguments for Playwright.
    Sets viewport, locale, and timeout defaults.
    """
    return {
        "viewport": {"width": 1920, "height": 1080},
        "locale": "fr-FR",
        "timezone_id": "Europe/Paris",
        # Record video only on failure (configured via pytest-playwright)
        "record_video_dir": None,  # Disabled by default, enable in CI
    }


@pytest.fixture(scope="session")
def browser_type_launch_args() -> dict:
    """
    Browser launch arguments.
    Headless in CI, headed locally for debugging.
    """
    is_ci = os.getenv("CI", "false").lower() == "true"
    return {
        "headless": is_ci,
        "slow_mo": 0 if is_ci else 100,  # Slow down for local debugging
    }


@pytest.fixture(scope="session")
def base_url() -> str:
    """Get base URL for current environment."""
    return get_config("base_url")


@pytest.fixture(scope="session")
def api_url() -> str:
    """Get API URL for current environment."""
    return get_config("api_url")


@pytest.fixture
def configured_page(page: Page, base_url: str) -> Generator[Page, None, None]:
    """
    Page fixture with WallTrack-specific configuration.
    Sets timeouts and navigates to base URL.
    """
    # Set timeout defaults (in milliseconds)
    page.set_default_timeout(15_000)  # Action timeout: 15s
    page.set_default_navigation_timeout(30_000)  # Navigation timeout: 30s

    # Configure expect defaults
    expect.set_options(timeout=10_000)  # Expect timeout: 10s

    yield page

    # Cleanup: Close any open dialogs or modals
    # (Playwright handles page cleanup automatically)


# =============================================================================
# API Fixtures
# =============================================================================


@pytest.fixture
def api_request_context(playwright: Playwright, api_url: str) -> Generator:
    """
    API request context for making direct API calls.
    Useful for setting up test data before E2E tests.
    """
    context = playwright.request.new_context(
        base_url=api_url,
        extra_http_headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    yield context
    context.dispose()


# =============================================================================
# Factory Fixtures (imported from support/factories)
# =============================================================================

# These will be imported from support/factories as the project grows
# Example:
# from tests.support.factories import WalletFactory, TokenFactory
#
# @pytest.fixture
# def wallet_factory(api_request_context):
#     return WalletFactory(api_request_context)


# =============================================================================
# External API Mock Fixtures
# =============================================================================

# Import mock fixtures for external APIs (DexScreener, etc.)
# These are available in E2E tests via pytest_plugins
pytest_plugins = ["tests.fixtures.dexscreener_mock"]


# =============================================================================
# Helper Fixtures
# =============================================================================


@pytest.fixture
def screenshot_on_failure(page: Page, request: pytest.FixtureRequest) -> Generator:
    """
    Capture screenshot on test failure.
    Screenshots are saved to test-results/ directory.
    """
    yield

    # Check if test failed
    if request.node.rep_call.failed if hasattr(request.node, "rep_call") else False:
        test_name = request.node.name
        screenshot_path = f"test-results/screenshots/{test_name}.png"
        page.screenshot(path=screenshot_path, full_page=True)


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:
    """Store test result for screenshot_on_failure fixture."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
