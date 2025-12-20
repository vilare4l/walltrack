"""Threshold constants for trade eligibility."""

from typing import Final

# Default thresholds
DEFAULT_TRADE_THRESHOLD: Final[float] = 0.70
DEFAULT_HIGH_CONVICTION_THRESHOLD: Final[float] = 0.85

# Position sizing multipliers (AC4)
HIGH_CONVICTION_MULTIPLIER: Final[float] = 1.5  # 1.5x position
STANDARD_MULTIPLIER: Final[float] = 1.0  # 1.0x position
NO_TRADE_MULTIPLIER: Final[float] = 0.0  # No position

# Safety filters
MIN_LIQUIDITY_FOR_TRADE_USD: Final[float] = 1000.0
BLOCK_HONEYPOTS: Final[bool] = True
