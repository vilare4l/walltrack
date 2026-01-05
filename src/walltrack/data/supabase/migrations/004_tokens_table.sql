-- ============================================================================
-- Migration: 004_tokens_table.sql
-- Description: Create tokens table (read-through cache)
-- Date: 2025-01-05
-- Pattern: Read-Through Cache
-- Dependencies: None
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    address TEXT NOT NULL UNIQUE,
    symbol TEXT,
    name TEXT,

    -- Safety Score
    safety_score NUMERIC(3,2),
    liquidity_usd NUMERIC(12,2),
    holder_distribution_top_10_percent NUMERIC(5,2),
    contract_analysis_score NUMERIC(3,2),
    age_hours INTEGER,

    -- Safety Checks (pre-calculated booleans)
    liquidity_check_passed BOOLEAN,
    holder_distribution_check_passed BOOLEAN,
    contract_check_passed BOOLEAN,
    age_check_passed BOOLEAN,

    -- Analysis Metadata
    last_analyzed_at TIMESTAMPTZ,
    analysis_source TEXT,  -- 'rugcheck', 'helius', 'dexscreener'
    analysis_error TEXT,

    -- Blacklist
    is_blacklisted BOOLEAN NOT NULL DEFAULT false,
    blacklist_reason TEXT,
    blacklisted_at TIMESTAMPTZ,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE walltrack.tokens IS
'Read-through cache for token safety analysis (RugCheck, Helius, DexScreener). TTL: 1 hour.';

COMMENT ON COLUMN walltrack.tokens.safety_score IS
'Aggregated safety score 0-1 (ex: 0.75 = 75%). Formula: AVG(liquidity_check + holder_check + contract_check + age_check).';

COMMENT ON COLUMN walltrack.tokens.last_analyzed_at IS
'Last analysis timestamp. TTL: Re-fetch if > 1 hour old.';

COMMENT ON COLUMN walltrack.tokens.is_blacklisted IS
'Permanently banned token (confirmed rug). Immutable once set.';

-- Indexes
CREATE INDEX idx_tokens_address ON walltrack.tokens(address);
CREATE INDEX idx_tokens_last_analyzed ON walltrack.tokens(last_analyzed_at);
CREATE INDEX idx_tokens_blacklisted ON walltrack.tokens(is_blacklisted) WHERE is_blacklisted = true;
CREATE INDEX idx_tokens_safety_checks ON walltrack.tokens(liquidity_check_passed, holder_distribution_check_passed, contract_check_passed);

-- Triggers
CREATE TRIGGER tokens_updated_at
    BEFORE UPDATE ON walltrack.tokens
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Rollback
-- DROP TABLE IF NOT EXISTS walltrack.tokens CASCADE;
