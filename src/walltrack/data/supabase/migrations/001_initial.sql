-- Initial migration for WallTrack
-- Creates all base tables in the walltrack schema

-- Create schema
CREATE SCHEMA IF NOT EXISTS walltrack;

-- Set search path
SET search_path TO walltrack, public;

-- =============================================================================
-- Config table for dynamic runtime configuration
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.config (
    key VARCHAR(100) PRIMARY KEY,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100)
);

-- Trigger for auto-updating updated_at
CREATE OR REPLACE FUNCTION walltrack.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_config_updated_at
    BEFORE UPDATE ON walltrack.config
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Default configuration values
INSERT INTO walltrack.config (key, value, description) VALUES
    ('scoring_weights', '{"wallet": 0.30, "cluster": 0.25, "token": 0.25, "context": 0.20}', 'Signal scoring factor weights'),
    ('score_threshold', '0.70', 'Minimum score for trade eligibility'),
    ('high_conviction_threshold', '0.85', 'Score threshold for high conviction trades'),
    ('drawdown_threshold_pct', '20.0', 'Drawdown % to trigger circuit breaker'),
    ('win_rate_threshold_pct', '40.0', 'Win rate % to trigger circuit breaker'),
    ('max_concurrent_positions', '5', 'Maximum concurrent open positions')
ON CONFLICT (key) DO NOTHING;

-- Index for fast lookups
CREATE INDEX IF NOT EXISTS idx_config_updated_at ON walltrack.config(updated_at);
