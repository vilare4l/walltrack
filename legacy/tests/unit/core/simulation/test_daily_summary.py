"""Tests for daily simulation summary."""

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestGenerateDailySummary:
    """Tests for generate_daily_summary function."""

    async def test_returns_summary_dict(self) -> None:
        """Test that daily summary returns expected keys."""
        mock_portfolio = MagicMock()
        mock_portfolio.total_pnl = Decimal("150.50")
        mock_portfolio.total_unrealized_pnl = Decimal("100.00")
        mock_portfolio.total_realized_pnl = Decimal("50.50")
        mock_portfolio.position_count = 3

        mock_calculator = MagicMock()
        mock_calculator.calculate_portfolio_pnl = AsyncMock(return_value=mock_portfolio)

        mock_supabase = MagicMock()
        mock_supabase.select = AsyncMock(return_value=[])

        with patch(
            "walltrack.core.simulation.daily_summary.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.core.simulation.daily_summary.get_pnl_calculator",
                return_value=mock_calculator,
            ):
                from walltrack.core.simulation.daily_summary import (
                    generate_daily_summary,
                )

                summary = await generate_daily_summary()

                assert "date" in summary
                assert "trades_count" in summary
                assert "wins" in summary
                assert "losses" in summary
                assert "win_rate" in summary
                assert "total_pnl" in summary
                assert summary["total_pnl"] == 150.50

    async def test_calculates_win_rate(self) -> None:
        """Test that win rate is calculated correctly."""
        mock_portfolio = MagicMock()
        mock_portfolio.total_pnl = Decimal("100")
        mock_portfolio.total_unrealized_pnl = Decimal("50")
        mock_portfolio.total_realized_pnl = Decimal("50")
        mock_portfolio.position_count = 2

        mock_calculator = MagicMock()
        mock_calculator.calculate_portfolio_pnl = AsyncMock(return_value=mock_portfolio)

        # Create mock trades - 3 wins, 1 loss
        today = datetime.now(UTC).isoformat()
        mock_trades = [
            {"executed_at": today, "pnl": 10.0},
            {"executed_at": today, "pnl": 20.0},
            {"executed_at": today, "pnl": 5.0},
            {"executed_at": today, "pnl": -5.0},
        ]

        mock_supabase = MagicMock()
        mock_supabase.select = AsyncMock(return_value=mock_trades)

        with patch(
            "walltrack.core.simulation.daily_summary.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.core.simulation.daily_summary.get_pnl_calculator",
                return_value=mock_calculator,
            ):
                from walltrack.core.simulation.daily_summary import (
                    generate_daily_summary,
                )

                summary = await generate_daily_summary()

                assert summary["trades_count"] == 4
                assert summary["wins"] == 3
                assert summary["losses"] == 1
                assert summary["win_rate"] == 75.0  # 3/4 * 100


class TestSendSummaryAlert:
    """Tests for send_summary_alert function."""

    async def test_formats_message_correctly(self) -> None:
        """Test that alert message is formatted correctly."""
        from walltrack.core.simulation.daily_summary import send_summary_alert

        summary = {
            "date": "2025-12-21",
            "trades_count": 10,
            "wins": 7,
            "losses": 3,
            "win_rate": 70.0,
            "total_pnl": 150.50,
            "realized_pnl": 100.00,
            "unrealized_pnl": 50.50,
            "open_positions": 3,
        }

        # Just test it doesn't raise (no webhook configured)
        with patch(
            "walltrack.core.simulation.daily_summary.get_settings"
        ) as mock_settings:
            mock_settings.return_value = MagicMock(
                discord_webhook_url=None,
                telegram_bot_token=None,
                telegram_chat_id=None,
            )

            # Should not raise
            await send_summary_alert(summary)
