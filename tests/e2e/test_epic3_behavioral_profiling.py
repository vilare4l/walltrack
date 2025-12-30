"""E2E tests for Epic 3: Wallet Behavioral Profiling (Story 3.3).

Tests the complete UI flow for behavioral profiling:
- Config page "Run Behavioral Profiling" button is functional
- Sidebar displays behavioral profile with badges (AC2, AC3)
- Status feedback during profiling
- Insufficient data message for <10 trades (AC4)
"""

import os
from unittest.mock import AsyncMock, patch

import pytest
from playwright.async_api import Page, expect

from walltrack.core.behavioral.profiler import BehavioralProfile
from walltrack.data.models.wallet import Wallet


@pytest.fixture
def sample_behavioral_profile():
    """Sample behavioral profile for testing."""
    from decimal import Decimal

    return BehavioralProfile(
        wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        confidence="high",
        total_trades=50,
        position_size_style="medium",
        position_size_avg=Decimal("2.5"),
        hold_duration_style="day_trader",
        hold_duration_avg=21600,  # 6 hours
    )


@pytest.fixture
def sample_wallet_with_profile():
    """Sample wallet with behavioral profile data."""
    from datetime import UTC, datetime
    from decimal import Decimal

    return Wallet(
        wallet_address="9xQeWvG816bUx9EPjHmaT23yvVM2ZWbrrpZb9PusVFin",
        discovery_date=datetime.now(UTC),
        token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        score=85.5,
        win_rate=75.0,
        pnl_total=Decimal("12.5"),
        entry_delay_seconds=3600,
        total_trades=50,
        metrics_last_updated=datetime.now(UTC),
        metrics_confidence="high",
        decay_status="ok",
        is_blacklisted=False,
        # Behavioral profiling fields
        position_size_style="medium",
        position_size_avg=Decimal("2.5"),
        hold_duration_avg=21600,
        hold_duration_style="day_trader",
        behavioral_last_updated=datetime.now(UTC),
        behavioral_confidence="high",
    )


