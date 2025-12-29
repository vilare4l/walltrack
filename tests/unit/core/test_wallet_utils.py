"""Tests for wallet utility functions."""

import pytest

from walltrack.core.wallet.utils import truncate_address


class TestTruncateAddress:
    """Tests for truncate_address utility function."""

    def test_truncates_long_address(self) -> None:
        """Should truncate addresses longer than 12 characters."""
        address = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
        result = truncate_address(address)

        assert result == "9WzD...AWWM"
        assert len(result) == 11  # 4 + 3 (dots) + 4 = 11

    def test_returns_short_address_unchanged(self) -> None:
        """Should return short addresses unchanged."""
        short_address = "9WzDXw"
        result = truncate_address(short_address)

        assert result == short_address

    def test_returns_12_char_address_unchanged(self) -> None:
        """Should return exactly 12-char address unchanged."""
        address = "123456789012"
        result = truncate_address(address)

        assert result == address

    def test_truncates_13_char_address(self) -> None:
        """Should truncate 13-char address."""
        address = "1234567890123"
        result = truncate_address(address)

        assert result == "1234...0123"

    def test_handles_empty_string(self) -> None:
        """Should handle empty string without error."""
        result = truncate_address("")

        assert result == ""

    def test_typical_solana_address(self) -> None:
        """Should correctly truncate typical Solana address."""
        # Typical Solana address is 44 characters
        address = "5Hk2...xY9z" * 4  # 40 chars, would be truncated
        result = truncate_address(address)

        assert "..." in result
        assert len(result) <= 12
