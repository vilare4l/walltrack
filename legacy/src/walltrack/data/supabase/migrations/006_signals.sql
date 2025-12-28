-- Supabase migration: signals table for signal logging
-- Story 3-6: Signal Logging & Storage (FR18)

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tx_signature VARCHAR(100) NOT NULL UNIQUE,
    wallet_address VARCHAR(50) NOT NULL,
    token_address VARCHAR(50) NOT NULL,
    direction VARCHAR(10) NOT NULL,

    -- Transaction details
    amount_token DECIMAL(30, 10),
    amount_sol DECIMAL(20, 10),
    slot BIGINT,

    -- Scores
    final_score DECIMAL(5, 4),
    wallet_score DECIMAL(5, 4),
    cluster_score DECIMAL(5, 4),
    token_score DECIMAL(5, 4),
    context_score DECIMAL(5, 4),

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'received',
    eligibility_status VARCHAR(30),
    conviction_tier VARCHAR(20),

    -- Filter info
    filter_status VARCHAR(20),
    filter_reason TEXT,

    -- Trade link (FK to trades table when Epic 4 completes)
    trade_id UUID,

    -- Timestamps
    timestamp TIMESTAMPTZ NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processing_time_ms DECIMAL(10, 2),

    -- Metadata
    raw_factors JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for query performance (AC2, NFR23: 6 months of data)
CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_wallet ON signals(wallet_address, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_score ON signals(final_score DESC) WHERE final_score IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_eligibility ON signals(eligibility_status, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_signals_trade ON signals(trade_id) WHERE trade_id IS NOT NULL;

-- Composite index for common queries
CREATE INDEX IF NOT EXISTS idx_signals_wallet_score ON signals(wallet_address, final_score DESC, timestamp DESC);

-- Function for calculating averages
CREATE OR REPLACE FUNCTION get_signal_averages(start_ts TIMESTAMPTZ, end_ts TIMESTAMPTZ)
RETURNS TABLE(avg_score DECIMAL, avg_processing_ms DECIMAL) AS $$
BEGIN
    RETURN QUERY
    SELECT
        AVG(final_score)::DECIMAL,
        AVG(processing_time_ms)::DECIMAL
    FROM signals
    WHERE timestamp >= start_ts AND timestamp <= end_ts
    AND final_score IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Comment for documentation
COMMENT ON TABLE signals IS 'Signal logging table for all processed signals (FR18)';
COMMENT ON COLUMN signals.tx_signature IS 'Unique transaction signature from Solana';
COMMENT ON COLUMN signals.final_score IS 'Multi-factor composite score (0-1)';
COMMENT ON COLUMN signals.eligibility_status IS 'Trade eligibility: trade_eligible, below_threshold';
COMMENT ON COLUMN signals.conviction_tier IS 'Position sizing tier: high, standard, none';
COMMENT ON COLUMN signals.trade_id IS 'Link to executed trade (Epic 4)';
