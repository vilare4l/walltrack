-- Performance Analytics Migration
-- Materialized views and indexes for fast dashboard queries
-- Story 6-6: Dashboard Performance Analytics

-- =====================================================
-- Materialized View: Daily PnL Aggregation
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_daily_pnl_summary AS
SELECT
    DATE(closed_at) AS trade_date,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(CASE WHEN pnl_sol < 0 THEN 1 ELSE 0 END) AS losing_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    SUM(CASE WHEN pnl_sol > 0 THEN pnl_sol ELSE 0 END) AS gross_profit_sol,
    SUM(CASE WHEN pnl_sol < 0 THEN ABS(pnl_sol) ELSE 0 END) AS gross_loss_sol,
    AVG(CASE WHEN pnl_sol > 0 THEN pnl_sol END) AS avg_win_sol,
    AVG(CASE WHEN pnl_sol < 0 THEN ABS(pnl_sol) END) AS avg_loss_sol,
    AVG(EXTRACT(EPOCH FROM (closed_at - created_at))) AS avg_duration_seconds
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY DATE(closed_at)
ORDER BY trade_date;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_daily_pnl_trade_date
ON mv_daily_pnl_summary (trade_date);

-- =====================================================
-- Materialized View: Wallet Performance Summary
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_wallet_performance AS
SELECT
    source_wallet_id,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol,
    MIN(closed_at) AS first_trade_at,
    MAX(closed_at) AS last_trade_at
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY source_wallet_id;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_wallet_perf_wallet
ON mv_wallet_performance (source_wallet_id);

-- =====================================================
-- Materialized View: Exit Strategy Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_exit_strategy_performance AS
SELECT
    exit_strategy_id,
    exit_type,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY exit_strategy_id, exit_type;

CREATE INDEX IF NOT EXISTS idx_mv_exit_strategy_perf_strategy
ON mv_exit_strategy_performance (exit_strategy_id);

CREATE INDEX IF NOT EXISTS idx_mv_exit_strategy_perf_type
ON mv_exit_strategy_performance (exit_type);

-- =====================================================
-- Materialized View: Time-of-Day Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_time_of_day_performance AS
SELECT
    CASE
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 0 AND 5 THEN 'night'
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 6 AND 11 THEN 'morning'
        WHEN EXTRACT(HOUR FROM closed_at) BETWEEN 12 AND 17 THEN 'afternoon'
        ELSE 'evening'
    END AS time_period,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY time_period;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_time_of_day_period
ON mv_time_of_day_performance (time_period);

-- =====================================================
-- Materialized View: Day-of-Week Performance
-- =====================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_day_of_week_performance AS
SELECT
    EXTRACT(DOW FROM closed_at) AS day_of_week,
    TO_CHAR(closed_at, 'Day') AS day_name,
    COUNT(*) AS trade_count,
    SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END) AS winning_trades,
    SUM(pnl_sol) AS total_pnl_sol,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND((SUM(CASE WHEN pnl_sol > 0 THEN 1 ELSE 0 END)::NUMERIC / COUNT(*)) * 100, 2)
        ELSE 0
    END AS win_rate,
    CASE
        WHEN COUNT(*) > 0
        THEN ROUND(SUM(pnl_sol) / COUNT(*), 6)
        ELSE 0
    END AS avg_pnl_sol
FROM trades
WHERE status = 'closed' AND closed_at IS NOT NULL
GROUP BY day_of_week, day_name
ORDER BY day_of_week;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_day_of_week_dow
ON mv_day_of_week_performance (day_of_week);

-- =====================================================
-- Function: Refresh All Performance Materialized Views
-- =====================================================
CREATE OR REPLACE FUNCTION refresh_performance_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_daily_pnl_summary;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_wallet_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_exit_strategy_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_time_of_day_performance;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_day_of_week_performance;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- Indexes on trades table for performance queries
-- =====================================================
CREATE INDEX IF NOT EXISTS idx_trades_closed_at_pnl
ON trades (closed_at, pnl_sol)
WHERE status = 'closed' AND closed_at IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_trades_source_wallet_closed
ON trades (source_wallet_id, closed_at)
WHERE status = 'closed';

CREATE INDEX IF NOT EXISTS idx_trades_exit_strategy_closed
ON trades (exit_strategy_id, closed_at)
WHERE status = 'closed';

-- =====================================================
-- Table: Performance Dashboard Cache
-- =====================================================
CREATE TABLE IF NOT EXISTS performance_cache (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cache_key TEXT UNIQUE NOT NULL,
    data JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_performance_cache_key
ON performance_cache (cache_key);

CREATE INDEX IF NOT EXISTS idx_performance_cache_expires
ON performance_cache (expires_at);

-- Function to clean expired cache entries
CREATE OR REPLACE FUNCTION cleanup_performance_cache()
RETURNS void AS $$
BEGIN
    DELETE FROM performance_cache WHERE expires_at < NOW();
END;
$$ LANGUAGE plpgsql;

-- RLS Policy for performance cache (service account only)
ALTER TABLE performance_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY performance_cache_service_policy ON performance_cache
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =====================================================
-- Comment on objects
-- =====================================================
COMMENT ON MATERIALIZED VIEW mv_daily_pnl_summary IS 'Daily aggregated PnL metrics for performance dashboard';
COMMENT ON MATERIALIZED VIEW mv_wallet_performance IS 'Per-wallet performance aggregation';
COMMENT ON MATERIALIZED VIEW mv_exit_strategy_performance IS 'Performance breakdown by exit strategy';
COMMENT ON MATERIALIZED VIEW mv_time_of_day_performance IS 'Performance breakdown by time of day';
COMMENT ON MATERIALIZED VIEW mv_day_of_week_performance IS 'Performance breakdown by day of week';
COMMENT ON TABLE performance_cache IS 'Server-side cache for dashboard data';
COMMENT ON FUNCTION refresh_performance_views() IS 'Refresh all performance materialized views concurrently';
COMMENT ON FUNCTION cleanup_performance_cache() IS 'Remove expired cache entries';
