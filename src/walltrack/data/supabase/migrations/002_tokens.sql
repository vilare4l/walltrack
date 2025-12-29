-- Migration: 002_tokens.sql
-- Created: 2025-12-29
-- Purpose: Token storage for token discovery and surveillance
-- Used by: TokenRepository (Story 2.1 - Token Discovery Trigger)
-- Schema: walltrack (must exist, see POSTGRES_SCHEMA in .env)

-- =============================================================================
-- TABLE DEFINITION
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    mint TEXT UNIQUE NOT NULL,
    symbol TEXT,
    name TEXT,
    price_usd NUMERIC,
    market_cap NUMERIC,
    volume_24h NUMERIC,
    liquidity_usd NUMERIC,
    age_minutes INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_checked TIMESTAMPTZ
);

COMMENT ON TABLE walltrack.tokens IS 'Discovered tokens from DexScreener and other sources';
COMMENT ON COLUMN walltrack.tokens.id IS 'Unique identifier for the token record';
COMMENT ON COLUMN walltrack.tokens.mint IS 'Solana token mint address (unique)';
COMMENT ON COLUMN walltrack.tokens.symbol IS 'Token symbol (e.g., SOL, USDC)';
COMMENT ON COLUMN walltrack.tokens.name IS 'Token name (e.g., Solana, USD Coin)';
COMMENT ON COLUMN walltrack.tokens.price_usd IS 'Current price in USD';
COMMENT ON COLUMN walltrack.tokens.market_cap IS 'Market capitalization in USD';
COMMENT ON COLUMN walltrack.tokens.volume_24h IS '24-hour trading volume in USD';
COMMENT ON COLUMN walltrack.tokens.liquidity_usd IS 'Total liquidity in USD';
COMMENT ON COLUMN walltrack.tokens.age_minutes IS 'Token age in minutes since creation';
COMMENT ON COLUMN walltrack.tokens.created_at IS 'When this record was first created';
COMMENT ON COLUMN walltrack.tokens.updated_at IS 'Last modification timestamp';
COMMENT ON COLUMN walltrack.tokens.last_checked IS 'Last time token data was refreshed from API';

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Drop existing trigger if any
DROP TRIGGER IF EXISTS update_tokens_updated_at ON walltrack.tokens;

-- Create trigger for auto-updating updated_at
-- (uses existing walltrack.update_updated_at_column function from 001_config.sql)
CREATE TRIGGER update_tokens_updated_at
    BEFORE UPDATE ON walltrack.tokens
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE walltrack.tokens ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
DROP POLICY IF EXISTS "Service role full access to tokens" ON walltrack.tokens;
CREATE POLICY "Service role full access to tokens"
    ON walltrack.tokens FOR ALL
    USING (auth.role() = 'service_role');

-- =============================================================================
-- GRANTS
-- =============================================================================

GRANT ALL ON walltrack.tokens TO service_role;
GRANT SELECT ON walltrack.tokens TO authenticated, anon;

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_tokens_mint ON walltrack.tokens(mint);
CREATE INDEX IF NOT EXISTS idx_tokens_last_checked ON walltrack.tokens(last_checked);
CREATE INDEX IF NOT EXISTS idx_tokens_created_at ON walltrack.tokens(created_at);

-- =============================================================================
-- VERIFICATION
-- =============================================================================

-- Verify table was created
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables
               WHERE table_schema = 'walltrack' AND table_name = 'tokens') THEN
        RAISE NOTICE 'SUCCESS: walltrack.tokens table created';
    ELSE
        RAISE EXCEPTION 'FAILED: walltrack.tokens table not created';
    END IF;
END $$;
