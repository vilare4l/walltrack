-- Daily snapshots for tracking starting capital and daily P&L
-- Story 10.5-10: Daily Loss Limit

CREATE TABLE IF NOT EXISTS walltrack.daily_snapshots (
    id BIGSERIAL PRIMARY KEY,
    date DATE NOT NULL UNIQUE,
    starting_capital DECIMAL(20, 8) NOT NULL,

    -- End of day values (updated by job)
    ending_capital DECIMAL(20, 8),
    realized_pnl DECIMAL(20, 8),
    unrealized_pnl DECIMAL(20, 8),
    total_pnl DECIMAL(20, 8),
    pnl_pct DECIMAL(10, 4),

    -- Trade statistics
    trades_count INTEGER DEFAULT 0,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,

    -- Limits status
    daily_limit_hit BOOLEAN DEFAULT FALSE,
    daily_limit_hit_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for date lookups
CREATE INDEX IF NOT EXISTS idx_daily_snapshots_date ON walltrack.daily_snapshots(date DESC);

-- Comment
COMMENT ON TABLE walltrack.daily_snapshots IS 'Daily snapshots for tracking starting capital and P&L';
