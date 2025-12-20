-- Migration: 012_wallet_metrics
-- Description: Wallet metrics and score history tables for feedback loop
-- Story: 6-2 Wallet Score Updates

-- Wallet metrics table
CREATE TABLE IF NOT EXISTS wallet_metrics (
    wallet_address TEXT PRIMARY KEY,
    current_score DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    lifetime_trades INTEGER DEFAULT 0,
    lifetime_wins INTEGER DEFAULT 0,
    lifetime_losses INTEGER DEFAULT 0,
    lifetime_pnl DECIMAL(30, 18) DEFAULT 0,
    rolling_trades INTEGER DEFAULT 0,
    rolling_wins INTEGER DEFAULT 0,
    rolling_pnl DECIMAL(30, 18) DEFAULT 0,
    last_trade_timestamp TIMESTAMPTZ,
    last_score_update TIMESTAMPTZ DEFAULT NOW(),
    is_flagged BOOLEAN DEFAULT FALSE,
    is_blacklisted BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for wallet metrics
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_score ON wallet_metrics(current_score);
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_flagged ON wallet_metrics(is_flagged) WHERE is_flagged = TRUE;
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_blacklisted ON wallet_metrics(is_blacklisted) WHERE is_blacklisted = TRUE;
CREATE INDEX IF NOT EXISTS idx_wallet_metrics_last_trade ON wallet_metrics(last_trade_timestamp DESC);

-- Wallet score history table
CREATE TABLE IF NOT EXISTS wallet_score_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_address TEXT NOT NULL,
    score DECIMAL(5, 4) NOT NULL,
    previous_score DECIMAL(5, 4) NOT NULL,
    change DECIMAL(5, 4) NOT NULL,
    update_type TEXT NOT NULL CHECK (update_type IN (
        'trade_outcome', 'manual_adjustment', 'decay_penalty', 'recalibration'
    )),
    trade_id UUID,
    reason TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for score history
CREATE INDEX IF NOT EXISTS idx_score_history_wallet ON wallet_score_history(wallet_address);
CREATE INDEX IF NOT EXISTS idx_score_history_created ON wallet_score_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_score_history_trade ON wallet_score_history(trade_id) WHERE trade_id IS NOT NULL;

-- Score update configuration (singleton)
CREATE TABLE IF NOT EXISTS score_update_config (
    id TEXT PRIMARY KEY DEFAULT 'current',
    base_win_increase DECIMAL(5, 4) DEFAULT 0.02,
    profit_multiplier DECIMAL(5, 4) DEFAULT 0.01,
    max_win_increase DECIMAL(5, 4) DEFAULT 0.10,
    base_loss_decrease DECIMAL(5, 4) DEFAULT 0.03,
    loss_multiplier DECIMAL(5, 4) DEFAULT 0.015,
    max_loss_decrease DECIMAL(5, 4) DEFAULT 0.15,
    decay_flag_threshold DECIMAL(5, 4) DEFAULT 0.30,
    blacklist_threshold DECIMAL(5, 4) DEFAULT 0.15,
    rolling_window_trades INTEGER DEFAULT 20,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Initialize config if not exists
INSERT INTO score_update_config (id)
VALUES ('current')
ON CONFLICT (id) DO NOTHING;

-- Enable Row Level Security
ALTER TABLE wallet_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE wallet_score_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE score_update_config ENABLE ROW LEVEL SECURITY;

-- RLS Policies for service role access
CREATE POLICY "Service role full access to wallet_metrics"
    ON wallet_metrics FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to wallet_score_history"
    ON wallet_score_history FOR ALL
    USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access to score_update_config"
    ON score_update_config FOR ALL
    USING (auth.role() = 'service_role');
