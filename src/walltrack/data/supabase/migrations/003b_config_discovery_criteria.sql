-- Migration: 003b_config_discovery_criteria.sql
-- Date: 2026-01-01
-- Story: 3.1 - Wallet Discovery from Tokens
-- Description: Add wallet discovery criteria configuration parameters to config table

-- Insert discovery configuration parameters
-- Note: config table schema is (key, value, updated_at) - no category or description columns
-- Using dot-notation in key to simulate categories: "discovery.early_entry_minutes" instead of category='discovery', key='early_entry_minutes'
INSERT INTO walltrack.config (key, value)
VALUES
  ('discovery.early_entry_minutes', '30'),
  ('discovery.min_profit_percent', '50')
ON CONFLICT (key) DO NOTHING;  -- Don't overwrite if already exists

-- Verify insertion
-- SELECT * FROM walltrack.config WHERE key LIKE 'discovery.%' ORDER BY key;

-- Add comment for documentation
COMMENT ON TABLE walltrack.config IS 'System configuration parameters. Category "discovery" controls wallet discovery criteria (early entry + profitable exit filters).';

-- Rollback (commented)
-- DELETE FROM walltrack.config WHERE key LIKE 'discovery.%';
