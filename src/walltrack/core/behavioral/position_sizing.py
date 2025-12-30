"""Position sizing analysis functions.

This module provides functions to calculate and classify wallet position sizes
based on transaction history.
"""

from decimal import Decimal

from walltrack.data.models.transaction import SwapTransaction, TransactionType
from walltrack.data.supabase.repositories.config_repo import ConfigRepository


def calculate_position_size_avg(transactions: list[SwapTransaction]) -> Decimal:
    """Calculate average position size from BUY transactions.

    Extracts SOL amounts from all BUY transactions and calculates the average.
    Returns Decimal with 8 decimal precision for consistency with blockchain values.

    Args:
        transactions: List of swap transactions to analyze.

    Returns:
        Average position size in SOL with 8 decimal precision.
        Returns Decimal('0') if no BUY transactions found.

    Example:
        >>> txs = [
        ...     SwapTransaction(tx_type=TransactionType.BUY, sol_amount=1.5, ...),
        ...     SwapTransaction(tx_type=TransactionType.BUY, sol_amount=2.5, ...),
        ...     SwapTransaction(tx_type=TransactionType.SELL, sol_amount=3.0, ...),
        ... ]
        >>> calculate_position_size_avg(txs)
        Decimal('2.00000000')
    """
    # Filter BUY transactions only
    buy_transactions = [tx for tx in transactions if tx.tx_type == TransactionType.BUY]

    # Return 0 if no BUY transactions
    if not buy_transactions:
        return Decimal("0")

    # Calculate average SOL amount
    total_sol = sum(tx.sol_amount for tx in buy_transactions)
    avg_sol = total_sol / len(buy_transactions)

    # Return as Decimal with 8 decimal precision
    return Decimal(str(avg_sol)).quantize(Decimal("0.00000001"))


async def classify_position_size(
    avg_position_size: Decimal,
    config: ConfigRepository,
) -> str:
    """Classify position size style based on average SOL amount.

    Uses configurable thresholds from config repository:
    - small: <= position_size_small_max (default: 1.0 SOL)
    - medium: <= position_size_medium_max (default: 5.0 SOL)
    - large: > position_size_medium_max

    Args:
        avg_position_size: Average position size in SOL.
        config: ConfigRepository instance for threshold values.

    Returns:
        Position size classification: "small", "medium", or "large".

    Example:
        >>> config = ConfigRepository(client)
        >>> await classify_position_size(Decimal('0.5'), config)
        'small'
        >>> await classify_position_size(Decimal('3.0'), config)
        'medium'
        >>> await classify_position_size(Decimal('10.0'), config)
        'large'
    """
    # Get thresholds from config with error handling
    try:
        small_max = await config.get_position_size_small_max()
        medium_max = await config.get_position_size_medium_max()
    except Exception:
        # Fallback to hardcoded defaults if config fails
        small_max = 1.0
        medium_max = 5.0

    # Classify based on thresholds
    if avg_position_size <= Decimal(str(small_max)):
        return "small"
    elif avg_position_size <= Decimal(str(medium_max)):
        return "medium"
    else:
        return "large"
