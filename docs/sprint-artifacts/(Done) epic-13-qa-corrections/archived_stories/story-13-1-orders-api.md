# Story 13-1: Create Orders API Route

## Priority: CRITICAL

## Problem Statement

The Orders API route file is completely missing. Epic 10.5-13 (Order UI) requires REST endpoints to list, view, retry, and cancel orders. The underlying infrastructure (model, repository, services) is 100% complete but NOT exposed via REST API.

## Current State

- `src/walltrack/models/order.py` - Complete order model with state machine
- `src/walltrack/data/supabase/repositories/order_repo.py` - Full CRUD + retry logic
- `src/walltrack/services/order/order_factory.py` - Order creation service
- `src/walltrack/services/order/executor.py` - Order execution service
- `src/walltrack/services/order/entry_service.py` - Entry order flow
- **NO `src/walltrack/api/routes/orders.py`** - Missing!
- **NOT registered in `app.py`**

## Required Implementation

Create `src/walltrack/api/routes/orders.py` with:

```python
# Endpoints needed:
GET    /api/orders                    # List orders with pagination and status filter
GET    /api/orders/{order_id}         # Get order details
GET    /api/orders/status/{status}    # Filter by status (pending, filled, failed, etc.)
POST   /api/orders/{order_id}/retry   # Force immediate retry
POST   /api/orders/{order_id}/cancel  # Cancel order with reason
GET    /api/orders/stats              # Order statistics and health metrics
POST   /api/orders/bulk-status        # Get status of multiple orders
```

## Acceptance Criteria

- [ ] Create `routes/orders.py` with all endpoints
- [ ] Register router in `app.py` with prefix `/api/orders`
- [ ] List endpoint supports pagination (limit, offset)
- [ ] List endpoint supports status filter
- [ ] Retry endpoint validates order can be retried
- [ ] Cancel endpoint validates order can be cancelled
- [ ] Stats endpoint returns success rate, avg execution time
- [ ] All endpoints return proper HTTP status codes
- [ ] All endpoints have structured logging

## Files to Create/Modify

- CREATE: `src/walltrack/api/routes/orders.py`
- MODIFY: `src/walltrack/api/app.py` (add router registration)

## Dependencies

- OrderRepository already exists
- Order model already exists
- OrderExecutor already exists

## Estimated Effort

2-3 hours

## Impact

**Blocks:** Epic 10.5-13 (Order UI) cannot function without this
