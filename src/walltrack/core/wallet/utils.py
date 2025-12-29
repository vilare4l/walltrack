"""Wallet utility functions.

Shared utilities for wallet operations used across UI and core modules.
"""


def truncate_address(address: str) -> str:
    """Truncate wallet address for display: AbCd...xYz1.

    Args:
        address: Full wallet address.

    Returns:
        Truncated address for UI display (first 4 + last 4 chars).

    Example:
        >>> truncate_address("9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM")
        '9WzD...AWWM'
    """
    if len(address) > 12:
        return f"{address[:4]}...{address[-4:]}"
    return address
