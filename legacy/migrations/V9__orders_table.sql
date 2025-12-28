-- WallTrack Orders Table Migration
-- Date: 2024-12-26
-- Purpose: Create orders table for order lifecycle management
-- Version: V9

-- ============================================================
-- PHASE 1: CREATE ORDERS TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS walltrack.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Order Type and Direction
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('entry', 'exit')),
    side VARCHAR(10) NOT NULL CHECK (side IN ('buy', 'sell')),

    -- References
    signal_id VARCHAR(100),  -- For ENTRY orders
    position_id UUID,        -- For EXIT orders (references positions table)

    -- Token Info
    token_address VARCHAR(44) NOT NULL,
    token_symbol VARCHAR(20),

    -- Amounts
    amount_sol DECIMAL(20, 8) NOT NULL,
    amount_tokens DECIMAL(30, 8),

    -- Pricing
    expected_price DECIMAL(30, 12) NOT NULL,
    actual_price DECIMAL(30, 12),
    max_slippage_bps INTEGER NOT NULL DEFAULT 100,

    -- Status
    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'submitted', 'confirming', 'filled', 'failed', 'cancelled')),

    -- Execution Details
    tx_signature VARCHAR(100),
    filled_at TIMESTAMPTZ,

    -- Retry Management
    attempt_count INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    last_error TEXT,
    next_retry_at TIMESTAMPTZ,

    -- Simulation Mode
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,

    -- Locking (for retry worker concurrency control)
    locked_until TIMESTAMPTZ,
    locked_by VARCHAR(50),

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ============================================================
-- PHASE 2: CREATE INDEXES
-- ============================================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_orders_status ON walltrack.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_position ON walltrack.orders(position_id) WHERE position_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_orders_signal ON walltrack.orders(signal_id) WHERE signal_id IS NOT NULL;

-- Retry worker index (orders needing retry with locking)
CREATE INDEX IF NOT EXISTS idx_orders_retry
    ON walltrack.orders(status, next_retry_at, locked_until)
    WHERE status IN ('pending', 'failed');

-- Index for retry candidate queries (prioritized)
CREATE INDEX IF NOT EXISTS idx_orders_retry_candidates
    ON walltrack.orders(order_type DESC, created_at ASC)
    WHERE status IN ('pending', 'failed') AND next_retry_at IS NOT NULL;

-- Active orders (non-terminal)
CREATE INDEX IF NOT EXISTS idx_orders_active
    ON walltrack.orders(created_at DESC)
    WHERE status NOT IN ('filled', 'cancelled');

-- History queries
CREATE INDEX IF NOT EXISTS idx_orders_created ON walltrack.orders(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_orders_filled ON walltrack.orders(filled_at DESC)
    WHERE filled_at IS NOT NULL;

-- Token-based queries
CREATE INDEX IF NOT EXISTS idx_orders_token ON walltrack.orders(token_address);

-- Simulation filtering
CREATE INDEX IF NOT EXISTS idx_orders_simulated ON walltrack.orders(is_simulated, created_at DESC);

-- ============================================================
-- PHASE 3: CREATE UPDATED_AT TRIGGER
-- ============================================================

CREATE OR REPLACE FUNCTION walltrack.update_orders_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_orders_updated ON walltrack.orders;
CREATE TRIGGER trg_orders_updated
    BEFORE UPDATE ON walltrack.orders
    FOR EACH ROW EXECUTE FUNCTION walltrack.update_orders_timestamp();

-- ============================================================
-- PHASE 4: CREATE ORDER HISTORY VIEW
-- ============================================================

CREATE OR REPLACE VIEW walltrack.order_history AS
SELECT
    o.id,
    o.order_type,
    o.side,
    o.token_address,
    o.token_symbol,
    o.amount_sol,
    o.amount_tokens,
    o.expected_price,
    o.actual_price,
    o.status,
    o.tx_signature,
    o.attempt_count,
    o.last_error,
    o.is_simulated,
    o.created_at,
    o.filled_at,

    -- Calculated fields
    CASE
        WHEN o.actual_price IS NOT NULL AND o.expected_price > 0 THEN
            ROUND(ABS(o.actual_price - o.expected_price) / o.expected_price * 10000)
        ELSE NULL
    END AS slippage_bps,

    EXTRACT(EPOCH FROM (COALESCE(o.filled_at, NOW()) - o.created_at)) AS duration_seconds,

    -- Position info (for EXIT orders)
    p.entry_price AS position_entry_price,
    p.entry_amount_sol AS position_entry_sol,

    -- Signal info (for ENTRY orders)
    s.score AS signal_score

FROM walltrack.orders o
LEFT JOIN walltrack.positions p ON o.position_id = p.id
LEFT JOIN walltrack.signals s ON o.signal_id = s.id
ORDER BY o.created_at DESC;

-- ============================================================
-- PHASE 5: CREATE ORDER STATS VIEW
-- ============================================================

CREATE OR REPLACE VIEW walltrack.order_stats AS
SELECT
    is_simulated,
    order_type,
    status,
    COUNT(*) as count,
    AVG(attempt_count) as avg_attempts,
    AVG(CASE WHEN slippage_bps IS NOT NULL THEN slippage_bps ELSE NULL END) as avg_slippage_bps,
    MIN(created_at) as first_order,
    MAX(created_at) as last_order
FROM (
    SELECT
        o.*,
        CASE
            WHEN o.actual_price IS NOT NULL AND o.expected_price > 0 THEN
                ABS(o.actual_price - o.expected_price) / o.expected_price * 10000
            ELSE NULL
        END AS slippage_bps
    FROM walltrack.orders o
) sub
GROUP BY is_simulated, order_type, status;

-- ============================================================
-- PHASE 6: CREATE ORDER STATUS LOG TABLE
-- ============================================================

CREATE TABLE IF NOT EXISTS walltrack.order_status_log (
    id BIGSERIAL PRIMARY KEY,
    order_id UUID NOT NULL REFERENCES walltrack.orders(id) ON DELETE CASCADE,
    old_status VARCHAR(20),
    new_status VARCHAR(20) NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW(),
    details TEXT
);

-- Index for fast lookup
CREATE INDEX IF NOT EXISTS idx_order_status_log_order ON walltrack.order_status_log(order_id, changed_at);

-- Trigger to log status changes
CREATE OR REPLACE FUNCTION walltrack.log_order_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.status IS DISTINCT FROM NEW.status THEN
        INSERT INTO walltrack.order_status_log (order_id, old_status, new_status, details)
        VALUES (NEW.id, OLD.status, NEW.status, NEW.last_error);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_order_status_change ON walltrack.orders;
CREATE TRIGGER trg_order_status_change
    AFTER UPDATE ON walltrack.orders
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.log_order_status_change();
