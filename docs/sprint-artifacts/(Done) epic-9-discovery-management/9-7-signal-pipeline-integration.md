# Story 9.7: Signal Pipeline Integration

## Story Info
- **Epic**: Epic 9 - Discovery Management & Scheduling
- **Status**: ready
- **Priority**: Critical
- **Depends on**: Story 3.2 (Signal Filtering), Story 3.4 (Signal Scoring), Story 3.5 (Threshold)

## User Story

**As a** system operator,
**I want** the signal pipeline to be fully connected end-to-end,
**So that** webhook signals are scored, threshold-checked, and can trigger trade execution.

## Problem Statement

The signal pipeline currently has all components built but NOT connected:
- `SignalFilter` works (filters monitored/blacklisted wallets)
- `SignalScorer` exists but is never called
- `ThresholdChecker` exists but is never called

In `src/walltrack/services/signal/pipeline.py` lines 66-68:
```python
# TODO(Story 3.4): Score signal with signal_scorer
# TODO(Story 3.5): Apply threshold with threshold_checker
```

Signals pass filtering but then disappear - they're never scored or evaluated for trading.

## Acceptance Criteria

### AC 1: Pipeline Connects All Components
**Given** a webhook signal passes filtering
**When** the signal context is created
**Then** the signal is scored using `SignalScorer`
**And** the scored signal is checked against threshold
**And** eligible signals are marked for trade execution

### AC 2: Wallet Data Loading
**Given** a signal needs scoring
**When** the scorer requires wallet metrics
**Then** wallet data is loaded from repository (win_rate, score, profile)
**And** missing wallet data is handled gracefully (use defaults)
**And** data is cached for performance

### AC 3: Token Data Loading
**Given** a signal needs scoring
**When** the scorer requires token characteristics
**Then** token data is fetched (liquidity, market cap, age)
**And** honeypot risk is evaluated
**And** missing token data uses safe defaults

### AC 4: Threshold Decision Logging
**Given** a scored signal reaches threshold checker
**When** threshold decision is made
**Then** decision is logged (PASS/FAIL, score, margin)
**And** eligible signals are returned with conviction level
**And** metrics are updated for monitoring

### AC 5: Trade Execution Bridge
**Given** a signal passes threshold
**When** it's marked as trade-eligible
**Then** signal is converted to trade request format
**And** trade request is queued for Epic 4 execution
**And** signal-to-trade link is recorded

## Technical Specifications

### Updated Pipeline Flow

```python
# src/walltrack/services/signal/pipeline.py

class SignalPipeline:
    def __init__(
        self,
        signal_filter: SignalFilter,
        signal_scorer: SignalScorer,           # ADD
        threshold_checker: ThresholdChecker,   # ADD
        wallet_repo: WalletRepository,         # ADD
        token_service: TokenCharacteristicsService,  # ADD
        trade_queue: TradeQueue,               # ADD (optional)
    ):
        self.filter = signal_filter
        self.scorer = signal_scorer
        self.threshold = threshold_checker
        self.wallet_repo = wallet_repo
        self.token_service = token_service
        self.trade_queue = trade_queue

    async def process_swap_event(
        self, event: ParsedSwapEvent
    ) -> ProcessingResult:
        """Full pipeline: filter -> score -> threshold -> execute."""

        # Step 1: Filter (existing)
        filter_result = await self.filter.filter_signal(event)
        if filter_result.status != FilterStatus.PASSED:
            return ProcessingResult(
                passed=False,
                reason=filter_result.status.value
            )

        signal_context = filter_result.context

        # Step 2: Load enrichment data
        wallet_data = await self._load_wallet_data(event.wallet_address)
        token_data = await self._load_token_data(event.token_address)

        # Step 3: Score signal (NEW)
        scored_signal = await self.scorer.score(
            signal=signal_context,
            wallet=wallet_data,
            token=token_data,
        )

        # Step 4: Apply threshold (NEW)
        threshold_result = await self.threshold.check(scored_signal)

        if not threshold_result.is_eligible:
            return ProcessingResult(
                passed=False,
                reason="below_threshold",
                score=scored_signal.final_score,
            )

        # Step 5: Queue for execution (NEW)
        trade_eligible = threshold_result.trade_signal
        if self.trade_queue:
            await self.trade_queue.enqueue(trade_eligible)

        return ProcessingResult(
            passed=True,
            score=scored_signal.final_score,
            conviction=trade_eligible.conviction_level,
            trade_queued=True,
        )
```

### Data Loading Helpers

