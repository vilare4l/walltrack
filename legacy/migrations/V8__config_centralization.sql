-- WallTrack Configuration Centralization Migration
-- Date: 2024-12-26
-- Purpose: Create centralized config tables for hot-reload capability
-- Version: V8

-- ============================================================
-- PHASE 1: CREATE CONFIG TABLES
-- ============================================================

-- 1.1 Trading Configuration
CREATE TABLE IF NOT EXISTS walltrack.trading_config (
    id SERIAL PRIMARY KEY,

    -- Position Sizing
    base_position_size_pct DECIMAL(5,2) DEFAULT 2.0,
    min_position_sol DECIMAL(10,4) DEFAULT 0.01,
    max_position_sol DECIMAL(10,4) DEFAULT 1.0,
    max_concurrent_positions INTEGER DEFAULT 5,

    -- Thresholds
    score_threshold DECIMAL(4,3) DEFAULT 0.70,
    high_conviction_threshold DECIMAL(4,3) DEFAULT 0.85,
    high_conviction_multiplier DECIMAL(4,2) DEFAULT 1.5,

    -- Token Filters
    min_token_age_seconds INTEGER DEFAULT 300,
    max_token_age_hours INTEGER DEFAULT 24,
    min_liquidity_usd DECIMAL(12,2) DEFAULT 10000.0,
    max_market_cap_usd DECIMAL(15,2) DEFAULT 10000000.0,

    -- Timing
    max_position_hold_hours INTEGER DEFAULT 24,
    max_daily_trades INTEGER DEFAULT 20,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT trading_config_single CHECK (id = 1)
);

-- 1.2 Scoring Configuration
CREATE TABLE IF NOT EXISTS walltrack.scoring_config (
    id SERIAL PRIMARY KEY,

    -- Main Weights (must sum to 1.0)
    wallet_weight DECIMAL(4,3) DEFAULT 0.30,
    cluster_weight DECIMAL(4,3) DEFAULT 0.25,
    token_weight DECIMAL(4,3) DEFAULT 0.25,
    context_weight DECIMAL(4,3) DEFAULT 0.20,

    -- Wallet Score Sub-Weights
    wallet_win_rate_weight DECIMAL(4,3) DEFAULT 0.35,
    wallet_pnl_weight DECIMAL(4,3) DEFAULT 0.25,
    wallet_timing_weight DECIMAL(4,3) DEFAULT 0.25,
    wallet_consistency_weight DECIMAL(4,3) DEFAULT 0.15,
    wallet_leader_bonus DECIMAL(4,3) DEFAULT 0.15,
    wallet_max_decay_penalty DECIMAL(4,3) DEFAULT 0.30,

    -- Token Score Sub-Weights
    token_liquidity_weight DECIMAL(4,3) DEFAULT 0.30,
    token_mcap_weight DECIMAL(4,3) DEFAULT 0.25,
    token_holder_dist_weight DECIMAL(4,3) DEFAULT 0.20,
    token_volume_weight DECIMAL(4,3) DEFAULT 0.25,

    -- Token Thresholds
    token_min_liquidity_usd DECIMAL(12,2) DEFAULT 1000.0,
    token_optimal_liquidity_usd DECIMAL(12,2) DEFAULT 50000.0,
    token_min_mcap_usd DECIMAL(12,2) DEFAULT 10000.0,
    token_optimal_mcap_usd DECIMAL(12,2) DEFAULT 500000.0,

    -- Context Score
    peak_trading_hours_utc INTEGER[] DEFAULT ARRAY[14,15,16,17,18],
    high_volatility_threshold DECIMAL(4,3) DEFAULT 0.10,

    -- Cluster Score
    solo_signal_base DECIMAL(4,3) DEFAULT 0.50,
    min_participation_rate DECIMAL(4,3) DEFAULT 0.30,

    -- New Token Penalty
    new_token_penalty_minutes INTEGER DEFAULT 5,
    max_new_token_penalty DECIMAL(4,3) DEFAULT 0.30,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT scoring_config_single CHECK (id = 1),
    CONSTRAINT scoring_weights_sum CHECK (
        ABS(wallet_weight + cluster_weight + token_weight + context_weight - 1.0) < 0.001
    )
);

