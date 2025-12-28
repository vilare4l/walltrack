# Story 11.3: Component Migration to ConfigService

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 8
- **Depends on**: Story 11-2 (ConfigService)

## User Story

**As a** system architect,
**I want** tous les composants existants migrés vers ConfigService,
**So that** plus aucun paramètre n'est hardcodé.

## Acceptance Criteria

### AC 1: Constants Files Removed
**Given** les fichiers `constants/scoring.py`, `constants/threshold.py` existent
**When** la migration est terminée
**Then** ces fichiers sont supprimés ou réduits aux fallback defaults
**And** plus aucun composant ne les importe

### AC 2: Signal Components Migrated
**Given** `SignalScorer`, `ThresholdChecker`, `SignalFilter`
**When** ils sont instanciés
**Then** ils reçoivent `ConfigService` en injection
**And** ils utilisent `await config.get()` pour chaque paramètre

### AC 3: Cluster Components Migrated
**Given** `SignalAmplifier`, `SyncDetector`, `LeaderDetection`
**When** ils sont instanciés
**Then** ils utilisent `ConfigService` pour leurs seuils

### AC 4: Discovery Components Migrated
**Given** `DecayDetector`, `PumpFinder`, `Profiler`
**When** ils sont instanciés
**Then** ils utilisent `ConfigService` pour leurs seuils

### AC 5: No Hardcoded Values
**Given** tous les composants migrés
**When** je grep pour des valeurs numériques hardcodées
**Then** seuls les fallback defaults restent
**And** ils sont documentés comme fallbacks

## Technical Specifications

### Migration Pattern

Chaque composant suit le même pattern de migration:

**Before (hardcoded):**
```python
class SignalScorer:
    SCORE_THRESHOLD = 0.70
    HIGH_CONVICTION = 0.85

    def score(self, signal):
        if signal.score >= self.SCORE_THRESHOLD:
            return True
```

**After (ConfigService):**
```python
class SignalScorer:
    def __init__(self, config_service: ConfigService):
        self.config = config_service

    async def score(self, signal):
        threshold = await self.config.get("trading.score_threshold", Decimal("0.70"))
        if signal.score >= threshold:
            return True
```

### Components to Migrate

#### Signal Pipeline

**src/walltrack/services/scoring/signal_scorer.py:**
```python
"""Signal scorer with dynamic configuration."""

from decimal import Decimal
from typing import Optional

import structlog

from walltrack.services.config.config_service import ConfigService, get_config_service
from walltrack.models.signal import Signal

logger = structlog.get_logger(__name__)


class SignalScorer:
    """
    Scores signals using configurable weights.

    All thresholds and weights come from ConfigService.
    """

    def __init__(self, config_service: Optional[ConfigService] = None):
        self._config = config_service
        self._config_initialized = False

    async def _get_config(self) -> ConfigService:
        """Get or initialize config service."""
        if self._config is None:
            self._config = await get_config_service()
        return self._config

    async def calculate_score(self, signal: Signal) -> Decimal:
        """Calculate composite signal score."""
        config = await self._get_config()

        # Get weights from config
        wallet_weight = await config.get("scoring.wallet_score_weight", Decimal("0.30"))
        timing_weight = await config.get("scoring.timing_score_weight", Decimal("0.25"))
        market_weight = await config.get("scoring.market_score_weight", Decimal("0.20"))
        cluster_weight = await config.get("scoring.cluster_score_weight", Decimal("0.25"))

        # Calculate weighted score
        score = (
            signal.wallet_score * wallet_weight +
            signal.timing_score * timing_weight +
            signal.market_score * market_weight +
            signal.cluster_score * cluster_weight
        )

        return score

    async def is_tradeable(self, signal: Signal) -> bool:
        """Check if signal meets minimum threshold."""
        config = await self._get_config()

        threshold = await config.get("trading.score_threshold", Decimal("0.70"))
        return signal.score >= threshold

    async def is_high_conviction(self, signal: Signal) -> bool:
        """Check if signal is high conviction."""
        config = await self._get_config()

        high_threshold = await config.get("trading.high_conviction_threshold", Decimal("0.85"))
        return signal.score >= high_threshold


async def get_signal_scorer() -> SignalScorer:
    """Get signal scorer with config service."""
    config = await get_config_service()
    return SignalScorer(config_service=config)
```

