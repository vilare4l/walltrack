# Story 14.3: Scoring Simplification

## Story Info
- **Epic**: Epic 14 - System Simplification & Automation
- **Status**: ready-for-dev
- **Priority**: P0 - Critical
- **Story Points**: 8
- **Depends on**: Story 14-2 (WalletCache Cluster Integration)

## User Story

**As a** system operator,
**I want** the signal scoring system simplified from 4 weighted factors to a 2-component model with binary token safety,
**So that** I can understand and tune the scoring with 8 parameters instead of 30+, and the system uses a clear, maintainable algorithm.

## Background

**Current State (over-engineered):**
- 4 weighted factors: Wallet (30%), Cluster (25%), Token (25%), Context (20%)
- 15+ sub-criteria with complex calculations
- 30+ configuration parameters
- Context Score is 2/3 placeholders (`volatility_score`, `activity_score` are hardcoded)
- 2 thresholds (0.70 trade, 0.85 high conviction)
- ~1,500 lines of code

**Target State (simplified):**
- Token safety: Binary check (honeypot, freeze, mint authority)
- Wallet score: `win_rate * 0.6 + pnl_normalized * 0.4 + leader_bonus`
- Cluster boost: Multiplier 1.0x to 1.8x
- Single threshold: 0.65
- ~400 lines of code

## Acceptance Criteria

### AC 1: Token Safety Binary Check
**Given** a signal arrives for a token
**When** the scoring system evaluates it
**Then** token safety is checked as a binary gate:
  - If `is_honeypot = True` -> reject immediately
  - If `has_freeze_authority = True` -> reject immediately
  - If `has_mint_authority = True` -> reject immediately
**And** safe tokens pass to wallet scoring
**And** no gradual token score is calculated (removed)

### AC 2: Wallet Score Simplification
**Given** a wallet with `win_rate=0.75`, `avg_pnl=150`, `is_leader=True`
**When** the wallet score is calculated
**Then** the formula is: `(win_rate * 0.6) + (pnl_norm * 0.4) * leader_bonus`
**And** PnL is normalized between -100 and +500 to 0.0-1.0 range
**And** leader bonus is 1.15x multiplier
**And** final score is capped at 1.0

### AC 3: Cluster Boost Application
**Given** a wallet in a cluster with `amplification_factor=1.4`
**When** the final score is calculated
**Then** `final_score = wallet_score * cluster_boost`
**And** cluster_boost is between 1.0x (no cluster) and 1.8x (max)
**And** solo wallets get 1.0x boost (not 0.50 penalty)

### AC 4: Single Threshold Decision
**Given** a signal with `final_score=0.68`
**When** the threshold check is applied
**Then** `TRADE` decision is returned (score >= 0.65)
**And** no HIGH/STANDARD conviction distinction exists
**And** position_multiplier equals the cluster_boost

### AC 5: ScoredSignal Model Simplification
**Given** scoring is complete
**When** the ScoredSignal is created
**Then** it contains flat fields: `final_score`, `wallet_score`, `cluster_boost`, `token_safe`, `is_leader`
**And** the old nested structures (FactorScore, WalletScoreComponents, etc.) are removed
**And** an `explanation` field provides human-readable reasoning

### AC 6: Config Parameter Reduction
**Given** the scoring configuration
**When** I review available parameters
**Then** only ~8 parameters exist:
  - `trade_threshold` (0.65)
  - `wallet_win_rate_weight` (0.60)
  - `wallet_pnl_weight` (0.40)
  - `leader_bonus` (1.15)
  - `pnl_normalize_min` (-100)
  - `pnl_normalize_max` (500)
  - `min_cluster_boost` (1.0)
  - `max_cluster_boost` (1.8)
**And** old 30+ parameters are removed

### AC 7: Config Panel UI Simplification
**Given** the Settings page in the dashboard
**When** I view the scoring configuration
**Then** Token Weight slider is removed
**And** Context Weight slider is removed
**And** High Conviction threshold slider is removed
**And** Pie Chart visualization is removed
**And** Score Preview has 4 inputs (not 8)
**And** Signal Analysis table shows: Time, Wallet, Token, Score, Cluster, Status

### AC 8: Historical Validation
**Given** 30 days of historical signal data
**When** I compare old vs new scoring
**Then** trade eligibility rate is within 10% of old rate
**And** no significant increase in false positives
**And** score distribution is documented

## Technical Specifications

### New Scoring Model

