-- Migration: 007_config_behavioral_parameters.sql
-- Date: 2025-12-30
-- Story: 3.3 - Wallet Behavioral Profiling
-- Description: Add behavioral profiling configuration parameters to config table (key-value store)

-- Insert behavioral profiling configuration parameters
-- Using INSERT ... ON CONFLICT to make migration idempotent
INSERT INTO walltrack.config (key, value)
VALUES
    ('behavioral_min_trades', '10'),
    ('behavioral_confidence_high', '50'),
    ('behavioral_confidence_medium', '10'),
    ('position_size_small_max', '1.0'),
    ('position_size_medium_max', '5.0'),
    ('hold_duration_scalper_max', '3600'),
    ('hold_duration_day_trader_max', '86400'),
    ('hold_duration_swing_trader_max', '604800')
ON CONFLICT (key) DO NOTHING;

-- Rollback (commented):
-- DELETE FROM walltrack.config WHERE key IN (
--   'behavioral_min_trades',
--   'behavioral_confidence_high',
--   'behavioral_confidence_medium',
--   'position_size_small_max',
--   'position_size_medium_max',
--   'hold_duration_scalper_max',
--   'hold_duration_day_trader_max',
--   'hold_duration_swing_trader_max'
-- );
