"""Solana RPC transaction parser.

Parses raw Solana RPC transaction data into structured SwapTransaction models.
Detects BUY/SELL swap events from raw instructions and balance changes.

This is a shared component reusable across Stories 3.1, 3.2, 3.3.
"""

from typing import Any

import structlog

from walltrack.data.models.transaction import SwapTransaction, TransactionType

log = structlog.get_logger(__name__)

# Solana constant: 1 SOL = 1,000,000,000 lamports
LAMPORTS_PER_SOL = 1_000_000_000


class TransactionParser:
    """Parser for Solana RPC transaction data.

    Converts raw getTransaction() RPC responses into SwapTransaction models.
    Detects BUY/SELL direction from SOL and token balance changes.

    Detection Logic:
        BUY:  SOL decreased + Token increased → Bought tokens with SOL
        SELL: SOL increased + Token decreased → Sold tokens for SOL

    Attributes:
        None - stateless parser, safe for concurrent use.

    Example:
        parser = TransactionParser()
        raw_tx = await rpc_client.getTransaction(signature)
        swap = parser.parse(raw_tx)
        if swap:
            print(f"{swap.tx_type}: {swap.token_amount} tokens for {swap.sol_amount} SOL")
    """

    def parse(self, raw_transaction: dict[str, Any]) -> SwapTransaction | None:
        """Parse raw RPC transaction into SwapTransaction.

        Args:
            raw_transaction: Raw transaction dict from getTransaction() RPC call.
                Expected structure:
                {
                    "transaction": {"message": {...}, "signatures": [...]},
                    "meta": {"err": ..., "preBalances": [...], "postBalances": [...],
                             "preTokenBalances": [...], "postTokenBalances": [...]},
                    "blockTime": <unix_timestamp>
                }

        Returns:
            SwapTransaction if valid swap detected, None otherwise.

        Rejects:
            - Failed transactions (meta.err not None)
            - Non-swap transactions (no token balance change)
            - Invalid/incomplete transaction data
        """
        try:
            # Validate transaction structure
            if not self._is_valid_transaction(raw_transaction):
                return None

            meta = raw_transaction["meta"]
            transaction = raw_transaction["transaction"]
            signature = transaction["signatures"][0]
            timestamp = raw_transaction.get("blockTime", 0)

            # Extract balance changes
            sol_change = self._calculate_sol_change(meta)
            token_change = self._calculate_token_change(meta)

            if token_change is None:
                log.debug(
                    "transaction_no_token_change",
                    signature=signature[:8] + "...",
                )
                return None

            # Determine transaction type (BUY or SELL)
            tx_type = self._determine_transaction_type(sol_change, token_change)
            if tx_type is None:
                return None

            # Extract wallet address (first account key is typically the signer)
            # Handle both RPC format (dict with 'pubkey') and legacy format (string)
            first_account = transaction["message"]["accountKeys"][0]
            if isinstance(first_account, dict):
                # RPC format: {"pubkey": "...", "signer": True, "writable": True}
                wallet_address = first_account["pubkey"]
            else:
                # Legacy format: direct string
                wallet_address = first_account

            # Build SwapTransaction
            swap = SwapTransaction(
                signature=signature,
                timestamp=timestamp,
                tx_type=tx_type,
                token_mint=token_change["mint"],
                sol_amount=abs(sol_change),
                token_amount=abs(token_change["amount"]),
                wallet_address=wallet_address,
            )

            log.debug(
                "transaction_parsed",
                signature=signature[:8] + "...",
                tx_type=tx_type.value,
                token_mint=token_change["mint"][:8] + "...",
                sol_amount=abs(sol_change),
                token_amount=abs(token_change["amount"]),
            )

            return swap

        except (KeyError, IndexError, ValueError, TypeError) as e:
            log.warning(
                "transaction_parse_error",
                error=str(e),
                error_type=type(e).__name__,
            )
            return None

    def _is_valid_transaction(self, raw_transaction: dict[str, Any]) -> bool:
        """Check if transaction has required fields and succeeded.

        Args:
            raw_transaction: Raw transaction dict.

        Returns:
            True if transaction is valid and succeeded, False otherwise.
        """
        # Check required top-level fields
        if "transaction" not in raw_transaction:
            return False
        if "meta" not in raw_transaction:
            return False

        meta = raw_transaction["meta"]

        # Reject failed transactions
        if meta.get("err") is not None:
            return False

        # Check for required meta fields
        if "preBalances" not in meta or "postBalances" not in meta:
            return False

        # Check for signatures
        transaction = raw_transaction["transaction"]
        if "signatures" not in transaction or not transaction["signatures"]:
            return False

        # Check for message with account keys
        if "message" not in transaction:
            return False
        if "accountKeys" not in transaction["message"]:
            return False
        if not transaction["message"]["accountKeys"]:
            return False

        return True

    def _calculate_sol_change(self, meta: dict[str, Any]) -> float:
        """Calculate SOL balance change in SOL (not lamports).

        Args:
            meta: Transaction metadata with preBalances and postBalances.

        Returns:
            SOL change (positive = gained, negative = lost).
            First account (index 0) is the wallet executing the transaction.
        """
        pre_balance = meta["preBalances"][0]  # lamports before
        post_balance = meta["postBalances"][0]  # lamports after
        lamports_change = post_balance - pre_balance

        # Convert lamports to SOL
        return lamports_change / LAMPORTS_PER_SOL

    def _calculate_token_change(
        self, meta: dict[str, Any]
    ) -> dict[str, Any] | None:
        """Calculate token balance change.

        Args:
            meta: Transaction metadata with preTokenBalances and postTokenBalances.

        Returns:
            Dict with "mint" and "amount" (float) if token change detected.
            Returns None if no token balance change.

        Logic:
            - Compares preTokenBalances vs postTokenBalances
            - Detects new token accounts (appeared in post)
            - Detects closed token accounts (disappeared in post)
            - Detects balance changes in existing accounts
        """
        pre_token_balances = meta.get("preTokenBalances", [])
        post_token_balances = meta.get("postTokenBalances", [])

        # Case 1: New token account appeared (BUY)
        if not pre_token_balances and post_token_balances:
            token_balance = post_token_balances[0]
            return {
                "mint": token_balance["mint"],
                "amount": token_balance["uiTokenAmount"]["uiAmount"],
            }

        # Case 2: Token account closed (SELL - all tokens sold)
        if pre_token_balances and not post_token_balances:
            token_balance = pre_token_balances[0]
            return {
                "mint": token_balance["mint"],
                "amount": -token_balance["uiTokenAmount"]["uiAmount"],  # Negative = sold
            }

        # Case 3: Token balance changed (partial BUY/SELL)
        if pre_token_balances and post_token_balances:
            # Match token accounts by mint address
            pre_by_mint = {tb["mint"]: tb for tb in pre_token_balances}
            post_by_mint = {tb["mint"]: tb for tb in post_token_balances}

            # Find first mint with balance change
            for mint, post_balance in post_by_mint.items():
                post_amount = post_balance["uiTokenAmount"]["uiAmount"]

                if mint in pre_by_mint:
                    pre_amount = pre_by_mint[mint]["uiTokenAmount"]["uiAmount"]
                    amount_change = post_amount - pre_amount

                    if abs(amount_change) > 0.0001:  # Ignore dust
                        return {"mint": mint, "amount": amount_change}
                else:
                    # New token appeared (not in pre)
                    return {"mint": mint, "amount": post_amount}

            # Check for tokens that disappeared
            for mint, pre_balance in pre_by_mint.items():
                if mint not in post_by_mint:
                    pre_amount = pre_balance["uiTokenAmount"]["uiAmount"]
                    return {"mint": mint, "amount": -pre_amount}

        # No token balance change detected
        return None

    def _determine_transaction_type(
        self, sol_change: float, token_change: dict[str, Any]
    ) -> TransactionType | None:
        """Determine transaction type from balance changes.

        Args:
            sol_change: SOL balance change (positive = gained, negative = lost).
            token_change: Dict with "mint" and "amount" (positive = gained, negative = lost).

        Returns:
            TransactionType.BUY if bought tokens with SOL.
            TransactionType.SELL if sold tokens for SOL.
            None if transaction pattern doesn't match BUY or SELL.

        Logic:
            BUY:  Lost SOL (negative) + Gained tokens (positive)
            SELL: Gained SOL (positive) + Lost tokens (negative)
        """
        token_amount = token_change["amount"]

        # BUY: Lost SOL + Gained tokens
        if sol_change < 0 and token_amount > 0:
            return TransactionType.BUY

        # SELL: Gained SOL + Lost tokens
        if sol_change > 0 and token_amount < 0:
            return TransactionType.SELL

        # Ambiguous pattern (e.g., gained both SOL and tokens, or lost both)
        log.debug(
            "transaction_ambiguous_pattern",
            sol_change=sol_change,
            token_change=token_amount,
        )
        return None
