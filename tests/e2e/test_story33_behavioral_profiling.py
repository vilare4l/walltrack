"""E2E tests for Story 3.3: Wallet Behavioral Profiling.

Tests the complete UI flow for behavioral profiling configuration and display:
- Config page "Behavioral Profiling Criteria" section with sliders (Task 4b UI)
- Explorer sidebar "🧠 Behavioral Profile" section with table display (Task 5)
- Verify criteria can be configured and saved
- Verify behavioral profile displays correctly with badges
"""

import os
from unittest.mock import patch

import pytest
from playwright.async_api import Page, expect


@pytest.fixture
def sample_wallet_with_profile():
    """Sample wallet with behavioral profile data."""
    from datetime import UTC, datetime
    from decimal import Decimal

    from walltrack.data.models.wallet import Wallet

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
        hold_duration_avg=21600,  # 6 hours
        hold_duration_style="day_trader",
        behavioral_last_updated=datetime.now(UTC),
        behavioral_confidence="high",
    )


@pytest.mark.skipif(
    not os.getenv("HELIUS_API_KEY"), reason="HELIUS_API_KEY not set"
)
class TestBehavioralProfilingConfigUI:
    """E2E tests for behavioral profiling configuration UI (Task 4b)."""

    @pytest.mark.asyncio
    async def test_config_criteria_section_exists(self, page: Page):
        """Test that Config page has 'Behavioral Profiling Criteria' section.

        AC: Accordion section with sliders for position size, hold duration, and confidence thresholds.
        """
        # Navigate to dashboard
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)

        # Navigate to Config tab
        await page.click('button:has-text("Config")')
        await page.wait_for_timeout(1000)

        # Look for "Behavioral Profiling Criteria" accordion
        criteria_accordion = page.locator('text="Behavioral Profiling Criteria"')
        await expect(criteria_accordion).to_be_visible(
            timeout=5000
        ), "Behavioral Profiling Criteria section missing"

    @pytest.mark.asyncio
    async def test_config_criteria_sliders_present(self, page: Page):
        """Test that all 8 configuration inputs are present.

        AC: 2 position size sliders, 3 hold duration sliders, 3 confidence number inputs.
        """
        # Navigate to Config page
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)
        await page.click('button:has-text("Config")')
        await page.wait_for_timeout(1000)

        # Open Behavioral Profiling Criteria accordion
        criteria_accordion = page.locator('text="Behavioral Profiling Criteria"')
        await criteria_accordion.click()
        await page.wait_for_timeout(500)

        # Verify Position Size sliders
        pos_small_label = page.locator('text="Position Size: Small Max (SOL)"')
        await expect(pos_small_label).to_be_visible(
            timeout=3000
        ), "Position Size Small Max slider missing"

        pos_medium_label = page.locator('text="Position Size: Medium Max (SOL)"')
        await expect(pos_medium_label).to_be_visible(
            timeout=3000
        ), "Position Size Medium Max slider missing"

        # Verify Hold Duration sliders
        hold_scalper_label = page.locator('text="Hold Duration: Scalper Max"')
        await expect(hold_scalper_label).to_be_visible(
            timeout=3000
        ), "Hold Duration Scalper Max slider missing"

        hold_day_label = page.locator('text="Hold Duration: Day Trader Max"')
        await expect(hold_day_label).to_be_visible(
            timeout=3000
        ), "Hold Duration Day Trader Max slider missing"

        hold_swing_label = page.locator('text="Hold Duration: Swing Trader Max"')
        await expect(hold_swing_label).to_be_visible(
            timeout=3000
        ), "Hold Duration Swing Trader Max slider missing"

        # Verify Confidence threshold inputs
        conf_high_label = page.locator('text="Confidence: High Threshold"')
        await expect(conf_high_label).to_be_visible(
            timeout=3000
        ), "Confidence High Threshold input missing"

        conf_medium_label = page.locator('text="Confidence: Medium Threshold"')
        await expect(conf_medium_label).to_be_visible(
            timeout=3000
        ), "Confidence Medium Threshold input missing"

        conf_low_label = page.locator('text="Confidence: Low Threshold"')
        await expect(conf_low_label).to_be_visible(
            timeout=3000
        ), "Confidence Low Threshold input missing"

    @pytest.mark.asyncio
    async def test_config_criteria_save_button_exists(self, page: Page):
        """Test that 'Update Behavioral Criteria' button exists.

        AC: Button to save criteria changes.
        """
        # Navigate to Config page
        await page.goto("http://localhost:7860")
        await page.wait_for_selector("text=WallTrack", timeout=10000)
        await page.click('button:has-text("Config")')
        await page.wait_for_timeout(1000)

        # Open Behavioral Profiling Criteria accordion
        criteria_accordion = page.locator('text="Behavioral Profiling Criteria"')
        await criteria_accordion.click()
        await page.wait_for_timeout(500)

        # Verify "Update Behavioral Criteria" button
        save_button = page.locator('button:has-text("Update Behavioral Criteria")')
        await expect(save_button).to_be_visible(
            timeout=3000
        ), "Update Behavioral Criteria button missing"


