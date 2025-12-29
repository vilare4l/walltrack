"""Tests for WallTrack exception hierarchy."""

import pytest


class TestWallTrackError:
    """Tests for base WallTrackError exception."""

    def test_walltrack_error_is_exception(self) -> None:
        """
        Given: WallTrackError class
        When: Checking inheritance
        Then: It inherits from Exception
        """
        from walltrack.core.exceptions import WallTrackError

        assert issubclass(WallTrackError, Exception)

    def test_walltrack_error_can_be_raised(self) -> None:
        """
        Given: WallTrackError
        When: Raised with a message
        Then: Message is accessible via str()
        """
        from walltrack.core.exceptions import WallTrackError

        with pytest.raises(WallTrackError, match="Test error message"):
            raise WallTrackError("Test error message")

    def test_walltrack_error_str_representation(self) -> None:
        """
        Given: WallTrackError with message
        When: Converting to string
        Then: Returns the message
        """
        from walltrack.core.exceptions import WallTrackError

        error = WallTrackError("Something went wrong")
        assert str(error) == "Something went wrong"


class TestDatabaseConnectionError:
    """Tests for DatabaseConnectionError exception."""

    def test_inherits_from_walltrack_error(self) -> None:
        """
        Given: DatabaseConnectionError class
        When: Checking inheritance
        Then: It inherits from WallTrackError
        """
        from walltrack.core.exceptions import DatabaseConnectionError, WallTrackError

        assert issubclass(DatabaseConnectionError, WallTrackError)

    def test_can_be_raised_with_db_context(self) -> None:
        """
        Given: DatabaseConnectionError
        When: Raised with database context
        Then: Context is included in message
        """
        from walltrack.core.exceptions import DatabaseConnectionError

        with pytest.raises(DatabaseConnectionError, match="Neo4j"):
            raise DatabaseConnectionError("Neo4j: Connection refused")

    def test_can_catch_as_walltrack_error(self) -> None:
        """
        Given: DatabaseConnectionError raised
        When: Catching as WallTrackError
        Then: Exception is caught
        """
        from walltrack.core.exceptions import DatabaseConnectionError, WallTrackError

        with pytest.raises(WallTrackError):
            raise DatabaseConnectionError("Supabase: API key invalid")


class TestConfigurationError:
    """Tests for ConfigurationError exception."""

    def test_inherits_from_walltrack_error(self) -> None:
        """
        Given: ConfigurationError class
        When: Checking inheritance
        Then: It inherits from WallTrackError
        """
        from walltrack.core.exceptions import ConfigurationError, WallTrackError

        assert issubclass(ConfigurationError, WallTrackError)


class TestValidationError:
    """Tests for ValidationError exception."""

    def test_inherits_from_walltrack_error(self) -> None:
        """
        Given: ValidationError class
        When: Checking inheritance
        Then: It inherits from WallTrackError
        """
        from walltrack.core.exceptions import ValidationError, WallTrackError

        assert issubclass(ValidationError, WallTrackError)


class TestExternalServiceError:
    """Tests for ExternalServiceError exception."""

    def test_inherits_from_walltrack_error(self) -> None:
        """
        Given: ExternalServiceError class
        When: Checking inheritance
        Then: It inherits from WallTrackError
        """
        from walltrack.core.exceptions import ExternalServiceError, WallTrackError

        assert issubclass(ExternalServiceError, WallTrackError)

    def test_external_service_error_with_service_and_message(self) -> None:
        """
        Given: ExternalServiceError with service and message
        When: Exception is raised
        Then: Service name is included in error message
        """
        from walltrack.core.exceptions import ExternalServiceError

        error = ExternalServiceError(service="Helius", message="Rate limited")
        assert "Helius" in str(error)
        assert "Rate limited" in str(error)
        assert error.service == "Helius"
        assert error.status_code is None

    def test_external_service_error_with_status_code(self) -> None:
        """
        Given: ExternalServiceError with status_code
        When: Exception is raised
        Then: Status code is accessible via attribute
        """
        from walltrack.core.exceptions import ExternalServiceError

        error = ExternalServiceError(
            service="DexScreener", message="Rate limited", status_code=429
        )
        assert error.service == "DexScreener"
        assert error.status_code == 429
        assert "DexScreener" in str(error)

    def test_external_service_error_without_status_code(self) -> None:
        """
        Given: ExternalServiceError without status_code
        When: Exception is raised
        Then: Status code is None
        """
        from walltrack.core.exceptions import ExternalServiceError

        error = ExternalServiceError(service="Jupiter", message="Timeout")
        assert error.status_code is None

    def test_external_service_error_can_catch_as_walltrack_error(self) -> None:
        """
        Given: ExternalServiceError raised
        When: Catching as WallTrackError
        Then: Exception is caught
        """
        from walltrack.core.exceptions import ExternalServiceError, WallTrackError

        with pytest.raises(WallTrackError):
            raise ExternalServiceError(service="API", message="Failed", status_code=500)


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError exception."""

    def test_inherits_from_walltrack_error(self) -> None:
        """
        Given: CircuitBreakerOpenError class
        When: Checking inheritance
        Then: It inherits from WallTrackError
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError, WallTrackError

        assert issubclass(CircuitBreakerOpenError, WallTrackError)

    def test_circuit_breaker_open_error_message(self) -> None:
        """
        Given: CircuitBreakerOpenError
        When: Raised with a message
        Then: Message is accessible via str()
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError

        error = CircuitBreakerOpenError("Circuit is open for Helius API")
        assert "Circuit is open" in str(error)
        assert "Helius" in str(error)

    def test_circuit_breaker_open_error_can_catch_as_walltrack_error(self) -> None:
        """
        Given: CircuitBreakerOpenError raised
        When: Catching as WallTrackError
        Then: Exception is caught
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError, WallTrackError

        with pytest.raises(WallTrackError):
            raise CircuitBreakerOpenError("Circuit breaker triggered")
