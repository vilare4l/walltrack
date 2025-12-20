"""Signal filter constants."""

from typing import Final

# Performance requirements
MAX_LOOKUP_TIME_MS: Final[int] = 50  # AC1: < 50ms lookup

# Cache settings
WALLET_CACHE_TTL_SECONDS: Final[int] = 300  # 5 minutes
WALLET_CACHE_MAX_SIZE: Final[int] = 10000  # Maximum cached wallets
CACHE_REFRESH_BATCH_SIZE: Final[int] = 100

# Logging
LOG_DISCARDED_SIGNALS: Final[bool] = True  # DEBUG level logging
LOG_BLACKLISTED_SIGNALS: Final[bool] = True  # INFO level logging
