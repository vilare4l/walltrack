# Story 13-4: Integrate PositionSizer into RiskManager

## Priority: CRITICAL

## Problem Statement

The `RiskManager` class is a stub that doesn't use the fully implemented `PositionSizer`. This creates two separate paths for position sizing:

1. **SignalPipeline** -> uses `PositionSizer` (correct, Stories 10.5-8 to 10.5-11 implemented)
2. **EntryOrderService** -> uses `RiskManager` (stub, missing all features)

## Evidence

**RiskManager (`risk_manager.py`):**
```python
# Line 102-103:
# TODO: Implement daily loss limit check (Story 10.5-10)
# TODO: Implement concentration limit check (Story 10.5-11)

async def calculate_position_size(self, signal, current_price) -> PositionSizeInfo:
    # Returns basic calculation, doesn't use PositionSizer
    return PositionSizeInfo(
        amount_sol=Decimal("0.1"),  # Hardcoded!
        mode="risk_based",
    )
```

**PositionSizer (`position_sizer.py`):**
- Fully implements Stories 10.5-8 to 10.5-11
- Has DrawdownCalculator, DailyLossTracker, ConcentrationChecker
- Uses PositionConfigRepository for config

## Impact

- Orders created via EntryOrderService have incorrect position sizes
- Daily loss limit not enforced for orders
- Concentration limits not enforced for orders
- Drawdown-based reduction not applied

## Solution

Inject PositionSizer into RiskManager and delegate to it.

### Changes Required

**File: `src/walltrack/services/risk/risk_manager.py`**

```python
from walltrack.services.trade.position_sizer import PositionSizer, get_position_sizer

class RiskManager:
    def __init__(self):
        self._position_sizer: PositionSizer | None = None

    async def _get_position_sizer(self) -> PositionSizer:
        if self._position_sizer is None:
            self._position_sizer = await get_position_sizer()
        return self._position_sizer

    async def calculate_position_size(
        self,
        signal: SignalLogEntry,
        current_price: Decimal,
    ) -> PositionSizeInfo:
        sizer = await self._get_position_sizer()

        # Build request from signal
        request = PositionSizeRequest(
            signal_score=signal.final_score or 0.5,
            available_balance_sol=await self._get_available_balance(),
            current_position_count=await self._get_position_count(),
            current_allocated_sol=await self._get_allocated_sol(),
            token_address=signal.token_address,
            signal_id=signal.id,
            cluster_id=None,  # TODO: Add to signal
        )

        result = await sizer.calculate_size(request)

        return PositionSizeInfo(
            amount_sol=Decimal(str(result.final_size_sol)),
            mode=result.sizing_mode.value,
            decision=result.decision.value,
            reason=result.reason,
        )

    async def check_entry_allowed(
        self,
        token_address: str,
        cluster_id: str | None,
    ) -> RiskCheckResult:
        sizer = await self._get_position_sizer()

        # Use PositionSizer's built-in checks
        request = PositionSizeRequest(
            signal_score=0.75,  # Dummy score for check
            available_balance_sol=await self._get_available_balance(),
            current_position_count=await self._get_position_count(),
            current_allocated_sol=await self._get_allocated_sol(),
            token_address=token_address,
            cluster_id=cluster_id,
        )

        result = await sizer.calculate_size(request)

        if result.decision == SizingDecision.BLOCKED_DRAWDOWN:
            return RiskCheckResult(allowed=False, reason="Blocked by drawdown limit")
        if result.decision == SizingDecision.BLOCKED_DAILY_LOSS:
            return RiskCheckResult(allowed=False, reason="Blocked by daily loss limit")
        if result.decision == SizingDecision.BLOCKED_CONCENTRATION:
            return RiskCheckResult(allowed=False, reason="Blocked by concentration limit")
        if result.decision == SizingDecision.BLOCKED_DUPLICATE:
            return RiskCheckResult(allowed=False, reason="Position already exists")
        if result.decision == SizingDecision.SKIPPED_MAX_POSITIONS:
            return RiskCheckResult(allowed=False, reason="Max positions reached")

        return RiskCheckResult(allowed=True, reason=None)
```

## Acceptance Criteria

- [ ] RiskManager delegates to PositionSizer
- [ ] calculate_position_size uses full sizing logic
- [ ] check_entry_allowed uses PositionSizer's checks
- [ ] Daily loss limit enforced
- [ ] Concentration limits enforced
- [ ] Drawdown-based reduction applied
- [ ] Remove TODO comments after implementation

## Files to Modify

- `src/walltrack/services/risk/risk_manager.py`

## Dependencies

- PositionSizer already complete
- No changes to PositionSizer needed

## Testing

```python
# Test: RiskManager uses PositionSizer
async def test_risk_manager_uses_position_sizer():
    rm = await get_risk_manager()
    signal = create_test_signal(score=0.8)

    result = await rm.calculate_position_size(signal, Decimal("0.001"))

    # Should not be hardcoded 0.1 SOL
    assert result.amount_sol != Decimal("0.1")
    assert result.mode == "risk_based"
```

## Estimated Effort

1-2 hours
