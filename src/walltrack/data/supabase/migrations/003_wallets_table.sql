-- ============================================================================
-- Migration: 003_wallets_table.sql
-- Description: Create wallets table (watchlist registry)
-- Date: 2025-01-05
-- Story: 1.1 - Database Schema Migration & Mock Data
-- Pattern: Registry Pattern
-- Dependencies: 002_exit_strategies_table.sql
-- ============================================================================
-- ⚠️ CODE REVIEW NOTE: Header corrected from "Epic 3" to "Story 1.1" (2026-01-05)
-- ============================================================================

-- Create wallets table
CREATE TABLE IF NOT EXISTS walltrack.wallets (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    address TEXT NOT NULL UNIQUE,
    label TEXT,

    -- Configuration
    mode TEXT NOT NULL DEFAULT 'simulation'
        CHECK (mode IN ('simulation', 'live')),

    -- Relations
    exit_strategy_id UUID NOT NULL
        REFERENCES walltrack.exit_strategies(id)
        ON DELETE RESTRICT,

    -- Discovery Context
    discovery_source TEXT
        CHECK (discovery_source IN ('twitter', 'telegram', 'scanner', 'referral', 'manual', 'other')),
    discovery_date DATE,
    discovery_notes TEXT,

    -- Initial Performance Baseline
    initial_win_rate_percent NUMERIC(5,2)
        CHECK (initial_win_rate_percent >= 0 AND initial_win_rate_percent <= 100),
    initial_trades_observed INTEGER
        CHECK (initial_trades_observed >= 0),
    initial_avg_pnl_percent NUMERIC(8,4),
    observation_period_days INTEGER
        CHECK (observation_period_days > 0),

    -- Helius Webhook Sync (Global webhook, per-wallet tracking)
    helius_synced_at TIMESTAMPTZ,
    helius_sync_status TEXT DEFAULT 'pending'
        CHECK (helius_sync_status IN ('pending', 'synced', 'error')),

    -- Status
    is_active BOOLEAN NOT NULL DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    last_signal_at TIMESTAMPTZ,
    notes TEXT
);

-- ============================================================================
-- Documentation (COMMENT ON)
-- ============================================================================

COMMENT ON TABLE walltrack.wallets IS
'Watchlist registry - Wallets Solana to track with discovery context and performance baseline.
Pattern: Registry Pattern (watchlist configuration).
Helius webhook: GLOBAL (1 webhook for all wallets, not 1 per wallet).
Batch sync every 5 min to update webhook address list.';

-- Identity group
COMMENT ON COLUMN walltrack.wallets.address IS
'Solana wallet address (base58, 32-44 chars). UNIQUE - One wallet = one configuration.';

COMMENT ON COLUMN walltrack.wallets.label IS
'Human-readable label for UI (ex: "CryptoWhale #1", "DegenApe"). Optional.';

-- Configuration group
COMMENT ON COLUMN walltrack.wallets.mode IS
'Trading mode: simulation (paper trading) or live (real capital).
Default simulation for safety - promote to live after validation period.';

-- Relations group
COMMENT ON COLUMN walltrack.wallets.exit_strategy_id IS
'FK to exit_strategies - Default exit strategy for this wallet.
IMPORTANT: Override at position level (positions.exit_strategy_override), not here.
NOT NULL - Every wallet must have a default strategy.';

-- Discovery group
COMMENT ON COLUMN walltrack.wallets.discovery_source IS
'Discovery channel: twitter, telegram, scanner, referral, manual, other.
Audit trail - Enables analysis of which sources produce best wallets.';

COMMENT ON COLUMN walltrack.wallets.discovery_date IS
'Date when wallet was discovered. Used for cohort analysis.';

COMMENT ON COLUMN walltrack.wallets.discovery_notes IS
'Free-text discovery context (ex: "Found via @CryptoGuru thread - Focus memecoins").
Useful for justifying wallet addition decisions.';

-- Initial Performance group
COMMENT ON COLUMN walltrack.wallets.initial_win_rate_percent IS
'Win rate observed BEFORE adding to watchlist. Baseline for comparison.
Used to detect degradation: if actual_win_rate < initial_win_rate * 0.8 → Red flag.';

COMMENT ON COLUMN walltrack.wallets.initial_trades_observed IS
'Number of trades analyzed during observation period.
Used to calculate initial_win_rate_percent and validate statistical significance.';

COMMENT ON COLUMN walltrack.wallets.initial_avg_pnl_percent IS
'Average PnL % observed during observation period.
Formula: SUM(pnl_percent) / initial_trades_observed.
Baseline to compare against actual performance.';

COMMENT ON COLUMN walltrack.wallets.observation_period_days IS
'Observation period duration in days (ex: 7, 14, 30).
Context for initial metrics - 30 days > 7 days for statistical reliability.';

-- Helius Sync group
COMMENT ON COLUMN walltrack.wallets.helius_synced_at IS
'Timestamp of last sync to Helius global webhook.
NULL = Never synced → Not monitored → No signals received.
Batch sync every 5 min updates this for active wallets.';

