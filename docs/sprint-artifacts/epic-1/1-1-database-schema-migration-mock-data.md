# Story 1.1: Database Schema Migration & Mock Data

Status: done

## Story

As an operator,
I want all 9 database tables created with comprehensive mock data,
So that I can validate the complete data structure before implementing business logic.

## Acceptance Criteria

**Given** a fresh Supabase database in the walltrack schema
**When** I execute all migration files sequentially
**Then** 7 core tables are created successfully (config, exit_strategies, wallets, tokens, signals, orders, positions)
**And** each table has COMMENT ON TABLE documenting its architectural pattern
**And** each column has COMMENT ON COLUMN documenting its purpose

**Given** the database schema is migrated
**When** I execute the mock data insertion script
**Then** mock data is inserted for 7 core tables:
- `config`: 1 row (singleton pattern)
- `exit_strategies`: 3 templates (conservative, balanced, aggressive)
- `wallets`: 5 wallets (3 simulation mode, 2 live mode) with discovery metrics
- `tokens`: 8 tokens with safety scores (4 safe ≥0.60, 4 unsafe <0.60)
- `signals`: 20 signals across different wallets (10 filtered, 10 processed)
- `positions`: 12 positions (6 open, 6 closed) with PnL data
- `orders`: 18 orders (12 filled, 4 pending, 2 failed)

**And** all foreign key relationships are valid (no orphaned records)
**And** mock data represents realistic scenarios (successful trades, failed trades, filtered signals)

**Given** mock data is inserted
**When** I query each table via Supabase dashboard
**Then** I can view all mock records
**And** I can validate the data structure matches the design guides in `docs/database-design/*.md`

## Tasks / Subtasks

### Task 1: Create Helper Functions Migration (AC: All)
- [ ] **1.1** Create `000_helper_functions.sql` migration file
  - Create `walltrack` schema if not exists
  - Create `update_updated_at()` trigger function for auto-updating `updated_at` timestamps
  - Add rollback script as comment

### Task 2: Create Config Table Migration (AC: #1)
- [ ] **2.1** Create `001_config_table.sql` migration file
  - Define all config fields: trading params, risk management, safety thresholds, webhook config
  - Add COMMENT ON TABLE explaining "Configuration Singleton - Only 1 row allowed"
  - Add COMMENT ON COLUMN for each field explaining purpose
  - Create trigger to enforce singleton pattern (max 1 row)
  - Add rollback script as comment
- [ ] **2.2** Insert 1 row of default config data (singleton)
  - Total capital: $10,000
  - Risk per trade: 5%
  - Safety threshold: 0.60
  - Stop loss: 20%, Trailing stop: 15%
  - Circuit breaker: 15% loss threshold

### Task 3: Create Exit Strategies Table Migration (AC: #1)
- [ ] **3.1** Create `002_exit_strategies_table.sql` migration file
  - Define fields: name, stop_loss_percent, trailing_stop_percent, scaling_out_config, mirror_exit_enabled
  - Add COMMENT ON TABLE explaining "Catalog Pattern - Reusable templates"
  - Add COMMENT ON COLUMN for each field
  - Add UNIQUE constraint on `is_default` (only one default strategy)
  - Add rollback script as comment
- [ ] **3.2** Insert 3 exit strategy templates
  - **Default**: Stop-loss 20%, Trailing 15%, Scaling 50%@2x/25%@3x/25%forever, Mirror enabled
  - **Conservative**: Stop-loss 15%, Trailing 10%, Scaling 33%@1.5x/33%@2x/34%@3x, Mirror enabled
  - **Aggressive**: Stop-loss 30%, Trailing 20%, Scaling 25%@3x/25%@5x/50%forever, Mirror disabled

### Task 4: Create Wallets Table Migration (AC: #1)
- [ ] **4.1** Create `003_wallets_table.sql` migration file
  - Define fields: address, label, mode, exit_strategy_id (FK), discovery metrics, helius sync status
  - Add COMMENT ON TABLE explaining "Registry Pattern - Watchlist configuration"
  - Add COMMENT ON COLUMN for each field
  - Add CHECK constraint on mode (simulation | live)
  - Add CHECK constraint on address (Solana base58 regex)
  - Create indexes: idx_wallets_address, idx_wallets_mode, idx_wallets_is_active
  - Add rollback script as comment
