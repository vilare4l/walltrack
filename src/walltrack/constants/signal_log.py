"""Signal logging constants."""

from typing import Final

# Query performance
MAX_QUERY_RESULTS: Final[int] = 1000
DEFAULT_QUERY_LIMIT: Final[int] = 100

# Data retention (NFR23: 6 months)
DATA_RETENTION_DAYS: Final[int] = 180

# Async logging
LOG_BATCH_SIZE: Final[int] = 50
LOG_FLUSH_INTERVAL_SECONDS: Final[int] = 5
MAX_LOG_QUEUE_SIZE: Final[int] = 1000
