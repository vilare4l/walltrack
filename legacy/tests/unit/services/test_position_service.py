"""Tests for PositionService with simulation support."""

from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from walltrack.models.position import Position, PositionStatus


class TestPositionService:
    """Tests for PositionService class."""

    @pytest.fixture
    def mock_supabase(self) -> MagicMock:
        """Create mock Supabase client."""
        mock = MagicMock()
        mock.insert = AsyncMock()
        mock.select = AsyncMock()
        mock.update = AsyncMock()
        return mock

    @pytest.fixture
    def sample_position_data(self) -> dict:
        """Create sample position data."""
        return {
            "id": str(uuid4()),
            "signal_id": str(uuid4()),
            "token_address": "TestToken1111111111111111111111111111111111",
            "entry_price": 0.001,
            "entry_amount_sol": 1.0,
            "entry_amount_tokens": 100000.0,
            "current_amount_tokens": 100000.0,
            "exit_strategy_id": "default",
            "conviction_tier": "standard",
            "status": "open",
            "simulated": True,
            "entry_time": datetime.now(UTC).isoformat(),
            "created_at": datetime.now(UTC).isoformat(),
            "updated_at": datetime.now(UTC).isoformat(),
        }


class TestGetActivePositions(TestPositionService):
    """Tests for get_active_positions method."""

    async def test_get_active_positions_filters_by_simulation_mode(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that get_active_positions filters by current simulation mode."""
        from walltrack.services.position_service import PositionService

        mock_supabase.select.return_value = [sample_position_data]

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.services.position_service.is_simulation_mode",
                return_value=True,
            ):
                service = PositionService()
                positions = await service.get_active_positions()

                # Should have filtered by simulated=True
                mock_supabase.select.assert_called_once()
                call_args = mock_supabase.select.call_args
                assert call_args[1]["filters"]["simulated"] is True
                assert call_args[1]["filters"]["status"] == "open"

    async def test_get_active_positions_explicit_simulation_filter(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that explicit simulated parameter overrides mode."""
        from walltrack.services.position_service import PositionService

        mock_supabase.select.return_value = [sample_position_data]

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            service = PositionService()
            await service.get_active_positions(simulated=False)

            call_args = mock_supabase.select.call_args
            assert call_args[1]["filters"]["simulated"] is False

    async def test_get_active_positions_returns_position_objects(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that get_active_positions returns Position objects."""
        from walltrack.services.position_service import PositionService

        mock_supabase.select.return_value = [sample_position_data]

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.services.position_service.is_simulation_mode",
                return_value=True,
            ):
                service = PositionService()
                positions = await service.get_active_positions()

                assert len(positions) == 1
                assert isinstance(positions[0], Position)
                assert positions[0].simulated is True


class TestGetAllSimulatedPositions(TestPositionService):
    """Tests for get_all_simulated_positions method."""

    async def test_get_all_simulated_positions(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test getting all simulated positions regardless of status."""
        from walltrack.services.position_service import PositionService

        # Create both open and closed positions
        open_position = sample_position_data.copy()
        closed_position = sample_position_data.copy()
        closed_position["id"] = str(uuid4())
        closed_position["status"] = "closed"

        mock_supabase.select.return_value = [open_position, closed_position]

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            service = PositionService()
            positions = await service.get_all_simulated_positions()

            assert len(positions) == 2
            # Should filter only by simulated, not status
            call_args = mock_supabase.select.call_args
            assert call_args[1]["filters"]["simulated"] is True
            assert "status" not in call_args[1]["filters"]


class TestCreatePosition(TestPositionService):
    """Tests for create_position method."""

    async def test_create_position_sets_simulated_flag_from_mode(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that create_position sets simulated flag based on execution mode."""
        from walltrack.services.position_service import PositionService

        mock_supabase.insert.return_value = sample_position_data

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.services.position_service.is_simulation_mode",
                return_value=True,
            ):
                service = PositionService()
                position = await service.create_position(
                    signal_id=str(uuid4()),
                    token_address="TestToken1111111111111111111111111111111111",
                    entry_price=0.001,
                    entry_amount_sol=1.0,
                    entry_amount_tokens=100000.0,
                    exit_strategy_id="default",
                    conviction_tier="standard",
                )

                # Verify simulated flag was set
                call_args = mock_supabase.insert.call_args
                inserted_data = call_args[0][1]
                assert inserted_data["simulated"] is True

    async def test_create_position_live_mode(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that create_position sets simulated=False in live mode."""
        from walltrack.services.position_service import PositionService

        sample_position_data["simulated"] = False
        mock_supabase.insert.return_value = sample_position_data

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            with patch(
                "walltrack.services.position_service.is_simulation_mode",
                return_value=False,
            ):
                service = PositionService()
                position = await service.create_position(
                    signal_id=str(uuid4()),
                    token_address="TestToken1111111111111111111111111111111111",
                    entry_price=0.001,
                    entry_amount_sol=1.0,
                    entry_amount_tokens=100000.0,
                    exit_strategy_id="default",
                    conviction_tier="standard",
                )

                call_args = mock_supabase.insert.call_args
                inserted_data = call_args[0][1]
                assert inserted_data["simulated"] is False


class TestClosePosition(TestPositionService):
    """Tests for close_position method."""

    async def test_close_position_updates_status_and_pnl(
        self,
        mock_supabase: MagicMock,
        sample_position_data: dict,
    ) -> None:
        """Test that close_position updates status, exit price, and P&L."""
        from walltrack.services.position_service import PositionService

        position_id = sample_position_data["id"]
        closed_data = sample_position_data.copy()
        closed_data["status"] = "closed"
        closed_data["exit_price"] = 0.002
        closed_data["realized_pnl_sol"] = 1.0

        mock_supabase.update.return_value = closed_data

        with patch(
            "walltrack.services.position_service.get_supabase_client",
            return_value=mock_supabase,
        ):
            service = PositionService()
            position = await service.close_position(
                position_id=position_id,
                exit_price=0.002,
                realized_pnl_sol=1.0,
            )

            # Verify update was called with correct data
            mock_supabase.update.assert_called_once()
            call_args = mock_supabase.update.call_args
            assert call_args[0][0] == "positions"
            assert call_args[0][1]["id"] == position_id
            update_data = call_args[0][2]
            assert update_data["status"] == "closed"
            assert update_data["exit_price"] == 0.002
            assert update_data["realized_pnl_sol"] == 1.0
