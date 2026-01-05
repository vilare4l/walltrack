-- ============================================================================
-- Migration: 001_config_table.sql
-- Description: Create config table (singleton)
-- Date: 2025-01-05
-- Pattern: Configuration Singleton
-- Dependencies: 000_helper_functions.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.config (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Trading Parameters
    capital NUMERIC(12,2) NOT NULL DEFAULT 300.00,
    risk_per_trade_percent NUMERIC(5,2) NOT NULL DEFAULT 2.00,
    position_sizing_mode TEXT NOT NULL DEFAULT 'fixed_percent'
        CHECK (position_sizing_mode IN ('fixed_percent', 'kelly', 'martingale')),

    -- Risk Management
    slippage_tolerance_percent NUMERIC(5,2) NOT NULL DEFAULT 3.00,
    max_drawdown_percent NUMERIC(5,2) NOT NULL DEFAULT 20.00,
    min_win_rate_alert NUMERIC(5,2) NOT NULL DEFAULT 40.00,
    consecutive_max_loss_trigger INTEGER NOT NULL DEFAULT 6,

    -- Safety Thresholds
    safety_score_threshold NUMERIC(3,2) NOT NULL DEFAULT 0.60,
    min_liquidity_usd NUMERIC(12,2) NOT NULL DEFAULT 50000.00,
    max_top_10_holder_percent NUMERIC(5,2) NOT NULL DEFAULT 80.00,
    min_token_age_hours INTEGER NOT NULL DEFAULT 0,

    -- Monitoring
    price_polling_interval_seconds INTEGER NOT NULL DEFAULT 45,
    webhook_timeout_alert_hours INTEGER NOT NULL DEFAULT 48,
    max_price_staleness_minutes INTEGER NOT NULL DEFAULT 5,

    -- Status
    webhook_last_signal_at TIMESTAMPTZ,
    circuit_breaker_active BOOLEAN NOT NULL DEFAULT false,
    circuit_breaker_reason TEXT,
    circuit_breaker_activated_at TIMESTAMPTZ,

    -- Helius Webhook (Global)
    helius_webhook_id TEXT,
    helius_webhook_url TEXT,
    helius_webhook_secret TEXT,
    helius_last_sync_at TIMESTAMPTZ,
    helius_sync_error TEXT,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ============================================================================
-- Documentation
-- ============================================================================

COMMENT ON TABLE walltrack.config IS
'Configuration singleton - Global system parameters (1 row max).
Pattern: Configuration Singleton.
Helius webhook: GLOBAL (1 webhook for all wallets).';

COMMENT ON COLUMN walltrack.config.capital IS
'Total capital available for trading (USD). Updated manually when funds added/removed.';

COMMENT ON COLUMN walltrack.config.risk_per_trade_percent IS
'Risk per trade as % of capital. Formula: position_size = capital * risk_per_trade / stop_loss_percent.';

COMMENT ON COLUMN walltrack.config.max_drawdown_percent IS
'Maximum drawdown before circuit breaker activation (ex: -20%).';

COMMENT ON COLUMN walltrack.config.helius_webhook_id IS
'ID of global Helius webhook. Created once via API, stored here.';

COMMENT ON COLUMN walltrack.config.helius_last_sync_at IS
'Timestamp of last wallet list sync to Helius. Batch sync every 5 min.';

-- ============================================================================
-- Indexes
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_config_updated_at
    ON walltrack.config(updated_at);

-- ============================================================================
-- Triggers
-- ============================================================================

CREATE TRIGGER config_updated_at
    BEFORE UPDATE ON walltrack.config
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- ============================================================================
-- Singleton Constraint (1 row max)
-- ============================================================================

CREATE OR REPLACE FUNCTION walltrack.prevent_multiple_config_rows()
RETURNS TRIGGER AS $$
BEGIN
    IF (SELECT COUNT(*) FROM walltrack.config) >= 1 THEN
        RAISE EXCEPTION 'config table is singleton - only 1 row allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER config_singleton_check
    BEFORE INSERT ON walltrack.config
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.prevent_multiple_config_rows();

-- ============================================================================
-- Initial Data
-- ============================================================================

INSERT INTO walltrack.config (
    capital,
    risk_per_trade_percent,
    max_drawdown_percent,
    min_win_rate_alert,
    consecutive_max_loss_trigger
) VALUES (
    300.00,
    2.00,
    20.00,
    40.00,
    6
);

-- ============================================================================
-- Rollback (commented for safety)
-- ============================================================================

-- DROP TRIGGER IF EXISTS config_singleton_check ON walltrack.config;
-- DROP FUNCTION IF EXISTS walltrack.prevent_multiple_config_rows();
-- DROP TABLE IF EXISTS walltrack.config CASCADE;
