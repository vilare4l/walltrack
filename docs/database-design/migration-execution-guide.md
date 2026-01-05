# WallTrack Database Migration Execution Guide

**Story:** 1.1 - Database Schema Migration & Mock Data
**Date:** 2026-01-05
**Database:** PostgreSQL via Supabase (Local Docker)

## Prerequisites

- Docker and Docker Compose running
- Supabase services running (`supabase-db`, `supabase-pooler` containers)
- PostgreSQL client or Docker access

## Migration Files

All migrations are located in:
```
src/walltrack/data/supabase/migrations/
```

### Execution Order

1. **000_helper_functions.sql** - Schema and helper functions
2. **001_config_table.sql** - System configuration (singleton pattern)
3. **002_exit_strategies_table.sql** - Exit strategy templates (catalog pattern)
4. **003_wallets_table.sql** - Smart money wallet registry
5. **004_tokens_table.sql** - Token safety cache
6. **005_signals_table.sql** - Helius signal event sourcing
7. **006_orders_table.sql** - Order command log
8. **007_positions_table.sql** - Position aggregate root
9. **008_insert_mock_data.sql** - Mock data: config, exit_strategies, wallets, tokens
10. **009_insert_signals_positions_orders.sql** - Mock data: signals, positions, orders

## Execution Methods

### Method 1: Docker Exec (Recommended for Windows)

```bash
# Execute each migration file
powershell -Command "Get-Content 'C:\Users\pc\projects\walltrack\src\walltrack\data\supabase\migrations\000_helper_functions.sql' -Raw | docker exec -i supabase-db psql -U supabase_admin -d postgres"

powershell -Command "Get-Content 'C:\Users\pc\projects\walltrack\src\walltrack\data\supabase\migrations\001_config_table.sql' -Raw | docker exec -i supabase-db psql -U supabase_admin -d postgres"

# ... repeat for each migration file 002-009
```

### Method 2: Batch Execution

Create a PowerShell script `run_migrations.ps1`:

```powershell
$migrations = @(
    "000_helper_functions.sql",
    "001_config_table.sql",
    "002_exit_strategies_table.sql",
    "003_wallets_table.sql",
    "004_tokens_table.sql",
    "005_signals_table.sql",
    "006_orders_table.sql",
    "007_positions_table.sql",
    "008_insert_mock_data.sql",
    "009_insert_signals_positions_orders.sql"
)

$basePath = "C:\Users\pc\projects\walltrack\src\walltrack\data\supabase\migrations"

foreach ($migration in $migrations) {
    Write-Host "Executing: $migration" -ForegroundColor Cyan
    $filePath = Join-Path $basePath $migration
    Get-Content $filePath -Raw | docker exec -i supabase-db psql -U supabase_admin -d postgres
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✅ SUCCESS: $migration" -ForegroundColor Green
    } else {
        Write-Host "❌ FAILED: $migration" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`n✅ ALL MIGRATIONS COMPLETED SUCCESSFULLY" -ForegroundColor Green
```

Run: `powershell .\run_migrations.ps1`

## Verification Queries

### Check Table Creation

```sql
SELECT tablename
FROM pg_tables
WHERE schemaname = 'walltrack'
ORDER BY tablename;
```

Expected: 9 tables (config, exit_strategies, wallets, tokens, signals, positions, orders, circuit_breaker_events, performance)

### Check Mock Data Counts

```sql
SELECT
    'config' as table_name, COUNT(*) as row_count FROM walltrack.config
UNION ALL SELECT 'exit_strategies', COUNT(*) FROM walltrack.exit_strategies
UNION ALL SELECT 'wallets', COUNT(*) FROM walltrack.wallets
UNION ALL SELECT 'tokens', COUNT(*) FROM walltrack.tokens
UNION ALL SELECT 'signals', COUNT(*) FROM walltrack.signals
UNION ALL SELECT 'positions', COUNT(*) FROM walltrack.positions
UNION ALL SELECT 'orders', COUNT(*) FROM walltrack.orders
ORDER BY table_name;
```

Expected counts:
- config: 1
- exit_strategies: 3
- wallets: 5
- tokens: 8
- signals: 20
- positions: 12
- orders: 18

### Verify Signal Distribution

```sql
SELECT action_taken, COUNT(*) as count
FROM walltrack.signals
GROUP BY action_taken
ORDER BY action_taken;
```

Expected:
- circuit_breaker_active: 3
- ignored_sell: 3
- position_created: 10
- rejected_safety: 4

### Verify Position Status

```sql
SELECT status, COUNT(*) as count
FROM walltrack.positions
GROUP BY status
ORDER BY status;
```

Expected:
- open: 6
- closed: 6

### Verify Order Status

```sql
SELECT status, COUNT(*) as count
FROM walltrack.orders
GROUP BY status
ORDER BY status;
```

Expected:
- executed: 12
- failed: 2
- pending: 4

### Verify Foreign Key Integrity

```sql
-- Check for orphaned records
SELECT
    'Orphaned positions (no wallet)' as check_name,
    COUNT(*)
FROM walltrack.positions p
LEFT JOIN walltrack.wallets w ON p.wallet_id = w.id
WHERE w.id IS NULL
UNION ALL
SELECT
    'Orphaned positions (no token)',
    COUNT(*)
