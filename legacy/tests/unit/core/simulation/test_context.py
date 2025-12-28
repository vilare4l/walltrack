"""Tests for execution mode context management."""

import pytest

from walltrack.config.settings import ExecutionMode


class TestExecutionMode:
    """Tests for ExecutionMode enum."""

    def test_execution_mode_values(self) -> None:
        """Test ExecutionMode enum has correct values."""
        assert ExecutionMode.LIVE.value == "live"
        assert ExecutionMode.SIMULATION.value == "simulation"

    def test_execution_mode_is_string_enum(self) -> None:
        """Test ExecutionMode is a string enum."""
        assert isinstance(ExecutionMode.LIVE, str)
        assert isinstance(ExecutionMode.SIMULATION, str)

    def test_execution_mode_from_string(self) -> None:
        """Test creating ExecutionMode from string."""
        assert ExecutionMode("live") == ExecutionMode.LIVE
        assert ExecutionMode("simulation") == ExecutionMode.SIMULATION


class TestExecutionModeContext:
    """Tests for execution mode context functions."""

    def test_get_execution_mode_default(self) -> None:
        """Test default execution mode is SIMULATION."""
        from walltrack.core.simulation.context import get_execution_mode

        assert get_execution_mode() == ExecutionMode.SIMULATION

    def test_is_simulation_mode_default(self) -> None:
        """Test is_simulation_mode returns True by default."""
        from walltrack.core.simulation.context import is_simulation_mode

        assert is_simulation_mode() is True

    def test_is_live_mode_default(self) -> None:
        """Test is_live_mode returns False by default."""
        from walltrack.core.simulation.context import is_live_mode

        assert is_live_mode() is False

    def test_execution_mode_context_manager(self) -> None:
        """Test context manager for temporary mode override."""
        from walltrack.core.simulation.context import (
            execution_mode_context,
            get_execution_mode,
        )

        # Default is SIMULATION
        assert get_execution_mode() == ExecutionMode.SIMULATION

        # Override to LIVE within context
        with execution_mode_context(ExecutionMode.LIVE):
            assert get_execution_mode() == ExecutionMode.LIVE

        # Returns to default after context
        assert get_execution_mode() == ExecutionMode.SIMULATION

    def test_execution_mode_context_nested(self) -> None:
        """Test nested context managers work correctly."""
        from walltrack.core.simulation.context import (
            execution_mode_context,
            get_execution_mode,
        )

        assert get_execution_mode() == ExecutionMode.SIMULATION

        with execution_mode_context(ExecutionMode.LIVE):
            assert get_execution_mode() == ExecutionMode.LIVE

            with execution_mode_context(ExecutionMode.SIMULATION):
                assert get_execution_mode() == ExecutionMode.SIMULATION

            assert get_execution_mode() == ExecutionMode.LIVE

        assert get_execution_mode() == ExecutionMode.SIMULATION

    def test_execution_mode_context_exception_safety(self) -> None:
        """Test context manager properly resets on exception."""
        from walltrack.core.simulation.context import (
            execution_mode_context,
            get_execution_mode,
        )

        assert get_execution_mode() == ExecutionMode.SIMULATION

        with pytest.raises(ValueError):
            with execution_mode_context(ExecutionMode.LIVE):
                assert get_execution_mode() == ExecutionMode.LIVE
                raise ValueError("Test error")

        # Mode should be restored even after exception
        assert get_execution_mode() == ExecutionMode.SIMULATION


class TestInitializeExecutionMode:
    """Tests for initialize_execution_mode function."""

    def test_initialize_from_settings(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Test initializing execution mode from settings."""
        from walltrack.config.settings import Settings
        from walltrack.core.simulation.context import (
            get_execution_mode,
            initialize_execution_mode,
        )

        # Mock settings to return LIVE mode
        mock_settings = Settings(execution_mode=ExecutionMode.LIVE)
        monkeypatch.setattr(
            "walltrack.core.simulation.context.get_settings", lambda: mock_settings
        )

        initialize_execution_mode()
        assert get_execution_mode() == ExecutionMode.LIVE
