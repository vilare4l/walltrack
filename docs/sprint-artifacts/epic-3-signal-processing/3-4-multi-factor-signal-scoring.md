# Story 3.4: Multi-Factor Signal Scoring Engine

## Story Info
- **Epic**: Epic 3 - Real-Time Signal Processing & Scoring
- **Status**: ready
- **Priority**: High
- **FR**: FR15

## User Story

**As an** operator,
**I want** signals scored using multiple factors,
**So that** high-quality opportunities are prioritized.

## Acceptance Criteria

### AC 1: Factor Calculation
**Given** a filtered signal with wallet and token data
**When** scoring engine processes the signal
**Then** four factor scores are calculated:
- Wallet score (30%): based on wallet performance metrics
- Cluster score (25%): based on cluster activity and leader status
- Token score (25%): based on token characteristics
- Context score (20%): based on timing, market conditions

### AC 2: Wallet Score
**Given** wallet score calculation
**When** wallet metrics are evaluated
**Then** win rate, PnL history, timing percentile contribute to score
**And** decay status reduces score if flagged
**And** leader status in cluster boosts score

### AC 3: Cluster Score
**Given** cluster score calculation
**When** cluster activity is checked (from Story 2.6)
**Then** amplification factor is applied if cluster members moved together
**And** solo wallet movement gets base cluster score

### AC 4: Token Score
**Given** token score calculation
**When** token characteristics are evaluated
**Then** liquidity, market cap, holder distribution contribute
**And** very new tokens (< 5 min) get reduced score
**And** suspicious patterns (honeypot indicators) reduce score

### AC 5: Context Score
**Given** context score calculation
**When** market context is evaluated
**Then** time of day patterns are considered
**And** recent market volatility is factored

### AC 6: Final Score
**Given** all factor scores calculated
**When** final score is computed
**Then** weighted average produces score between 0.0 and 1.0
**And** individual factor contributions are preserved for analysis

## Technical Notes

- FR15: Calculate multi-factor signal score
- Implement in `src/walltrack/core/scoring/signal_scorer.py`
- Weights configurable via Supabase config table
- ML model (XGBoost) can replace/augment rules-based scoring later

---

## Technical Specification

### 1. Domain Models

