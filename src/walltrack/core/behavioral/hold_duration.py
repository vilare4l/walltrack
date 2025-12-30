"""Hold duration analysis functions.

This module provides functions to calculate and classify wallet hold duration
patterns based on transaction history.
"""

from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository


def calculate_hold_duration_avg(transactions: list[SwapTransaction]) -> int:
    """Calculate average hold duration from matched BUY/SELL pairs.

    Matches each BUY transaction with its corresponding SELL transaction
    for the same token, calculates hold duration in seconds, and returns average.

    Args:
        transactions: List of swap transactions to analyze (must be sorted by timestamp).

    Returns:
        Average hold duration in seconds.
        Returns 0 if no valid BUY/SELL pairs found.

    Algorithm:
        1. Group transactions by token_mint
        2. For each token, match BUY with subsequent SELL (FIFO)
        3. Calculate duration: sell_timestamp - buy_timestamp
        4. Return average of all durations

    Example:
        >>> txs = [
        ...     SwapTransaction(tx_type=TransactionType.BUY, timestamp=1000, token_mint="ABC", ...),
        ...     SwapTransaction(tx_type=TransactionType.SELL, timestamp=5000, token_mint="ABC", ...),
        ... ]
        >>> calculate_hold_duration_avg(txs)
        4000
    """
    # Group transactions by token
    token_groups: dict[str, list[SwapTransaction]] = {}
    for tx in transactions:
        if tx.token_mint not in token_groups:
            token_groups[tx.token_mint] = []
        token_groups[tx.token_mint].append(tx)

    # Match BUY/SELL pairs and calculate durations
    durations: list[int] = []

    for token_mint, token_txs in token_groups.items():
        # Sort by timestamp
        sorted_txs = sorted(token_txs, key=lambda t: t.timestamp)

        # FIFO matching: track open BUY positions
        buy_queue: list[SwapTransaction] = []

        for tx in sorted_txs:
            if tx.tx_type == TransactionType.BUY:
                buy_queue.append(tx)
            elif tx.tx_type == TransactionType.SELL and buy_queue:
                # Match with oldest BUY (FIFO)
                buy_tx = buy_queue.pop(0)
                duration = tx.timestamp - buy_tx.timestamp
                durations.append(duration)

    # Return average duration
    if not durations:
        return 0

    return sum(durations) // len(durations)


async def classify_hold_duration(
    avg_hold_duration: int,
    config: ConfigRepository,
) -> str:
    """Classify hold duration style based on average seconds held.

    Uses configurable thresholds from config repository:
    - scalper: <= hold_duration_scalper_max (default: 3600s = 1 hour)
    - day_trader: <= hold_duration_day_trader_max (default: 86400s = 24 hours)
    - swing_trader: <= hold_duration_swing_trader_max (default: 604800s = 7 days)
    - position_trader: > swing_trader_max

    Args:
        avg_hold_duration: Average hold duration in seconds.
        config: ConfigRepository instance for threshold values.

    Returns:
        Hold duration classification: "scalper", "day_trader", "swing_trader", or "position_trader".

    Example:
        >>> config = ConfigRepository(client)
        >>> await classify_hold_duration(1800, config)  # 30 minutes
        'scalper'
        >>> await classify_hold_duration(7200, config)  # 2 hours
        'day_trader'
    """
    # Get thresholds from config with error handling
    try:
        scalper_max = await config.get_hold_duration_scalper_max()
        day_trader_max = await config.get_hold_duration_day_trader_max()
        swing_trader_max = await config.get_hold_duration_swing_trader_max()
    except Exception:
        # Fallback to hardcoded defaults if config fails
        scalper_max = 3600  # 1 hour
        day_trader_max = 86400  # 24 hours
        swing_trader_max = 604800  # 7 days

    # Classify based on thresholds
    if avg_hold_duration <= scalper_max:
        return "scalper"
    elif avg_hold_duration <= day_trader_max:
        return "day_trader"
    elif avg_hold_duration <= swing_trader_max:
        return "swing_trader"
    else:
        return "position_trader"


def format_duration_human(seconds: int) -> str:
    """Format duration in seconds to human-readable string.

    Converts seconds to a readable format like "2h 30m" or "3d 5h 20m".
    Shows only significant units (non-zero values).

    Args:
        seconds: Duration in seconds.

    Returns:
        Human-readable duration string.

    Example:
        >>> format_duration_human(3600)
        '1h'
        >>> format_duration_human(7320)
        '2h 2m'
        >>> format_duration_human(90061)
        '1d 1h 1m'
        >>> format_duration_human(45)
        '45s'
    """
    if seconds == 0:
        return "0s"

    # Calculate time units
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    # Build string with non-zero units
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 and not parts:  # Only show seconds if no larger units
        parts.append(f"{secs}s")

    return " ".join(parts)
