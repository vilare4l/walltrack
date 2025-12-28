"""Tests for change strategy modal component."""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.ui.components.change_strategy_modal import (
    apply_strategy_change,
    calculate_preview,
    fetch_position,
    fetch_strategies,
    fetch_strategy,
    format_preview_markdown,
    open_modal,
)


class TestFetchStrategies:
    """Tests for fetch_strategies function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful strategy fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "strategies": [
                {"id": "strat-1", "name": "Balanced", "version": 1, "status": "active"},
                {"id": "strat-2", "name": "Aggressive", "version": 2, "status": "active"},
                {"id": "strat-3", "name": "Inactive", "version": 1, "status": "draft"},
            ]
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_strategies()

        assert len(result) == 2  # Only active strategies
        assert result[0] == ("Balanced (v1)", "strat-1")
        assert result[1] == ("Aggressive (v2)", "strat-2")

    @pytest.mark.asyncio
    async def test_fetch_error(self) -> None:
        """Test fetch handles errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await fetch_strategies()

        assert result == []


class TestFetchPosition:
    """Tests for fetch_position function."""

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

            result = await fetch_position("pos-123")

        assert result is not None
        assert result["id"] == "pos-123"

    @pytest.mark.asyncio
    async def test_fetch_not_found(self) -> None:
        """Test fetch when not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position("nonexistent")

        assert result is None


class TestFetchStrategy:
    """Tests for fetch_strategy function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful strategy fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "strat-1",
            "name": "Balanced",
            "rules": [{"rule_type": "take_profit", "trigger_pct": 50}],
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_strategy("strat-1")

        assert result is not None
        assert result["name"] == "Balanced"