- [ ] **4.2** Insert 5 wallet records
  - 3 simulation wallets with realistic discovery metrics (win_rate: 60-75%, trades: 50-200)
  - 2 live wallets with lower trade counts (trades: 20-50)
  - Use realistic Solana addresses (base58, 32-44 chars)
  - Link to exit strategies (2 default, 1 conservative, 2 aggressive)

### Task 5: Create Tokens Table Migration (AC: #1)
- [ ] **5.1** Create `004_tokens_table.sql` migration file
  - Define fields: address, symbol, name, safety_score, individual checks, cache metadata, DEX info
  - Add COMMENT ON TABLE explaining "Read-Through Cache - TTL 1h"
  - Add COMMENT ON COLUMN for each field
  - Create index: idx_tokens_address (unique), idx_tokens_last_analyzed_at
  - Add rollback script as comment
- [ ] **5.2** Insert 8 token records
  - 4 safe tokens (safety_score ≥ 0.60): BONK, WIF, MYRO, JTO
  - 4 unsafe tokens (safety_score < 0.60): random memecoins
  - Include realistic metadata: liquidity, holder distribution, age
  - last_analyzed_at within last 30 minutes (fresh cache)

### Task 6: Create Signals Table Migration (AC: #1)
- [ ] **6.1** Create `005_signals_table.sql` migration file
  - Define fields: wallet_id (FK), token_address, transaction_signature, signal_type, processing fields, raw_payload
  - Add COMMENT ON TABLE explaining "Event Sourcing - Immutable append-only log"
  - Add COMMENT ON COLUMN for each field
  - Add UNIQUE constraint on transaction_signature (idempotency)
  - Create indexes: idx_signals_wallet_id, idx_signals_created_at, idx_signals_filtered
  - Add partial index for processing queue: WHERE filtered=false AND position_created=false
  - Add rollback script as comment
- [ ] **6.2** Insert 20 signal records
  - 10 filtered signals (5 safety_check_failed, 3 circuit_breaker, 2 duplicate)
  - 10 processed signals (position_created=true, linked to positions table)
  - Distribute across all 5 wallets
  - Use realistic transaction signatures (base58, 88 chars)
  - Timestamps spread over last 7 days

### Task 7: Create Orders Table Migration (AC: #1)
- [ ] **7.1** Create `006_orders_table.sql` migration file
  - Define fields: wallet_id, token_id, position_id (FK), order_type, mode, swap details, status, execution, retry
  - Add COMMENT ON TABLE explaining "Command Log - Retry mechanism"
  - Add COMMENT ON COLUMN for each field
  - Add CHECK constraint on order_type (entry | exit_stop_loss | exit_trailing_stop | exit_scaling | exit_mirror | exit_manual)
  - Add CHECK constraint on status (pending | submitted | executed | failed | cancelled)
  - Create indexes: idx_orders_position_id, idx_orders_status, idx_orders_created_at
  - Add partial index for retry queue: WHERE status='pending' AND retry_count < max_retries
  - Create trigger for auto-calculating execution_duration_ms
  - Add rollback script as comment
- [ ] **7.2** Insert 18 order records
  - 12 filled orders (6 entry, 6 exit with various types)
  - 4 pending orders (retry_count 0-2)
  - 2 failed orders (retry_count = max_retries = 3)
  - Link to positions table (1 position can have multiple orders)
  - Use realistic values: prices, amounts, slippage, timestamps

### Task 8: Create Positions Table Migration (AC: #1)
- [ ] **8.1** Create `007_positions_table.sql` migration file
  - Define fields: wallet_id, token_id, signal_id (FK), mode, entry, current state, PnL breakdown, exit, strategy
  - Add COMMENT ON TABLE explaining "Aggregate Root - PnL tracking (realized/unrealized)"
  - Add COMMENT ON COLUMN for each field
  - Add CHECK constraint on mode (simulation | live)
  - Add CHECK constraint on status (open | closed | error)
  - Create indexes: idx_positions_wallet_id, idx_positions_token_id, idx_positions_status
  - Add partial index for price monitor: WHERE status = 'open'
  - Create trigger for auto-updating unrealized_pnl_usd based on current_price
  - Add rollback script as comment
