"""Tests for wallet UI component."""

import pandas as pd

from walltrack.ui.components.wallets import (
    format_wallet_detail,
    wallets_to_dataframe,
)


class TestWalletsToDataframe:
    """Tests for wallets_to_dataframe function."""

    def test_empty_wallets(self) -> None:
        """Test with empty wallet list."""
        df = wallets_to_dataframe([])
        assert len(df) == 0
        assert "Address" in df.columns

    def test_wallet_formatting(self) -> None:
        """Test wallet data formatting."""
        wallets = [
            {
                "address": "ABC123XYZ789DEF456GHI012JKL345MNO678",
                "status": "active",
                "score": 0.75,
                "profile": {
                    "win_rate": 0.6,
                    "total_pnl": 10.5,
                    "total_trades": 25,
                },
                "last_signal_at": "2024-01-15T10:30:00",
            }
        ]

        df = wallets_to_dataframe(wallets)

        assert len(df) == 1
        assert "..." in df.iloc[0]["Address"]  # Truncated
        assert df.iloc[0]["Status"] == "active"
        assert "75.00%" in df.iloc[0]["Score"]

    def test_wallet_without_profile(self) -> None:
        """Test wallet with missing profile data."""
        wallets = [
            {
                "address": "A" * 44,
                "status": "active",
                "score": 0.5,
            }
        ]

        df = wallets_to_dataframe(wallets)

        assert len(df) == 1
        assert df.iloc[0]["Win Rate"] == "0.0%"
        assert df.iloc[0]["Trades"] == 0

    def test_wallet_without_last_signal(self) -> None:
        """Test wallet without last signal timestamp."""
        wallets = [
            {
                "address": "B" * 44,
                "status": "active",
                "score": 0.6,
                "profile": {"win_rate": 0.5, "total_pnl": 1.0, "total_trades": 10},
            }
        ]

        df = wallets_to_dataframe(wallets)

        assert df.iloc[0]["Last Signal"] == "-"

    def test_multiple_wallets(self) -> None:
        """Test with multiple wallets."""
        wallets = [
            {"address": "A" * 44, "status": "active", "score": 0.8, "profile": {}},
            {"address": "B" * 44, "status": "blacklisted", "score": 0.3, "profile": {}},
            {"address": "C" * 44, "status": "decay_detected", "score": 0.5, "profile": {}},
        ]

        df = wallets_to_dataframe(wallets)

        assert len(df) == 3
        assert df.iloc[1]["Status"] == "blacklisted"


class TestFormatWalletDetail:
    """Tests for format_wallet_detail function."""

    def test_none_wallet(self) -> None:
        """Test with None wallet."""
        result = format_wallet_detail(None)
        assert "No wallet selected" in result

    def test_wallet_formatting(self) -> None:
        """Test wallet detail formatting."""
        wallet = {
            "address": "TEST_ADDRESS_123456789012345678901234",
            "status": "active",
            "score": 0.8,
            "profile": {
                "win_rate": 0.65,
                "total_pnl": 15.5,
                "total_trades": 30,
                "avg_pnl_per_trade": 0.5,
                "avg_hold_time_hours": 2.5,
                "timing_percentile": 0.3,
                "avg_position_size_sol": 0.1,
            },
            "discovered_at": "2024-01-01T00:00:00",
            "discovery_count": 3,
            "rolling_win_rate": 0.6,
            "consecutive_losses": 1,
        }

        result = format_wallet_detail(wallet)

        assert "TEST_ADDRESS_123456789012345678901234" in result
        assert "active" in result
        assert "65.0%" in result
        assert "15.50 SOL" in result

    def test_wallet_with_decay_detected(self) -> None:
        """Test wallet with decay detected status."""
        wallet = {
            "address": "DECAY_WALLET_" + "X" * 32,
            "status": "decay_detected",
            "score": 0.4,
            "profile": {"win_rate": 0.35, "total_pnl": -5.0, "total_trades": 20},
            "decay_detected_at": "2024-01-10T15:30:00",
            "consecutive_losses": 5,
            "rolling_win_rate": 0.3,
        }

        result = format_wallet_detail(wallet)

        assert "decay_detected" in result
        assert "2024-01-10" in result
        assert "5" in result  # consecutive losses

    def test_wallet_minimal_data(self) -> None:
        """Test wallet with minimal data."""
        wallet = {
            "address": "MINIMAL_" + "Z" * 36,
            "status": "active",
            "score": 0.5,
            "profile": {},
        }

        result = format_wallet_detail(wallet)

        assert "MINIMAL_" in result
        assert "0.0%" in result  # default win rate
        assert "N/A" in result  # missing discovered_at


class TestDataframeColumns:
    """Tests for DataFrame column structure."""

    def test_dataframe_has_expected_columns(self) -> None:
        """Test DataFrame has all expected columns."""
        df = wallets_to_dataframe([])

        expected_columns = [
            "Address",
            "Status",
            "Score",
            "Win Rate",
            "Total PnL",
            "Trades",
            "Last Signal",
        ]

        for col in expected_columns:
            assert col in df.columns

    def test_dataframe_with_data_has_full_address(self) -> None:
        """Test DataFrame with data has Full Address column."""
        wallets = [{"address": "A" * 44, "status": "active", "score": 0.5, "profile": {}}]
        df = wallets_to_dataframe(wallets)

        assert "Full Address" in df.columns
        assert df.iloc[0]["Full Address"] == "A" * 44
