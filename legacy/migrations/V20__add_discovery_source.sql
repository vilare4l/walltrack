-- Epic 14 Story 14-5: Add discovery source tracking to wallets table
-- Tracks origin of wallet discovery: pump_discovery, cluster_expansion, funding_link, manual

ALTER TABLE wallets
ADD COLUMN IF NOT EXISTS discovery_source VARCHAR(20) DEFAULT NULL;

ALTER TABLE wallets
ADD COLUMN IF NOT EXISTS discovered_from_wallet VARCHAR(44) DEFAULT NULL;

ALTER TABLE wallets
ADD COLUMN IF NOT EXISTS discovered_from_token VARCHAR(44) DEFAULT NULL;

-- Add index for filtering by discovery source
CREATE INDEX IF NOT EXISTS idx_wallets_discovery_source
ON wallets(discovery_source)
WHERE discovery_source IS NOT NULL;

-- Add foreign key constraint for discovered_from_wallet (optional, self-referential)
-- Not enforced to allow flexibility during cluster expansion
-- ALTER TABLE wallets
-- ADD CONSTRAINT fk_discovered_from_wallet
-- FOREIGN KEY (discovered_from_wallet) REFERENCES wallets(address);

COMMENT ON COLUMN wallets.discovery_source IS
'Origin of wallet discovery: pump_discovery, cluster_expansion, funding_link, manual';

COMMENT ON COLUMN wallets.discovered_from_wallet IS
'Parent wallet address if discovered via cluster_expansion';

COMMENT ON COLUMN wallets.discovered_from_token IS
'Token mint address if discovered via pump_discovery';