```python
# src/walltrack/core/models/scoring.py
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator


class ScoreCategory(str, Enum):
    """Categories of signal scoring factors."""
    WALLET = "wallet"
    CLUSTER = "cluster"
    TOKEN = "token"
    CONTEXT = "context"


class FactorScore(BaseModel):
    """Individual factor score with breakdown."""

    category: ScoreCategory
    score: float = Field(..., ge=0.0, le=1.0)
    weight: float = Field(..., ge=0.0, le=1.0)
    weighted_contribution: float = Field(..., ge=0.0)
    components: dict[str, float] = Field(default_factory=dict)
    explanation: str = ""


class WalletScoreComponents(BaseModel):
    """Components of wallet score calculation."""

    win_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    avg_pnl_percentage: float = Field(default=0.0)
    timing_percentile: float = Field(default=0.5, ge=0.0, le=1.0)
    consistency_score: float = Field(default=0.5, ge=0.0, le=1.0)
    is_leader: bool = False
    leader_bonus: float = Field(default=0.0, ge=0.0)
    decay_penalty: float = Field(default=0.0, ge=0.0, le=0.5)


class ClusterScoreComponents(BaseModel):
    """Components of cluster score calculation."""

    cluster_size: int = Field(default=1, ge=1)
    active_members_count: int = Field(default=0, ge=0)
    participation_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    amplification_factor: float = Field(default=1.0, ge=1.0)
    cluster_strength: float = Field(default=0.0, ge=0.0, le=1.0)
    is_solo_signal: bool = True


class TokenScoreComponents(BaseModel):
    """Components of token score calculation."""

    liquidity_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_cap_score: float = Field(default=0.5, ge=0.0, le=1.0)
    holder_distribution_score: float = Field(default=0.5, ge=0.0, le=1.0)
    volume_score: float = Field(default=0.5, ge=0.0, le=1.0)
    age_penalty: float = Field(default=0.0, ge=0.0, le=0.5)  # Penalty for very new tokens
    honeypot_risk: float = Field(default=0.0, ge=0.0, le=1.0)


class ContextScoreComponents(BaseModel):
    """Components of context score calculation."""

    time_of_day_score: float = Field(default=0.5, ge=0.0, le=1.0)
    market_volatility_score: float = Field(default=0.5, ge=0.0, le=1.0)
    recent_activity_score: float = Field(default=0.5, ge=0.0, le=1.0)


class ScoringWeights(BaseModel):
    """Configurable weights for scoring factors."""

    wallet: float = Field(default=0.30, ge=0.0, le=1.0)
    cluster: float = Field(default=0.25, ge=0.0, le=1.0)
    token: float = Field(default=0.25, ge=0.0, le=1.0)
    context: float = Field(default=0.20, ge=0.0, le=1.0)

    @field_validator("context")
    @classmethod
    def validate_weights_sum(cls, v, info):
        """Ensure weights sum to 1.0."""
        values = info.data
        total = values.get("wallet", 0.3) + values.get("cluster", 0.25) + \
                values.get("token", 0.25) + v
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v


class ScoredSignal(BaseModel):
    """Signal with complete scoring breakdown."""

    # Signal identification
    tx_signature: str
    wallet_address: str
    token_address: str
    direction: str

    # Final score
    final_score: float = Field(..., ge=0.0, le=1.0)

    # Factor breakdowns
    wallet_score: FactorScore
    cluster_score: FactorScore
    token_score: FactorScore
    context_score: FactorScore

    # Detailed components (for analysis)
    wallet_components: WalletScoreComponents
    cluster_components: ClusterScoreComponents
    token_components: TokenScoreComponents
    context_components: ContextScoreComponents

    # Metadata
    weights_used: ScoringWeights
    scored_at: datetime = Field(default_factory=datetime.utcnow)
    scoring_time_ms: float = 0.0


class ScoringConfig(BaseModel):
    """Complete scoring configuration from database."""

    weights: ScoringWeights = Field(default_factory=ScoringWeights)

    # Wallet scoring params
    leader_bonus_multiplier: float = 0.15
    decay_penalty_max: float = 0.3
    min_trades_for_stats: int = 5

    # Token scoring params
    min_liquidity_usd: float = 1000.0
    optimal_liquidity_usd: float = 50000.0
    new_token_age_penalty_minutes: int = 5
    max_age_penalty: float = 0.3

    # Cluster scoring params
    solo_signal_base_score: float = 0.5
    min_cluster_participation: float = 0.3

    # Context scoring params
    peak_hours_utc: list[int] = Field(default_factory=lambda: [14, 15, 16, 17, 18])
    high_volatility_threshold: float = 0.1

    updated_at: datetime = Field(default_factory=datetime.utcnow)
```

### 2. Configuration Constants

```python
# src/walltrack/core/constants/scoring.py
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
```

### 3. Scoring Engine Service

