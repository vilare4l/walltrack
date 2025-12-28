-- Trade executions log
-- Schema: walltrack

SET search_path TO walltrack, public;

-- =============================================================================
-- Trades table
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    signal_id UUID REFERENCES walltrack.signals(id),

    -- Trade details
    direction TEXT NOT NULL CHECK (direction IN ('buy', 'sell')),
    token_address TEXT NOT NULL,
    input_mint TEXT NOT NULL,
    output_mint TEXT NOT NULL,

    -- Amounts
    input_amount BIGINT NOT NULL,
    output_amount BIGINT,
    output_amount_min BIGINT,
    slippage_bps INTEGER NOT NULL,

    -- Execution
    status TEXT NOT NULL DEFAULT 'pending',
    tx_signature TEXT UNIQUE,
    quote_source TEXT NOT NULL DEFAULT 'jupiter',
    entry_price DECIMAL(30, 18),
    execution_time_ms DECIMAL(10, 2),

    -- Failure tracking
    failure_reason TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    submitted_at TIMESTAMPTZ,
    confirmed_at TIMESTAMPTZ,

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN (
        'pending', 'quoting', 'signing', 'submitted',
        'confirming', 'success', 'failed', 'retry'
    )),
    CONSTRAINT valid_failure_reason CHECK (
        failure_reason IS NULL OR failure_reason IN (
            'quote_failed', 'slippage_exceeded', 'insufficient_balance',
            'transaction_expired', 'network_error', 'rpc_error', 'unknown'
        )
    )
);

-- Trigger for auto-updating updated_at if exists
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        -- No updated_at column in trades, skip
        NULL;
    END IF;
END$$;

-- Indexes
CREATE INDEX IF NOT EXISTS idx_trades_signal ON walltrack.trades(signal_id);
CREATE INDEX IF NOT EXISTS idx_trades_token ON walltrack.trades(token_address);
CREATE INDEX IF NOT EXISTS idx_trades_status ON walltrack.trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_created ON walltrack.trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_signature ON walltrack.trades(tx_signature)
    WHERE tx_signature IS NOT NULL;

-- =============================================================================
-- Trade execution metrics (aggregated)
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.trade_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    hour INTEGER NOT NULL CHECK (hour >= 0 AND hour < 24),

    -- Counts
    total_trades INTEGER NOT NULL DEFAULT 0,
    successful_trades INTEGER NOT NULL DEFAULT 0,
    failed_trades INTEGER NOT NULL DEFAULT 0,

    -- Volumes
    total_input_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,
    total_output_sol DECIMAL(20, 9) NOT NULL DEFAULT 0,

    -- Performance
    avg_execution_time_ms DECIMAL(10, 2),
    avg_slippage_bps DECIMAL(10, 2),

    -- Source breakdown
    jupiter_trades INTEGER NOT NULL DEFAULT 0,
    raydium_trades INTEGER NOT NULL DEFAULT 0,

    UNIQUE(date, hour)
);

CREATE INDEX IF NOT EXISTS idx_trade_metrics_date ON walltrack.trade_metrics(date DESC);

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE walltrack.trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE walltrack.trade_metrics ENABLE ROW LEVEL SECURITY;

-- Service role full access
CREATE POLICY "Service role full access on trades"
ON walltrack.trades FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on trade_metrics"
ON walltrack.trade_metrics FOR ALL TO service_role USING (true);

-- Read access for dashboard
CREATE POLICY "Allow read on trades"
ON walltrack.trades FOR SELECT USING (true);

CREATE POLICY "Allow read on trade_metrics"
ON walltrack.trade_metrics FOR SELECT USING (true);

-- =============================================================================
-- Helper function to record trade
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.record_trade(
    p_signal_id UUID,
    p_direction TEXT,
    p_token_address TEXT,
    p_input_mint TEXT,
    p_output_mint TEXT,
    p_input_amount BIGINT,
    p_slippage_bps INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_trade_id UUID;
BEGIN
    INSERT INTO walltrack.trades (
        signal_id, direction, token_address, input_mint, output_mint,
        input_amount, slippage_bps, status
    )
    VALUES (
        p_signal_id, p_direction, p_token_address, p_input_mint, p_output_mint,
        p_input_amount, p_slippage_bps, 'pending'
    )
    RETURNING id INTO v_trade_id;

    RETURN v_trade_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Helper function to update trade result
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.update_trade_result(
    p_trade_id UUID,
    p_status TEXT,
    p_tx_signature TEXT,
    p_output_amount BIGINT,
    p_entry_price DECIMAL(30, 18),
    p_execution_time_ms DECIMAL(10, 2),
    p_failure_reason TEXT,
    p_error_message TEXT
)
RETURNS VOID AS $$
BEGIN
    UPDATE walltrack.trades
    SET
        status = p_status,
        tx_signature = p_tx_signature,
        output_amount = p_output_amount,
        entry_price = p_entry_price,
        execution_time_ms = p_execution_time_ms,
        failure_reason = p_failure_reason,
        error_message = p_error_message,
        confirmed_at = CASE WHEN p_status = 'success' THEN NOW() ELSE NULL END
    WHERE id = p_trade_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Function to update hourly trade metrics
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.update_trade_metrics()
RETURNS TRIGGER AS $$
DECLARE
    v_date DATE;
    v_hour INTEGER;
BEGIN
    v_date := DATE(NEW.created_at);
    v_hour := EXTRACT(HOUR FROM NEW.created_at);

    INSERT INTO walltrack.trade_metrics (date, hour, total_trades, successful_trades, failed_trades,
                                         total_input_sol, jupiter_trades, raydium_trades)
    VALUES (v_date, v_hour, 1,
            CASE WHEN NEW.status = 'success' THEN 1 ELSE 0 END,
            CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END,
            NEW.input_amount::DECIMAL / 1000000000,
            CASE WHEN NEW.quote_source = 'jupiter' THEN 1 ELSE 0 END,
            CASE WHEN NEW.quote_source = 'raydium' THEN 1 ELSE 0 END)
    ON CONFLICT (date, hour) DO UPDATE
    SET
        total_trades = trade_metrics.total_trades + 1,
        successful_trades = trade_metrics.successful_trades +
            CASE WHEN NEW.status = 'success' THEN 1 ELSE 0 END,
        failed_trades = trade_metrics.failed_trades +
            CASE WHEN NEW.status = 'failed' THEN 1 ELSE 0 END,
        total_input_sol = trade_metrics.total_input_sol +
            NEW.input_amount::DECIMAL / 1000000000,
        jupiter_trades = trade_metrics.jupiter_trades +
            CASE WHEN NEW.quote_source = 'jupiter' THEN 1 ELSE 0 END,
        raydium_trades = trade_metrics.raydium_trades +
            CASE WHEN NEW.quote_source = 'raydium' THEN 1 ELSE 0 END;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to update metrics on trade insert
CREATE TRIGGER update_trade_metrics_on_insert
    AFTER INSERT ON walltrack.trades
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_trade_metrics();
