-- Migration: Signal Accuracy Tracking
-- Created: 2025-12-20
-- Description: Tables for signal accuracy tracking, snapshots, and retrospective analysis

-- Accuracy snapshots for trend analysis
CREATE TABLE IF NOT EXISTS accuracy_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    signal_to_win_rate DECIMAL(5, 2) NOT NULL,
    signal_to_trade_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    avg_signal_score DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_score_winners DECIMAL(5, 4) NOT NULL DEFAULT 0,
    avg_score_losers DECIMAL(5, 4) NOT NULL DEFAULT 0,
    score_differential DECIMAL(5, 4) NOT NULL DEFAULT 0,
    optimal_threshold DECIMAL(5, 4) NOT NULL DEFAULT 0.6,
    total_signals INTEGER NOT NULL DEFAULT 0,
    traded_signals INTEGER NOT NULL DEFAULT 0,
    winning_trades INTEGER NOT NULL DEFAULT 0,
    losing_trades INTEGER NOT NULL DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_accuracy_snapshots_date
    ON accuracy_snapshots(snapshot_date DESC);

-- Threshold analyses for optimization
CREATE TABLE IF NOT EXISTS threshold_analyses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    threshold DECIMAL(5, 4) NOT NULL,
    would_trade_count INTEGER NOT NULL DEFAULT 0,
    would_win_count INTEGER NOT NULL DEFAULT 0,
    would_lose_count INTEGER NOT NULL DEFAULT 0,
    win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    total_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    profit_factor DECIMAL(10, 4) NOT NULL DEFAULT 0,
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for threshold lookups
CREATE INDEX IF NOT EXISTS idx_threshold_analyses_date
    ON threshold_analyses(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_threshold_analyses_threshold
    ON threshold_analyses(threshold);

-- Factor accuracy breakdown
CREATE TABLE IF NOT EXISTS factor_accuracy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    analysis_date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    factor_name VARCHAR(100) NOT NULL,
    high_score_win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    low_score_win_rate DECIMAL(5, 2) NOT NULL DEFAULT 0,
    is_predictive BOOLEAN NOT NULL DEFAULT FALSE,
    correlation_with_outcome DECIMAL(6, 4) NOT NULL DEFAULT 0,
    recommended_weight_adjustment VARCHAR(20) NOT NULL DEFAULT 'none',
    sample_size INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for factor lookups
CREATE INDEX IF NOT EXISTS idx_factor_accuracy_date
    ON factor_accuracy(analysis_date DESC);
CREATE INDEX IF NOT EXISTS idx_factor_accuracy_factor
    ON factor_accuracy(factor_name);

-- Retrospective signal analysis
CREATE TABLE IF NOT EXISTS retrospective_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID NOT NULL,
    signal_score DECIMAL(5, 4) NOT NULL,
    token_address VARCHAR(64) NOT NULL,
    wallet_address VARCHAR(64) NOT NULL,
    signal_timestamp TIMESTAMPTZ NOT NULL,
    threshold_at_time DECIMAL(5, 4) NOT NULL,
    outcome VARCHAR(20) NOT NULL, -- missed_opportunity, bullet_dodged, uncertain
    estimated_pnl DECIMAL(20, 8),
    price_at_signal DECIMAL(30, 15),
    peak_price_after DECIMAL(30, 15),
    min_price_after DECIMAL(30, 15),
    window_hours INTEGER NOT NULL DEFAULT 24,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for retrospective analysis
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_signal
    ON retrospective_signals(signal_id);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_date
    ON retrospective_signals(signal_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_outcome
    ON retrospective_signals(outcome);
CREATE INDEX IF NOT EXISTS idx_retrospective_signals_token
    ON retrospective_signals(token_address);

-- Retrospective analysis summaries
CREATE TABLE IF NOT EXISTS retrospective_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    window_hours INTEGER NOT NULL DEFAULT 24,
    total_non_traded INTEGER NOT NULL DEFAULT 0,
    missed_opportunities INTEGER NOT NULL DEFAULT 0,
    bullets_dodged INTEGER NOT NULL DEFAULT 0,
    uncertain INTEGER NOT NULL DEFAULT 0,
    total_missed_pnl DECIMAL(20, 8) NOT NULL DEFAULT 0,
    total_avoided_loss DECIMAL(20, 8) NOT NULL DEFAULT 0,
    net_impact DECIMAL(20, 8) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for summary lookups
CREATE INDEX IF NOT EXISTS idx_retrospective_summaries_date
    ON retrospective_summaries(period_start DESC, period_end DESC);

-- RLS policies
ALTER TABLE accuracy_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE threshold_analyses ENABLE ROW LEVEL SECURITY;
ALTER TABLE factor_accuracy ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrospective_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE retrospective_summaries ENABLE ROW LEVEL SECURITY;

-- Service role access policies
CREATE POLICY accuracy_snapshots_service_policy ON accuracy_snapshots
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY threshold_analyses_service_policy ON threshold_analyses
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY factor_accuracy_service_policy ON factor_accuracy
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY retrospective_signals_service_policy ON retrospective_signals
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY retrospective_summaries_service_policy ON retrospective_summaries
    FOR ALL USING (true) WITH CHECK (true);

-- Cleanup function for old snapshots (keep 90 days)
CREATE OR REPLACE FUNCTION cleanup_old_accuracy_data()
RETURNS void AS $$
BEGIN
    DELETE FROM accuracy_snapshots WHERE snapshot_date < NOW() - INTERVAL '90 days';
    DELETE FROM threshold_analyses WHERE analysis_date < NOW() - INTERVAL '30 days';
    DELETE FROM factor_accuracy WHERE analysis_date < NOW() - INTERVAL '30 days';
    DELETE FROM retrospective_signals WHERE created_at < NOW() - INTERVAL '30 days';
    DELETE FROM retrospective_summaries WHERE created_at < NOW() - INTERVAL '90 days';
END;
$$ LANGUAGE plpgsql;

COMMENT ON TABLE accuracy_snapshots IS 'Point-in-time accuracy metrics for trend analysis';
COMMENT ON TABLE threshold_analyses IS 'Analysis of different threshold effectiveness';
COMMENT ON TABLE factor_accuracy IS 'Accuracy breakdown by scoring factor';
COMMENT ON TABLE retrospective_signals IS 'Retrospective analysis of non-traded signals';
COMMENT ON TABLE retrospective_summaries IS 'Aggregated retrospective analysis summaries';
