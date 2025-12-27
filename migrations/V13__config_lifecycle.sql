-- ============================================
-- Configuration Lifecycle Migration
-- Adds name, status, version to existing config tables
-- Migrates from single-row (id=1) to multi-row lifecycle
-- Version: V13
-- Date: 2024-12-26
-- ============================================

-- ============================================
-- PHASE 1: CREATE STATUS ENUM
-- ============================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'config_status' AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'walltrack')) THEN
        CREATE TYPE walltrack.config_status AS ENUM ('default', 'draft', 'active', 'archived');
    END IF;
END$$;

-- ============================================
-- PHASE 2: ADD LIFECYCLE COLUMNS TO ALL CONFIG TABLES
-- ============================================

-- Trading Config
ALTER TABLE walltrack.trading_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- Scoring Config
ALTER TABLE walltrack.scoring_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- Discovery Config
ALTER TABLE walltrack.discovery_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- Cluster Config
ALTER TABLE walltrack.cluster_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- Risk Config
ALTER TABLE walltrack.risk_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- Exit Config
ALTER TABLE walltrack.exit_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- API Config
ALTER TABLE walltrack.api_config
    ADD COLUMN IF NOT EXISTS name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS status walltrack.config_status DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS description TEXT,
    ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS created_by VARCHAR(100) DEFAULT 'system';

-- ============================================
-- PHASE 3: MIGRATE EXISTING ROW TO ACTIVE
-- ============================================

UPDATE walltrack.trading_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.scoring_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.discovery_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.cluster_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.risk_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.exit_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

UPDATE walltrack.api_config
SET name = 'Active Configuration',
    status = 'active',
    description = 'System active configuration'
WHERE id = 1 AND (name IS NULL OR status IS NULL OR status = 'draft');

-- ============================================
-- PHASE 4: REMOVE SINGLE-ROW CONSTRAINTS
-- ============================================

ALTER TABLE walltrack.trading_config DROP CONSTRAINT IF EXISTS trading_config_single;
ALTER TABLE walltrack.scoring_config DROP CONSTRAINT IF EXISTS scoring_config_single;
ALTER TABLE walltrack.discovery_config DROP CONSTRAINT IF EXISTS discovery_config_single;
ALTER TABLE walltrack.cluster_config DROP CONSTRAINT IF EXISTS cluster_config_single;
ALTER TABLE walltrack.risk_config DROP CONSTRAINT IF EXISTS risk_config_single;
ALTER TABLE walltrack.exit_config DROP CONSTRAINT IF EXISTS exit_config_single;
ALTER TABLE walltrack.api_config DROP CONSTRAINT IF EXISTS api_config_single;

-- ============================================
-- PHASE 5: ADD NEW CONSTRAINTS
-- ============================================

-- Make name NOT NULL after setting values
ALTER TABLE walltrack.trading_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.scoring_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.discovery_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.cluster_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.risk_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.exit_config ALTER COLUMN name SET NOT NULL;
ALTER TABLE walltrack.api_config ALTER COLUMN name SET NOT NULL;

-- Make status NOT NULL
ALTER TABLE walltrack.trading_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.scoring_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.discovery_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.cluster_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.risk_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.exit_config ALTER COLUMN status SET NOT NULL;
ALTER TABLE walltrack.api_config ALTER COLUMN status SET NOT NULL;

-- Add unique constraint on name (one name per table, regardless of status)
ALTER TABLE walltrack.trading_config ADD CONSTRAINT IF NOT EXISTS uq_trading_config_name UNIQUE (name);
ALTER TABLE walltrack.scoring_config ADD CONSTRAINT IF NOT EXISTS uq_scoring_config_name UNIQUE (name);
ALTER TABLE walltrack.discovery_config ADD CONSTRAINT IF NOT EXISTS uq_discovery_config_name UNIQUE (name);
ALTER TABLE walltrack.cluster_config ADD CONSTRAINT IF NOT EXISTS uq_cluster_config_name UNIQUE (name);
ALTER TABLE walltrack.risk_config ADD CONSTRAINT IF NOT EXISTS uq_risk_config_name UNIQUE (name);
ALTER TABLE walltrack.exit_config ADD CONSTRAINT IF NOT EXISTS uq_exit_config_name UNIQUE (name);
ALTER TABLE walltrack.api_config ADD CONSTRAINT IF NOT EXISTS uq_api_config_name UNIQUE (name);

