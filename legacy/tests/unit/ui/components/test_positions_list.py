"""Tests for positions list component."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from walltrack.ui.components.positions_list import (
    EXIT_TYPE_EMOJI,
    format_active_positions,
    format_closed_positions,
    format_duration,
    format_exit_type,
    format_pnl_colored,
)


class TestFormatPnlColored:
    """Tests for format_pnl_colored function."""

    def test_positive_pnl(self) -> None:
        """Test positive P&L formatting."""
        result = format_pnl_colored(50.0)
        assert result == "🟢 +50.00%"

    def test_negative_pnl(self) -> None:
        """Test negative P&L formatting."""
        result = format_pnl_colored(-25.5)
        assert result == "🔴 -25.50%"

    def test_zero_pnl(self) -> None:
        """Test zero P&L formatting."""
        result = format_pnl_colored(0.0)
        assert result == "⚪ 0.00%"

    def test_small_positive(self) -> None:
        """Test small positive P&L."""
        result = format_pnl_colored(0.01)
        assert result == "🟢 +0.01%"


class TestFormatDuration:
    """Tests for format_duration function."""

    def test_minutes(self) -> None:
        """Test duration less than 1 hour."""
        # 30 minutes ago
        entry = (datetime.now(UTC) - timedelta(minutes=30)).isoformat()
        result = format_duration(entry)
        assert "m" in result

    def test_hours(self) -> None:
        """Test duration between 1 and 24 hours."""
        # 5 hours ago
        entry = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        result = format_duration(entry)
        assert "h" in result

    def test_days(self) -> None:
        """Test duration more than 24 hours."""
        # 2 days ago
        entry = (datetime.now(UTC) - timedelta(days=2)).isoformat()
        result = format_duration(entry)
        assert "d" in result

    def test_none_entry_time(self) -> None:
        """Test None entry time returns dash."""
        result = format_duration(None)
        assert result == "-"

    def test_invalid_time(self) -> None:
        """Test invalid time format returns dash."""
        result = format_duration("invalid-date")
        assert result == "-"


class TestFormatExitType:
    """Tests for format_exit_type function."""

    def test_known_exit_types(self) -> None:
        """Test all known exit type emojis."""
        for exit_type, emoji in EXIT_TYPE_EMOJI.items():
            result = format_exit_type(exit_type)
            assert result == f"{emoji} {exit_type}"

    def test_unknown_exit_type(self) -> None:
        """Test unknown exit type uses question mark."""
        result = format_exit_type("unknown_type")
        assert result == "❓ unknown_type"

    def test_none_exit_type(self) -> None:
        """Test None exit type."""
        result = format_exit_type(None)
        assert result == "❓ unknown"


class TestFormatActivePositions:
    """Tests for format_active_positions function."""

    def test_empty_list(self) -> None:
        """Test empty positions list."""
        result = format_active_positions([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_single_position(self) -> None:
        """Test single active position formatting."""
        positions: list[dict[str, Any]] = [
            {
                "id": "abc12345-1234-1234-1234-123456789012",
                "token_symbol": "PEPE",
                "token_address": "0x1234567890abcdef",
                "entry_price": 0.001,
                "current_price": 0.0015,
                "pnl_pct": 50.0,
                "size_sol": 1.5,
                "exit_strategy_id": "balanced",
                "entry_time": datetime.now(UTC).isoformat(),
            }
        ]

        result = format_active_positions(positions)

        assert len(result) == 1
        assert result.iloc[0]["Token"] == "PEPE"
        assert "🟢" in result.iloc[0]["P&L"]
        assert "SOL" in result.iloc[0]["Size"]
        assert result.iloc[0]["_full_id"] == "abc12345-1234-1234-1234-123456789012"

    def test_position_with_strategy_join(self) -> None:
        """Test position with joined strategy data."""
        positions: list[dict[str, Any]] = [
            {
                "id": "abc12345-1234-1234-1234-123456789012",
                "token_symbol": "DOGE",
                "entry_price": 0.001,
                "current_price": 0.001,
                "pnl_pct": 0.0,
                "size_sol": 2.0,
                "exit_strategies": {"id": "strat-1", "name": "Aggressive"},
                "entry_time": datetime.now(UTC).isoformat(),
            }
        ]

        result = format_active_positions(positions)

        assert result.iloc[0]["Strategy"] == "Aggressive"

    def test_position_without_symbol(self) -> None:
        """Test position using truncated address when no symbol."""
        positions: list[dict[str, Any]] = [
            {
                "id": "abc12345-1234-1234-1234-123456789012",
                "token_address": "0xabcdef1234567890",
                "entry_price": 0.001,
                "pnl_pct": -10.0,
                "size_sol": 1.0,
            }
        ]

        result = format_active_positions(positions)

        assert "..." in result.iloc[0]["Token"]


class TestFormatClosedPositions:
    """Tests for format_closed_positions function."""

    def test_empty_list(self) -> None:
        """Test empty closed positions list."""
        result = format_closed_positions([])
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_single_closed_position(self) -> None:
        """Test single closed position formatting."""
        positions: list[dict[str, Any]] = [
            {
                "id": "xyz12345-1234-1234-1234-123456789012",
                "token_symbol": "SHIB",
                "entry_price": 0.001,
                "exit_price": 0.002,
                "pnl_pct": 100.0,
                "exit_type": "take_profit",
                "exit_strategy_id": "conservative",
                "exit_time": "2025-12-25T10:00:00Z",
            }
        ]

        result = format_closed_positions(positions)

        assert len(result) == 1
        assert result.iloc[0]["Token"] == "SHIB"
        assert "🎯" in result.iloc[0]["Exit Type"]
        assert result.iloc[0]["Date"] == "2025-12-25"

    def test_different_exit_types(self) -> None:
        """Test formatting of different exit types."""
        exit_types = ["take_profit", "stop_loss", "trailing_stop", "manual"]
        positions: list[dict[str, Any]] = [
            {
                "id": f"pos-{i}-1234-1234-1234-123456789012",
                "token_symbol": f"TOKEN{i}",
                "entry_price": 0.001,
                "exit_price": 0.001,
                "pnl_pct": 0.0,
                "exit_type": exit_type,
                "exit_time": "2025-12-25T10:00:00Z",
            }
            for i, exit_type in enumerate(exit_types)
        ]

        result = format_closed_positions(positions)

        assert "🎯" in result.iloc[0]["Exit Type"]
        assert "🛑" in result.iloc[1]["Exit Type"]
        assert "📉" in result.iloc[2]["Exit Type"]
        assert "✋" in result.iloc[3]["Exit Type"]


class TestFetchPositions:
    """Tests for fetch_active_positions and fetch_closed_positions."""

    @pytest.mark.asyncio
    async def test_fetch_active_positions_success(self) -> None:
        """Test successful fetch of active positions."""
        from walltrack.ui.components.positions_list import fetch_active_positions

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [{"id": "pos-1", "token_symbol": "TEST"}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_active_positions()

        assert len(result) == 1
        assert result[0]["id"] == "pos-1"

    @pytest.mark.asyncio
    async def test_fetch_active_positions_error(self) -> None:
        """Test fetch handles errors gracefully."""
        from walltrack.ui.components.positions_list import fetch_active_positions

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await fetch_active_positions()

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_closed_positions_success(self) -> None:
        """Test successful fetch of closed positions."""
        from walltrack.ui.components.positions_list import fetch_closed_positions

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "positions": [{"id": "closed-1", "exit_type": "take_profit"}]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_closed_positions(limit=5)

        assert len(result) == 1
        assert result[0]["exit_type"] == "take_profit"


class TestActionHandlers:
    """Tests for action button handlers."""

    def test_make_action_handler_with_callback(self) -> None:
        """Test action handler calls callback."""
        from walltrack.ui.components.positions_list import _make_action_handler

        callback = MagicMock()
        handler = _make_action_handler("Testing", callback)

        result = handler("position-123")

        callback.assert_called_once_with("position-123")
        assert "Testing" in result
        # Handler shows first 8 chars: "position"
        assert "position" in result

    def test_make_action_handler_no_position(self) -> None:
        """Test action handler with no position selected."""
        from walltrack.ui.components.positions_list import _make_action_handler

        callback = MagicMock()
        handler = _make_action_handler("Testing", callback)

        result = handler(None)

        callback.assert_not_called()
        assert result == "Select a position first"

    def test_make_action_handler_without_callback(self) -> None:
        """Test action handler without callback."""
        from walltrack.ui.components.positions_list import _make_action_handler

        handler = _make_action_handler("Testing", None)

        result = handler("position-123")

        assert "Testing" in result


class TestLoadPositionsData:
    """Tests for load_positions_data function."""

    @pytest.mark.asyncio
    async def test_load_both_positions(self) -> None:
        """Test loading both active and closed positions."""
        from walltrack.ui.components.positions_list import load_positions_data

        with (
            patch(
                "walltrack.ui.components.positions_list.fetch_active_positions",
                new_callable=AsyncMock,
            ) as mock_active,
            patch(
                "walltrack.ui.components.positions_list.fetch_closed_positions",
                new_callable=AsyncMock,
            ) as mock_closed,
        ):
            mock_active.return_value = [
                {
                    "id": "active-1",
                    "token_symbol": "ACT",
                    "entry_price": 0.001,
                    "pnl_pct": 10.0,
                    "size_sol": 1.0,
                }
            ]
            mock_closed.return_value = [
                {
                    "id": "closed-1",
                    "token_symbol": "CLS",
                    "entry_price": 0.001,
                    "exit_price": 0.002,
                    "pnl_pct": 100.0,
                    "exit_type": "take_profit",
                    "exit_time": "2025-12-25T10:00:00Z",
                }
            ]

            active_df, closed_df = await load_positions_data()

        assert len(active_df) == 1
        assert len(closed_df) == 1
        assert active_df.iloc[0]["Token"] == "ACT"
        assert closed_df.iloc[0]["Token"] == "CLS"
