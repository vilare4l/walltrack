-- Migration: 007_position_sizing.sql
-- Story: 4-3 Dynamic Position Sizing

CREATE TABLE IF NOT EXISTS position_sizing_config (
    id UUID PRIMARY KEY DEFAULT '00000000-0000-0000-0000-000000000001',
    base_position_pct DECIMAL(5, 2) NOT NULL DEFAULT 2.0,
    min_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.01,
    max_position_sol DECIMAL(20, 9) NOT NULL DEFAULT 1.0,
    high_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.5,
    standard_conviction_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.0,
    high_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.85,
    min_conviction_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.70,
    max_concurrent_positions INTEGER NOT NULL DEFAULT 5,
    max_capital_allocation_pct DECIMAL(5, 2) NOT NULL DEFAULT 50.0,
    reserve_sol DECIMAL(20, 9) NOT NULL DEFAULT 0.05,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,
    CONSTRAINT valid_base_pct CHECK (base_position_pct > 0 AND base_position_pct <= 100),
    CONSTRAINT valid_thresholds CHECK (high_conviction_threshold > min_conviction_threshold)
);

CREATE TABLE IF NOT EXISTS position_sizing_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID,
    token_address TEXT,
    signal_score DECIMAL(5, 4) NOT NULL,
    available_balance_sol DECIMAL(20, 9) NOT NULL,
    current_position_count INTEGER NOT NULL,
    current_allocated_sol DECIMAL(20, 9) NOT NULL,
    config_snapshot JSONB NOT NULL,
    decision TEXT NOT NULL,
    conviction_tier TEXT NOT NULL,
    base_size_sol DECIMAL(20, 9) NOT NULL,
    multiplier DECIMAL(5, 2) NOT NULL,
    calculated_size_sol DECIMAL(20, 9) DEFAULT 0,
    final_size_sol DECIMAL(20, 9) NOT NULL,
    reason TEXT,
    reduction_applied BOOLEAN DEFAULT FALSE,
    reduction_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_position_audit_signal ON position_sizing_audit(signal_id);
CREATE INDEX IF NOT EXISTS idx_position_audit_created ON position_sizing_audit(created_at DESC);

INSERT INTO position_sizing_config (id) VALUES ('00000000-0000-0000-0000-000000000001')
ON CONFLICT (id) DO NOTHING;

ALTER TABLE position_sizing_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE position_sizing_audit ENABLE ROW LEVEL SECURITY;