**src/walltrack/models/scoring.py:**
```python
"""Simplified scoring models."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ScoredSignal:
    """
    Simplified scored signal result.

    Replaces the complex nested FactorScore structures.
    """
    # Core scores
    final_score: float
    wallet_score: float
    cluster_boost: float

    # Token safety (binary)
    token_safe: bool
    token_reject_reason: Optional[str] = None

    # Context
    is_leader: bool = False
    cluster_id: Optional[str] = None

    # Decision
    should_trade: bool = False
    position_multiplier: float = 1.0

    # Human-readable explanation
    explanation: str = ""

    @property
    def passed_threshold(self) -> bool:
        """Check if score passed trade threshold."""
        return self.token_safe and self.should_trade


@dataclass
class ScoringConfig:
    """Simplified scoring configuration (~8 parameters)."""
    # Threshold
    trade_threshold: float = 0.65

    # Wallet score weights
    wallet_win_rate_weight: float = 0.60
    wallet_pnl_weight: float = 0.40
    leader_bonus: float = 1.15

    # PnL normalization
    pnl_normalize_min: float = -100.0
    pnl_normalize_max: float = 500.0

    # Cluster boost
    min_cluster_boost: float = 1.0
    max_cluster_boost: float = 1.8
```

### Simplified SignalScorer

**src/walltrack/services/scoring/signal_scorer.py:**
```python
"""Simplified signal scorer."""

from walltrack.models.scoring import ScoredSignal, ScoringConfig
from walltrack.models.token import TokenCharacteristics
from walltrack.services.signal.wallet_cache import WalletCacheEntry


class SignalScorer:
    """
    Simplified 2-component signal scorer.

    Scoring formula:
    1. Token Safety: Binary gate (honeypot, freeze, mint)
    2. Wallet Score: win_rate * 0.6 + pnl_norm * 0.4 + leader_bonus
    3. Cluster Boost: 1.0x to 1.8x multiplier
    4. Final: wallet_score * cluster_boost >= threshold
    """

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or ScoringConfig()

    def score(
        self,
        wallet: WalletCacheEntry,
        token: TokenCharacteristics,
        cluster_boost: float = 1.0,
    ) -> ScoredSignal:
        """
        Score a signal using simplified 2-component model.

        Args:
            wallet: Cached wallet data with profile metrics
            token: Token characteristics including safety flags
            cluster_boost: Cluster amplification factor (1.0-1.8)

        Returns:
            ScoredSignal with decision and explanation
        """
        # Step 1: Token Safety Gate (binary)
        if not self._is_token_safe(token):
            return ScoredSignal(
                final_score=0.0,
                wallet_score=0.0,
                cluster_boost=cluster_boost,
                token_safe=False,
                token_reject_reason=self._get_token_reject_reason(token),
                should_trade=False,
                explanation=f"Token rejected: {self._get_token_reject_reason(token)}",
            )

        # Step 2: Calculate Wallet Score
        wallet_score = self._calculate_wallet_score(wallet)

        # Step 3: Apply Cluster Boost
        clamped_boost = max(
            self.config.min_cluster_boost,
            min(self.config.max_cluster_boost, cluster_boost)
        )
        final_score = min(1.0, wallet_score * clamped_boost)

        # Step 4: Threshold Decision
        should_trade = final_score >= self.config.trade_threshold

        # Build explanation
        explanation = self._build_explanation(
            wallet, wallet_score, clamped_boost, final_score, should_trade
        )

        return ScoredSignal(
            final_score=final_score,
            wallet_score=wallet_score,
            cluster_boost=clamped_boost,
            token_safe=True,
            is_leader=wallet.is_leader,
            cluster_id=wallet.cluster_id,
            should_trade=should_trade,
            position_multiplier=clamped_boost if should_trade else 1.0,
            explanation=explanation,
        )

    def _is_token_safe(self, token: TokenCharacteristics) -> bool:
        """Binary token safety check."""
        if token.is_honeypot:
            return False
        if token.has_freeze_authority:
            return False
        if token.has_mint_authority:
            return False
        return True

    def _get_token_reject_reason(self, token: TokenCharacteristics) -> str:
        """Get reason for token rejection."""
        if token.is_honeypot:
            return "honeypot"
        if token.has_freeze_authority:
            return "freeze_authority"
        if token.has_mint_authority:
            return "mint_authority"
        return "unknown"

    def _calculate_wallet_score(self, wallet: WalletCacheEntry) -> float:
        """
        Calculate wallet score from win_rate and PnL.

        Formula: (win_rate * 0.6) + (pnl_norm * 0.4) * leader_bonus
        """
        # Win rate component (already 0-1)
        win_rate = wallet.win_rate or 0.0

        # PnL normalized to 0-1 range
        pnl_norm = self._normalize_pnl(wallet.avg_pnl or 0.0)

        # Base score
        base_score = (
            win_rate * self.config.wallet_win_rate_weight +
            pnl_norm * self.config.wallet_pnl_weight
        )

        # Apply leader bonus
        if wallet.is_leader:
            base_score *= self.config.leader_bonus

        return min(1.0, base_score)

    def _normalize_pnl(self, pnl: float) -> float:
        """Normalize PnL to 0-1 range."""
        pnl_min = self.config.pnl_normalize_min
        pnl_max = self.config.pnl_normalize_max

        if pnl <= pnl_min:
            return 0.0
        if pnl >= pnl_max:
            return 1.0

        return (pnl - pnl_min) / (pnl_max - pnl_min)

    def _build_explanation(
        self,
        wallet: WalletCacheEntry,
        wallet_score: float,
        cluster_boost: float,
        final_score: float,
        should_trade: bool,
    ) -> str:
        """Build human-readable explanation."""
        parts = [
            f"Wallet: {wallet_score:.2f} (WR:{wallet.win_rate:.0%}, PnL:{wallet.avg_pnl:.0f})",
        ]

        if wallet.is_leader:
            parts.append(f"Leader bonus: {self.config.leader_bonus}x")

        if cluster_boost > 1.0:
            parts.append(f"Cluster boost: {cluster_boost:.2f}x")

        parts.append(f"Final: {final_score:.2f}")

        if should_trade:
            parts.append(f"TRADE (>= {self.config.trade_threshold})")
        else:
            parts.append(f"NO TRADE (< {self.config.trade_threshold})")

        return " | ".join(parts)
```

