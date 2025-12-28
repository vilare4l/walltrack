"""Unit tests for Helius webhook parser."""

import time

import pytest

from walltrack.services.helius.models import ParsedSwapEvent, SwapDirection
from walltrack.services.helius.webhook_manager import WebhookParser


@pytest.fixture
def parser() -> WebhookParser:
    """Create a WebhookParser instance."""
    return WebhookParser()


@pytest.fixture
def sample_swap_payload() -> dict:
    """Sample Helius webhook payload for a swap transaction."""
    return {
        "webhookID": "test-webhook-123",
        "type": "SWAP",
        "timestamp": 1704067200,
        "signature": "5KtPn1LGuxhFqp7tN3DwYmN7aBcDeFgHiJkLmNoPqRsTuVwXyZ",
        "fee": 5000,
        "feePayer": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "slot": 123456789,
        "nativeTransfers": [],
        "tokenTransfers": [
            {
                "fromUserAccount": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "toUserAccount": "DEXAccount123456789012345678901234567890123",
                "mint": "So11111111111111111111111111111111111111112",
                "tokenAmount": 1000000000,  # 1 SOL in lamports
            },
            {
                "fromUserAccount": "DEXAccount123456789012345678901234567890123",
                "toUserAccount": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
                "mint": "TokenMint123456789012345678901234567890123",
                "tokenAmount": 1000000,
            },
        ],
        "accountData": [
            {"account": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"},
        ],
        "source": "JUPITER",
        "description": "Test swap transaction",
    }


@pytest.fixture
def sample_transfer_payload() -> dict:
    """Sample Helius webhook payload for a non-swap transfer."""
    return {
        "webhookID": "test-webhook-456",
        "type": "TRANSFER",
        "timestamp": 1704067200,
        "signature": "TransferSig123456789012345678901234567890123",
        "fee": 5000,
        "feePayer": "Wallet123456789012345678901234567890123456",
        "slot": 123456790,
        "nativeTransfers": [],
        "tokenTransfers": [],
        "accountData": [],
        "source": "",
        "description": "Simple transfer",
    }


class TestWebhookParser:
    """Tests for WebhookParser class."""

    def test_parse_valid_swap_buy(self, parser: WebhookParser, sample_swap_payload: dict) -> None:
        """Test parsing a valid swap payload (buy direction)."""
        result = parser.parse_payload(sample_swap_payload)

        assert result is not None
        assert isinstance(result, ParsedSwapEvent)
        assert result.wallet_address == "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
        assert result.token_address == "TokenMint123456789012345678901234567890123"
        assert result.direction == SwapDirection.BUY
        assert result.amount_sol == 1.0  # 1e9 lamports = 1 SOL
        assert result.amount_token == 1000000
        assert result.slot == 123456789
        assert result.fee_lamports == 5000

    def test_parse_valid_swap_sell(self, parser: WebhookParser) -> None:
        """Test parsing a swap payload (sell direction)."""
        payload = {
            "webhookID": "test-webhook-sell",
            "type": "SWAP",
            "timestamp": 1704067200,
            "signature": "SellSig12345678901234567890123456789012345678",
            "fee": 5000,
            "feePayer": "SellerWallet123456789012345678901234567890",
            "slot": 123456800,
            "tokenTransfers": [
                {
                    "fromUserAccount": "SellerWallet123456789012345678901234567890",
                    "toUserAccount": "DEXAccount123456789012345678901234567890123",
                    "mint": "TokenMint123456789012345678901234567890123",
                    "tokenAmount": 500000,
                },
                {
                    "fromUserAccount": "DEXAccount123456789012345678901234567890123",
                    "toUserAccount": "SellerWallet123456789012345678901234567890",
                    "mint": "So11111111111111111111111111111111111111112",
                    "tokenAmount": 500000000,  # 0.5 SOL
                },
            ],
            "accountData": [],
            "source": "RAYDIUM",
        }

        result = parser.parse_payload(payload)

        assert result is not None
        assert result.direction == SwapDirection.SELL
        assert result.amount_sol == 0.5

    def test_parse_non_swap_returns_none(
        self, parser: WebhookParser, sample_transfer_payload: dict
    ) -> None:
        """Test that non-swap transactions return None."""
        result = parser.parse_payload(sample_transfer_payload)
        assert result is None

    def test_parse_empty_payload_returns_none(self, parser: WebhookParser) -> None:
        """Test that empty payloads return None."""
        result = parser.parse_payload({})
        assert result is None

    def test_parse_invalid_payload_returns_none(self, parser: WebhookParser) -> None:
        """Test that invalid payloads return None without raising."""
        result = parser.parse_payload({"invalid": "data"})
        assert result is None

    def test_parse_payload_without_token_transfers(self, parser: WebhookParser) -> None:
        """Test parsing swap without token transfers returns None."""
        payload = {
            "webhookID": "test",
            "type": "SWAP",
            "timestamp": 1704067200,
            "signature": "NoTransferSig12345678901234567890123456789",
            "fee": 5000,
            "feePayer": "Wallet123456789012345678901234567890123456",
            "slot": 123,
            "tokenTransfers": [],
            "accountData": [
                {"account": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"}
            ],
        }

        result = parser.parse_payload(payload)
        assert result is None

    def test_parse_batch(self, parser: WebhookParser, sample_swap_payload: dict) -> None:
        """Test parsing a batch of payloads."""
        payloads = [sample_swap_payload, {"invalid": "data"}, sample_swap_payload]

        results = parser.parse_batch(payloads)

        assert len(results) == 2
        assert all(isinstance(r, ParsedSwapEvent) for r in results)


class TestWebhookParserPerformance:
    """Performance tests for webhook parsing."""

    def test_parsing_completes_under_500ms(
        self, parser: WebhookParser, sample_swap_payload: dict
    ) -> None:
        """Test that parsing completes well under 500ms (NFR2)."""
        start = time.perf_counter()

        # Parse 100 payloads to get meaningful measurement
        for _ in range(100):
            parser.parse_payload(sample_swap_payload)

        elapsed_ms = (time.perf_counter() - start) * 1000
        avg_ms = elapsed_ms / 100

        # Each parse should be well under 500ms
        assert avg_ms < 50, f"Average parsing time {avg_ms:.2f}ms exceeds 50ms"

    def test_single_parse_performance(
        self, parser: WebhookParser, sample_swap_payload: dict
    ) -> None:
        """Test single parse performance."""
        start = time.perf_counter()
        result = parser.parse_payload(sample_swap_payload)
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert result is not None
        assert elapsed_ms < 100, f"Single parse took {elapsed_ms:.2f}ms"


class TestSwapDetection:
    """Tests for swap detection logic."""

    def test_detects_jupiter_swap(self, parser: WebhookParser) -> None:
        """Test detection of Jupiter DEX swap."""
        payload = {
            "type": "UNKNOWN",
            "timestamp": 1704067200,
            "signature": "JupiterSig1234567890123456789012345678901234",
            "fee": 5000,
            "feePayer": "Wallet123456789012345678901234567890123456",
            "slot": 123,
            "tokenTransfers": [
                {
                    "fromUserAccount": "Wallet123456789012345678901234567890123456",
                    "toUserAccount": "DEX12345678901234567890123456789012345678",
                    "mint": "So11111111111111111111111111111111111111112",
                    "tokenAmount": 1000000000,
                },
                {
                    "fromUserAccount": "DEX12345678901234567890123456789012345678",
                    "toUserAccount": "Wallet123456789012345678901234567890123456",
                    "mint": "Token12345678901234567890123456789012345678",
                    "tokenAmount": 1000,
                },
            ],
            "accountData": [
                {"account": "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4"}
            ],
        }

        result = parser.parse_payload(payload)
        assert result is not None
        assert result.direction == SwapDirection.BUY

    def test_detects_raydium_swap_by_source(self, parser: WebhookParser) -> None:
        """Test detection of Raydium swap via source field."""
        payload = {
            "type": "UNKNOWN",
            "timestamp": 1704067200,
            "signature": "RaydiumSig123456789012345678901234567890123",
            "fee": 5000,
            "feePayer": "Wallet123456789012345678901234567890123456",
            "slot": 123,
            "tokenTransfers": [
                {
                    "fromUserAccount": "Wallet123456789012345678901234567890123456",
                    "toUserAccount": "DEX12345678901234567890123456789012345678",
                    "mint": "So11111111111111111111111111111111111111112",
                    "tokenAmount": 1000000000,
                },
                {
                    "fromUserAccount": "DEX12345678901234567890123456789012345678",
                    "toUserAccount": "Wallet123456789012345678901234567890123456",
                    "mint": "Token12345678901234567890123456789012345678",
                    "tokenAmount": 1000,
                },
            ],
            "accountData": [],
            "source": "RAYDIUM",
        }

        result = parser.parse_payload(payload)
        assert result is not None
