-- Migration: 004_wallets_watchlist_status.sql
-- Date: 2025-12-30
-- Story: 3.5 - Auto Watchlist Management
-- Description: Add wallet_status lifecycle and watchlist metadata to wallets table

-- Add wallet_status column with CHECK constraint
ALTER TABLE walltrack.wallets
  ADD COLUMN IF NOT EXISTS wallet_status TEXT NOT NULL DEFAULT 'discovered'
  CHECK (wallet_status IN (
    'discovered',   -- Story 3.1: Just discovered from token
    'profiled',     -- Story 3.2-3.3: Metrics calculated
    'ignored',      -- Story 3.5: Failed watchlist criteria
    'watchlisted',  -- Story 3.5: Passed watchlist criteria
    'flagged',      -- Story 3.4: Decay detected
    'removed',      -- Manual: Removed from system
    'blacklisted'   -- Manual: Permanently excluded
  ));

-- Add watchlist metadata columns
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_added_date TIMESTAMPTZ;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_score NUMERIC(5,4);  -- 0.0000 to 1.0000
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS watchlist_reason TEXT;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS manual_override BOOLEAN DEFAULT FALSE;

-- Create index on wallet_status for filtering (Epic 4 clustering, Story 3.4 decay)
CREATE INDEX IF NOT EXISTS idx_wallets_status ON walltrack.wallets(wallet_status);

-- Create partial index on watchlist_score for watchlisted wallets only
CREATE INDEX IF NOT EXISTS idx_wallets_watchlist_score
  ON walltrack.wallets(watchlist_score DESC)
  WHERE wallet_status = 'watchlisted';

-- Update existing wallets: discovered/NULL → profiled (Stories 3.1-3.3 are done)
UPDATE walltrack.wallets
SET wallet_status = 'profiled'
WHERE wallet_status IS NULL OR wallet_status = 'discovered';

-- Add comment for documentation
COMMENT ON COLUMN walltrack.wallets.wallet_status IS 'Lifecycle status: discovered → profiled → watchlisted/ignored → flagged → removed/blacklisted';
COMMENT ON COLUMN walltrack.wallets.watchlist_score IS 'Composite score (0.0000-1.0000) from watchlist evaluation criteria';
COMMENT ON COLUMN walltrack.wallets.watchlist_reason IS 'Why wallet was watchlisted or ignored (e.g., "Failed: win_rate < 0.70")';
COMMENT ON COLUMN walltrack.wallets.manual_override IS 'True if status was set manually (not by automatic evaluation)';

-- Verification queries (Story 3.5 Issue #7)
-- 1. Verify columns exist
-- SELECT column_name, data_type, is_nullable, column_default
-- FROM information_schema.columns
-- WHERE table_schema = 'walltrack' AND table_name = 'wallets'
--   AND column_name IN ('wallet_status', 'watchlist_score', 'watchlist_reason', 'watchlist_added_date', 'manual_override')
-- ORDER BY column_name;
-- Expected: 5 rows showing all watchlist columns

-- 2. Verify indexes exist
-- SELECT indexname, indexdef
-- FROM pg_indexes
-- WHERE schemaname = 'walltrack' AND tablename = 'wallets'
--   AND indexname IN ('idx_wallets_status', 'idx_wallets_watchlist_score');
-- Expected: 2 rows showing both indexes

-- 3. Verify CHECK constraint exists
-- SELECT conname, pg_get_constraintdef(oid)
-- FROM pg_constraint
-- WHERE conrelid = 'walltrack.wallets'::regclass
--   AND conname LIKE '%wallet_status%';
-- Expected: 1 row showing wallet_status CHECK constraint

-- 4. Verify wallet status distribution
-- SELECT wallet_status, COUNT(*) FROM walltrack.wallets GROUP BY wallet_status ORDER BY COUNT(*) DESC;
-- Expected: Counts by status (should see 'profiled', 'watchlisted', 'ignored', etc.)

-- 5. Verify watchlisted wallets sample
-- SELECT wallet_address, wallet_status, watchlist_score, watchlist_reason, manual_override
-- FROM walltrack.wallets WHERE wallet_status = 'watchlisted' LIMIT 5;
-- Expected: Up to 5 watchlisted wallets with scores and reasons

-- Rollback (commented)
-- DROP INDEX IF EXISTS idx_wallets_status;
-- DROP INDEX IF EXISTS idx_wallets_watchlist_score;
-- ALTER TABLE walltrack.wallets DROP COLUMN wallet_status;
-- ALTER TABLE walltrack.wallets DROP COLUMN watchlist_added_date;
-- ALTER TABLE walltrack.wallets DROP COLUMN watchlist_score;
-- ALTER TABLE walltrack.wallets DROP COLUMN watchlist_reason;
-- ALTER TABLE walltrack.wallets DROP COLUMN manual_override;
