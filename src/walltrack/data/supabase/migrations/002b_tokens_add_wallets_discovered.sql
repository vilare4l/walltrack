-- Migration: 002b_tokens_add_wallets_discovered.sql
-- Date: 2025-12-30
-- Story: 3.1 - Wallet Discovery from Tokens
-- Purpose: Add wallets_discovered flag to track which tokens have been processed for wallet discovery

-- =============================================================================
-- ALTER TABLE - Add wallets_discovered column
-- =============================================================================

ALTER TABLE walltrack.tokens
ADD COLUMN IF NOT EXISTS wallets_discovered BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN walltrack.tokens.wallets_discovered IS 'TRUE if wallets have been discovered from this token (Story 3.1)';

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'walltrack'
          AND table_name = 'tokens'
          AND column_name = 'wallets_discovered'
    ) THEN
        RAISE NOTICE 'SUCCESS: wallets_discovered column added to walltrack.tokens';
    ELSE
        RAISE EXCEPTION 'FAILED: wallets_discovered column not added';
    END IF;
END $$;

-- =============================================================================
-- ROLLBACK (commented)
-- =============================================================================

-- To rollback this migration, run:
-- ALTER TABLE walltrack.tokens DROP COLUMN IF EXISTS wallets_discovered;
