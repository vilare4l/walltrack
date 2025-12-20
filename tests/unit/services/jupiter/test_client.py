"""Unit tests for JupiterClient.

Tests cover:
- Quote retrieval
- Swap transaction building
- Error classification
- Trade executor validation
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from walltrack.config.jupiter_settings import JupiterSettings
from walltrack.constants.solana import WSOL_MINT
from walltrack.models.trade import (
    FailureReason,
    SwapDirection,
    SwapQuote,
    SwapResult,
    TradeRequest,
    TradeStatus,
)
from walltrack.services.jupiter.client import (
    JupiterClient,
    QuoteError,
)


@pytest.fixture
def mock_settings():
    """Create mock Jupiter settings."""
    return JupiterSettings(
        jupiter_api_url="https://quote-api.jup.ag/v6",
        default_slippage_bps=100,
        max_trade_sol=1.0,
        min_trade_sol=0.01,
    )


@pytest.fixture
def jupiter_client(mock_settings):
    """Create Jupiter client with mock settings."""
    return JupiterClient(settings=mock_settings)


# Test token mint (valid base58)
TEST_TOKEN_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC


class TestSwapQuoteModel:
    """Tests for SwapQuote model."""

    def test_effective_price_calculation(self):
        """Test effective price is calculated correctly."""
        quote = SwapQuote(
            input_mint=WSOL_MINT,
            output_mint=TEST_TOKEN_MINT,
            input_amount=100_000_000,  # 0.1 SOL
            output_amount=1_000_000_000,  # 1000 tokens
            output_amount_min=990_000_000,
            slippage_bps=100,
            price_impact_pct=0.5,
        )

        assert quote.effective_price == 10.0  # 1000/100

    def test_effective_price_zero_input(self):
        """Test effective price with zero input."""
        quote = SwapQuote(
            input_mint=WSOL_MINT,
            output_mint=TEST_TOKEN_MINT,
            input_amount=0,
            output_amount=0,
            output_amount_min=0,
            slippage_bps=100,
            price_impact_pct=0,
        )

        assert quote.effective_price == 0.0

    def test_invalid_mint_rejected(self):
        """Test invalid mint address is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            SwapQuote(
                input_mint="invalid",
                output_mint=TEST_TOKEN_MINT,
                input_amount=100,
                output_amount=100,
                output_amount_min=99,
                slippage_bps=100,
                price_impact_pct=0,
            )


class TestSwapResultModel:
    """Tests for SwapResult model."""

    def test_was_successful_true(self):
        """Test was_successful property when successful."""
        result = SwapResult(
            success=True,
            status=TradeStatus.SUCCESS,
            tx_signature="abc123signature",
            input_amount=100_000_000,
            output_amount=1_000_000_000,
            execution_time_ms=1500,
        )

        assert result.was_successful is True

    def test_was_successful_false_no_signature(self):
        """Test was_successful false when no signature."""
        result = SwapResult(
            success=True,
            status=TradeStatus.FAILED,
            tx_signature=None,
            input_amount=100_000_000,
            execution_time_ms=1500,
        )

        assert result.was_successful is False


class TestTradeRequestModel:
    """Tests for TradeRequest model."""

    def test_valid_trade_request(self):
        """Test valid trade request creation."""
        request = TradeRequest(
            signal_id="test-signal-123",
            token_address=TEST_TOKEN_MINT,
            direction=SwapDirection.BUY,
            amount_sol=0.1,
            slippage_bps=100,
        )

        assert request.amount_sol == 0.1
        assert request.direction == SwapDirection.BUY

    def test_invalid_token_address_rejected(self):
        """Test invalid token address is rejected."""
        with pytest.raises(ValueError, match="Invalid"):
            TradeRequest(
                signal_id="test-signal-123",
                token_address="invalid",
                direction=SwapDirection.BUY,
                amount_sol=0.1,
            )

    def test_zero_amount_rejected(self):
        """Test zero amount is rejected."""
        with pytest.raises(ValueError):
            TradeRequest(
                signal_id="test-signal-123",
                token_address=TEST_TOKEN_MINT,
                direction=SwapDirection.BUY,
                amount_sol=0,
            )


