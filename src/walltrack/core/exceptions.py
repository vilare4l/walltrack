"""WallTrack exception hierarchy.

This module defines the base exception class and specialized exceptions
for different error categories across the application.
"""


class WallTrackError(Exception):
    """Base exception for all WallTrack errors.

    All custom exceptions in WallTrack should inherit from this class
    to enable consistent error handling and logging.
    """

    pass


class DatabaseConnectionError(WallTrackError):
    """Raised when database connection fails.

    Use this for Supabase, Neo4j, or any other database connection issues.
    Include the database name in the error message for context.

    Example:
        raise DatabaseConnectionError("Neo4j: Connection refused")
    """

    pass


class ConfigurationError(WallTrackError):
    """Raised when configuration is invalid or missing.

    Use this for issues with environment variables, settings files,
    or any configuration-related problems.

    Example:
        raise ConfigurationError("Missing required env var: SUPABASE_URL")
    """

    pass


class ValidationError(WallTrackError):
    """Raised when data validation fails.

    Use this for invalid input data, schema validation errors,
    or business rule violations.

    Example:
        raise ValidationError("Wallet address must be 44 characters")
    """

    pass


class ExternalServiceError(WallTrackError):
    """Raised when an external service call fails.

    Use this for API errors from Helius, Jupiter, DexScreener, etc.

    Attributes:
        service: Name of the external service that failed.
        status_code: HTTP status code if available, None otherwise.

    Example:
        raise ExternalServiceError(service="Helius", message="Rate limited", status_code=429)
    """

    def __init__(
        self,
        service: str,
        message: str,
        status_code: int | None = None,
    ) -> None:
        self.service = service
        self.status_code = status_code
        super().__init__(f"{service}: {message}")


class CircuitBreakerOpenError(WallTrackError):
    """Raised when circuit breaker is open.

    Use this when an API client's circuit breaker has tripped due to
    consecutive failures and requests are being blocked.

    Example:
        raise CircuitBreakerOpenError("Circuit is open for Helius API")
    """

    pass


class WalletConnectionError(WallTrackError):
    """Raised when wallet connection or validation fails.

    Use this for errors during wallet address validation, RPC calls,
    or any wallet-related operations.

    Attributes:
        wallet_address: The wallet address that failed validation (if available).

    Example:
        raise WalletConnectionError("Invalid address format", wallet_address="abc123")
    """

    def __init__(self, message: str, wallet_address: str | None = None) -> None:
        super().__init__(message)
        self.wallet_address = wallet_address