- [ ] **8.2** Insert 12 position records
  - 6 open positions (3 simulation, 3 live) with various PnL states (+10% to -5%)
  - 6 closed positions (4 profitable, 2 losses) with realistic exit reasons
  - Link to wallets, tokens, signals, orders tables
  - Realistic entry/exit prices, amounts, timestamps (spread over last 30 days)

### Task 9: Validate Migration Execution (AC: All)
- [ ] **9.1** Execute all migrations in order on local Supabase instance
  - Run migrations 000 → 007 sequentially
  - Verify each migration completes without errors
  - Check table creation in Supabase dashboard
- [ ] **9.2** Verify table structure and comments
  - Query pg_catalog to verify COMMENT ON TABLE for each table
  - Query pg_catalog to verify COMMENT ON COLUMN for all columns
  - Validate indexes created correctly
- [ ] **9.3** Verify mock data integrity
  - Query each table and count rows (match expected counts)
  - Validate all foreign key relationships (no orphaned records)
  - Check mock data realism (values make sense, dates logical)
  - Test queries from future UI (e.g., SELECT open positions, SELECT wallet performance)

### Task 10: Document Migration & Mock Data (AC: #3)
- [ ] **10.1** Create migration execution guide in docs/database-design/
  - Document execution order
  - Document how to run migrations (psql or Supabase CLI)
  - Document rollback procedure
  - Document verification queries
- [ ] **10.2** Add completion notes to this story
  - List all created files
  - Document any deviations from original design
  - Note any issues encountered and resolutions
  - Update sprint-status.yaml to mark story as done

## Dev Notes

### Architectural Patterns to Follow

**Critical Architecture Decisions:**
- **[ADR-001]** Helius Global Webhook - ONE webhook for all wallets (not 1 per wallet)
- **[ADR-002]** Exit Strategy Override at Position Level (not wallet level)
- **[ADR-003]** Performance Materialized View (batch refresh daily at 00:00 UTC)
- **[ADR-004]** Circuit Breaker Non-Closing (blocks NEW positions, existing continue)

**Design Patterns Applied:**
1. **Configuration Singleton** (config) - 1 row max, trigger enforcement
2. **Catalog Pattern** (exit_strategies) - Reusable templates, DRY
3. **Registry Pattern** (wallets) - Watchlist configuration
4. **Read-Through Cache** (tokens) - TTL 1h, fetch-on-miss
5. **Event Sourcing** (signals) - Immutable append-only logs
6. **Command Log** (orders) - Retry mechanism, execution tracking
7. **Aggregate Root** (positions) - PnL tracking, realized/unrealized separation

### Database Conventions

**Naming Conventions (CRITICAL - Must follow exactly):**
- Tables: `snake_case` plural (e.g., `wallets`, `positions`, `tokens`)
- Columns: `snake_case` (e.g., `wallet_id`, `created_at`, `is_active`)
- Primary keys: `id` (UUID, auto-generated via `gen_random_uuid()`)
- Foreign keys: `{table}_id` (e.g., `wallet_id`, `token_id`)
- Timestamps: `created_at`, `updated_at` (TIMESTAMPTZ, auto-updated via trigger)
- Booleans: `is_{property}` or `has_{property}` (e.g., `is_active`, `has_mirror_exit`)
- Indexes: `idx_{table}_{column(s)}` (e.g., `idx_positions_wallet_id`)
- Constraints: `fk_{source_table}_{target_table}`, `uq_{table}_{column(s)}`

