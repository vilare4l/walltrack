"""
Format Helpers

Formatting utilities for test assertions and data display.
"""

from __future__ import annotations


def format_sol_amount(amount: float, decimals: int = 4) -> str:
    """
    Format SOL amount for display.

    Args:
        amount: Amount in SOL
        decimals: Number of decimal places

    Returns:
        Formatted string like "1.2345 SOL"

    Example:
        format_sol_amount(1.23456789)  # "1.2346 SOL"
    """
    return f"{amount:.{decimals}f} SOL"


def truncate_address(address: str, chars: int = 4) -> str:
    """
    Truncate wallet/token address for display.

    Args:
        address: Full Solana address (44 chars)
        chars: Number of chars to show on each side

    Returns:
        Truncated address like "AbCd...WxYz"

    Example:
        truncate_address("AbCdEfGhIjKlMnOpQrStUvWxYz1234567890ABCD")
        # "AbCd...ABCD"
    """
    if len(address) <= chars * 2 + 3:
        return address
    return f"{address[:chars]}...{address[-chars:]}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format decimal as percentage.

    Args:
        value: Decimal value (0.0 to 1.0)
        decimals: Number of decimal places

    Returns:
        Formatted string like "78.5%"

    Example:
        format_percentage(0.785)  # "78.5%"
    """
    return f"{value * 100:.{decimals}f}%"


def format_decay_badge(status: str) -> str:
    """
    Get emoji badge for decay status.

    Args:
        status: One of "ok", "flagged", "downgraded", "dormant"

    Returns:
        Emoji badge string

    Example:
        format_decay_badge("ok")  # "🟢"
    """
    badges = {
        "ok": "🟢",
        "flagged": "🟡",
        "downgraded": "🔴",
        "dormant": "⚪",
    }
    return badges.get(status, "❓")
