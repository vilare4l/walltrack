# Story 11.1: Config Schema & Migration

## Story Info
- **Epic**: Epic 11 - Configuration Centralization & Exit Strategy Simulation
- **Status**: ready
- **Priority**: P0 - Critical
- **Story Points**: 3
- **Depends on**: None

## User Story

**As a** system architect,
**I want** une structure de tables normalisée pour toutes les configurations,
**So that** chaque paramètre est stocké de manière cohérente avec son lifecycle.

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

**migrations/V8__config_centralization.sql:**
```sql
-- ============================================
-- Configuration Centralization Migration
-- ============================================

-- Create status enum
CREATE TYPE walltrack.config_status AS ENUM ('default', 'draft', 'active', 'archived');

-- ============================================
-- Trading Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.trading_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Position Sizing
    base_position_pct DECIMAL(5,2) NOT NULL DEFAULT 2.0,
    max_position_sol DECIMAL(20,8) NOT NULL DEFAULT 1.0,
    min_position_sol DECIMAL(20,8) NOT NULL DEFAULT 0.05,
    high_conviction_multiplier DECIMAL(5,2) NOT NULL DEFAULT 1.5,

    -- Risk-Based Sizing
    sizing_mode TEXT NOT NULL DEFAULT 'risk_based',
    risk_per_trade_pct DECIMAL(5,2) NOT NULL DEFAULT 1.0,

    -- Limits
    max_concurrent_positions INTEGER NOT NULL DEFAULT 5,
    daily_loss_limit_pct DECIMAL(5,2) NOT NULL DEFAULT 5.0,
    daily_loss_limit_enabled BOOLEAN NOT NULL DEFAULT TRUE,

    -- Concentration
    max_concentration_token_pct DECIMAL(5,2) NOT NULL DEFAULT 25.0,
    max_concentration_cluster_pct DECIMAL(5,2) NOT NULL DEFAULT 50.0,
    max_positions_per_cluster INTEGER NOT NULL DEFAULT 3,

    -- Drawdown Tiers
    drawdown_reduction_tiers JSONB NOT NULL DEFAULT '[
        {"threshold_pct": 5, "size_reduction_pct": 0},
        {"threshold_pct": 10, "size_reduction_pct": 25},
        {"threshold_pct": 15, "size_reduction_pct": 50},
        {"threshold_pct": 20, "size_reduction_pct": 100}
    ]'::JSONB,

    -- Thresholds
    score_threshold DECIMAL(4,3) NOT NULL DEFAULT 0.70,
    high_conviction_threshold DECIMAL(4,3) NOT NULL DEFAULT 0.85,

    -- Slippage
    max_slippage_entry_bps INTEGER NOT NULL DEFAULT 100,
    max_slippage_exit_bps INTEGER NOT NULL DEFAULT 150,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    -- Constraints
    CONSTRAINT uq_trading_config_name_status UNIQUE (name, status),
    CONSTRAINT chk_trading_single_active CHECK (
        status != 'active' OR id = (
            SELECT id FROM walltrack.trading_config
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
        )
    )
);

-- ============================================
-- Scoring Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.scoring_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Weights
    wallet_score_weight DECIMAL(4,3) NOT NULL DEFAULT 0.30,
    timing_score_weight DECIMAL(4,3) NOT NULL DEFAULT 0.25,
    market_score_weight DECIMAL(4,3) NOT NULL DEFAULT 0.20,
    cluster_score_weight DECIMAL(4,3) NOT NULL DEFAULT 0.25,

    -- Wallet Scoring
    wallet_win_rate_weight DECIMAL(4,3) NOT NULL DEFAULT 0.40,
    wallet_avg_pnl_weight DECIMAL(4,3) NOT NULL DEFAULT 0.30,
    wallet_consistency_weight DECIMAL(4,3) NOT NULL DEFAULT 0.30,

    -- Timing
    timing_decay_hours INTEGER NOT NULL DEFAULT 4,
    timing_freshness_bonus DECIMAL(4,3) NOT NULL DEFAULT 0.2,

    -- Market
    market_liquidity_threshold DECIMAL(20,2) NOT NULL DEFAULT 10000,
    market_volume_threshold DECIMAL(20,2) NOT NULL DEFAULT 5000,

    -- Cluster Amplification
    cluster_min_sync_ratio DECIMAL(4,3) NOT NULL DEFAULT 0.3,
    cluster_amplification_factor DECIMAL(4,3) NOT NULL DEFAULT 1.2,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_scoring_config_name_status UNIQUE (name, status)
);

-- ============================================
-- Discovery Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.discovery_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Discovery Runs
    run_interval_minutes INTEGER NOT NULL DEFAULT 60,
    max_wallets_per_run INTEGER NOT NULL DEFAULT 100,
    min_wallet_age_days INTEGER NOT NULL DEFAULT 30,

    -- Wallet Criteria
    min_win_rate DECIMAL(4,3) NOT NULL DEFAULT 0.55,
    min_trades INTEGER NOT NULL DEFAULT 10,
    min_avg_pnl_pct DECIMAL(8,2) NOT NULL DEFAULT 20.0,
    max_avg_loss_pct DECIMAL(8,2) NOT NULL DEFAULT -30.0,

    -- Decay Detection
    decay_lookback_days INTEGER NOT NULL DEFAULT 30,
    decay_threshold DECIMAL(4,3) NOT NULL DEFAULT 0.15,
    decay_check_interval_hours INTEGER NOT NULL DEFAULT 24,

    -- Pump Detection
    pump_volume_spike_threshold DECIMAL(8,2) NOT NULL DEFAULT 3.0,
    pump_price_spike_threshold DECIMAL(8,2) NOT NULL DEFAULT 2.0,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_discovery_config_name_status UNIQUE (name, status)
);

-- ============================================
-- Cluster Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.cluster_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Clustering
    min_cluster_size INTEGER NOT NULL DEFAULT 3,
    max_cluster_size INTEGER NOT NULL DEFAULT 20,
    similarity_threshold DECIMAL(4,3) NOT NULL DEFAULT 0.7,

    -- Sync Detection
    sync_time_window_minutes INTEGER NOT NULL DEFAULT 60,
    sync_token_overlap_threshold DECIMAL(4,3) NOT NULL DEFAULT 0.3,

    -- Leader Detection
    leader_min_followers INTEGER NOT NULL DEFAULT 2,
    leader_time_advantage_minutes INTEGER NOT NULL DEFAULT 5,

    -- Amplification
    enable_cluster_amplification BOOLEAN NOT NULL DEFAULT TRUE,
    amplification_max_boost DECIMAL(4,3) NOT NULL DEFAULT 1.5,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_cluster_config_name_status UNIQUE (name, status)
);

-- ============================================
-- Risk Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.risk_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Circuit Breaker
    circuit_breaker_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    circuit_breaker_loss_threshold DECIMAL(5,2) NOT NULL DEFAULT 10.0,
    circuit_breaker_cooldown_minutes INTEGER NOT NULL DEFAULT 60,

    -- Drawdown Limits
    max_drawdown_pct DECIMAL(5,2) NOT NULL DEFAULT 20.0,
    drawdown_lookback_days INTEGER NOT NULL DEFAULT 30,

    -- Order Retry
    max_order_attempts INTEGER NOT NULL DEFAULT 3,
    retry_delay_base_seconds INTEGER NOT NULL DEFAULT 5,
    retry_delay_multiplier DECIMAL(4,2) NOT NULL DEFAULT 3.0,

    -- Emergency
    emergency_exit_threshold_pct DECIMAL(5,2) NOT NULL DEFAULT 50.0,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_risk_config_name_status UNIQUE (name, status)
);

-- ============================================
-- Exit Configuration (Strategy Defaults)
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.exit_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Default Strategy Assignments
    default_strategy_standard_id UUID,
    default_strategy_high_conviction_id UUID,

    -- Time Limits
    default_max_hold_hours INTEGER NOT NULL DEFAULT 168,
    stagnation_hours INTEGER NOT NULL DEFAULT 24,
    stagnation_threshold_pct DECIMAL(5,2) NOT NULL DEFAULT 5.0,

    -- Price History
    price_collection_interval_seconds INTEGER NOT NULL DEFAULT 5,
    price_history_retention_days INTEGER NOT NULL DEFAULT 30,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_exit_config_name_status UNIQUE (name, status)
);

-- ============================================
-- API Configuration
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.api_config (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    status walltrack.config_status NOT NULL DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,

    -- Rate Limits
    dexscreener_requests_per_minute INTEGER NOT NULL DEFAULT 30,
    birdeye_requests_per_minute INTEGER NOT NULL DEFAULT 60,
    jupiter_requests_per_minute INTEGER NOT NULL DEFAULT 100,
    helius_requests_per_minute INTEGER NOT NULL DEFAULT 100,

    -- Timeouts
    api_timeout_seconds INTEGER NOT NULL DEFAULT 10,
    rpc_timeout_seconds INTEGER NOT NULL DEFAULT 30,

    -- Retry
    api_retry_count INTEGER NOT NULL DEFAULT 3,
    api_retry_backoff_seconds INTEGER NOT NULL DEFAULT 1,

    -- Caching
    price_cache_ttl_seconds INTEGER NOT NULL DEFAULT 5,
    token_info_cache_ttl_seconds INTEGER NOT NULL DEFAULT 300,

    -- Metadata
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    updated_by VARCHAR(100) DEFAULT 'system',

    CONSTRAINT uq_api_config_name_status UNIQUE (name, status)
);

-- ============================================
-- Config Audit Log
-- ============================================
CREATE TABLE IF NOT EXISTS walltrack.config_audit_log (
    id BIGSERIAL PRIMARY KEY,
    config_table VARCHAR(50) NOT NULL,
    config_id UUID NOT NULL,
    action VARCHAR(20) NOT NULL,  -- 'create', 'update', 'activate', 'archive', 'delete'

    -- Change details
    old_values JSONB,
    new_values JSONB,
    changed_fields TEXT[],

    -- Context
    reason TEXT,
    performed_by VARCHAR(100) NOT NULL DEFAULT 'system',
    performed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Source
    source_ip VARCHAR(45),
    user_agent TEXT
);

CREATE INDEX idx_config_audit_table ON walltrack.config_audit_log(config_table, performed_at DESC);
CREATE INDEX idx_config_audit_config ON walltrack.config_audit_log(config_id, performed_at DESC);

-- ============================================
-- Version Auto-Increment Trigger
-- ============================================
CREATE OR REPLACE FUNCTION walltrack.increment_config_version()
RETURNS TRIGGER AS $$
BEGIN
    NEW.version := OLD.version + 1;
    NEW.updated_at := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to each config table
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

-- ============================================
-- Insert Default Configurations
-- ============================================

-- Trading Config Defaults
INSERT INTO walltrack.trading_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default trading configuration - do not modify');

INSERT INTO walltrack.trading_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active trading configuration');

-- Scoring Config Defaults
INSERT INTO walltrack.scoring_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default scoring configuration');

INSERT INTO walltrack.scoring_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active scoring configuration');

-- Discovery Config Defaults
INSERT INTO walltrack.discovery_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default discovery configuration');

INSERT INTO walltrack.discovery_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active discovery configuration');

-- Cluster Config Defaults
INSERT INTO walltrack.cluster_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default cluster configuration');

INSERT INTO walltrack.cluster_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active cluster configuration');

-- Risk Config Defaults
INSERT INTO walltrack.risk_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default risk configuration');

INSERT INTO walltrack.risk_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active risk configuration');

-- Exit Config Defaults
INSERT INTO walltrack.exit_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default exit configuration');

INSERT INTO walltrack.exit_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active exit configuration');

-- API Config Defaults
INSERT INTO walltrack.api_config (name, status, description)
VALUES ('System Defaults', 'default', 'System default API configuration');

INSERT INTO walltrack.api_config (name, status, description)
VALUES ('Active Configuration', 'active', 'Currently active API configuration');
```

## Implementation Tasks

- [ ] Create config_status enum type
- [ ] Create all 8 config tables with proper columns
- [ ] Add lifecycle columns to each table
- [ ] Create config_audit_log table
- [ ] Add version auto-increment triggers
- [ ] Insert default configurations
- [ ] Insert active configurations (clone of defaults)
- [ ] Add unique constraints for name+status
- [ ] Create indexes for performance
- [ ] Write validation tests

## Definition of Done

- [ ] All 8 config tables created
- [ ] Status enum enforced
- [ ] Default and active configs exist
- [ ] Version auto-increments on update
- [ ] Audit log table ready
- [ ] Constraints prevent multiple active configs
- [ ] Migration reversible

## File List

### New Files
- `migrations/V8__config_centralization.sql` - Main migration

### Modified Files
- None (new migration)
