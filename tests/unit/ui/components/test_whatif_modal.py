"""Tests for what-if simulation modal component."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.ui.components.whatif_modal import (
    fetch_position,
    fetch_strategies,
    format_comparison_result,
    format_position_info,
    open_whatif_modal,
    run_comparison,
)


class TestFetchPosition:
    """Tests for fetch_position function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful position fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"id": "pos-123", "status": "closed"}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position("pos-123")

        assert result is not None
        assert result["id"] == "pos-123"

    @pytest.mark.asyncio
    async def test_fetch_not_found(self) -> None:
        """Test fetch when position not found."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_position("nonexistent")

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_error(self) -> None:
        """Test fetch handles errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await fetch_position("pos-123")

        assert result is None


class TestFetchStrategies:
    """Tests for fetch_strategies function."""

    @pytest.mark.asyncio
    async def test_fetch_success(self) -> None:
        """Test successful strategies fetch."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "strategies": [
                {"id": "strat-1", "name": "Balanced", "version": 1, "status": "active"},
                {"id": "strat-2", "name": "Aggressive", "version": 2, "status": "active"},
                {"id": "strat-3", "name": "Draft", "version": 1, "status": "draft"},
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
    async def test_fetch_empty(self) -> None:
        """Test fetch with no strategies."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"strategies": []}

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await fetch_strategies()

        assert result == []

    @pytest.mark.asyncio
    async def test_fetch_error(self) -> None:
        """Test fetch handles errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await fetch_strategies()

        assert result == []


class TestRunComparison:
    """Tests for run_comparison function."""

    @pytest.mark.asyncio
    async def test_run_success(self) -> None:
        """Test successful comparison run."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "rows": [{"strategy_name": "Balanced", "simulated_pnl_pct": 50}],
            "best_strategy_name": "Balanced",
        }

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await run_comparison("pos-123", ["strat-1"])

        assert result is not None
        assert result["best_strategy_name"] == "Balanced"

    @pytest.mark.asyncio
    async def test_run_empty_strategies(self) -> None:
        """Test run with empty strategy list."""
        result = await run_comparison("pos-123", [])

        assert result is None

    @pytest.mark.asyncio
    async def test_run_api_error(self) -> None:
        """Test run handles API errors."""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await run_comparison("pos-123", ["strat-1"])

        assert result is None

    @pytest.mark.asyncio
    async def test_run_connection_error(self) -> None:
        """Test run handles connection errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=Exception("Connection error")
            )

            result = await run_comparison("pos-123", ["strat-1"])

        assert result is None


class TestFormatComparisonResult:
    """Tests for format_comparison_result function."""

    def test_format_with_results(self) -> None:
        """Test formatting with comparison results."""
        result: dict[str, Any] = {
            "rows": [
                {
                    "strategy_name": "Balanced",
                    "simulated_pnl_pct": 50.5,
                    "exit_types": ["take_profit"],
                    "duration_hours": 5.5,
                },
                {
                    "strategy_name": "Aggressive",
                    "simulated_pnl_pct": -10.0,
                    "exit_types": ["stop_loss"],
                    "duration_hours": 2.0,
                },
            ],
            "best_strategy_name": "Balanced",
            "best_improvement_pct": 25.0,
        }

        md = format_comparison_result(result)

        assert "Strategy Comparison Results" in md
        assert "Balanced" in md
        assert "Aggressive" in md
        assert "🟢" in md  # Positive P&L
        assert "🔴" in md  # Negative P&L
        assert "+50.50%" in md
        assert "-10.00%" in md
        assert "5.5h" in md
        assert "Best Strategy" in md
        assert "+25.00%" in md

    def test_format_empty_result(self) -> None:
        """Test formatting with empty result."""
        result = format_comparison_result({})

        assert "No comparison results" in result

    def test_format_no_rows(self) -> None:
        """Test formatting with no rows."""
        result = format_comparison_result({"rows": []})

        assert "No strategies to compare" in result

    def test_format_no_duration(self) -> None:
        """Test formatting with missing duration."""
        result_data: dict[str, Any] = {
            "rows": [
                {
                    "strategy_name": "Test",
                    "simulated_pnl_pct": 10.0,
                    "exit_types": [],
                    "duration_hours": 0,
                }
            ]
        }

        md = format_comparison_result(result_data)

        assert "N/A" in md

    def test_format_no_best_strategy(self) -> None:
        """Test formatting without best strategy info."""
        result_data: dict[str, Any] = {
            "rows": [
                {
                    "strategy_name": "Test",
                    "simulated_pnl_pct": 10.0,
                    "exit_types": ["take_profit"],
                    "duration_hours": 1.0,
                }
            ]
        }

        md = format_comparison_result(result_data)

        assert "Test" in md
        assert "Best Strategy" not in md


class TestFormatPositionInfo:
    """Tests for format_position_info function."""

    def test_format_basic(self) -> None:
        """Test basic position info formatting."""
        position: dict[str, Any] = {
            "token_symbol": "SOL",
            "entry_price": 0.001,
            "exit_price": 0.002,
            "exit_type": "take_profit",
            "pnl_pct": 100.0,
            "entry_time": "2025-12-25T10:00:00Z",
        }

        md = format_position_info(position)

        assert "SOL" in md
        assert "0.00100000" in md
        assert "0.00200000" in md
        assert "take_profit" in md
        assert "+100.00%" in md
        assert "🟢" in md

    def test_format_negative_pnl(self) -> None:
        """Test formatting with negative P&L."""
        position: dict[str, Any] = {
            "token_address": "abc123def456xyz",
            "entry_price": 0.001,
            "exit_price": 0.0005,
            "exit_type": "stop_loss",
            "pnl_pct": -50.0,
        }

        md = format_position_info(position)

        assert "🔴" in md
        assert "-50.00%" in md

    def test_format_with_token_address(self) -> None:
        """Test formatting with token address when no symbol."""
        position: dict[str, Any] = {
            "token_address": "abcdefghijklmnop",
            "entry_price": 0.001,
            "exit_price": 0.001,
            "pnl_pct": 0.0,
        }

        md = format_position_info(position)

        # Should truncate to 12 chars
        assert "abcdefghijkl" in md


class TestOpenWhatifModal:
    """Tests for open_whatif_modal function."""

    @pytest.mark.asyncio
    async def test_open_empty_id(self) -> None:
        """Test opening with empty position ID."""
        result = await open_whatif_modal("")

        container_update, _, _, _, _, _, pos_id, _ = result
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_not_found(self) -> None:
        """Test opening non-existent position."""
        with patch(
            "walltrack.ui.components.whatif_modal.fetch_position",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = None

            result = await open_whatif_modal("nonexistent")

        _, info_md, _, _, _, _, pos_id, _ = result
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_active_position(self) -> None:
        """Test opening for active position (should fail)."""
        with patch(
            "walltrack.ui.components.whatif_modal.fetch_position",
            new_callable=AsyncMock,
        ) as mock_fetch:
            mock_fetch.return_value = {"id": "pos-123", "status": "open"}

            result = await open_whatif_modal("pos-123")

        _, info_md, _, _, _, _, pos_id, _ = result
        assert "closed positions" in info_md.lower()
        assert pos_id is None

    @pytest.mark.asyncio
    async def test_open_closed_position(self) -> None:
        """Test opening for closed position."""
        position = {
            "id": "pos-123",
            "status": "closed",
            "token_symbol": "SOL",
            "entry_price": 0.001,
            "exit_price": 0.002,
            "exit_type": "take_profit",
            "pnl_pct": 100.0,
            "entry_time": "2025-12-25T10:00:00Z",
        }
        strategies = [
            ("Balanced (v1)", "strat-1"),
            ("Aggressive (v2)", "strat-2"),
            ("Conservative (v1)", "strat-3"),
        ]

        with (
            patch(
                "walltrack.ui.components.whatif_modal.fetch_position",
                new_callable=AsyncMock,
            ) as mock_fetch_pos,
            patch(
                "walltrack.ui.components.whatif_modal.fetch_strategies",
                new_callable=AsyncMock,
            ) as mock_fetch_strats,
        ):
            mock_fetch_pos.return_value = position
            mock_fetch_strats.return_value = strategies

            result = await open_whatif_modal("pos-123")

        container_update, info_md, checkbox_update, _, _, _, pos_id, _ = result

        assert pos_id == "pos-123"
        assert "SOL" in info_md
        # Pre-selected first 3 strategies
        assert checkbox_update["value"] == ["strat-1", "strat-2", "strat-3"]

    @pytest.mark.asyncio
    async def test_open_preselects_first_three(self) -> None:
        """Test that first 3 strategies are pre-selected."""
        position = {
            "id": "pos-123",
            "status": "closed",
            "entry_price": 0.001,
            "exit_price": 0.002,
            "pnl_pct": 100.0,
        }
        strategies = [
            ("Strategy A", "a"),
            ("Strategy B", "b"),
            ("Strategy C", "c"),
            ("Strategy D", "d"),
            ("Strategy E", "e"),
        ]

        with (
            patch(
                "walltrack.ui.components.whatif_modal.fetch_position",
                new_callable=AsyncMock,
            ) as mock_fetch_pos,
            patch(
                "walltrack.ui.components.whatif_modal.fetch_strategies",
                new_callable=AsyncMock,
            ) as mock_fetch_strats,
        ):
            mock_fetch_pos.return_value = position
            mock_fetch_strats.return_value = strategies

            result = await open_whatif_modal("pos-123")

        _, _, checkbox_update, _, _, _, _, _ = result

        # Should only pre-select first 3
        assert checkbox_update["value"] == ["a", "b", "c"]

    @pytest.mark.asyncio
    async def test_open_with_few_strategies(self) -> None:
        """Test opening with fewer than 3 strategies."""
        position = {
            "id": "pos-123",
            "status": "closed",
            "entry_price": 0.001,
            "exit_price": 0.002,
            "pnl_pct": 100.0,
        }
        strategies = [("Strategy A", "a")]

        with (
            patch(
                "walltrack.ui.components.whatif_modal.fetch_position",
                new_callable=AsyncMock,
            ) as mock_fetch_pos,
            patch(
                "walltrack.ui.components.whatif_modal.fetch_strategies",
                new_callable=AsyncMock,
            ) as mock_fetch_strats,
        ):
            mock_fetch_pos.return_value = position
            mock_fetch_strats.return_value = strategies

            result = await open_whatif_modal("pos-123")

        _, _, checkbox_update, _, _, _, _, _ = result

        # Should only pre-select the one available
        assert checkbox_update["value"] == ["a"]
