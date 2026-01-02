-- Migration: 004c_config_performance_criteria.sql
-- Date: 2026-01-01
-- Story: 3.2 - Wallet Performance Analysis (AC7)
-- Description: Add performance analysis configurable criteria

-- Insert performance criteria configuration
INSERT INTO walltrack.config (category, key, value, description, created_at, updated_at)
VALUES (
    'performance',
    'min_profit_percent',
    '10.0',
    'Minimum profit percentage for win rate calculation (AC2: 10% default)',
    NOW(),
    NOW()
)
ON CONFLICT (category, key) DO NOTHING;

-- Rollback (commented):
-- DELETE FROM walltrack.config WHERE category = 'performance' AND key = 'min_profit_percent';
