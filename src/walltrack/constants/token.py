"""Token data fetching constants."""

from typing import Final

# Cache settings
TOKEN_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes (AC2)
TOKEN_CACHE_MAX_SIZE: Final[int] = 5000

# API timeouts
DEXSCREENER_TIMEOUT_SECONDS: Final[int] = 5
BIRDEYE_TIMEOUT_SECONDS: Final[int] = 5
MAX_RETRIES: Final[int] = 3
RETRY_DELAY_SECONDS: Final[float] = 0.5

# New token threshold
NEW_TOKEN_AGE_MINUTES: Final[int] = 10  # AC4

# API endpoints
DEXSCREENER_BASE_URL: Final[str] = "https://api.dexscreener.com/latest"
BIRDEYE_BASE_URL: Final[str] = "https://public-api.birdeye.so"

# Rate limiting
DEXSCREENER_RATE_LIMIT_PER_MINUTE: Final[int] = 300
BIRDEYE_RATE_LIMIT_PER_MINUTE: Final[int] = 100

# Scoring thresholds
MIN_LIQUIDITY_USD: Final[float] = 1000.0  # Minimum for trading
SUSPICIOUS_TOP_HOLDER_PCT: Final[float] = 50.0  # Red flag if top 10 hold > 50%
