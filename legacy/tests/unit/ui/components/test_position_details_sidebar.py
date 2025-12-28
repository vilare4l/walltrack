"""Tests for position details sidebar component."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.ui.components.position_details_sidebar import (
    EXIT_TYPE_EMOJI,
    _calculate_next_tp,
    _format_duration,
    fetch_position_details,
    open_sidebar,
    render_active_position,
    render_closed_position,
)


class TestCalculateNextTp:
    """Tests for _calculate_next_tp function."""

    def test_no_rules(self) -> None:
        """Test with no rules."""
        result = _calculate_next_tp([], 10.0)
        assert result is None

    def test_no_tp_rules(self) -> None:
        """Test with rules but no take_profit type."""
        rules = [{"rule_type": "stop_loss", "trigger_pct": -10}]
        result = _calculate_next_tp(rules, 10.0)
        assert result is None

    def test_next_tp_found(self) -> None:
        """Test finding next TP level."""
        rules = [
            {"rule_type": "take_profit", "trigger_pct": 50},
            {"rule_type": "take_profit", "trigger_pct": 100},
        ]
        result = _calculate_next_tp(rules, 30.0)
        assert result is not None
        assert "20.0%" in result
        assert "50%" in result

    def test_all_tps_reached(self) -> None:
        """Test when all TP levels passed."""
        rules = [
            {"rule_type": "take_profit", "trigger_pct": 50},
            {"rule_type": "take_profit", "trigger_pct": 100},
        ]
        result = _calculate_next_tp(rules, 150.0)
        assert result is None


class TestFormatDuration:
    """Tests for _format_duration function."""

    def test_current_time(self) -> None:
        """Test duration to current time."""
        entry = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
        result = _format_duration(entry)
        assert "hours" in result
        assert "5" in result

    def test_with_exit_time(self) -> None:
        """Test duration with exit time."""
        entry = "2025-12-25T10:00:00Z"
        exit_time = "2025-12-25T15:00:00Z"
        result = _format_duration(entry, exit_time)
        assert "5.0 hours" == result

    def test_invalid_time(self) -> None:
        """Test with invalid time."""
        result = _format_duration("invalid")
        assert result == "N/A"


class TestRenderActivePosition:
    """Tests for render_active_position function."""

    def test_basic_render(self) -> None:
        """Test basic active position rendering."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "current_price": "0.0015",
            "pnl_pct": 50.0,
            "pnl_sol": 0.5,
            "size_sol": 1.0,
            "entry_time": datetime.now(UTC).isoformat(),
            "exit_strategies": {"name": "Balanced", "rules": []},
            "signals": {"wallet_address": "abc123wallet", "score": 0.85},
        }

        result = render_active_position(position)

        assert "Performance" in result
        assert "Balanced" in result
        assert "0.001" in result
        assert "🟢" in result  # Positive P&L

    def test_negative_pnl(self) -> None:
        """Test rendering with negative P&L."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "current_price": "0.0005",
            "pnl_pct": -50.0,
            "pnl_sol": -0.5,
            "size_sol": 1.0,
            "entry_time": datetime.now(UTC).isoformat(),
        }

        result = render_active_position(position)

        assert "🔴" in result  # Negative P&L

    def test_with_strategy_rules(self) -> None:
        """Test rendering with strategy rules."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "current_price": "0.0012",
            "pnl_pct": 20.0,
            "size_sol": 1.0,
            "entry_time": datetime.now(UTC).isoformat(),
            "exit_strategies": {
                "name": "Aggressive",
                "rules": [
                    {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50},
                    {"rule_type": "take_profit", "trigger_pct": 100, "exit_pct": 100},
                ],
            },
        }

        result = render_active_position(position)

        assert "take_profit" in result
        assert "50" in result
        assert "⏳" in result  # Not yet reached

    def test_with_next_tp(self) -> None:
        """Test rendering shows next TP info."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "current_price": "0.001",
            "pnl_pct": 0.0,
            "size_sol": 1.0,
            "entry_time": datetime.now(UTC).isoformat(),
            "exit_strategies": {
                "name": "Test",
                "rules": [{"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50}],
            },
        }

        result = render_active_position(position)

        assert "Next TP in:" in result


class TestRenderClosedPosition:
    """Tests for render_closed_position function."""

    def test_basic_render(self) -> None:
        """Test basic closed position rendering."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "exit_price": "0.002",
            "pnl_pct": 100.0,
            "pnl_sol": 1.0,
            "entry_time": "2025-12-25T10:00:00Z",
            "exit_time": "2025-12-25T15:00:00Z",
            "exit_type": "take_profit",
            "exit_strategies": {"name": "Balanced", "rules": []},
            "signals": {"wallet_address": "abc123wallet", "score": 0.85},
        }

        result = render_closed_position(position)

        assert "Final Result" in result
        assert "take_profit" in result
        assert "🎯" in result  # Take profit emoji

    def test_different_exit_types(self) -> None:
        """Test different exit type emojis."""
        for exit_type, emoji in EXIT_TYPE_EMOJI.items():
            position: dict[str, Any] = {
                "entry_price": "0.001",
                "exit_price": "0.001",
                "pnl_pct": 0.0,
                "entry_time": "2025-12-25T10:00:00Z",
                "exit_time": "2025-12-25T15:00:00Z",
                "exit_type": exit_type,
            }

            result = render_closed_position(position)

            assert emoji in result

    def test_with_reached_levels(self) -> None:
        """Test rendering shows reached levels."""
        position: dict[str, Any] = {
            "entry_price": "0.001",
            "exit_price": "0.002",
            "pnl_pct": 100.0,
            "entry_time": "2025-12-25T10:00:00Z",
            "exit_time": "2025-12-25T15:00:00Z",
            "exit_type": "take_profit",
            "exit_strategies": {
                "name": "Test",
                "rules": [
                    {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50},
                    {"rule_type": "take_profit", "trigger_pct": 150, "exit_pct": 100},
                ],
            },
        }

        result = render_closed_position(position)

        assert "✅" in result  # 50% was reached
        assert "❌" in result  # 150% was not reached