COMMENT ON COLUMN walltrack.wallets.helius_sync_status IS
'Sync status: pending (not yet synced), synced (monitored), error (sync failed).
CRITICAL: is_active=true AND helius_sync_status!=synced → Wallet NOT monitored!';

-- Status group
COMMENT ON COLUMN walltrack.wallets.is_active IS
'Active/inactive flag. Inactive wallets removed from Helius webhook (no signals).
Pause mechanism - is_active=false preserves history without deletion.';

-- Metadata group
COMMENT ON COLUMN walltrack.wallets.last_signal_at IS
'Timestamp of last signal received from Helius for this wallet.
Health check: is_active=true AND last_signal_at IS NULL/old → Dead wallet or sync issue.';

-- ============================================================================
-- Indexes
-- ============================================================================

-- Core lookups
CREATE INDEX IF NOT EXISTS idx_wallets_address
    ON walltrack.wallets(address);

CREATE INDEX IF NOT EXISTS idx_wallets_active
    ON walltrack.wallets(is_active);

-- Mode filter (active wallets only)
CREATE INDEX IF NOT EXISTS idx_wallets_mode
    ON walltrack.wallets(mode)
    WHERE is_active = true;

-- Health checks
CREATE INDEX IF NOT EXISTS idx_wallets_last_signal
    ON walltrack.wallets(last_signal_at DESC);

CREATE INDEX IF NOT EXISTS idx_wallets_sync_health
    ON walltrack.wallets(helius_synced_at, last_signal_at)
    WHERE is_active = true;

-- Batch sync targets
CREATE INDEX IF NOT EXISTS idx_wallets_sync_pending
    ON walltrack.wallets(helius_sync_status)
    WHERE is_active = true AND helius_sync_status = 'pending';

-- Relations
CREATE INDEX IF NOT EXISTS idx_wallets_exit_strategy_id
    ON walltrack.wallets(exit_strategy_id);

-- Analytics
CREATE INDEX IF NOT EXISTS idx_wallets_discovery_source
    ON walltrack.wallets(discovery_source)
    WHERE discovery_source IS NOT NULL;

-- ============================================================================
-- Triggers
-- ============================================================================

-- Auto-update updated_at
CREATE TRIGGER wallets_updated_at
    BEFORE UPDATE ON walltrack.wallets
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- ============================================================================
-- Validation Constraints
-- ============================================================================

-- Solana address format validation (base58, 32-44 chars)
ALTER TABLE walltrack.wallets
    ADD CONSTRAINT wallets_address_format
    CHECK (address ~ '^[1-9A-HJ-NP-Za-km-z]{32,44}$');

-- ============================================================================
-- Rollback Script (commented for safety)
-- ============================================================================

-- DROP TABLE IF EXISTS walltrack.wallets CASCADE;
-- -- Warning: CASCADE will drop dependent objects:
-- -- - positions.wallet_id FK
-- -- - signals.wallet_address FK (if exists)
-- -- - performance.wallet_id FK

-- ============================================================================
-- Usage Examples
-- ============================================================================

-- Example 1: Add wallet to watchlist (simulation mode)
/*
INSERT INTO walltrack.wallets (
    address,
    label,
    mode,
    exit_strategy_id,
    discovery_source,
    discovery_date,
    discovery_notes,
    initial_win_rate_percent,
    initial_trades_observed,
    initial_avg_pnl_percent,
    observation_period_days
) VALUES (
    'ABC123...XYZ789',
    'CryptoWhale #1',
    'simulation',
    'uuid-strategy-default',
    'twitter',
    '2025-01-05',
    'Found via @CryptoGuru thread - Focus low-cap memecoins',
    68.00,
    25,
    12.50,
    14
);
*/

-- Example 2: Promote wallet to live mode
/*
UPDATE walltrack.wallets
SET mode = 'live',
    notes = 'Promoted to live after 30 days simulation - 65% win rate confirmed'
WHERE address = 'ABC123...XYZ789'
  AND mode = 'simulation';
*/

-- Example 3: Health check - Active wallets not synced
/*
SELECT
    address,
    label,
    helius_sync_status,
    helius_synced_at,
    EXTRACT(EPOCH FROM (NOW() - created_at)) / 60 AS minutes_since_creation
FROM walltrack.wallets
WHERE is_active = true
  AND helius_sync_status != 'synced';
*/

-- Example 4: Detect silent wallets (no signals > 7 days)
/*
SELECT
    address,
    label,
    last_signal_at,
    EXTRACT(DAY FROM NOW() - last_signal_at) AS days_silent
FROM walltrack.wallets
WHERE is_active = true
  AND helius_sync_status = 'synced'
  AND (last_signal_at IS NULL OR last_signal_at < NOW() - INTERVAL '7 days')
ORDER BY last_signal_at ASC NULLS FIRST;
*/
