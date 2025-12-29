# Story 1.7: Database Migrations

**Status:** done
**Epic:** 1 - Foundation & Core Infrastructure
**Created:** 2025-12-29
**Sprint Artifacts:** docs/sprint-artifacts/epic-1/

---

## Story

**As a** developer,
**I want** database migrations for V2 Supabase tables,
**So that** the code written in Epic 1 can actually run against a real database.

**Context:** This story was added after Epic 1 retrospective identified a gap - code was written that uses database tables (`ConfigRepository` in Story 1.5), but no migrations were created because unit tests mocked Supabase.

---

## Acceptance Criteria

### AC1: Migration Infrastructure
- [x] Directory `src/walltrack/data/supabase/migrations/` exists
- [x] Migration naming convention: `NNN_description.sql` (e.g., `001_config.sql`)
- [x] README in migrations folder documenting how to apply

### AC2: Config Table Migration
- [x] Migration `001_config.sql` creates `config` table
- [x] Schema matches `ConfigRepository` expectations:
  - `key TEXT PRIMARY KEY`
  - `value TEXT`
  - `updated_at TIMESTAMPTZ DEFAULT NOW()`
- [x] Trigger for auto-updating `updated_at`
- [x] RLS policies for service role access

### AC3: Migration Executed
- [x] Migration applied to Supabase instance
- [x] `ConfigRepository` can read/write to real database
- [x] Integration test validates table exists

---

## Tasks / Subtasks

### Task 1: Create Migration Infrastructure (AC: 1)
- [x] 1.1 Create `src/walltrack/data/supabase/migrations/` directory
- [x] 1.2 Create `README.md` with migration instructions

### Task 2: Create Config Migration (AC: 2)
- [x] 2.1 Create `001_config.sql` with table definition
- [x] 2.2 Add updated_at trigger
- [x] 2.3 Add RLS policies

### Task 3: Execute Migration (AC: 3)
- [x] 3.1 Apply migration to Supabase (via docker exec)
- [x] 3.2 Verify table structure and insert/select
- [x] 3.3 Update story status to done

---

## Dev Notes

### Gap Identified

During Epic 1 retrospective, we identified that:
1. Story 1.5 created `ConfigRepository` that expects a `config` table
2. Unit tests pass because they mock Supabase client
3. No actual migration was created for V2
4. V1 legacy migrations exist but use `walltrack.` schema prefix

### Migration Pattern for V2

```sql
-- V2 migrations use default schema (public)
-- No schema prefix required
CREATE TABLE IF NOT EXISTS config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

### Files Created

```
src/walltrack/data/supabase/migrations/
├── README.md           # Instructions for applying migrations
└── 001_config.sql      # Config table for Story 1.5
```

### How to Apply Migrations

```bash
# Option 1: Via Supabase Dashboard
# Go to SQL Editor and paste the migration content

# Option 2: Via psql (if direct access)
psql $DATABASE_URL -f src/walltrack/data/supabase/migrations/001_config.sql

# Option 3: Via supabase CLI
supabase db push
```

---

## Technical Patterns

### Migration Template

```sql
-- Migration: NNN_description.sql
-- Created: YYYY-MM-DD
-- Purpose: Brief description

-- =============================================================================
-- TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- columns
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_table_name_updated_at
    BEFORE UPDATE ON table_name
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE table_name ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access"
    ON table_name FOR ALL
    USING (auth.role() = 'service_role');

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_table_name_column ON table_name(column);
```

---

## Previous Story Intelligence

### From Story 1.5 (Trading Wallet Connection)
- `ConfigRepository` created in `src/walltrack/data/supabase/repositories/config_repo.py`
- Uses `TABLE_NAME = "config"`
- Methods: `get_value()`, `set_value()`, `get_values()`, `delete_value()`
- Expected to store `trading_wallet_address`

### From Story 1.2 (Database Connections)
- `SupabaseClient` uses async Supabase client
- Connection tested with `SELECT 1`
- No table-level operations tested

---

## Success Criteria

**Story DONE when:**
1. Migration files exist in `src/walltrack/data/supabase/migrations/`
2. `001_config.sql` creates table matching `ConfigRepository` schema
3. Migration applied to Supabase instance
4. `ConfigRepository` can read/write successfully
5. Integration test confirms table exists

---

## Dependencies

### Story Dependencies
- Story 1.2: Database Connections (provides SupabaseClient)
- Story 1.5: Trading Wallet Connection (provides ConfigRepository)

### External Dependencies
- Supabase project access
- Database credentials in `.env`

---

_Story generated by SM Agent (Bob) - 2025-12-29_
_Mode: Hotfix - Gap identified during Epic 1 retrospective_