```python
# src/walltrack/core/scoring/signal_scorer.py
import time
from datetime import datetime, timezone

import structlog

from walltrack.core.constants.scoring import (
    CONSISTENCY_WEIGHT,
    DEFAULT_CLUSTER_WEIGHT,
    DEFAULT_CONTEXT_WEIGHT,
    DEFAULT_TOKEN_WEIGHT,
    DEFAULT_WALLET_WEIGHT,
    HIGH_VOLATILITY_THRESHOLD,
    HOLDER_DIST_WEIGHT,
    LEADER_BONUS,
    LIQUIDITY_WEIGHT,
    MARKET_CAP_WEIGHT,
    MAX_DECAY_PENALTY,
    MAX_NEW_TOKEN_PENALTY,
    MIN_LIQUIDITY_USD,
    MIN_MARKET_CAP_USD,
    NEW_TOKEN_PENALTY_MINUTES,
    OPTIMAL_LIQUIDITY_USD,
    OPTIMAL_MARKET_CAP_USD,
    PEAK_TRADING_HOURS_UTC,
    PNL_WEIGHT,
    SOLO_SIGNAL_BASE,
    TIMING_WEIGHT,
    VOLUME_WEIGHT,
    WIN_RATE_WEIGHT,
)
from walltrack.core.models.scoring import (
    ClusterScoreComponents,
    ContextScoreComponents,
    FactorScore,
    ScoreCategory,
    ScoredSignal,
    ScoringConfig,
    ScoringWeights,
    TokenScoreComponents,
    WalletScoreComponents,
)
from walltrack.core.models.signal_filter import SignalContext
from walltrack.core.models.token import TokenCharacteristics
from walltrack.core.models.wallet import Wallet
from walltrack.services.cluster.amplifier import ClusterAmplifier

logger = structlog.get_logger(__name__)


class SignalScorer:
    """
    Multi-factor signal scoring engine.

    Calculates weighted score from:
    - Wallet score (30%): performance, timing, leader status
    - Cluster score (25%): activity amplification
    - Token score (25%): liquidity, market cap, holder distribution
    - Context score (20%): timing, market conditions
    """

    def __init__(
        self,
        config: ScoringConfig | None = None,
        cluster_amplifier: ClusterAmplifier | None = None,
    ):
        self.config = config or ScoringConfig()
        self.cluster_amplifier = cluster_amplifier

    async def score(
        self,
        signal: SignalContext,
        wallet: Wallet,
        token: TokenCharacteristics,
    ) -> ScoredSignal:
        """
        Calculate multi-factor score for a signal.

        Args:
            signal: Filtered signal context
            wallet: Wallet data with performance metrics
            token: Token characteristics

        Returns:
            ScoredSignal with complete breakdown
        """
        start_time = time.perf_counter()

        # Calculate individual factor scores
        wallet_score, wallet_components = self._calculate_wallet_score(
            wallet, signal.is_cluster_leader
        )
        cluster_score, cluster_components = await self._calculate_cluster_score(
            signal, wallet
        )
        token_score, token_components = self._calculate_token_score(token)
        context_score, context_components = self._calculate_context_score(signal)

        # Get weights
        weights = self.config.weights

        # Calculate weighted final score (AC6)
        final_score = (
            wallet_score.weighted_contribution +
            cluster_score.weighted_contribution +
            token_score.weighted_contribution +
            context_score.weighted_contribution
        )

        # Clamp to [0, 1]
        final_score = max(0.0, min(1.0, final_score))

        scoring_time_ms = (time.perf_counter() - start_time) * 1000

        logger.info(
            "signal_scored",
            wallet=signal.wallet_address[:8] + "...",
            token=signal.token_address[:8] + "...",
            final_score=round(final_score, 4),
            wallet_score=round(wallet_score.score, 4),
            cluster_score=round(cluster_score.score, 4),
            token_score=round(token_score.score, 4),
            context_score=round(context_score.score, 4),
            scoring_time_ms=round(scoring_time_ms, 2),
        )

        return ScoredSignal(
            tx_signature=signal.tx_signature,
            wallet_address=signal.wallet_address,
            token_address=signal.token_address,
            direction=signal.direction,
            final_score=final_score,
            wallet_score=wallet_score,
            cluster_score=cluster_score,
            token_score=token_score,
            context_score=context_score,
            wallet_components=wallet_components,
            cluster_components=cluster_components,
            token_components=token_components,
            context_components=context_components,
            weights_used=weights,
            scoring_time_ms=scoring_time_ms,
        )

    def _calculate_wallet_score(
        self,
        wallet: Wallet,
        is_leader: bool,
    ) -> tuple[FactorScore, WalletScoreComponents]:
        """
        Calculate wallet score (AC2).

        Components:
        - Win rate (35%)
        - PnL history (25%)
        - Timing percentile (25%)
        - Consistency (15%)
        + Leader bonus
        - Decay penalty
        """
        # Component scores
        win_rate = wallet.win_rate if wallet.win_rate else 0.5
        avg_pnl = wallet.avg_pnl_percentage if wallet.avg_pnl_percentage else 0.0
        timing = wallet.timing_percentile if wallet.timing_percentile else 0.5
        consistency = wallet.consistency_score if wallet.consistency_score else 0.5

        # Normalize PnL to [0, 1] range (assuming -100% to +500% range)
        pnl_normalized = max(0.0, min(1.0, (avg_pnl + 100) / 600))

        # Base score calculation
        base_score = (
            win_rate * WIN_RATE_WEIGHT +
            pnl_normalized * PNL_WEIGHT +
            timing * TIMING_WEIGHT +
            consistency * CONSISTENCY_WEIGHT
        )

        # Leader bonus (AC2)
        leader_bonus = LEADER_BONUS if is_leader else 0.0

        # Decay penalty (AC2)
        decay_penalty = 0.0
        if wallet.is_decayed:
            decay_penalty = MAX_DECAY_PENALTY

        # Final wallet score
        final_score = max(0.0, min(1.0, base_score + leader_bonus - decay_penalty))

        weight = self.config.weights.wallet
        weighted_contribution = final_score * weight

        components = WalletScoreComponents(
            win_rate=win_rate,
            avg_pnl_percentage=avg_pnl,
            timing_percentile=timing,
            consistency_score=consistency,
            is_leader=is_leader,
            leader_bonus=leader_bonus,
            decay_penalty=decay_penalty,
        )

        return FactorScore(
            category=ScoreCategory.WALLET,
            score=final_score,
            weight=weight,
            weighted_contribution=weighted_contribution,
            components={
                "win_rate": win_rate,
                "pnl_normalized": pnl_normalized,
                "timing": timing,
                "consistency": consistency,
                "leader_bonus": leader_bonus,
                "decay_penalty": decay_penalty,
            },
            explanation=f"Wallet score: {final_score:.2f} (win_rate={win_rate:.2f}, leader={is_leader})",
        ), components

    async def _calculate_cluster_score(
        self,
        signal: SignalContext,
        wallet: Wallet,
    ) -> tuple[FactorScore, ClusterScoreComponents]:
        """
        Calculate cluster score (AC3).

        Uses amplification factor from Story 2.6 if cluster activity detected.
        Solo signals get base cluster score.
        """
        weight = self.config.weights.cluster

        # Check if wallet is in a cluster
        if not signal.cluster_id or self.cluster_amplifier is None:
            # Solo signal (AC3)
            components = ClusterScoreComponents(
                cluster_size=1,
                is_solo_signal=True,
            )

            return FactorScore(
                category=ScoreCategory.CLUSTER,
                score=SOLO_SIGNAL_BASE,
                weight=weight,
                weighted_contribution=SOLO_SIGNAL_BASE * weight,
                components={"is_solo": True, "base_score": SOLO_SIGNAL_BASE},
                explanation="Solo signal - base cluster score applied",
            ), components

        # Get cluster amplification (from Story 2.6)
        amplification = await self.cluster_amplifier.calculate_amplification(
            cluster_id=signal.cluster_id,
            token_address=signal.token_address,
        )

        if not amplification:
            components = ClusterScoreComponents(is_solo_signal=True)
            return FactorScore(
                category=ScoreCategory.CLUSTER,
                score=SOLO_SIGNAL_BASE,
                weight=weight,
                weighted_contribution=SOLO_SIGNAL_BASE * weight,
                components={"is_solo": True},
                explanation="No cluster amplification data",
            ), components

        # Calculate cluster score from amplification
        # Amplification factor is typically 1.0-1.8
        # Map to score: (factor - 1.0) / 0.8 for 1.0-1.8 range
        factor = amplification.amplification_factor.final_factor
        cluster_score = min(1.0, (factor - 1.0) / 0.8 + SOLO_SIGNAL_BASE)

        components = ClusterScoreComponents(
            cluster_size=amplification.cluster_activity.member_count,
            active_members_count=amplification.cluster_activity.active_in_window,
            participation_rate=amplification.cluster_activity.participation_rate,
            amplification_factor=factor,
            cluster_strength=amplification.cluster_activity.cluster_strength,
            is_solo_signal=False,
        )

        return FactorScore(
            category=ScoreCategory.CLUSTER,
            score=cluster_score,
            weight=weight,
            weighted_contribution=cluster_score * weight,
            components={
                "amplification_factor": factor,
                "participation_rate": components.participation_rate,
                "cluster_strength": components.cluster_strength,
            },
            explanation=f"Cluster amplification: {factor:.2f}x",
        ), components

    def _calculate_token_score(
        self,
        token: TokenCharacteristics,
    ) -> tuple[FactorScore, TokenScoreComponents]:
        """
        Calculate token score (AC4).

        Components:
        - Liquidity (30%)
        - Market cap (25%)
        - Holder distribution (20%)
        - Volume (25%)
        - New token penalty
        - Honeypot risk
        """
        # Liquidity score (higher is better, with optimal ceiling)
        liquidity_usd = token.liquidity.usd if token.liquidity else 0
        if liquidity_usd < MIN_LIQUIDITY_USD:
            liquidity_score = 0.0
        elif liquidity_usd >= OPTIMAL_LIQUIDITY_USD:
            liquidity_score = 1.0
        else:
            liquidity_score = (liquidity_usd - MIN_LIQUIDITY_USD) / \
                             (OPTIMAL_LIQUIDITY_USD - MIN_LIQUIDITY_USD)

        # Market cap score
        mcap = token.market_cap_usd or 0
        if mcap < MIN_MARKET_CAP_USD:
            mcap_score = 0.2  # Low but not zero
        elif mcap >= OPTIMAL_MARKET_CAP_USD:
            mcap_score = 1.0
        else:
            mcap_score = 0.2 + 0.8 * (mcap - MIN_MARKET_CAP_USD) / \
                        (OPTIMAL_MARKET_CAP_USD - MIN_MARKET_CAP_USD)

        # Holder distribution score
        holder_score = 0.5  # Default
        if token.holder_count:
            # More holders is better
            holder_score = min(1.0, token.holder_count / 500)

        if token.top_10_holder_percentage:
            # Penalize concentrated holdings
            concentration_penalty = max(0, (token.top_10_holder_percentage - 30) / 70)
            holder_score -= concentration_penalty * 0.3

        # Volume score (24h)
        volume = token.volume.h24 if token.volume else 0
        volume_score = min(1.0, volume / 100000) if volume > 0 else 0.3

        # Base token score
        base_score = (
            liquidity_score * LIQUIDITY_WEIGHT +
            mcap_score * MARKET_CAP_WEIGHT +
            holder_score * HOLDER_DIST_WEIGHT +
            volume_score * VOLUME_WEIGHT
        )

        # Age penalty for very new tokens (AC4)
        age_penalty = 0.0
        if token.is_new_token and token.age_minutes < NEW_TOKEN_PENALTY_MINUTES:
            age_penalty = MAX_NEW_TOKEN_PENALTY * \
                         (1 - token.age_minutes / NEW_TOKEN_PENALTY_MINUTES)

        # Honeypot risk (AC4)
        honeypot_risk = 0.0
        if token.is_honeypot:
            honeypot_risk = 0.5
        elif token.has_freeze_authority or token.has_mint_authority:
            honeypot_risk = 0.2

        # Final token score
        final_score = max(0.0, min(1.0, base_score - age_penalty - honeypot_risk))

        weight = self.config.weights.token
        weighted_contribution = final_score * weight

        components = TokenScoreComponents(
            liquidity_score=liquidity_score,
            market_cap_score=mcap_score,
            holder_distribution_score=holder_score,
            volume_score=volume_score,
            age_penalty=age_penalty,
            honeypot_risk=honeypot_risk,
        )

        return FactorScore(
            category=ScoreCategory.TOKEN,
            score=final_score,
            weight=weight,
            weighted_contribution=weighted_contribution,
            components={
                "liquidity": liquidity_score,
                "market_cap": mcap_score,
                "holders": holder_score,
                "volume": volume_score,
                "age_penalty": age_penalty,
                "honeypot_risk": honeypot_risk,
            },
            explanation=f"Token score: {final_score:.2f} (liq={liquidity_score:.2f})",
        ), components

    def _calculate_context_score(
        self,
        signal: SignalContext,
    ) -> tuple[FactorScore, ContextScoreComponents]:
        """
        Calculate context score (AC5).

        Components:
        - Time of day patterns
        - Market volatility
        """
        # Time of day score
        current_hour = signal.timestamp.hour
        if current_hour in PEAK_TRADING_HOURS_UTC:
            time_score = 1.0
        elif abs(current_hour - 16) <= 2:  # Near peak
            time_score = 0.8
        else:
            time_score = 0.6

        # Market volatility (placeholder - would integrate with market data)
        volatility_score = 0.7  # Default moderate

        # Recent activity score (placeholder)
        activity_score = 0.6

        # Combined context score
        final_score = (
            time_score * 0.4 +
            volatility_score * 0.35 +
            activity_score * 0.25
        )

        weight = self.config.weights.context
        weighted_contribution = final_score * weight

        components = ContextScoreComponents(
            time_of_day_score=time_score,
            market_volatility_score=volatility_score,
            recent_activity_score=activity_score,
        )

        return FactorScore(
            category=ScoreCategory.CONTEXT,
            score=final_score,
            weight=weight,
            weighted_contribution=weighted_contribution,
            components={
                "time_of_day": time_score,
                "volatility": volatility_score,
                "activity": activity_score,
            },
            explanation=f"Context score: {final_score:.2f} (hour={current_hour})",
        ), components

    def update_config(self, config: ScoringConfig) -> None:
        """Update scoring configuration (hot-reload)."""
        self.config = config
        logger.info(
            "scoring_config_updated",
            weights=config.weights.model_dump(),
        )
```

