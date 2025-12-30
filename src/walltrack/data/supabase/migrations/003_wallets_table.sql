-- Migration: 003_wallets_table.sql
-- Date: 2025-12-30
-- Story: 3.1 - Wallet Discovery from Tokens
-- Purpose: Create wallets table for storing discovered smart money wallets

-- =============================================================================
-- TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.wallets (
    wallet_address TEXT PRIMARY KEY,  -- Solana address, prevents duplicates
    discovery_date TIMESTAMPTZ NOT NULL DEFAULT now(),
    token_source TEXT NOT NULL REFERENCES walltrack.tokens(mint) ON DELETE CASCADE,  -- FIXED: Foreign key for referential integrity
    score NUMERIC(5,4) DEFAULT 0.0,  -- FIXED: Changed from FLOAT to avoid rounding errors (0.0000-1.0000)
    win_rate NUMERIC(5,4) DEFAULT 0.0,  -- FIXED: Changed from FLOAT (0.0000-1.0000)
    decay_status TEXT DEFAULT 'ok',  -- Values: 'ok', 'flagged', 'downgraded', 'dormant'
    is_blacklisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE walltrack.wallets IS 'Discovered smart money wallets from token holders';
COMMENT ON COLUMN walltrack.wallets.wallet_address IS 'Solana wallet address (PRIMARY KEY prevents duplicates)';
COMMENT ON COLUMN walltrack.wallets.discovery_date IS 'When this wallet was first discovered';
COMMENT ON COLUMN walltrack.wallets.token_source IS 'First token address that led to discovery (multi-token keeps FIRST)';
COMMENT ON COLUMN walltrack.wallets.score IS 'Wallet performance score (0.0-1.0, calculated in Story 3.2)';
COMMENT ON COLUMN walltrack.wallets.win_rate IS 'Win rate percentage (0.0-1.0, calculated in Story 3.2)';
COMMENT ON COLUMN walltrack.wallets.decay_status IS 'Activity status: ok, flagged, downgraded, dormant';
COMMENT ON COLUMN walltrack.wallets.is_blacklisted IS 'TRUE if wallet is blacklisted (Story 3.5)';
COMMENT ON COLUMN walltrack.wallets.created_at IS 'Record creation timestamp';
COMMENT ON COLUMN walltrack.wallets.updated_at IS 'Last modification timestamp';

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS update_wallets_updated_at ON walltrack.wallets;

-- Create trigger for auto-updating updated_at
-- (uses existing walltrack.update_updated_at_column function from 001_config.sql)
CREATE TRIGGER update_wallets_updated_at
    BEFORE UPDATE ON walltrack.wallets
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_wallets_discovery_date ON walltrack.wallets(discovery_date DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_token_source ON walltrack.wallets(token_source);  -- FIXED: Index for querying wallets by source token
CREATE INDEX IF NOT EXISTS idx_wallets_score ON walltrack.wallets(score DESC) WHERE score > 0.0;
CREATE INDEX IF NOT EXISTS idx_wallets_decay_status ON walltrack.wallets(decay_status);
CREATE INDEX IF NOT EXISTS idx_wallets_blacklisted ON walltrack.wallets(is_blacklisted) WHERE is_blacklisted = TRUE;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE walltrack.wallets ENABLE ROW LEVEL SECURITY;

-- FIXED: Anon role is READ-ONLY (security)
-- Gradio dashboard can read wallets but cannot modify/delete
DROP POLICY IF EXISTS "Anon read only wallets" ON walltrack.wallets;
CREATE POLICY "Anon read only wallets"
    ON walltrack.wallets FOR SELECT
    TO anon
    USING (true);

-- Service role has FULL access (backend operations)
DROP POLICY IF EXISTS "Service role full access to wallets" ON walltrack.wallets;
CREATE POLICY "Service role full access to wallets"
    ON walltrack.wallets FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- GRANTS
-- =============================================================================

GRANT ALL ON walltrack.wallets TO service_role;
GRANT SELECT, INSERT, UPDATE ON walltrack.wallets TO authenticated, anon;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'walltrack' AND table_name = 'wallets'
    ) THEN
        RAISE NOTICE 'SUCCESS: walltrack.wallets table created';
    ELSE
        RAISE EXCEPTION 'FAILED: walltrack.wallets table not created';
    END IF;
END $$;

-- =============================================================================
-- ROLLBACK (commented)
-- =============================================================================

-- To rollback this migration, run:
-- DROP TABLE IF EXISTS walltrack.wallets CASCADE;