-- 1.3 Discovery Configuration
CREATE TABLE IF NOT EXISTS walltrack.discovery_config (
    id SERIAL PRIMARY KEY,

    -- Schedule
    discovery_cron TEXT DEFAULT '0 */6 * * *',

    -- Pump Token Criteria
    pump_min_gain_pct DECIMAL(5,2) DEFAULT 100.0,
    pump_min_liquidity_usd DECIMAL(12,2) DEFAULT 10000.0,
    pump_max_market_cap_usd DECIMAL(15,2) DEFAULT 5000000.0,
    pump_min_age_minutes INTEGER DEFAULT 30,
    pump_max_age_hours INTEGER DEFAULT 24,
    pump_max_tokens_per_run INTEGER DEFAULT 20,

    -- Early Buyer Filtering
    buyer_min_amount_sol DECIMAL(10,4) DEFAULT 0.1,
    buyer_max_amount_sol DECIMAL(10,4) DEFAULT 10.0,
    buyer_max_per_token INTEGER DEFAULT 100,

    -- Wallet Profiling Thresholds
    profile_min_total_trades INTEGER DEFAULT 10,
    profile_min_win_rate_pct DECIMAL(5,2) DEFAULT 50.0,
    profile_min_pnl_sol DECIMAL(10,4) DEFAULT 1.0,
    profile_lookback_days INTEGER DEFAULT 90,

    -- Decay Detection
    decay_rolling_window INTEGER DEFAULT 20,
    decay_win_rate_threshold DECIMAL(5,2) DEFAULT 40.0,
    decay_recovery_threshold DECIMAL(5,2) DEFAULT 50.0,
    decay_consecutive_loss_threshold INTEGER DEFAULT 3,
    decay_score_downgrade_factor DECIMAL(4,3) DEFAULT 0.80,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT discovery_config_single CHECK (id = 1)
);

-- 1.4 Cluster Configuration
CREATE TABLE IF NOT EXISTS walltrack.cluster_config (
    id SERIAL PRIMARY KEY,

    -- Cluster Detection
    min_cluster_size INTEGER DEFAULT 3,
    min_cluster_strength DECIMAL(4,3) DEFAULT 0.30,
    min_cluster_edges INTEGER DEFAULT 2,
    max_analysis_depth INTEGER DEFAULT 3,

    -- Sync Buy Detection
    sync_buy_window_minutes INTEGER DEFAULT 5,
    sync_buy_lookback_days INTEGER DEFAULT 30,

    -- Co-occurrence Analysis
    cooccurrence_min_tokens INTEGER DEFAULT 3,
    cooccurrence_time_window_hours INTEGER DEFAULT 24,
    cooccurrence_min_jaccard DECIMAL(4,3) DEFAULT 0.20,
    cooccurrence_min_count INTEGER DEFAULT 2,

    -- Funding Analysis
    funding_min_amount_sol DECIMAL(10,4) DEFAULT 0.1,
    funding_strength_cap_sol DECIMAL(10,4) DEFAULT 10.0,
    funding_max_depth INTEGER DEFAULT 3,

    -- Leader Detection
    leader_min_score DECIMAL(4,3) DEFAULT 0.30,
    leader_funding_weight DECIMAL(4,3) DEFAULT 0.30,
    leader_timing_weight DECIMAL(4,3) DEFAULT 0.25,
    leader_centrality_weight DECIMAL(4,3) DEFAULT 0.25,
    leader_performance_weight DECIMAL(4,3) DEFAULT 0.20,
    leader_pnl_cap_usd DECIMAL(12,2) DEFAULT 10000.0,

    -- Signal Amplification
    amplification_window_seconds INTEGER DEFAULT 600,
    min_active_members_for_amp INTEGER DEFAULT 2,
    base_amplification_factor DECIMAL(4,2) DEFAULT 1.20,
    max_amplification_factor DECIMAL(4,2) DEFAULT 1.80,
    min_amplification_multiplier DECIMAL(4,2) DEFAULT 1.00,
    max_amplification_multiplier DECIMAL(4,2) DEFAULT 3.00,
    cohesion_threshold DECIMAL(4,3) DEFAULT 0.30,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT cluster_config_single CHECK (id = 1)
);

