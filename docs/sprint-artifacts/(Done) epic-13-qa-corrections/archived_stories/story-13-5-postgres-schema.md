# Story 13-5: Fix Postgres Schema References

## Priority: CRITICAL

## Problem Statement

New migrations V9 and V10 reference `walltrack.positions` but the positions table is in the public schema. This causes foreign key constraint failures.

## Evidence

**V9__orders_table.sql:**
```sql
position_id UUID REFERENCES walltrack.positions(id),
-- ERROR: relation "walltrack.positions" does not exist
```

**V10__price_history.sql:**
```sql
position_id UUID NOT NULL REFERENCES walltrack.positions(id),
-- ERROR: relation "walltrack.positions" does not exist
```

**Actual table location:**
```sql
-- From 009_positions.sql (old migration):
CREATE TABLE IF NOT EXISTS positions (  -- NO schema prefix = public schema
    id TEXT PRIMARY KEY,
    ...
);
```

## Impact

- V9 and V10 migrations will FAIL on execution
- Orders cannot be linked to positions
- Price history cannot be tracked per position
- Epic 10.5 and 12 database support is broken

## Solution Options

### Option A: Move positions to walltrack schema (Recommended)
Create migration to move public.positions to walltrack.positions.

### Option B: Update V9/V10 to reference public.positions
Less disruptive but inconsistent with new schema convention.

## Recommended: Option A

Maintains schema consistency with new migration system.

### Changes Required

**Create new migration: `V15__move_positions_schema.sql`**

```sql
-- Move positions table from public to walltrack schema
-- This is a non-destructive migration

-- Step 1: Create new table in walltrack schema
CREATE TABLE IF NOT EXISTS walltrack.positions (
    id TEXT PRIMARY KEY,
    signal_id TEXT,
    token_address TEXT NOT NULL,
    token_symbol TEXT,
    entry_price DECIMAL(20, 10) NOT NULL,
    entry_amount_sol DECIMAL(20, 10) NOT NULL,
    entry_amount_tokens DECIMAL(30, 10),
    entry_timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    exit_strategy_id TEXT REFERENCES exit_strategies(id),
    conviction_tier TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active',
    current_price DECIMAL(20, 10),
    current_value_sol DECIMAL(20, 10),
    unrealized_pnl_sol DECIMAL(20, 10),
    unrealized_pnl_pct DECIMAL(10, 4),
    peak_price DECIMAL(20, 10),
    peak_pnl_pct DECIMAL(10, 4),
    levels_hit JSONB DEFAULT '[]',
    exit_price DECIMAL(20, 10),
    exit_amount_sol DECIMAL(20, 10),
    exit_timestamp TIMESTAMPTZ,
    realized_pnl_sol DECIMAL(20, 10),
    realized_pnl_pct DECIMAL(10, 4),
    exit_reason TEXT,
    hold_duration_hours DECIMAL(10, 2),
    cluster_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Step 2: Copy data from public.positions
INSERT INTO walltrack.positions
SELECT * FROM public.positions
ON CONFLICT (id) DO NOTHING;

-- Step 3: Create indexes on new table
CREATE INDEX IF NOT EXISTS idx_wt_positions_status ON walltrack.positions(status);
CREATE INDEX IF NOT EXISTS idx_wt_positions_token ON walltrack.positions(token_address);
CREATE INDEX IF NOT EXISTS idx_wt_positions_signal ON walltrack.positions(signal_id);

-- Step 4: Update foreign key in orders (if exists)
-- Note: May need ALTER TABLE if constraint already exists

-- Step 5: Keep old table for backward compatibility (can drop later)
-- DROP TABLE IF EXISTS public.positions; -- DO NOT run until all code migrated
```

**Update code to use walltrack.positions:**
- `src/walltrack/data/supabase/repositories/position_repo.py`: Update table reference

## Acceptance Criteria

- [ ] V15 migration created and tested
- [ ] Data copied from public.positions to walltrack.positions
- [ ] V9 orders table foreign key works
- [ ] V10 position_price_metrics foreign key works
- [ ] Position repository updated to use walltrack schema
- [ ] Old public.positions marked for deprecation

## Files to Create/Modify

- CREATE: `migrations/V15__move_positions_schema.sql`
- MODIFY: `src/walltrack/data/supabase/repositories/position_repo.py`

## Testing

```sql
-- Verify migration
SELECT COUNT(*) FROM walltrack.positions;
SELECT COUNT(*) FROM public.positions;
-- Should be equal

-- Verify FK works
INSERT INTO walltrack.orders (id, position_id, ...)
VALUES (uuid_generate_v4(), 'existing-position-id', ...);
-- Should not fail
```

## Estimated Effort

2 hours

## Risk

- Data migration must be tested in staging first
- Rollback: Can restore from public.positions backup
