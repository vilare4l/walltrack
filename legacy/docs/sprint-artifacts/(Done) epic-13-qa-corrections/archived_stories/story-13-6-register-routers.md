# Story 13-6: Register Missing API Routers

## Priority: HIGH

## Problem Statement

Several API routers exist but are not registered in `app.py`, making their endpoints inaccessible.

## Evidence

**`app.py` lines 104-113:**
```python
app.include_router(health.router)
app.include_router(webhooks.router, prefix="/webhooks")
app.include_router(wallets.router, prefix="/api/wallets")
app.include_router(clusters.router, prefix="/api")
app.include_router(trades.router, prefix="/api/trades")
app.include_router(config.router, prefix="/api/config")
app.include_router(risk.router, prefix="/api")
app.include_router(discovery.router, prefix="/api")
app.include_router(positions.router, prefix="/api")
app.include_router(positions.analysis_router, prefix="/api")
# MISSING: position_sizing.router
# MISSING: orders.router (after Story 13-1)
```

**`position_sizing.py` exists with endpoints:**
```python
@router.post("/calculate")
async def calculate_position_size(...):
    ...

@router.post("/validate")
async def validate_sizing(...):
    ...
```

## Impact

- `/api/position-sizing/calculate` returns 404
- `/api/position-sizing/validate` returns 404
- Epic 10.5-8 UI cannot call these endpoints

## Solution

Add missing router registrations to `app.py`.

### Changes Required

**File: `src/walltrack/api/app.py`**

```python
from walltrack.api.routes import (
    # ... existing imports ...
    position_sizing,
)

# After existing routers:
app.include_router(position_sizing.router, prefix="/api/position-sizing")

# After Story 13-1 is complete:
# from walltrack.api.routes import orders
# app.include_router(orders.router, prefix="/api/orders")
```

## Acceptance Criteria

- [ ] position_sizing router registered with `/api/position-sizing` prefix
- [ ] `/api/position-sizing/calculate` returns 200
- [ ] `/api/position-sizing/validate` returns 200
- [ ] orders router registered after Story 13-1

## Files to Modify

- `src/walltrack/api/app.py`

## Testing

```bash
# Test position sizing endpoint
curl -X POST http://localhost:8000/api/position-sizing/calculate \
  -H "Content-Type: application/json" \
  -d '{"signal_score": 0.8, "available_balance_sol": 10}'
# Should return 200 with calculated size
```

## Estimated Effort

15 minutes

## Dependencies

- Story 13-1 must be complete before registering orders router
