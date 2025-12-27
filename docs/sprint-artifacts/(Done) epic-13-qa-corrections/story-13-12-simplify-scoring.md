# Story 13-12: Simplify Signal Scoring System

## Priority: MEDIUM

## Problem Statement

The current signal scoring system is over-engineered with 15+ criteria, 30+ configurable parameters, and ~1,500 lines of code. The Context Score (20% of total) is mostly placeholders, Token Score has arbitrary thresholds, and Wallet Consistency adds complexity for minimal value (~4.5% of final score).

The system should be simplified to focus on what actually matters:
1. **Wallet quality** (win rate + PnL)
2. **Cluster amplification** (group activity boost)
3. **Token safety** (honeypot/scam filter - binary)

## Current State

### Complexity Metrics
- **Lines of Code:** ~1,500 LOC across 6+ files
- **Scoring Factors:** 4 (Wallet 30%, Cluster 25%, Token 25%, Context 20%)
- **Sub-criteria:** 15+ individual metrics
- **Configurable Parameters:** 30+ in database
- **Thresholds:** 0.70 (trade), 0.85 (high conviction)

### Files Involved
- `src/walltrack/services/scoring/signal_scorer.py` (706 lines)
- `src/walltrack/services/scoring/threshold_checker.py` (183 lines)
- `src/walltrack/models/scoring.py` (complex nested structures)
- `src/walltrack/constants/scoring.py` (30+ constants)
- `src/walltrack/services/config/models.py` (ScoringConfig)

## Target State

### Simplified Logic
```python
def should_trade(signal, wallet, token, cluster):
    # 1. Token safety filter (binary - blocks scams)
    if not is_token_safe(token):
        return NO_TRADE

    # 2. Wallet score (simple: win_rate 60% + pnl 40%)
    wallet_score = calculate_wallet_score(wallet)

    # 3. Cluster boost (1.0x to 1.8x multiplier)
    cluster_boost = cluster.amplification_factor or 1.0

    # 4. Final decision
    final_score = wallet_score * cluster_boost

    if final_score >= TRADE_THRESHOLD:
        return TRADE_ELIGIBLE, position_multiplier=cluster_boost
    else:
        return NO_TRADE

def is_token_safe(token) -> bool:
    """Binary safety check - blocks honeypots and scams."""
    if token.is_honeypot:
        return False
    if token.has_freeze_authority:
        return False
    if token.has_mint_authority:
        return False
    return True

def calculate_wallet_score(wallet) -> float:
    """Simple wallet quality: win_rate + normalized PnL."""
    win_rate = wallet.profile.win_rate or 0.0
    pnl_normalized = normalize_pnl(wallet.profile.avg_pnl_per_trade)

    score = (win_rate * 0.6) + (pnl_normalized * 0.4)

    # Leader bonus
    if wallet.is_cluster_leader:
        score *= 1.15

    return min(1.0, score)
```

### New Scoring Structure
```
FINAL_SCORE = wallet_score × cluster_boost

Where:
- wallet_score = (win_rate × 0.6) + (pnl_norm × 0.4) [+ leader bonus]
- cluster_boost = amplification_factor (1.0 - 1.8)
- token_safe = binary filter (must pass to trade)

Decision:
- final_score >= 0.65 → TRADE (position_size = cluster_boost × base)
- final_score < 0.65 → NO_TRADE
```

## Required Implementation

### Phase 1: Simplify Signal Scorer

**MODIFY** `src/walltrack/services/scoring/signal_scorer.py`:

1. **REMOVE** `_calculate_context_score()` method entirely (~100 lines)
2. **REMOVE** `_calculate_token_score()` complex scoring (~150 lines)
3. **REPLACE WITH** `_is_token_safe()` binary check (~20 lines)
4. **SIMPLIFY** `_calculate_wallet_score()`:
   - Keep: win_rate, pnl_normalized, leader_bonus
   - Remove: consistency calculation, timing_percentile, decay_penalty
   - Target: ~50 lines (from ~150)
5. **KEEP** `_calculate_cluster_score()` as-is (already simple)
6. **SIMPLIFY** main `score()` method:
   - Check token safety first (early return if unsafe)
   - Calculate wallet_score
   - Apply cluster_boost as multiplier
   - Return simplified ScoredSignal

**Target:** Reduce from 706 lines to ~200 lines

### Phase 2: Simplify Threshold Checker

**MODIFY** `src/walltrack/services/scoring/threshold_checker.py`:

1. **REMOVE** dual threshold logic (0.70/0.85)
2. **REPLACE WITH** single threshold (0.65)
3. **REMOVE** conviction tiers (HIGH/STANDARD)
4. **SIMPLIFY** position multiplier:
   - Use cluster_boost directly as multiplier
   - Remove tier-based multiplier mapping
5. **REMOVE** optional filters (already in token safety check)

**Target:** Reduce from 183 lines to ~50 lines

### Phase 3: Simplify Models

**MODIFY** `src/walltrack/models/scoring.py`:

