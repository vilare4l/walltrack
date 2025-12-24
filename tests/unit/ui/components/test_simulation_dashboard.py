"""Tests for simulation dashboard components."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestModeIndicator:
    """Tests for mode indicator component."""

    def test_get_mode_html_simulation(self) -> None:
        """Test HTML for simulation mode."""
        with patch(
            "walltrack.ui.components.mode_indicator.get_execution_mode"
        ) as mock_mode:
            from walltrack.config.settings import ExecutionMode
            from walltrack.ui.components.mode_indicator import get_mode_html

            mock_mode.return_value = ExecutionMode.SIMULATION

            html = get_mode_html()

            assert "SIMULATION" in html
            assert "#ff6b6b" in html  # Orange/red color

    def test_get_mode_html_live(self) -> None:
        """Test HTML for live mode."""
        with patch(
            "walltrack.ui.components.mode_indicator.get_execution_mode"
        ) as mock_mode:
            from walltrack.config.settings import ExecutionMode
            from walltrack.ui.components.mode_indicator import get_mode_html

            mock_mode.return_value = ExecutionMode.LIVE

            html = get_mode_html()

            assert "LIVE" in html
            assert "#4caf50" in html  # Green color


class TestSimulationBanner:
    """Tests for simulation banner component."""

    def test_create_simulation_banner(self) -> None:
        """Test simulation banner creation."""
        from walltrack.ui.components.simulation_dashboard import (
            create_simulation_banner,
        )

        banner = create_simulation_banner()

        # Just check it returns a Gradio HTML component
        assert hasattr(banner, "value")
        assert "SIMULATION MODE" in banner.value
        assert "NOT real" in banner.value


class TestGetSimulationSummary:
    """Tests for get_simulation_summary function."""

    async def test_returns_portfolio_summary(self) -> None:
        """Test that summary returns expected keys."""
        from decimal import Decimal
        from datetime import datetime, UTC

        mock_portfolio = MagicMock()
        mock_portfolio.total_pnl = Decimal("150.50")
        mock_portfolio.total_unrealized_pnl = Decimal("100.00")
        mock_portfolio.total_realized_pnl = Decimal("50.50")
        mock_portfolio.position_count = 3
        mock_portfolio.positions_with_stale_prices = 1
        mock_portfolio.calculated_at = datetime.now(UTC)

        mock_calculator = MagicMock()
        mock_calculator.calculate_portfolio_pnl = AsyncMock(return_value=mock_portfolio)

        with patch(
            "walltrack.ui.components.simulation_dashboard.get_pnl_calculator",
            return_value=mock_calculator,
        ):
            from walltrack.ui.components.simulation_dashboard import (
                get_simulation_summary,
            )

            summary = await get_simulation_summary()

            assert summary["total_pnl"] == 150.50
            assert summary["unrealized_pnl"] == 100.00
            assert summary["realized_pnl"] == 50.50
            assert summary["position_count"] == 3
            assert summary["stale_prices"] == 1


class TestGetSimulationPositionsData:
    """Tests for get_simulation_positions_data function."""

    async def test_returns_formatted_positions(self) -> None:
        """Test that positions are formatted correctly."""
        from decimal import Decimal
        from datetime import datetime, UTC

        # Mock position
        mock_position = MagicMock()
        mock_position.token_address = "TestToken1111111111111111111111111111111111"
        mock_position.entry_price = 0.001
        mock_position.current_amount_tokens = 100000.0

        # Mock price cache
        mock_price_cache = MagicMock()
        mock_price_cache.price = Decimal("0.002")
        mock_price_cache.is_stale = False

        mock_position_service = MagicMock()
        mock_position_service.get_active_positions = AsyncMock(
            return_value=[mock_position]
        )

        mock_calculator = MagicMock()
        mock_calculator._get_current_price = AsyncMock(return_value=mock_price_cache)

        with patch(
            "walltrack.ui.components.simulation_dashboard.get_position_service",
            return_value=mock_position_service,
        ):
            with patch(
                "walltrack.ui.components.simulation_dashboard.get_pnl_calculator",
                return_value=mock_calculator,
            ):
                from walltrack.ui.components.simulation_dashboard import (
                    get_simulation_positions_data,
                )

                positions = await get_simulation_positions_data()

                assert len(positions) == 1
                assert "Token" in positions[0]
                assert "Entry Price" in positions[0]
                assert "Current Price" in positions[0]
                assert "Status" in positions[0]
                assert positions[0]["Status"] == "SIMULATED"

    async def test_handles_stale_prices(self) -> None:
        """Test that stale prices are indicated."""
        from decimal import Decimal

        mock_position = MagicMock()
        mock_position.token_address = "TestToken1111111111111111111111111111111111"
        mock_position.entry_price = 0.001
        mock_position.current_amount_tokens = 100000.0

        mock_price_cache = MagicMock()
        mock_price_cache.price = Decimal("0.002")
        mock_price_cache.is_stale = True  # Stale price

        mock_position_service = MagicMock()
        mock_position_service.get_active_positions = AsyncMock(
            return_value=[mock_position]
        )

        mock_calculator = MagicMock()
        mock_calculator._get_current_price = AsyncMock(return_value=mock_price_cache)

        with patch(
            "walltrack.ui.components.simulation_dashboard.get_position_service",
            return_value=mock_position_service,
        ):
            with patch(
                "walltrack.ui.components.simulation_dashboard.get_pnl_calculator",
                return_value=mock_calculator,
            ):
                from walltrack.ui.components.simulation_dashboard import (
                    get_simulation_positions_data,
                )

                positions = await get_simulation_positions_data()

                # Stale indicator should be present
                assert "⚠️" in positions[0]["Current Price"]