**src/walltrack/services/signal/threshold_checker.py:**
```python
"""Threshold checker with dynamic configuration."""

from decimal import Decimal

from walltrack.services.config.config_service import ConfigService, get_config_service
from walltrack.models.signal import Signal


class ThresholdChecker:
    """
    Checks various thresholds for signal validation.

    All thresholds are loaded from ConfigService.
    """

    def __init__(self, config_service: ConfigService):
        self.config = config_service

    async def check_market_quality(self, signal: Signal) -> tuple[bool, str]:
        """Check market quality thresholds."""
        min_liquidity = await self.config.get(
            "scoring.market_liquidity_threshold",
            Decimal("10000")
        )
        min_volume = await self.config.get(
            "scoring.market_volume_threshold",
            Decimal("5000")
        )

        if signal.market_data.liquidity < min_liquidity:
            return False, f"Liquidity too low: {signal.market_data.liquidity} < {min_liquidity}"

        if signal.market_data.volume_24h < min_volume:
            return False, f"Volume too low: {signal.market_data.volume_24h} < {min_volume}"

        return True, "OK"

    async def check_wallet_quality(self, signal: Signal) -> tuple[bool, str]:
        """Check wallet quality thresholds."""
        min_win_rate = await self.config.get("discovery.min_win_rate", Decimal("0.55"))
        min_trades = await self.config.get("discovery.min_trades", 10)

        if signal.wallet_stats.win_rate < min_win_rate:
            return False, f"Wallet win rate too low: {signal.wallet_stats.win_rate}"

        if signal.wallet_stats.total_trades < min_trades:
            return False, f"Wallet trades too few: {signal.wallet_stats.total_trades}"

        return True, "OK"
```

#### Cluster Components

**src/walltrack/core/cluster/signal_amplifier.py:**
```python
"""Cluster signal amplifier with dynamic configuration."""

from decimal import Decimal

from walltrack.services.config.config_service import ConfigService, get_config_service


class SignalAmplifier:
    """
    Amplifies signals based on cluster synchronization.

    Uses configurable amplification factors.
    """

    def __init__(self, config_service: ConfigService):
        self.config = config_service

    async def calculate_amplification(
        self,
        base_score: Decimal,
        sync_ratio: Decimal,
    ) -> Decimal:
        """Calculate amplified score based on cluster sync."""
        enable_amp = await self.config.get(
            "cluster.enable_cluster_amplification",
            True
        )

        if not enable_amp:
            return base_score

        min_sync = await self.config.get(
            "cluster.cluster_min_sync_ratio",
            Decimal("0.3")
        )
        max_boost = await self.config.get(
            "cluster.amplification_max_boost",
            Decimal("1.5")
        )
        amp_factor = await self.config.get(
            "scoring.cluster_amplification_factor",
            Decimal("1.2")
        )

        if sync_ratio < min_sync:
            return base_score

        # Calculate boost proportional to sync ratio
        boost = Decimal("1") + (sync_ratio - min_sync) * (amp_factor - Decimal("1"))
        boost = min(boost, max_boost)

        return base_score * boost
```

**src/walltrack/core/cluster/sync_detector.py:**
```python
"""Cluster sync detection with dynamic configuration."""

from datetime import datetime, timedelta
from decimal import Decimal

from walltrack.services.config.config_service import ConfigService


class SyncDetector:
    """
    Detects synchronized trading activity in clusters.

    Uses configurable time windows and thresholds.
    """

    def __init__(self, config_service: ConfigService):
        self.config = config_service

    async def detect_sync(
        self,
        cluster_trades: list,
        reference_time: datetime,
    ) -> Decimal:
        """Detect synchronization ratio for cluster trades."""
        time_window = await self.config.get(
            "cluster.sync_time_window_minutes",
            60
        )
        overlap_threshold = await self.config.get(
            "cluster.sync_token_overlap_threshold",
            Decimal("0.3")
        )

        window_start = reference_time - timedelta(minutes=time_window)

        # Count trades within window
        in_window = [t for t in cluster_trades if t.timestamp >= window_start]

        if not cluster_trades:
            return Decimal("0")

        sync_ratio = Decimal(len(in_window)) / Decimal(len(cluster_trades))
        return sync_ratio
```

