-- Migration: 008_exit_strategies.sql
-- Story: 4-4 Exit Strategy Data Model

CREATE TABLE IF NOT EXISTS exit_strategies (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    preset TEXT NOT NULL DEFAULT 'custom',
    is_default BOOLEAN NOT NULL DEFAULT false,
    take_profit_levels JSONB NOT NULL DEFAULT '[]',
    stop_loss DECIMAL(5, 4) NOT NULL DEFAULT 0.5,
    trailing_stop JSONB NOT NULL DEFAULT '{"enabled": false, "activation_multiplier": 2.0, "distance_percentage": 30.0}',
    time_rules JSONB NOT NULL DEFAULT '{"max_hold_hours": null, "stagnation_exit_enabled": false, "stagnation_threshold_pct": 5.0, "stagnation_hours": 24}',
    moonbag JSONB NOT NULL DEFAULT '{"percentage": 0.0, "stop_loss": null}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by TEXT,
    CONSTRAINT valid_preset CHECK (preset IN ('conservative', 'balanced', 'moonbag_aggressive', 'quick_flip', 'diamond_hands', 'custom')),
    CONSTRAINT valid_stop_loss CHECK (stop_loss >= 0.1 AND stop_loss <= 1.0)
);

CREATE INDEX IF NOT EXISTS idx_exit_strategies_preset ON exit_strategies(preset);
CREATE INDEX IF NOT EXISTS idx_exit_strategies_default ON exit_strategies(is_default);

CREATE TABLE IF NOT EXISTS exit_strategy_assignments (
    id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL REFERENCES exit_strategies(id) ON DELETE CASCADE,
    conviction_tier TEXT,
    position_id UUID,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT assignment_target CHECK (
        (conviction_tier IS NOT NULL AND position_id IS NULL) OR
        (conviction_tier IS NULL AND position_id IS NOT NULL)
    ),
    CONSTRAINT valid_tier CHECK (conviction_tier IS NULL OR conviction_tier IN ('high', 'standard'))
);

CREATE INDEX IF NOT EXISTS idx_assignments_tier ON exit_strategy_assignments(conviction_tier) WHERE conviction_tier IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_assignments_active ON exit_strategy_assignments(is_active);

ALTER TABLE exit_strategies ENABLE ROW LEVEL SECURITY;
ALTER TABLE exit_strategy_assignments ENABLE ROW LEVEL SECURITY;
