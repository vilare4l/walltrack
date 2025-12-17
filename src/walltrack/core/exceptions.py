"""Custom exceptions for WallTrack.

All exceptions inherit from WallTrackError for consistent error handling.
"""


class WallTrackError(Exception):
    """Base exception for all WallTrack errors."""

    pass


class WalletNotFoundError(WallTrackError):
    """Raised when a wallet is not found in the database."""

    pass


class SignalNotFoundError(WallTrackError):
    """Raised when a signal is not found."""

    pass


class TradeNotFoundError(WallTrackError):
    """Raised when a trade is not found."""

    pass


class CircuitBreakerOpenError(WallTrackError):
    """Raised when circuit breaker is open and request is rejected."""

    pass


class InsufficientBalanceError(WallTrackError):
    """Raised when wallet has insufficient balance for trade."""

    pass


class InvalidSignatureError(WallTrackError):
    """Raised when webhook HMAC signature validation fails."""

    pass


class ExternalAPIError(WallTrackError):
    """Raised when an external API call fails after retries."""

    def __init__(self, service: str, message: str) -> None:
        self.service = service
        super().__init__(f"{service}: {message}")


class ConfigurationError(WallTrackError):
    """Raised when configuration is invalid or missing."""

    pass


class DatabaseConnectionError(WallTrackError):
    """Raised when database connection fails."""

    pass


class SignalProcessingError(WallTrackError):
    """Raised when signal processing fails."""

    pass


class TradeExecutionError(WallTrackError):
    """Raised when trade execution fails."""

    pass
