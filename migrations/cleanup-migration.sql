-- WallTrack Database Cleanup Migration
-- Date: 2024-12-26
-- Purpose: Remove orphan tables and align schema with code

-- ============================================================
-- PHASE 1: DROP ORPHAN TABLES (not used by any code)
-- ============================================================

-- Analytics tables (backtest/calibration/patterns removed from code)
DROP TABLE IF EXISTS walltrack.accuracy_metrics CASCADE;
DROP TABLE IF EXISTS walltrack.calibration_runs CASCADE;
DROP TABLE IF EXISTS walltrack.pattern_analysis CASCADE;
DROP TABLE IF EXISTS walltrack.performance_analytics CASCADE;
DROP TABLE IF EXISTS walltrack.backtest_results CASCADE;

-- Discovery tables (not implemented in code)
DROP TABLE IF EXISTS walltrack.discovery_config CASCADE;
DROP TABLE IF EXISTS walltrack.discovery_runs CASCADE;
DROP TABLE IF EXISTS walltrack.discovery_run_wallets CASCADE;

-- Redundant/unused config tables
DROP TABLE IF EXISTS walltrack.config CASCADE;  -- Replaced by system_config
DROP TABLE IF EXISTS walltrack.risk_config CASCADE;

-- Cache tables (not used)
DROP TABLE IF EXISTS walltrack.signal_cache CASCADE;
DROP TABLE IF EXISTS walltrack.token_price_history CASCADE;
DROP TABLE IF EXISTS walltrack.historical_prices CASCADE;

-- Test table
DROP TABLE IF EXISTS walltrack.test_connection CASCADE;

-- ============================================================
-- PHASE 2: VERIFY REMAINING TABLES
-- ============================================================

-- These tables should remain (actively used by code):
--
-- Core Trading:
--   - wallets          (discovery/profiler)
--   - signals          (signal pipeline)
--   - positions        (position management)
--   - trades           (trade outcomes)
--   - trade_outcomes   (feedback loop)
--   - exit_executions  (exit management)
--   - exit_strategies  (exit config)
--
-- Risk Management:
--   - system_config           (global config)
--   - circuit_breaker_triggers (risk events)
--   - capital_snapshots       (capital tracking)
--
-- Monitoring:
--   - webhook_logs     (helius webhooks)
--   - alerts           (system alerts)
--   - wallet_metrics   (wallet scores)
--   - historical_signals (signal history for UI)
--
-- Position Sizing:
--   - position_sizing_config  (sizing rules)

-- ============================================================
-- PHASE 3: LIST REMAINING TABLES (verification query)
-- ============================================================

SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'walltrack'
ORDER BY table_name;

-- Expected output after cleanup:
-- alerts
-- capital_snapshots
-- circuit_breaker_triggers
-- exit_executions
-- exit_strategies
-- historical_signals
-- position_sizing_config
-- positions
-- signals
-- system_config
-- trade_outcomes
-- trades
-- wallet_metrics
-- wallets
-- webhook_logs
