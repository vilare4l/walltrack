"""Tests for discovery UI component."""

from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from walltrack.ui.components.discovery import (
    _format_datetime,
    apply_filter,
    fetch_discovery_config,
    fetch_discovery_history,
    fetch_discovery_stats,
    fetch_pumped_tokens,
    format_stats_display,
    go_next_page,
    go_prev_page,
    load_history_and_stats,
    save_discovery_config,
    trigger_discovery,
)


class TestFormatDatetime:
    """Tests for _format_datetime helper."""

    def test_format_none_returns_never(self) -> None:
        """Test that None returns 'Never'."""
        assert _format_datetime(None) == "Never"

    def test_format_empty_string_returns_never(self) -> None:
        """Test that empty string returns 'Never'."""
        assert _format_datetime("") == "Never"

    def test_format_iso_datetime(self) -> None:
        """Test formatting ISO datetime string."""
        result = _format_datetime("2024-01-15T10:30:00+00:00")
        assert "2024-01-15" in result
        assert "10:30:00" in result

    def test_format_z_suffix(self) -> None:
        """Test formatting datetime with Z suffix."""
        result = _format_datetime("2024-01-15T10:30:00Z")
        assert "2024-01-15" in result

    def test_format_invalid_returns_original(self) -> None:
        """Test that invalid string returns original."""
        result = _format_datetime("not a date")
        assert result == "not a date"


class TestFetchDiscoveryConfig:
    """Tests for fetch_discovery_config function."""

    async def test_fetch_config_success(self) -> None:
        """Test successful config fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "enabled": True,
            "schedule_hours": 6,
            "params": {"max_tokens": 20},
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_config()

        assert result["enabled"] is True
        assert result["schedule_hours"] == 6

    async def test_fetch_config_error_returns_empty(self) -> None:
        """Test that errors return empty dict."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_config()

        assert result == {}


class TestSaveDiscoveryConfig:
    """Tests for save_discovery_config function."""

    async def test_save_config_success(self) -> None:
        """Test successful config save."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.put.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await save_discovery_config(
                enabled=True,
                schedule_hours=6,
                min_price_change=100.0,
                min_volume=50000.0,
                max_age=72,
                early_window=30,
                min_profit=50.0,
                max_tokens=20,
            )

        assert "successfully" in result

    async def test_save_config_error(self) -> None:
        """Test save config error handling."""
        mock_client = AsyncMock()
        mock_client.put.side_effect = Exception("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await save_discovery_config(
                enabled=True,
                schedule_hours=6,
                min_price_change=100.0,
                min_volume=50000.0,
                max_age=72,
                early_window=30,
                min_profit=50.0,
                max_tokens=20,
            )

        assert "Failed" in result


class TestTriggerDiscovery:
    """Tests for trigger_discovery function."""

    async def test_trigger_success(self) -> None:
        """Test successful discovery trigger."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"run_id": "test-uuid"}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await trigger_discovery(
                min_price_change=100.0,
                min_volume=50000.0,
                max_age=72,
                early_window=30,
                min_profit=50.0,
                max_tokens=20,
            )

        assert "started" in result
        assert "test-uuid" in result

    async def test_trigger_error(self) -> None:
        """Test trigger error handling."""
        mock_client = AsyncMock()
        mock_client.post.side_effect = Exception("API error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await trigger_discovery(
                min_price_change=100.0,
                min_volume=50000.0,
                max_age=72,
                early_window=30,
                min_profit=50.0,
                max_tokens=20,
            )

        assert "Failed" in result


class TestFetchPumpedTokens:
    """Tests for fetch_pumped_tokens function."""

    async def test_fetch_empty_tokens(self) -> None:
        """Test fetching when no tokens found."""
        mock_finder = MagicMock()
        mock_finder.find_pumped_tokens = AsyncMock(return_value=[])
        mock_finder.close = AsyncMock()

        with patch("walltrack.ui.components.discovery.PumpFinder", return_value=mock_finder):
            result = await fetch_pumped_tokens()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    async def test_fetch_tokens_error(self) -> None:
        """Test error handling in fetch."""
        with patch(
            "walltrack.ui.components.discovery.PumpFinder",
            side_effect=Exception("API error"),
        ):
            result = await fetch_pumped_tokens()

        assert isinstance(result, pd.DataFrame)
        assert "Error" in result.columns


