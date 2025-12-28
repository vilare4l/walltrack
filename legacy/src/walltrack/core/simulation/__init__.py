"""Simulation mode module for paper trading."""

from walltrack.core.simulation.context import (
    ExecutionMode,
    execution_mode_context,
    get_execution_mode,
    initialize_execution_mode,
    is_live_mode,
    is_simulation_mode,
)

__all__ = [
    "ExecutionMode",
    "execution_mode_context",
    "get_execution_mode",
    "initialize_execution_mode",
    "is_live_mode",
    "is_simulation_mode",
]