### 4. Scoring Config Repository

```python
# src/walltrack/data/supabase/repositories/scoring_config_repo.py
from datetime import datetime, timezone

import structlog
from supabase import AsyncClient

from walltrack.core.models.scoring import ScoringConfig, ScoringWeights

logger = structlog.get_logger(__name__)


class ScoringConfigRepository:
    """Repository for scoring configuration."""

    def __init__(self, client: AsyncClient):
        self.client = client
        self._cached_config: ScoringConfig | None = None
        self._cache_time: datetime | None = None
        self._cache_ttl_seconds = 60  # Refresh every minute

    async def get_config(self) -> ScoringConfig:
        """Get current scoring configuration."""
        # Check cache
        if self._cached_config and self._cache_time:
            elapsed = (datetime.now(timezone.utc) - self._cache_time).total_seconds()
            if elapsed < self._cache_ttl_seconds:
                return self._cached_config

        try:
            result = await self.client.table("scoring_config").select(
                "*"
            ).order("updated_at", desc=True).limit(1).execute()

            if not result.data:
                # Return default config
                self._cached_config = ScoringConfig()
                self._cache_time = datetime.now(timezone.utc)
                return self._cached_config

            row = result.data[0]

            weights = ScoringWeights(
                wallet=row.get("weight_wallet", 0.30),
                cluster=row.get("weight_cluster", 0.25),
                token=row.get("weight_token", 0.25),
                context=row.get("weight_context", 0.20),
            )

            config = ScoringConfig(
                weights=weights,
                leader_bonus_multiplier=row.get("leader_bonus", 0.15),
                decay_penalty_max=row.get("decay_penalty_max", 0.30),
                min_liquidity_usd=row.get("min_liquidity_usd", 1000.0),
                new_token_age_penalty_minutes=row.get("new_token_penalty_minutes", 5),
                solo_signal_base_score=row.get("solo_signal_base", 0.5),
                updated_at=datetime.fromisoformat(row["updated_at"]) if row.get("updated_at") else datetime.now(timezone.utc),
            )

            self._cached_config = config
            self._cache_time = datetime.now(timezone.utc)

            return config

        except Exception as e:
            logger.error("scoring_config_fetch_error", error=str(e))
            return self._cached_config or ScoringConfig()

    async def update_config(self, config: ScoringConfig) -> None:
        """Update scoring configuration."""
        await self.client.table("scoring_config").upsert({
            "id": "default",
            "weight_wallet": config.weights.wallet,
            "weight_cluster": config.weights.cluster,
            "weight_token": config.weights.token,
            "weight_context": config.weights.context,
            "leader_bonus": config.leader_bonus_multiplier,
            "decay_penalty_max": config.decay_penalty_max,
            "min_liquidity_usd": config.min_liquidity_usd,
            "new_token_penalty_minutes": config.new_token_age_penalty_minutes,
            "solo_signal_base": config.solo_signal_base_score,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).execute()

        # Invalidate cache
        self._cached_config = config
        self._cache_time = datetime.now(timezone.utc)

        logger.info("scoring_config_saved", weights=config.weights.model_dump())

    def invalidate_cache(self) -> None:
        """Force config refresh on next fetch."""
        self._cache_time = None
```