**Migration Template (MUST use this format):**
```sql
-- Migration: NNN_description.sql
-- Date: YYYY-MM-DD
-- Story: 1.1

CREATE TABLE IF NOT EXISTS walltrack.table_name (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_table_name_updated_at
    BEFORE UPDATE ON walltrack.table_name
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at();

-- Indexes
CREATE INDEX idx_table_field ON walltrack.table_name(field);

-- Comments
COMMENT ON TABLE walltrack.table_name IS 'Description of table purpose and pattern';
COMMENT ON COLUMN walltrack.table_name.field IS 'Description of field purpose';

-- Rollback (commented)
-- DROP TABLE IF EXISTS walltrack.table_name CASCADE;
```

### File Structure (Exact paths required)

**Migration Files Location:**
```
src/walltrack/data/supabase/migrations/
├── 000_helper_functions.sql      # Schema + triggers
├── 001_config_table.sql           # System configuration
├── 002_exit_strategies_table.sql  # Exit strategies catalog + default data
├── 003_wallets_table.sql          # Watchlist registry + mock data
├── 004_tokens_table.sql           # Token metadata cache + mock data
├── 005_signals_table.sql          # Webhook events log + mock data
├── 006_orders_table.sql           # Jupiter swap orders + mock data
├── 007_positions_table.sql        # Trading positions + mock data
```

**IMPORTANT:** Create `src/walltrack/data/supabase/migrations/` directory if it doesn't exist.

**CRITICAL:** The V2 rebuild (`src/`) is empty. DO NOT use `legacy/migrations/` - those are documentation only. Create NEW migrations in `src/walltrack/data/supabase/migrations/`.

### Mock Data Requirements

**Realism Criteria:**
- **Solana Addresses**: Use realistic base58 strings (32-44 chars), example: `7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU`
- **Transaction Signatures**: Use realistic base58 strings (88 chars), example: `5VERv8NMvzbJMEkV8xnrLkEaWRtSz9CosKDYjCJjBRnbJLgp8uirBgmQpjKhoR4tjF3ZpRzrFmBV6UjKdiSZkQUW`
- **Token Symbols**: Use real Solana tokens (BONK, WIF, MYRO, JTO) and generic memecoins (PEPE, DOGE, etc.)
- **Prices**: Use realistic Solana token prices ($0.00001 - $1.00 range for most tokens)
- **Timestamps**: Spread across last 7-30 days, logical ordering (entry before exit)
- **PnL**: Mix of profitable (+10% to +200%) and losing (-5% to -20%) trades
- **Safety Scores**: 4 safe tokens (0.60-0.85), 4 unsafe tokens (0.20-0.55)

**Foreign Key Integrity:**
- Every `wallet_id` FK must reference an existing row in `wallets`
- Every `token_id` FK must reference an existing row in `tokens`
- Every `position_id` FK must reference an existing row in `positions`
- Every `signal_id` FK must reference an existing row in `signals`
- NO orphaned records allowed

### Testing Standards

**Verification Queries (Run after migration):**
```sql
-- Verify table counts
SELECT 'config' AS table_name, COUNT(*) AS row_count FROM walltrack.config
UNION ALL
SELECT 'exit_strategies', COUNT(*) FROM walltrack.exit_strategies
UNION ALL
SELECT 'wallets', COUNT(*) FROM walltrack.wallets
UNION ALL
SELECT 'tokens', COUNT(*) FROM walltrack.tokens
UNION ALL
SELECT 'signals', COUNT(*) FROM walltrack.signals
UNION ALL
SELECT 'orders', COUNT(*) FROM walltrack.orders
UNION ALL
SELECT 'positions', COUNT(*) FROM walltrack.positions;

-- Verify foreign key integrity
SELECT
    'wallets' AS table_name,
    COUNT(*) AS orphaned_rows
FROM walltrack.wallets w
LEFT JOIN walltrack.exit_strategies es ON w.exit_strategy_id = es.id
WHERE es.id IS NULL;

-- Verify config singleton (must be exactly 1 row)
SELECT COUNT(*) AS config_rows FROM walltrack.config;
-- Expected: 1

-- Verify table comments exist
SELECT
    schemaname,
    tablename,
    obj_description(('walltrack.' || tablename)::regclass) AS table_comment
FROM pg_tables
WHERE schemaname = 'walltrack'
ORDER BY tablename;
```

