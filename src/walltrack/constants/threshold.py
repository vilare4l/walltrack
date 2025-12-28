"""Simplified threshold constants for trade eligibility.

Epic 14 Simplification:
- Single threshold (0.65) replaces dual HIGH/STANDARD thresholds
- Position multiplier equals cluster_boost (not conviction tier)
- Token safety is binary gate in SignalScorer
"""

from typing import Final

# =============================================================================
# Simplified Threshold (Single threshold)
# =============================================================================

# Single trade threshold - signals must score >= this to trade
DEFAULT_TRADE_THRESHOLD: Final[float] = 0.65


# =============================================================================
# Legacy Constants (DEPRECATED - kept for backward compatibility)
# =============================================================================
# These will be removed in a future version.

# Old dual threshold (replaced by single threshold)
DEFAULT_HIGH_CONVICTION_THRESHOLD: Final[float] = 0.65  # Same as trade threshold now

# Old position sizing multipliers (now uses cluster_boost directly)
HIGH_CONVICTION_MULTIPLIER: Final[float] = 1.0  # No longer used
STANDARD_MULTIPLIER: Final[float] = 1.0  # No longer used
NO_TRADE_MULTIPLIER: Final[float] = 0.0  # Still used for no-trade signals

# Old safety filters (now binary gate in SignalScorer)
MIN_LIQUIDITY_FOR_TRADE_USD: Final[float] = 0.0  # No longer used
BLOCK_HONEYPOTS: Final[bool] = True  # Still valid but enforced in scorer