### 5. Database Schema

```sql
-- Supabase migration: scoring_config table
CREATE TABLE IF NOT EXISTS scoring_config (
    id VARCHAR(50) PRIMARY KEY DEFAULT 'default',

    -- Weights (must sum to 1.0)
    weight_wallet DECIMAL(4, 3) NOT NULL DEFAULT 0.300,
    weight_cluster DECIMAL(4, 3) NOT NULL DEFAULT 0.250,
    weight_token DECIMAL(4, 3) NOT NULL DEFAULT 0.250,
    weight_context DECIMAL(4, 3) NOT NULL DEFAULT 0.200,

    -- Wallet scoring params
    leader_bonus DECIMAL(4, 3) NOT NULL DEFAULT 0.150,
    decay_penalty_max DECIMAL(4, 3) NOT NULL DEFAULT 0.300,
    min_trades_for_stats INTEGER NOT NULL DEFAULT 5,

    -- Token scoring params
    min_liquidity_usd DECIMAL(15, 2) NOT NULL DEFAULT 1000.00,
    optimal_liquidity_usd DECIMAL(15, 2) NOT NULL DEFAULT 50000.00,
    new_token_penalty_minutes INTEGER NOT NULL DEFAULT 5,
    max_age_penalty DECIMAL(4, 3) NOT NULL DEFAULT 0.300,

    -- Cluster scoring params
    solo_signal_base DECIMAL(4, 3) NOT NULL DEFAULT 0.500,
    min_cluster_participation DECIMAL(4, 3) NOT NULL DEFAULT 0.300,

    -- Metadata
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by VARCHAR(100),

    -- Constraint: weights must sum to 1.0
    CONSTRAINT weights_sum_check CHECK (
        ABS(weight_wallet + weight_cluster + weight_token + weight_context - 1.0) < 0.001
    )
);

-- Insert default config
INSERT INTO scoring_config (id) VALUES ('default')
ON CONFLICT (id) DO NOTHING;

-- Audit table for config changes
CREATE TABLE IF NOT EXISTS scoring_config_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config_id VARCHAR(50) NOT NULL,
    previous_values JSONB NOT NULL,
    new_values JSONB NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(100)
);

-- Trigger to track config changes
CREATE OR REPLACE FUNCTION log_scoring_config_change()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO scoring_config_history (config_id, previous_values, new_values, changed_by)
    VALUES (
        OLD.id,
        row_to_json(OLD)::jsonb,
        row_to_json(NEW)::jsonb,
        NEW.updated_by
    );
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scoring_config_audit
    AFTER UPDATE ON scoring_config
    FOR EACH ROW
    EXECUTE FUNCTION log_scoring_config_change();
```

