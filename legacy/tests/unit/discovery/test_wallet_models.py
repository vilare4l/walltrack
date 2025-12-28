"""Tests for wallet models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from walltrack.data.models.wallet import (
    DiscoveryResult,
    TokenLaunch,
    Wallet,
    WalletProfile,
    WalletStatus,
)


class TestWalletStatus:
    """Tests for WalletStatus enum."""

    def test_status_values(self) -> None:
        """Test all status values exist."""
        assert WalletStatus.ACTIVE.value == "active"
        assert WalletStatus.DECAY_DETECTED.value == "decay_detected"
        assert WalletStatus.BLACKLISTED.value == "blacklisted"
        assert WalletStatus.INSUFFICIENT_DATA.value == "insufficient_data"


class TestWalletProfile:
    """Tests for WalletProfile model."""

    def test_default_values(self) -> None:
        """Test default profile values."""
        profile = WalletProfile()
        assert profile.win_rate == 0.0
        assert profile.total_pnl == 0.0
        assert profile.total_trades == 0
        assert profile.timing_percentile == 0.5
        assert profile.preferred_hours == []

    def test_win_rate_bounds(self) -> None:
        """Test win_rate must be between 0 and 1."""
        with pytest.raises(ValidationError):
            WalletProfile(win_rate=1.5)

        with pytest.raises(ValidationError):
            WalletProfile(win_rate=-0.1)

    def test_valid_profile(self) -> None:
        """Test creating a valid profile."""
        profile = WalletProfile(
            win_rate=0.75,
            total_pnl=1000.0,
            avg_pnl_per_trade=100.0,
            total_trades=10,
            timing_percentile=0.2,
            avg_hold_time_hours=4.5,
            preferred_hours=[9, 10, 11, 14, 15],
            avg_position_size_sol=0.5,
        )
        assert profile.win_rate == 0.75
        assert profile.total_trades == 10


class TestWallet:
    """Tests for Wallet model."""

    def test_minimum_wallet(self) -> None:
        """Test creating wallet with minimum fields."""
        wallet = Wallet(address="A" * 32)  # Minimum 32 chars
        assert wallet.address == "A" * 32
        assert wallet.status == WalletStatus.ACTIVE
        assert wallet.score == 0.5
        assert wallet.discovery_count == 1

    def test_address_validation(self) -> None:
        """Test address length validation."""
        # Too short
        with pytest.raises(ValidationError):
            Wallet(address="A" * 31)

        # Too long
        with pytest.raises(ValidationError):
            Wallet(address="A" * 45)

    def test_score_bounds(self) -> None:
        """Test score must be between 0 and 1."""
        with pytest.raises(ValidationError):
            Wallet(address="A" * 32, score=1.5)

        with pytest.raises(ValidationError):
            Wallet(address="A" * 32, score=-0.1)

    def test_is_trackable(self) -> None:
        """Test is_trackable method."""
        wallet = Wallet(address="A" * 32, status=WalletStatus.ACTIVE)
        assert wallet.is_trackable() is True

        wallet.status = WalletStatus.BLACKLISTED
        assert wallet.is_trackable() is False

        wallet.status = WalletStatus.INSUFFICIENT_DATA
        assert wallet.is_trackable() is False

        wallet.status = WalletStatus.DECAY_DETECTED
        assert wallet.is_trackable() is True

    def test_has_sufficient_data(self) -> None:
        """Test has_sufficient_data method."""
        wallet = Wallet(address="A" * 32)
        assert wallet.has_sufficient_data() is False

        wallet.profile.total_trades = 5
        assert wallet.has_sufficient_data() is True

        wallet.profile.total_trades = 4
        assert wallet.has_sufficient_data() is False


class TestDiscoveryResult:
    """Tests for DiscoveryResult model."""

    def test_minimum_result(self) -> None:
        """Test creating result with minimum fields."""
        result = DiscoveryResult(
            token_mint="token123",
            duration_seconds=1.5,
        )
        assert result.new_wallets == 0
        assert result.updated_wallets == 0
        assert result.errors == []

    def test_full_result(self) -> None:
        """Test creating result with all fields."""
        result = DiscoveryResult(
            new_wallets=5,
            updated_wallets=3,
            total_processed=8,
            token_mint="token123",
            duration_seconds=2.5,
            errors=["Error 1", "Error 2"],
        )
        assert result.new_wallets == 5
        assert result.total_processed == 8
        assert len(result.errors) == 2


class TestTokenLaunch:
    """Tests for TokenLaunch model."""

    def test_minimum_token(self) -> None:
        """Test creating token with minimum fields."""
        token = TokenLaunch(
            mint="token123",
            launch_time=datetime.utcnow(),
        )
        assert token.mint == "token123"
        assert token.symbol == ""
        assert token.peak_mcap == 0.0

    def test_full_token(self) -> None:
        """Test creating token with all fields."""
        launch_time = datetime.utcnow()
        token = TokenLaunch(
            mint="token123",
            symbol="TEST",
            launch_time=launch_time,
            peak_mcap=1000000.0,
            current_mcap=500000.0,
            volume_24h=250000.0,
        )
        assert token.symbol == "TEST"
        assert token.peak_mcap == 1000000.0
        assert token.launch_time == launch_time

    def test_mcap_non_negative(self) -> None:
        """Test market cap must be non-negative."""
        with pytest.raises(ValidationError):
            TokenLaunch(
                mint="token123",
                launch_time=datetime.utcnow(),
                peak_mcap=-100.0,
            )
