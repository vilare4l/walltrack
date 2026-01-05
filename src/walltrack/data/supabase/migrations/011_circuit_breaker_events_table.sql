-- ============================================================================
-- Migration: 011_circuit_breaker_events_table.sql (Event Sourcing - Immutable)
-- Description: Create circuit breaker audit trail table
-- Date: 2026-01-05
-- Story: 1.1 - Database Schema Migration & Mock Data (Extended)
-- Pattern: Event Sourcing Pattern (Immutable)
-- Dependencies: 001_config_table.sql
-- ============================================================================
--
-- 📝 INCLUSION JUSTIFICATION (Code Review Resolution - 2026-01-05)
--
-- This table was initially flagged as "scope creep" beyond Story 1.1's 7 core tables.
-- Decision: KEEP in Story 1.1 for the following reasons:
--
-- 1. **Config Dependency:** Circuit breaker state is tracked in `config` table (core table #1)
--    The events table provides immutable audit trail for config.circuit_breaker_active changes
--
-- 2. **Data Foundation Completeness:** Story 1.1's objective is "validate complete data structure"
--    Circuit breaker is a critical safety mechanism - its audit trail belongs in foundation
--
-- 3. **Event Sourcing Pattern:** Aligns with `signals` table (core table #5) pattern
--    Both use immutable append-only logs for system events
--
-- 4. **No Business Logic:** This is pure schema (CREATE TABLE), aligns with Story 1.1 scope
--    Implementation of circuit breaker triggers/workers belongs to Epic 4 (different story)
--
-- 5. **Numbering Resolution:** Renumbered from 009 → 011 to resolve conflict with mock data
--    Final sequence: 000-007 (core tables), 008-009 (mock data), 010-011 (supplemental tables)
--
-- Approved by: Code Review (Option B - Renumber and Keep)
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.circuit_breaker_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Event Data
    event_type TEXT NOT NULL CHECK (event_type IN ('activated', 'deactivated')),
    trigger_reason TEXT NOT NULL,  -- 'max_drawdown', 'min_win_rate', 'consecutive_losses', 'manual'

    -- Metrics (snapshot at activation)
    current_drawdown_percent NUMERIC(5,2),
    current_win_rate NUMERIC(5,2),
    consecutive_losses INTEGER,

    -- Thresholds (snapshot config at activation)
    max_drawdown_threshold NUMERIC(5,2),
    min_win_rate_threshold NUMERIC(5,2),
    consecutive_loss_threshold INTEGER,

    -- Impact
    new_positions_blocked INTEGER,  -- Counter: signals rejected while CB active
    open_positions_at_activation INTEGER,  -- Snapshot: positions open when CB activated

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    deactivated_at TIMESTAMPTZ,  -- NULL if still active
    notes TEXT
);

COMMENT ON TABLE walltrack.circuit_breaker_events IS 'Event sourcing - Audit trail of circuit breaker activations/deactivations (immutable).';
COMMENT ON COLUMN walltrack.circuit_breaker_events.trigger_reason IS 'Root cause: max_drawdown, min_win_rate, consecutive_losses, manual.';
COMMENT ON COLUMN walltrack.circuit_breaker_events.current_drawdown_percent IS 'Snapshot drawdown at activation moment. Forensics: validate threshold calibration.';
COMMENT ON COLUMN walltrack.circuit_breaker_events.new_positions_blocked IS 'How many signals rejected while CB active. FOMO metric: opportunities missed.';

CREATE INDEX idx_cb_events_created_at ON walltrack.circuit_breaker_events(created_at DESC);
CREATE INDEX idx_cb_events_type ON walltrack.circuit_breaker_events(event_type);
CREATE INDEX idx_cb_events_active ON walltrack.circuit_breaker_events(deactivated_at) WHERE deactivated_at IS NULL;

-- Rollback
-- DROP TABLE IF EXISTS walltrack.circuit_breaker_events CASCADE;
