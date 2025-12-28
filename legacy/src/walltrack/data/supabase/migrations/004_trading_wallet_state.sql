-- Trading wallet state tracking for trade execution
-- Schema: walltrack

SET search_path TO walltrack, public;

-- =============================================================================
-- Trading Wallet State (single row, updated on changes)
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.trading_wallet_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    public_key VARCHAR(44) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'disconnected',
    safe_mode BOOLEAN NOT NULL DEFAULT false,
    safe_mode_reason VARCHAR(50),
    safe_mode_since TIMESTAMPTZ,
    error_message TEXT,
    last_validated TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Ensure only one row exists (trading wallet singleton)
    CONSTRAINT single_trading_wallet CHECK (
        id = '00000000-0000-0000-0000-000000000001'::uuid
    ),
    CONSTRAINT valid_status CHECK (
        status IN ('connected', 'disconnected', 'error', 'validating')
    ),
    CONSTRAINT valid_safe_mode_reason CHECK (
        safe_mode_reason IS NULL OR safe_mode_reason IN (
            'connection_failed', 'signing_failed', 'rpc_unavailable',
            'insufficient_balance', 'manual'
        )
    )
);

-- Trigger for auto-updating updated_at
CREATE TRIGGER update_trading_wallet_state_updated_at
    BEFORE UPDATE ON walltrack.trading_wallet_state
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Initialize single trading wallet state row
INSERT INTO walltrack.trading_wallet_state (id, public_key, status)
VALUES ('00000000-0000-0000-0000-000000000001', '', 'disconnected')
ON CONFLICT (id) DO NOTHING;

-- =============================================================================
-- Balance Snapshots for history and analytics
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.wallet_balance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    sol_balance_lamports BIGINT NOT NULL,
    sol_balance_ui DECIMAL(20, 9) NOT NULL,
    total_value_sol DECIMAL(20, 9) NOT NULL,
    token_count INTEGER NOT NULL DEFAULT 0,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_balance CHECK (sol_balance_lamports >= 0)
);

-- Index for time-series queries
CREATE INDEX IF NOT EXISTS idx_balance_snapshots_time
ON walltrack.wallet_balance_snapshots(snapshot_at DESC);

-- =============================================================================
-- Token Balance Snapshots (linked to wallet snapshots)
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.token_balance_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wallet_snapshot_id UUID REFERENCES walltrack.wallet_balance_snapshots(id) ON DELETE CASCADE,
    mint_address VARCHAR(44) NOT NULL,
    symbol VARCHAR(20),
    amount DECIMAL(30, 0) NOT NULL,
    decimals INTEGER NOT NULL,
    ui_amount DECIMAL(20, 9) NOT NULL,
    estimated_value_sol DECIMAL(20, 9),
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_token_snapshots_wallet
ON walltrack.token_balance_snapshots(wallet_snapshot_id);

CREATE INDEX IF NOT EXISTS idx_token_snapshots_mint
ON walltrack.token_balance_snapshots(mint_address);

-- =============================================================================
-- Safe Mode Events audit trail
-- =============================================================================

CREATE TABLE IF NOT EXISTS walltrack.safe_mode_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type VARCHAR(20) NOT NULL, -- 'entered', 'exited', 'exit_failed'
    reason VARCHAR(50),
    error_message TEXT,
    triggered_by VARCHAR(20) NOT NULL, -- 'auto', 'manual', 'recovery'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT valid_event_type CHECK (
        event_type IN ('entered', 'exited', 'exit_failed')
    ),
    CONSTRAINT valid_triggered_by CHECK (
        triggered_by IN ('auto', 'manual', 'recovery')
    )
);

CREATE INDEX IF NOT EXISTS idx_safe_mode_events_time
ON walltrack.safe_mode_events(created_at DESC);

-- =============================================================================
-- RLS Policies
-- =============================================================================

ALTER TABLE walltrack.trading_wallet_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE walltrack.wallet_balance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE walltrack.token_balance_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE walltrack.safe_mode_events ENABLE ROW LEVEL SECURITY;

-- Service role has full access
CREATE POLICY "Service role full access on trading_wallet_state"
ON walltrack.trading_wallet_state FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on wallet_balance_snapshots"
ON walltrack.wallet_balance_snapshots FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on token_balance_snapshots"
ON walltrack.token_balance_snapshots FOR ALL TO service_role USING (true);

CREATE POLICY "Service role full access on safe_mode_events"
ON walltrack.safe_mode_events FOR ALL TO service_role USING (true);

-- Anonymous/authenticated read access for dashboard
CREATE POLICY "Allow read on trading_wallet_state"
ON walltrack.trading_wallet_state FOR SELECT USING (true);

CREATE POLICY "Allow read on wallet_balance_snapshots"
ON walltrack.wallet_balance_snapshots FOR SELECT USING (true);

CREATE POLICY "Allow read on token_balance_snapshots"
ON walltrack.token_balance_snapshots FOR SELECT USING (true);

CREATE POLICY "Allow read on safe_mode_events"
ON walltrack.safe_mode_events FOR SELECT USING (true);

-- =============================================================================
-- Helper function for recording balance snapshots
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.record_balance_snapshot(
    p_sol_lamports BIGINT,
    p_sol_ui DECIMAL(20, 9),
    p_total_sol DECIMAL(20, 9),
    p_token_count INTEGER
)
RETURNS UUID AS $$
DECLARE
    v_snapshot_id UUID;
BEGIN
    INSERT INTO walltrack.wallet_balance_snapshots (
        sol_balance_lamports, sol_balance_ui, total_value_sol, token_count
    )
    VALUES (p_sol_lamports, p_sol_ui, p_total_sol, p_token_count)
    RETURNING id INTO v_snapshot_id;

    RETURN v_snapshot_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Helper function for recording safe mode events
-- =============================================================================

CREATE OR REPLACE FUNCTION walltrack.record_safe_mode_event(
    p_event_type VARCHAR(20),
    p_reason VARCHAR(50),
    p_error TEXT,
    p_triggered_by VARCHAR(20)
)
RETURNS UUID AS $$
DECLARE
    v_event_id UUID;
BEGIN
    INSERT INTO walltrack.safe_mode_events (
        event_type, reason, error_message, triggered_by
    )
    VALUES (p_event_type, p_reason, p_error, p_triggered_by)
    RETURNING id INTO v_event_id;

    RETURN v_event_id;
END;
$$ LANGUAGE plpgsql;
