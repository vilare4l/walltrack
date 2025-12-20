-- Migration: 013_calibration
-- Description: Tables for scoring model calibration
-- Epic: 6 - Feedback Loop & Performance Analytics
-- Story: 6-3 - Scoring Model Recalibration

-- Calibration analyses
CREATE TABLE IF NOT EXISTS calibration_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_count INTEGER NOT NULL DEFAULT 0,
    min_trades_required INTEGER NOT NULL DEFAULT 100,

    -- Current weights at time of analysis (JSONB)
    current_weights JSONB NOT NULL,

    -- Suggested weights based on analysis (JSONB)
    suggested_weights JSONB NOT NULL,

    -- Factor correlations (array of JSONB)
    correlations JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Estimated win rate improvement percentage
    estimated_improvement DECIMAL(5,2) NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for recent analyses
CREATE INDEX IF NOT EXISTS idx_calibration_analyses_analyzed_at
    ON calibration_analyses(analyzed_at DESC);


-- Calibration suggestions for operator review
CREATE TABLE IF NOT EXISTS calibration_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_id UUID NOT NULL REFERENCES calibration_analyses(id),

    -- Status: pending, approved, rejected, modified
    status VARCHAR(20) NOT NULL DEFAULT 'pending',

    -- Weight configurations (JSONB)
    current_weights JSONB NOT NULL,
    suggested_weights JSONB NOT NULL,

    -- Individual weight change suggestions (array of JSONB)
    suggestions JSONB NOT NULL DEFAULT '[]'::jsonb,

    -- Estimated improvement percentage
    estimated_improvement DECIMAL(5,2) NOT NULL DEFAULT 0,

    -- Application tracking
    applied_at TIMESTAMPTZ,
    applied_weights JSONB,
    operator_notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for pending suggestions
CREATE INDEX IF NOT EXISTS idx_calibration_suggestions_status
    ON calibration_suggestions(status) WHERE status = 'pending';

-- Index for analysis lookup
CREATE INDEX IF NOT EXISTS idx_calibration_suggestions_analysis_id
    ON calibration_suggestions(analysis_id);


-- Weight archive for historical tracking
CREATE TABLE IF NOT EXISTS weight_archives (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Weight configuration (JSONB)
    weights JSONB NOT NULL,

    -- Active period
    active_from TIMESTAMPTZ NOT NULL,
    active_until TIMESTAMPTZ NOT NULL,

    -- Associated suggestion if from calibration
    suggestion_id UUID REFERENCES calibration_suggestions(id),

    -- Performance during this weight period
    performance_during DECIMAL(5,2),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for date range queries
CREATE INDEX IF NOT EXISTS idx_weight_archives_active_range
    ON weight_archives(active_from, active_until);


-- Current active weights (singleton row pattern)
CREATE TABLE IF NOT EXISTS scoring_weights (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    wallet_weight DECIMAL(4,3) NOT NULL DEFAULT 0.350,
    cluster_weight DECIMAL(4,3) NOT NULL DEFAULT 0.250,
    token_weight DECIMAL(4,3) NOT NULL DEFAULT 0.250,
    context_weight DECIMAL(4,3) NOT NULL DEFAULT 0.150,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by TEXT,

    -- Ensure weights sum to approximately 1
    CONSTRAINT weights_sum_check CHECK (
        ABS(wallet_weight + cluster_weight + token_weight + context_weight - 1.0) < 0.01
    )
);

-- Insert default weights
INSERT INTO scoring_weights (wallet_weight, cluster_weight, token_weight, context_weight)
VALUES (0.350, 0.250, 0.250, 0.150)
ON CONFLICT (id) DO NOTHING;


-- Auto-calibration configuration (singleton)
CREATE TABLE IF NOT EXISTS auto_calibration_config (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton
    enabled BOOLEAN NOT NULL DEFAULT FALSE,
    min_trades_between INTEGER NOT NULL DEFAULT 100,
    max_weight_change DECIMAL(4,3) NOT NULL DEFAULT 0.100,
    min_improvement_threshold DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    log_all_changes BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insert default config
INSERT INTO auto_calibration_config (enabled)
VALUES (FALSE)
ON CONFLICT (id) DO NOTHING;


-- Add updated_at trigger function if not exists
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers
DROP TRIGGER IF EXISTS update_calibration_suggestions_updated_at ON calibration_suggestions;
CREATE TRIGGER update_calibration_suggestions_updated_at
    BEFORE UPDATE ON calibration_suggestions
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_scoring_weights_updated_at ON scoring_weights;
CREATE TRIGGER update_scoring_weights_updated_at
    BEFORE UPDATE ON scoring_weights
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_auto_calibration_config_updated_at ON auto_calibration_config;
CREATE TRIGGER update_auto_calibration_config_updated_at
    BEFORE UPDATE ON auto_calibration_config
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();


-- RLS policies (assuming auth is set up)
ALTER TABLE calibration_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE calibration_suggestions ENABLE ROW LEVEL SECURITY;
ALTER TABLE weight_archives ENABLE ROW LEVEL SECURITY;
ALTER TABLE scoring_weights ENABLE ROW LEVEL SECURITY;
ALTER TABLE auto_calibration_config ENABLE ROW LEVEL SECURITY;

-- Service role policies (for backend access)
CREATE POLICY calibration_analyses_service_all ON calibration_analyses
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY calibration_suggestions_service_all ON calibration_suggestions
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY weight_archives_service_all ON weight_archives
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY scoring_weights_service_all ON scoring_weights
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY auto_calibration_config_service_all ON auto_calibration_config
    FOR ALL USING (TRUE) WITH CHECK (TRUE);
