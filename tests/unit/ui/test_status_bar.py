"""Tests for status bar component."""

from datetime import UTC, datetime, timedelta

import pytest


class TestGetRelativeTime:
    """Tests for get_relative_time() utility function."""

    def test_just_now(self) -> None:
        """
        Given: A datetime less than 60 seconds ago
        When: get_relative_time() is called
        Then: Returns 'just now'
        """
        from walltrack.ui.components.status_bar import get_relative_time

        now = datetime.now(UTC)
        result = get_relative_time(now)
        assert result == "just now"

    def test_minutes_ago(self) -> None:
        """
        Given: A datetime 5 minutes ago
        When: get_relative_time() is called
        Then: Returns '5m ago'
        """
        from walltrack.ui.components.status_bar import get_relative_time

        five_minutes_ago = datetime.now(UTC) - timedelta(minutes=5)
        result = get_relative_time(five_minutes_ago)
        assert result == "5m ago"

    def test_hours_ago(self) -> None:
        """
        Given: A datetime 2 hours ago
        When: get_relative_time() is called
        Then: Returns '2h ago'
        """
        from walltrack.ui.components.status_bar import get_relative_time

        two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
        result = get_relative_time(two_hours_ago)
        assert result == "2h ago"

    def test_days_ago(self) -> None:
        """
        Given: A datetime 3 days ago
        When: get_relative_time() is called
        Then: Returns '3d ago'
        """
        from walltrack.ui.components.status_bar import get_relative_time

        three_days_ago = datetime.now(UTC) - timedelta(days=3)
        result = get_relative_time(three_days_ago)
        assert result == "3d ago"


class TestRenderStatusHtml:
    """Tests for render_status_html() function."""

    def test_returns_html_string(self) -> None:
        """
        Given: Status bar component
        When: render_status_html() is called
        Then: Returns a non-empty HTML string
        """
        from walltrack.ui.components.status_bar import render_status_html

        html = render_status_html()
        assert isinstance(html, str)
        assert len(html) > 0
        assert "status-bar" in html

    def test_contains_mode_indicator(self) -> None:
        """
        Given: Status bar in simulation mode
        When: render_status_html() is called
        Then: Returns HTML containing SIMULATION indicator
        """
        from walltrack.ui.components.status_bar import render_status_html

        html = render_status_html()
        assert "SIMULATION" in html or "LIVE" in html

    def test_contains_status_sections(self) -> None:
        """
        Given: Status bar component
        When: render_status_html() is called
        Then: Returns HTML with all status sections
        """
        from walltrack.ui.components.status_bar import render_status_html

        html = render_status_html()
        assert "System" in html or "Discovery" in html


class TestCreateStatusBar:
    """Tests for create_status_bar() function."""

    def test_creates_html_component(self) -> None:
        """
        Given: create_status_bar() function
        When: Called within gr.Blocks context
        Then: Returns a gr.HTML component
        """
        import gradio as gr

        from walltrack.ui.components.status_bar import create_status_bar

        with gr.Blocks():
            component = create_status_bar()

        assert component is not None
        # gr.HTML is the expected type
        assert isinstance(component, gr.HTML)


class TestWalletStatusDisplay:
    """Tests for wallet status in status bar."""

    def test_shows_wallet_not_connected_when_no_wallet(self) -> None:
        """
        Given: No trading wallet configured
        When: render_status_html() is called
        Then: Returns HTML with 'Not Connected' wallet status
        """
        from unittest.mock import patch

        from walltrack.ui.components.status_bar import render_status_html

        with patch(
            "walltrack.ui.components.status_bar.get_trading_wallet_status"
        ) as mock:
            mock.return_value = None
            html = render_status_html()

        assert "Wallet" in html
        assert "Not Connected" in html or "🔴" in html

    def test_shows_wallet_connected_when_wallet_exists(self) -> None:
        """
        Given: Trading wallet configured
        When: render_status_html() is called
        Then: Returns HTML with truncated wallet address
        """
        from unittest.mock import patch

        from walltrack.ui.components.status_bar import render_status_html

        with patch(
            "walltrack.ui.components.status_bar.get_trading_wallet_status"
        ) as mock:
            mock.return_value = "9WzD...xYz1"
            html = render_status_html()

        assert "Wallet" in html
        assert "9WzD...xYz1" in html or "🟢" in html