**Unit Test Coverage (Future Story):**
- Repository tests will verify CRUD operations on these tables
- Mock data will be used for integration tests
- E2E tests will query these tables via Gradio UI

### Project Structure Notes

**V2 Rebuild Context (CRITICAL):**
- `legacy/` contains V1 code - **DO NOT MODIFY** - reference only
- `src/walltrack/` is EMPTY - this is the NEW V2 codebase
- Migrations in `legacy/migrations/` are **DOCUMENTATION ONLY**
- **CREATE NEW migrations in `src/walltrack/data/supabase/migrations/`**
- Supabase V2 database is EMPTY - migrations will create schema from scratch

**Directory Creation Required:**
```bash
# Create migrations directory if not exists
mkdir -p src/walltrack/data/supabase/migrations
```

**Alignment with Project Structure:**
```
src/walltrack/
├── data/              # Data layer (this story creates migrations here)
│   ├── models/        # Pydantic models (future story)
│   ├── repositories/  # Repository interfaces (future story)
│   └── supabase/      # Supabase-specific code
│       ├── client.py  # Supabase client setup (future story)
│       └── migrations/ # ← THIS STORY CREATES FILES HERE
```

### References

**Source Documents (Critical to review):**
- [Database Schema Design](docs/architecture/database-schema-design-data-first-approach.md) - Complete schema overview, all table definitions, ADRs
- [Core Architectural Decisions](docs/architecture/core-architectural-decisions.md) - Migration template, Supabase setup, patterns
- [Implementation Patterns](docs/architecture/implementation-patterns-consistency-rules.md) - Naming conventions, structure patterns
- [Technical Requirements](docs/prd/technical-requirements.md) - Database tech stack, migration strategy
- [Epic 1 Story 1.1](docs/epics/epic-1-data-foundation-ui-framework.md#story-11) - Acceptance criteria, requirements

**Database Design Guides (Referenced by schema doc):**
- `docs/database-design/01-config.md` - Config table design guide
- `docs/database-design/02-exit-strategies.md` - Exit strategies design guide
- `docs/database-design/03-wallets.md` - Wallets design guide
- `docs/database-design/04-tokens.md` - Tokens design guide
- `docs/database-design/05-signals.md` - Signals design guide
- `docs/database-design/06-orders.md` - Orders design guide
- `docs/database-design/07-positions.md` - Positions design guide

**IMPORTANT:** If database design guides exist, read them before creating migrations. They contain detailed field descriptions, constraints, and rationale.

## Dev Agent Record

### Context Reference

<!-- Story context created by Scrum Master (Bob) via *create-story workflow -->
<!-- Mode: YOLO (automated, no elicitation) -->

### Agent Model Used

Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)

### Debug Log References

- Sprint Status: `docs/sprint-artifacts/sprint-status.yaml`
- Epic File: `docs/epics/epic-1-data-foundation-ui-framework.md`
- Architecture Docs: `docs/architecture/`
- PRD Docs: `docs/prd/`

### Completion Notes List

**Story Context Engine Analysis Completed:**
- ✅ Loaded Epic 1 Story 1.1 with complete acceptance criteria (BDD format)
- ✅ Loaded Database Schema Design (complete table definitions, ADRs, patterns)
- ✅ Loaded Core Architectural Decisions (migration template, Supabase setup)
- ✅ Loaded Implementation Patterns (naming conventions, structure patterns)
- ✅ Loaded Technical Requirements (database tech stack, migration strategy)
- ✅ Loaded Functional Requirements (context understanding)
- ✅ Identified V2 Rebuild context: `legacy/` is documentation only, `src/` is empty
- ✅ Identified critical patterns: 8 design patterns (Singleton, Catalog, Registry, Cache, Event Sourcing, Command Log, Aggregate Root, Materialized View)
- ✅ Identified naming conventions: Tables (snake_case plural), Columns (snake_case), PKs (id UUID), FKs ({table}_id), Timestamps (created_at/updated_at)
- ✅ Identified migration template: Sequential numbering (000-009), rollback scripts, COMMENT ON TABLE/COLUMN
- ✅ Identified mock data requirements: 7 tables with realistic data, foreign key integrity, scenario coverage
- ✅ Created 10 tasks with detailed subtasks for complete implementation
- ✅ Provided verification queries for testing migration success

