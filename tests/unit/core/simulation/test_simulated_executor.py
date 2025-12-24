"""Tests for simulated trade executor."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from walltrack.core.simulation.simulated_executor import SimulatedTradeExecutor
from walltrack.models.token import TokenCharacteristics, TokenFetchResult, TokenSource


class TestSimulatedTradeExecutor:
    """Tests for SimulatedTradeExecutor class."""

    @pytest.fixture
    def mock_token_result(self) -> TokenFetchResult:
        """Create a mock token fetch result."""
        token = TokenCharacteristics(
            token_address="TestToken1111111111111111111111111111111111",
            name="Test Token",
            symbol="TEST",
            price_usd=0.001,
            price_sol=0.00001,
            source=TokenSource.DEXSCREENER,
        )
        return TokenFetchResult(
            success=True,
            token=token,
            source=TokenSource.DEXSCREENER,
            fetch_time_ms=50.0,
        )

    @pytest.fixture
    def mock_sol_result(self) -> TokenFetchResult:
        """Create a mock SOL fetch result."""
        token = TokenCharacteristics(
            token_address="So11111111111111111111111111111111111111112",
            name="Wrapped SOL",
            symbol="SOL",
            price_usd=100.0,
            price_sol=1.0,
            source=TokenSource.DEXSCREENER,
        )
        return TokenFetchResult(
            success=True,
            token=token,
            source=TokenSource.DEXSCREENER,
            fetch_time_ms=50.0,
        )

    @pytest.fixture
    def executor(self) -> SimulatedTradeExecutor:
        """Create a simulated trade executor."""
        return SimulatedTradeExecutor()


class TestExecuteBuy(TestSimulatedTradeExecutor):
    """Tests for execute_buy method."""

    async def test_buy_returns_trade_record(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that execute_buy returns a valid trade record."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_buy(
                token_address="TestToken1111111111111111111111111111111111",
                amount_sol=1.0,
                slippage_bps=100,
            )

            assert result["success"] is True
            assert result["simulated"] is True
            assert result["side"] == "buy"
            assert result["amount_sol"] == 1.0
            assert "tx_signature" in result
            assert result["tx_signature"].startswith("SIM_")

    async def test_buy_applies_slippage_correctly(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that slippage is applied correctly (price increases for buyer)."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_buy(
                token_address="TestToken1111111111111111111111111111111111",
                amount_sol=1.0,
                slippage_bps=100,  # 1% slippage
            )

            # Execution price should be higher than market price (1% more)
            market_price = 0.001
            expected_execution_price = market_price * 1.01
            assert abs(result["price_usd"] - expected_execution_price) < 0.0001
            assert result["market_price_at_execution"] == market_price

    async def test_buy_calculates_tokens_received(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that tokens received is calculated correctly."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_buy(
                token_address="TestToken1111111111111111111111111111111111",
                amount_sol=1.0,
                slippage_bps=0,  # No slippage for easier calculation
            )

            # 1 SOL * $100 = $100 / $0.001 = 100,000 tokens
            assert result["amount_tokens"] == pytest.approx(100000.0, rel=0.01)


class TestExecuteSell(TestSimulatedTradeExecutor):
    """Tests for execute_sell method."""

    async def test_sell_returns_trade_record(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that execute_sell returns a valid trade record."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_sell(
                token_address="TestToken1111111111111111111111111111111111",
                amount_tokens=10000.0,
                slippage_bps=100,
            )

            assert result["success"] is True
            assert result["simulated"] is True
            assert result["side"] == "sell"
            assert result["amount_tokens"] == 10000.0
            assert "tx_signature" in result
            assert result["tx_signature"].startswith("SIM_")

    async def test_sell_applies_slippage_correctly(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that slippage is applied correctly (price decreases for seller)."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_sell(
                token_address="TestToken1111111111111111111111111111111111",
                amount_tokens=10000.0,
                slippage_bps=100,  # 1% slippage
            )

            # Execution price should be lower than market price (1% less)
            market_price = 0.001
            expected_execution_price = market_price * 0.99
            assert abs(result["price_usd"] - expected_execution_price) < 0.0001
            assert result["market_price_at_execution"] == market_price

    async def test_sell_calculates_sol_received(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that SOL received is calculated correctly."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_sell(
                token_address="TestToken1111111111111111111111111111111111",
                amount_tokens=100000.0,
                slippage_bps=0,  # No slippage for easier calculation
            )

            # 100,000 tokens * $0.001 = $100 / $100 = 1 SOL
            assert result["amount_sol"] == pytest.approx(1.0, rel=0.01)


class TestPriceFetching(TestSimulatedTradeExecutor):
    """Tests for price fetching methods."""

    async def test_fallback_price_when_api_fails(
        self,
        executor: SimulatedTradeExecutor,
    ) -> None:
        """Test that fallback price is used when API fails."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                return_value=TokenFetchResult(
                    success=False,
                    token=None,
                    source=TokenSource.DEXSCREENER,
                    fetch_time_ms=50.0,
                    error_message="API error",
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_buy(
                token_address="TestToken1111111111111111111111111111111111",
                amount_sol=1.0,
                slippage_bps=100,
            )

            # Should still return a valid result with fallback price
            assert result["success"] is True
            assert result["simulated"] is True

    async def test_sol_price_fallback(
        self,
        executor: SimulatedTradeExecutor,
    ) -> None:
        """Test that SOL price fallback is used when API fails."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                return_value=TokenFetchResult(
                    success=False,
                    token=None,
                    source=TokenSource.DEXSCREENER,
                    fetch_time_ms=50.0,
                )
            )
            mock_get_client.return_value = mock_client

            sol_price = await executor._get_sol_price()
            assert sol_price == Decimal("100")  # Fallback price


class TestTradeRecord(TestSimulatedTradeExecutor):
    """Tests for trade record structure."""

    async def test_trade_record_has_required_fields(
        self,
        executor: SimulatedTradeExecutor,
        mock_token_result: TokenFetchResult,
        mock_sol_result: TokenFetchResult,
    ) -> None:
        """Test that trade record contains all required fields."""
        with patch.object(executor, "_get_dex_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.fetch_token = AsyncMock(
                side_effect=lambda addr: (
                    mock_sol_result
                    if addr == "So11111111111111111111111111111111111111112"
                    else mock_token_result
                )
            )
            mock_get_client.return_value = mock_client

            result = await executor.execute_buy(
                token_address="TestToken1111111111111111111111111111111111",
                amount_sol=1.0,
                slippage_bps=100,
            )

            required_fields = [
                "id",
                "token_address",
                "side",
                "amount_sol",
                "amount_tokens",
                "price_usd",
                "slippage_bps",
                "simulated",
                "tx_signature",
                "executed_at",
                "market_price_at_execution",
                "success",
            ]

            for field in required_fields:
                assert field in result, f"Missing required field: {field}"