FROM walltrack.positions p
LEFT JOIN walltrack.tokens t ON p.token_id = t.id
WHERE t.id IS NULL
UNION ALL
SELECT
    'Orphaned orders (no wallet)',
    COUNT(*)
FROM walltrack.orders o
LEFT JOIN walltrack.wallets w ON o.wallet_id = w.id
WHERE w.id IS NULL
UNION ALL
SELECT
    'Orphaned orders (no token)',
    COUNT(*)
FROM walltrack.orders o
LEFT JOIN walltrack.tokens t ON o.token_id = t.id
WHERE t.id IS NULL;
```

Expected: All counts should be 0

## Rollback Procedures

Each migration file contains rollback SQL at the bottom (commented out):

```sql
-- Rollback
-- DROP TABLE IF EXISTS walltrack.table_name CASCADE;
-- DELETE FROM walltrack.table_name;
```

To rollback a specific table:
```bash
docker exec -i supabase-db psql -U supabase_admin -d postgres -c "DROP TABLE IF EXISTS walltrack.signals CASCADE;"
```

To rollback all mock data:
```bash
docker exec -i supabase-db psql -U supabase_admin -d postgres -c "
DELETE FROM walltrack.orders;
DELETE FROM walltrack.positions;
DELETE FROM walltrack.signals;
DELETE FROM walltrack.tokens;
DELETE FROM walltrack.wallets;
"
```

To rollback entire schema:
```bash
docker exec -i supabase-db psql -U supabase_admin -d postgres -c "DROP SCHEMA IF EXISTS walltrack CASCADE;"
```

## Common Issues

### Issue 1: Duplicate Key Errors

**Symptom:** `ERROR: duplicate key value violates unique constraint "wallets_address_key"`

**Cause:** Migration 008 or 009 was run multiple times

**Solution:** Delete existing mock data before re-running:
```bash
docker exec -i supabase-db psql -U supabase_admin -d postgres -c "
DELETE FROM walltrack.orders;
DELETE FROM walltrack.positions;
DELETE FROM walltrack.signals;
DELETE FROM walltrack.tokens WHERE address IN ('DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263', ...);
DELETE FROM walltrack.wallets WHERE address IN ('7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU', ...);
"
```

### Issue 2: Permission Denied

**Symptom:** `ERROR: permission denied for schema walltrack`

**Cause:** Using wrong database user

**Solution:** Always use `supabase_admin` user, not `postgres`:
```bash
# Correct:
docker exec -i supabase-db psql -U supabase_admin -d postgres

# Incorrect:
docker exec -i supabase-db psql -U postgres -d postgres
```

### Issue 3: Foreign Key Violations

**Symptom:** `ERROR: null value in column "exit_strategy_id" violates not-null constraint`

**Cause:** Exit strategies not inserted before wallets/positions

**Solution:** Run migrations in order (001, 002, 003, ...)

### Issue 4: SQL Syntax Errors in DO $$ Blocks

**Symptom:** `ERROR: syntax error at or near "wallet2_addr"`

**Cause:** PowerShell splitting DO $$ blocks incorrectly

**Solution:** Use `-Raw` flag with Get-Content:
```powershell
# Correct:
Get-Content 'file.sql' -Raw | docker exec ...

# Incorrect (breaks DO blocks):
Get-Content 'file.sql' | docker exec ...
```

## Database Connection Details

- **Host:** localhost (via Docker)
- **Port:** 5432 (via supabase-pooler)
- **Database:** postgres
- **Schema:** walltrack
- **User:** supabase_admin (NOT postgres)
- **Container:** supabase-db

## Mock Data Summary

### Wallets (5)
- 3 simulation mode (CryptoWhale #1, DegenApe Trader, HighRisk Gambler)
- 2 live mode (Proven Winner, MoonShot Hunter)
- Various exit strategies (Default, Conservative, Aggressive)

### Tokens (8)
- 4 safe tokens (BONK, WIF, MYRO, JTO) - safety_score ≥ 0.60
- 4 unsafe tokens (SCAM, RUG, PUMP, FAKE) - safety_score < 0.60

### Signals (20)
- 10 processed (position_created)
- 4 rejected (safety_score_too_low)
- 3 ignored (sell signals)
- 3 circuit breaker (various limits)

### Positions (12)
- 6 open (mix of profit, loss, breakeven states)
- 6 closed (various exit reasons: trailing_stop, stop_loss, manual, scaling_out, mirror_exit)

### Orders (18)
- 12 executed (6 entry + 6 exit)
- 4 pending (exit orders awaiting execution)
- 2 failed (with retry information)

## Security Notes

⚠️ **IMPORTANT:** These migrations include mock data for DEVELOPMENT ONLY. Do not use in production.

- Wallet addresses are fictional Solana addresses
- Transaction signatures are fake placeholders
- No real private keys or sensitive data
- Mock data should be cleared before production deployment

## Next Steps

After successful migration:

1. Verify all data with queries above
2. Test UI components (Story 1.2)
3. Implement Gradio dashboard
4. Add authentication/security layer
5. Integrate Helius webhooks (Epic 2)

---

**Last Updated:** 2026-01-05
**Story:** 1.1 - Database Schema Migration & Mock Data
**Status:** ✅ Completed