-- 1.5 Risk Configuration
CREATE TABLE IF NOT EXISTS walltrack.risk_config (
    id SERIAL PRIMARY KEY,

    -- Risk-Based Position Sizing
    risk_per_trade_pct DECIMAL(5,2) DEFAULT 1.0,       -- Max 1% risk per trade
    sizing_mode TEXT DEFAULT 'risk_based',              -- 'risk_based' or 'fixed_percent'

    -- Daily Loss Limit
    daily_loss_limit_pct DECIMAL(5,2) DEFAULT 5.0,      -- Stop trading if -5% daily
    daily_loss_limit_enabled BOOLEAN DEFAULT TRUE,

    -- Concentration Limits
    max_concentration_token_pct DECIMAL(5,2) DEFAULT 25.0,   -- Max 25% per token
    max_concentration_cluster_pct DECIMAL(5,2) DEFAULT 50.0, -- Max 50% per cluster
    max_positions_per_cluster INTEGER DEFAULT 3,

    -- Capital Protection (Drawdown)
    max_drawdown_pct DECIMAL(5,2) DEFAULT 20.0,
    drawdown_warning_pct DECIMAL(5,2) DEFAULT 15.0,

    -- Drawdown-Based Size Reduction Tiers (JSON array)
    drawdown_reduction_tiers JSONB DEFAULT '[
        {"threshold_pct": 5, "size_reduction_pct": 0},
        {"threshold_pct": 10, "size_reduction_pct": 25},
        {"threshold_pct": 15, "size_reduction_pct": 50},
        {"threshold_pct": 20, "size_reduction_pct": 100}
    ]'::JSONB,

    -- Win Rate Circuit Breaker
    win_rate_threshold_pct DECIMAL(5,2) DEFAULT 40.0,
    win_rate_window_size INTEGER DEFAULT 50,
    win_rate_min_trades INTEGER DEFAULT 10,

    -- Consecutive Loss Circuit Breaker
    consecutive_loss_threshold INTEGER DEFAULT 3,
    consecutive_loss_critical INTEGER DEFAULT 5,
    position_size_reduction_factor DECIMAL(4,3) DEFAULT 0.50,

    -- Circuit Breaker Behavior
    circuit_breaker_threshold INTEGER DEFAULT 5,
    circuit_breaker_cooldown_seconds INTEGER DEFAULT 30,
    auto_resume_enabled BOOLEAN DEFAULT TRUE,

    -- No Signal Warning
    no_signal_warning_hours INTEGER DEFAULT 48,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT risk_config_single CHECK (id = 1),
    CONSTRAINT sizing_mode_valid CHECK (sizing_mode IN ('risk_based', 'fixed_percent'))
);

-- 1.6 Exit Configuration
CREATE TABLE IF NOT EXISTS walltrack.exit_config (
    id SERIAL PRIMARY KEY,

    -- Default Stop Loss
    default_stop_loss_pct DECIMAL(5,2) DEFAULT 50.0,

    -- Default Take Profits
    default_tp1_multiplier DECIMAL(4,2) DEFAULT 2.0,
    default_tp1_sell_pct DECIMAL(5,2) DEFAULT 33.0,
    default_tp2_multiplier DECIMAL(4,2) DEFAULT 3.0,
    default_tp2_sell_pct DECIMAL(5,2) DEFAULT 33.0,
    default_tp3_multiplier DECIMAL(4,2) DEFAULT 5.0,
    default_tp3_sell_pct DECIMAL(5,2) DEFAULT 34.0,

    -- Trailing Stop Defaults
    trailing_stop_enabled BOOLEAN DEFAULT TRUE,
    trailing_stop_activation_multiplier DECIMAL(4,2) DEFAULT 2.0,
    trailing_stop_distance_pct DECIMAL(5,2) DEFAULT 30.0,

    -- Moonbag Defaults
    moonbag_enabled BOOLEAN DEFAULT FALSE,
    moonbag_percent DECIMAL(5,2) DEFAULT 0.0,
    moonbag_stop_loss_pct DECIMAL(5,2) DEFAULT 20.0,

    -- Time Limits
    default_max_hold_hours INTEGER DEFAULT 168,
    stagnation_exit_enabled BOOLEAN DEFAULT FALSE,
    stagnation_threshold_pct DECIMAL(5,2) DEFAULT 5.0,
    stagnation_hours INTEGER DEFAULT 6,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT exit_config_single CHECK (id = 1)
);

-- 1.7 API Configuration
CREATE TABLE IF NOT EXISTS walltrack.api_config (
    id SERIAL PRIMARY KEY,

    -- General API Settings
    default_timeout_seconds INTEGER DEFAULT 30,
    max_retries INTEGER DEFAULT 3,
    retry_base_delay_seconds DECIMAL(4,2) DEFAULT 1.0,

    -- DexScreener
    dexscreener_timeout_seconds INTEGER DEFAULT 5,
    dexscreener_rate_limit_per_minute INTEGER DEFAULT 300,

    -- Birdeye
    birdeye_timeout_seconds INTEGER DEFAULT 5,
    birdeye_rate_limit_per_minute INTEGER DEFAULT 100,

    -- Jupiter
    jupiter_quote_timeout_seconds INTEGER DEFAULT 5,
    jupiter_swap_timeout_seconds INTEGER DEFAULT 30,
    jupiter_confirmation_timeout_seconds INTEGER DEFAULT 60,
    jupiter_default_slippage_bps INTEGER DEFAULT 100,
    jupiter_max_slippage_bps INTEGER DEFAULT 500,
    jupiter_priority_fee_lamports INTEGER DEFAULT 10000,

    -- Cache TTLs
    token_cache_ttl_seconds INTEGER DEFAULT 300,
    wallet_cache_ttl_seconds INTEGER DEFAULT 60,
    config_cache_ttl_seconds INTEGER DEFAULT 60,

    -- Cache Sizes
    token_cache_max_size INTEGER DEFAULT 5000,
    wallet_cache_max_size INTEGER DEFAULT 10000,

    -- Metadata
    updated_at TIMESTAMP DEFAULT NOW(),
    updated_by TEXT DEFAULT 'system',

    CONSTRAINT api_config_single CHECK (id = 1)
);

