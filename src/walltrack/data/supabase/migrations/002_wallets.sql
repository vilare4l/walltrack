-- Wallets table for storing wallet data and profiles
-- Schema: walltrack

SET search_path TO walltrack, public;

-- =============================================================================
-- Wallets table
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.wallets (
    address VARCHAR(44) PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    score DECIMAL(5, 4) NOT NULL DEFAULT 0.5000,

    -- Profile metrics
    win_rate DECIMAL(5, 4) DEFAULT 0.0000,
    total_pnl DECIMAL(18, 4) DEFAULT 0.0000,
    avg_pnl_per_trade DECIMAL(18, 4) DEFAULT 0.0000,
    total_trades INTEGER DEFAULT 0,
    timing_percentile DECIMAL(5, 4) DEFAULT 0.5000,
    avg_hold_time_hours DECIMAL(10, 2) DEFAULT 0.00,
    preferred_hours INTEGER[] DEFAULT ARRAY[]::INTEGER[],
    avg_position_size_sol DECIMAL(18, 8) DEFAULT 0.00000000,

    -- Discovery metadata
    discovered_at TIMESTAMPTZ DEFAULT NOW(),
    discovery_count INTEGER DEFAULT 1,
    discovery_tokens TEXT[] DEFAULT ARRAY[]::TEXT[],

    -- Decay tracking
    decay_detected_at TIMESTAMPTZ,
    consecutive_losses INTEGER DEFAULT 0,
    rolling_win_rate DECIMAL(5, 4),

    -- Blacklist
    blacklisted_at TIMESTAMPTZ,
    blacklist_reason TEXT,

    -- Timestamps
    last_profiled_at TIMESTAMPTZ,
    last_signal_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('active', 'decay_detected', 'blacklisted', 'insufficient_data')),
    CONSTRAINT valid_score CHECK (score >= 0 AND score <= 1),
    CONSTRAINT valid_win_rate CHECK (win_rate >= 0 AND win_rate <= 1)
);

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_wallets_updated_at
    BEFORE UPDATE ON walltrack.wallets
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_wallets_status ON walltrack.wallets(status);
CREATE INDEX IF NOT EXISTS idx_wallets_score ON walltrack.wallets(score DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_win_rate ON walltrack.wallets(win_rate DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_last_signal ON walltrack.wallets(last_signal_at DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_discovered ON walltrack.wallets(discovered_at DESC);

-- RLS policies
ALTER TABLE walltrack.wallets ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow read access" ON walltrack.wallets FOR SELECT USING (true);
CREATE POLICY "Allow insert" ON walltrack.wallets FOR INSERT WITH CHECK (true);
CREATE POLICY "Allow update" ON walltrack.wallets FOR UPDATE USING (true);

-- =============================================================================
-- RPC function for incrementing wallet discovery
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.increment_wallet_discovery(
    wallet_address VARCHAR(44),
    new_tokens TEXT[]
)
RETURNS VOID AS $$
BEGIN
    UPDATE walltrack.wallets
    SET
        discovery_count = discovery_count + 1,
        discovery_tokens = (
            SELECT ARRAY(
                SELECT DISTINCT unnest(discovery_tokens || new_tokens)
            )
        ),
        updated_at = NOW()
    WHERE address = wallet_address;
END;
$$ LANGUAGE plpgsql;
