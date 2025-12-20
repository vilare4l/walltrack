"""Helius webhook management and parsing."""

from datetime import UTC, datetime

import structlog

from walltrack.constants.webhook import KNOWN_DEX_PROGRAMS, WRAPPED_SOL_MINT
from walltrack.services.helius.models import (
    HeliusWebhookPayload,
    ParsedSwapEvent,
    SwapDirection,
    TokenTransfer,
)

logger = structlog.get_logger(__name__)


class WebhookParser:
    """Parses Helius webhook payloads into structured swap events."""

    def parse_payload(self, raw_payload: dict) -> ParsedSwapEvent | None:
        """
        Parse raw Helius webhook payload into ParsedSwapEvent.

        Args:
            raw_payload: Raw dictionary from Helius webhook

        Returns:
            ParsedSwapEvent if valid swap, None otherwise
        """
        try:
            payload = HeliusWebhookPayload.model_validate(raw_payload)

            # Check if this is a swap transaction
            if not self._is_swap_transaction(payload):
                logger.debug(
                    "webhook_not_swap",
                    signature=payload.signature,
                    type=payload.transaction_type,
                )
                return None

            # Extract swap details
            return self._extract_swap_event(payload, raw_payload)

        except Exception as e:
            logger.error(
                "webhook_parse_error",
                error=str(e),
                payload_keys=list(raw_payload.keys()) if raw_payload else [],
            )
            return None

    def _is_swap_transaction(self, payload: HeliusWebhookPayload) -> bool:
        """
        Check if transaction involves a known DEX.

        Args:
            payload: Validated Helius payload

        Returns:
            True if this is a swap transaction
        """
        # Check if fee payer interacted with DEX programs
        for account in payload.account_data:
            if account.get("account") in KNOWN_DEX_PROGRAMS:
                return True

        # Check transaction type from Helius
        if payload.transaction_type.upper() == "SWAP":
            return True

        # Check source field (Helius enhanced parsing)
        return payload.source.upper() in ("JUPITER", "RAYDIUM", "ORCA", "PUMP_FUN")

    def _extract_swap_event(
        self,
        payload: HeliusWebhookPayload,
        raw_payload: dict,
    ) -> ParsedSwapEvent | None:
        """
        Extract swap details from payload.

        Args:
            payload: Validated Helius payload
            raw_payload: Original raw dictionary

        Returns:
            ParsedSwapEvent if extraction successful, None otherwise
        """
        if not payload.token_transfers:
            logger.debug(
                "no_token_transfers",
                signature=payload.signature,
            )
            return None

        token_transfers = []
        for t in payload.token_transfers:
            try:
                token_transfers.append(TokenTransfer.model_validate(t))
            except Exception as e:
                logger.debug("invalid_token_transfer", error=str(e), transfer=t)
                continue

        if not token_transfers:
            return None

        # Identify wallet (fee payer is typically the swapper)
        wallet_address = payload.fee_payer

        # Find the non-SOL token in the swap
        token_address = None
        direction = SwapDirection.BUY
        amount_token = 0.0
        amount_sol = 0.0

        for transfer in token_transfers:
            if transfer.mint == WRAPPED_SOL_MINT:
                # Convert lamports to SOL (amount comes as raw value)
                amount_sol = transfer.amount / 1e9 if transfer.amount > 1e6 else transfer.amount
                # If wallet sent SOL, it's a buy; if received SOL, it's a sell
                if transfer.from_account == wallet_address:
                    direction = SwapDirection.BUY
                else:
                    direction = SwapDirection.SELL
            else:
                token_address = transfer.mint
                amount_token = transfer.amount

        if not token_address:
            logger.debug(
                "no_token_address_found",
                signature=payload.signature,
                transfers_count=len(token_transfers),
            )
            return None

        try:
            return ParsedSwapEvent(
                tx_signature=payload.signature,
                wallet_address=wallet_address,
                token_address=token_address,
                direction=direction,
                amount_token=amount_token,
                amount_sol=amount_sol,
                timestamp=datetime.fromtimestamp(payload.timestamp, tz=UTC),
                slot=payload.slot,
                fee_lamports=payload.fee,
                raw_payload=raw_payload,
            )
        except Exception as e:
            logger.error(
                "swap_event_creation_failed",
                error=str(e),
                signature=payload.signature,
            )
            return None

    def parse_batch(self, payloads: list[dict]) -> list[ParsedSwapEvent]:
        """
        Parse a batch of webhook payloads.

        Args:
            payloads: List of raw webhook payloads

        Returns:
            List of successfully parsed swap events
        """
        events = []
        for payload in payloads:
            event = self.parse_payload(payload)
            if event:
                events.append(event)
        return events


# Singleton instance
_parser_instance: WebhookParser | None = None


def get_webhook_parser() -> WebhookParser:
    """Get or create webhook parser singleton."""
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = WebhookParser()
    return _parser_instance
