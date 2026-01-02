"""Background workers for autonomous task processing.

This package contains background workers that run continuously
to process tasks without manual intervention.

Workers:
    - WalletDiscoveryWorker: Discovers wallets from tokens (Story 3.5.5)
    - WalletProfilingWorker: Processes wallets from discovered → profiled → watchlisted
"""

from walltrack.workers.wallet_discovery_worker import WalletDiscoveryWorker
from walltrack.workers.wallet_profiling_worker import (
    WalletProfilingWorker,
    wallet_profiling_lifespan,
)

__all__ = [
    "WalletDiscoveryWorker",
    "WalletProfilingWorker",
    "wallet_profiling_lifespan",
]
