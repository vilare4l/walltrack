-- Migration: 005_wallets_schema_fix.sql
-- Date: 2025-12-30
-- Story: 3.2
-- Description: Fix wallets table schema to match Wallet model
--              Removes old discovery fields, adds correct fields

-- Drop old columns that don't match model
ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS discovery_count;
ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS discovery_tokens;
ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS discovered_at;
ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS status;

-- Add correct columns matching Wallet model
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS discovery_date TIMESTAMPTZ DEFAULT NOW();
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS token_source TEXT;
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS decay_status TEXT DEFAULT 'ok';
ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS is_blacklisted BOOLEAN DEFAULT FALSE;

-- Add check constraint for decay_status
ALTER TABLE walltrack.wallets ADD CONSTRAINT chk_decay_status
  CHECK (decay_status IN ('ok', 'flagged', 'downgraded', 'dormant'));

-- Update metrics_confidence constraint (already exists, ensure it's correct)
ALTER TABLE walltrack.wallets DROP CONSTRAINT IF EXISTS chk_metrics_confidence;
ALTER TABLE walltrack.wallets ADD CONSTRAINT chk_metrics_confidence
  CHECK (metrics_confidence IN ('unknown', 'low', 'medium', 'high'));

-- Update default values for score and win_rate to match model
ALTER TABLE walltrack.wallets ALTER COLUMN score SET DEFAULT 0.0;
ALTER TABLE walltrack.wallets ALTER COLUMN win_rate SET DEFAULT 0.0;

-- Make token_source NOT NULL after adding it
-- (First set existing nulls to a placeholder, then add constraint)
UPDATE walltrack.wallets SET token_source = 'UnknownTokenPlaceholder111111111111' WHERE token_source IS NULL;
ALTER TABLE walltrack.wallets ALTER COLUMN token_source SET NOT NULL;

-- Rollback (commented)
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS discovery_date;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS token_source;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS decay_status;
-- ALTER TABLE walltrack.wallets DROP COLUMN IF EXISTS is_blacklisted;
-- ALTER TABLE walltrack.wallets DROP CONSTRAINT IF EXISTS chk_decay_status;
-- ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS discovery_count INTEGER DEFAULT 1;
-- ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS discovery_tokens TEXT[] DEFAULT '{}';
-- ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ DEFAULT NOW();
-- ALTER TABLE walltrack.wallets ADD COLUMN IF NOT EXISTS status TEXT DEFAULT 'pending';
