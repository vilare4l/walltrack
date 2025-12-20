-- Migration: 017_backtest.sql
-- Description: Backtest preview tables for parameter optimization
-- Epic 6, Story 6-7: Backtest Preview

-- ============================================================================
-- BACKTEST RESULTS TABLE
-- ============================================================================
-- Stores completed backtest runs with configuration and results

CREATE TABLE IF NOT EXISTS backtest_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    config JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_seconds INTEGER,
    total_signals_analyzed INTEGER DEFAULT 0,
    signals_above_threshold INTEGER DEFAULT 0,
    metrics_comparison JSONB,
    simulated_trades JSONB DEFAULT '[]'::jsonb,
    trade_comparisons JSONB DEFAULT '[]'::jsonb,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled')),
    CONSTRAINT valid_dates CHECK (completed_at IS NULL OR completed_at >= started_at)
);

-- Index for querying recent backtests
CREATE INDEX IF NOT EXISTS idx_backtest_results_started_at
ON backtest_results(started_at DESC);

-- Index for filtering by status
CREATE INDEX IF NOT EXISTS idx_backtest_results_status
ON backtest_results(status);

-- ============================================================================
-- SIGNAL CACHE TABLE
-- ============================================================================
-- Caches historical signals for faster backtest execution

CREATE TABLE IF NOT EXISTS signal_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key VARCHAR(255) NOT NULL UNIQUE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    signal_count INTEGER NOT NULL DEFAULT 0,
    cached_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,

    CONSTRAINT valid_date_range CHECK (end_date >= start_date)
);

-- Index for cache lookup
CREATE INDEX IF NOT EXISTS idx_signal_cache_key
ON signal_cache(cache_key);

-- Index for cache expiry cleanup
CREATE INDEX IF NOT EXISTS idx_signal_cache_expires
ON signal_cache(expires_at);

-- ============================================================================
-- TOKEN PRICE HISTORY TABLE
-- ============================================================================
-- Stores historical price data for tokens (for backtest simulations)

CREATE TABLE IF NOT EXISTS token_price_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_address VARCHAR(44) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    price_usd DECIMAL(30, 18) NOT NULL,
    price_sol DECIMAL(30, 18),
    volume_24h DECIMAL(30, 2),
    liquidity_usd DECIMAL(30, 2),
    source VARCHAR(50) DEFAULT 'dexscreener',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_token_price UNIQUE (token_address, timestamp, source)
);

-- Index for price lookups by token and time range
CREATE INDEX IF NOT EXISTS idx_token_price_history_lookup
ON token_price_history(token_address, timestamp DESC);

-- Index for time-based queries
CREATE INDEX IF NOT EXISTS idx_token_price_history_timestamp
ON token_price_history(timestamp DESC);

-- ============================================================================
-- APPLIED SETTINGS HISTORY TABLE
-- ============================================================================
-- Tracks when backtest settings are applied to production

CREATE TABLE IF NOT EXISTS applied_settings_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    backtest_id UUID NOT NULL REFERENCES backtest_results(id),
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    changes_applied JSONB NOT NULL DEFAULT '[]'::jsonb,
    previous_values JSONB NOT NULL DEFAULT '{}'::jsonb,
    applied_by VARCHAR(100),
    rollback_at TIMESTAMPTZ,
    rollback_reason TEXT,

    CONSTRAINT fk_backtest FOREIGN KEY (backtest_id)
        REFERENCES backtest_results(id) ON DELETE CASCADE
);

-- Index for finding settings by backtest
CREATE INDEX IF NOT EXISTS idx_applied_settings_backtest
ON applied_settings_history(backtest_id);

-- Index for chronological queries
CREATE INDEX IF NOT EXISTS idx_applied_settings_applied_at
ON applied_settings_history(applied_at DESC);

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to clean expired signal cache entries
CREATE OR REPLACE FUNCTION cleanup_expired_signal_cache()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM signal_cache
    WHERE expires_at < NOW();

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$;

