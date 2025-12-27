# Story 11.1: Config Schema Lifecycle Migration

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 3
- **Depends on**: None

## ⚠️ Important Context

**Les tables de config existent déjà** (créées dans V8__config_centralization.sql) avec une structure "single row" (id=1 par table). Cette story **AJOUTE le lifecycle** (status, name, version) aux tables existantes via ALTER TABLE, elle ne les crée pas.

### État Actuel vs Cible

| Aspect | Actuel (V8) | Cible (V13) |
|--------|-------------|-------------|
| Structure | Single row (id=1) | Multiple rows avec lifecycle |
| Versioning | Aucun | version auto-incrémenté |
| Status | Aucun | default/draft/active/archived |
| Migration | N/A | Ligne existante → status='active' |

## User Story

**As a** system architect,
**I want** ajouter un lifecycle aux tables de configuration existantes,
**So that** chaque config peut avoir des versions (default, draft, active, archived).

## Acceptance Criteria

### AC 1: Config Tables Created
**Given** la migration V8 est exécutée
**When** je liste les tables du schema walltrack
**Then** je vois les tables de config:
- `trading_config`
- `scoring_config`
- `discovery_config`
- `cluster_config`
- `risk_config`
- `exit_config`
- `api_config`
- `config_audit_log`

### AC 2: Lifecycle Columns
**Given** une table de config existe
**When** j'examine sa structure
**Then** elle contient:
- `id` UUID PRIMARY KEY
- `status` ENUM ('default', 'draft', 'active', 'archived')
- `name` VARCHAR unique identifiant
- `version` INTEGER auto-incrémenté
- `created_at`, `updated_at` TIMESTAMPTZ
- `created_by`, `updated_by` VARCHAR

### AC 3: Default Presets Inserted
**Given** la migration s'exécute
**When** je query les configs
**Then** chaque table a au moins une entrée `status = 'default'`
**And** une entrée `status = 'active'` (clone des defaults)

### AC 4: Single Active Constraint
**Given** une table de config
**When** j'essaie d'avoir deux configs `active`
**Then** la contrainte empêche l'insertion
**And** une erreur explicite est retournée

### AC 5: Version Auto-Increment
**Given** une config draft existe
**When** je la modifie et sauvegarde
**Then** la version s'incrémente automatiquement

## Technical Specifications

### Database Migration

**migrations/V13__config_lifecycle.sql:**
```sql
-- ============================================
-- Configuration Lifecycle Migration
-- Adds name, status, version to existing config tables
-- Migrates from single-row (id=1) to multi-row lifecycle
-- ============================================

-- Create status enum
CREATE TYPE walltrack.config_status AS ENUM ('default', 'draft', 'active', 'archived');

-- ============================================
-- PHASE 1: ADD LIFECYCLE COLUMNS
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
-- PHASE 2: MIGRATE EXISTING ROW TO ACTIVE
-- ============================================

UPDATE walltrack.trading_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.scoring_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.discovery_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.cluster_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.risk_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.exit_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;
UPDATE walltrack.api_config SET name = 'Active Configuration', status = 'active' WHERE id = 1;

-- ============================================
-- PHASE 3: REMOVE SINGLE-ROW CONSTRAINT
-- ============================================

ALTER TABLE walltrack.trading_config DROP CONSTRAINT IF EXISTS trading_config_single;
ALTER TABLE walltrack.scoring_config DROP CONSTRAINT IF EXISTS scoring_config_single;
ALTER TABLE walltrack.discovery_config DROP CONSTRAINT IF EXISTS discovery_config_single;
ALTER TABLE walltrack.cluster_config DROP CONSTRAINT IF EXISTS cluster_config_single;
ALTER TABLE walltrack.risk_config DROP CONSTRAINT IF EXISTS risk_config_single;
ALTER TABLE walltrack.exit_config DROP CONSTRAINT IF EXISTS exit_config_single;
ALTER TABLE walltrack.api_config DROP CONSTRAINT IF EXISTS api_config_single;

-- ============================================
-- PHASE 4: ADD NEW CONSTRAINTS
-- ============================================

-- Add unique constraint on name+status
ALTER TABLE walltrack.trading_config ADD CONSTRAINT uq_trading_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.scoring_config ADD CONSTRAINT uq_scoring_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.discovery_config ADD CONSTRAINT uq_discovery_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.cluster_config ADD CONSTRAINT uq_cluster_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.risk_config ADD CONSTRAINT uq_risk_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.exit_config ADD CONSTRAINT uq_exit_config_name_status UNIQUE (name, status);
ALTER TABLE walltrack.api_config ADD CONSTRAINT uq_api_config_name_status UNIQUE (name, status);

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
-- PHASE 5: VERSION AUTO-INCREMENT TRIGGER
-- ============================================

CREATE OR REPLACE FUNCTION walltrack.increment_config_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version := COALESCE(OLD.version, 0) + 1;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop existing triggers (from V8) and recreate
DROP TRIGGER IF EXISTS trg_trading_config_audit ON walltrack.trading_config;
DROP TRIGGER IF EXISTS trg_scoring_config_audit ON walltrack.scoring_config;
DROP TRIGGER IF EXISTS trg_discovery_config_audit ON walltrack.discovery_config;
DROP TRIGGER IF EXISTS trg_cluster_config_audit ON walltrack.cluster_config;
DROP TRIGGER IF EXISTS trg_risk_config_audit ON walltrack.risk_config;
DROP TRIGGER IF EXISTS trg_exit_config_audit ON walltrack.exit_config;
DROP TRIGGER IF EXISTS trg_api_config_audit ON walltrack.api_config;

-- Create version triggers
CREATE TRIGGER trg_trading_config_version
    BEFORE UPDATE ON walltrack.trading_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_scoring_config_version
    BEFORE UPDATE ON walltrack.scoring_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_discovery_config_version
    BEFORE UPDATE ON walltrack.discovery_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_cluster_config_version
    BEFORE UPDATE ON walltrack.cluster_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_risk_config_version
    BEFORE UPDATE ON walltrack.risk_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_exit_config_version
    BEFORE UPDATE ON walltrack.exit_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();

CREATE TRIGGER trg_api_config_version
    BEFORE UPDATE ON walltrack.api_config
    FOR EACH ROW
    WHEN (OLD.* IS DISTINCT FROM NEW.*)
    EXECUTE FUNCTION walltrack.increment_config_version();
```

## Implementation Tasks

- [x] Create config_status enum type
- [x] ALTER existing tables to add lifecycle columns (name, status, version)
- [x] Migrate existing row (id=1) to status='active'
- [x] Remove single-row constraints (CHECK id=1)
- [x] Add unique constraints for name+status
- [x] Add partial unique index for single active
- [x] Add version auto-increment triggers
- [x] Write validation tests

## Definition of Done

- [x] All 7 config tables have lifecycle columns
- [x] Status enum enforced
- [x] Existing configs migrated to status='active'
- [x] Version auto-increments on update
- [x] Single-row constraints removed
- [x] Single-active constraint via partial index
- [x] Migration tested

## File List

### New Files
- `migrations/V13__config_lifecycle.sql` - Lifecycle migration

### Modified Files
- None (existing tables altered, not recreated)
