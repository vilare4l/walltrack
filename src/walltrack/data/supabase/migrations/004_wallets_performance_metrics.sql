-- Migration: 004_wallets_performance_metrics.sql
-- Date: 2025-12-30
-- Story: 3.2 - Wallet Performance Analysis
-- Description: Add performance metrics columns to wallets table

-- Add performance metrics columns
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS win_rate DECIMAL(5,2);
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS pnl_total DECIMAL(20,8);
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS entry_delay_seconds INTEGER;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS total_trades INTEGER DEFAULT 0;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS metrics_last_updated TIMESTAMPTZ;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS metrics_confidence TEXT DEFAULT 'unknown';

-- Add indexes for performance queries
CREATE INDEX IF NOT EXISTS idx_wallets_win_rate ON walltrack.wallets(win_rate DESC);
CREATE INDEX IF NOT EXISTS idx_wallets_pnl_total ON walltrack.wallets(pnl_total DESC);

-- Add constraint for metrics_confidence values
ALTER TABLE walltrack.wallets ADD CONSTRAINT chk_metrics_confidence
  CHECK (metrics_confidence IN ('unknown', 'low', 'medium', 'high'));

-- Rollback (commented):
-- DROP INDEX IF EXISTS idx_wallets_win_rate;
-- DROP INDEX IF EXISTS idx_wallets_pnl_total;
-- ALTER TABLE walltrack.wallets DROP CONSTRAINT IF EXISTS chk_metrics_confidence;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS win_rate;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS pnl_total;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS entry_delay_seconds;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS total_trades;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS metrics_last_updated;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS metrics_confidence;
