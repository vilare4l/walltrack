-- Migration: 010_config_decay_parameters.sql
-- Date: 2025-12-30
-- Story: 3.4 - Wallet Decay Detection
-- Description: Add decay detection configuration parameters to config table (key-value store)

-- Insert decay detection configuration parameters
-- Using INSERT ... ON CONFLICT to make migration idempotent
INSERT INTO walltrack.config (key, value)
VALUES
    -- Rolling window decay detection (AC1)
    ('decay_rolling_window_size', '20'),  -- Number of recent trades to analyze
    ('decay_min_trades', '20'),  -- Minimum trades required for decay check
    ('decay_threshold', '0.40'),  -- Win rate below 40% triggers "flagged"
    ('decay_recovery_threshold', '0.50'),  -- Win rate above 50% triggers recovery to "ok"

    -- Consecutive loss detection (AC2)
    ('decay_consecutive_loss_threshold', '3'),  -- 3+ consecutive losses triggers "downgraded"

    -- Dormancy detection (AC3)
    ('decay_dormancy_days', '30'),  -- Days without activity before "dormant"

    -- Score adjustments
    ('decay_score_downgrade_decay', '0.80'),  -- 20% score reduction on decay (multiply by 0.80)
    ('decay_score_downgrade_loss', '0.95'),  -- 5% reduction per loss beyond threshold (multiply by 0.95)
    ('decay_score_recovery_boost', '1.10')  -- 10% increase on recovery (multiply by 1.10)
ON CONFLICT (key) DO NOTHING;

-- Verification
DO $$
BEGIN
    IF (SELECT COUNT(*) FROM walltrack.config WHERE key LIKE 'decay_%') >= 9 THEN
        RAISE NOTICE 'SUCCESS: Decay detection configuration parameters added (9 keys)';
    ELSE
        RAISE EXCEPTION 'FAILED: Missing decay configuration parameters';
    END IF;
END $$;

-- Rollback (commented):
-- DELETE FROM walltrack.config WHERE key IN (
--   'decay_rolling_window_size',
--   'decay_min_trades',
--   'decay_threshold',
--   'decay_recovery_threshold',
--   'decay_consecutive_loss_threshold',
--   'decay_dormancy_days',
--   'decay_score_downgrade_decay',
--   'decay_score_downgrade_loss',
--   'decay_score_recovery_boost'
-- );
