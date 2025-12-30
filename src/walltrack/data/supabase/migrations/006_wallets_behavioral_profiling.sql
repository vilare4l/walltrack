-- Migration: 006_wallets_behavioral_profiling.sql
-- Date: 2025-12-30
-- Story: 3.3 - Wallet Behavioral Profiling
-- Description: Add behavioral profiling columns to wallets table

-- Add behavioral profiling columns
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS position_size_style TEXT
  CHECK (position_size_style IN ('small', 'medium', 'large'));

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS position_size_avg DECIMAL(20,8)
  CHECK (position_size_avg >= 0);

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS hold_duration_avg INTEGER
  CHECK (hold_duration_avg >= 0);

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS hold_duration_style TEXT
  CHECK (hold_duration_style IN ('scalper', 'day_trader', 'swing_trader', 'position_trader'));

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS behavioral_last_updated TIMESTAMPTZ;

ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS behavioral_confidence TEXT DEFAULT 'unknown'
  CHECK (behavioral_confidence IN ('high', 'medium', 'low', 'unknown'));

-- Add indexes for behavioral queries
CREATE INDEX IF NOT EXISTS idx_wallets_position_size ON walltrack.wallets(position_size_avg DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_hold_duration ON walltrack.wallets(hold_duration_avg);

-- Rollback (commented):
-- DROP INDEX IF EXISTS idx_wallets_position_size;
-- DROP INDEX IF EXISTS idx_wallets_hold_duration;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS position_size_style;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS position_size_avg;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS hold_duration_avg;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS hold_duration_style;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS behavioral_last_updated;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS behavioral_confidence;