#### Discovery Components

**src/walltrack/discovery/decay_detector.py:**
```python
"""Wallet decay detection with dynamic configuration."""

from datetime import datetime, timedelta
from decimal import Decimal

from walltrack.services.config.config_service import ConfigService


class DecayDetector:
    """
    Detects wallet performance decay.

    Uses configurable lookback periods and thresholds.
    """

    def __init__(self, config_service: ConfigService):
        self.config = config_service

    async def detect_decay(
        self,
        wallet_address: str,
        recent_stats: dict,
        historical_stats: dict,
    ) -> tuple[bool, Decimal]:
        """
        Detect if wallet shows performance decay.

        Returns (is_decaying, decay_amount).
        """
        lookback_days = await self.config.get(
            "discovery.decay_lookback_days",
            30
        )
        threshold = await self.config.get(
            "discovery.decay_threshold",
            Decimal("0.15")
        )

        # Compare recent vs historical win rate
        recent_wr = Decimal(str(recent_stats.get("win_rate", 0)))
        historical_wr = Decimal(str(historical_stats.get("win_rate", 0)))

        if historical_wr == 0:
            return False, Decimal("0")

        decay = (historical_wr - recent_wr) / historical_wr

        is_decaying = decay >= threshold

        return is_decaying, decay
```

### Dependency Injection Setup

**src/walltrack/core/dependencies.py:**
```python
"""Dependency injection setup for services."""

from typing import Optional

from walltrack.services.config.config_service import ConfigService, get_config_service


class ServiceContainer:
    """Container for dependency injection."""

    _instance: Optional["ServiceContainer"] = None
    _config_service: Optional[ConfigService] = None

    @classmethod
    async def get_instance(cls) -> "ServiceContainer":
        """Get or create service container."""
        if cls._instance is None:
            cls._instance = cls()
            await cls._instance._initialize()
        return cls._instance

    async def _initialize(self) -> None:
        """Initialize all services."""
        self._config_service = await get_config_service()

    @property
    def config(self) -> ConfigService:
        """Get config service."""
        if self._config_service is None:
            raise RuntimeError("ServiceContainer not initialized")
        return self._config_service


# Helper function for quick access
async def get_config() -> ConfigService:
    """Get config service via container."""
    container = await ServiceContainer.get_instance()
    return container.config
```

## Implementation Tasks

- [x] Create ServiceContainer for dependency injection
- [x] Migrate SignalScorer to use ConfigService
- [x] Migrate ThresholdChecker to use ConfigService
- [x] Migrate SignalFilter to use ConfigService
- [x] Migrate SignalAmplifier to use ConfigService
- [x] Migrate SyncDetector to use ConfigService
- [x] Migrate LeaderDetection to use ConfigService
- [x] Migrate DecayDetector to use ConfigService
- [x] Migrate PumpFinder to use ConfigService
- [x] Migrate Profiler to use ConfigService
- [x] Remove or deprecate constants files
- [x] Update all service instantiation points
- [x] Write tests for migrated components

## Definition of Done

- [x] All 10 components migrated
- [x] No hardcoded thresholds (except fallbacks)
- [x] Constants files removed/deprecated
- [x] All tests passing
- [x] No grep hits for magic numbers

## File List

### Modified Files
- `src/walltrack/services/scoring/signal_scorer.py`
- `src/walltrack/services/signal/threshold_checker.py`
- `src/walltrack/services/signal/signal_filter.py`
- `src/walltrack/core/cluster/signal_amplifier.py`
- `src/walltrack/core/cluster/sync_detector.py`
- `src/walltrack/core/cluster/leader_detection.py`
- `src/walltrack/discovery/decay_detector.py`
- `src/walltrack/discovery/pump_finder.py`
- `src/walltrack/discovery/profiler.py`

### New Files
- `src/walltrack/core/dependencies.py` - DI container

### Deleted Files
- `src/walltrack/constants/scoring.py` (or deprecated)
- `src/walltrack/constants/thresholds.py` (or deprecated)
