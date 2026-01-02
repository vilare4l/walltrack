-- Migration: 006b_config_behavioral_criteria.sql
-- Date: 2026-01-01
-- Story: 3.3 - Wallet Behavioral Profiling (Config Criteria)
-- Description: Insert behavioral profiling criteria into config table

-- Position Size Thresholds
INSERT INTO walltrack.config (key, value) VALUES
  ('behavioral.position_size_small_max', '0.5'),
  ('behavioral.position_size_medium_max', '2.0')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Hold Duration Thresholds (in seconds)
INSERT INTO walltrack.config (key, value) VALUES
  ('behavioral.hold_duration_scalper_max', '3600'),      -- 1 hour
  ('behavioral.hold_duration_day_trader_max', '86400'),  -- 24 hours
  ('behavioral.hold_duration_swing_trader_max', '604800') -- 7 days
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Confidence Level Thresholds (in number of trades)
INSERT INTO walltrack.config (key, value) VALUES
  ('behavioral.confidence_high_min', '20'),
  ('behavioral.confidence_medium_min', '10'),
  ('behavioral.confidence_low_min', '5')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;

-- Rollback (commented):
-- DELETE FROM walltrack.config WHERE key LIKE 'behavioral.%';
