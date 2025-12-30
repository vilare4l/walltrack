"""E2E tests for Epic 3: Wallet Performance Analysis (Story 3.2).

Tests the complete UI flow for wallet performance analysis:
- Wallet table displays performance metrics columns
- "Analyze All Wallets" button is functional
- Wallet detail panel shows performance metrics
- Status feedback during analysis
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from playwright.async_api import Page, expect

from walltrack.data.models.wallet import PerformanceMetrics


@pytest.fixture
def sample_performance_metrics():
    """Sample performance metrics for testing."""
    return PerformanceMetrics(
        win_rate=75.5,
        pnl_total=12.5,
        entry_delay_seconds=3600,
        total_trades=25,
        confidence="high",
    )


@pytest.mark.skipif(
    not os.getenv("HELIUS_API_KEY"), reason="HELIUS_API_KEY not set"
)
class TestWalletPerformanceAnalysisE2E:
    """E2E tests for wallet performance analysis UI."""

    @pytest.mark.asyncio
    async def test_wallet_table_shows_performance_columns(self, page: Page):
        """Test that wallet table displays performance metrics columns.

        AC: Wallet table shows: Address, Score, Win Rate, PnL, Entry Delay,
        Trades, Confidence, Status.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")

        # Wait for app to load
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Explorer tab
        await page.click('button:has-text("Explorer")')

        # Open Wallets accordion
        wallets_accordion = page.locator('div[data-testid="Wallets-accordion"]').first
        if await wallets_accordion.is_visible():
            await wallets_accordion.click()

        # Wait for wallet table to render
        await page.wait_for_selector("table", timeout=5000)

        # Verify table headers include performance metrics
        headers = await page.locator("thead th").all_text_contents()

        expected_headers = [
            "Address",
            "Score",
            "Win Rate",
            "PnL",
            "Entry Delay",
            "Trades",
            "Confidence",
            "Status",
        ]

        for expected in expected_headers:
            assert any(
                expected.lower() in h.lower() for h in headers
            ), f"Missing header: {expected}"

    @pytest.mark.asyncio
    async def test_analyze_all_wallets_button_exists(self, page: Page):
        """Test that 'Analyze All Wallets' button is present in UI.

        AC: Manual trigger button exists in Explorer > Wallets section.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Explorer tab
        await page.click('button:has-text("Explorer")')

        # Open Wallets accordion
        wallets_accordion = page.locator('div[data-testid="Wallets-accordion"]').first
        if await wallets_accordion.is_visible():
            await wallets_accordion.click()

        # Verify "Analyze All Wallets" button exists
        analyze_button = page.locator('button:has-text("Analyze All Wallets")')
        await expect(analyze_button).to_be_visible(timeout=5000)

    @pytest.mark.asyncio
    async def test_analyze_button_triggers_analysis(
        self, page: Page, sample_performance_metrics
    ):
        """Test clicking 'Analyze All Wallets' button triggers analysis.

        AC: Button click initiates analysis and shows status feedback.
        """
        # Mock the analysis function to avoid actual API calls
        with patch(
            "walltrack.core.analysis.analyze_all_wallets"
        ) as mock_analyze_all:
            mock_analyze_all.return_value = {
                "Wallet1111111111111111111111111111111": sample_performance_metrics,
            }

            # Navigate to dashboard
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)

            # Navigate to Explorer tab
            await page.click('button:has-text("Explorer")')

            # Open Wallets accordion
            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            # Find and click "Analyze All Wallets" button
            analyze_button = page.locator('button:has-text("Analyze All Wallets")')
            await analyze_button.click()

            # Verify status changes to "Analyzing..." (or similar)
            status_display = page.locator('input[label="Status"]')
            await expect(status_display).to_contain_text(
                "Analyzing", timeout=2000, ignore_case=True
            )

            # Wait for completion status
            await page.wait_for_timeout(3000)  # Wait for async operation

            # Verify success message appears
            await expect(status_display).to_contain_text(
                "complete", timeout=5000, ignore_case=True
            )

    @pytest.mark.asyncio
    async def test_wallet_detail_panel_shows_performance_metrics(self, page: Page):
        """Test wallet detail panel displays performance metrics.

        AC: Selecting a wallet shows detailed performance metrics in sidebar.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Explorer tab
        await page.click('button:has-text("Explorer")')

        # Open Wallets accordion
        wallets_accordion = page.locator('div[data-testid="Wallets-accordion"]').first
        if await wallets_accordion.is_visible():
            await wallets_accordion.click()

        # Wait for wallet table
        await page.wait_for_selector("table tbody tr", timeout=5000)

        # Click first wallet row
        first_row = page.locator("table tbody tr").first
        await first_row.click()

        # Wait for detail panel to appear
        await page.wait_for_selector("text=Wallet Details", timeout=3000)

        # Verify performance metrics section exists
        detail_panel = page.locator("text=Performance Metrics")
        await expect(detail_panel).to_be_visible(timeout=2000)

        # Verify performance metric fields are present
        expected_fields = [
            "Win Rate",
            "Total PnL",
            "Entry Delay",
            "Total Trades",
            "Confidence",
            "Last Updated",
        ]

        for field in expected_fields:
            field_locator = page.locator(f"text={field}")
            await expect(field_locator).to_be_visible(
                timeout=2000
            ), f"Missing field: {field}"

    @pytest.mark.asyncio
    async def test_performance_metrics_formatting(self, page: Page):
        """Test that performance metrics are formatted correctly in table.

        AC: Win Rate shows %, PnL shows SOL, Entry Delay is human-readable.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Explorer tab
        await page.click('button:has-text("Explorer")')

        # Open Wallets accordion
        wallets_accordion = page.locator('div[data-testid="Wallets-accordion"]').first
        if await wallets_accordion.is_visible():
            await wallets_accordion.click()

        # Wait for wallet table
        await page.wait_for_selector("table tbody tr", timeout=5000)

        # Get first row cells
        first_row = page.locator("table tbody tr").first
        cells = await first_row.locator("td").all_text_contents()

        # Verify formatting patterns (column indices match headers)
        # Win Rate (column 2): Should contain '%'
        win_rate_cell = cells[2] if len(cells) > 2 else ""
        assert "%" in win_rate_cell, f"Win Rate should contain %, got: {win_rate_cell}"

        # PnL (column 3): Should contain 'SOL'
        pnl_cell = cells[3] if len(cells) > 3 else ""
        assert "SOL" in pnl_cell, f"PnL should contain SOL, got: {pnl_cell}"

        # Entry Delay (column 4): Should be human-readable (h/min/s or -)
        delay_cell = cells[4] if len(cells) > 4 else ""
        assert any(
            unit in delay_cell for unit in ["h", "min", "s", "-"]
        ), f"Entry Delay should be human-readable, got: {delay_cell}"

        # Confidence (column 6): Should have emoji
        confidence_cell = cells[6] if len(cells) > 6 else ""
        assert any(
            emoji in confidence_cell for emoji in ["🟢", "🟡", "🟠", "⚪"]
        ), f"Confidence should have emoji, got: {confidence_cell}"


class TestWalletPerformanceAnalysisEmpty:
    """E2E tests for empty state handling."""

    @pytest.mark.asyncio
    async def test_empty_state_when_no_wallets(self, page: Page):
        """Test empty state message when no wallets discovered.

        AC: Clear message guides user to run wallet discovery first.
        """
        # Mock empty wallet list
        with patch(
            "walltrack.data.repositories.wallet_repository.WalletRepository.list_wallets"
        ) as mock_list:
            mock_list.return_value = AsyncMock(return_value=[])

            # Navigate to dashboard
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)

            # Navigate to Explorer tab
            await page.click('button:has-text("Explorer")')

            # Open Wallets accordion
            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            # Verify empty state message
            empty_message = page.locator("text=No wallets discovered yet")
            await expect(empty_message).to_be_visible(timeout=3000)

            # Verify guidance text exists
            guidance = page.locator("text=Run wallet discovery")
            await expect(guidance).to_be_visible(timeout=2000)