class TestApplyStrategyChange:
    """Tests for apply_strategy_change function."""

    @pytest.mark.asyncio
    async def test_apply_success(self) -> None:
        """Test successful strategy change."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": "Strategy changed successfully"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.patch = AsyncMock(
                return_value=mock_response
            )

            success, message = await apply_strategy_change("pos-123", "strat-1")

        assert success
        assert "successfully" in message

    @pytest.mark.asyncio
    async def test_apply_failure(self) -> None:
        """Test failed strategy change."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"detail": "Position not active"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.patch = AsyncMock(
                return_value=mock_response
            )

            success, message = await apply_strategy_change("pos-123", "strat-1")

        assert not success
        assert "not active" in message

    @pytest.mark.asyncio
    async def test_apply_error(self) -> None:
        """Test strategy change with error."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.patch = AsyncMock(
                side_effect=Exception("Connection error")
            )

            success, message = await apply_strategy_change("pos-123", "strat-1")

        assert not success
        assert "Error" in message


class TestCalculatePreview:
    """Tests for calculate_preview function."""

    def test_basic_preview(self) -> None:
        """Test basic preview calculation."""
        strategy: dict[str, Any] = {
            "name": "Balanced",
            "rules": [
                {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 100, "exit_pct": 100, "enabled": True},
                {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "enabled": True},
            ],
        }

        result = calculate_preview(strategy, Decimal("0.001"))

        assert result["strategy_name"] == "Balanced"
        assert len(result["levels"]) == 3

        # Check TP at 50%
        tp1 = result["levels"][0]
        assert tp1["type"] == "take_profit"
        assert tp1["trigger_pct"] == 50
        assert tp1["absolute_price"] == Decimal("0.0015")

    def test_with_executed_exits(self) -> None:
        """Test preview with executed exits."""
        strategy: dict[str, Any] = {
            "name": "Test",
            "rules": [
                {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50, "enabled": True},
                {"rule_type": "take_profit", "trigger_pct": 100, "exit_pct": 100, "enabled": True},
            ],
        }
        executed_exits = [{"exit_type": "take_profit", "trigger_pct": 50}]

        result = calculate_preview(strategy, Decimal("0.001"), executed_exits)

        # First TP should be marked as executed
        assert result["levels"][0]["already_executed"]
        assert not result["levels"][1]["already_executed"]

    def test_disabled_rules_excluded(self) -> None:
        """Test that disabled rules are excluded."""
        strategy: dict[str, Any] = {
            "name": "Test",
            "rules": [
                {"rule_type": "take_profit", "trigger_pct": 50, "exit_pct": 50, "enabled": True},
                {"rule_type": "stop_loss", "trigger_pct": -10, "exit_pct": 100, "enabled": False},
            ],
        }

        result = calculate_preview(strategy, Decimal("0.001"))

        assert len(result["levels"]) == 1
        assert result["levels"][0]["type"] == "take_profit"


class TestFormatPreviewMarkdown:
    """Tests for format_preview_markdown function."""

    def test_basic_format(self) -> None:
        """Test basic markdown formatting."""
        preview: dict[str, Any] = {
            "strategy_name": "Balanced",
            "levels": [
                {
                    "type": "take_profit",
                    "trigger_pct": 50,
                    "exit_pct": 50,
                    "absolute_price": Decimal("0.0015"),
                    "already_executed": False,
                },
            ],
        }

        result = format_preview_markdown(preview, Decimal("0.001"))

        assert "Balanced" in result
        assert "take_profit" in result
        assert "+50%" in result
        assert "⏳ Pending" in result

    def test_executed_level(self) -> None:
        """Test formatting of executed level."""
        preview: dict[str, Any] = {
            "strategy_name": "Test",
            "levels": [
                {
                    "type": "take_profit",
                    "trigger_pct": 50,
                    "exit_pct": 50,
                    "absolute_price": Decimal("0.0015"),
                    "already_executed": True,
                },
            ],
        }

        result = format_preview_markdown(preview, Decimal("0.001"))

        assert "✅ Executed" in result

    def test_no_trigger_pct(self) -> None:
        """Test level with no trigger percentage."""
        preview: dict[str, Any] = {
            "strategy_name": "Test",
            "levels": [
                {
                    "type": "time_based",
                    "trigger_pct": None,
                    "exit_pct": 100,
                    "absolute_price": None,
                    "already_executed": False,
                },
            ],
        }

        result = format_preview_markdown(preview, Decimal("0.001"))

        # Should use "-" for null values
        assert "| - |" in result


class TestOpenModal:
    """Tests for open_modal function."""

    @pytest.mark.asyncio
    async def test_open_empty_id(self) -> None:
        """Test opening with empty ID."""
        result = await open_modal("")

        container_update, _, dropdown_update, _, _, pos_id, entry_price = result
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_not_found(self) -> None:
        """Test opening non-existent position."""
        with patch(
            "walltrack.ui.components.change_strategy_modal.fetch_position",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await open_modal("nonexistent")

        _, current_text, _, _, _, pos_id, _ = result
        assert "not found" in current_text
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_closed_position(self) -> None:
        """Test opening for closed position fails."""
        with patch(
            "walltrack.ui.components.change_strategy_modal.fetch_position",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {"id": "pos-123", "status": "closed"}

            result = await open_modal("pos-123")

        _, current_text, _, _, _, pos_id, _ = result
        assert "closed" in current_text.lower()
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_active_position(self) -> None:
        """Test opening for active position."""
        position = {
            "id": "pos-123",
            "status": "open",
            "entry_price": "0.001",
            "exit_strategies": {"name": "Current Strategy"},
        }

        with (
            patch(
                "walltrack.ui.components.change_strategy_modal.fetch_position",
                new_callable=AsyncMock,
            ) as mock_fetch_pos,
            patch(
                "walltrack.ui.components.change_strategy_modal.fetch_strategies",
                new_callable=AsyncMock,
            ) as mock_fetch_strats,
        ):
            mock_fetch_pos.return_value = position
            mock_fetch_strats.return_value = [("Strategy A", "strat-a")]

            result = await open_modal("pos-123")

        container_update, current_text, dropdown_update, _, _, pos_id, entry_price = result

        assert "Current Strategy" in current_text
        assert pos_id == "pos-123"
        assert entry_price == "0.001"
