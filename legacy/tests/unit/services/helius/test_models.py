"""Unit tests for Helius webhook models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from walltrack.services.helius.models import (
    HeliusWebhookPayload,
    ParsedSwapEvent,
    SwapDirection,
    TokenTransfer,
    WebhookHealthStatus,
    WebhookValidationResult,
)


class TestHeliusWebhookPayload:
    """Tests for HeliusWebhookPayload model."""

    def test_valid_payload_parsing(self) -> None:
        """Test parsing a valid Helius payload."""
        data = {
            "webhookID": "webhook-123",
            "type": "SWAP",
            "timestamp": 1704067200,
            "signature": "tx-signature-123",
            "fee": 5000,
            "feePayer": "wallet-address-123",
            "slot": 123456789,
            "nativeTransfers": [],
            "tokenTransfers": [],
            "accountData": [],
        }

        payload = HeliusWebhookPayload.model_validate(data)

        assert payload.webhook_id == "webhook-123"
        assert payload.transaction_type == "SWAP"
        assert payload.timestamp == 1704067200
        assert payload.fee_payer == "wallet-address-123"

    def test_alias_fields(self) -> None:
        """Test that alias fields are correctly mapped."""
        data = {
            "webhookID": "webhook-456",
            "type": "TRANSFER",
            "timestamp": 1704067200,
            "signature": "sig",
            "fee": 5000,
            "feePayer": "payer",
            "slot": 123,
        }

        payload = HeliusWebhookPayload.model_validate(data)

        assert payload.webhook_id == "webhook-456"
        assert payload.fee_payer == "payer"

    def test_optional_fields_default(self) -> None:
        """Test that optional fields have correct defaults."""
        data = {
            "type": "SWAP",
            "timestamp": 1704067200,
            "signature": "sig",
            "fee": 5000,
            "feePayer": "payer",
            "slot": 123,
        }

        payload = HeliusWebhookPayload.model_validate(data)

        assert payload.webhook_id == ""
        assert payload.native_transfers == []
        assert payload.token_transfers == []
        assert payload.account_data == []


class TestTokenTransfer:
    """Tests for TokenTransfer model."""

    def test_valid_transfer(self) -> None:
        """Test parsing a valid token transfer."""
        data = {
            "fromUserAccount": "sender-wallet",
            "toUserAccount": "receiver-wallet",
            "mint": "token-mint-address",
            "tokenAmount": 1000000,
        }

        transfer = TokenTransfer.model_validate(data)

        assert transfer.from_account == "sender-wallet"
        assert transfer.to_account == "receiver-wallet"
        assert transfer.mint == "token-mint-address"
        assert transfer.amount == 1000000


class TestParsedSwapEvent:
    """Tests for ParsedSwapEvent model."""

    def test_valid_swap_event(self) -> None:
        """Test creating a valid swap event."""
        event = ParsedSwapEvent(
            tx_signature="tx-sig-123456789012345678901234567890123456789012",
            wallet_address="WalletAddr12345678901234567890123456789012",
            token_address="TokenMint12345678901234567890123456789012",
            direction=SwapDirection.BUY,
            amount_token=1000.0,
            amount_sol=0.5,
            timestamp=datetime.now(timezone.utc),
            slot=123456789,
            fee_lamports=5000,
        )

        assert event.direction == SwapDirection.BUY
        assert event.amount_token == 1000.0
        assert event.amount_sol == 0.5

    def test_invalid_wallet_address_too_short(self) -> None:
        """Test that short wallet addresses are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ParsedSwapEvent(
                tx_signature="tx-sig-123",
                wallet_address="short",  # Too short
                token_address="TokenMint12345678901234567890123456789012",
                direction=SwapDirection.BUY,
                amount_token=1000.0,
                amount_sol=0.5,
                timestamp=datetime.now(timezone.utc),
                slot=123456789,
                fee_lamports=5000,
            )

        assert "Invalid Solana address" in str(exc_info.value)

    def test_negative_amounts_rejected(self) -> None:
        """Test that negative amounts are rejected."""
        with pytest.raises(ValidationError):
            ParsedSwapEvent(
                tx_signature="tx-sig-123",
                wallet_address="WalletAddr12345678901234567890123456789012",
                token_address="TokenMint12345678901234567890123456789012",
                direction=SwapDirection.BUY,
                amount_token=-100.0,  # Negative
                amount_sol=0.5,
                timestamp=datetime.now(timezone.utc),
                slot=123456789,
                fee_lamports=5000,
            )

    def test_processing_started_at_default(self) -> None:
        """Test that processing_started_at has a default value."""
        event = ParsedSwapEvent(
            tx_signature="tx-sig-123456789012345678901234567890123456789012",
            wallet_address="WalletAddr12345678901234567890123456789012",
            token_address="TokenMint12345678901234567890123456789012",
            direction=SwapDirection.SELL,
            amount_token=1000.0,
            amount_sol=0.5,
            timestamp=datetime.now(timezone.utc),
            slot=123456789,
            fee_lamports=5000,
        )

        assert event.processing_started_at is not None
        assert isinstance(event.processing_started_at, datetime)


class TestSwapDirection:
    """Tests for SwapDirection enum."""

    def test_buy_value(self) -> None:
        """Test BUY direction value."""
        assert SwapDirection.BUY.value == "buy"

    def test_sell_value(self) -> None:
        """Test SELL direction value."""
        assert SwapDirection.SELL.value == "sell"


class TestWebhookValidationResult:
    """Tests for WebhookValidationResult model."""

    def test_valid_result(self) -> None:
        """Test creating a valid validation result."""
        result = WebhookValidationResult(
            is_valid=True,
            request_id="req-123",
        )

        assert result.is_valid is True
        assert result.error_message is None
        assert result.request_id == "req-123"
        assert result.timestamp is not None

    def test_invalid_result_with_error(self) -> None:
        """Test creating an invalid validation result with error."""
        result = WebhookValidationResult(
            is_valid=False,
            error_message="Signature mismatch",
        )

        assert result.is_valid is False
        assert result.error_message == "Signature mismatch"


class TestWebhookHealthStatus:
    """Tests for WebhookHealthStatus model."""

    def test_default_values(self) -> None:
        """Test default values for health status."""
        status = WebhookHealthStatus()

        assert status.status == "healthy"
        assert status.helius_connected is True
        assert status.last_webhook_received is None
        assert status.webhooks_processed_24h == 0
        assert status.average_processing_ms == 0.0

    def test_degraded_status(self) -> None:
        """Test creating a degraded status."""
        status = WebhookHealthStatus(
            status="degraded",
            helius_connected=False,
            webhooks_processed_24h=50,
            average_processing_ms=250.5,
        )

        assert status.status == "degraded"
        assert status.helius_connected is False
