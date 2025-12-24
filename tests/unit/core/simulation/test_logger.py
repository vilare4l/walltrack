"""Tests for simulation logger."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSimulationEventType:
    """Tests for SimulationEventType enum."""

    def test_event_types_exist(self) -> None:
        """Test that all expected event types exist."""
        from walltrack.core.simulation.logger import SimulationEventType

        assert hasattr(SimulationEventType, "TRADE_EXECUTED")
        assert hasattr(SimulationEventType, "POSITION_OPENED")
        assert hasattr(SimulationEventType, "POSITION_CLOSED")
        assert hasattr(SimulationEventType, "CIRCUIT_BREAKER")
        assert hasattr(SimulationEventType, "SIGNAL_PROCESSED")

    def test_event_types_are_strings(self) -> None:
        """Test that event types are string values."""
        from walltrack.core.simulation.logger import SimulationEventType

        assert SimulationEventType.TRADE_EXECUTED.value == "trade_executed"
        assert SimulationEventType.CIRCUIT_BREAKER.value == "circuit_breaker"


class TestSimulationLogger:
    """Tests for SimulationLogger class."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create mock Supabase client."""
        mock = MagicMock()
        mock.insert = AsyncMock(return_value={})
        return mock


class TestLogTrade(TestSimulationLogger):
    """Tests for log_trade method."""

    async def test_log_trade_stores_event(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that trade is logged to database."""
        with patch(
            "walltrack.core.simulation.logger.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.simulation.logger import SimulationLogger

            logger = SimulationLogger()
            await logger.log_trade(
                token_address="TestToken1111111111111111111111111111111111",
                side="buy",
                amount=1.0,
                price=0.001,
                signal_id="sig-123",
                pnl=0.5,
            )

            mock_supabase.insert.assert_called_once()
            call_args = mock_supabase.insert.call_args
            assert call_args[0][0] == "simulation_events"
            record = call_args[0][1]
            assert record["event_type"] == "trade_executed"
            assert record["simulated"] is True
            assert record["data"]["token_address"] == "TestToken1111111111111111111111111111111111"
            assert record["data"]["side"] == "buy"


class TestLogCircuitBreaker(TestSimulationLogger):
    """Tests for log_circuit_breaker method."""

    async def test_log_circuit_breaker_stores_event(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that circuit breaker event is logged."""
        with patch(
            "walltrack.core.simulation.logger.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.simulation.logger import SimulationLogger

            logger = SimulationLogger()
            await logger.log_circuit_breaker(
                breaker_type="drawdown",
                trigger_value=15.0,
                threshold=10.0,
                action="pause",
            )

            mock_supabase.insert.assert_called_once()
            call_args = mock_supabase.insert.call_args
            record = call_args[0][1]
            assert record["event_type"] == "circuit_breaker"
            assert record["data"]["breaker_type"] == "drawdown"
            assert record["data"]["action"] == "pause"


class TestLogSignalProcessed(TestSimulationLogger):
    """Tests for log_signal_processed method."""

    async def test_log_signal_processed_stores_event(
        self,
        mock_supabase: MagicMock,
    ) -> None:
        """Test that signal processing is logged."""
        with patch(
            "walltrack.core.simulation.logger.get_supabase_client",
            return_value=mock_supabase,
        ):
            from walltrack.core.simulation.logger import SimulationLogger

            logger = SimulationLogger()
            await logger.log_signal_processed(
                signal_id="sig-456",
                score=85.5,
                decision="trade",
                reason="High conviction signal",
            )

            mock_supabase.insert.assert_called_once()
            call_args = mock_supabase.insert.call_args
            record = call_args[0][1]
            assert record["event_type"] == "signal_processed"
            assert record["data"]["signal_id"] == "sig-456"
            assert record["data"]["score"] == 85.5
            assert record["data"]["decision"] == "trade"


class TestGetSimulationLogger:
    """Tests for get_simulation_logger singleton."""

    async def test_returns_singleton_instance(self) -> None:
        """Test that get_simulation_logger returns the same instance."""
        from walltrack.core.simulation.logger import (
            SimulationLogger,
            get_simulation_logger,
        )

        # Reset singleton
        import walltrack.core.simulation.logger as module

        module._simulation_logger = None

        logger1 = await get_simulation_logger()
        logger2 = await get_simulation_logger()

        assert logger1 is logger2
        assert isinstance(logger1, SimulationLogger)
