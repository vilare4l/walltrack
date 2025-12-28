-- Migration: 019_discovery_runs
-- Description: Tables for tracking discovery run history
-- Date: 2024-12-24

-- Discovery runs table
CREATE TABLE IF NOT EXISTS discovery_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'running',

    -- Trigger type
    trigger_type VARCHAR(20) NOT NULL, -- 'manual', 'scheduled', 'api'
    triggered_by VARCHAR(100), -- user/system identifier

    -- Parameters used
    min_price_change_pct DECIMAL(5,2),
    min_volume_usd DECIMAL(15,2),
    max_token_age_hours INTEGER,
    early_window_minutes INTEGER,
    min_profit_pct DECIMAL(5,2),
    max_tokens INTEGER,

    -- Results
    tokens_analyzed INTEGER DEFAULT 0,
    new_wallets INTEGER DEFAULT 0,
    updated_wallets INTEGER DEFAULT 0,
    profiled_wallets INTEGER DEFAULT 0,
    duration_seconds DECIMAL(10,2),

    -- Errors
    errors JSONB DEFAULT '[]',

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for discovery_runs
CREATE INDEX IF NOT EXISTS idx_discovery_runs_started ON discovery_runs(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_status ON discovery_runs(status);
CREATE INDEX IF NOT EXISTS idx_discovery_runs_trigger ON discovery_runs(trigger_type);

-- Discovery run wallets (link table)
CREATE TABLE IF NOT EXISTS discovery_run_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES discovery_runs(id) ON DELETE CASCADE,
    wallet_address VARCHAR(44) NOT NULL,
    source_token VARCHAR(44) NOT NULL,
    is_new BOOLEAN DEFAULT TRUE,
    initial_score DECIMAL(5,4),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for discovery_run_wallets
CREATE INDEX IF NOT EXISTS idx_drw_run ON discovery_run_wallets(run_id);
CREATE INDEX IF NOT EXISTS idx_drw_wallet ON discovery_run_wallets(wallet_address);
CREATE INDEX IF NOT EXISTS idx_drw_token ON discovery_run_wallets(source_token);

-- Comments for documentation
COMMENT ON TABLE discovery_runs IS 'History of wallet discovery runs';
COMMENT ON TABLE discovery_run_wallets IS 'Wallets discovered in each run';
COMMENT ON COLUMN discovery_runs.trigger_type IS 'How run was triggered: manual, scheduled, or api';
COMMENT ON COLUMN discovery_runs.status IS 'Run status: running, completed, failed, cancelled';