@pytest.mark.skipif(
    not os.getenv("HELIUS_API_KEY"), reason="HELIUS_API_KEY not set"
)
class TestBehavioralProfilingExplorerSidebar:
    """E2E tests for behavioral profile display in Explorer sidebar (Task 5)."""

    @pytest.mark.asyncio
    async def test_sidebar_behavioral_profile_section_exists(
        self, page: Page, sample_wallet_with_profile
    ):
        """Test that Explorer sidebar has '🧠 Behavioral Profile' section.

        AC: Section with emoji 🧠 displays in sidebar when wallet is selected.
        """
        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

            # Navigate to Explorer
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)
            await page.click('button:has-text("Explorer")')
            await page.wait_for_timeout(1000)

            # Open Wallets accordion
            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            # Wait for wallet table and select first wallet
            await page.wait_for_selector("table tbody tr", timeout=5000)
            first_row = page.locator("table tbody tr").first
            await first_row.click()

            # Wait for sidebar and verify Behavioral Profile section
            await page.wait_for_timeout(1000)
            profile_section = page.locator('text="🧠 Behavioral Profile"')
            await expect(profile_section).to_be_visible(
                timeout=3000
            ), "🧠 Behavioral Profile section missing from sidebar"

    @pytest.mark.asyncio
    async def test_sidebar_displays_position_size_badge(
        self, page: Page, sample_wallet_with_profile
    ):
        """Test sidebar displays Position Size badge and value.

        AC: Position Size badge (🟢 Small / 🟡 Medium / 🔴 Large) + avg SOL value displayed.
        """
        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

            # Navigate to Explorer and select wallet
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)
            await page.click('button:has-text("Explorer")')
            await page.wait_for_timeout(1000)

            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            await page.wait_for_selector("table tbody tr", timeout=5000)
            first_row = page.locator("table tbody tr").first
            await first_row.click()
            await page.wait_for_timeout(1000)

            # Verify Position Size badge (🟡 Medium for our sample wallet)
            position_badge = page.locator('text="🟡 Medium"')
            await expect(position_badge).to_be_visible(
                timeout=3000
            ), "Position Size badge (🟡 Medium) missing"

            # Verify avg position size value (2.50 SOL)
            position_value = page.locator('text="2.50 SOL"')
            await expect(position_value).to_be_visible(
                timeout=3000
            ), "Position Size avg value (2.50 SOL) missing"

    @pytest.mark.asyncio
    async def test_sidebar_displays_hold_duration_badge(
        self, page: Page, sample_wallet_with_profile
    ):
        """Test sidebar displays Hold Duration badge and value.

        AC: Hold Duration badge (⚡ Scalper / 📊 Day Trader / 📈 Swing / 💎 Position) + human-readable duration.
        """
        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

            # Navigate to Explorer and select wallet
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)
            await page.click('button:has-text("Explorer")')
            await page.wait_for_timeout(1000)

            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            await page.wait_for_selector("table tbody tr", timeout=5000)
            first_row = page.locator("table tbody tr").first
            await first_row.click()
            await page.wait_for_timeout(1000)

            # Verify Hold Duration badge (📊 Day Trader for our sample wallet)
            hold_badge = page.locator('text="📊 Day Trader"')
            await expect(hold_badge).to_be_visible(
                timeout=3000
            ), "Hold Duration badge (📊 Day Trader) missing"

            # Verify human-readable duration (21600s = 6h)
            hold_duration = page.locator('text="6h"')
            await expect(hold_duration).to_be_visible(
                timeout=3000
            ), "Hold Duration value (6h) missing"

    @pytest.mark.asyncio
    async def test_sidebar_displays_behavioral_confidence(
        self, page: Page, sample_wallet_with_profile
    ):
        """Test sidebar displays Behavioral Confidence level.

        AC: Confidence level (High/Medium/Low/Unknown) displayed in table.
        """
        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

            # Navigate to Explorer and select wallet
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)
            await page.click('button:has-text("Explorer")')
            await page.wait_for_timeout(1000)

            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            await page.wait_for_selector("table tbody tr", timeout=5000)
            first_row = page.locator("table tbody tr").first
            await first_row.click()
            await page.wait_for_timeout(1000)

            # Verify Confidence level (High for our sample wallet)
            confidence_display = page.locator('text="High"')
            await expect(confidence_display).to_be_visible(
                timeout=3000
            ), "Behavioral Confidence (High) missing"

    @pytest.mark.asyncio
    async def test_sidebar_table_format(self, page: Page, sample_wallet_with_profile):
        """Test sidebar uses table format for Behavioral Profile metrics.

        AC: Metrics displayed in a markdown table (| Metric | Value |).
        """
        # Mock wallet repository
        with patch(
            "walltrack.data.supabase.repositories.wallet_repo.WalletRepository.get_by_address"
        ) as mock_get:
            mock_get.return_value = sample_wallet_with_profile

            # Navigate to Explorer and select wallet
            await page.goto("http://localhost:7860")
            await page.wait_for_selector("text=WallTrack", timeout=10000)
            await page.click('button:has-text("Explorer")')
            await page.wait_for_timeout(1000)

            wallets_accordion = page.locator(
                'div[data-testid="Wallets-accordion"]'
            ).first
            if await wallets_accordion.is_visible():
                await wallets_accordion.click()

            await page.wait_for_selector("table tbody tr", timeout=5000)
            first_row = page.locator("table tbody tr").first
            await first_row.click()
            await page.wait_for_timeout(1000)

            # Verify table headers exist (Position Size, Hold Duration, Confidence, Last Analyzed)
            # These should be bolded in markdown (but rendered as regular text in HTML)
            position_size_header = page.locator('text="Position Size"')
            await expect(position_size_header).to_be_visible(
                timeout=3000
            ), "Position Size table row missing"

            hold_duration_header = page.locator('text="Hold Duration"')
            await expect(hold_duration_header).to_be_visible(
                timeout=3000
            ), "Hold Duration table row missing"

            confidence_header = page.locator('text="Confidence"')
            await expect(confidence_header).to_be_visible(
                timeout=3000
            ), "Confidence table row missing"

            last_analyzed_header = page.locator('text="Last Analyzed"')
            await expect(last_analyzed_header).to_be_visible(
                timeout=3000
            ), "Last Analyzed table row missing"
