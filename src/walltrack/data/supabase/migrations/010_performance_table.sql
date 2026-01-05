-- ============================================================================
-- Migration: 010_performance_table.sql (Materialized View Pattern)
-- Description: Create performance tracking table (1-to-1 with wallets)
-- Date: 2026-01-05
-- Story: 1.1 - Database Schema Migration & Mock Data (Extended)
-- Pattern: Materialized View Pattern
-- Dependencies: 003_wallets_table.sql
-- ============================================================================
--
-- 📝 INCLUSION JUSTIFICATION (Code Review Resolution - 2026-01-05)
--
-- This table was initially flagged as "scope creep" beyond Story 1.1's 7 core tables.
-- Decision: KEEP in Story 1.1 for the following reasons:
--
-- 1. **Tight Coupling:** Performance is a 1-to-1 relationship with wallets (FK)
--    Creating wallets without performance tracking would require immediate follow-up work
--
-- 2. **Data Foundation Completeness:** Story 1.1's objective is "validate complete data structure"
--    Performance metrics are essential to validate wallet tracking functionality
--
-- 3. **No Business Logic:** This is pure schema (CREATE TABLE), aligns with Story 1.1 scope
--    Implementation of performance calculation workers belongs to Epic 4 (different story)
--
-- 4. **Numbering Resolution:** Renumbered from 008 → 010 to resolve conflict with mock data
--    Final sequence: 000-007 (core tables), 008-009 (mock data), 010-011 (supplemental tables)
--
-- Approved by: Code Review (Option B - Renumber and Keep)
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.performance (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relations (1-to-1 with wallets)
    wallet_id UUID NOT NULL UNIQUE REFERENCES walltrack.wallets(id) ON DELETE CASCADE,

    -- Win Rate
    total_positions INTEGER NOT NULL DEFAULT 0,
    winning_positions INTEGER NOT NULL DEFAULT 0,
    losing_positions INTEGER NOT NULL DEFAULT 0,
    win_rate NUMERIC(5,2),  -- (winning_positions / total_positions) * 100

    -- PnL
    total_pnl_usd NUMERIC(12,2) NOT NULL DEFAULT 0.00,
    total_pnl_percent NUMERIC(8,4),
    average_win_usd NUMERIC(12,2),
    average_loss_usd NUMERIC(12,2),
    profit_ratio NUMERIC(8,4),  -- average_win / abs(average_loss)

    -- Signals (rolling windows)
    signal_count_all INTEGER NOT NULL DEFAULT 0,
    signal_count_30d INTEGER NOT NULL DEFAULT 0,
    signal_count_7d INTEGER NOT NULL DEFAULT 0,
    signal_count_24h INTEGER NOT NULL DEFAULT 0,

    -- Positions Time (rolling windows)
    positions_30d INTEGER NOT NULL DEFAULT 0,
    positions_7d INTEGER NOT NULL DEFAULT 0,
    positions_24h INTEGER NOT NULL DEFAULT 0,

    -- Best/Worst
    best_trade_pnl_usd NUMERIC(12,2),
    best_trade_pnl_percent NUMERIC(8,4),
    worst_trade_pnl_usd NUMERIC(12,2),
    worst_trade_pnl_percent NUMERIC(8,4),

    -- Streaks
    current_win_streak INTEGER NOT NULL DEFAULT 0,
    current_loss_streak INTEGER NOT NULL DEFAULT 0,
    max_win_streak INTEGER NOT NULL DEFAULT 0,
    max_loss_streak INTEGER NOT NULL DEFAULT 0,

    -- Metadata
    last_calculated_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

COMMENT ON TABLE walltrack.performance IS 'Materialized view - Pre-calculated wallet metrics (refreshed daily at 00:00 UTC).';
COMMENT ON COLUMN walltrack.performance.signal_count_30d IS 'Rolling window (30 days) - Recalculated daily.';
COMMENT ON COLUMN walltrack.performance.profit_ratio IS 'Risk/Reward ratio: average_win / abs(average_loss). Ex: 2.5 = wins 2.5x bigger than losses.';

CREATE INDEX idx_performance_wallet_id ON walltrack.performance(wallet_id);
CREATE INDEX idx_performance_win_rate ON walltrack.performance(win_rate DESC);
CREATE INDEX idx_performance_total_pnl ON walltrack.performance(total_pnl_usd DESC);

CREATE TRIGGER performance_updated_at BEFORE UPDATE ON walltrack.performance FOR EACH ROW EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Rollback
-- DROP TABLE IF EXISTS walltrack.performance CASCADE;