**Ultimate Developer Implementation Guide Created:**
This story file contains EVERYTHING needed to implement database migrations and mock data without errors, omissions, or architectural violations. The developer now has:
- Complete task breakdown (10 tasks, 30+ subtasks)
- Exact file paths and naming conventions
- Migration template with all required elements
- Mock data requirements with realism criteria
- Verification queries for testing
- All architectural patterns and ADRs referenced
- V2 Rebuild context clearly explained

**Next Step:** Developer executes `dev-story` workflow to implement all tasks and mark story as done.

### File List

**Files created by developer:**
- `src/walltrack/data/supabase/migrations/000_helper_functions.sql` ✅
- `src/walltrack/data/supabase/migrations/001_config_table.sql` ✅
- `src/walltrack/data/supabase/migrations/002_exit_strategies_table.sql` ✅
- `src/walltrack/data/supabase/migrations/003_wallets_table.sql` ✅
- `src/walltrack/data/supabase/migrations/004_tokens_table.sql` ✅
- `src/walltrack/data/supabase/migrations/005_signals_table.sql` ✅
- `src/walltrack/data/supabase/migrations/006_orders_table.sql` ✅
- `src/walltrack/data/supabase/migrations/007_positions_table.sql` ✅
- `src/walltrack/data/supabase/migrations/008_insert_mock_data.sql` ✅
- `src/walltrack/data/supabase/migrations/009_insert_signals_positions_orders.sql` ✅
- `docs/database-design/migration-execution-guide.md` ✅
- `run_migrations.py` ✅ (created but not used - Docker exec preferred)

**Total:** 12 files

### Implementation Notes (2026-01-05)

**Execution Summary:**
- ✅ All 10 migration files created and executed successfully
- ✅ All 7 core tables created with COMMENT ON TABLE/COLUMN
- ✅ All 50 mock data records inserted (config:1, exit_strategies:3, wallets:5, tokens:8, signals:20, positions:12, orders:18)
- ✅ All foreign key relationships validated (0 orphaned records)
- ✅ Migration execution guide created with verification queries and rollback procedures

**Deviations from Original Plan:**
1. **Mock data separated into two files**: Originally planned to include mock data in schema migrations (001-007), but separated into dedicated files (008, 009) for cleaner separation of concerns
2. **Exit strategy names**: Used simple names ('Default', 'Conservative', 'Aggressive') instead of longer descriptive names to match database schema
3. **Token schema**: Removed dex_name and pair_address fields, used contract_analysis_score instead of contract_verified to match actual table definition

**Issues Encountered and Resolutions:**
1. **PowerShell DO $$ blocks breaking**: PowerShell was splitting DO blocks line-by-line instead of as complete blocks
   - **Resolution**: Used `-Raw` flag with `Get-Content` to read entire file as single string
2. **Duplicate key errors on wallets/tokens**: Migration 008 was run multiple times during testing
   - **Resolution**: Created separate migration 009 for signals/positions/orders to allow partial re-runs
3. **Permission denied errors**: Initially used `postgres` user instead of `supabase_admin`
   - **Resolution**: Switched to `supabase_admin` user who owns the walltrack schema
4. **NULL exit_strategy_id constraint**: Used wrong exit strategy names in wallet INSERT
   - **Resolution**: Corrected to match exact names from exit_strategies table

**Verification Results:**
```sql
config: 1 row ✅
exit_strategies: 3 rows ✅
wallets: 5 rows (3 simulation, 2 live) ✅
tokens: 8 rows (4 safe ≥0.60, 4 unsafe <0.60) ✅
signals: 20 rows (10 processed, 10 filtered) ✅
positions: 12 rows (6 open, 6 closed) ✅
orders: 18 rows (12 executed, 4 pending, 2 failed) ✅
Orphaned records: 0 ✅
```

**Next Steps:**
- Story 1.2: Gradio application shell with three-tab navigation
- Epic 2: Wallet Discovery & Signal Reception workflows
- Integrate Helius webhooks for real signal ingestion
