"""Webhook-related constants for Helius integration."""

from typing import Final

# HMAC validation
HELIUS_SIGNATURE_HEADER: Final[str] = "X-Helius-Signature"
HMAC_ALGORITHM: Final[str] = "sha256"

# Processing limits
MAX_PROCESSING_TIME_MS: Final[int] = 500  # NFR2
WEBHOOK_TIMEOUT_SECONDS: Final[int] = 30

# Known DEX program IDs for swap detection
KNOWN_DEX_PROGRAMS: Final[frozenset[str]] = frozenset({
    "JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4",   # Jupiter v6
    "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",   # Jupiter v4
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8",  # Raydium AMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Orca Whirlpool
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP",  # Orca v1
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P",   # Pump.fun
})

# Token programs
SPL_TOKEN_PROGRAM: Final[str] = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
SPL_TOKEN_2022_PROGRAM: Final[str] = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# SOL mint address (wrapped SOL)
WRAPPED_SOL_MINT: Final[str] = "So11111111111111111111111111111111111111112"

# Solana address validation
MIN_SOLANA_ADDRESS_LENGTH: Final[int] = 32
MAX_SOLANA_ADDRESS_LENGTH: Final[int] = 44
