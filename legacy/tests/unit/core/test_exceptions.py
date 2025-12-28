"""Unit tests for custom exceptions.

Test ID: 1.0-UNIT-001
"""

import pytest

from walltrack.core.exceptions import (
    CircuitBreakerOpenError,
    ConfigurationError,
    ExternalAPIError,
    InsufficientBalanceError,
    InvalidSignatureError,
    SignalNotFoundError,
    TradeNotFoundError,
    WalletNotFoundError,
    WallTrackError,
)


@pytest.mark.unit
class TestWallTrackExceptions:
    """Tests for custom exception hierarchy."""

    def test_base_exception_is_catchable(self) -> None:
        """All custom exceptions inherit from WallTrackError."""
        with pytest.raises(WallTrackError):
            raise WalletNotFoundError("Wallet not found")

    def test_wallet_not_found_error(self) -> None:
        """WalletNotFoundError can be raised and caught."""
        with pytest.raises(WalletNotFoundError) as exc_info:
            raise WalletNotFoundError("Wallet ABC123 not found")

        assert "ABC123" in str(exc_info.value)

    def test_signal_not_found_error(self) -> None:
        """SignalNotFoundError can be raised and caught."""
        with pytest.raises(SignalNotFoundError):
            raise SignalNotFoundError("Signal not found")

    def test_trade_not_found_error(self) -> None:
        """TradeNotFoundError can be raised and caught."""
        with pytest.raises(TradeNotFoundError):
            raise TradeNotFoundError("Trade not found")

    def test_circuit_breaker_open_error(self) -> None:
        """CircuitBreakerOpenError can be raised and caught."""
        with pytest.raises(CircuitBreakerOpenError):
            raise CircuitBreakerOpenError("Circuit breaker is open")

    def test_insufficient_balance_error(self) -> None:
        """InsufficientBalanceError can be raised and caught."""
        with pytest.raises(InsufficientBalanceError):
            raise InsufficientBalanceError("Insufficient balance for trade")

    def test_invalid_signature_error(self) -> None:
        """InvalidSignatureError can be raised and caught."""
        with pytest.raises(InvalidSignatureError):
            raise InvalidSignatureError("HMAC signature validation failed")

    def test_external_api_error_includes_service_name(self) -> None:
        """ExternalAPIError includes service name in message."""
        with pytest.raises(ExternalAPIError) as exc_info:
            raise ExternalAPIError(service="Helius", message="Rate limit exceeded")

        error = exc_info.value
        assert error.service == "Helius"
        assert "Helius" in str(error)
        assert "Rate limit exceeded" in str(error)

    def test_configuration_error(self) -> None:
        """ConfigurationError can be raised and caught."""
        with pytest.raises(ConfigurationError):
            raise ConfigurationError("Missing required environment variable")

    def test_all_exceptions_inherit_from_base(self) -> None:
        """All custom exceptions are subclasses of WallTrackError."""
        exceptions = [
            WalletNotFoundError,
            SignalNotFoundError,
            TradeNotFoundError,
            CircuitBreakerOpenError,
            InsufficientBalanceError,
            InvalidSignatureError,
            ExternalAPIError,
            ConfigurationError,
        ]

        for exc_class in exceptions:
            assert issubclass(exc_class, WallTrackError), f"{exc_class.__name__} should inherit from WallTrackError"