-- 1.8 Config Audit Log
CREATE TABLE IF NOT EXISTS walltrack.config_audit_log (
    id SERIAL PRIMARY KEY,
    config_table TEXT NOT NULL,
    config_key TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TIMESTAMP DEFAULT NOW(),
    reason TEXT
);

-- Index for audit queries
CREATE INDEX IF NOT EXISTS idx_config_audit_table
    ON walltrack.config_audit_log(config_table);
CREATE INDEX IF NOT EXISTS idx_config_audit_date
    ON walltrack.config_audit_log(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_config_audit_key
    ON walltrack.config_audit_log(config_table, config_key);

-- ============================================================
-- PHASE 2: INSERT DEFAULT ROWS
-- ============================================================

-- Each config table has a single row with id=1

INSERT INTO walltrack.trading_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.scoring_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.discovery_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.cluster_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.risk_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.exit_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

INSERT INTO walltrack.api_config (id) VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- ============================================================
-- PHASE 3: CREATE TRIGGER FOR AUDIT LOG
-- ============================================================

CREATE OR REPLACE FUNCTION walltrack.log_config_change()
RETURNS TRIGGER AS $$
DECLARE
    col_name TEXT;
    old_val TEXT;
    new_val TEXT;
BEGIN
    -- Loop through all columns and log changes
    FOR col_name IN
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'walltrack'
        AND table_name = TG_TABLE_NAME
        AND column_name NOT IN ('id', 'updated_at', 'updated_by')
    LOOP
        EXECUTE format('SELECT ($1).%I::TEXT', col_name) INTO old_val USING OLD;
        EXECUTE format('SELECT ($1).%I::TEXT', col_name) INTO new_val USING NEW;

        IF old_val IS DISTINCT FROM new_val THEN
            INSERT INTO walltrack.config_audit_log (
                config_table,
                config_key,
                old_value,
                new_value,
                changed_by
            ) VALUES (
                TG_TABLE_NAME,
                col_name,
                old_val,
                new_val,
                COALESCE(NEW.updated_by, 'system')
            );
        END IF;
    END LOOP;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for each config table
DROP TRIGGER IF EXISTS trg_trading_config_audit ON walltrack.trading_config;
CREATE TRIGGER trg_trading_config_audit
    AFTER UPDATE ON walltrack.trading_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_scoring_config_audit ON walltrack.scoring_config;
CREATE TRIGGER trg_scoring_config_audit
    AFTER UPDATE ON walltrack.scoring_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_discovery_config_audit ON walltrack.discovery_config;
CREATE TRIGGER trg_discovery_config_audit
    AFTER UPDATE ON walltrack.discovery_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_cluster_config_audit ON walltrack.cluster_config;
CREATE TRIGGER trg_cluster_config_audit
    AFTER UPDATE ON walltrack.cluster_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_risk_config_audit ON walltrack.risk_config;
CREATE TRIGGER trg_risk_config_audit
    AFTER UPDATE ON walltrack.risk_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_exit_config_audit ON walltrack.exit_config;
CREATE TRIGGER trg_exit_config_audit
    AFTER UPDATE ON walltrack.exit_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

DROP TRIGGER IF EXISTS trg_api_config_audit ON walltrack.api_config;
CREATE TRIGGER trg_api_config_audit
    AFTER UPDATE ON walltrack.api_config
    FOR EACH ROW EXECUTE FUNCTION walltrack.log_config_change();

-- ============================================================
-- PHASE 4: VERIFICATION QUERY
-- ============================================================

SELECT table_name,
       (SELECT COUNT(*) FROM information_schema.columns c
        WHERE c.table_schema = 'walltrack' AND c.table_name = t.table_name) as column_count
FROM information_schema.tables t
WHERE table_schema = 'walltrack'
AND table_name LIKE '%_config'
ORDER BY table_name;
