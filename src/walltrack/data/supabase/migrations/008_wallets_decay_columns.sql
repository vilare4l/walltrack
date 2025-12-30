-- Migration: 008_wallets_decay_columns.sql
-- Date: 2025-12-30
-- Story: 3.4 - Wallet Decay Detection
-- Purpose: Add decay tracking columns to wallets table

-- =============================================================================
-- ADD COLUMNS FOR DECAY DETECTION
-- =============================================================================

-- Consecutive losses counter (AC2: Consecutive Loss Detection)
ALTER TABLE walltrack.wallets
ADD COLUMN IF NOT EXISTS consecutive_losses INTEGER DEFAULT 0;

COMMENT ON COLUMN walltrack.wallets.consecutive_losses IS 'Number of consecutive losing trades (AC2)';

-- Last activity date for dormancy detection (AC3: Dormancy Detection)
ALTER TABLE walltrack.wallets
ADD COLUMN IF NOT EXISTS last_activity_date TIMESTAMPTZ DEFAULT now();

COMMENT ON COLUMN walltrack.wallets.last_activity_date IS 'Last trade activity date for dormancy detection (AC3)';

-- Rolling window win rate (AC1: Rolling Window Decay Detection)
ALTER TABLE walltrack.wallets
ADD COLUMN IF NOT EXISTS rolling_win_rate DECIMAL(5,2);

COMMENT ON COLUMN walltrack.wallets.rolling_win_rate IS 'Win rate over most recent 20 trades (AC1), NULL if insufficient data';

-- =============================================================================
-- INDEXES FOR DECAY QUERIES
-- =============================================================================

-- Index for dormancy queries (wallets inactive for 30+ days)
CREATE INDEX IF NOT EXISTS idx_wallets_last_activity
ON walltrack.wallets(last_activity_date)
WHERE decay_status != 'dormant';

-- Index for consecutive losses queries
CREATE INDEX IF NOT EXISTS idx_wallets_consecutive_losses
ON walltrack.wallets(consecutive_losses DESC)
WHERE consecutive_losses > 0;

-- Index for rolling win rate queries (flagged wallets)
CREATE INDEX IF NOT EXISTS idx_wallets_rolling_win_rate
ON walltrack.wallets(rolling_win_rate)
WHERE rolling_win_rate IS NOT NULL;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
BEGIN
    -- Verify consecutive_losses column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'walltrack'
        AND table_name = 'wallets'
        AND column_name = 'consecutive_losses'
    ) THEN
        RAISE NOTICE 'SUCCESS: consecutive_losses column added';
    ELSE
        RAISE EXCEPTION 'FAILED: consecutive_losses column not added';
    END IF;

    -- Verify last_activity_date column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'walltrack'
        AND table_name = 'wallets'
        AND column_name = 'last_activity_date'
    ) THEN
        RAISE NOTICE 'SUCCESS: last_activity_date column added';
    ELSE
        RAISE EXCEPTION 'FAILED: last_activity_date column not added';
    END IF;

    -- Verify rolling_win_rate column exists
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'walltrack'
        AND table_name = 'wallets'
        AND column_name = 'rolling_win_rate'
    ) THEN
        RAISE NOTICE 'SUCCESS: rolling_win_rate column added';
    ELSE
        RAISE EXCEPTION 'FAILED: rolling_win_rate column not added';
    END IF;
END $$;

-- =============================================================================
-- ROLLBACK (commented)
-- =============================================================================

-- To rollback this migration, run:
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS consecutive_losses;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS last_activity_date;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS rolling_win_rate;
-- DROP INDEX IF EXISTS walltrack.idx_wallets_last_activity;
-- DROP INDEX IF EXISTS walltrack.idx_wallets_consecutive_losses;
-- DROP INDEX IF EXISTS walltrack.idx_wallets_rolling_win_rate;
