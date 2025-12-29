-- Migration: 001_config.sql
-- Created: 2025-12-29
-- Purpose: Key-value configuration storage for WallTrack V2
-- Used by: ConfigRepository (Story 1.5 - Trading Wallet Connection)
-- Schema: walltrack (must exist, see POSTGRES_SCHEMA in .env)

-- =============================================================================
-- PREREQUISITES
-- =============================================================================

-- Ensure walltrack schema exists (should be created by Supabase setup)
-- CREATE SCHEMA IF NOT EXISTS walltrack;

-- Grant schema access (run as supabase_admin)
GRANT USAGE ON SCHEMA walltrack TO service_role, authenticated, anon;

-- =============================================================================
-- TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.config (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE walltrack.config IS 'Key-value store for dynamic runtime configuration';
COMMENT ON COLUMN walltrack.config.key IS 'Unique configuration key (e.g., trading_wallet_address)';
COMMENT ON COLUMN walltrack.config.value IS 'Configuration value as text (JSON for complex values)';
COMMENT ON COLUMN walltrack.config.updated_at IS 'Last modification timestamp';

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Create the trigger function if it doesn't exist
CREATE OR REPLACE FUNCTION walltrack.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS update_config_updated_at ON walltrack.config;

-- Create trigger for auto-updating updated_at
CREATE TRIGGER update_config_updated_at
    BEFORE UPDATE ON walltrack.config
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE walltrack.config ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
DROP POLICY IF EXISTS "Service role full access to config" ON walltrack.config;
CREATE POLICY "Service role full access to config"
    ON walltrack.config FOR ALL
    USING (auth.role() = 'service_role');

-- =============================================================================
-- GRANTS
-- =============================================================================

GRANT ALL ON walltrack.config TO service_role;
GRANT SELECT ON walltrack.config TO authenticated, anon;

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_config_updated_at ON walltrack.config(updated_at);

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify table was created
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'walltrack' AND table_name = 'config') THEN
        RAISE NOTICE 'SUCCESS: walltrack.config table created';
    ELSE
        RAISE EXCEPTION 'FAILED: walltrack.config table not created';
    END IF;
END $$;
