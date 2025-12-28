"""Simplified scoring constants (~8 parameters).

Epic 14 Simplification: Reduced from 30+ parameters to 8.
All parameters are now in ScoringConfig model - these are just defaults.
"""

from typing import Final

# =============================================================================
# Simplified Scoring Parameters (~8 total)
# =============================================================================

# Single trade threshold (replaces dual HIGH/STANDARD thresholds)
DEFAULT_TRADE_THRESHOLD: Final[float] = 0.65

# Wallet score weights (must sum to 1.0)
DEFAULT_WALLET_WIN_RATE_WEIGHT: Final[float] = 0.60
DEFAULT_WALLET_PNL_WEIGHT: Final[float] = 0.40

# Leader bonus (multiplier for cluster leaders)
DEFAULT_LEADER_BONUS: Final[float] = 1.15

# PnL normalization range
DEFAULT_PNL_NORMALIZE_MIN: Final[float] = -100.0
DEFAULT_PNL_NORMALIZE_MAX: Final[float] = 500.0

# Cluster boost range
DEFAULT_MIN_CLUSTER_BOOST: Final[float] = 1.0
DEFAULT_MAX_CLUSTER_BOOST: Final[float] = 1.8


# =============================================================================
# Legacy Constants (DEPRECATED - kept for backward compatibility)
# =============================================================================
# These will be removed in a future version.

# Old 4-factor weights (no longer used)
DEFAULT_WALLET_WEIGHT: Final[float] = 1.0  # Now the only factor
DEFAULT_CLUSTER_WEIGHT: Final[float] = 0.0  # Now a multiplier, not factor
DEFAULT_TOKEN_WEIGHT: Final[float] = 0.0  # Now binary gate
DEFAULT_CONTEXT_WEIGHT: Final[float] = 0.0  # Removed

# Old wallet sub-weights (simplified)
WIN_RATE_WEIGHT: Final[float] = DEFAULT_WALLET_WIN_RATE_WEIGHT
PNL_WEIGHT: Final[float] = DEFAULT_WALLET_PNL_WEIGHT
TIMING_WEIGHT: Final[float] = 0.0  # Removed
CONSISTENCY_WEIGHT: Final[float] = 0.0  # Removed
LEADER_BONUS: Final[float] = DEFAULT_LEADER_BONUS
MAX_DECAY_PENALTY: Final[float] = 0.0  # Removed

# Old token weights (now binary gate)
LIQUIDITY_WEIGHT: Final[float] = 0.0
MARKET_CAP_WEIGHT: Final[float] = 0.0
HOLDER_DIST_WEIGHT: Final[float] = 0.0
VOLUME_WEIGHT: Final[float] = 0.0

# Old token thresholds (no longer used - binary safety check)
MIN_LIQUIDITY_USD: Final[float] = 0.0
OPTIMAL_LIQUIDITY_USD: Final[float] = 0.0
MIN_MARKET_CAP_USD: Final[float] = 0.0
OPTIMAL_MARKET_CAP_USD: Final[float] = 0.0
NEW_TOKEN_PENALTY_MINUTES: Final[int] = 0
MAX_NEW_TOKEN_PENALTY: Final[float] = 0.0

# Old cluster constants (now just a multiplier range)
SOLO_SIGNAL_BASE: Final[float] = 1.0  # No penalty for solo signals
MIN_PARTICIPATION_RATE: Final[float] = 0.0

# Old context constants (removed)
PEAK_TRADING_HOURS_UTC: Final[list[int]] = []
HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.0