```python
# BEFORE: Complex nested structures
ScoredSignal
├── wallet_score: FactorScore
├── cluster_score: FactorScore
├── token_score: FactorScore      # REMOVE
├── context_score: FactorScore    # REMOVE
├── wallet_components: WalletScoreComponents
├── cluster_components: ClusterScoreComponents
├── token_components: TokenScoreComponents   # REMOVE
├── context_components: ContextScoreComponents  # REMOVE
└── weights_used: ScoringWeights

# AFTER: Flat simple structure
ScoredSignal
├── final_score: float
├── wallet_score: float
├── cluster_boost: float
├── token_safe: bool
├── is_leader: bool
└── explanation: str
```

**REMOVE** classes:
- `ContextScoreComponents`
- `TokenScoreComponents` (replace with `token_safe: bool`)
- Complex `FactorScore` nesting

### Phase 4: Simplify Constants

**MODIFY** `src/walltrack/constants/scoring.py`:

```python
# BEFORE: 30+ constants
WALLET_WEIGHT = 0.30
CLUSTER_WEIGHT = 0.25
TOKEN_WEIGHT = 0.25
CONTEXT_WEIGHT = 0.20
WALLET_WIN_RATE_WEIGHT = 0.35
WALLET_PNL_WEIGHT = 0.25
# ... 25+ more

# AFTER: ~8 constants
TRADE_THRESHOLD = 0.65
WALLET_WIN_RATE_WEIGHT = 0.60
WALLET_PNL_WEIGHT = 0.40
LEADER_BONUS = 1.15
PNL_NORMALIZE_MIN = -100
PNL_NORMALIZE_MAX = 500
MIN_CLUSTER_BOOST = 1.0
MAX_CLUSTER_BOOST = 1.8
```

### Phase 5: Simplify Config

**MODIFY** `src/walltrack/services/config/models.py`:

Remove from `ScoringConfig`:
- All context_* parameters
- All token_* parameters (except safety flags)
- wallet_timing_weight, wallet_consistency_weight
- Complex sub-weights

Keep:
- trade_threshold
- wallet_win_rate_weight, wallet_pnl_weight
- leader_bonus
- pnl_normalize range

**MODIFY** Config UI:
- Remove pie chart (no more 4 factors)
- Simplify to basic sliders for remaining params

### Phase 6: Update Pipeline

**MODIFY** `src/walltrack/services/signal/pipeline.py`:

1. Update `process_swap_event()` to use simplified scoring
2. Remove context/token score from `ProcessingResult`
3. Simplify logging to show: wallet_score, cluster_boost, token_safe

### Phase 7: Update Tests

**MODIFY** test files:
- `tests/unit/services/scoring/test_signal_scorer.py` - Simplify test cases
- `tests/unit/services/scoring/test_threshold_checker.py` - Remove tier tests
- Remove context_score and token_score assertions
- Add token_safe boolean tests

## Files Summary

### To MODIFY (Major Changes)
```
src/walltrack/services/scoring/signal_scorer.py    (706 → ~200 lines)
src/walltrack/services/scoring/threshold_checker.py (183 → ~50 lines)
src/walltrack/models/scoring.py                    (simplify structures)
src/walltrack/constants/scoring.py                 (30+ → ~8 constants)
src/walltrack/services/config/models.py            (reduce ScoringConfig)
src/walltrack/services/signal/pipeline.py          (update result handling)
```

### To MODIFY (Minor Changes)
```
src/walltrack/ui/components/config_panel.py        (remove pie chart)
src/walltrack/ui/components/signals.py             (update score display)
tests/unit/services/scoring/test_signal_scorer.py
tests/unit/services/scoring/test_threshold_checker.py
```

## Acceptance Criteria

- [ ] Token safety is binary check (honeypot, freeze, mint authorities)
- [ ] Wallet score uses only win_rate (60%) + PnL (40%) + leader bonus
- [ ] Cluster boost applies as direct multiplier (1.0-1.8x)
- [ ] Context score completely removed
- [ ] Single trade threshold (0.65) replaces dual thresholds
- [ ] Position multiplier = cluster_boost (no tier mapping)
- [ ] Configurable parameters reduced to ~8
- [ ] Code reduced from ~1,500 to ~400 lines
- [ ] `uv run pytest` passes
- [ ] `uv run mypy src/` passes
- [ ] Scoring still logs properly for debugging

## Comparison

| Aspect | Before | After |
|--------|--------|-------|
| Lines of Code | ~1,500 | ~400 |
| Scoring Factors | 4 | 2 + 1 filter |
| Sub-criteria | 15+ | 4 |
| Config Parameters | 30+ | ~8 |
| Thresholds | 2 (0.70, 0.85) | 1 (0.65) |
| Token Score | Complex (liquidity, mcap, volume, holders) | Binary (safe/unsafe) |
| Context Score | 3 components (2 placeholders) | Removed |
| Wallet Consistency | Complex calculation | Removed |

## Dependencies

- None - this is a simplification/refactor

## Estimated Effort

4-5 hours

## Impact

- **Reduces complexity** - easier to understand and maintain
- **Faster scoring** - fewer calculations
- **Clearer decisions** - binary token safety + simple score
- **Less config overhead** - fewer parameters to tune
- **Same effectiveness** - honeypot filter + wallet quality = core value
