-- Price history for positions
-- Partitioned by date for efficient cleanup
-- Story 10.5-7: Price History Collection

-- Create schema if not exists
CREATE SCHEMA IF NOT EXISTS walltrack;

-- Price history table (partitioned by recorded_at)
CREATE TABLE IF NOT EXISTS walltrack.price_history (
    id BIGSERIAL,
    position_id UUID NOT NULL,
    token_address VARCHAR(44) NOT NULL,

    -- Price data
    price DECIMAL(30, 12) NOT NULL,
    source VARCHAR(20) NOT NULL,

    -- Timestamp
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Partitioning
    PRIMARY KEY (id, recorded_at)
) PARTITION BY RANGE (recorded_at);

-- Create partitions for current and next month
CREATE TABLE IF NOT EXISTS walltrack.price_history_current PARTITION OF walltrack.price_history
    FOR VALUES FROM (DATE_TRUNC('month', NOW())) TO (DATE_TRUNC('month', NOW()) + INTERVAL '1 month');

CREATE TABLE IF NOT EXISTS walltrack.price_history_next PARTITION OF walltrack.price_history
    FOR VALUES FROM (DATE_TRUNC('month', NOW()) + INTERVAL '1 month') TO (DATE_TRUNC('month', NOW()) + INTERVAL '2 months');

-- Indexes for price_history
CREATE INDEX IF NOT EXISTS idx_price_history_position ON walltrack.price_history(position_id, recorded_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_history_token ON walltrack.price_history(token_address, recorded_at DESC);

-- Compressed price history (1-minute OHLC)
CREATE TABLE IF NOT EXISTS walltrack.price_history_compressed (
    id BIGSERIAL PRIMARY KEY,
    position_id UUID NOT NULL,
    token_address VARCHAR(44) NOT NULL,

    -- OHLC data
    period_start TIMESTAMPTZ NOT NULL,
    open_price DECIMAL(30, 12) NOT NULL,
    high_price DECIMAL(30, 12) NOT NULL,
    low_price DECIMAL(30, 12) NOT NULL,
    close_price DECIMAL(30, 12) NOT NULL,

    -- Sample count
    sample_count INTEGER NOT NULL DEFAULT 1,

    UNIQUE(position_id, period_start)
);

CREATE INDEX IF NOT EXISTS idx_price_compressed_position ON walltrack.price_history_compressed(position_id, period_start DESC);

-- Position price metrics (materialized for performance)
CREATE TABLE IF NOT EXISTS walltrack.position_price_metrics (
    position_id UUID PRIMARY KEY,

    -- Peak tracking
    peak_price DECIMAL(30, 12) NOT NULL,
    peak_at TIMESTAMPTZ NOT NULL,

    -- Current metrics
    current_price DECIMAL(30, 12),
    last_update TIMESTAMPTZ,

    -- Drawdown from peak
    max_drawdown_pct DECIMAL(10, 4) NOT NULL DEFAULT 0,
    current_drawdown_pct DECIMAL(10, 4) NOT NULL DEFAULT 0,

    -- PnL at peak
    unrealized_pnl_at_peak DECIMAL(20, 8),

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Foreign key reference to positions table
ALTER TABLE walltrack.position_price_metrics
    ADD CONSTRAINT fk_price_metrics_position
    FOREIGN KEY (position_id)
    REFERENCES walltrack.positions(id)
    ON DELETE CASCADE;

-- Function to create new monthly partitions
CREATE OR REPLACE FUNCTION walltrack.create_price_history_partition(partition_date DATE)
RETURNS VOID AS $$
DECLARE
    partition_name TEXT;
    start_date DATE;
    end_date DATE;
BEGIN
    partition_name := 'price_history_' || TO_CHAR(partition_date, 'YYYY_MM');
    start_date := DATE_TRUNC('month', partition_date);
    end_date := start_date + INTERVAL '1 month';

    EXECUTE FORMAT(
        'CREATE TABLE IF NOT EXISTS walltrack.%I PARTITION OF walltrack.price_history
         FOR VALUES FROM (%L) TO (%L)',
        partition_name, start_date, end_date
    );
END;
$$ LANGUAGE plpgsql;

-- Comments
COMMENT ON TABLE walltrack.price_history IS 'Real-time price history for positions (5-second intervals)';
COMMENT ON TABLE walltrack.price_history_compressed IS 'Compressed price history (1-minute OHLC) for older data';
COMMENT ON TABLE walltrack.position_price_metrics IS 'Materialized price metrics for positions (peak, drawdown)';
