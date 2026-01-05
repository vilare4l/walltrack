-- ============================================================================
-- Migration: 002_exit_strategies_table.sql
-- Description: Create exit_strategies table (catalog pattern)
-- Date: 2025-01-05
-- Pattern: Catalog Pattern
-- Dependencies: 001_config_table.sql
-- ============================================================================

CREATE TABLE IF NOT EXISTS walltrack.exit_strategies (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    name TEXT NOT NULL UNIQUE,
    description TEXT,

    -- Stop Loss
    stop_loss_percent NUMERIC(5,2) NOT NULL DEFAULT 20.00
        CHECK (stop_loss_percent > 0 AND stop_loss_percent <= 100),

    -- Trailing Stop
    trailing_stop_enabled BOOLEAN NOT NULL DEFAULT false,
    trailing_stop_percent NUMERIC(5,2) DEFAULT 15.00
        CHECK (trailing_stop_percent > 0 AND trailing_stop_percent <= 100),
    trailing_activation_threshold_percent NUMERIC(5,2) DEFAULT 20.00
        CHECK (trailing_activation_threshold_percent >= 0),

    -- Scaling Out
    scaling_enabled BOOLEAN NOT NULL DEFAULT true,
    scaling_level_1_percent NUMERIC(5,2) DEFAULT 50.00,
    scaling_level_1_multiplier NUMERIC(4,2) DEFAULT 2.00,
    scaling_level_2_percent NUMERIC(5,2) DEFAULT 25.00,
    scaling_level_2_multiplier NUMERIC(4,2) DEFAULT 3.00,
    scaling_level_3_percent NUMERIC(5,2) DEFAULT 25.00,
    scaling_level_3_multiplier NUMERIC(4,2),  -- NULL = ride forever

    -- Mirror Exit
    mirror_exit_enabled BOOLEAN NOT NULL DEFAULT true,

    -- Status
    is_default BOOLEAN NOT NULL DEFAULT false,
    is_active BOOLEAN NOT NULL DEFAULT true,

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT,
    notes TEXT
);

COMMENT ON TABLE walltrack.exit_strategies IS
'Catalog of reusable exit strategy templates. Pattern: Catalog (DRY - Don''t Repeat Yourself).';

COMMENT ON COLUMN walltrack.exit_strategies.stop_loss_percent IS
'Stop loss % (ex: 20 = -20% max loss). NOT NULL - Every strategy must have stop loss.';

COMMENT ON COLUMN walltrack.exit_strategies.trailing_stop_enabled IS
'Enable trailing stop? Protects profits by following price peak.';

COMMENT ON COLUMN walltrack.exit_strategies.scaling_level_3_multiplier IS
'Level 3 multiplier. NULL = ride forever (no automatic exit).';

COMMENT ON COLUMN walltrack.exit_strategies.is_default IS
'Is this the default strategy? UNIQUE constraint ensures only 1 default.';

-- Indexes
CREATE UNIQUE INDEX IF NOT EXISTS idx_exit_strategies_default
    ON walltrack.exit_strategies(is_default)
    WHERE is_default = true;

CREATE INDEX IF NOT EXISTS idx_exit_strategies_name
    ON walltrack.exit_strategies(name);

CREATE INDEX IF NOT EXISTS idx_exit_strategies_active
    ON walltrack.exit_strategies(is_active)
    WHERE is_active = true;

-- Triggers
CREATE TRIGGER exit_strategies_updated_at
    BEFORE UPDATE ON walltrack.exit_strategies
    FOR EACH ROW
    EXECUTE FUNCTION walltrack.update_updated_at_column();

-- Constraints
ALTER TABLE walltrack.exit_strategies
    ADD CONSTRAINT exit_strategies_scaling_sum_check
    CHECK (
        NOT scaling_enabled OR
        (scaling_level_1_percent + scaling_level_2_percent + scaling_level_3_percent = 100)
    );

-- Default Data
INSERT INTO walltrack.exit_strategies (
    name, description, is_default,
    stop_loss_percent, trailing_stop_enabled,
    scaling_enabled, scaling_level_1_multiplier, scaling_level_2_multiplier,
    mirror_exit_enabled
) VALUES
    ('Default', 'Balanced strategy with 20% SL, scaling at 2x/3x, mirror exit', true,
     20.00, false, true, 2.00, 3.00, true),
    ('Conservative', 'Tight SL (15%), early profit taking at 1.5x/2x', false,
     15.00, false, true, 1.50, 2.00, true),
    ('Aggressive', 'Wide SL (30%), trailing, let winners run to 3x/5x', false,
     30.00, true, true, 3.00, 5.00, true);

-- Rollback
-- DROP TABLE IF EXISTS walltrack.exit_strategies CASCADE;
