-- Migration: 004b_config_watchlist_criteria.sql
-- Date: 2025-12-30
-- Story: 3.5 - Auto Watchlist Management
-- Description: Add watchlist criteria configuration parameters to config table

-- Insert watchlist configuration parameters
-- Note: config table already exists from Epic 2
INSERT INTO walltrack.config (category, key, value, description)
VALUES
  (
    'watchlist',
    'min_winrate',
    '0.70',
    'Minimum win rate to qualify for watchlist (0.0-1.0). Higher = stricter filtering.'
  ),
  (
    'watchlist',
    'min_pnl',
    '5.0',
    'Minimum total PnL in SOL to qualify for watchlist. Higher = more profitable wallets only.'
  ),
  (
    'watchlist',
    'min_trades',
    '10',
    'Minimum number of trades to qualify for watchlist. Higher = more experienced wallets only.'
  ),
  (
    'watchlist',
    'max_decay_score',
    '0.3',
    'Maximum decay score to qualify for watchlist (0.0-1.0). Lower = exclude decaying wallets.'
  )
ON CONFLICT (category, key) DO NOTHING;  -- Don't overwrite if already exists

-- Verify insertion
-- SELECT * FROM walltrack.config WHERE category = 'watchlist' ORDER BY key;

-- Add comment for documentation
COMMENT ON TABLE walltrack.config IS 'System configuration parameters. Category "watchlist" controls auto watchlist evaluation.';

-- Rollback (commented)
-- DELETE FROM walltrack.config WHERE category = 'watchlist';
