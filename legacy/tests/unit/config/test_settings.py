"""Unit tests for application settings.

Test ID: 1.2-UNIT-001
"""

import os
from unittest.mock import patch

import pytest
from pydantic import SecretStr, ValidationError

from walltrack.config.settings import Settings


class TestSettingsValidation:
    """Tests for Settings validation."""

    def test_default_settings_are_valid(self) -> None:
        """Default settings should pass all validation."""
        # Clear environment variables that would override defaults
        env_vars_to_clear = ["DEBUG", "LOG_LEVEL", "PORT"]
        original_values = {k: os.environ.pop(k, None) for k in env_vars_to_clear}

        try:
            # Use _env_file=None to ignore .env and test true defaults
            settings = Settings(_env_file=None)  # type: ignore[call-arg]
            assert settings.port == 8000
            assert settings.debug is False
            assert settings.log_level == "INFO"
        finally:
            # Restore original environment
            for k, v in original_values.items():
                if v is not None:
                    os.environ[k] = v

    def test_port_must_be_valid_range(self) -> None:
        """Port must be between 1 and 65535."""
        with pytest.raises(ValidationError) as exc_info:
            Settings(port=0)
        assert "greater than or equal to 1" in str(exc_info.value)

        with pytest.raises(ValidationError) as exc_info:
            Settings(port=70000)
        assert "less than or equal to 65535" in str(exc_info.value)

    def test_log_level_must_be_valid(self) -> None:
        """Log level must be one of the allowed values."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        for level in valid_levels:
            settings = Settings(log_level=level)  # type: ignore[arg-type]
            assert settings.log_level == level

        with pytest.raises(ValidationError):
            Settings(log_level="INVALID")  # type: ignore[arg-type]

    def test_neo4j_uri_validation(self) -> None:
        """Neo4j URI must start with valid protocol."""
        # Valid URIs
        Settings(neo4j_uri="bolt://localhost:7687")
        Settings(neo4j_uri="neo4j://localhost:7687")
        Settings(neo4j_uri="neo4j+s://localhost:7687")

        # Invalid URI
        with pytest.raises(ValidationError) as exc_info:
            Settings(neo4j_uri="http://localhost:7687")
        assert "Neo4j URI must start with" in str(exc_info.value)

    def test_supabase_url_validation(self) -> None:
        """Supabase URL must use HTTP(S) protocol."""
        # Valid URLs
        Settings(supabase_url="http://localhost:54321")
        Settings(supabase_url="https://myproject.supabase.co")

        # Invalid URL
        with pytest.raises(ValidationError) as exc_info:
            Settings(supabase_url="bolt://localhost:54321")
        assert "Supabase URL must start with" in str(exc_info.value)

    def test_score_threshold_range(self) -> None:
        """Score threshold must be between 0 and 1."""
        Settings(score_threshold=0.0)
        Settings(score_threshold=1.0)
        Settings(score_threshold=0.5)

        with pytest.raises(ValidationError):
            Settings(score_threshold=-0.1)

        with pytest.raises(ValidationError):
            Settings(score_threshold=1.1)


class TestSecretProtection:
    """Tests for secret value protection."""

    def test_secrets_use_secretstr_type(self) -> None:
        """All sensitive values should use SecretStr type."""
        settings = Settings()

        # Check types
        assert isinstance(settings.neo4j_password, SecretStr)
        assert isinstance(settings.supabase_key, SecretStr)
        assert isinstance(settings.helius_api_key, SecretStr)
        assert isinstance(settings.helius_webhook_secret, SecretStr)
        assert isinstance(settings.trading_wallet_private_key, SecretStr)

    def test_secrets_not_exposed_in_repr(self) -> None:
        """Secrets should not be exposed in string representation."""
        settings = Settings(
            neo4j_password=SecretStr("super_secret_password"),
            helius_api_key=SecretStr("my_api_key"),
        )

        repr_str = repr(settings)

        # Secrets should be masked
        assert "super_secret_password" not in repr_str
        assert "my_api_key" not in repr_str
        assert "**********" in repr_str

    def test_secrets_not_exposed_in_dict(self) -> None:
        """Secrets should not be exposed when dumping to dict."""
        settings = Settings(
            neo4j_password=SecretStr("super_secret_password"),
        )

        # Default dump should hide secrets
        data = settings.model_dump()
        assert data["neo4j_password"] != "super_secret_password"

    def test_secrets_accessible_via_get_secret_value(self) -> None:
        """Secrets can be accessed via get_secret_value() when needed."""
        settings = Settings(
            neo4j_password=SecretStr("my_password"),
        )

        assert settings.neo4j_password.get_secret_value() == "my_password"


class TestEnvironmentLoading:
    """Tests for environment variable loading."""

    def test_settings_load_from_env(self) -> None:
        """Settings should load values from environment variables."""
        with patch.dict(
            os.environ,
            {
                "DEBUG": "true",
                "PORT": "9000",
                "LOG_LEVEL": "DEBUG",
            },
        ):
            settings = Settings()
            assert settings.debug is True
            assert settings.port == 9000
            assert settings.log_level == "DEBUG"

    def test_env_values_override_defaults(self) -> None:
        """Environment values should override default values."""
        with patch.dict(
            os.environ,
            {
                "MAX_CONCURRENT_POSITIONS": "10",
                "SCORE_THRESHOLD": "0.80",
            },
        ):
            settings = Settings()
            assert settings.max_concurrent_positions == 10
            assert settings.score_threshold == 0.80

    def test_case_insensitive_env_loading(self) -> None:
        """Environment variables should be loaded case-insensitively."""
        with patch.dict(os.environ, {"debug": "true"}):
            settings = Settings()
            assert settings.debug is True


class TestCacheConfiguration:
    """Tests for cache-related settings."""

    def test_cache_ttl_ranges(self) -> None:
        """Cache TTL values must be within valid ranges."""
        # Valid values
        Settings(token_cache_ttl=60)
        Settings(token_cache_ttl=3600)
        Settings(wallet_cache_ttl=10)
        Settings(wallet_cache_ttl=300)

        # Invalid values
        with pytest.raises(ValidationError):
            Settings(token_cache_ttl=30)  # Below minimum

        with pytest.raises(ValidationError):
            Settings(wallet_cache_ttl=5)  # Below minimum


class TestRetryConfiguration:
    """Tests for retry and circuit breaker settings."""

    def test_retry_settings_ranges(self) -> None:
        """Retry settings must be within valid ranges."""
        Settings(max_retries=1)
        Settings(max_retries=10)

        with pytest.raises(ValidationError):
            Settings(max_retries=0)

        with pytest.raises(ValidationError):
            Settings(max_retries=20)

    def test_circuit_breaker_settings(self) -> None:
        """Circuit breaker settings must be valid."""
        Settings(circuit_breaker_threshold=3, circuit_breaker_cooldown=10)
        Settings(circuit_breaker_threshold=20, circuit_breaker_cooldown=300)

        with pytest.raises(ValidationError):
            Settings(circuit_breaker_threshold=2)  # Below minimum

        with pytest.raises(ValidationError):
            Settings(circuit_breaker_cooldown=5)  # Below minimum
