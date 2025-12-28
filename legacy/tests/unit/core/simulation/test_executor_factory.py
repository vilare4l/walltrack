"""Tests for trade executor factory."""

import pytest

from walltrack.config.settings import ExecutionMode


class TestGetTradeExecutor:
    """Tests for get_trade_executor factory function."""

    def test_returns_simulated_executor_in_simulation_mode(self) -> None:
        """Test factory returns SimulatedTradeExecutor in simulation mode."""
        from walltrack.core.simulation.context import execution_mode_context
        from walltrack.core.trading.executor_factory import get_trade_executor
        from walltrack.core.simulation.simulated_executor import SimulatedTradeExecutor

        with execution_mode_context(ExecutionMode.SIMULATION):
            executor = get_trade_executor()
            assert isinstance(executor, SimulatedTradeExecutor)

    def test_returns_live_executor_in_live_mode(self) -> None:
        """Test factory returns JupiterExecutor in live mode."""
        from walltrack.core.simulation.context import execution_mode_context
        from walltrack.core.trading.executor_factory import get_trade_executor
        from walltrack.core.trading.jupiter_executor import JupiterExecutor

        with execution_mode_context(ExecutionMode.LIVE):
            executor = get_trade_executor()
            assert isinstance(executor, JupiterExecutor)

    def test_executor_has_execute_buy_method(self) -> None:
        """Test executor implements execute_buy method."""
        from walltrack.core.simulation.context import execution_mode_context
        from walltrack.core.trading.executor_factory import get_trade_executor

        with execution_mode_context(ExecutionMode.SIMULATION):
            executor = get_trade_executor()
            assert hasattr(executor, "execute_buy")
            assert callable(executor.execute_buy)

    def test_executor_has_execute_sell_method(self) -> None:
        """Test executor implements execute_sell method."""
        from walltrack.core.simulation.context import execution_mode_context
        from walltrack.core.trading.executor_factory import get_trade_executor

        with execution_mode_context(ExecutionMode.SIMULATION):
            executor = get_trade_executor()
            assert hasattr(executor, "execute_sell")
            assert callable(executor.execute_sell)