### Simplified ThresholdChecker

**src/walltrack/services/scoring/threshold_checker.py:**
```python
"""Simplified threshold checker."""

from dataclasses import dataclass
from walltrack.models.scoring import ScoredSignal, ScoringConfig


@dataclass
class ThresholdResult:
    """Result of threshold check."""
    passed: bool
    score: float
    threshold: float
    position_multiplier: float


class ThresholdChecker:
    """
    Simplified single-threshold checker.

    Replaces the dual HIGH/STANDARD threshold system.
    """

    def __init__(self, config: ScoringConfig | None = None):
        self.config = config or ScoringConfig()

    def check(self, signal: ScoredSignal) -> ThresholdResult:
        """
        Check if signal passes trade threshold.

        Args:
            signal: Scored signal to check

        Returns:
            ThresholdResult with pass/fail and multiplier
        """
        if not signal.token_safe:
            return ThresholdResult(
                passed=False,
                score=0.0,
                threshold=self.config.trade_threshold,
                position_multiplier=1.0,
            )

        passed = signal.final_score >= self.config.trade_threshold

        return ThresholdResult(
            passed=passed,
            score=signal.final_score,
            threshold=self.config.trade_threshold,
            position_multiplier=signal.cluster_boost if passed else 1.0,
        )
```

### UI Changes: Config Panel

**src/walltrack/ui/components/config_panel.py:**

The config panel needs to be significantly simplified:

**REMOVE:**
- Token Weight slider
- Context Weight slider
- High Conviction threshold slider
- Pie Chart visualization (4 sectors)
- Complex 8-input Score Preview
- "Normalize" button for weights

**KEEP/MODIFY:**
- Trade Threshold slider (change default to 0.65)
- Wallet score weights (win_rate 60%, pnl 40%)
- Cluster boost range (1.0x - 1.8x)
- Leader bonus config (1.15x)
- Simplified Score Preview (4 inputs)
- Signal Analysis table (simplified columns)

**New Signal Analysis columns:**
```
| Time | Wallet | Token | Score | Cluster | Status |

# Removed: Token Score (T), Context Score (X) columns
# Cluster column shows boost factor (e.g., "1.4x")
```

## Implementation Tasks

- [ ] Create new `ScoredSignal` dataclass (flat structure)
- [ ] Create new `ScoringConfig` dataclass (~8 params)
- [ ] Rewrite `SignalScorer` class (~200 lines)
- [ ] Rewrite `ThresholdChecker` class (~50 lines)
- [ ] Remove old complex models (FactorScore, etc.)
- [ ] Update `constants/scoring.py` (reduce to ~8 params)
- [ ] Remove `constants/threshold.py` dual thresholds
- [ ] Update `SignalPipeline` to use new scorer
- [ ] Update `config_panel.py` (major rewrite, ~440 lines removed)
- [ ] Update `signals.py` table columns
- [ ] Create DB migration for deprecated columns
- [ ] Write validation script for historical comparison
- [ ] Run historical validation on 30 days of signals
- [ ] Update all unit tests for scoring
- [ ] Run `uv run pytest`
- [ ] Run `uv run mypy src/`
- [ ] Verify UI loads and works correctly
- [ ] Update `docs/architecture.md` - Signal Scoring section (see below)