### 6. API Endpoints

```python
# src/walltrack/api/routes/scoring.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import structlog

from walltrack.core.models.scoring import ScoredSignal, ScoringConfig, ScoringWeights
from walltrack.core.scoring.signal_scorer import SignalScorer
from walltrack.data.supabase.repositories.scoring_config_repo import ScoringConfigRepository

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/scoring", tags=["scoring"])


class UpdateWeightsRequest(BaseModel):
    """Request to update scoring weights."""
    wallet: float
    cluster: float
    token: float
    context: float


def get_scoring_config_repo() -> ScoringConfigRepository:
    """Dependency for scoring config repository."""
    from walltrack.data.supabase.client import get_supabase_client
    return ScoringConfigRepository(get_supabase_client())


def get_signal_scorer() -> SignalScorer:
    """Dependency for signal scorer."""
    from walltrack.core.scoring.signal_scorer import get_scorer
    return get_scorer()


@router.get("/config", response_model=ScoringConfig)
async def get_scoring_config(
    repo: ScoringConfigRepository = Depends(get_scoring_config_repo),
) -> ScoringConfig:
    """Get current scoring configuration."""
    return await repo.get_config()


@router.put("/config/weights")
async def update_weights(
    request: UpdateWeightsRequest,
    repo: ScoringConfigRepository = Depends(get_scoring_config_repo),
    scorer: SignalScorer = Depends(get_signal_scorer),
) -> dict:
    """
    Update scoring weights.

    Weights must sum to 1.0.
    Changes take effect immediately (hot-reload).
    """
    # Validate sum
    total = request.wallet + request.cluster + request.token + request.context
    if abs(total - 1.0) > 0.001:
        raise HTTPException(
            status_code=400,
            detail=f"Weights must sum to 1.0, got {total}",
        )

    # Get current config and update weights
    config = await repo.get_config()
    config.weights = ScoringWeights(
        wallet=request.wallet,
        cluster=request.cluster,
        token=request.token,
        context=request.context,
    )

    # Save to database
    await repo.update_config(config)

    # Hot-reload scorer config
    scorer.update_config(config)

    logger.info(
        "scoring_weights_updated",
        wallet=request.wallet,
        cluster=request.cluster,
        token=request.token,
        context=request.context,
    )

    return {
        "status": "updated",
        "weights": config.weights.model_dump(),
    }


@router.post("/config/reset")
async def reset_to_defaults(
    repo: ScoringConfigRepository = Depends(get_scoring_config_repo),
    scorer: SignalScorer = Depends(get_signal_scorer),
) -> dict:
    """Reset scoring configuration to defaults."""
    default_config = ScoringConfig()
    await repo.update_config(default_config)
    scorer.update_config(default_config)

    return {
        "status": "reset",
        "weights": default_config.weights.model_dump(),
    }
```

