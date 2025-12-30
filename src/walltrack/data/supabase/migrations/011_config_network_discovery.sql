-- Migration: 011_config_network_discovery.sql
-- Date: 2025-12-30
-- Epic: 4 - Clustering & Network Discovery
-- Description: Add network discovery configuration parameters

INSERT INTO walltrack.config (category, key, value, description)
VALUES
  (
    'network_discovery',
    'enabled',
    'true',
    'Enable/disable automatic network discovery when wallet is watchlisted. Set to false to pause discovery.'
  ),
  (
    'network_discovery',
    'max_siblings_per_funder',
    '50',
    'Maximum number of sibling wallets to discover per funder. Higher = more discovery but slower.'
  ),
  (
    'network_discovery',
    'min_funding_amount',
    '1.0',
    'Minimum funding amount in SOL to consider a funding relationship. Higher = filter micro-transactions.'
  ),
  (
    'network_discovery',
    'max_network_size',
    '100',
    'Maximum total wallets to discover per session. Circuit breaker to prevent explosion.'
  ),
  (
    'network_discovery',
    'min_funder_contribution',
    '5.0',
    'Minimum SOL a funder must have contributed to watchlisted wallet to trigger discovery. Higher = only significant funders.'
  )
ON CONFLICT (category, key) DO NOTHING;

-- Add comment
COMMENT ON TABLE walltrack.config IS 'System configuration. Categories: watchlist (Story 3.5), network_discovery (Epic 4).';

-- Verification
-- SELECT * FROM walltrack.config WHERE category = 'network_discovery' ORDER BY key;

-- Rollback (commented)
-- DELETE FROM walltrack.config WHERE category = 'network_discovery';
