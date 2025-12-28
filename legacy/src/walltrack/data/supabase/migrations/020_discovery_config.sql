-- Discovery configuration table
-- Stores scheduler settings for automatic discovery runs

CREATE TABLE IF NOT EXISTS discovery_config (
    id INTEGER PRIMARY KEY DEFAULT 1,
    enabled BOOLEAN DEFAULT TRUE,
    schedule_hours INTEGER DEFAULT 6,

    -- Default parameters for scheduled runs
    min_price_change_pct DECIMAL(5,2) DEFAULT 100.0,
    min_volume_usd DECIMAL(15,2) DEFAULT 50000.0,
    max_token_age_hours INTEGER DEFAULT 72,
    early_window_minutes INTEGER DEFAULT 30,
    min_profit_pct DECIMAL(5,2) DEFAULT 50.0,
    max_tokens INTEGER DEFAULT 20,
    profile_immediately BOOLEAN DEFAULT TRUE,

    -- Audit fields
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_by VARCHAR(100),

    -- Ensure only one row exists (singleton pattern)
    CONSTRAINT single_row CHECK (id = 1)
);

-- Insert default config if not exists
INSERT INTO discovery_config (id) VALUES (1) ON CONFLICT DO NOTHING;

-- Add comment for documentation
COMMENT ON TABLE discovery_config IS 'Singleton table for discovery scheduler configuration';
