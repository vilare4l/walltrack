"""Transaction parser for Helius API responses.

This module provides utilities to parse swap transactions from Helius API
transaction history responses.
"""

import structlog

from walltrack.data.models.transaction import SwapTransaction, TransactionType

log = structlog.get_logger(__name__)


def parse_swap_transaction(tx: dict, wallet_address: str) -> SwapTransaction | None:
    """Parse a swap transaction from Helius API response.

    Extracts transaction details from Helius enriched transaction data,
    including determining BUY vs SELL based on SOL flow direction.

    Args:
        tx: Transaction dictionary from Helius API response.
        wallet_address: Wallet address to analyze transaction for.

    Returns:
        SwapTransaction object if parsing succeeds, None if malformed.

    Transaction Type Determination:
        - BUY: nativeTransfers shows SOL leaving wallet (fromUserAccount == wallet_address)
        - SELL: nativeTransfers shows SOL entering wallet (toUserAccount == wallet_address)

    Example:
        tx_data = {
            "signature": "5j7s8k2d...",
            "timestamp": 1703001234,
            "type": "SWAP",
            "nativeTransfers": [{
                "fromUserAccount": "wallet1",
                "toUserAccount": "pool",
                "amount": 1000000000
            }],
            "tokenTransfers": [{
                "mint": "token1",
                "fromUserAccount": "pool",
                "toUserAccount": "wallet1",
                "tokenAmount": 1000000
            }]
        }
        result = parse_swap_transaction(tx_data, "wallet1")
        # Returns SwapTransaction with tx_type=BUY
    """
    try:
        # Extract signature
        signature = tx.get("signature")
        if not signature:
            log.warning("transaction_missing_signature", tx=tx)
            return None

        # Extract timestamp
        timestamp = tx.get("timestamp")
        if timestamp is None:
            log.warning("transaction_missing_timestamp", signature=signature[:8] + "...")
            return None

        # Extract native transfers (SOL movements)
        native_transfers = tx.get("nativeTransfers", [])
        if not native_transfers:
            log.debug(
                "transaction_missing_native_transfers",
                signature=signature[:8] + "...",
            )
            return None

        # Extract token transfers
        token_transfers = tx.get("tokenTransfers", [])
        if not token_transfers:
            log.debug(
                "transaction_missing_token_transfers",
                signature=signature[:8] + "...",
            )
            return None

        # Determine transaction type based on SOL flow direction
        # BUY: SOL leaves wallet (fromUserAccount == wallet_address)
        # SELL: SOL enters wallet (toUserAccount == wallet_address)
        tx_type: TransactionType | None = None
        sol_amount_lamports = 0

        for transfer in native_transfers:
            from_account = transfer.get("fromUserAccount")
            to_account = transfer.get("toUserAccount")
            amount = transfer.get("amount", 0)

            if from_account == wallet_address:
                # SOL leaving wallet = BUY
                tx_type = TransactionType.BUY
                sol_amount_lamports = amount
                break
            elif to_account == wallet_address:
                # SOL entering wallet = SELL
                tx_type = TransactionType.SELL
                sol_amount_lamports = amount
                break

        if tx_type is None:
            log.debug(
                "transaction_wallet_not_in_native_transfers",
                signature=signature[:8] + "...",
                wallet=wallet_address[:8] + "...",
            )
            return None

        # Convert lamports to SOL (1 SOL = 1e9 lamports)
        sol_amount = sol_amount_lamports / 1e9

        # Extract token details from first token transfer
        token_transfer = token_transfers[0]
        token_mint = token_transfer.get("mint")
        if not token_mint:
            log.warning(
                "transaction_missing_token_mint",
                signature=signature[:8] + "...",
            )
            return None

        # Extract token amount
        token_amount = token_transfer.get("tokenAmount", 0)

        # Create SwapTransaction object
        swap_tx = SwapTransaction(
            signature=signature,
            timestamp=timestamp,
            tx_type=tx_type,
            token_mint=token_mint,
            sol_amount=sol_amount,
            token_amount=float(token_amount),
            wallet_address=wallet_address,
        )

        log.debug(
            "transaction_parsed_successfully",
            signature=signature[:8] + "...",
            tx_type=tx_type.value,
            sol_amount=sol_amount,
        )

        return swap_tx

    except Exception as e:
        log.error(
            "transaction_parsing_error",
            signature=tx.get("signature", "unknown")[:8] + "...",
            error=str(e),
        )
        return None