-- Partial unique index: only one active per table
CREATE UNIQUE INDEX IF NOT EXISTS idx_trading_config_single_active
    ON walltrack.trading_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_scoring_config_single_active
    ON walltrack.scoring_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovery_config_single_active
    ON walltrack.discovery_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_cluster_config_single_active
    ON walltrack.cluster_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_risk_config_single_active
    ON walltrack.risk_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_config_single_active
    ON walltrack.exit_config((1)) WHERE status = 'active';
CREATE UNIQUE INDEX IF NOT EXISTS idx_api_config_single_active
    ON walltrack.api_config((1)) WHERE status = 'active';

-- ============================================
-- PHASE 6: VERSION AUTO-INCREMENT TRIGGER
-- ============================================

CREATE OR REPLACE FUNCTION walltrack.increment_config_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version := COALESCE(OLD.version, 0) + 1;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create version triggers (replace audit triggers for config changes)
DROP TRIGGER IF EXISTS trg_trading_config_version ON walltrack.trading_config;
CREATE TRIGGER trg_trading_config_version
    BEFORE UPDATE ON walltrack.trading_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_scoring_config_version ON walltrack.scoring_config;
CREATE TRIGGER trg_scoring_config_version
    BEFORE UPDATE ON walltrack.scoring_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_discovery_config_version ON walltrack.discovery_config;
CREATE TRIGGER trg_discovery_config_version
    BEFORE UPDATE ON walltrack.discovery_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_cluster_config_version ON walltrack.cluster_config;
CREATE TRIGGER trg_cluster_config_version
    BEFORE UPDATE ON walltrack.cluster_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_risk_config_version ON walltrack.risk_config;
CREATE TRIGGER trg_risk_config_version
    BEFORE UPDATE ON walltrack.risk_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_exit_config_version ON walltrack.exit_config;
CREATE TRIGGER trg_exit_config_version
    BEFORE UPDATE ON walltrack.exit_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

DROP TRIGGER IF EXISTS trg_api_config_version ON walltrack.api_config;
CREATE TRIGGER trg_api_config_version
    BEFORE UPDATE ON walltrack.api_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

-- ============================================
-- PHASE 7: ADD STATUS INDEX FOR FAST LOOKUPS
-- ============================================

CREATE INDEX IF NOT EXISTS idx_trading_config_status ON walltrack.trading_config(status);
CREATE INDEX IF NOT EXISTS idx_scoring_config_status ON walltrack.scoring_config(status);
CREATE INDEX IF NOT EXISTS idx_discovery_config_status ON walltrack.discovery_config(status);
CREATE INDEX IF NOT EXISTS idx_cluster_config_status ON walltrack.cluster_config(status);
CREATE INDEX IF NOT EXISTS idx_risk_config_status ON walltrack.risk_config(status);
CREATE INDEX IF NOT EXISTS idx_exit_config_status ON walltrack.exit_config(status);
CREATE INDEX IF NOT EXISTS idx_api_config_status ON walltrack.api_config(status);

-- ============================================
-- VERIFICATION
-- ============================================

DO $$
DECLARE
    table_name TEXT;
    active_count INTEGER;
BEGIN
    FOR table_name IN
        SELECT unnest(ARRAY['trading_config', 'scoring_config', 'discovery_config',
                           'cluster_config', 'risk_config', 'exit_config', 'api_config'])
    LOOP
        EXECUTE format('SELECT COUNT(*) FROM walltrack.%I WHERE status = ''active''', table_name)
        INTO active_count;

        IF active_count != 1 THEN
            RAISE WARNING 'Table % should have exactly 1 active config, found %', table_name, active_count;
        END IF;
    END LOOP;

    RAISE NOTICE 'V13 Config Lifecycle Migration completed successfully';
END$$;