## Definition of Done

- [ ] Token safety is binary check (3 conditions)
- [ ] Wallet score uses only win_rate (60%) + PnL (40%) + leader bonus
- [ ] Cluster boost is direct multiplier (1.0-1.8x)
- [ ] Context score completely removed
- [ ] Single trade threshold (0.65)
- [ ] Code reduced from ~1,500 to ~400 lines (backend)
- [ ] Config Panel UI reduced from 690 to ~250 lines
- [ ] Pie Chart removed from Settings
- [ ] Historical validation shows acceptable trade rate
- [ ] All tests updated and passing
- [ ] **Architecture document updated** (`docs/architecture.md` section "Signal Scoring")

## Test Cases

```python
# tests/unit/services/scoring/test_signal_scorer_simplified.py

import pytest
from decimal import Decimal
from walltrack.models.scoring import ScoredSignal, ScoringConfig
from walltrack.services.scoring.signal_scorer import SignalScorer
from walltrack.services.signal.wallet_cache import WalletCacheEntry
from walltrack.models.token import TokenCharacteristics


class TestTokenSafetyGate:
    """Test binary token safety check."""

    @pytest.fixture
    def scorer(self):
        return SignalScorer()

    @pytest.fixture
    def safe_token(self):
        return TokenCharacteristics(
            address="token123",
            is_honeypot=False,
            has_freeze_authority=False,
            has_mint_authority=False,
        )

    @pytest.fixture
    def good_wallet(self):
        return WalletCacheEntry(
            address="wallet123",
            win_rate=0.75,
            avg_pnl=150.0,
            is_leader=False,
        )

    def test_honeypot_rejected(self, scorer, good_wallet):
        """Honeypot tokens are immediately rejected."""
        token = TokenCharacteristics(
            address="token123",
            is_honeypot=True,
            has_freeze_authority=False,
            has_mint_authority=False,
        )

        result = scorer.score(good_wallet, token)

        assert result.token_safe is False
        assert result.should_trade is False
        assert result.token_reject_reason == "honeypot"

    def test_freeze_authority_rejected(self, scorer, good_wallet):
        """Tokens with freeze authority are rejected."""
        token = TokenCharacteristics(
            address="token123",
            is_honeypot=False,
            has_freeze_authority=True,
            has_mint_authority=False,
        )

        result = scorer.score(good_wallet, token)

        assert result.token_safe is False
        assert result.token_reject_reason == "freeze_authority"

    def test_safe_token_passes(self, scorer, good_wallet, safe_token):
        """Safe tokens pass to wallet scoring."""
        result = scorer.score(good_wallet, safe_token)

        assert result.token_safe is True
        assert result.wallet_score > 0


class TestWalletScoring:
    """Test simplified wallet scoring."""

    @pytest.fixture
    def scorer(self):
        return SignalScorer()

    @pytest.fixture
    def safe_token(self):
        return TokenCharacteristics(
            address="token123",
            is_honeypot=False,
            has_freeze_authority=False,
            has_mint_authority=False,
        )

    def test_wallet_score_calculation(self, scorer, safe_token):
        """Wallet score uses win_rate * 0.6 + pnl_norm * 0.4."""
        wallet = WalletCacheEntry(
            address="wallet123",
            win_rate=0.80,  # 80% win rate
            avg_pnl=200.0,  # Normalized to ~0.5
            is_leader=False,
        )

        result = scorer.score(wallet, safe_token)

        # Expected: 0.80 * 0.6 + 0.5 * 0.4 = 0.48 + 0.20 = 0.68
        assert 0.65 < result.wallet_score < 0.72

    def test_leader_bonus_applied(self, scorer, safe_token):
        """Leaders get 1.15x bonus."""
        wallet = WalletCacheEntry(
            address="wallet123",
            win_rate=0.70,
            avg_pnl=100.0,
            is_leader=True,
        )

        result = scorer.score(wallet, safe_token)

        # Should have leader bonus applied
        assert result.is_leader is True
        # Score should be higher due to 1.15x bonus


class TestClusterBoost:
    """Test cluster boost application."""

    @pytest.fixture
    def scorer(self):
        return SignalScorer()

    @pytest.fixture
    def safe_token(self):
        return TokenCharacteristics(
            address="token123",
            is_honeypot=False,
            has_freeze_authority=False,
            has_mint_authority=False,
        )

    def test_cluster_boost_multiplier(self, scorer, safe_token):
        """Cluster boost multiplies final score."""
        wallet = WalletCacheEntry(
            address="wallet123",
            win_rate=0.60,
            avg_pnl=100.0,
            is_leader=False,
            cluster_id="cluster_1",
        )

        result_solo = scorer.score(wallet, safe_token, cluster_boost=1.0)
        result_cluster = scorer.score(wallet, safe_token, cluster_boost=1.4)

        # Cluster boost should increase final score
        assert result_cluster.final_score > result_solo.final_score
        assert result_cluster.final_score == pytest.approx(
            result_solo.wallet_score * 1.4, rel=0.01
        )

    def test_cluster_boost_clamped(self, scorer, safe_token):
        """Cluster boost is clamped to 1.0-1.8 range."""
        wallet = WalletCacheEntry(
            address="wallet123",
            win_rate=0.70,
            avg_pnl=100.0,
            is_leader=False,
        )

        result = scorer.score(wallet, safe_token, cluster_boost=2.5)

        assert result.cluster_boost == 1.8  # Clamped to max


class TestThresholdDecision:
    """Test single threshold decision."""

    def test_single_threshold(self):
        """Only one threshold at 0.65."""
        scorer = SignalScorer(ScoringConfig(trade_threshold=0.65))

        wallet = WalletCacheEntry(
            address="wallet123",
            win_rate=0.80,
            avg_pnl=200.0,
            is_leader=False,
        )
        token = TokenCharacteristics(
            address="token123",
            is_honeypot=False,
            has_freeze_authority=False,
            has_mint_authority=False,
        )

        result = scorer.score(wallet, token)

        # 0.80 * 0.6 + ~0.5 * 0.4 = 0.68 >= 0.65
        assert result.should_trade is True
        assert result.position_multiplier == 1.0  # No cluster boost
```