class TestFetchPositionDetails:
    """Tests for fetch_position_details function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful position fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "pos-123", "status": "open"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position_details("pos-123")

        assert result is not None
        assert result["id"] == "pos-123"

    @pytest.mark.asyncio
    async def test_fetch_with_truncated_id(self) -> None:
        """Test fetch with truncated ID."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "pos-12345", "status": "open"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position_details("pos-123...")

        assert result is not None

    @pytest.mark.asyncio
    async def test_fetch_not_found(self) -> None:
        """Test fetch when position not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position_details("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_error(self) -> None:
        """Test fetch handles errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await fetch_position_details("pos-123")

        assert result is None


class TestOpenSidebar:
    """Tests for open_sidebar function."""

    @pytest.mark.asyncio
    async def test_open_empty_id(self) -> None:
        """Test opening with empty ID."""
        result = await open_sidebar("")

        # Returns 4 values: container_update, content, strategy_update, pos_id
        container_update, content, strategy_update, pos_id = result
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_not_found(self) -> None:
        """Test opening non-existent position."""
        with patch(
            "walltrack.ui.components.position_details_sidebar.fetch_position_details",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await open_sidebar("nonexistent")

        _, content, _, pos_id = result
        assert "not found" in content
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_active_position(self) -> None:
        """Test opening active position shows strategy button."""
        position = {
            "id": "active-pos-123",
            "status": "open",
            "entry_price": "0.001",
            "current_price": "0.0015",
            "pnl_pct": 50.0,
            "size_sol": 1.0,
            "entry_time": datetime.now(UTC).isoformat(),
        }

        with patch(
            "walltrack.ui.components.position_details_sidebar.fetch_position_details",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = position

            result = await open_sidebar("active-pos-123")

        container_update, content, strategy_update, pos_id = result
        assert pos_id == "active-pos-123"
        # Strategy visible for active position
        assert strategy_update.get("visible", False) is True

    @pytest.mark.asyncio
    async def test_open_closed_position(self) -> None:
        """Test opening closed position hides strategy button."""
        position = {
            "id": "closed-pos-123",
            "status": "closed",
            "entry_price": "0.001",
            "exit_price": "0.002",
            "pnl_pct": 100.0,
            "entry_time": "2025-12-25T10:00:00Z",
            "exit_time": "2025-12-25T15:00:00Z",
            "exit_type": "take_profit",
        }

        with patch(
            "walltrack.ui.components.position_details_sidebar.fetch_position_details",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = position

            result = await open_sidebar("closed-pos-123")

        container_update, content, strategy_update, pos_id = result
        assert pos_id == "closed-pos-123"
        # Strategy hidden for closed position
        assert strategy_update.get("visible", True) is False