-- Function to get or create cache entry
CREATE OR REPLACE FUNCTION get_or_create_signal_cache(
    p_cache_key VARCHAR(255),
    p_start_date DATE,
    p_end_date DATE,
    p_ttl_minutes INTEGER DEFAULT 30
)
RETURNS TABLE (
    cache_id UUID,
    is_fresh BOOLEAN,
    signals JSONB
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_cache_id UUID;
    v_signals JSONB;
    v_is_fresh BOOLEAN;
BEGIN
    -- Try to get existing valid cache
    SELECT sc.id, sc.signals, (sc.expires_at > NOW()) INTO v_cache_id, v_signals, v_is_fresh
    FROM signal_cache sc
    WHERE sc.cache_key = p_cache_key
    LIMIT 1;

    IF v_cache_id IS NOT NULL AND v_is_fresh THEN
        RETURN QUERY SELECT v_cache_id, TRUE, v_signals;
    ELSE
        -- Create new cache entry (signals will be populated by application)
        INSERT INTO signal_cache (cache_key, start_date, end_date, signals, expires_at)
        VALUES (
            p_cache_key,
            p_start_date,
            p_end_date,
            '[]'::jsonb,
            NOW() + (p_ttl_minutes || ' minutes')::interval
        )
        ON CONFLICT (cache_key) DO UPDATE SET
            expires_at = NOW() + (p_ttl_minutes || ' minutes')::interval,
            cached_at = NOW()
        RETURNING id INTO v_cache_id;

        RETURN QUERY SELECT v_cache_id, FALSE, '[]'::jsonb;
    END IF;
END;
$$;

-- Function to update backtest progress
CREATE OR REPLACE FUNCTION update_backtest_progress(
    p_backtest_id UUID,
    p_status VARCHAR(20),
    p_signals_analyzed INTEGER DEFAULT NULL,
    p_signals_above_threshold INTEGER DEFAULT NULL,
    p_error_message TEXT DEFAULT NULL
)
RETURNS VOID
LANGUAGE plpgsql
AS $$
BEGIN
    UPDATE backtest_results
    SET
        status = p_status,
        total_signals_analyzed = COALESCE(p_signals_analyzed, total_signals_analyzed),
        signals_above_threshold = COALESCE(p_signals_above_threshold, signals_above_threshold),
        error_message = COALESCE(p_error_message, error_message),
        completed_at = CASE WHEN p_status IN ('completed', 'failed', 'cancelled') THEN NOW() ELSE completed_at END,
        duration_seconds = CASE
            WHEN p_status IN ('completed', 'failed', 'cancelled')
            THEN EXTRACT(EPOCH FROM (NOW() - started_at))::INTEGER
            ELSE duration_seconds
        END,
        updated_at = NOW()
    WHERE id = p_backtest_id;
END;
$$;

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE backtest_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE signal_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE token_price_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE applied_settings_history ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users full access (single-user system)
CREATE POLICY backtest_results_policy ON backtest_results
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY signal_cache_policy ON signal_cache
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY token_price_history_policy ON token_price_history
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY applied_settings_policy ON applied_settings_history
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_backtest_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_backtest_results_updated_at
    BEFORE UPDATE ON backtest_results
    FOR EACH ROW
    EXECUTE FUNCTION update_backtest_updated_at();

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE backtest_results IS 'Stores backtest run configurations and results';
COMMENT ON TABLE signal_cache IS 'Caches historical signals for faster backtest execution';
COMMENT ON TABLE token_price_history IS 'Historical price data for backtest simulations';
COMMENT ON TABLE applied_settings_history IS 'Audit trail of settings applied from backtests';

COMMENT ON FUNCTION cleanup_expired_signal_cache() IS 'Removes expired cache entries';
COMMENT ON FUNCTION get_or_create_signal_cache(VARCHAR, DATE, DATE, INTEGER) IS 'Gets existing cache or creates placeholder';
COMMENT ON FUNCTION update_backtest_progress(UUID, VARCHAR, INTEGER, INTEGER, TEXT) IS 'Updates backtest status and metrics';