## File List

### New Files
- `tests/unit/services/scoring/test_signal_scorer_simplified.py`

### Modified Files
- `src/walltrack/models/scoring.py` - Replace with simplified models
- `src/walltrack/services/scoring/signal_scorer.py` - Complete rewrite
- `src/walltrack/services/scoring/threshold_checker.py` - Simplify
- `src/walltrack/constants/scoring.py` - Reduce to ~8 params
- `src/walltrack/services/signal/pipeline.py` - Use new scorer
- `src/walltrack/ui/components/config_panel.py` - Major simplification
- `src/walltrack/ui/components/signals.py` - Simplify columns

### Files to DELETE (or heavily refactor)
- Old FactorScore, WalletScoreComponents, etc. from models
- Old complex scoring constants

---

## Architecture Document Update Required

**Why:** This story represents a significant architectural evolution. The original `docs/architecture.md` defines a 4-factor scoring model that this story replaces with a simplified 2-component model. To maintain architecture-code consistency, the main architecture document must be updated.

**Sections to update in `docs/architecture.md`:**

### 1. Core Architectural Decisions → Data Architecture (lines ~139-150)

Add a note that scoring has been simplified:
```markdown
**Signal Scoring (Simplified in Epic 14):**
- Token safety: Binary gate (honeypot, freeze, mint authority)
- Wallet score: win_rate (60%) + PnL normalized (40%) + leader bonus (1.15x)
- Cluster boost: Multiplier 1.0x to 1.8x
- Single threshold: 0.65
```

### 2. Exit Strategy System section (lines ~189-237)

Keep the Exit Strategy model (TakeProfitLevel, TrailingStopConfig, etc.) as-is - these are still valid. Only the **signal scoring** changed, not the exit strategy configuration.

### 3. Add new ADR reference

Add to the document:
```markdown
## ADR Reference: Epic 14 Scoring Simplification

**Date:** 2025-12-27
**Status:** Implemented
**Context:** Original 4-factor scoring (Wallet 30%, Cluster 25%, Token 25%, Context 20%) was over-engineered with 30+ parameters and placeholder components.
**Decision:** Simplified to 2-component model + binary token gate. See `docs/sprint-artifacts/epic-14-simplification/architecture.md` for full ADR.
**Consequences:** Code reduced from ~1,500 to ~400 LOC. Config simplified from 30+ to ~8 parameters.
```

### 4. Configuration Layers section (lines ~253-256)

Update scoring config example:
```markdown
**Dynamic** (Supabase table):
- trade_threshold (0.65)
- wallet_win_rate_weight (0.60)
- wallet_pnl_weight (0.40)
- leader_bonus (1.15)
- min/max_cluster_boost (1.0-1.8)
```
