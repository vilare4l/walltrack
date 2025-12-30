-- Migration: 009_decay_events_table.sql
-- Date: 2025-12-30
-- Story: 3.4 - Wallet Decay Detection
-- Purpose: Create decay_events table for logging decay status changes

-- =============================================================================
-- TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.decay_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL REFERENCES walltrack.wallets(wallet_address) ON DELETE CASCADE,
    event_type TEXT NOT NULL CHECK (event_type IN ('decay_detected', 'recovery', 'consecutive_losses', 'dormancy')),
    rolling_win_rate DECIMAL(5,2),  -- Win rate at time of event (0.00 to 1.00)
    lifetime_win_rate DECIMAL(5,2),  -- Overall win rate
    consecutive_losses INTEGER DEFAULT 0,
    score_before DECIMAL(5,4),  -- Score before event
    score_after DECIMAL(5,4),  -- Score after event
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

COMMENT ON TABLE walltrack.decay_events IS 'Logs wallet decay status changes and score adjustments (AC4)';
COMMENT ON COLUMN walltrack.decay_events.wallet_address IS 'Wallet that experienced decay event';
COMMENT ON COLUMN walltrack.decay_events.event_type IS 'Type: decay_detected, recovery, consecutive_losses, dormancy';
COMMENT ON COLUMN walltrack.decay_events.rolling_win_rate IS 'Win rate over most recent 20 trades at time of event';
COMMENT ON COLUMN walltrack.decay_events.lifetime_win_rate IS 'Overall win rate (all trades)';
COMMENT ON COLUMN walltrack.decay_events.consecutive_losses IS 'Number of consecutive losses at time of event';
COMMENT ON COLUMN walltrack.decay_events.score_before IS 'Wallet score before adjustment';
COMMENT ON COLUMN walltrack.decay_events.score_after IS 'Wallet score after adjustment';
COMMENT ON COLUMN walltrack.decay_events.created_at IS 'When the decay event occurred';

-- =============================================================================
-- INDEXES
-- =============================================================================

-- Index for querying events by wallet (most recent first)
CREATE INDEX IF NOT EXISTS idx_decay_events_wallet
ON walltrack.decay_events(wallet_address, created_at DESC);

-- Index for querying events by type (most recent first)
CREATE INDEX IF NOT EXISTS idx_decay_events_type
ON walltrack.decay_events(event_type, created_at DESC);

-- Index for querying recent events across all wallets
CREATE INDEX IF NOT EXISTS idx_decay_events_created_at
ON walltrack.decay_events(created_at DESC);

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE walltrack.decay_events ENABLE ROW LEVEL SECURITY;

-- Anon role can INSERT (for DecayDetector service) and SELECT (for dashboard)
-- Note: DELETE/UPDATE still blocked for security
DROP POLICY IF EXISTS "Anon can insert and select decay_events" ON walltrack.decay_events;
CREATE POLICY "Anon can insert and select decay_events"
    ON walltrack.decay_events FOR ALL
    TO anon
    USING (true)
    WITH CHECK (true);

-- Service role has FULL access (backend operations)
DROP POLICY IF EXISTS "Service role full access to decay_events" ON walltrack.decay_events;
CREATE POLICY "Service role full access to decay_events"
    ON walltrack.decay_events FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================================================
-- GRANTS
-- =============================================================================

GRANT ALL ON walltrack.decay_events TO service_role;
GRANT SELECT, INSERT ON walltrack.decay_events TO authenticated, anon;

-- =============================================================================
-- VERIFICATION
-- =============================================================================

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'walltrack' AND table_name = 'decay_events'
    ) THEN
        RAISE NOTICE 'SUCCESS: walltrack.decay_events table created';
    ELSE
        RAISE EXCEPTION 'FAILED: walltrack.decay_events table not created';
    END IF;
END $$;

-- =============================================================================
-- ROLLBACK (commented)
-- =============================================================================

-- To rollback this migration, run:
-- DROP TABLE IF EXISTS walltrack.decay_events CASCADE;