```python
async def _load_wallet_data(self, address: str) -> WalletScoringData:
    """Load wallet data for scoring with caching."""
    # Check cache first
    cached = self._wallet_cache.get(address)
    if cached:
        return cached

    # Load from repository
    wallet = await self.wallet_repo.get_by_address(address)
    if not wallet:
        # Return safe defaults for unknown wallet
        return WalletScoringData(
            score=0.3,
            win_rate=0.0,
            total_trades=0,
            is_decayed=False,
            is_cluster_leader=False,
        )

    data = WalletScoringData(
        score=wallet.score,
        win_rate=wallet.profile.win_rate,
        total_trades=wallet.profile.total_trades,
        avg_pnl=wallet.profile.avg_pnl_per_trade,
        timing_percentile=wallet.profile.timing_percentile,
        is_decayed=wallet.status == WalletStatus.DECAY_DETECTED,
        is_cluster_leader=False,  # TODO: Load from Neo4j
    )

    self._wallet_cache.set(address, data, ttl=300)  # 5 min cache
    return data

async def _load_token_data(self, mint: str) -> TokenCharacteristics:
    """Load token characteristics for scoring."""
    try:
        return await self.token_service.get_characteristics(mint)
    except Exception as e:
        log.warning("token_data_failed", mint=mint, error=str(e))
        # Return conservative defaults
        return TokenCharacteristics(
            liquidity_usd=0,
            market_cap_usd=0,
            holder_count=0,
            age_minutes=0,
            is_honeypot=True,  # Assume worst case
        )
```

### Processing Result Model

```python
@dataclass
class ProcessingResult:
    """Result of full pipeline processing."""
    passed: bool
    reason: str = ""
    score: float = 0.0
    conviction: ConvictionLevel = ConvictionLevel.NONE
    trade_queued: bool = False
    processing_time_ms: float = 0.0
```

### Integration with Webhooks

```python
# src/walltrack/api/routes/webhooks.py

async def _process_swap_event(event: ParsedSwapEvent) -> None:
    """Process swap event through full pipeline."""
    pipeline = await get_signal_pipeline()  # Dependency injection

    start = time.time()
    result = await pipeline.process_swap_event(event)
    duration_ms = (time.time() - start) * 1000

    log.info(
        "signal_processed",
        wallet=event.wallet_address[:12],
        token=event.token_address[:12],
        passed=result.passed,
        score=f"{result.score:.2f}" if result.score else None,
        conviction=result.conviction.value if result.passed else None,
        duration_ms=f"{duration_ms:.1f}",
    )
```

## Dependencies

### New Dependencies
```python
# Add to pipeline factory
from walltrack.services.scoring.signal_scorer import SignalScorer
from walltrack.services.scoring.threshold_checker import ThresholdChecker
from walltrack.services.token.characteristics import TokenCharacteristicsService
```

### Existing Components Used
- `SignalFilter` (Story 3.2)
- `SignalScorer` (Story 3.4)
- `ThresholdChecker` (Story 3.5)
- `WalletRepository` (Epic 1)

## Testing Requirements

### Unit Tests
```python
class TestSignalPipelineIntegration:
    async def test_full_pipeline_high_score_passes(self):
        """Signal with high wallet score passes threshold."""

    async def test_full_pipeline_low_score_rejected(self):
        """Signal with low score is rejected at threshold."""

    async def test_missing_wallet_uses_defaults(self):
        """Unknown wallet gets safe default scores."""

    async def test_honeypot_token_rejected(self):
        """Honeypot tokens are rejected regardless of wallet."""

    async def test_trade_queued_on_pass(self):
        """Eligible signals are queued for execution."""
```

### Integration Tests
```python
async def test_webhook_to_trade_queue():
    """Full flow from webhook to trade queue."""
    # Send mock webhook
    # Verify signal scored
    # Verify threshold checked
    # Verify trade queued
```

## Definition of Done

- [ ] Pipeline connects filter -> scorer -> threshold
- [ ] Wallet data loaded from repository with caching
- [ ] Token data loaded with safe defaults on failure
- [ ] Trade-eligible signals queued for execution
- [ ] Logging at each pipeline stage
- [ ] Unit tests pass (>90% coverage)
- [ ] Integration test: webhook -> trade queue works
- [ ] Performance: full pipeline < 100ms

## Estimated Effort

- **Implementation**: 3-4 hours
- **Testing**: 2 hours
- **Total**: 5-6 hours

## Notes

This is the CRITICAL missing piece. All components exist but aren't wired together. After this story, signals will actually be evaluated and can trigger trades.
