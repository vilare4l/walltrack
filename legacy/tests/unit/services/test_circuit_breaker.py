"""Unit tests for circuit breaker implementation.

Test ID: 1.3-UNIT-001
"""

from datetime import datetime, timedelta

import pytest

from walltrack.core.exceptions import CircuitBreakerOpenError
from walltrack.services.base import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_initial_state_is_closed(self) -> None:
        """Circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_can_execute_when_closed(self) -> None:
        """Requests can execute when circuit is closed."""
        cb = CircuitBreaker()
        assert cb.can_execute() is True

    def test_record_success_resets_failure_count(self) -> None:
        """Recording success resets the failure counter."""
        cb = CircuitBreaker()
        cb.failure_count = 3
        cb.record_success()
        assert cb.failure_count == 0
        assert cb.state == CircuitState.CLOSED

    def test_record_failure_increments_count(self) -> None:
        """Recording failure increments the counter."""
        cb = CircuitBreaker(failure_threshold=5)
        cb.record_failure()
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_circuit_opens_after_threshold(self) -> None:
        """Circuit opens after reaching failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN
        assert cb.failure_count == 3

    def test_cannot_execute_when_open(self) -> None:
        """Requests cannot execute when circuit is open."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)

        for _ in range(3):
            cb.record_failure()

        assert cb.can_execute() is False

    def test_half_open_after_cooldown(self) -> None:
        """Circuit transitions to HALF_OPEN after cooldown."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)

        for _ in range(3):
            cb.record_failure()

        # Simulate time passing
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=31)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self) -> None:
        """Successful request in HALF_OPEN closes the circuit."""
        cb = CircuitBreaker(failure_threshold=3)
        cb.state = CircuitState.HALF_OPEN
        cb.failure_count = 3

        cb.record_success()

        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_raise_if_open_when_closed(self) -> None:
        """raise_if_open does nothing when circuit is closed."""
        cb = CircuitBreaker()
        cb.raise_if_open()  # Should not raise

    def test_raise_if_open_when_open(self) -> None:
        """raise_if_open raises exception when circuit is open."""
        cb = CircuitBreaker(failure_threshold=3)

        for _ in range(3):
            cb.record_failure()

        with pytest.raises(CircuitBreakerOpenError):
            cb.raise_if_open()

    def test_cooldown_not_exceeded(self) -> None:
        """Circuit stays open during cooldown period."""
        cb = CircuitBreaker(failure_threshold=3, cooldown_seconds=30)

        for _ in range(3):
            cb.record_failure()

        # Simulate only partial cooldown time passing
        cb.last_failure_time = datetime.utcnow() - timedelta(seconds=10)

        assert cb.can_execute() is False
        assert cb.state == CircuitState.OPEN
