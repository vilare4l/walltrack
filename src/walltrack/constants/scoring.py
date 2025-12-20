"""Scoring constants for multi-factor signal scoring."""

from typing import Final

# Default weights (configurable via DB)
DEFAULT_WALLET_WEIGHT: Final[float] = 0.30
DEFAULT_CLUSTER_WEIGHT: Final[float] = 0.25
DEFAULT_TOKEN_WEIGHT: Final[float] = 0.25
DEFAULT_CONTEXT_WEIGHT: Final[float] = 0.20

# Wallet score components
WIN_RATE_WEIGHT: Final[float] = 0.35
PNL_WEIGHT: Final[float] = 0.25
TIMING_WEIGHT: Final[float] = 0.25
CONSISTENCY_WEIGHT: Final[float] = 0.15
LEADER_BONUS: Final[float] = 0.15  # Added to wallet score if leader
MAX_DECAY_PENALTY: Final[float] = 0.30

# Token score components
LIQUIDITY_WEIGHT: Final[float] = 0.30
MARKET_CAP_WEIGHT: Final[float] = 0.25
HOLDER_DIST_WEIGHT: Final[float] = 0.20
VOLUME_WEIGHT: Final[float] = 0.25

# Token thresholds
MIN_LIQUIDITY_USD: Final[float] = 1000.0
OPTIMAL_LIQUIDITY_USD: Final[float] = 50000.0
MIN_MARKET_CAP_USD: Final[float] = 10000.0
OPTIMAL_MARKET_CAP_USD: Final[float] = 500000.0
NEW_TOKEN_PENALTY_MINUTES: Final[int] = 5
MAX_NEW_TOKEN_PENALTY: Final[float] = 0.30

# Cluster score components
SOLO_SIGNAL_BASE: Final[float] = 0.5
MIN_PARTICIPATION_RATE: Final[float] = 0.3

# Context score
PEAK_TRADING_HOURS_UTC: Final[list[int]] = [14, 15, 16, 17, 18]  # 2-6 PM UTC
HIGH_VOLATILITY_THRESHOLD: Final[float] = 0.10  # 10% price change