@pytest.mark.skipif(
    not os.getenv("HELIUS_API_KEY"), reason="HELIUS_API_KEY not set"
)
class TestBehavioralProfilingE2E:
    """E2E tests for behavioral profiling UI."""

    @pytest.mark.asyncio
    async def test_config_page_has_profiling_button(self, page: Page):
        """Test that Config page has 'Run Behavioral Profiling' button.

        AC: Manual trigger button exists in Config > Behavioral Profiling section.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Config tab
        await page.click('button:has-text("Config")')

        # Open Behavioral Profiling accordion
        profiling_accordion = page.locator('div:has-text("Behavioral Profiling")')
        if await profiling_accordion.is_visible():
            await profiling_accordion.click()

        # Verify "Run Behavioral Profiling" button exists
        profiling_button = page.locator('button:has-text("Run Behavioral Profiling")')
        await expect(profiling_button).to_be_visible(timeout=5000)

    @pytest.mark.asyncio
    async def test_profiling_button_triggers_analysis(
        self, page: Page, sample_behavioral_profile
    ):
        """Test clicking 'Run Behavioral Profiling' button triggers analysis.

        AC: Button click initiates profiling and shows status feedback.
        """
        # Mock the profiling function to avoid actual API calls
        with patch(
            "walltrack.core.behavioral.profiler.BehavioralProfiler.analyze"
        ) as mock_analyze:
            mock_analyze.return_value = sample_behavioral_profile

            # Navigate to dashboard
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)

            # Navigate to Config tab
            await page.click('button:has-text("Config")')

            # Open Behavioral Profiling accordion
            profiling_accordion = page.locator(
                'div:has-text("Behavioral Profiling")'
            )
            if await profiling_accordion.is_visible():
                await profiling_accordion.click()

            # Find and click "Run Behavioral Profiling" button
            profiling_button = page.locator(
                'button:has-text("Run Behavioral Profiling")'
            )
            await profiling_button.click()

            # Verify status changes to "Profiling..." (or similar)
            status_display = page.locator('input[label="Status"]')
            await expect(status_display).to_contain_text(
                "Profiling", timeout=2000, ignore_case=True
            )

            # Wait for completion status
            await page.wait_for_timeout(3000)  # Wait for async operation

            # Verify success message appears
            await expect(status_display).to_contain_text(
                "profiled", timeout=5000, ignore_case=True
            )

    @pytest.mark.asyncio
    async def test_sidebar_displays_behavioral_profile(
        self, page: Page, sample_wallet_with_profile
    ):
        """Test sidebar displays behavioral profile with badges (AC2, AC3).

        AC2: Position Size badges (🟢 small, 🟡 medium, 🔴 large)
        AC3: Hold Duration badges (⚡ scalper, 📊 day trader, 📈 swing, 🎯 position)
        """
        # Mock wallet repository to return wallet with profile
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

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

            # Wait for wallet table
            await page.wait_for_selector("table tbody tr", timeout=5000)

            # Click first wallet row to open sidebar
            first_row = page.locator("table tbody tr").first
            await first_row.click()

            # Wait for sidebar to appear
            await page.wait_for_selector("text=🎯 Behavioral Profile", timeout=3000)

            # Verify Behavioral Profile section exists
            profile_section = page.locator("text=🎯 Behavioral Profile")
            await expect(profile_section).to_be_visible(timeout=2000)

            # AC2: Verify Position Size badge (🟡 for medium)
            position_badge = page.locator("text=🟡")
            await expect(position_badge).to_be_visible(
                timeout=2000
            ), "Position size badge missing"

            position_text = page.locator("text=MEDIUM")
            await expect(position_text).to_be_visible(
                timeout=2000
            ), "Position size style missing"

            # Verify avg position size displayed
            avg_size_text = page.locator("text=Avg Size: **2.5")
            await expect(avg_size_text).to_be_visible(
                timeout=2000
            ), "Average position size missing"

            # AC3: Verify Hold Duration badge (📊 for day_trader)
            hold_badge = page.locator("text=📊")
            await expect(hold_badge).to_be_visible(
                timeout=2000
            ), "Hold duration badge missing"

            hold_text = page.locator("text=DAY TRADER")
            await expect(hold_text).to_be_visible(
                timeout=2000
            ), "Hold duration style missing"

            # Verify avg hold time displayed (human-readable)
            hold_time_text = page.locator("text=Avg Hold Time:")
            await expect(hold_time_text).to_be_visible(
                timeout=2000
            ), "Average hold time missing"

            # Verify confidence badge (✅ for high)
            confidence_badge = page.locator("text=✅")
            await expect(confidence_badge).to_be_visible(
                timeout=2000
            ), "Confidence badge missing"

    @pytest.mark.asyncio
    async def test_sidebar_shows_insufficient_data_message(self, page: Page):
        """Test sidebar shows 'Insufficient data' for wallets with <10 trades (AC4).

        AC4: Wallets with <10 trades display appropriate message.
        """
        from datetime import UTC, datetime
        from decimal import Decimal

        # Create wallet with insufficient data (no behavioral profile)
        wallet_insufficient_data = Wallet(
            wallet_address="TestWallet111111111111111111111111111",
            discovery_date=datetime.now(UTC),
            token_source="EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
            score=50.0,
            win_rate=None,
            pnl_total=None,
            entry_delay_seconds=None,
            total_trades=5,  # < 10 trades
            metrics_last_updated=None,
            metrics_confidence="unknown",
            decay_status="ok",
            is_blacklisted=False,
            # No behavioral profile fields set
            position_size_style=None,
            position_size_avg=None,
            hold_duration_avg=None,
            hold_duration_style=None,
            behavioral_last_updated=None,
            behavioral_confidence="unknown",
        )

        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = wallet_insufficient_data

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

            # Wait for wallet table
            await page.wait_for_selector("table tbody tr", timeout=5000)

            # Click first wallet row to open sidebar
            first_row = page.locator("table tbody tr").first
            await first_row.click()

            # Wait for sidebar to appear
            await page.wait_for_selector("text=🎯 Behavioral Profile", timeout=3000)

            # Verify "Insufficient data" message
            insufficient_msg = page.locator(
                "text=Insufficient data for behavioral analysis"
            )
            await expect(insufficient_msg).to_be_visible(
                timeout=2000
            ), "Insufficient data message missing for <10 trades"

            # Verify requirement message
            requirement_msg = page.locator("text=requires 10+ trades")
            await expect(requirement_msg).to_be_visible(
                timeout=2000
            ), "Trade requirement message missing"

    @pytest.mark.asyncio
    async def test_profiling_status_feedback(self, page: Page):
        """Test profiling status feedback during batch operation.

        AC: Status textbox shows progress during profiling (profiled/skipped/errors).
        """
        # Navigate to Config page
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Config tab
        await page.click('button:has-text("Config")')

        # Open Behavioral Profiling accordion
        profiling_accordion = page.locator('div:has-text("Behavioral Profiling")')
        if await profiling_accordion.is_visible():
            await profiling_accordion.click()

        # Verify status textbox exists and is "Ready"
        status_display = page.locator('input[label="Status"]')
        await expect(status_display).to_have_value("Ready", timeout=2000)

        # Click profiling button
        profiling_button = page.locator('button:has-text("Run Behavioral Profiling")')
        await profiling_button.click()

        # Verify status changes during execution
        await expect(status_display).to_contain_text("Profiling", timeout=2000)

        # Wait for completion
        await page.wait_for_timeout(3000)

        # Verify final status shows results (profiled/skipped counts)
        status_text = await status_display.input_value()
        assert any(
            keyword in status_text.lower()
            for keyword in ["profiled", "skipped", "complete"]
        ), f"Status should show results, got: {status_text}"


class TestBehavioralProfilingEmpty:
    """E2E tests for empty state handling."""

    @pytest.mark.asyncio
    async def test_profiling_with_no_wallets(self, page: Page):
        """Test profiling button behavior when no wallets exist.

        AC: Clear message when no wallets to profile.
        """
        # Mock empty wallet list
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_all"
        ) as mock_list:
            mock_list.return_value = AsyncMock(return_value=[])

            # Navigate to Config page
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)

            # Navigate to Config tab
            await page.click('button:has-text("Config")')

            # Open Behavioral Profiling accordion
            profiling_accordion = page.locator(
                'div:has-text("Behavioral Profiling")'
            )
            if await profiling_accordion.is_visible():
                await profiling_accordion.click()

            # Click profiling button
            profiling_button = page.locator(
                'button:has-text("Run Behavioral Profiling")'
            )
            await profiling_button.click()

            # Wait for status update
            await page.wait_for_timeout(2000)

            # Verify status shows "no wallets" or similar
            status_display = page.locator('input[label="Status"]')
            status_text = await status_display.input_value()
            assert any(
                keyword in status_text.lower() for keyword in ["no wallet", "0 wallet"]
            ), f"Status should indicate no wallets, got: {status_text}"
