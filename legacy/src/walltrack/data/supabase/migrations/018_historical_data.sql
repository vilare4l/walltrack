-- Migration: 018_historical_data.sql
-- Description: Historical data tables for backtesting
-- Epic 8: Backtesting & Scenario Analysis

-- ============================================================================
-- HISTORICAL SIGNALS TABLE
-- ============================================================================
-- Stores signal snapshots for backtest replay

CREATE TABLE IF NOT EXISTS historical_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    wallet_address VARCHAR(44) NOT NULL,
    token_address VARCHAR(44) NOT NULL,
    wallet_score DECIMAL(10, 6) NOT NULL,
    cluster_id UUID,
    cluster_amplification DECIMAL(10, 6) DEFAULT 1.0,
    token_price_usd DECIMAL(30, 18) NOT NULL,
    token_market_cap DECIMAL(30, 2),
    token_liquidity DECIMAL(30, 2),
    token_age_minutes INTEGER,
    computed_score DECIMAL(10, 6) NOT NULL,
    score_breakdown JSONB NOT NULL DEFAULT '{}',
    trade_eligible BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for date range queries (used in get_signals_for_range)
CREATE INDEX IF NOT EXISTS idx_historical_signals_timestamp
ON historical_signals(timestamp);

-- Index for wallet queries
CREATE INDEX IF NOT EXISTS idx_historical_signals_wallet
ON historical_signals(wallet_address);

-- Index for token queries
CREATE INDEX IF NOT EXISTS idx_historical_signals_token
ON historical_signals(token_address);

-- Compound index for date range filtering
CREATE INDEX IF NOT EXISTS idx_historical_signals_date_range
ON historical_signals(timestamp DESC, computed_score DESC);

-- ============================================================================
-- HISTORICAL PRICES TABLE
-- ============================================================================
-- Stores price data for P&L calculations during backtest

CREATE TABLE IF NOT EXISTS historical_prices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_address VARCHAR(44) NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    price_usd DECIMAL(30, 18) NOT NULL,
    source VARCHAR(50) DEFAULT 'dexscreener',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT unique_historical_price UNIQUE (token_address, timestamp)
);

-- Index for price timeline queries (used in get_price_timeline)
CREATE INDEX IF NOT EXISTS idx_historical_prices_token_time
ON historical_prices(token_address, timestamp);

-- Index for timestamp queries
CREATE INDEX IF NOT EXISTS idx_historical_prices_timestamp
ON historical_prices(timestamp);

-- ============================================================================
-- ROW LEVEL SECURITY
-- ============================================================================

ALTER TABLE historical_signals ENABLE ROW LEVEL SECURITY;
ALTER TABLE historical_prices ENABLE ROW LEVEL SECURITY;

CREATE POLICY historical_signals_policy ON historical_signals
    FOR ALL USING (true) WITH CHECK (true);

CREATE POLICY historical_prices_policy ON historical_prices
    FOR ALL USING (true) WITH CHECK (true);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE historical_signals IS 'Signal snapshots for backtest replay';
COMMENT ON TABLE historical_prices IS 'Historical price data for P&L calculations';
