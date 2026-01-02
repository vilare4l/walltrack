-- Migration: 004b_config_watchlist_criteria.sql
-- Date: 2025-12-30
-- Story: 3.5 - Auto Watchlist Management
-- Description: Add watchlist criteria configuration parameters to config table

-- Insert watchlist configuration parameters
-- Note: config table schema is (key, value, updated_at) - no category or description columns
-- Using dot-notation in key to simulate categories: "watchlist.min_winrate" instead of category='watchlist', key='min_winrate'
INSERT INTO walltrack.config (key, value)
VALUES
  ('watchlist.min_winrate', '0.70'),
  ('watchlist.min_pnl', '5.0'),
  ('watchlist.min_trades', '10'),
  ('watchlist.max_decay_score', '0.3')
ON CONFLICT (key) DO NOTHING;  -- Don't overwrite if already exists

-- Verify insertion
-- SELECT * FROM walltrack.config WHERE category = 'watchlist' ORDER BY key;

-- Add comment for documentation
COMMENT ON TABLE walltrack.config IS 'System configuration parameters. Category "watchlist" controls auto watchlist evaluation.';

-- Rollback (commented)
-- DELETE FROM walltrack.config WHERE category = 'watchlist';
