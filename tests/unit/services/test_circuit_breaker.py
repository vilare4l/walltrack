"""Tests for CircuitBreaker implementation."""

from datetime import datetime, timedelta, timezone

import pytest


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_state_has_closed(self) -> None:
        """
        Given: CircuitState enum
        When: Accessing CLOSED state
        Then: State exists
        """
        from walltrack.services.base import CircuitState

        assert CircuitState.CLOSED is not None

    def test_circuit_state_has_open(self) -> None:
        """
        Given: CircuitState enum
        When: Accessing OPEN state
        Then: State exists
        """
        from walltrack.services.base import CircuitState

        assert CircuitState.OPEN is not None

    def test_circuit_state_has_half_open(self) -> None:
        """
        Given: CircuitState enum
        When: Accessing HALF_OPEN state
        Then: State exists
        """
        from walltrack.services.base import CircuitState

        assert CircuitState.HALF_OPEN is not None


class TestCircuitBreaker:
    """Tests for CircuitBreaker dataclass."""

    def test_circuit_breaker_initial_state_is_closed(self) -> None:
        """
        Given: New CircuitBreaker
        When: Created with defaults
        Then: State is CLOSED
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_default_thresholds(self) -> None:
        """
        Given: New CircuitBreaker
        When: Created with defaults
        Then: Has default threshold of 5 and cooldown of 30
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.failure_threshold == 5
        assert cb.cooldown_seconds == 30

    def test_circuit_breaker_custom_thresholds(self) -> None:
        """
        Given: CircuitBreaker with custom thresholds
        When: Created
        Then: Uses custom values
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker(failure_threshold=10, cooldown_seconds=60)
        assert cb.failure_threshold == 10
        assert cb.cooldown_seconds == 60

    def test_record_success_resets_failure_count(self) -> None:
        """
        Given: CircuitBreaker with some failures
        When: record_success() is called
        Then: Failure count is reset to 0
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        cb.failure_count = 3
        cb.record_success()
        assert cb.failure_count == 0

    def test_record_success_sets_state_to_closed(self) -> None:
        """
        Given: CircuitBreaker in HALF_OPEN state
        When: record_success() is called
        Then: State becomes CLOSED
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker()
        cb.state = CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_record_failure_increments_failure_count(self) -> None:
        """
        Given: CircuitBreaker with 0 failures
        When: record_failure() is called
        Then: Failure count is incremented
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        cb.record_failure()
        assert cb.failure_count == 1

    def test_record_failure_sets_last_failure_time(self) -> None:
        """
        Given: CircuitBreaker
        When: record_failure() is called
        Then: last_failure_time is set
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.last_failure_time is None
        cb.record_failure()
        assert cb.last_failure_time is not None

    def test_circuit_opens_after_threshold_failures(self) -> None:
        """
        Given: CircuitBreaker with threshold of 5
        When: 5 failures are recorded
        Then: Circuit opens (state = OPEN)
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=5)

        for _ in range(5):
            cb.record_failure()

        assert cb.state == CircuitState.OPEN

    def test_circuit_stays_closed_before_threshold(self) -> None:
        """
        Given: CircuitBreaker with threshold of 5
        When: 4 failures are recorded
        Then: Circuit stays closed
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=5)

        for _ in range(4):
            cb.record_failure()

        assert cb.state == CircuitState.CLOSED

    def test_can_execute_returns_true_when_closed(self) -> None:
        """
        Given: CircuitBreaker in CLOSED state
        When: can_execute() is called
        Then: Returns True
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        assert cb.can_execute() is True

    def test_can_execute_returns_false_when_open_and_not_cooled_down(self) -> None:
        """
        Given: CircuitBreaker in OPEN state, not cooled down
        When: can_execute() is called
        Then: Returns False
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(cooldown_seconds=30)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.now(timezone.utc)

        assert cb.can_execute() is False

    def test_can_execute_transitions_to_half_open_after_cooldown(self) -> None:
        """
        Given: CircuitBreaker in OPEN state, cooldown elapsed
        When: can_execute() is called
        Then: Transitions to HALF_OPEN and returns True
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(cooldown_seconds=30)
        cb.state = CircuitState.OPEN
        # Set last_failure_time to 31 seconds ago
        cb.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=31)

        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_can_execute_returns_true_when_half_open(self) -> None:
        """
        Given: CircuitBreaker in HALF_OPEN state
        When: can_execute() is called
        Then: Returns True (allows test request)
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker()
        cb.state = CircuitState.HALF_OPEN

        assert cb.can_execute() is True

    def test_half_open_failure_reopens_circuit(self) -> None:
        """
        Given: CircuitBreaker in HALF_OPEN state
        When: record_failure() is called
        Then: Circuit reopens (OPEN) with reset failure count
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(failure_threshold=5)
        cb.state = CircuitState.HALF_OPEN
        cb.failure_count = 4  # Previous failures

        cb.record_failure()

        # Should reopen immediately in HALF_OPEN state
        assert cb.state == CircuitState.OPEN

    def test_raise_if_open_does_nothing_when_closed(self) -> None:
        """
        Given: CircuitBreaker in CLOSED state
        When: raise_if_open() is called
        Then: No exception raised
        """
        from walltrack.services.base import CircuitBreaker

        cb = CircuitBreaker()
        cb.raise_if_open()  # Should not raise

    def test_raise_if_open_raises_when_open(self) -> None:
        """
        Given: CircuitBreaker in OPEN state, not cooled down
        When: raise_if_open() is called
        Then: CircuitBreakerOpenError is raised
        """
        from walltrack.core.exceptions import CircuitBreakerOpenError
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(cooldown_seconds=30)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.now(timezone.utc)

        with pytest.raises(CircuitBreakerOpenError):
            cb.raise_if_open()

    def test_raise_if_open_transitions_to_half_open_after_cooldown(self) -> None:
        """
        Given: CircuitBreaker in OPEN state, cooldown elapsed
        When: raise_if_open() is called
        Then: Transitions to HALF_OPEN and does not raise
        """
        from walltrack.services.base import CircuitBreaker, CircuitState

        cb = CircuitBreaker(cooldown_seconds=30)
        cb.state = CircuitState.OPEN
        cb.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=31)

        cb.raise_if_open()  # Should not raise
        assert cb.state == CircuitState.HALF_OPEN
