"""
Example E2E Test

Demonstrates the test patterns and fixtures for WallTrack.
This test serves as a template for Epic 1 tests.

To run:
    uv run pytest tests/e2e/test_example.py -v

Note: This test will fail until the Gradio app is running.
      Start the app first: uv run python -m walltrack.main
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from tests.support.factories import WalletFactory, TokenFactory, SignalFactory


# =============================================================================
# Smoke Tests (Quick validation)
# =============================================================================


@pytest.mark.smoke
@pytest.mark.e2e
class TestSmoke:
    """Quick smoke tests to validate basic functionality."""

    def test_app_loads(self, page: Page, base_url: str) -> None:
        """
        GIVEN the WallTrack app is running
        WHEN I navigate to the home page
        THEN the page loads successfully
        AND the title contains 'WallTrack'
        """
        page.goto(base_url)

        # Assert page loads (Gradio apps have specific structure)
        expect(page).to_have_title_matching(r".*WallTrack.*|.*Gradio.*")

    def test_status_bar_visible(self, page: Page, base_url: str) -> None:
        """
        GIVEN the WallTrack app is running
        WHEN I navigate to the home page
        THEN the status bar is visible
        AND it shows system status
        """
        page.goto(base_url)

        # Assert status bar is visible (using elem_id from Gradio)
        status_bar = page.locator("#status-bar")
        expect(status_bar).to_be_visible(timeout=15_000)
        expect(status_bar).to_contain_text("System")


# =============================================================================
# Factory Usage Examples
# =============================================================================


class TestFactoryExamples:
    """Examples of using data factories in tests."""

    def test_wallet_factory_generates_valid_data(self) -> None:
        """
        GIVEN the WalletFactory
        WHEN I generate a wallet
        THEN it has valid structure and realistic data
        """
        wallet = WalletFactory.build()

        # Assert structure
        assert "address" in wallet
        assert "win_rate" in wallet
        assert "decay_status" in wallet

        # Assert valid values
        assert len(wallet["address"]) == 44  # Solana address length
        assert 0.0 <= wallet["win_rate"] <= 1.0
        assert wallet["decay_status"] in ["ok", "flagged", "downgraded", "dormant"]

    def test_wallet_factory_accepts_overrides(self) -> None:
        """
        GIVEN the WalletFactory
        WHEN I generate a wallet with custom values
        THEN those values are applied
        """
        wallet = WalletFactory.build(
            win_rate=0.85,
            decay_status="ok",
            is_leader=True,
        )

        assert wallet["win_rate"] == 0.85
        assert wallet["decay_status"] == "ok"
        assert wallet["is_leader"] is True

    def test_high_performance_wallet_factory(self) -> None:
        """
        GIVEN the HighPerformanceWalletFactory
        WHEN I generate a wallet
        THEN it has high performance metrics
        """
        from tests.support.factories.wallet_factory import HighPerformanceWalletFactory

        wallet = HighPerformanceWalletFactory.build()

        assert wallet["win_rate"] >= 0.7
        assert wallet["decay_status"] == "ok"
        assert wallet["is_leader"] is True

    def test_token_factory_generates_valid_data(self) -> None:
        """
        GIVEN the TokenFactory
        WHEN I generate a token
        THEN it has valid structure
        """
        token = TokenFactory.build()

        assert len(token["address"]) == 44
        assert len(token["symbol"]) >= 3
        assert token["market_cap"] > 0
        assert token["liquidity_usd"] > 0

    def test_signal_factory_with_score(self) -> None:
        """
        GIVEN the SignalFactory
        WHEN I generate an actionable signal
        THEN it has valid scoring data
        """
        from tests.support.factories.signal_factory import ActionableSignalFactory

        signal = ActionableSignalFactory.build()

        assert signal["score"] >= 0.70
        assert signal["status"] == "actionable"
        assert "wallet_score" in signal["score_breakdown"]

    def test_batch_generation(self) -> None:
        """
        GIVEN the factories
        WHEN I generate multiple items
        THEN each item is unique
        """
        wallets = WalletFactory.build_batch(5)

        # All addresses should be unique
        addresses = [w["address"] for w in wallets]
        assert len(set(addresses)) == 5


# =============================================================================
# Helper Usage Examples
# =============================================================================


class TestHelperExamples:
    """Examples of using test helpers."""

    def test_format_helpers(self) -> None:
        """Test format helper functions."""
        from tests.support.helpers import format_sol_amount, truncate_address

        # SOL formatting
        assert format_sol_amount(1.2345) == "1.2345 SOL"
        assert format_sol_amount(0.1, decimals=2) == "0.10 SOL"

        # Address truncation
        long_addr = "A" * 44
        truncated = truncate_address(long_addr)
        assert truncated == "AAAA...AAAA"

    def test_decay_badge_formatting(self) -> None:
        """Test decay status badge formatting."""
        from tests.support.helpers.format_helpers import format_decay_badge

        assert format_decay_badge("ok") == "🟢"
        assert format_decay_badge("flagged") == "🟡"
        assert format_decay_badge("downgraded") == "🔴"
        assert format_decay_badge("dormant") == "⚪"


# =============================================================================
# E2E Test Template (for Epic 1)
# =============================================================================


@pytest.mark.e2e
class TestEpic1Foundation:
    """
    Epic 1: Foundation & Core Infrastructure

    These tests validate Story 1.4: Gradio Base App & Status Bar.
    Note: Comprehensive tests are in test_epic1_validation.py.
    """

    def test_gradio_app_renders(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC1

        GIVEN Gradio app with gr.themes.Soft()
        WHEN I open the dashboard
        THEN the page loads without errors
        """
        page.goto(base_url)

        # Assert page loads without critical errors
        expect(page.locator("body")).not_to_contain_text("Error 404")
        expect(page.locator("body")).not_to_contain_text("Internal Server Error")

    def test_status_bar_shows_system_status(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - AC2

        GIVEN all services connected
        WHEN status bar renders
        THEN it shows system status
        """
        page.goto(base_url)

        # Wait for status bar to load (uses elem_id="status-bar")
        status_bar = page.locator("#status-bar")
        expect(status_bar).to_be_visible(timeout=15_000)

        # Assert system status shown
        expect(status_bar).to_contain_text("System")

    def test_navigation_to_settings(self, page: Page, base_url: str) -> None:
        """
        Story 1.4 - Navigation works

        GIVEN the dashboard is open
        WHEN I click on Settings navigation
        THEN the Settings page loads
        """
        page.goto(base_url)

        # Navigate to Settings (was Config, renamed in Gradio 6)
        page.click("text=Settings")
        page.wait_for_load_state("networkidle")

        # Verify page changed
        expect(page.locator("body")).to_contain_text("Settings", ignore_case=True)