class TestJupiterQuote:
    """Tests for Jupiter quote functionality."""

    @pytest.mark.asyncio
    async def test_get_quote_success(self, jupiter_client):
        """Test successful quote retrieval."""
        mock_response = {
            "inputMint": WSOL_MINT,
            "outputMint": TEST_TOKEN_MINT,
            "inAmount": "100000000",
            "outAmount": "1000000000",
            "otherAmountThreshold": "990000000",
            "priceImpactPct": "0.5",
            "routePlan": [{"source": "raydium"}],
        }

        mock_http = MagicMock()
        mock_http.get = AsyncMock(
            return_value=MagicMock(
                json=lambda: mock_response,
                raise_for_status=lambda: None,
            )
        )

        jupiter_client._http_client = mock_http

        quote = await jupiter_client.get_quote(
            input_mint=WSOL_MINT,
            output_mint=TEST_TOKEN_MINT,
            amount=100_000_000,
            slippage_bps=100,
        )

        assert quote.input_amount == 100_000_000
        assert quote.output_amount == 1_000_000_000
        assert quote.quote_source == "jupiter"

    @pytest.mark.asyncio
    async def test_get_quote_not_initialized_raises(self, jupiter_client):
        """Test that get_quote raises when not initialized."""
        from walltrack.services.jupiter.client import JupiterError

        jupiter_client._http_client = None

        with pytest.raises(JupiterError, match="not initialized"):
            await jupiter_client.get_quote(
                input_mint=WSOL_MINT,
                output_mint=TEST_TOKEN_MINT,
                amount=100_000_000,
            )

    @pytest.mark.asyncio
    async def test_get_quote_http_error_raises(self, jupiter_client):
        """Test that HTTP errors raise QuoteError."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad request"
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Bad request",
            request=MagicMock(),
            response=mock_response,
        )

        mock_http = MagicMock()
        mock_http.get = AsyncMock(return_value=mock_response)

        jupiter_client._http_client = mock_http

        with pytest.raises(QuoteError):
            await jupiter_client.get_quote(
                input_mint=WSOL_MINT,
                output_mint=TEST_TOKEN_MINT,
                amount=100_000_000,
            )


class TestErrorClassification:
    """Tests for error classification."""

    def test_classify_slippage_error(self, jupiter_client):
        """Test slippage error classification."""
        reason = jupiter_client._classify_error("Slippage tolerance exceeded")
        assert reason == FailureReason.SLIPPAGE_EXCEEDED

    def test_classify_balance_error(self, jupiter_client):
        """Test insufficient balance error classification."""
        reason = jupiter_client._classify_error("Insufficient balance for swap")
        assert reason == FailureReason.INSUFFICIENT_BALANCE

    def test_classify_expired_error(self, jupiter_client):
        """Test transaction expired error classification."""
        reason = jupiter_client._classify_error("Blockhash not found or expired")
        assert reason == FailureReason.TRANSACTION_EXPIRED

    def test_classify_unknown_error(self, jupiter_client):
        """Test unknown error classification."""
        reason = jupiter_client._classify_error("Some random error")
        assert reason == FailureReason.UNKNOWN


class TestTradeExecutor:
    """Tests for TradeExecutor."""

    @pytest.mark.asyncio
    async def test_execute_blocked_when_wallet_not_ready(self):
        """Test trade blocked when wallet not ready."""
        from walltrack.services.trade.executor import TradeExecutor

        mock_wallet = MagicMock()
        mock_wallet.is_ready_for_trading = False

        executor = TradeExecutor(wallet_client=mock_wallet)

        request = TradeRequest(
            signal_id="test-signal-id",
            token_address=TEST_TOKEN_MINT,
            direction=SwapDirection.BUY,
            amount_sol=0.1,
        )

        result = await executor.execute(request)

        assert result.success is False
        assert result.failure_reason == FailureReason.INSUFFICIENT_BALANCE
        assert "not ready" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_blocked_when_exceeds_max(self):
        """Test trade blocked when amount exceeds max."""
        from walltrack.services.trade.executor import TradeExecutor

        mock_wallet = MagicMock()
        mock_wallet.is_ready_for_trading = True

        settings = JupiterSettings(max_trade_sol=0.5, min_trade_sol=0.01)
        executor = TradeExecutor(settings=settings, wallet_client=mock_wallet)

        request = TradeRequest(
            signal_id="test-signal-id",
            token_address=TEST_TOKEN_MINT,
            direction=SwapDirection.BUY,
            amount_sol=1.0,  # Exceeds max of 0.5
        )

        result = await executor.execute(request)

        assert result.success is False
        assert "exceeds max" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_execute_blocked_when_below_min(self):
        """Test trade blocked when amount below min."""
        from walltrack.services.trade.executor import TradeExecutor

        mock_wallet = MagicMock()
        mock_wallet.is_ready_for_trading = True

        settings = JupiterSettings(max_trade_sol=1.0, min_trade_sol=0.05)
        executor = TradeExecutor(settings=settings, wallet_client=mock_wallet)

        request = TradeRequest(
            signal_id="test-signal-id",
            token_address=TEST_TOKEN_MINT,
            direction=SwapDirection.BUY,
            amount_sol=0.01,  # Below min of 0.05
        )

        result = await executor.execute(request)

        assert result.success is False
        assert "below min" in result.error_message.lower()


class TestJupiterSettings:
    """Tests for JupiterSettings."""

    def test_default_settings(self):
        """Test default settings values."""
        settings = JupiterSettings()

        assert settings.default_slippage_bps == 100
        assert settings.max_slippage_bps == 500
        assert settings.max_trade_sol == 1.0

    def test_max_slippage_must_be_gte_default(self):
        """Test max slippage validation."""
        with pytest.raises(ValueError, match="max_slippage"):
            JupiterSettings(
                default_slippage_bps=200,
                max_slippage_bps=100,  # Less than default
            )
