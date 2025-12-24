"""Execution mode context management."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

from walltrack.config.settings import ExecutionMode, get_settings

_execution_mode: ContextVar[ExecutionMode] = ContextVar(
    "execution_mode",
    default=ExecutionMode.SIMULATION,
)


def get_execution_mode() -> ExecutionMode:
    """Get current execution mode."""
    return _execution_mode.get()


def is_simulation_mode() -> bool:
    """Check if running in simulation mode."""
    return get_execution_mode() == ExecutionMode.SIMULATION


def is_live_mode() -> bool:
    """Check if running in live mode."""
    return get_execution_mode() == ExecutionMode.LIVE


@contextmanager
def execution_mode_context(mode: ExecutionMode) -> Generator[None, None, None]:
    """Context manager for temporary mode override."""
    token = _execution_mode.set(mode)
    try:
        yield
    finally:
        _execution_mode.reset(token)


def initialize_execution_mode() -> None:
    """Initialize execution mode from settings."""
    settings = get_settings()
    _execution_mode.set(settings.execution_mode)
