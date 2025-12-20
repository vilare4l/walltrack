-- Migration: Pattern Analysis
-- Description: Tables for pattern analysis and insights (Story 6-5)
-- Created: 2025-12-20

-- Pattern analyses table stores analysis results
CREATE TABLE IF NOT EXISTS pattern_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analyzed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    trade_count INTEGER NOT NULL,
    baseline_win_rate DECIMAL(5, 2) NOT NULL,
    patterns JSONB NOT NULL DEFAULT '[]',
    time_patterns JSONB NOT NULL DEFAULT '[]',
    wallet_patterns JSONB NOT NULL DEFAULT '[]',
    token_patterns JSONB NOT NULL DEFAULT '[]',
    cluster_patterns JSONB NOT NULL DEFAULT '[]',
    top_positive_patterns JSONB NOT NULL DEFAULT '[]',
    top_negative_patterns JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Pattern alerts table for significant pattern notifications
CREATE TABLE IF NOT EXISTS pattern_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pattern_id UUID NOT NULL,
    pattern_type VARCHAR(50) NOT NULL,
    pattern_name VARCHAR(255) NOT NULL,
    sentiment VARCHAR(20) NOT NULL CHECK (sentiment IN ('positive', 'negative', 'neutral')),
    message TEXT NOT NULL,
    suggested_action TEXT NOT NULL,
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE,
    acknowledged_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_pattern_analyses_analyzed_at
    ON pattern_analyses(analyzed_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_acknowledged
    ON pattern_alerts(acknowledged) WHERE acknowledged = FALSE;

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_created_at
    ON pattern_alerts(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_pattern_type
    ON pattern_alerts(pattern_type);

CREATE INDEX IF NOT EXISTS idx_pattern_alerts_sentiment
    ON pattern_alerts(sentiment);

-- Enable Row Level Security
ALTER TABLE pattern_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE pattern_alerts ENABLE ROW LEVEL SECURITY;

-- RLS policies for pattern_analyses
CREATE POLICY pattern_analyses_select_policy ON pattern_analyses
    FOR SELECT USING (true);

CREATE POLICY pattern_analyses_insert_policy ON pattern_analyses
    FOR INSERT WITH CHECK (true);

CREATE POLICY pattern_analyses_update_policy ON pattern_analyses
    FOR UPDATE USING (true);

-- RLS policies for pattern_alerts
CREATE POLICY pattern_alerts_select_policy ON pattern_alerts
    FOR SELECT USING (true);

CREATE POLICY pattern_alerts_insert_policy ON pattern_alerts
    FOR INSERT WITH CHECK (true);

CREATE POLICY pattern_alerts_update_policy ON pattern_alerts
    FOR UPDATE USING (true);

-- Function to cleanup old pattern analyses (keep last 30 days)
CREATE OR REPLACE FUNCTION cleanup_old_pattern_analyses()
RETURNS void AS $$
BEGIN
    DELETE FROM pattern_analyses
    WHERE analyzed_at < NOW() - INTERVAL '30 days';
END;
$$ LANGUAGE plpgsql;

-- Function to cleanup acknowledged alerts older than 7 days
CREATE OR REPLACE FUNCTION cleanup_acknowledged_alerts()
RETURNS void AS $$
BEGIN
    DELETE FROM pattern_alerts
    WHERE acknowledged = TRUE
    AND acknowledged_at < NOW() - INTERVAL '7 days';
END;
$$ LANGUAGE plpgsql;

-- Trigger to set acknowledged_at when alert is acknowledged
CREATE OR REPLACE FUNCTION set_acknowledged_at()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.acknowledged = TRUE AND OLD.acknowledged = FALSE THEN
        NEW.acknowledged_at = NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_set_acknowledged_at
    BEFORE UPDATE ON pattern_alerts
    FOR EACH ROW
    EXECUTE FUNCTION set_acknowledged_at();

-- Comments for documentation
COMMENT ON TABLE pattern_analyses IS 'Stores results of pattern analysis runs';
COMMENT ON TABLE pattern_alerts IS 'Alerts generated for significant trading patterns';
COMMENT ON COLUMN pattern_analyses.patterns IS 'JSON array of all identified Pattern objects';
COMMENT ON COLUMN pattern_analyses.top_positive_patterns IS 'Top patterns correlated with success';
COMMENT ON COLUMN pattern_analyses.top_negative_patterns IS 'Top patterns correlated with failure';
COMMENT ON COLUMN pattern_alerts.acknowledged IS 'Whether the alert has been reviewed by user';