### 7. Unit Tests

```python
# tests/unit/core/scoring/test_signal_scorer.py
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from walltrack.core.models.scoring import (
    ScoredSignal,
    ScoringConfig,
    ScoringWeights,
)
from walltrack.core.models.signal_filter import SignalContext
from walltrack.core.models.token import TokenCharacteristics, TokenLiquidity
from walltrack.core.models.wallet import Wallet
from walltrack.core.scoring.signal_scorer import SignalScorer


@pytest.fixture
def sample_signal() -> SignalContext:
    """Sample signal context."""
    return SignalContext(
        wallet_address="Wallet123456789012345678901234567890123",
        token_address="Token1234567890123456789012345678901234",
        direction="buy",
        amount_token=1000000,
        amount_sol=1.0,
        timestamp=datetime.now(timezone.utc),
        tx_signature="sig123",
        cluster_id="cluster-1",
        is_cluster_leader=True,
        wallet_reputation=0.8,
    )


@pytest.fixture
def sample_wallet() -> Wallet:
    """Sample wallet with good stats."""
    return Wallet(
        wallet_address="Wallet123456789012345678901234567890123",
        win_rate=0.75,
        avg_pnl_percentage=150.0,
        timing_percentile=0.85,
        consistency_score=0.7,
        is_decayed=False,
        is_leader=True,
    )


@pytest.fixture
def sample_token() -> TokenCharacteristics:
    """Sample token with good characteristics."""
    return TokenCharacteristics(
        token_address="Token1234567890123456789012345678901234",
        name="Good Token",
        symbol="GOOD",
        price_usd=0.001,
        market_cap_usd=200000,
        liquidity=TokenLiquidity(usd=30000),
        holder_count=250,
        age_minutes=60,
        is_new_token=False,
    )


class TestSignalScorer:
    """Tests for SignalScorer."""

    @pytest.mark.asyncio
    async def test_score_calculation(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that scoring produces valid result."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert isinstance(result, ScoredSignal)
        assert 0.0 <= result.final_score <= 1.0
        assert result.wallet_score.score > 0
        assert result.token_score.score > 0

    @pytest.mark.asyncio
    async def test_weights_sum_to_one(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that weights sum to 1.0."""
        scorer = SignalScorer()
        result = await scorer.score(sample_signal, sample_wallet, sample_token)

        weights = result.weights_used
        total = weights.wallet + weights.cluster + weights.token + weights.context
        assert abs(total - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_leader_bonus_applied(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that leader bonus increases wallet score."""
        scorer = SignalScorer()

        # Score with leader status
        sample_signal.is_cluster_leader = True
        result_leader = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Score without leader status
        sample_signal.is_cluster_leader = False
        sample_wallet.is_leader = False
        result_no_leader = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_leader.wallet_score.score > result_no_leader.wallet_score.score

    @pytest.mark.asyncio
    async def test_decay_penalty_applied(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that decay penalty reduces wallet score."""
        scorer = SignalScorer()

        # Score without decay
        sample_wallet.is_decayed = False
        result_normal = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Score with decay
        sample_wallet.is_decayed = True
        result_decayed = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_decayed.wallet_score.score < result_normal.wallet_score.score

    @pytest.mark.asyncio
    async def test_new_token_penalty(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that very new tokens get penalized."""
        scorer = SignalScorer()

        # Established token
        sample_token.is_new_token = False
        sample_token.age_minutes = 60
        result_established = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Very new token
        sample_token.is_new_token = True
        sample_token.age_minutes = 2
        result_new = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_new.token_score.score < result_established.token_score.score

    @pytest.mark.asyncio
    async def test_low_liquidity_score(
        self,
        sample_signal: SignalContext,
        sample_wallet: Wallet,
        sample_token: TokenCharacteristics,
    ):
        """Test that low liquidity reduces token score."""
        scorer = SignalScorer()

        # Good liquidity
        sample_token.liquidity = TokenLiquidity(usd=50000)
        result_good = await scorer.score(sample_signal, sample_wallet, sample_token)

        # Low liquidity
        sample_token.liquidity = TokenLiquidity(usd=500)
        result_low = await scorer.score(sample_signal, sample_wallet, sample_token)

        assert result_low.token_score.score < result_good.token_score.score

    @pytest.mark.asyncio
    async def test_config_update(self):
        """Test that config updates are applied."""
        scorer = SignalScorer()

        new_config = ScoringConfig(
            weights=ScoringWeights(
                wallet=0.40,
                cluster=0.20,
                token=0.20,
                context=0.20,
            )
        )

        scorer.update_config(new_config)

        assert scorer.config.weights.wallet == 0.40
        assert scorer.config.weights.cluster == 0.20
```

---

## Implementation Tasks

- [ ] Create `src/walltrack/core/scoring/signal_scorer.py`
- [ ] Implement wallet score calculation
- [ ] Implement cluster score calculation
- [ ] Implement token score calculation
- [ ] Implement context score calculation
- [ ] Calculate weighted final score
- [ ] Preserve factor contributions
- [ ] Make weights configurable

## Definition of Done

- [ ] All four factors calculated correctly
- [ ] Weighted score between 0.0 and 1.0
- [ ] Factor contributions preserved
- [ ] Weights configurable via config