class TestFetchDiscoveryStats:
    """Tests for fetch_discovery_stats function."""

    async def test_fetch_stats_success(self) -> None:
        """Test successful stats fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "total_runs": 100,
            "successful_runs": 95,
            "failed_runs": 5,
            "total_wallets_discovered": 1000,
            "avg_wallets_per_run": 10.0,
            "avg_duration_seconds": 60.0,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_stats()

        assert isinstance(result, dict)
        assert result["total_runs"] == 100
        assert result["successful_runs"] == 95

    async def test_fetch_stats_with_date_range(self) -> None:
        """Test stats fetch with date range."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"total_runs": 50}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_stats("2024-01-01", "2024-01-31")

        assert isinstance(result, dict)
        mock_client.get.assert_called_once()

    async def test_fetch_stats_error(self) -> None:
        """Test stats fetch error handling."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_stats()

        assert result == {}


class TestFormatStatsDisplay:
    """Tests for format_stats_display function."""

    def test_format_empty_stats(self) -> None:
        """Test formatting empty stats."""
        result = format_stats_display({})
        assert result == "No statistics available"

    def test_format_stats_with_data(self) -> None:
        """Test formatting stats with data."""
        stats = {
            "total_runs": 100,
            "successful_runs": 95,
            "failed_runs": 5,
            "total_wallets_discovered": 1000,
            "total_wallets_updated": 500,
            "avg_wallets_per_run": 10.0,
            "avg_duration_seconds": 60.0,
            "last_run_at": "2024-01-15T10:30:00Z",
        }
        result = format_stats_display(stats)

        assert "100" in result  # total runs
        assert "95" in result  # successful
        assert "5" in result  # failed
        assert "95.0%" in result  # success rate
        assert "1000" in result  # wallets discovered
        assert "10.0" in result  # avg wallets
        assert "60.0s" in result  # duration

    def test_format_stats_zero_runs(self) -> None:
        """Test formatting stats with zero runs."""
        stats = {"total_runs": 0, "successful_runs": 0}
        result = format_stats_display(stats)
        assert "0.0%" in result  # success rate is 0%


class TestFetchDiscoveryHistory:
    """Tests for fetch_discovery_history function."""

    async def test_fetch_history_success(self) -> None:
        """Test successful history fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "runs": [
                {
                    "started_at": "2024-01-15T10:30:00Z",
                    "tokens_analyzed": 10,
                    "new_wallets": 5,
                    "updated_wallets": 3,
                    "duration_seconds": 45.5,
                    "status": "completed",
                }
            ],
            "total": 1,
            "page": 1,
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_history()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 1
        assert "Date" in result.columns
        assert "Status" in result.columns

    async def test_fetch_history_empty(self) -> None:
        """Test history fetch with no runs."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"runs": [], "total": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_history()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    async def test_fetch_history_with_pagination(self) -> None:
        """Test history fetch with pagination."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"runs": [], "total": 0}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            await fetch_discovery_history(page=2)

        mock_client.get.assert_called_once()
        call_args = mock_client.get.call_args
        assert call_args[1]["params"]["page"] == 2

    async def test_fetch_history_error(self) -> None:
        """Test history fetch error handling."""
        mock_client = AsyncMock()
        mock_client.get.side_effect = Exception("Connection error")
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = None

        with patch("walltrack.ui.components.discovery.httpx.AsyncClient", return_value=mock_client):
            result = await fetch_discovery_history()

        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0


class TestPaginationFunctions:
    """Tests for pagination helper functions."""

    async def test_go_prev_page_from_page_2(self) -> None:
        """Test going to previous page from page 2."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {"total_runs": 10}
                mock_history.return_value = pd.DataFrame()

                stats_md, history_df, page_text, page_num = await go_prev_page("", "", 2)

        assert page_num == 1
        assert page_text == "Page 1"
        mock_history.assert_called_with(None, None, 1)

    async def test_go_prev_page_from_page_1(self) -> None:
        """Test going to previous page from page 1 stays at 1."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {}
                mock_history.return_value = pd.DataFrame()

                _, _, _, page_num = await go_prev_page("", "", 1)

        assert page_num == 1

    async def test_go_next_page(self) -> None:
        """Test going to next page."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {"total_runs": 100}
                mock_history.return_value = pd.DataFrame()

                _, _, page_text, page_num = await go_next_page("", "", 1)

        assert page_num == 2
        assert page_text == "Page 2"

    async def test_apply_filter_resets_to_page_1(self) -> None:
        """Test applying filter resets to page 1."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {}
                mock_history.return_value = pd.DataFrame()

                _, _, _, page_num = await apply_filter("2024-01-01", "2024-01-31")

        assert page_num == 1
        mock_history.assert_called_with("2024-01-01", "2024-01-31", 1)


class TestLoadHistoryAndStats:
    """Tests for load_history_and_stats function."""

    async def test_load_with_dates(self) -> None:
        """Test loading with date filters."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {"total_runs": 50}
                mock_history.return_value = pd.DataFrame({"Date": ["2024-01-15"]})

                stats_md, history_df, page_text, page_num = await load_history_and_stats(
                    "2024-01-01", "2024-01-31", 1
                )

        assert "50" in stats_md  # total runs
        assert len(history_df) == 1
        assert page_text == "Page 1"
        assert page_num == 1
        mock_stats.assert_called_with("2024-01-01", "2024-01-31")
        mock_history.assert_called_with("2024-01-01", "2024-01-31", 1)

    async def test_load_with_empty_dates(self) -> None:
        """Test loading with empty date strings."""
        with patch("walltrack.ui.components.discovery.fetch_discovery_stats", new_callable=AsyncMock) as mock_stats:
            with patch("walltrack.ui.components.discovery.fetch_discovery_history", new_callable=AsyncMock) as mock_history:
                mock_stats.return_value = {}
                mock_history.return_value = pd.DataFrame()

                await load_history_and_stats("", "", 1)

        # Empty strings should be converted to None
        mock_stats.assert_called_with(None, None)
        mock_history.assert_called_with(None, None, 1)
